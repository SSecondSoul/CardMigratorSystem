"""G1 offline boundary tests: no database changes to the user's installation."""
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from hashlib import sha256
import io
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import test_registered_ssm_graph as graph_fixtures
from card_migration_system.adapters.generation import GenerationResponse, OfflineGenerationClient
from card_migration_system.application.generation_preview import prepare_registered_generation
from card_migration_system.interfaces.cli import main
from card_migration_system.prompts.generation import PINS, PromptBindingError, build_generation_messages
from card_migration_system.reporting.identity import digest
from card_migration_system.stages.generation import (GenerationBoundaryError, PreparedGeneration,
    model_configuration, prepare_generation, run_offline_generation)

REPOSITORY = Path(__file__).resolve().parents[1]/'engine'
CODE = "<template><article>offline test</article></template><script>throw new Error('must not execute')</script><style></style>"


class FakeClient(OfflineGenerationClient):
    def __init__(self, response=None, error=None):
        self.calls = 0
        self.response = response or GenerationResponse(CODE, 'qwen', 'qwen-plus', 'stop', 100, 20)
        self.error = error

    def generate(self, request):
        self.calls += 1
        request['model_config']['model'] = 'mutated-caller-copy'
        if self.error:
            raise self.error
        return self.response


def copy_prompt_sources(root):
    for name in PINS:
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY / name, destination)


class GenerationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        copy_prompt_sources(self.root)
        self.source = b'<template><article>source</article></template>'
        self.ssm = json.dumps({'schema_version': '3.0', 'metadata': {'source_file': 'Counter.vue'}}).encode()
        self.key, self.input_id = 'a' * 32, 'b' * 32
        self.source_path = f'inputs/{self.input_id}/Counter.vue'
        self.report = {'status': 'completed', 'extraction_id': self.key, 'request_sha256': 'c' * 64,
            'migration_quality_status': 'not_run', 'contract_evaluation': {'status': 'pass'}, 'receipt': {'status': 'completed'},
            'actual_model_calls': 0, 'production_ready': False, 'langsmith_uploaded': False,
            'request': {'source': {'input_id': self.input_id, 'source_sha256': sha256(self.source).hexdigest(), 'filename': 'Counter.vue'}},
            'files': [{'kind': 'ssm', 'relative_path': f'ssm-extractions/{self.key}/ssm.json', 'sha256': sha256(self.ssm).hexdigest()}],
            'contract_projection': {'evidence_index': [{'path': self.source_path, 'sha256': sha256(self.source).hexdigest()}]}}
        self.implementation = {'implementation_sha256': 'd' * 64, 'dependency_lock_sha256': 'e' * 64,
                              'p1_sha256': 'f' * 64, 'mode': 'development_stub', 'fixture_protocol': 'p2b-control-v1'}

    def prepare(self, **overrides):
        values = dict(repository_root=self.root, extraction_report=self.report, ssm_bytes=self.ssm,
            source_bytes=self.source, source_path=self.source_path, implementation=self.implementation,
            provider='qwen', model='qwen-plus')
        values.update(overrides)
        return prepare_generation(**values)

    def reseal(self, prepared, change):
        value = prepared.payload()
        change(value)
        content = json.dumps(value, sort_keys=True, allow_nan=False).encode()
        return PreparedGeneration(content, sha256(content).hexdigest())

    def test_request_is_deterministic_detached_and_not_registered(self):
        prepared = self.prepare()
        self.assertEqual(prepared, self.prepare())
        snapshot = prepared.payload()
        self.implementation['implementation_sha256'] = '0' * 64
        snapshot['model_config']['model'] = 'changed'
        self.assertEqual(prepared.payload()['model_config']['model'], 'qwen-plus')
        self.assertEqual(prepared.payload()['implementation']['implementation_sha256'], 'd' * 64)
        self.assertFalse(snapshot['external_calls_permitted'])
        self.assertFalse(snapshot['persistent_registration'])

    def test_existing_prompt_rules_are_retained_without_importing_server(self):
        messages, pins = build_generation_messages(self.root, json.loads(self.ssm))
        text = messages[1]['content']
        for rule in ('CLASS', 'this.data.get', 'this.watch', 'initData', 'trackby'):
            self.assertIn(rule.lower(), text.lower())
        self.assertEqual(pins, PINS)
        self.assertNotIn('local_server.api.evaluation_routes', sys.modules)
        self.assertEqual(messages[0]['role'], 'system')

    def test_prompt_drift_is_blocked_before_builder_execution(self):
        path = self.root / 'prompts/generation_builder.py'
        path.write_text("raise AssertionError('never execute whole server')", encoding='utf-8')
        with self.assertRaisesRegex(PromptBindingError, 'generation_prompt_source_drift'):
            self.prepare()

    def test_missing_prompt_and_class_rule_drift_block(self):
        path = self.root / 'prompts/generation_builder.py'
        path.write_text('CLASS_BINDING_RULE = "changed"', encoding='utf-8')
        with self.assertRaisesRegex(PromptBindingError, 'source_drift'):
            self.prepare()
        # A distinct absent temporary checkout; do not delete any files.
        with self.assertRaisesRegex(PromptBindingError, 'source_missing'):
            self.prepare(repository_root=self.root / 'absent')

    def test_non_completed_or_untrusted_extraction_cannot_prepare(self):
        for status in ('prepared', 'received', 'blocked', 'review_required'):
            with self.subTest(status=status), self.assertRaises(GenerationBoundaryError):
                self.prepare(extraction_report={**self.report, 'status': status})
        for values in ({'receipt': None}, {'actual_model_calls': False}, {'production_ready': True},
                       {'contract_evaluation': {'status': 'not_run'}}, {'migration_quality_status': 'pass'}):
            with self.subTest(values=values), self.assertRaises(GenerationBoundaryError):
                self.prepare(extraction_report={**self.report, **values})

    def test_source_and_ssm_bytes_and_references_must_match(self):
        for values in ({'source_bytes': self.source + b' '}, {'ssm_bytes': self.ssm + b' '},
                       {'source_path': 'inputs/other/Counter.vue'}):
            with self.subTest(values=values), self.assertRaises(GenerationBoundaryError):
                self.prepare(**values)
        self.report['files'][0]['relative_path'] = 'ssm-extractions/other/ssm.json'
        with self.assertRaisesRegex(GenerationBoundaryError, 'ssm_reference_mismatch'):
            self.prepare()

    def test_unsupported_ssm_schema_and_filename_are_not_silently_used(self):
        for ssm in ({'schema_version': '4', 'metadata': {'source_file': 'Counter.vue'}},
                    {'schema_version': '3.0', 'metadata': {'source_file': 'Other.vue'}}):
            raw = json.dumps(ssm).encode()
            self.report['files'][0]['sha256'] = sha256(raw).hexdigest()
            with self.subTest(ssm=ssm), self.assertRaisesRegex(GenerationBoundaryError, 'invalid_ssm'):
                self.prepare(ssm_bytes=raw)

    def test_model_config_rejects_credentials_nonfinite_and_boolean_budgets(self):
        for changes in ({'provider': 'https://endpoint?key=secret'}, {'model': 'a\nsecret'},
                        {'max_output_tokens': True}, {'max_total_tokens': 1}, {'timeout_seconds': False},
                        {'temperature': True}, {'temperature': float('nan')}, {'timeout_seconds': 301}):
            options = {'provider': 'qwen', 'model': 'qwen-plus', **changes}
            with self.subTest(changes=changes), self.assertRaises(GenerationBoundaryError):
                model_configuration(**options)

    def test_fingerprint_covers_prompt_model_budget_and_implementation(self):
        first = self.prepare()
        for changes in ({'model': 'other'}, {'max_total_tokens': 65536}, {'max_output_tokens': 4096}, {'timeout_seconds': 120}):
            self.assertNotEqual(first.request_sha256, self.prepare(**changes).request_sha256)
        self.implementation['implementation_sha256'] = '0' * 64
        self.assertNotEqual(first.request_sha256, self.prepare().request_sha256)

    def test_tampered_seal_and_rehashed_authority_or_extra_fields_block_before_call(self):
        first, client = self.prepare(), FakeClient()
        with self.assertRaisesRegex(GenerationBoundaryError, 'request_hash_mismatch'):
            run_offline_generation(replace(first, payload_bytes=first.payload_bytes + b' '), client)
        for change in (lambda value: value.update(external_calls_permitted=True),
                       lambda value: value.update(api_key='not-allowed'),
                       lambda value: value['model_config'].update(api_key='not-allowed'),
                       lambda value: value['source'].update(path='../outside'),
                       lambda value: value['prompt'].update(source_pins={}),
                       lambda value: value['prompt']['messages'][1].update(content='drift')):
            with self.assertRaises(GenerationBoundaryError):
                run_offline_generation(self.reseal(first, change), client)
        self.assertEqual(client.calls, 0)

    def test_no_default_or_generic_external_client(self):
        with self.assertRaisesRegex(GenerationBoundaryError, 'offline_client_required'):
            run_offline_generation(self.prepare(), object())

    def test_local_candidate_is_not_a_real_model_call_or_registered_san_revision(self):
        prepared, client = self.prepare(), FakeClient()
        with patch('socket.create_connection', side_effect=AssertionError('no network')):
            result = run_offline_generation(prepared, client)
        self.assertEqual(client.calls, 1)
        self.assertEqual(result['candidate']['code'], CODE)  # Never execute its script.
        self.assertEqual(result['candidate']['sha256'], sha256(CODE.encode()).hexdigest())
        self.assertEqual(result['candidate']['provenance'], 'offline_client_test')
        self.assertIsNone(result['contract_revision'])
        self.assertIsNone(result['candidate']['parent_revision_id'])
        self.assertFalse(result['persistent_registration'])
        self.assertEqual(result['actual_model_calls'], 0)
        self.assertEqual(result['migration_quality_status'], 'not_run')
        self.assertEqual(prepared.payload()['model_config']['model'], 'qwen-plus')

    def test_client_exception_is_sanitized_and_never_retried(self):
        client = FakeClient(error=RuntimeError('key=private; raw source code'))
        with self.assertRaisesRegex(GenerationBoundaryError, '^generation_client_outcome_unknown_no_retry$'):
            run_offline_generation(self.prepare(), client)
        self.assertEqual(client.calls, 1)

    def test_model_identity_and_truncation_are_rejected(self):
        for changes in ({'provider': 'other'}, {'model': 'other'}, {'finish_reason': 'length'}, {'finish_reason': 'content_filter'}):
            with self.subTest(changes=changes), self.assertRaises(GenerationBoundaryError):
                run_offline_generation(self.prepare(), FakeClient(replace(FakeClient().response, **changes)))

    def test_usage_missing_is_unknown_not_zero_and_reported_budget_is_checked(self):
        result = run_offline_generation(self.prepare(), FakeClient(GenerationResponse(CODE, 'qwen', 'qwen-plus', 'stop')))
        self.assertEqual(result['budget_status'], 'usage_unknown')
        self.assertIsNone(result['usage']['input_tokens'])
        self.assertIsNone(result['usage']['output_tokens'])
        for changes in ({'input_tokens': True}, {'output_tokens': -1}, {'output_tokens': 8193}, {'input_tokens': 32768}):
            with self.subTest(changes=changes), self.assertRaises(GenerationBoundaryError):
                run_offline_generation(self.prepare(), FakeClient(replace(FakeClient().response, **changes)))

    def test_plain_sfc_shape_only_rejects_fences_prose_empty_and_invalid_utf8(self):
        for code in ('', '```san\n' + CODE + '\n```', 'Here is the code:' + CODE,
                     '<script>only fragment</script>', CODE + '\x00', '\ud800'):
            with self.subTest(code=repr(code)[:40]), self.assertRaises(GenerationBoundaryError):
                run_offline_generation(self.prepare(), FakeClient(replace(FakeClient().response, code=code)))


