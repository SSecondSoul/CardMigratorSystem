"""Offline handoff checks against real temporary SQLite/Alembic schema, not MySQL QA."""
import importlib.util
import json
from hashlib import sha256
import re
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

import test_vertical_slice as fixtures
from sqlalchemy import inspect

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mysql_handoff_export', PROJECT / 'scripts/export_mysql_handoff.py')
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)
FOLDER = PROJECT / export.DESTINATION


def multi_user_export():
    module_spec=importlib.util.spec_from_file_location('multi_user_export',PROJECT/'scripts/export_multi_user_schema.py')
    module=importlib.util.module_from_spec(module_spec)
    with patch.dict(sys.modules,{'export_mysql_handoff':export}):module_spec.loader.exec_module(module)
    return module


class MysqlHandoffTests(unittest.TestCase):
    setUp = fixtures.VerticalSliceTests.setUp

    def test_generated_documents_are_current_and_main_file_is_portable(self):
        files = export.build()
        for name, content in files.items():
            self.assertEqual((FOLDER / name).read_text(encoding='utf-8'), content, name)
        self.assertIn('```sql\n' + files['schema_current.sql'] + '```', files['MYSQL_DATABASE_HANDOFF.md'])
        self.assertIn(files['verify_schema.sql'], files['MYSQL_DATABASE_HANDOFF.md'])

    def test_table_and_column_inventory_matches_actual_alembic_database(self):
        snapshot = json.loads(export.build()['schema_current.json'])
        inspector = inspect(self.service.engine)
        self.assertEqual(snapshot['table_count'], 26)
        # v1 handoff is a frozen 0007 baseline; 0008 accounts are additive.
        baseline={t['name'] for t in snapshot['tables']}
        self.assertTrue(baseline <= set(inspector.get_table_names()))
        self.assertEqual(set(inspector.get_table_names())-baseline,{'users','auth_sessions','user_limits','user_usage_daily','input_owners','job_owners','audit_logs','auth_throttle'})
        for table in snapshot['tables']:
            actual = inspector.get_columns(table['name'])
            self.assertEqual([c['name'] for c in actual], [c['name'] for c in table['columns']])
            self.assertEqual([c['nullable'] for c in actual], [c['nullable'] for c in table['columns']])
            self.assertEqual(inspector.get_pk_constraint(table['name'])['constrained_columns'], table['primary_key'])

    def test_unique_foreign_key_and_check_inventory_matches_actual_database(self):
        inspector = inspect(self.service.engine)
        snapshot = json.loads(export.build()['schema_current.json'])
        for table in snapshot['tables']:
            name = table['name']
            self.assertEqual({tuple(u['column_names']) for u in inspector.get_unique_constraints(name)}, {tuple(u) for u in table['unique']}, name)
            actual = {(tuple(f['constrained_columns']), f['referred_table'], tuple(f['referred_columns'])) for f in inspector.get_foreign_keys(name)}
            expected = {(tuple(f['columns']), f['target_table'], tuple(f['target_columns'])) for f in table['foreign_keys']}
            self.assertEqual(actual, expected, name)
            self.assertEqual({c['sqltext'] for c in inspector.get_check_constraints(name)}, set(table['checks']), name)

    def test_mysql_ddl_has_correct_creation_order_safe_types_and_parent_keys(self):
        tables = export.model_tables();by_name = {t.name: export.describe(t) for t in tables}
        created = set()
        sql = export.build()['schema_current.sql']
        self.assertNotIn('IF NOT EXISTS', sql.split('\n', 2)[-1])
        for prohibited in ('DROP TABLE', 'DROP DATABASE', 'TRUNCATE', 'FOREIGN_KEY_CHECKS', 'INSERT INTO', 'UPDATE alembic_version'):
            self.assertNotIn(prohibited, sql.upper() if prohibited.isupper() else sql)
        for table in tables:
            info = by_name[table.name];text = export.ddl(table)
            self.assertIn('ENGINE=InnoDB', text);self.assertIn('COLLATE utf8mb4_0900_bin', text)
            for c in info['columns']:
                if c['name'].endswith('_at') or c['name'] in ('last_seen', 'expires_at'):
                    self.assertEqual(c['mysql_type'], 'DOUBLE')
            for fk in info['foreign_keys']:
                self.assertTrue(fk['target_table'] in created or fk['target_table'] == table.name)
                parent = by_name[fk['target_table']]
                self.assertIn(fk['target_columns'], [parent['primary_key'], *parent['unique']])
                for child_column, parent_column in zip(fk['columns'], fk['target_columns']):
                    self.assertEqual(next(c['mysql_type'] for c in info['columns'] if c['name'] == child_column),
                                     next(c['mysql_type'] for c in parent['columns'] if c['name'] == parent_column))
            created.add(table.name)
        self.assertEqual(sql.count(' AUTO_INCREMENT'), 1)
        self.assertNotIn('CREATE TABLE `users`', sql)
        self.assertNotIn('CREATE TABLE `auth_sessions`', sql)
        self.assertNotIn('CREATE TABLE `checkpoints`', sql)

    def test_export_does_not_connect_database_or_modify_runtime(self):
        with patch('sqlalchemy.create_engine', side_effect=AssertionError('No database connection allowed')):
            files = export.build()
        self.assertEqual(len(files), 4)
        self.assertIn('offline_mysql_preparation_not_runtime_adapter', files['schema_current.json'])
        self.assertEqual(json.loads(files['schema_current.json'])['alembic_version_rows'], 0)

    def test_multi_user_handoff_matches_all_34_tables_without_mutating_v1(self):
        before=export.build()
        module=multi_user_export()
        with patch('sqlalchemy.create_engine',side_effect=AssertionError('Export is offline')):files=module.build()
        self.assertEqual(export.build(),before,'v2 must not mutate the frozen v1 exporter')
        for name,content in files.items():
            self.assertEqual((PROJECT/module.DESTINATION/name).read_text(encoding='utf-8'),content,name)
        snapshot=json.loads(files['schema_multi_user.json']);inspector=inspect(self.service.engine)
        self.assertEqual(snapshot['table_count'],34)
        self.assertEqual({t['name'] for t in snapshot['tables']},set(inspector.get_table_names()))
        for table in snapshot['tables']:
            name=table['name'];columns=inspector.get_columns(name)
            self.assertEqual([(c['name'],c['nullable']) for c in columns],[(c['name'],c['nullable']) for c in table['columns']],name)
            self.assertEqual(inspector.get_pk_constraint(name)['constrained_columns'],table['primary_key'],name)
            self.assertEqual({tuple(u['column_names']) for u in inspector.get_unique_constraints(name)},{tuple(u) for u in table['unique']},name)
            self.assertEqual({(tuple(f['constrained_columns']),f['referred_table'],tuple(f['referred_columns'])) for f in inspector.get_foreign_keys(name)},
                             {(tuple(f['columns']),f['target_table'],tuple(f['target_columns'])) for f in table['foreign_keys']},name)
            self.assertEqual({c['sqltext'] for c in inspector.get_check_constraints(name)},set(table['checks']),name)

    def test_multi_user_file_is_standalone_and_verification_is_read_only(self):
        files=multi_user_export().build();doc=files['MYSQL_MULTI_USER_HANDOFF.md'];verify=files['verify_schema.sql']
        snapshot=json.loads(files['schema_multi_user.json'])
        self.assertEqual(len(files),4)
        self.assertIn('```sql\n'+files['schema_multi_user.sql']+'```',doc)
        self.assertIn('```sql\n'+verify+'```',doc)
        self.assertNotIn('../mysql_handoff_v1',doc)
        for title in ('## 0.','## 1.','## 2.','## 3.','## 4.','## 5.','## 6.','## 7.','## 8.','## 9.','## 10.','## 11.'):
            self.assertIn(title,doc)
        for token in ('missing_table','unexpected_table','ENFORCED','UPDATE_RULE','DELETE_RULE','SUB_PART','alembic_rows_must_be_zero'):
            self.assertIn(token,verify)
        for table in snapshot['tables']:
            self.assertIn(f"FROM `{snapshot['database']}`.`{table['name']}`",verify)
        for prohibited in ('INSERT','UPDATE','DELETE','DROP','ALTER','CREATE','TRUNCATE'):
            self.assertIsNone(re.search(r'\b'+prohibited+r'\b',verify,re.I))
        self.assertEqual(snapshot['schema_sql_sha256'],sha256(files['schema_multi_user.sql'].encode()).hexdigest())
        self.assertEqual(snapshot['alembic_version_rows'],0)

    def test_multi_user_mysql_dialect_compiles_every_table_and_keeps_fk_parent_keys(self):
        from sqlalchemy.dialects import mysql
        from sqlalchemy.schema import CreateTable
        module=multi_user_export();tables=export.model_tables(include_accounts=True);created=set()
        infos={t.name:export.describe(t,purposes=module.PURPOSES,meanings=module.MEANINGS) for t in tables}
        self.assertEqual(len(tables),34)
        for table in tables:
            # Compilation is offline grammar/type checking, not MySQL execution.
            self.assertIn('CREATE TABLE',str(CreateTable(table).compile(dialect=mysql.dialect())))
            ddl=export.ddl(table,purposes=module.PURPOSES,meanings=module.MEANINGS)
            self.assertIn('ENGINE=InnoDB',ddl);self.assertIn('utf8mb4_0900_bin',ddl)
            for fk in infos[table.name]['foreign_keys']:
                self.assertTrue(fk['target_table'] in created or fk['target_table']==table.name)
                parent=infos[fk['target_table']]
                self.assertIn(fk['target_columns'],[parent['primary_key'],*parent['unique']])
                for child_col,parent_col in zip(fk['columns'],fk['target_columns']):
                    self.assertEqual(next(c['mysql_type'] for c in infos[table.name]['columns'] if c['name']==child_col),next(c['mysql_type'] for c in parent['columns'] if c['name']==parent_col))
            created.add(table.name)

    def test_future_schema_drift_stops_export_instead_of_silently_claiming_0008(self):
        module=multi_user_export()
        with patch('card_migration_system.persistence.database.HEAD','future_version'):
            with self.assertRaisesRegex(ValueError,'Review schema changes'):module.build()


if __name__ == '__main__':
    unittest.main()
