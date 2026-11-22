"""Offline by default; --connect inspects MySQL using read-only transactions.

Never changes tables, data, Alembic versions, SQLite settings, or migration jobs.
Credentials come from the named environment variable or a hidden local prompt,
never a CLI argument or saved report.
"""
import argparse
from datetime import datetime, timezone
from dataclasses import dataclass
import getpass
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import struct
import sys
import tomllib
from uuid import uuid4

PROJECT=Path(__file__).resolve().parents[3]
SCHEMA=PROJECT/'docs/deployment/mysql_handoff_v2/schema_multi_user.json'


class CheckError(ValueError):
    def __init__(self,code,*,driver_error_code=None):
        self.code=code
        self.driver_error_code=driver_error_code if type(driver_error_code) is int else None
        super().__init__(code)


@dataclass(frozen=True)
class ConnectionConfig:
    host:str;port:int;name:str;username:str;password_env:str
    connect_timeout:int;read_timeout:int;tls_mode:str;ca_file:str
    password_file:str=''


def load_config(path):
    try:
        raw=Path(path).read_bytes()
        if len(raw)>16384:raise ValueError()
        data=tomllib.loads(raw.decode('utf-8'))
        if set(data)!={'schema_version','database','tls'} or type(data['schema_version']) is not int or data['schema_version']!=1:raise ValueError()
        db=data['database'];tls=data['tls']
        required={'host','port','name','username','password_env','connect_timeout','read_timeout'}
        if type(db) is not dict or not required<=set(db) or set(db)-required-{'password_file'}:raise ValueError()
        if type(db.get('password_file','')) is not str:raise ValueError()
        if type(tls) is not dict or set(tls)!={'mode','ca_file'}:raise ValueError()
        if any(type(db[k]) is not str for k in ('host','name','username','password_env')) or type(tls['ca_file']) is not str:raise ValueError()
        if db['host'] and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,252}',db['host']):raise ValueError()
        if not re.fullmatch(r'[A-Za-z0-9_]{1,64}',db['name']):raise ValueError()
        if db['username'] and not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',db['username']):raise ValueError()
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{1,79}',db['password_env']):raise ValueError()
        if type(db['port']) is not int or not 1<=db['port']<=65535:raise ValueError()
        if any(type(db[k]) is not int or not 1<=db[k]<=30 for k in ('connect_timeout','read_timeout')):raise ValueError()
        if tls['mode'] not in ('verify_identity','verify_ca','disabled'):raise ValueError()
        if tls['mode']=='verify_ca' and not tls['ca_file'].strip():raise ValueError()
        if tls['mode']=='disabled' and tls['ca_file']:raise ValueError()
        config=ConnectionConfig(db['host'],db['port'],db['name'],db['username'],db['password_env'],db['connect_timeout'],db['read_timeout'],tls['mode'],tls['ca_file'],db.get('password_file',''))
        if config.password_file:secret_path(config)
        return config
    except (ValueError,KeyError,TypeError,OSError) as error:
        # Never echo unknown fields, passwords, URLs or TOML parser snippets.
        raise CheckError('mysql_config_invalid_or_missing') from None


def private_ip(host):
    try:address=ipaddress.ip_address(host)
    except ValueError:return False
    return address.is_loopback or any(address.version==net.version and address in net for net in (
        ipaddress.ip_network('10.0.0.0/8'),ipaddress.ip_network('172.16.0.0/12'),
        ipaddress.ip_network('192.168.0.0/16'),ipaddress.ip_network('fc00::/7')))


def pending(config,environ,allow_insecure=False):
    items=[]
    if not config.host:items.append('mysql_host_missing')
    if not config.username:items.append('mysql_username_missing')
    if not environ.get(config.password_env) and not config.password_file:items.append('mysql_password_missing')
    if config.password_file and not environ.get(config.password_env) and not secret_path(config).is_file():items.append('mysql_protected_password_missing')
    if importlib.util.find_spec('pymysql') is None:items.append('mysql_driver_missing')
    if config.ca_file and not ca_path(config).is_file():items.append('mysql_ca_file_missing')
    if config.tls_mode=='disabled' and not (allow_insecure and private_ip(config.host)):items.append('mysql_insecure_lan_not_explicitly_allowed')
    return items