class RegisteredPreviewTests(unittest.TestCase):
    def setUp(self):
        graph_fixtures.RegisteredGraphTests.setUp(self)
        copy_prompt_sources(self.project/'engine')

    execute = graph_fixtures.RegisteredGraphTests.execute

    def test_preview_uses_real_registered_ssm_without_source_reparse_or_writes(self):
        key = self.execute()['extraction_id']
        before = self.ledger.report(key)
        original = self.service.report(self.run_id)
        with patch('card_migration_system.adapters.ssm.SSMExtractor.extract', side_effect=AssertionError('no reparse')):
            prepared = prepare_registered_generation(self.service, key, provider='qwen', model='qwen-plus')
        self.assertEqual(prepared.payload()['ssm']['extraction_id'], key)
        self.assertEqual(self.ledger.report(key), before)
        self.assertEqual(self.service.report(self.run_id), original)
        self.assertEqual(list(self.settings.artifact_dir.glob('generations/*')), [])

    def test_cli_preview_no_model_credentials_or_prompt_output_and_no_execution_flag(self):
        key = self.execute()['extraction_id']
        output = io.StringIO()
        with patch('card_migration_system.interfaces.cli.load_settings', return_value=self.settings), redirect_stdout(output):
            self.assertEqual(main(['generation-preview', '--extraction-id', key, '--provider', 'qwen', '--model', 'qwen-plus']), 0)
        result = json.loads(output.getvalue())
        self.assertFalse(result['external_calls_permitted'])
        self.assertFalse(result['persistent_registration'])
        self.assertEqual(result['actual_model_calls'], 0)
        self.assertNotIn('messages', result)
        self.assertNotIn('source_code', result)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['generation-preview', '--extraction-id', key, '--provider', 'qwen', '--model', 'qwen-plus', '--execute'])
