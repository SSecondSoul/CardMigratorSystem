"""Explicit cloud bootstrap with hidden, process-local administrator credentials.

Default: offline plan only. --execute creates only the configured business DB,
delegates its 34-table initialization to the system, then checks native MySQL
JSON/time/locks/constraints/rollback. No app account, GRANT, migration job, model
call, old-data upload, credential file, runtime switch or destructive DDL.
"""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from card_migration_system.config import load_settings
from card_migration_system.persistence.database import initialize, SchemaReviewError
from card_migration_system.persistence.mysql_connection import (
    CheckError, connect_options, inspect_schema, load_config, version_review)


def native_checks(connection, second):
    """Temporary DML is always rolled back; locks are connection-local."""
    lock_name = 'cardmig-smoke:' + uuid4().hex
    row_id = uuid4().hex
    with connection.cursor() as cursor, second.cursor() as other:
        try:
            cursor.execute('SELECT GET_LOCK(%s,0)', (lock_name,))
            if cursor.fetchone()[0] != 1:raise CheckError('mysql_native_lock_acquire_failed')
            other.execute('SELECT GET_LOCK(%s,0)', (lock_name,))
            if other.fetchone()[0] != 0:raise CheckError('mysql_native_lock_exclusion_failed')
            cursor.execute('SELECT RELEASE_LOCK(%s)', (lock_name,))
            if cursor.fetchone()[0] != 1:raise CheckError('mysql_native_lock_release_failed')
            other.execute('SELECT GET_LOCK(%s,0)', (lock_name,))
            if other.fetchone()[0] != 1:raise CheckError('mysql_native_lock_reacquire_failed')
            other.execute('SELECT RELEASE_LOCK(%s)', (lock_name,))
            if other.fetchone()[0] != 1:raise CheckError('mysql_native_lock_release_failed')
            payload = {'unicode': '中文', 'values': [True, None, 1.25]}
            epoch = 1794995830.1234567
            cursor.execute('SELECT JSON_TYPE(CAST(%s AS JSON)),CAST(%s AS JSON),%s',
                           ('null', json.dumps(payload, ensure_ascii=False), epoch))
            kind, actual, timestamp = cursor.fetchone()
            if kind != 'NULL' or json.loads(actual) != payload or float(timestamp) != epoch:
                raise CheckError('mysql_native_json_or_timestamp_mismatch')
            connection.rollback();connection.begin()
            cursor.execute('INSERT INTO source_inputs (id,filename,relative_path,sha256) VALUES (%s,%s,%s,%s)',
                           (row_id, '__rollback_probe__.vue', '__rollback_probe__/' + row_id, '0' * 64))
            cursor.execute('SELECT COUNT(*) FROM source_inputs WHERE id=%s', (row_id,))
            if cursor.fetchone()[0] != 1:raise CheckError('mysql_native_insert_readback_failed')
            try:
                cursor.execute('INSERT INTO source_inputs (id,filename,relative_path,sha256) VALUES (%s,%s,%s,%s)',
                               (row_id, '__duplicate_probe__.vue', '__rollback_probe__/' + row_id, '0' * 64))
            except Exception as error:
                if not error.args or error.args[0] != 1062:raise CheckError('mysql_native_duplicate_check_failed') from None
            else:raise CheckError('mysql_native_unique_not_enforced')
            connection.rollback()
            cursor.execute('SELECT COUNT(*) FROM source_inputs WHERE id=%s', (row_id,))
            if cursor.fetchone()[0] != 0:raise CheckError('mysql_native_rollback_failed')
            connection.rollback();connection.begin()
            try:
                cursor.execute('INSERT INTO tasks (id,input_id,name) VALUES (%s,%s,%s)',
                               (uuid4().hex, row_id, '__foreign_key_probe__'))
            except Exception as error:
                # ER_NO_REFERENCED_ROW and ER_NO_REFERENCED_ROW_2: both mean
                # the FK rejected a missing parent; some limited users receive
                # the less detailed 1216 instead of 1452. Never accept permission
                # errors, arbitrary integrity errors, or an accepted insert.
                number=error.args[0] if error.args and type(error.args[0]) is int else None
                if number not in (1216,1452):
                    raise CheckError('mysql_native_foreign_key_check_failed',driver_error_code=number) from None
            else:raise CheckError('mysql_native_foreign_key_not_enforced')
            connection.rollback();connection.begin()
            # A negative test alone could hide a broken normal insert path.
            task_id=uuid4().hex
            cursor.execute('INSERT INTO source_inputs (id,filename,relative_path,sha256) VALUES (%s,%s,%s,%s)',
                           (row_id,'__rollback_probe__.vue','__rollback_probe__/'+row_id,'0'*64))
            cursor.execute('INSERT INTO tasks (id,input_id,name) VALUES (%s,%s,%s)',
                           (task_id,row_id,'__valid_foreign_key_probe__'))
            cursor.execute('SELECT COUNT(*) FROM tasks WHERE id=%s AND input_id=%s',(task_id,row_id))
            if cursor.fetchone()[0]!=1:raise CheckError('mysql_native_foreign_key_positive_insert_failed')
            connection.rollback()
            cursor.execute('SELECT COUNT(*) FROM tasks WHERE id=%s',(task_id,))
            if cursor.fetchone()[0]!=0:raise CheckError('mysql_native_foreign_key_positive_rollback_failed')
            cursor.execute('SELECT COUNT(*) FROM source_inputs WHERE id=%s',(row_id,))
            if cursor.fetchone()[0]!=0:raise CheckError('mysql_native_rollback_failed')
            connection.rollback();connection.begin()
            try:
                cursor.execute('INSERT INTO users (id,username,username_normalized,display_name,password_hash,role,is_active,must_change_password,created_at,password_changed_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                               (uuid4().hex, 'probe_' + row_id, 'probe_' + row_id, 'rollback probe',
                                'not-a-login-password-hash', 'invalid_role', 0, 1, epoch, epoch))
            except Exception as error:
                if not error.args or error.args[0] != 3819:raise CheckError('mysql_native_check_constraint_failed') from None
            else:raise CheckError('mysql_native_check_constraint_not_enforced')
            return {'json_unicode_and_null': True, 'epoch_roundtrip': True,
                    'two_connection_lock_exclusion': True, 'insert_readback_and_rollback': True,
                    'unique_enforced': True, 'foreign_key_enforced': True,
                    'foreign_key_valid_insert_and_rollback':True,'check_enforced': True}
        finally:
            connection.rollback();second.rollback()


