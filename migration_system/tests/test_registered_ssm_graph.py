"""Registered real extraction graph, migration/receipt/backup fault-injection tests."""
from contextlib import closing, redirect_stdout
from dataclasses import replace
from hashlib import sha256
import io
import json
from pathlib import Path
import shutil
import sqlite3
import unittest
from unittest.mock import patch

import test_vertical_slice as fixtures
from test_ssm_extraction import SOURCE, REPOSITORY
from card_migration_system.adapters.ssm import ExtractionError, SSMExtractor
from card_migration_system.application.extractions import ExtractionService
from card_migration_system.application.service import Service, ServiceError
from card_migration_system.application.storage import StorageError
from card_migration_system.graph.extraction import execute_extraction
from card_migration_system.interfaces.cli import main
from card_migration_system.persistence.backup import create_backup, verify_backup, restore_backup
from card_migration_system.persistence.database import HEAD, initialize, transaction
from card_migration_system.persistence.runtime_lock import execution_guard, RuntimeBusyError
from card_migration_system.persistence.ssm_extractions import SSMExtraction, SSMExtractionFile


class RegisteredGraphTests(unittest.TestCase):
    def setUp(self):
        fixtures.VerticalSliceTests.setUp(self)
        # Temp DB/storage use a byte-identical extractor source mirror. Route
        # parser execution to the real read-only checkout's installed Node deps.
        routing = patch('card_migration_system.application.extractions.SSMExtractor',
                        side_effect=lambda repository: SSMExtractor(REPOSITORY))
        routing.start()
        self.addCleanup(routing.stop)
        self.ledger = ExtractionService(self.service)
        self.source = self.service.create_input({'filename': 'Counter.vue', 'source': SOURCE.decode()})
        task = self.service.create_task({'input_id': self.source['input_id']})
        self.run_id = self.service.enqueue(task['task_id'], {'profile': 'success', 'max_repair_rounds': 0}, 'ssm-ref')['run_id']

    def execute(self, **kwargs):
        return execute_extraction(self.service, run_id=self.run_id, **kwargs)

    def file(self, key, kind):
        return self.settings.artifact_dir / f'ssm-extractions/{key}/{kind}.json'

    def corrupt_registered_json(self, key, kind, mutate):
        path = self.file(key, kind)
        value = json.loads(path.read_bytes())
        mutate(value)
        content = json.dumps(value, sort_keys=True).encode()
        path.write_bytes(content)  # Deliberate corruption of a disposable test artifact.
        with transaction(self.service.engine) as session:
            row = session.get(SSMExtractionFile, f'ssm-extractions/{key}/{kind}.json')
            row.sha256 = sha256(content).hexdigest()

    def test_real_graph_registers_evidence_but_does_not_upgrade_fixture_report(self):
        before = self.service.report(self.run_id)
        result = self.execute()
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(result['graph_pending'])
        report = self.ledger.report(result['extraction_id'])
        self.assertEqual({item['kind'] for item in report['files']}, {'request', 'ssm', 'receipt'})
        self.assertEqual(report['migration_quality_status'], 'not_run')
        self.assertEqual(report['actual_model_calls'], 0)
        self.assertEqual(before, self.service.report(self.run_id))
        self.assertEqual(json.loads(self.ledger.download(result['extraction_id']))['schema_version'], '3.0')
        with closing(sqlite3.connect(self.settings.graph_database)) as connection:
            self.assertGreater(connection.execute('SELECT count(*) FROM checkpoints WHERE thread_id=?',
                ('ssm:' + result['extraction_id'],)).fetchone()[0], 0)

    def test_expected_parser_failure_is_registered_without_fake_artifact(self):
        with patch.object(SSMExtractor, 'extract', side_effect=ExtractionError('ssm_script_syntax_error')):
            result = self.execute()
        self.assertEqual(result['status'], 'blocked')
        report = self.ledger.report(result['extraction_id'])
        self.assertEqual({item['kind'] for item in report['files']}, {'request', 'receipt'})
        with self.assertRaisesRegex(ServiceError, 'ssm_not_completed'):
            self.ledger.download(result['extraction_id'])

    def test_completed_execution_is_not_run_again(self):
        key = self.execute()['extraction_id']
        with patch.object(SSMExtractor, 'extract', side_effect=AssertionError('no parser')):
            self.assertEqual(execute_extraction(self.service, extraction_id=key)['status'], 'completed')

    def test_interrupt_before_parser_resumes_from_prepared(self):
        with patch.object(SSMExtractor, 'extract', side_effect=AssertionError('not yet')):
            result = self.execute(interrupt_after=['prepare_source'])
        self.assertEqual(result['status'], 'prepared')
        self.assertTrue(result['graph_pending'])
        self.assertEqual(execute_extraction(self.service, extraction_id=result['extraction_id'])['status'], 'completed')

    def test_interrupt_after_response_reuses_receipt(self):
        result = self.execute(interrupt_after=['extract_ssm'])
        self.assertEqual(result['status'], 'received')
        with patch.object(SSMExtractor, 'extract', side_effect=AssertionError('no second parse')):
            resumed = execute_extraction(self.service, extraction_id=result['extraction_id'])
        self.assertEqual(resumed['status'], 'completed')

    def test_receipt_committed_before_checkpoint_failure_is_reused(self):
        original = ExtractionService.extract
        def fail_after_receipt(ledger, key):
            original(ledger, key)
            raise RuntimeError('controlled checkpoint gap')
        key = self.ledger.create(run_id=self.run_id)
        with patch.object(ExtractionService, 'extract', fail_after_receipt):
            with self.assertRaises(ServiceError):
                execute_extraction(self.service, extraction_id=key)
        self.assertEqual(self.ledger.report(key)['status'], 'review_required')
        with patch.object(SSMExtractor, 'extract', side_effect=AssertionError('no duplicate')):
            self.assertEqual(execute_extraction(self.service, extraction_id=key)['status'], 'completed')

    def test_started_without_receipt_is_not_automatically_retried(self):
        key = self.ledger.create(run_id=self.run_id)
        with transaction(self.service.engine) as session:
            session.get(SSMExtraction, key).status = 'started'
        with patch.object(SSMExtractor, 'extract', side_effect=AssertionError('ambiguous')):
            with self.assertRaisesRegex(ServiceError, 'ssm_unresolved_attempt_requires_review'):
                execute_extraction(self.service, extraction_id=key)
        self.assertEqual(self.ledger.report(key)['status'], 'review_required')

    def test_execution_binding_drift_refuses_resume_but_historical_report_is_readable(self):
        key = self.execute(interrupt_after=['prepare_source'])['extraction_id']
        with patch.object(ExtractionService, 'binding', return_value={}):
            with self.assertRaisesRegex(ServiceError, 'ssm_execution_binding_drift'):
                execute_extraction(self.service, extraction_id=key)
            self.assertEqual(self.ledger.report(key)['status'], 'review_required')

    def test_ambiguous_old_binding_can_be_marked_review_without_execution_then_backed_up(self):
        key = self.ledger.create(run_id=self.run_id)
        with transaction(self.service.engine) as session:
            session.get(SSMExtraction, key).status = 'started'
        with patch.object(ExtractionService, 'binding', return_value={}):
            with patch.object(SSMExtractor, 'extract', side_effect=AssertionError('no retry')):
                with self.assertRaisesRegex(ServiceError, 'ssm_execution_binding_drift'):
                    execute_extraction(self.service, extraction_id=key)
        self.assertEqual(self.ledger.report(key)['status'], 'review_required')
        self.assertEqual(create_backup(self.settings, backup_id='review-after-drift')['status'], 'backup_created')

    def test_os_execution_guard_excludes_second_graph(self):
        with execution_guard(self.settings.runtime_dir):
            with self.assertRaises(RuntimeBusyError):
                self.execute()

    def test_corrupt_output_blocks_report_and_download(self):
        key = self.execute()['extraction_id']
        self.file(key, 'ssm').write_bytes(b'corrupt')
        with self.assertRaises(StorageError):
            self.ledger.report(key)
        with self.assertRaises(StorageError):
            self.ledger.download(key)

    def test_receipt_identity_is_checked_even_if_file_hash_is_replaced(self):
        key = self.execute()['extraction_id']
        self.corrupt_registered_json(key, 'receipt', lambda receipt: receipt.update(extraction_id='0'*32))
        with self.assertRaisesRegex(ServiceError, 'ssm_registered_evidence_invalid'):
            self.ledger.report(key)

    def test_bool_does_not_count_as_zero_model_calls(self):
        key = self.execute()['extraction_id']
        self.corrupt_registered_json(key, 'receipt', lambda receipt: receipt.update(actual_model_calls=False))
        with self.assertRaises(ServiceError):
            self.ledger.report(key)

    def test_source_reference_corruption_blocks_report(self):
        key = self.execute()['extraction_id']
        path = self.settings.artifact_dir / f"inputs/{self.source['input_id']}/Counter.vue"
        path.write_bytes(b'changed source')
        with self.assertRaises(StorageError):
            self.ledger.report(key)

    def test_terminal_stop_reason_must_match_receipt(self):
        key = self.execute()['extraction_id']
        with transaction(self.service.engine) as session:
            session.get(SSMExtraction, key).stop_reason = 'invented_pass'
        with self.assertRaises(ServiceError):
            self.ledger.report(key)

    def test_ambient_langsmith_setting_does_not_enable_upload(self):
        with patch.dict('os.environ', {'LANGSMITH_TRACING': 'true', 'LANGSMITH_API_KEY': 'not-a-real-key'}):
            with patch('socket.socket.connect', side_effect=AssertionError('network disallowed')):
                result = self.execute()
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(result['langsmith_uploaded'])

    def test_resume_refuses_a_different_source_reference(self):
        key = self.execute(interrupt_after=['prepare_source'])['extraction_id']
        with self.assertRaisesRegex(ServiceError, 'ssm_resume_source_not_allowed'):
            execute_extraction(self.service, extraction_id=key, run_id=self.run_id)

    def test_missing_registered_output_blocks_report_and_backup(self):
        key = self.execute()['extraction_id']
        with transaction(self.service.engine) as session:
            session.delete(session.get(SSMExtractionFile, f'ssm-extractions/{key}/ssm.json'))
        with self.assertRaises(ServiceError):
            self.ledger.report(key)
        with self.assertRaises(ServiceError):
            create_backup(self.settings, backup_id='missing-ssm')

    def test_backup_restore_includes_all_registered_ssm_files_and_checkpoint(self):
        result = self.execute()
        key = result['extraction_id']
        before, content = self.ledger.report(key), self.ledger.download(key)
        create_backup(self.settings, backup_id='with-ssm')
        verify_backup(self.settings, 'with-ssm')
        restored_settings = replace(self.settings, runtime_dir=self.project / 'var/restored-ssm',
                                    artifact_dir=self.settings.artifact_dir / 'restored-ssm')
        restore_backup(restored_settings, 'with-ssm')
        restored = Service(restored_settings)
        self.addCleanup(restored.close)
        self.assertEqual(ExtractionService(restored).report(key), before)
        self.assertEqual(ExtractionService(restored).download(key), content)

    def test_backup_preserves_interrupted_graph_and_resumes_without_duplicate_parse(self):
        result = self.execute(interrupt_after=['extract_ssm'])
        key = result['extraction_id']
        create_backup(self.settings, backup_id='pending-ssm')
        restored_settings = replace(self.settings, runtime_dir=self.project / 'var/restored-pending',
                                    artifact_dir=self.settings.artifact_dir / 'restored-pending')
        restore_backup(restored_settings, 'pending-ssm')
        restored = Service(restored_settings)
        self.addCleanup(restored.close)
        with patch.object(SSMExtractor, 'extract', side_effect=AssertionError('must reuse receipt')):
            self.assertEqual(execute_extraction(restored, extraction_id=key)['status'], 'completed')

    def test_backup_refuses_unresolved_started_extraction(self):
        key = self.ledger.create(run_id=self.run_id)
        with transaction(self.service.engine) as session:
            session.get(SSMExtraction, key).status = 'started'
        with self.assertRaisesRegex(ServiceError, 'backup_requires_resolved_ssm_attempts'):
            create_backup(self.settings, backup_id='started-ssm')

    def test_blocked_receipt_is_included_in_verified_backup(self):
        with patch.object(SSMExtractor, 'extract', side_effect=ExtractionError('ssm_node_missing')):
            result = self.execute()
        create_backup(self.settings, backup_id='blocked-ssm')
        self.assertEqual(verify_backup(self.settings, 'blocked-ssm')['status'], 'backup_verified')
        self.assertEqual(result['status'], 'blocked')

    def test_corrupt_archived_ssm_blocks_restore_without_creating_target(self):
        key = self.execute()['extraction_id']
        create_backup(self.settings, backup_id='corrupt-ssm')
        archive = self.project / 'var/backups/corrupt-ssm'
        (archive / f'artifacts/ssm-extractions/{key}/ssm.json').write_bytes(b'corrupt')
        restored_settings = replace(self.settings, runtime_dir=self.project / 'var/restored-corrupt',
                                    artifact_dir=self.settings.artifact_dir / 'restored-corrupt')
        with self.assertRaises(ServiceError):
            restore_backup(restored_settings, 'corrupt-ssm')
        self.assertFalse(restored_settings.runtime_dir.exists())

    def test_read_only_api_reports_and_downloads_registered_ssm(self):
        key = self.execute()['extraction_id']
        client = fixtures.VerticalSliceTests.app(self).test_client()
        response = client.get(f'/api/v1/ssm-extractions/{key}/report', base_url=fixtures.BASE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'completed')
        response = client.get(f'/api/v1/ssm-extractions/{key}/artifact', base_url=fixtures.BASE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data)['schema_version'], '3.0')

    def test_cli_has_separate_graph_and_report_commands(self):
        output = io.StringIO()
        with patch('card_migration_system.interfaces.cli.load_settings', return_value=self.settings), redirect_stdout(output):
            self.assertEqual(main(['extract-ssm-graph', '--run-id', self.run_id]), 0)
        key = json.loads(output.getvalue())['extraction_id']
        output = io.StringIO()
        with patch('card_migration_system.interfaces.cli.load_settings', return_value=self.settings), redirect_stdout(output):
            self.assertEqual(main(['ssm-extraction-report', '--extraction-id', key]), 0)
        self.assertEqual(json.loads(output.getvalue())['status'], 'completed')

    def test_schema_upgrade_0002_preserves_existing_run_report(self):
        before = self.service.report(self.run_id)
        self.service.close()
        with closing(sqlite3.connect(self.settings.business_database)) as connection:
            for table in ('migration_feedback', 'migration_model_calls', 'migration_files', 'migration_jobs'):
                connection.execute('DROP TABLE ' + table)
            connection.execute('DROP TABLE ssm_extraction_files')
            connection.execute('DROP TABLE ssm_extractions')
            connection.execute("UPDATE alembic_version SET version_num='0002_worker_health'")
            connection.commit()
        with self.assertRaisesRegex(ValueError, 'schema_mismatch'):
            Service(self.settings)
        initialize(self.settings)
        self.service = Service(self.settings)
        self.addCleanup(self.service.close)
        self.assertEqual(self.service.report(self.run_id), before)
        with closing(sqlite3.connect(self.settings.business_database)) as connection:
            self.assertEqual(connection.execute('SELECT version_num FROM alembic_version').fetchone()[0], HEAD)


if __name__ == '__main__':
    unittest.main()
