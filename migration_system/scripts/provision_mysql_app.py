"""Explicit minimal-privilege MySQL application account provisioning.

Offline plan by default. --execute asks for root password locally, creates ONE
new account limited to this database, stores ONLY its random application secret
with Windows CurrentUser DPAPI, and writes new opt-in configs. No old data is
uploaded. --init-admin reuses the existing administrator initialization CLI.
No API/Worker is started or switched.
"""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import getpass
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import sys
from uuid import uuid4

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.persistence.mysql_connection import (
    CheckError,load_config,connect_options,credential_binding,password_for,inspect_schema,version_review,
    secret_path as protected_secret_path)
from card_migration_system.persistence.protected_password import save_password,SecretError

PRIVILEGES={'SELECT','INSERT','UPDATE','DELETE'}


def grant_resource(database, *, partial_revokes=False):
    # With partial_revokes OFF, '_' in a database-level GRANT is a wildcard,
    # even inside backticks. Escape it rather than granting on similarly named DBs.
    if not re.fullmatch(r'[A-Za-z0-9_]{1,64}',database):raise CheckError('mysql_grant_database_invalid')
    name=database if partial_revokes else database.replace('_',r'\_')
    return '`'+name+'`.*'


def check_grants(lines, database, *, partial_revokes=False):
    actual=set()
    for line in lines:
        match=re.fullmatch(r'GRANT (.+) ON (.+) TO .+',line)
        if not match or 'WITH GRANT OPTION' in line:
            raise CheckError('mysql_application_grants_require_review')
        privileges={value.strip() for value in match[1].split(',')}
        resource=match[2]
        if resource=='*.*' and privileges=={'USAGE'}:continue
        if resource!=grant_resource(database,partial_revokes=partial_revokes) or not privileges<=PRIVILEGES:
            raise CheckError('mysql_application_grants_require_review')
        actual.update(privileges)
    if actual!=PRIVILEGES:raise CheckError('mysql_application_grants_incomplete')


def _connection_toml(config):
    values={'host':config.host,'port':config.port,'name':config.name,'username':config.username,
            'password_env':config.password_env,'password_file':config.password_file,
            'connect_timeout':config.connect_timeout,'read_timeout':config.read_timeout}
    return ('# Application only. Secret is CurrentUser DPAPI encrypted, never plaintext.\n'
            'schema_version = 1\n[database]\n'+''.join(key+' = '+json.dumps(value,ensure_ascii=False)+'\n' for key,value in values.items())
            +'\n[tls]\nmode = '+json.dumps(config.tls_mode)+'\nca_file = '+json.dumps(config.ca_file,ensure_ascii=False)+'\n')


def provision(config_file, username, root_password, progress):
    if os.name!='nt':raise CheckError('mysql_local_provision_requires_windows_dpapi')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{2,31}',username) or username.lower()=='root':
        raise CheckError('mysql_application_username_invalid')
    admin=load_config(config_file)
    if admin.username!='root' or admin.tls_mode not in ('verify_ca','verify_identity'):
        raise CheckError('mysql_application_provision_requires_verified_root_config')
    config_path=PROJECT/'configs/mysql_app.local.toml'
    runtime_path=PROJECT/'configs/mysql_multi_user.local.toml'
    application=replace(admin,username=username,password_env='CARDMIG_MYSQL_APP_PASSWORD',
                        password_file='var/secrets/mysql-app.dpapi')
    secret_path=protected_secret_path(application)
    for path in (config_path,runtime_path,secret_path):
        if path.exists() or path.is_symlink():raise CheckError('mysql_application_local_files_exist_do_not_overwrite')
    import pymysql
    root=pymysql.connect(**connect_options(admin,root_password))
    try:
        with root.cursor() as cursor:
            cursor.execute('SELECT VERSION(),USER(),@@GLOBAL.partial_revokes')
            version,session_user,partial_revokes=cursor.fetchone();version_review(version)
            if partial_revokes not in (0,1):raise CheckError('mysql_partial_revokes_requires_review')
            partial_revokes=bool(partial_revokes)
            host=session_user.rsplit('@',1)[-1]
            if host!='localhost':
                try:host=str(ipaddress.ip_address(host))
                except ValueError:raise CheckError('mysql_application_source_host_requires_review') from None
            progress.update(allowed_source=host,application_username=username,stage='root_connected')
            snapshot=json.loads((PROJECT/'docs/deployment/mysql_handoff_v2/schema_multi_user.json').read_text(encoding='utf-8'))
            structure=inspect_schema(cursor,admin,snapshot)
            cursor.execute('SELECT version_num FROM alembic_version')
            if structure['differences_total'] or [row[0] for row in cursor.fetchall()]!=['0008_multi_user']:
                raise CheckError('mysql_application_provision_requires_initialized_schema')
            if set(structure['nonempty_tables'])-{'alembic_version'}:
                raise CheckError('mysql_fresh_database_expected')
            try:
                cursor.execute('SHOW GRANTS FOR %s@%s',(username,host))
            except pymysql.MySQLError as error:
                if not error.args or error.args[0]!=1141:raise
            else:raise CheckError('mysql_application_account_already_exists_do_not_reset')
            root.rollback()
            password=secrets.token_urlsafe(36)
            save_password(secret_path,password,credential_binding(application))
            progress.update(secret_saved_encrypted=True,stage='encrypted_secret_saved')
            cursor.execute('CREATE USER %s@%s IDENTIFIED BY %s REQUIRE SSL',(username,host,password))
            progress.update(application_account_created=True,stage='application_account_created')
            resource=grant_resource(admin.name,partial_revokes=partial_revokes)
            cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON {resource} TO %s@%s',(username,host))
            cursor.execute('SHOW GRANTS FOR %s@%s',(username,host))
            check_grants([row[0] for row in cursor.fetchall()],admin.name,partial_revokes=partial_revokes)
            progress.update(stage='minimal_grants_verified')
        password=None
        return finish_application(application,host,progress)
    finally:root.rollback();root.close()