def secret_path(config):
    path=(PROJECT/config.password_file).resolve()
    if not path.is_relative_to(PROJECT.resolve()/'var/secrets') or path.is_dir():
        raise CheckError('mysql_protected_password_path_invalid')
    return path


def credential_binding(config):
    return {'host':config.host.lower(),'port':config.port,'database':config.name,'username':config.username}


def password_for(config,environ):
    if environ.get(config.password_env):return environ[config.password_env]
    if config.password_file:
        from .protected_password import load_password,SecretError
        try:return load_password(secret_path(config),credential_binding(config))
        except SecretError as error:raise CheckError(error.code) from None
    raise CheckError('mysql_password_missing')


def ca_path(config):
    path=Path(config.ca_file)
    return path if path.is_absolute() else PROJECT/path


def connect_options(config,password):
    options=dict(host=config.host,port=config.port,user=config.username,password=password,database=config.name,
                 charset='utf8mb4',collation='utf8mb4_0900_bin',connect_timeout=config.connect_timeout,
                 read_timeout=config.read_timeout,write_timeout=config.read_timeout,autocommit=False,local_infile=False)
    if config.tls_mode in ('verify_identity', 'verify_ca'):
        if config.tls_mode == 'verify_ca' and not config.ca_file.strip():
            raise CheckError('mysql_verify_ca_requires_explicit_ca')
        try:context=ssl.create_default_context(cafile=str(ca_path(config)) if config.ca_file else None)
        except (OSError,ValueError,ssl.SSLError):raise CheckError('mysql_ca_invalid') from None
        context.check_hostname=config.tls_mode=='verify_identity';context.verify_mode=ssl.CERT_REQUIRED
        options['ssl']=context
    else:options['ssl_disabled']=True
    return options


def probe_endpoint(config):
    """Inspect MySQL greeting/TLS without a username, password, SQL or auth packet."""
    if not config.host:
        raise CheckError('mysql_host_missing')
    if config.tls_mode not in ('verify_identity', 'verify_ca'):
        raise CheckError('mysql_probe_requires_verified_tls')
    context = connect_options(config, '')['ssl']
    with socket.create_connection((config.host, config.port), config.connect_timeout) as stream:
        stream.settimeout(config.read_timeout)
        def read_exact(count):
            data = b''
            while len(data) < count:
                part = stream.recv(count - len(data))
                if not part:
                    raise CheckError('mysql_probe_greeting_incomplete')
                data += part
            return data
        header = read_exact(4)
        length = int.from_bytes(header[:3], 'little')
        if header[3] != 0 or not 16 <= length <= 65536:
            raise CheckError('mysql_probe_invalid_greeting')
        packet = read_exact(length)
        if packet[0] != 10:
            raise CheckError('mysql_probe_not_protocol_10')
        end = packet.find(b'\0', 1)
        if not 1 < end <= 128 or len(packet) < end + 21:
            raise CheckError('mysql_probe_invalid_greeting')
        version = packet[1:end].decode('ascii', errors='replace')
        flags_offset = end + 14
        lower = int.from_bytes(packet[flags_offset:flags_offset + 2], 'little')
        result = {'status': 'mysql_endpoint_probed', 'network_connected': True,
                  'server_greeting_version': version, 'mysql_ssl_advertised': bool(lower & 0x0800),
                  'tls_verified': False, 'tls_verification_mode': config.tls_mode,
                  'tls_identity_verified': False, 'authentication_attempted': False,
                  'sql_executed': False, 'runtime_switch_performed': False}
        if not result['mysql_ssl_advertised']:
            result['status'] = 'mysql_tls_configuration_required'
            return result
        # SSLRequest only: do not send the subsequent HandshakeResponse41/auth.
        payload = struct.pack('<IIB23s', 0x0200 | 0x0800 | 0x8000, 16 * 1024 * 1024, 45, b'')
        stream.sendall(len(payload).to_bytes(3, 'little') + b'\x01' + payload)
        try:
            with context.wrap_socket(stream, server_hostname=config.host) as secured:
                result['tls_verified'] = True
                result['tls_identity_verified'] = config.tls_mode == 'verify_identity'
                result['tls_version'] = secured.version()
        except ssl.SSLCertVerificationError as error:
            result['status'] = 'mysql_tls_ca_or_identity_review_required'
            result['tls_verify_code'] = getattr(error, 'verify_code', None)
            message = getattr(error, 'verify_message', '').lower()
            result['tls_verification_reason'] = (
                'hostname_mismatch' if 'hostname mismatch' in message or 'ip address mismatch' in message
                else 'certificate_expired' if 'expired' in message
                else 'certificate_not_yet_valid' if 'not yet valid' in message
                else 'certificate_chain_not_trusted' if 'issuer' in message or 'self-signed' in message
                else 'certificate_validation_failed')
        except ssl.SSLError:
            result['status'] = 'mysql_tls_handshake_failed'
        return result