def execute(config_file, password):
    import pymysql
    config = load_config(config_file)
    if config.tls_mode not in ('verify_identity', 'verify_ca'):
        raise CheckError('mysql_bootstrap_requires_verified_tls')
    if config.username != 'root':
        raise CheckError('mysql_bootstrap_requires_explicit_root_config')
    options = connect_options(config, password)
    server_options = dict(options);server_options.pop('database')
    connection = pymysql.connect(**server_options)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT VERSION(),@@SESSION.sql_mode')
            version, modes = cursor.fetchone();warnings = version_review(version)
            if not {'STRICT_TRANS_TABLES', 'STRICT_ALL_TABLES'} & set(modes.split(',')):
                raise CheckError('mysql_strict_mode_required')
            cursor.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
            cipher = cursor.fetchone()
            if not cipher or not cipher[1]:raise CheckError('mysql_tls_not_negotiated')
            cursor.execute('SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s', (config.name,))
            created = cursor.fetchone() is None
            if created:
                cursor.execute(f'CREATE DATABASE `{config.name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin')
                connection.commit()
    finally:
        connection.close()
    # No subprocess, shell argument, log or saved config receives the password.
    prior = os.environ.get(config.password_env)
    os.environ[config.password_env] = password
    try:
        settings = load_settings(project_root=PROJECT, config_file='configs/mysql_multi_user.example.toml')
        settings = replace(settings, mysql_connection_file=Path(config_file).resolve())
        initialize(settings)
    finally:
        if prior is None:os.environ.pop(config.password_env, None)
        else:os.environ[config.password_env] = prior
    connection = pymysql.connect(**options)
    try:
        second = pymysql.connect(**options)
        try:
            native = native_checks(connection, second)
        finally:
            second.close()
        snapshot = json.loads((PROJECT / 'docs/deployment/mysql_handoff_v2/schema_multi_user.json').read_text(encoding='utf-8'))
        with connection.cursor() as cursor:
            structure = inspect_schema(cursor, config, snapshot)
            cursor.execute('SELECT version_num FROM alembic_version')
            revisions = [row[0] for row in cursor.fetchall()]
        if structure['differences_total'] or revisions != ['0008_multi_user']:
            raise CheckError('mysql_bootstrap_final_schema_check_failed')
        return {'status': 'mysql_bootstrap_and_native_checks_passed', 'database': config.name,
                'database_created': created, 'server_version': version, 'version_warnings': warnings,
                'tls_verification_mode': config.tls_mode, 'tls_identity_verified': config.tls_mode == 'verify_identity',
                'schema': structure, 'schema_revision': revisions[0], 'native_checks': native,
                'old_data_uploaded': False, 'application_account_created': False,
                'runtime_switch_performed': False, 'api_worker_end_to_end': 'not_run',
                'model_calls': 0, 'created_at': datetime.now(timezone.utc).isoformat()}
    finally:
        connection.rollback();connection.close()