def finish_application(application, host, progress):
    """Verify the existing app identity/secret and write new configs, no account DDL."""
    import pymysql
    config_path=PROJECT/'configs/mysql_app.local.toml'
    runtime_path=PROJECT/'configs/mysql_multi_user.local.toml'
    for path in (config_path,runtime_path):
        if path.exists() or path.is_symlink():raise CheckError('mysql_application_local_files_exist_do_not_overwrite')
    options=connect_options(application,password_for(application,{}))
    one=pymysql.connect(**options)
    try:
        with one.cursor() as cursor:
            cursor.execute('SELECT CURRENT_USER(),DATABASE()')
            actual_user,actual_database=cursor.fetchone()
            if actual_user!=application.username+'@'+host or actual_database!=application.name:
                raise CheckError('mysql_application_identity_mismatch')
            cursor.execute('SELECT @@GLOBAL.partial_revokes')
            partial=cursor.fetchone()[0]
            if partial not in (0,1):raise CheckError('mysql_partial_revokes_requires_review')
            cursor.execute('SHOW GRANTS')
            check_grants([row[0] for row in cursor.fetchall()],application.name,partial_revokes=bool(partial))
            snapshot=json.loads((PROJECT/'docs/deployment/mysql_handoff_v2/schema_multi_user.json').read_text(encoding='utf-8'))
            structure=inspect_schema(cursor,application,snapshot)
            cursor.execute('SELECT version_num FROM alembic_version')
            if structure['differences_total'] or [row[0] for row in cursor.fetchall()]!=['0008_multi_user']:
                raise CheckError('mysql_application_provision_requires_initialized_schema')
            if set(structure['nonempty_tables'])-{'alembic_version'}:
                raise CheckError('mysql_fresh_database_expected')
        two=pymysql.connect(**options)
        try:
            from bootstrap_cloud_mysql import native_checks
            native=native_checks(one,two)
        finally:two.close()
    finally:one.rollback();one.close()
    with config_path.open('x',encoding='utf-8') as stream:stream.write(_connection_toml(application))
    runtime=(PROJECT/'configs/mysql_multi_user.example.toml').read_text(encoding='utf-8')
    runtime=runtime.replace('configs/mysql_connection.local.toml','configs/mysql_app.local.toml')
    with runtime_path.open('x',encoding='utf-8') as stream:stream.write(runtime)
    progress.update(status='mysql_application_account_and_native_checks_passed',stage='application_config_ready',
                    granted_privileges=sorted(PRIVILEGES),native_checks=native,
                    connection_config=str(config_path),system_config=str(runtime_path),
                    secret_storage='Windows CurrentUser DPAPI',database=application.name,
                    tls_verification_mode=application.tls_mode,tls_identity_verified=application.tls_mode=='verify_identity')
    return progress