def check_expression(value, *, metadata=False):
    """Parse only the IN/IS NULL/equality/>= AND grammar used in frozen 0008.

    Preserve string values and grouping; don't erase arbitrary parentheses/OR.
    MySQL's backticks and utf8mb4 string introducers are representations only.
    Some MySQL-compatible INFORMATION_SCHEMA implementations additionally escape
    the OUTER quotes of introduced identifier-like string literals. Recognize
    exactly that metadata token (one/two matching slash layers), never globally
    unescape text, change literal values or normalize executable source SQL.
    """
    if type(value) is not str or len(value)>8192:raise ValueError('Unsupported CHECK')
    escaped_literal = (r"_utf8mb4(?P<metadata_slashes>\\{1,2})'(?P<metadata_value>[A-Za-z0-9_]+)(?P=metadata_slashes)'|"
                       if metadata else '')
    pattern=re.compile(escaped_literal+r"\s+|`[A-Za-z_][A-Za-z0-9_]*`|_utf8mb4(?=')|'(?:''|[^'])*'|>=|=|[A-Za-z_][A-Za-z0-9_]*|[0-9]+|[(),]",re.I)
    tokens=[];at=0
    while at<len(value):
        match=pattern.match(value,at)
        if not match:raise ValueError('Unsupported CHECK')
        token=match.group();at=match.end()
        if metadata and match.group('metadata_value') is not None:
            tokens.append("'"+match.group('metadata_value')+"'")
            continue
        if token.isspace() or token.lower()=='_utf8mb4':continue
        tokens.append(token if token.startswith("'") else token.strip('`').lower())
    index=0
    def take(expected=None):
        nonlocal index
        if index>=len(tokens) or expected is not None and tokens[index]!=expected:raise ValueError('Unsupported CHECK')
        token=tokens[index];index+=1;return token
    def expression():
        atoms=[]
        while True:
            if index<len(tokens) and tokens[index]=='(':
                take('(');atoms.extend(expression());take(')')
            else:
                name=take()
                if not re.fullmatch('[a-z_][a-z0-9_]*',name):raise ValueError('Unsupported CHECK')
                op=take()
                if op=='in':
                    take('(');values=[]
                    while True:
                        literal=take()
                        if not literal.startswith("'"):raise ValueError('Unsupported CHECK')
                        values.append(literal)
                        if index<len(tokens) and tokens[index]==',':take(',')
                        else:break
                    take(')');atom=(name,'in',tuple(sorted(set(values))))
                elif op=='is':take('null');atom=(name,'is',None)
                elif op in ('>=','='):
                    literal=take()
                    if op=='>=' and not literal.isdecimal() or op=='=' and not literal.startswith("'"):raise ValueError('Unsupported CHECK')
                    atom=(name,op,literal)
                else:raise ValueError('Unsupported CHECK')
                atoms.append(atom)
            if index<len(tokens) and tokens[index]=='and':take('and')
            else:return atoms
    parsed=frozenset(expression())
    if index!=len(tokens):raise ValueError('Unsupported CHECK')
    return parsed


