"""G2 durable OFFLINE generation; synthetic sources and temporary databases only."""
from contextlib import closing, redirect_stdout
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_generation_boundary as fixtures
import test_vertical_slice
from card_migration_system.adapters.generation import GenerationResponse
from card_migration_system.application.generations import GenerationService
from card_migration_system.application.service import Service, ServiceError
from card_migration_system.graph.generation import execute_generation
from card_migration_system.interfaces.cli import main
from card_migration_system.persistence.backup import create_backup, verify_backup, restore_backup
from card_migration_system.persistence.database import initialize, transaction, HEAD
from card_migration_system.persistence.generations import (GenerationJob, GenerationAttempt, GenerationFile,
                                                         GenerationCandidate, metadata)
from card_migration_system.persistence.runtime_lock import execution_guard, RuntimeBusyError


class RegisteredGenerationTests(unittest.TestCase):
    def setUp(self):
        fixtures.RegisteredPreviewTests.setUp(self)
        self.extraction_id = self.execute()['extraction_id']
        self.generations = GenerationService(self.service)

    execute = fixtures.RegisteredPreviewTests.execute

    def create(self, key='case', **options):
        return self.generations.create(self.extraction_id, key, provider='qwen', model='qwen-plus', **options)

    def run_generation(self, key, client=None, **options):
        return execute_generation(self.service, generation_id=key, client=client or fixtures.FakeClient(), **options)

    def generation_file(self, key, kind):
        name = 'candidate.san' if kind == 'candidate' else kind + '.json'
        return self.settings.artifact_dir / f'generations/{key}/{name}'

    def corrupt_json(self, key, kind, mutate):
        path = self.generation_file(key, kind)
        value = json.loads(path.read_bytes())
        mutate(value)
        raw = json.dumps(value, sort_keys=True).encode()
        path.write_bytes(raw)  # Controlled temporary evidence corruption.
        with transaction(self.service.engine) as session:
            session.get(GenerationFile, f'generations/{key}/{kind}.json').sha256 = sha256(raw).hexdigest()

    def test_create_freezes_full_request_before_call_and_idempotently_reuses_it(self):
        client = fixtures.FakeClient()
        key = self.create()
        self.assertEqual(self.create(), key)
        result = self.generations.report(key)
        self.assertEqual(client.calls, 0)
        self.assertIsNone(result['attempt'])
        self.assertEqual(result['status'], 'prepared')
        self.assertTrue(result['persistent_registration'])
        self.assertFalse(result['request']['prepared']['persistent_registration'])  # G1 template retained, not rewritten.
        self.assertTrue(result['request']['prepared']['prompt']['messages'][1]['content'])
        with self.assertRaisesRegex(ServiceError, 'generation_idempotency_conflict'):
            self.create(max_output_tokens=4096)

    def test_graph_registers_only_offline_candidate_and_keeps_original_reports(self):
        key, client = self.create(), fixtures.FakeClient()
        original, source = self.service.report(self.run_id), self.ledger.report(self.extraction_id)
        result = self.run_generation(key, client)
        report = self.generations.report(key)
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(result['graph_pending'])
        self.assertEqual(client.calls, 1)
        self.assertEqual({item['kind'] for item in report['files']}, {'request', 'receipt', 'candidate'})
        self.assertEqual(report['candidate']['source_kind'], 'offline_client_test')
        self.assertIsNone(report['candidate']['parent_id'])
        self.assertIsNone(report['contract_revision'])
        self.assertEqual(report['migration_quality_status'], 'not_run')
        self.assertEqual(report['actual_model_calls'], 0)
        self.assertEqual(self.generations.download(key), fixtures.CODE.encode())
        self.assertEqual(self.service.report(self.run_id), original)
        self.assertEqual(self.ledger.report(self.extraction_id), source)
        with closing(sqlite3.connect(self.settings.graph_database)) as connection:
            self.assertGreater(connection.execute('SELECT count(*) FROM checkpoints WHERE thread_id=?',
                ('generation:' + key,)).fetchone()[0], 0)

    def test_prepared_interrupt_resumes_with_one_call(self):
        key, client = self.create(), fixtures.FakeClient()
        result = self.run_generation(key, client, interrupt_after=['prepare_generation'])
        self.assertTrue(result['graph_pending'])
        self.assertEqual(result['status'], 'prepared')
        self.assertEqual(client.calls, 0)
        self.assertEqual(self.run_generation(key, client)['status'], 'completed')
        self.assertEqual(client.calls, 1)

    def test_committed_receipt_interrupt_resumes_without_second_call(self):
        key, client = self.create(), fixtures.FakeClient()
        result = self.run_generation(key, client, interrupt_after=['invoke_offline_client'])
        self.assertEqual(result['status'], 'received')
        self.assertEqual(client.calls, 1)
        unused = fixtures.FakeClient(error=AssertionError('must not call'))
        self.assertEqual(self.run_generation(key, unused)['status'], 'completed')
        self.assertEqual(unused.calls, 0)

    def test_receipt_committed_before_checkpoint_gap_is_reused_after_review(self):
        key, client = self.create(), fixtures.FakeClient()
        original = GenerationService.invoke
        def crash_after_commit(ledger, key, client):
            original(ledger, key, client)
            raise RuntimeError('synthetic checkpoint gap')
        with patch.object(GenerationService, 'invoke', crash_after_commit), self.assertRaises(ServiceError):
            self.run_generation(key, client)
        self.assertEqual(self.generations.report(key)['status'], 'review_required')
        self.assertEqual(client.calls, 1)
        unused = fixtures.FakeClient(error=AssertionError('must reuse'))
        self.assertEqual(self.run_generation(key, unused)['status'], 'completed')
        self.assertEqual(unused.calls, 0)

    def test_finished_job_is_not_invoked_again(self):
        key, client = self.create(), fixtures.FakeClient()
        self.run_generation(key, client)
        self.run_generation(key, client)
        self.assertEqual(client.calls, 1)

    def test_exception_is_unknown_uses_slot_and_never_auto_retries(self):
        key = self.create()
        client = fixtures.FakeClient(error=RuntimeError('credential=secret; source text'))
        with self.assertRaisesRegex(ServiceError, '^generation_client_outcome_unknown_no_retry$'):
            self.run_generation(key, client)
        result = self.generations.report(key)
        self.assertEqual(result['status'], 'review_required')
        self.assertEqual(result['client_outcome'], 'unknown')
        self.assertIsNone(result['offline_client_invocations'])
        self.assertEqual(result['generation_slots_reserved'], 1)
        with self.assertRaisesRegex(ServiceError, 'unresolved_attempt'):
            self.run_generation(key, client)
        self.assertEqual(client.calls, 1)

    def test_real_child_exit_after_call_start_is_unknown_and_not_repeated(self):
        key = self.create()
        probe = Path(__file__).with_name('generation_crash_probe.py')
        completed = subprocess.run([sys.executable, str(probe), str(self.project), key], capture_output=True, timeout=30)
        self.assertEqual(completed.returncode, 29, completed.stderr.decode(errors='replace'))
        self.assertEqual(self.generations.report(key)['status'], 'started')
        client = fixtures.FakeClient()
        with self.assertRaisesRegex(ServiceError, 'unresolved_attempt'):
            self.run_generation(key, client)
        self.assertEqual(client.calls, 0)
        self.assertEqual(self.generations.report(key)['status'], 'review_required')

    def test_invalid_or_truncated_output_records_blocked_receipt_without_candidate(self):
        key = self.create()
        client = fixtures.FakeClient(GenerationResponse('truncated', 'qwen', 'qwen-plus', 'length'))
        result = self.run_generation(key, client)
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(result['candidate'])
        self.assertEqual({item['kind'] for item in result['files']}, {'request', 'receipt'})
        self.assertEqual(self.generations.report(key)['receipt']['error'], 'generation_incomplete_output')
        with self.assertRaisesRegex(ServiceError, 'not_completed'):
            self.generations.download(key)

    def test_budget_overrun_records_block_and_missing_usage_remains_unknown(self):
        key = self.create()
        self.run_generation(key, fixtures.FakeClient(GenerationResponse(fixtures.CODE, 'qwen', 'qwen-plus', 'stop', 1, 8193)))
        self.assertEqual(self.generations.report(key)['receipt']['error'], 'generation_output_budget_exceeded')
        other = self.create('unknown-usage')
        self.run_generation(other, fixtures.FakeClient(GenerationResponse(fixtures.CODE, 'qwen', 'qwen-plus', 'stop')))
        report = self.generations.report(other)
        self.assertEqual(report['receipt']['budget_status'], 'usage_unknown')
        self.assertIsNone(report['receipt']['usage']['input_tokens'])

    def test_drift_does_not_rewrite_history_or_call_client(self):
        key = self.create()
        before = self.generations.report(key)
        altered = {**self.service.implementation_binding(), 'implementation_sha256': '0' * 64}
        client = fixtures.FakeClient()
        with patch.object(self.service, 'implementation_binding', return_value=altered):
            self.assertEqual(self.generations.report(key), before)
            with self.assertRaisesRegex(ServiceError, 'binding_drift'):
                self.run_generation(key, client)
        self.assertEqual(client.calls, 0)

    def test_drift_during_call_blocks_acceptance_and_requires_review(self):
        key = self.create()
        binding = self.service.implementation_binding()
        client = fixtures.FakeClient()
        original = client.generate
        def response(request):
            result = original(request)
            self.service.implementation_binding = lambda: {**binding, 'implementation_sha256': '0' * 64}
            return result
        client.generate = response
        with self.assertRaisesRegex(ServiceError, 'binding_drift'):
            self.run_generation(key, client)
        report = self.generations.report(key)
        self.assertEqual(report['status'], 'review_required')
        self.assertIsNone(report['candidate'])

    def test_unknown_attempt_can_be_reviewed_and_backed_up_after_drift_without_execution(self):
        key = self.create()
        with self.assertRaises(ServiceError):
            self.run_generation(key, fixtures.FakeClient(error=RuntimeError('unknown')))
        create_backup(self.settings, backup_id='reviewed-unknown-generation')
        self.assertEqual(verify_backup(self.settings, 'reviewed-unknown-generation')['status'], 'backup_verified')

    def test_backup_includes_pending_receipt_and_restored_graph_reuses_it(self):
        key = self.create()
        self.run_generation(key, interrupt_after=['invoke_offline_client'])
        before = self.generations.report(key)
        create_backup(self.settings, backup_id='generation-pending')
        verified = verify_backup(self.settings, 'generation-pending')
        self.assertEqual(verified['status'], 'backup_verified')
        restored_settings = replace(self.settings, runtime_dir=self.project / 'var/generation-restored',
            artifact_dir=self.settings.artifact_dir / 'generation-restored')
        restore_backup(restored_settings, 'generation-pending')
        restored = Service(restored_settings)
        self.addCleanup(restored.close)
        self.assertEqual(GenerationService(restored).report(key), before)
        unused = fixtures.FakeClient(error=AssertionError('no repeat'))
        result = execute_generation(restored, generation_id=key, client=unused)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(unused.calls, 0)

    def test_backup_refuses_unresolved_started_attempt(self):
        key = self.create()
        client = fixtures.FakeClient(error=KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            self.run_generation(key, client)
        with self.assertRaisesRegex(ServiceError, 'backup_requires_resolved_generation_attempts'):
            create_backup(self.settings, backup_id='unresolved-generation')

    def test_corrupt_candidate_blocks_report_download_and_backup(self):
        key = self.create()
        self.run_generation(key)
        self.generation_file(key, 'candidate').write_bytes(b'corrupt')
        for action in (lambda: self.generations.report(key), lambda: self.generations.download(key),
                       lambda: create_backup(self.settings, backup_id='corrupt-generation')):
            with self.assertRaises(ValueError):
                action()

    def test_rehashed_wrong_receipt_identity_or_boolean_count_cannot_pass(self):
        key = self.create()
        self.run_generation(key)
        original = self.generation_file(key, 'receipt').read_bytes()
        for mutate in (lambda value: value.update(generation_id='0' * 32),
                       lambda value: value.update(actual_model_calls=False),
                       lambda value: value['usage'].update(output_tokens=True)):
            self.generation_file(key, 'receipt').write_bytes(original)
            # Each next mutation starts from original bytes; the controlled helper updates its hash.
            self.corrupt_json(key, 'receipt', mutate)
            with self.assertRaises(ServiceError):
                self.generations.report(key)

    def test_missing_or_cross_job_candidate_registry_is_rejected(self):
        key = self.create()
        self.run_generation(key)
        with transaction(self.service.engine) as session:
            session.get(GenerationCandidate, key + ':candidate:1').sha256 = '0' * 64
        with self.assertRaises(ServiceError):
            self.generations.report(key)

    def test_os_guard_and_resume_source_options_prevent_parallel_or_new_input(self):
        key, client = self.create(), fixtures.FakeClient()
        with execution_guard(self.settings.runtime_dir), self.assertRaises(RuntimeBusyError):
            self.run_generation(key, client)
        with self.assertRaisesRegex(ServiceError, 'resume_input_not_allowed'):
            execute_generation(self.service, generation_id=key, extraction_id=self.extraction_id, client=client)
        self.assertEqual(client.calls, 0)

    def test_ambient_langsmith_does_not_enable_upload(self):
        key = self.create()
        with patch.dict(os.environ, {'LANGSMITH_TRACING': 'true', 'LANGSMITH_API_KEY': 'not-a-real-key'}):
            with patch('socket.socket.connect', side_effect=AssertionError('network disallowed')):
                result = self.run_generation(key)
        self.assertFalse(result['langsmith_uploaded'])

    def test_http_report_download_are_read_only_and_clearly_offline(self):
        key = self.create()
        self.run_generation(key)
        before = self.generations.report(key)
        client = test_vertical_slice.VerticalSliceTests.app(self).test_client()
        report = client.get(f'/api/v1/generations/{key}/report', base_url=test_vertical_slice.BASE)
        artifact = client.get(f'/api/v1/generations/{key}/artifact', base_url=test_vertical_slice.BASE)
        self.assertEqual(report.status_code, 200)
        self.assertEqual(artifact.status_code, 200)
        self.assertIn('offline_generation_', artifact.headers['Content-Disposition'])
        self.assertEqual(self.generations.report(key), before)
        self.assertEqual(client.post(f'/api/v1/generations/{key}/execute', base_url=test_vertical_slice.BASE).status_code, 403)

    def test_cli_prepares_with_explicit_key_and_only_reads_reports(self):
        output = io.StringIO()
        args = ['prepare-generation', '--extraction-id', self.extraction_id, '--idempotency-key', 'cli-case',
                '--provider', 'qwen', '--model', 'qwen-plus']
        with patch('card_migration_system.interfaces.cli.load_settings', return_value=self.settings), redirect_stdout(output):
            self.assertEqual(main(args), 0)
        key = json.loads(output.getvalue())['generation_id']
        output = io.StringIO()
        with patch('card_migration_system.interfaces.cli.load_settings', return_value=self.settings), redirect_stdout(output):
            self.assertEqual(main(['generation-report', '--generation-id', key]), 0)
        self.assertEqual(json.loads(output.getvalue())['status'], 'prepared')

    def test_upgrade_0003_retains_original_source_and_fixture_reports(self):
        source, original = self.ledger.report(self.extraction_id), self.service.report(self.run_id)
        self.service.close()
        # Simulate a real 0003 snapshot by removing only this test's empty new tables.
        from card_migration_system.persistence.database import engine_for
        engine = engine_for(self.settings.business_database)
        try:
            with engine.begin() as connection:
                from card_migration_system.persistence.migrations import metadata as migration_metadata
                migration_metadata.drop_all(connection)
                metadata.drop_all(connection)
                connection.exec_driver_sql("UPDATE alembic_version SET version_num='0003_ssm_extractions'")
        finally:
            engine.dispose()
        with self.assertRaisesRegex(ValueError, 'schema_mismatch'):
            Service(self.settings)
        initialize(self.settings)
        self.service = Service(self.settings)
        self.addCleanup(self.service.close)
        from card_migration_system.application.extractions import ExtractionService
        self.assertEqual(ExtractionService(self.service).report(self.extraction_id), source)
        self.assertEqual(self.service.report(self.run_id), original)
        with closing(sqlite3.connect(self.settings.business_database)) as connection:
            self.assertEqual(connection.execute('SELECT version_num FROM alembic_version').fetchone()[0], HEAD)

    def test_concurrent_same_key_registers_one_generation_request(self):
        with ThreadPoolExecutor(max_workers=3) as pool:
            keys = list(pool.map(lambda _: self.create('concurrent'), range(3)))
        self.assertEqual(len(set(keys)), 1)
        self.assertEqual(self.generations.report(keys[0])['status'], 'prepared')

    def test_corrupt_request_stops_before_client_or_candidate_registration(self):
        key = self.create()
        with transaction(self.service.engine) as session:
            row = session.get(GenerationJob, key)
            row.request = {**row.request, 'external_calls_permitted': True}
        client = fixtures.FakeClient()
        with self.assertRaisesRegex(ServiceError, 'request_hash_mismatch'):
            self.run_generation(key, client)
        self.assertEqual(client.calls, 0)
        with transaction(self.service.engine) as session:
            self.assertIsNone(session.get(GenerationCandidate, key + ':candidate:1'))
