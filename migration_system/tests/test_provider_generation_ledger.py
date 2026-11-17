"""Recorded exchanges, real durable graph/DB; synthetic transport, no paid calls."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_generation_boundary as fixtures
from card_migration_system.adapters.qwen_transport import Exchange, InputTokenBound, QwenHTTPSClient
from card_migration_system.application.generation_preview import prepare_registered_generation
from card_migration_system.application.provider_generations import (ProviderGenerationService, RecordedOfflineTransport, path_for)
from card_migration_system.application.service import Service, ServiceError
from card_migration_system.graph.provider_generation import execute_recorded_generation
from card_migration_system.persistence.backup import create_backup, verify_backup, restore_backup
from card_migration_system.persistence.database import initialize, transaction, HEAD, engine_for
from card_migration_system.persistence.provider_generations import ProviderGenerationJob as Job, ProviderGenerationFile as File, metadata
from card_migration_system.persistence.runtime_lock import execution_guard, RuntimeBusyError


class SyntheticTransport(RecordedOfflineTransport):
    def __init__(self, *, fault=None, mutate=None):
        self.calls, self.fault, self.mutate = 0, fault, mutate

    def exchange(self, plan):
        self.calls += 1
        if self.fault:
            raise self.fault
        value = {'id': 'fixture-response', 'model': 'qwen-plus',
            'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': fixtures.CODE}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120}}
        if self.mutate:
            self.mutate(value)
        return Exchange(200, json.dumps(value).encode())


class ProviderLedgerTests(unittest.TestCase):
    execute = fixtures.RegisteredPreviewTests.execute

    def setUp(self):
        fixtures.RegisteredPreviewTests.setUp(self)
        self.extraction_id = self.execute()['extraction_id']
        self.provider = ProviderGenerationService(self.service)

    def create(self, key='recorded', **options):
        prepared = prepare_registered_generation(self.service, self.extraction_id, provider='qwen', model='qwen-plus')
        bound = InputTokenBound(prepared.payload()['prompt']['messages_sha256'], 'qwen-plus', 200,
            'upper_bound', 'synthetic-counter', '1' * 64, True)
        return self.provider.create(self.extraction_id, key, **{'token_bound': bound,
            'provider': 'qwen', 'model': 'qwen-plus', **options})

    def generate(self, key, transport=None, **options):
        return execute_recorded_generation(self.service, generation_id=key, transport=transport or SyntheticTransport(), **options)

    def file(self, key, kind):
        return self.settings.artifact_dir / path_for(key, kind)

    def corrupt(self, key, kind, mutation):
        path = self.file(key, kind)
        value = json.loads(path.read_bytes())
        mutation(value)
        raw = json.dumps(value).encode()
        path.write_bytes(raw)  # Fault injection in disposable test artifacts only.
        with transaction(self.service.engine) as session:
            session.get(File, path_for(key, kind)).sha256 = sha256(raw).hexdigest()

    def test_frozen_request_and_idempotency_with_no_attempt_or_model_call(self):
        key = self.create()
        self.assertEqual(self.create(), key)
        report = self.provider.report(key)
        self.assertEqual(report['status'], 'prepared')
        self.assertIsNone(report['attempt'])
        self.assertEqual(report['slots_reserved'], 0)
        self.assertEqual(report['actual_model_calls'], 0)
        self.assertFalse(report['request']['external_calls_permitted'])
        self.assertEqual({f['kind'] for f in report['files']}, {'plan', 'request'})
        with self.assertRaisesRegex(ServiceError, 'idempotency_conflict'):
            self.create(timeout_seconds=120)

    def test_live_mode_and_real_client_are_rejected_before_any_attempt(self):
        with self.assertRaisesRegex(ServiceError, 'live_counter_and_approval_not_integrated'):
            self.create(execution_mode='provider_https')
        key = self.create()
        with self.assertRaisesRegex(ServiceError, 'offline_transport_required'):
            self.provider.invoke(key, QwenHTTPSClient('not-a-real-key'))
        self.assertIsNone(self.provider.report(key)['attempt'])

    def test_missing_or_estimated_input_count_cannot_start_or_create(self):
        prepared = prepare_registered_generation(self.service, self.extraction_id, provider='qwen', model='qwen-plus')
        for bound in (None, InputTokenBound(prepared.payload()['prompt']['messages_sha256'], 'qwen-plus', 100,
                                           'estimate', 'test', '1' * 64, True)):
            with self.assertRaises(ValueError):
                self.create(token_bound=bound)
        with transaction(self.service.engine) as session:
            from sqlalchemy import select
            self.assertEqual(list(session.scalars(select(Job.id))), [])

    def test_graph_registers_raw_response_but_never_real_generation_revision(self):
        original = self.service.report(self.run_id)
        key, transport = self.create(), SyntheticTransport()
        result = self.generate(key, transport)
        report = self.provider.report(key)
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(result['graph_pending'])
        self.assertEqual(transport.calls, 1)
        self.assertEqual(report['actual_model_calls'], 0)
        self.assertEqual(report['usage']['total_tokens'], 120)
        self.assertEqual(report['candidate']['provenance'], 'offline_transport_test')
        self.assertIsNone(report['contract_revision'])
        self.assertEqual(report['migration_quality_status'], 'not_run')
        self.assertEqual({f['kind'] for f in report['files']}, {'plan', 'request', 'response', 'receipt', 'candidate'})
        self.assertEqual(self.service.report(self.run_id), original)
        self.assertEqual(self.generate(key, transport)['status'], 'completed')
        self.assertEqual(transport.calls, 1)
        with closing(sqlite3.connect(self.settings.graph_database)) as connection:
            self.assertGreater(connection.execute('SELECT count(*) FROM checkpoints WHERE thread_id=?', ('provider-generation:' + key,)).fetchone()[0], 0)

    def test_start_is_committed_before_entering_transport(self):
        key, ledger = self.create(), self.provider
        class CheckStart(SyntheticTransport):
            def exchange(self, plan):
                report = ledger.report(key)
                self_test.assertEqual(report['status'], 'started')
                self_test.assertEqual(report['attempt']['status'], 'started')
                return super().exchange(plan)
        self_test = self
        self.generate(key, CheckStart())

    def test_prepared_interrupt_and_received_interrupt_resume_without_duplicate(self):
        for node in ('prepare_transport', 'record_exchange'):
            key, transport = self.create(node), SyntheticTransport()
            self.assertTrue(self.generate(key, transport, interrupt_after=[node])['graph_pending'])
            count = transport.calls
            self.assertEqual(count, 0 if node == 'prepare_transport' else 1)
            self.assertEqual(self.generate(key, transport)['status'], 'completed')
            self.assertEqual(transport.calls, 1)

    def test_receipt_checkpoint_gap_is_reused_even_after_review(self):
        key, transport = self.create(), SyntheticTransport()
        original = ProviderGenerationService._invoke_locked
        def gap(ledger, key, transport):
            original(ledger, key, transport)
            raise RuntimeError('gap')
        with patch.object(ProviderGenerationService, '_invoke_locked', gap), self.assertRaises(ServiceError):
            self.generate(key, transport)
        self.assertEqual(self.provider.report(key)['status'], 'review_required')
        self.assertEqual(self.generate(key, transport)['status'], 'completed')
        self.assertEqual(transport.calls, 1)

    def test_timeout_records_unknown_usage_and_never_retries(self):
        key, transport = self.create(), SyntheticTransport(fault=TimeoutError('raw-secret-source'))
        for _ in range(2):
            report = self.generate(key, transport)
            self.assertEqual(report['status'], 'review_required')
            self.assertIsNone(report['usage'])
            self.assertEqual(report['slots_reserved'], 1)
        self.assertEqual(transport.calls, 1)
        receipt = self.file(key, 'receipt').read_text()
        self.assertNotIn('raw-secret-source', receipt)

    def test_invalid_truncated_or_overbudget_output_keeps_usage(self):
        for fault in ('code', 'finish', 'budget'):
            key = self.create(fault)
            def mutate(value):
                if fault == 'code': value['choices'][0]['message']['content'] = 'not code'
                if fault == 'finish': value['choices'][0]['finish_reason'] = 'length'
                if fault == 'budget': value['usage'] = {'prompt_tokens': 100, 'completion_tokens': 9000, 'total_tokens': 9100}
            result = self.generate(key, SyntheticTransport(mutate=mutate))
            self.assertEqual(result['status'], 'blocked')
            self.assertIsNotNone(result['usage'])
            self.assertIsNone(self.provider.report(key)['candidate'])

    def test_http_error_and_missing_usage_require_review_and_preserve_response(self):
        for fault in ('http', 'usage'):
            key = self.create(fault)
            class FaultTransport(SyntheticTransport):
                def exchange(self, plan):
                    raw = super().exchange(plan)
                    return Exchange(503, raw.body) if fault == 'http' else raw
            transport = FaultTransport(mutate=lambda v: v.pop('usage'))
            self.assertEqual(self.generate(key, transport)['status'], 'review_required')
            self.assertTrue(self.file(key, 'response').is_file())
            self.generate(key, transport)
            self.assertEqual(transport.calls, 1)

    def test_corrupt_receipt_identity_or_cross_source_never_passes_rehashed(self):
        for mutation in (lambda v: v.update(generation_id='f' * 32),
                         lambda v: v.update(execution_mode='provider_https'),
                         lambda v: v.update(schema_version=True),
                         lambda v: v['outcome'].update(actual_model_calls=1),
                         lambda v: v['file_refs']['candidate'].update(path='other/candidate.san')):
            key = self.create('corrupt-' + str(id(mutation)))
            self.generate(key)
            self.corrupt(key, 'receipt', mutation)
            with self.assertRaises(ValueError):
                self.provider.report(key)

    def test_corrupt_raw_response_or_candidate_blocks_report_and_backup(self):
        key = self.create()
        self.generate(key)
        self.file(key, 'response').write_bytes(b'corrupt')
        with self.assertRaises(ValueError): self.provider.report(key)
        with self.assertRaises(ValueError): create_backup(self.settings, backup_id='corrupt-recorded')

    def test_rehashed_candidate_bytes_must_match_response_not_only_its_file_ref(self):
        key = self.create()
        self.generate(key)
        changed = fixtures.CODE.encode() + b' '
        self.file(key, 'candidate').write_bytes(changed)
        fingerprint = sha256(changed).hexdigest()
        with transaction(self.service.engine) as session:
            session.get(File, path_for(key, 'candidate')).sha256 = fingerprint
        self.corrupt(key, 'receipt', lambda r: r['file_refs']['candidate'].update(sha256=fingerprint))
        with self.assertRaisesRegex(ServiceError, 'candidate_mismatch'):
            self.provider.report(key)

    def test_orphan_receipt_after_file_commit_gap_never_authorizes_resend(self):
        key, transport = self.create(), SyntheticTransport()
        original = self.service.storage.put
        def crash(path, content):
            result = original(path, content)
            if path == path_for(key, 'receipt'):
                raise RuntimeError('DB receipt not committed')
            return result
        with patch.object(self.service.storage, 'put', side_effect=crash), self.assertRaises(ServiceError):
            self.generate(key, transport)
        self.assertTrue(self.file(key, 'receipt').exists())
        report = self.provider.report(key)
        self.assertIsNone(report['receipt'])
        self.assertIsNone(report['transport_invocations'])
        self.assertEqual({f['kind'] for f in report['files']}, {'plan', 'request'})
        with self.assertRaisesRegex(ServiceError, 'unresolved_attempt'):
            self.generate(key, transport)
        self.assertEqual(transport.calls, 1)

    def test_rehashed_boolean_http_status_is_not_an_integer(self):
        key = self.create()
        self.generate(key)
        self.corrupt(key, 'receipt', lambda r: r.update(http_status=True))
        with self.assertRaisesRegex(ServiceError, 'http_status_invalid'):
            self.provider.report(key)

    def test_drift_after_response_keeps_known_usage_and_no_new_exchange(self):
        key, service = self.create(), self.service
        initial = service.implementation_binding()
        class DriftTransport(SyntheticTransport):
            def exchange(self, plan):
                result = super().exchange(plan)
                service.implementation_binding = lambda: {**initial, 'implementation_sha256': '0' * 64}
                return result
        transport = DriftTransport()
        with self.assertRaisesRegex(ServiceError, 'binding_drift'):
            self.generate(key, transport)
        self.assertEqual(self.provider.report(key)['usage']['total_tokens'], 120)
        self.assertEqual(self.provider.report(key)['status'], 'review_required')
        with self.assertRaisesRegex(ServiceError, 'binding_drift'): self.generate(key, transport)
        self.assertEqual(transport.calls, 1)

    def test_real_child_exit_after_start_retains_unknown_slot(self):
        key = self.create()
        probe = Path(__file__).with_name('provider_crash_probe.py')
        completed = subprocess.run([sys.executable, str(probe), str(self.project), key], capture_output=True, timeout=30)
        self.assertEqual(completed.returncode, 31, completed.stderr.decode(errors='replace'))
        self.assertEqual(self.provider.report(key)['status'], 'started')
        transport = SyntheticTransport()
        with self.assertRaisesRegex(ServiceError, 'unresolved_attempt'): self.generate(key, transport)
        report = self.provider.report(key)
        self.assertEqual(report['status'], 'review_required')
        self.assertIsNone(report['transport_invocations'])
        self.assertEqual(report['slots_reserved'], 1)
        self.assertEqual(transport.calls, 0)

    def test_backup_restores_received_response_and_resumes_with_zero_dispatch(self):
        key = self.create()
        self.generate(key, interrupt_after=['record_exchange'])
        before = self.provider.report(key)
        create_backup(self.settings, backup_id='recorded-received')
        self.assertEqual(verify_backup(self.settings, 'recorded-received')['status'], 'backup_verified')
        settings = replace(self.settings, runtime_dir=self.project / 'var/restored-recorded',
            artifact_dir=self.settings.artifact_dir / 'restored-recorded')
        restore_backup(settings, 'recorded-received')
        service = Service(settings)
        self.addCleanup(service.close)
        self.assertEqual(ProviderGenerationService(service).report(key), before)
        transport = SyntheticTransport(fault=AssertionError('no second call'))
        self.assertEqual(execute_recorded_generation(service, generation_id=key, transport=transport)['status'], 'completed')
        self.assertEqual(transport.calls, 0)

    def test_unresolved_start_blocks_backup_but_explicit_review_can_preserve_it(self):
        key = self.create()
        with self.assertRaises(KeyboardInterrupt): self.provider.invoke(key, SyntheticTransport(fault=KeyboardInterrupt()))
        with self.assertRaisesRegex(ServiceError, 'resolved_provider_attempts'):
            create_backup(self.settings, backup_id='recorded-started')
        self.provider.review(key, 'provider_unknown_outcome')
        create_backup(self.settings, backup_id='recorded-reviewed')
        self.assertEqual(verify_backup(self.settings, 'recorded-reviewed')['status'], 'backup_verified')

    def test_concurrent_same_key_and_runtime_lock_prevent_parallel_dispatch(self):
        with ThreadPoolExecutor(max_workers=3) as pool:
            keys = list(pool.map(lambda _: self.create('concurrent'), range(3)))
        self.assertEqual(len(set(keys)), 1)
        transport = SyntheticTransport()
        with execution_guard(self.settings.runtime_dir), self.assertRaises(RuntimeBusyError):
            self.provider.invoke(keys[0], transport)
        self.assertEqual(transport.calls, 0)

    def test_ambient_tracing_cannot_enable_upload_or_network(self):
        key = self.create()
        with patch.dict(os.environ, {'LANGSMITH_TRACING': 'true', 'LANGSMITH_API_KEY': 'not-a-real-key'}), \
                patch('socket.socket.connect', side_effect=AssertionError('no network')):
            self.assertFalse(self.generate(key)['langsmith_uploaded'])

    def test_upgrade_0004_preserves_registered_ssm_and_g2_records(self):
        from card_migration_system.application.generations import GenerationService
        g2 = GenerationService(self.service)
        g2key = g2.create(self.extraction_id, 'before-0005', provider='qwen', model='qwen-plus')
        before, source = g2.report(g2key), self.ledger.report(self.extraction_id)
        self.service.close()
        engine = engine_for(self.settings.business_database)
        try:
            with engine.begin() as connection:
                from card_migration_system.persistence.migrations import metadata as migration_metadata
                migration_metadata.drop_all(connection)
                metadata.drop_all(connection)
                connection.exec_driver_sql("UPDATE alembic_version SET version_num='0004_generation_ledger'")
        finally:
            engine.dispose()
        with self.assertRaisesRegex(ValueError, 'schema_mismatch'): Service(self.settings)
        initialize(self.settings)
        self.service = Service(self.settings)
        self.addCleanup(self.service.close)
        from card_migration_system.application.extractions import ExtractionService
        self.assertEqual(ExtractionService(self.service).report(self.extraction_id), source)
        self.assertEqual(GenerationService(self.service).report(g2key), before)
        with closing(sqlite3.connect(self.settings.business_database)) as connection:
            self.assertEqual(connection.execute('SELECT version_num FROM alembic_version').fetchone()[0], HEAD)