def type_matches(expected,actual):
    actual=actual.lower()
    if expected=='BOOLEAN':return actual=='tinyint(1)'
    if expected=='INTEGER':return actual in ('int','int(11)')
    return expected.lower()==actual


def version_review(version):
    """Allow schema inspection, not runtime certification, on 8.0.16+ / 8.4.

    MySQL before 8.0.16 did not enforce the CHECKs required by this schema.
    The handoff target remains 8.4; inspecting 8.0 does not upgrade that claim.
    """
    match=re.match(r'^(\d+)\.(\d+)\.(\d+)(?:\D|$)',version)
    if not match or 'mariadb' in version.lower():
        raise CheckError('mysql_version_not_supported_for_inspection')
    major,minor,patch=map(int,match.groups())
    if (major,minor)==(8,4):
        return []
    if (major,minor)==(8,0) and patch>=16:
        return ['mysql_8_0_differs_from_handoff_target_8_4']
    raise CheckError('mysql_version_not_supported_for_inspection')


def inspect_schema(cursor,config,snapshot):
    """SELECTs only; returns structural differences, never user/source contents."""
    name=config.name;differences=[]
    def query(sql,params=(name,)):
        cursor.execute(sql,params);return cursor.fetchall()
    tables=query('SELECT TABLE_NAME, ENGINE, TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE=\'BASE TABLE\'')
    actual={row[0]:row[1:] for row in tables};expected={t['name']:t for t in snapshot['tables']}
    for table in sorted(set(actual)^set(expected)):differences.append({'table':table,'kind':'missing_or_extra_table'})
    columns=query('SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA, COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME, ORDINAL_POSITION')
    column_map={table:[] for table in actual}
    for table,*column in columns:column_map.setdefault(table,[]).append(column)
    key_rows=query("SELECT k.TABLE_NAME, tc.CONSTRAINT_TYPE, k.CONSTRAINT_NAME, k.COLUMN_NAME, k.REFERENCED_TABLE_SCHEMA, k.REFERENCED_TABLE_NAME, k.REFERENCED_COLUMN_NAME FROM information_schema.TABLE_CONSTRAINTS tc JOIN information_schema.KEY_COLUMN_USAGE k ON tc.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA AND tc.TABLE_NAME=k.TABLE_NAME AND tc.CONSTRAINT_NAME=k.CONSTRAINT_NAME WHERE tc.CONSTRAINT_SCHEMA=%s ORDER BY k.TABLE_NAME, k.CONSTRAINT_NAME, k.ORDINAL_POSITION")
    keys={}
    for table,kind,key,col,ref_schema,ref_table,ref_col in key_rows:
        keys.setdefault((table,kind,key),[]).append((col,ref_schema,ref_table,ref_col))
    checks=query("SELECT tc.TABLE_NAME, cc.CHECK_CLAUSE, tc.ENFORCED FROM information_schema.CHECK_CONSTRAINTS cc JOIN information_schema.TABLE_CONSTRAINTS tc ON tc.CONSTRAINT_SCHEMA=cc.CONSTRAINT_SCHEMA AND tc.CONSTRAINT_NAME=cc.CONSTRAINT_NAME WHERE tc.CONSTRAINT_SCHEMA=%s")
    rules=query('SELECT TABLE_NAME, UPDATE_RULE, DELETE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=%s')
    for table,update,delete in rules:
        if update!='RESTRICT' or delete!='RESTRICT':differences.append({'table':table,'kind':'foreign_key_action_mismatch'})
    for table,definition in expected.items():
        if table not in actual:continue
        if tuple(actual[table])!=('InnoDB','utf8mb4_0900_bin'):differences.append({'table':table,'kind':'engine_or_collation_mismatch',
                'expected':{'engine':'InnoDB','collation':'utf8mb4_0900_bin'},'actual':{'engine':actual[table][0],'collation':actual[table][1]}})
        got=column_map.get(table,[])
        if [c[0] for c in got]!=[c['name'] for c in definition['columns']]:differences.append({'table':table,'kind':'column_order_or_membership_mismatch',
                'expected':[c['name'] for c in definition['columns']],'actual':[c[0] for c in got]})
        for col,want in zip(got,definition['columns']):
            column,column_type,nullable,default,extra,collation=col
            auto='auto_increment' in extra.lower()
            if column!=want['name'] or not type_matches(want['mysql_type'],column_type) or (nullable=='YES')!=want['nullable'] or default is not None or auto!=want['autoincrement'] or extra not in ('','auto_increment') or (want['mysql_type'].startswith('VARCHAR(') and collation!='utf8mb4_0900_bin'):
                differences.append({'table':table,'column':want['name'],'kind':'column_definition_mismatch',
                    'expected':{'type':want['mysql_type'],'nullable':want['nullable'],'default':None,'autoincrement':want['autoincrement'],
                                'collation':'utf8mb4_0900_bin' if want['mysql_type'].startswith('VARCHAR(') else None},
                    'actual':{'column':column,'type':column_type,'nullable':nullable=='YES','default':default,'extra':extra,'collation':collation}})
        pk=[tuple(row[0] for row in rows) for (t,kind,_),rows in keys.items() if t==table and kind=='PRIMARY KEY']
        unique={tuple(row[0] for row in rows) for (t,kind,_),rows in keys.items() if t==table and kind=='UNIQUE'}
        fks={(tuple(r[0] for r in rows),tuple(r[1] for r in rows),tuple(r[2] for r in rows),tuple(r[3] for r in rows)) for (t,kind,_),rows in keys.items() if t==table and kind=='FOREIGN KEY'}
        want_fks={(tuple(f['columns']),(name,)*len(f['columns']),(f['target_table'],)*len(f['columns']),tuple(f['target_columns'])) for f in definition['foreign_keys']}
        if pk!=[tuple(definition['primary_key'])] or unique!={tuple(u) for u in definition['unique']} or fks!=want_fks:differences.append({'table':table,'kind':'key_constraint_mismatch',
                'expected':{'primary_key':[definition['primary_key']],'unique':definition['unique'],'foreign_keys':sorted(want_fks,key=repr)},
                'actual':{'primary_key':pk,'unique':sorted(unique,key=repr),'foreign_keys':sorted(fks,key=repr)}})
        try:
            actual_checks=[clause for t,clause,enforced in checks if t==table]
            if any(enforced!='YES' for t,_,enforced in checks if t==table) or len(actual_checks)!=len(definition['checks']) or {check_expression(c,metadata=True) for c in actual_checks}!={check_expression(c) for c in definition['checks']}:raise ValueError()
        except ValueError:differences.append({'table':table,'kind':'check_constraint_mismatch_or_unsupported',
                'expected':definition['checks'],'actual':[{'clause':clause,'enforced':enforced} for t,clause,enforced in checks if t==table]})
    nonempty=[]
    # Only request the constant 1; no usernames, hashes, source or reports are read.
    if set(actual)==set(expected):
        for table in sorted(expected):
            cursor.execute(f'SELECT 1 FROM `{name}`.`{table}` LIMIT 1')
            if cursor.fetchone() is not None:nonempty.append(table)
    return {'expected_tables':len(expected),'actual_tables':len(actual),'differences':differences[:100],
            'differences_total':len(differences),'nonempty_tables':nonempty,
            'prepared_empty_database':not nonempty if set(actual)==set(expected) else None}