def save_report(report):
    folder = PROJECT / 'var/mysql-bootstrap-reports';folder.mkdir(parents=True, exist_ok=True)
    report_file = folder / (uuid4().hex + '.json')
    report.setdefault('created_at', datetime.now(timezone.utc).isoformat())
    with report_file.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    return report_file


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=PROJECT / 'configs/mysql_connection.local.toml')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if not args.execute:
            print(json.dumps({'status': 'offline_bootstrap_plan_only', 'host': config.host, 'port': config.port,
                              'database': config.name, 'tables': 34, 'password_prompted': False,
                              'runtime_switch_performed': False}));return 0
        if not sys.stdin.isatty():raise CheckError('mysql_password_requires_interactive_terminal')
        password = getpass.getpass('MySQL root password (hidden, not saved): ')
        if not password:raise CheckError('mysql_password_missing')
        try:
            report = execute(args.config, password)
        finally:
            password = None
        report_file = save_report(report)
        print(json.dumps({'status': report['status'], 'report_file': str(report_file),
                          'runtime_switch_performed': False}, ensure_ascii=True));return 0
    except (KeyboardInterrupt, EOFError):
        code, number, review = 'mysql_bootstrap_cancelled', None, None
    except Exception as error:
        code = error.code if isinstance(error, CheckError) else 'mysql_bootstrap_failed_requires_review'
        known = {'mysql_bootstrap_artifact_drift', 'mysql_bootstrap_unexpected_statement',
                 'mysql_schema_requires_manual_review', 'mysql_refuse_stamp_nonempty_or_unknown_database',
                 'mysql_transaction_lock_unavailable', 'mysql_transaction_lock_release_failed',
                 'database_schema_mismatch', 'database_not_initialized'}
        if error.args and type(error.args[0]) is str and error.args[0] in known:
            code = error.args[0]
        number = getattr(error,'driver_error_code',None)
        if number is None:number = error.args[0] if error.args and type(error.args[0]) is int else None
        original = getattr(error, 'orig', None)
        if number is None and original is not None and original.args and type(original.args[0]) is int:
            number = original.args[0]
        review = error.review if isinstance(error, SchemaReviewError) else None
    result = {'status': 'blocked', 'error': code, 'driver_error_code': number,
              'do_not_blindly_retry_ddl': True, 'runtime_switch_performed': False}
    if review is not None:result['schema'] = review
    if args.execute:
        try:result['report_file'] = str(save_report(result))
        except OSError:result['report_save_failed'] = True
    print(json.dumps(result));return 2


if __name__ == '__main__':
    raise SystemExit(main())