def resume_provision(config_file, report_file, progress):
    """Recover only a known post-grant probe failure. Never recreate/reset/grant."""
    path=Path(report_file).resolve()
    if not path.is_relative_to(PROJECT.resolve()/'var/mysql-provision-reports'):
        raise CheckError('mysql_application_resume_report_path_invalid')
    try:
        raw=path.read_bytes()
        if len(raw)>16384:raise ValueError()
        prior=json.loads(raw)
        if (type(prior) is not dict or prior.get('status')!='blocked'
                or prior.get('stage')!='minimal_grants_verified'
                or prior.get('application_account_created') is not True
                or prior.get('secret_saved_encrypted') is not True
                or prior.get('administrator_initialized') is not False
                or prior.get('runtime_switch_performed') is not False
                or not str(prior.get('error','')).startswith('mysql_native_')
                or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{2,31}',prior.get('application_username',''))
                or prior['application_username'].lower()=='root'):
            raise ValueError()
        host=prior['allowed_source']
        if host!='localhost':host=str(ipaddress.ip_address(host))
    except (OSError,ValueError,TypeError,KeyError):
        raise CheckError('mysql_application_resume_report_invalid') from None
    admin=load_config(config_file)
    if admin.username!='root' or admin.tls_mode not in ('verify_ca','verify_identity'):
        raise CheckError('mysql_application_provision_requires_verified_root_config')
    application=replace(admin,username=prior['application_username'],password_env='CARDMIG_MYSQL_APP_PASSWORD',
                        password_file='var/secrets/mysql-app.dpapi')
    # DPAPI verifies the endpoint/database/username binding, not just report text.
    if not protected_secret_path(application).is_file():raise CheckError('mysql_protected_password_missing')
    progress.update(application_account_created=True,secret_saved_encrypted=True,
                    application_username=application.username,allowed_source=host,
                    stage='minimal_grants_verified',resumed_from_report=path.name,
                    account_ddl_executed=False)
    return finish_application(application,host,progress)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=PROJECT/'configs/mysql_connection.local.toml')
    parser.add_argument('--app-user',default='cardmig_app')
    parser.add_argument('--init-admin',action='store_true',help='Initialize a new web administrator with hidden password prompts')
    parser.add_argument('--admin-user',default='admin')
    parser.add_argument('--resume-report',type=Path,help='Continue a known post-grant probe failure using the encrypted app secret; no root prompt')
    parser.add_argument('--execute',action='store_true');args=parser.parse_args(argv)
    progress={'status':'blocked','stage':'not_started','application_account_created':False,
              'secret_saved_encrypted':False,'root_password_saved':False,'old_data_uploaded':False,
              'runtime_switch_performed':False,'model_calls':0,'administrator_initialized':False}
    if not args.execute:
        print(json.dumps({**progress,'status':'offline_application_provision_plan',
                          'application_username':args.app_user,'privileges':sorted(PRIVILEGES),
                          'initialize_administrator':args.init_admin,'administrator_username':args.admin_user if args.init_admin else None,
                          'resume_existing_account':args.resume_report is not None,
                          'password_storage':'Windows CurrentUser DPAPI; application password only'}));return 0
    try:
        if args.resume_report:
            resume_provision(args.config,args.resume_report,progress)
        else:
            if not sys.stdin.isatty():raise CheckError('mysql_password_requires_interactive_terminal')
            password=getpass.getpass('MySQL root password (hidden, not saved): ')
            if not password:raise CheckError('mysql_password_missing')
            try:provision(args.config,args.app_user,password,progress)
            finally:password=None
        if args.init_admin:
            if not sys.stdin.isatty():raise CheckError('mysql_password_requires_interactive_terminal')
            progress.update(stage='administrator_initialization')
            from card_migration_system.interfaces import accounts_cli
            code=accounts_cli.main(['init-admin','--project-root',str(PROJECT),
                                   '--config',str(PROJECT/'configs/mysql_multi_user.local.toml'),
                                   '--username',args.admin_user])
            if code:raise CheckError('mysql_administrator_initialization_incomplete_use_init_admin')
            progress.update(administrator_initialized=True,administrator_username=args.admin_user,
                            status='mysql_application_and_administrator_ready',stage='administrator_initialized')
        result=0
    except (EOFError,KeyboardInterrupt):
        progress.update(status='blocked',error='mysql_application_provision_cancelled');result=2
    except Exception as error:
        progress['status']='blocked'
        progress['error']=error.code if isinstance(error,(CheckError,SecretError)) else 'mysql_application_provision_failed_requires_review'
        progress['driver_error_code']=getattr(error,'driver_error_code',None)
        if progress['driver_error_code'] is None:
            progress['driver_error_code']=error.args[0] if error.args and type(error.args[0]) is int else None
        progress['do_not_blindly_retry_account_creation']=True;result=2
    progress['created_at']=datetime.now(timezone.utc).isoformat()
    try:
        folder=PROJECT/'var/mysql-provision-reports';folder.mkdir(parents=True,exist_ok=True)
        path=folder/(uuid4().hex+'.json')
        with path.open('x',encoding='utf-8') as stream:json.dump(progress,stream,ensure_ascii=False,indent=2)
        print(json.dumps({'status':progress['status'],'stage':progress['stage'],'report_file':str(path),
                          **({'error':progress['error']} if 'error' in progress else {})}));return result
    except OSError:
        print(json.dumps({'status':'blocked','error':'mysql_application_provision_report_save_failed',
                          'do_not_blindly_retry_account_creation':True}));return 2


if __name__=='__main__':raise SystemExit(main())