def connect_check(config,password,snapshot,connector):
    connection=connector(**connect_options(config,password))
    try:
        with connection.cursor() as cursor:
            cursor.execute('SET SESSION TRANSACTION READ ONLY')
            cursor.execute('SELECT VERSION(), DATABASE(), @@SESSION.sql_mode')
            version,database,sql_mode=cursor.fetchone()
            warnings=version_review(version)
            if database!=config.name:raise CheckError('mysql_database_mismatch')
            if not {'STRICT_TRANS_TABLES','STRICT_ALL_TABLES'}&set(sql_mode.split(',')):raise CheckError('mysql_strict_mode_required')
            cursor.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
            row=cursor.fetchone();cipher=row[1] if row else ''
            if config.tls_mode in ('verify_identity','verify_ca') and not cipher:raise CheckError('mysql_tls_not_negotiated')
            result=inspect_schema(cursor,config,snapshot)
            return {'status':'mysql_prepared_schema_verified' if not result['differences_total'] and result['prepared_empty_database'] else 'mysql_schema_review_required',
                    'network_connected':True,'server_version':version,'handoff_target_version':'8.4',
                    'version_warnings':warnings,'application_compatibility_status':'not_validated',
                    'tls_verified':config.tls_mode in ('verify_identity','verify_ca'),
                    'tls_verification_mode':config.tls_mode,'tls_identity_verified':config.tls_mode=='verify_identity',
                    'tls_encrypted':bool(cipher),'schema':result,'runtime_switch_performed':False,'active_business_backend':'not_inspected','read_only':True}
    finally:
        try:connection.rollback()
        finally:connection.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,default=PROJECT/'configs/mysql_connection.local.toml')
    network = parser.add_mutually_exclusive_group()
    network.add_argument('--connect',action='store_true')
    network.add_argument('--probe',action='store_true',help='Greeting/TLS only; no credentials or SQL')
    parser.add_argument('--password-prompt',action='store_true',help='Hidden local password prompt for read-only --connect')
    parser.add_argument('--save-report',action='store_true',help='Save sanitized inspection result under var/mysql-inspection-reports')
    parser.add_argument('--allow-insecure-lan',action='store_true');args=parser.parse_args(argv)
    if args.password_prompt and not args.connect:parser.error('--password-prompt requires --connect')
    def emit(result):
        if args.save_report:
            try:
                folder=PROJECT/'var/mysql-inspection-reports';folder.mkdir(parents=True,exist_ok=True)
                path=folder/(uuid4().hex+'.json')
                result['created_at']=datetime.now(timezone.utc).isoformat()
                result['report_file']=str(path)
                with path.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
            except OSError:result['report_save_failed']=True
        print(json.dumps(result,ensure_ascii=True,indent=2))
    try:
        config=load_config(args.config)
        if args.probe:
            result = probe_endpoint(config)
            emit(result)
            return 0 if result['tls_verified'] else 2
        missing=pending(config,os.environ,args.allow_insecure_lan)
        if args.password_prompt:missing=[item for item in missing if item!='mysql_password_missing']
        if not args.connect or missing:
            emit({'status':'configuration_pending' if missing else 'mysql_connection_prepared_not_connected',
                              'pending':missing,'password_environment_variable':config.password_env,'network_connected':False,
                              'runtime_switch_performed':False,'active_business_backend':'not_inspected','schema_checked':False});return 2 if args.connect and missing else 0
        if args.password_prompt:
            if not sys.stdin.isatty():raise CheckError('mysql_password_requires_interactive_terminal')
            password=getpass.getpass('MySQL password (hidden, read-only inspection): ')
            if not password:raise CheckError('mysql_password_missing')
        else:password=password_for(config,os.environ)
        import pymysql
        snapshot=json.loads(SCHEMA.read_text(encoding='utf-8'))
        if snapshot['schema_basis']!='0008_multi_user' or snapshot['table_count']!=34:raise CheckError('mysql_expected_schema_not_reviewed')
        try:result=connect_check(config,password,snapshot,pymysql.connect)
        finally:password=None
        emit(result);return 0 if result['status']=='mysql_prepared_schema_verified' else 2
    except (EOFError,KeyboardInterrupt):result={'status':'blocked','error':'mysql_inspection_cancelled'}
    except CheckError as error:
        result={'status':'blocked','error':error.code}
    except Exception as error:
        # Driver errors may contain passwords/URLs. Numeric code only, never str(error).
        number=error.args[0] if error.args and type(error.args[0]) is int else None
        result={'status':'blocked','error':'mysql_connection_or_inspection_failed','driver_error_code':number}
    result.update(network_result_unconfirmed=True,runtime_switch_performed=False)
    emit(result);return 2

if __name__=='__main__':raise SystemExit(main())
