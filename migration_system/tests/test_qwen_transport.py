"""G3 protocol fixtures only. No real credentials, provider sockets or model calls."""
from dataclasses import replace
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

import test_generation_boundary as fixtures
from card_migration_system.adapters.qwen_transport import (CallPermit, ENDPOINT, Exchange, InputTokenBound,
    MAX_RESPONSE_BYTES, NoRedirect, QwenHTTPSClient, build_qwen_plan, inspect_exchange)
from card_migration_system.application.generations import GenerationService
from card_migration_system.contracts import load_p1_contracts
from card_migration_system.reporting.provider_generation import freeze_provider_contract, project_provider_artifact
from card_migration_system.stages.generation import GenerationBoundaryError


class QwenTransportTests(unittest.TestCase):
    setUp = fixtures.GenerationBoundaryTests.setUp
    prepare = fixtures.GenerationBoundaryTests.prepare

    def plan(self, **options):
        prepared = self.prepare()
        bound = InputTokenBound(prepared.payload()['prompt']['messages_sha256'], 'qwen-plus', 200,
            'upper_bound', 'synthetic-test-counter', '1' * 64, True)
        return build_qwen_plan(prepared, **{'token_bound': bound, **options})

    def permit(self, plan):
        return CallPermit(plan.fingerprint, 'a' * 32 + ':generate:1', True, True)

    def response(self, **updates):
        value = {'id': 'chatcmpl-synthetic-fixture', 'model': 'qwen-plus',
            'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': fixtures.CODE}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120}}
        value.update(updates)
        return Exchange(200, json.dumps(value).encode())

    def test_payload_uses_exact_frozen_messages_and_explicit_nonstreaming_cap(self):
        plan = self.plan()
        body = json.loads(plan.wire_body)
        self.assertEqual(body['messages'], plan.prepared.payload()['prompt']['messages'])
        self.assertEqual(body['max_tokens'], 8192)
        self.assertFalse(body['stream'])
        self.assertFalse(body['enable_thinking'])
        self.assertNotIn('output_file_path', body)
        self.assertNotIn('api_key', body)
        self.assertNotIn('extra_body', body)

    def test_endpoint_allowlist_rejects_redirect_targets_credentials_ports_and_controls(self):
        for endpoint in ('http://127.0.0.1/x', ENDPOINT + '?key=secret', ENDPOINT + '#fragment',
                         ENDPOINT.replace('dashscope.aliyuncs.com', 'dashscope.aliyuncs.com.evil.test'),
                         ENDPOINT.replace('https://', 'https://user:secret@'),
                         ENDPOINT.replace('.com/', '.com:443/'), '\n' + ENDPOINT):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                self.plan(endpoint=endpoint)
        self.plan(endpoint='https://ws-example.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions')

    def test_unknown_provider_or_model_profile_not_silently_routed(self):
        with self.assertRaisesRegex(GenerationBoundaryError, 'profile_unsupported'):
            build_qwen_plan(self.prepare(provider='other'))
        with self.assertRaisesRegex(GenerationBoundaryError, 'profile_unsupported'):
            build_qwen_plan(self.prepare(model='qwen-unknown'))

    def test_preflight_blocks_missing_estimated_wrong_wrapper_or_overbudget_bound(self):
        for plan in (self.plan(token_bound=None), self.plan(token_bound=replace(self.plan().bound, method='estimate')),
                     self.plan(token_bound=replace(self.plan().bound, includes_chat_wrapper=False)),
                     self.plan(token_bound=replace(self.plan().bound, count=32768))):
            with self.assertRaises(GenerationBoundaryError):
                plan.preflight()
        self.plan().preflight()

    def test_bound_is_tied_to_model_message_fingerprint_and_counter(self):
        for change in ({'model': 'other'}, {'messages_sha256': '0' * 64}, {'count': True},
                       {'counter_sha256': 'invalid'}, {'includes_chat_wrapper': 1}):
            with self.subTest(change=change), self.assertRaises(GenerationBoundaryError):
                self.plan(token_bound=replace(self.plan().bound, **change))

    def test_plan_hash_covers_bound_endpoint_and_wire_and_cannot_be_modified(self):
        plan = self.plan()
        self.assertNotEqual(plan.fingerprint, self.plan(token_bound=replace(plan.bound, count=201)).fingerprint)
        self.assertNotEqual(plan.fingerprint, self.plan(endpoint='https://ws-test.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions').fingerprint)
        with self.assertRaisesRegex(GenerationBoundaryError, 'plan_drift'):
            replace(plan, wire_body=plan.wire_body + b' ').verify()

    def test_network_is_disabled_by_default_and_credential_is_not_in_repr(self):
        client, plan = QwenHTTPSClient('test-not-a-real-key'), self.plan()
        self.assertNotIn('test-not-a-real-key', repr(client))
        with patch('socket.socket.connect', side_effect=AssertionError('no network')):
            with self.assertRaisesRegex(GenerationBoundaryError, 'network_disabled'):
                client.send(plan, self.permit(plan))

    def test_no_send_without_durable_start_approval_or_matching_permit(self):
        plan, client = self.plan(), QwenHTTPSClient('test-not-a-real-key', network_enabled=True)
        with patch.object(client, '_post', side_effect=AssertionError('must not send')) as post:
            for permit in (None, replace(self.permit(plan), durable_start_recorded=False),
                           replace(self.permit(plan), explicit_call_approved=False),
                           replace(self.permit(plan), plan_sha256='0' * 64)):
                with self.assertRaises(GenerationBoundaryError):
                    client.send(plan, permit)
            self.assertEqual(post.call_count, 0)

    def test_unknown_transport_outcome_has_no_usage_guess_and_no_retry(self):
        plan, client = self.plan(), QwenHTTPSClient('test-not-a-real-key', network_enabled=True)
        with patch.object(client, '_post', side_effect=TimeoutError('test-secret and raw source')) as post:
            result = client.send(plan, self.permit(plan))
            with self.assertRaisesRegex(GenerationBoundaryError, 'already_used'):
                client.send(plan, self.permit(plan))
        self.assertEqual(post.call_count, 1)
        self.assertEqual(result['status'], 'review_required')
        self.assertIsNone(result['usage'])
        self.assertIsNone(result['actual_model_calls'])
        self.assertNotIn('test-secret', str(result))

    def test_https_options_drop_proxies_and_redirects_and_bound_response_read(self):
        client, plan = QwenHTTPSClient('test-not-a-real-key'), self.plan()
        exchange = self.response()
        captured = {}
        class FakeResponse:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size): captured['size'] = size; return exchange.body
        class FakeOpener:
            def open(self, req, **kwargs):
                captured.update(url=req.full_url, body=req.data, timeout=kwargs['timeout'],
                    authorization=req.get_header('Authorization'))
                return FakeResponse()
        def build(*handlers): captured['handlers'] = handlers; return FakeOpener()
        with patch('card_migration_system.adapters.qwen_transport.request.build_opener', side_effect=build):
            with patch('socket.socket.connect', side_effect=AssertionError('no sockets')):
                received = client._post(plan)
        self.assertEqual(received, exchange)
        self.assertEqual(captured['size'], MAX_RESPONSE_BYTES + 1)
        self.assertEqual(captured['body'], plan.wire_body)
        self.assertEqual(captured['timeout'], 240)
        self.assertEqual(captured['authorization'], 'Bearer test-not-a-real-key')
        self.assertEqual(captured['handlers'][0].proxies, {})
        self.assertTrue(any(type(handler) is NoRedirect for handler in captured['handlers']))
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.test'))

    def test_fixture_response_is_never_real_generation_evidence(self):
        result = inspect_exchange(self.plan(), self.response())
        self.assertEqual(result['status'], 'response_checked_not_migration_pass')
        self.assertEqual(result['actual_model_calls'], 0)
        self.assertEqual(result['candidate']['provenance'], 'offline_transport_test')
        self.assertEqual(result['migration_quality_status'], 'not_run')

    def test_known_usage_survives_invalid_code_truncation_and_model_mismatch(self):
        for change in ('content', 'finish', 'model'):
            value = json.loads(self.response().body)
            if change == 'content': value['choices'][0]['message']['content'] = '```invalid code```'
            if change == 'finish': value['choices'][0]['finish_reason'] = 'length'
            if change == 'model': value['model'] = 'other'
            result = inspect_exchange(self.plan(), Exchange(200, json.dumps(value).encode()))
            self.assertEqual(result['usage']['total_tokens'], 120)
            self.assertIsNone(result['candidate'])
            self.assertTrue(result['diagnostics'])

    def test_http_error_bad_json_oversize_and_missing_usage_remain_review(self):
        for exchange in (Exchange(401, b'{"error":"secret raw text"}'), Exchange(200, b'not json'),
                         Exchange(200, b'x' * (MAX_RESPONSE_BYTES + 1)), self.response(usage=None)):
            result = inspect_exchange(self.plan(), exchange)
            self.assertEqual(result['status'], 'review_required')
            self.assertIsNone(result['candidate'])
            self.assertIsNone(result['usage'])
            self.assertNotIn('secret raw text', str(result))

    def test_usage_types_sums_and_reported_input_bound_are_checked(self):
        for usage in ({'prompt_tokens': True, 'completion_tokens': 20, 'total_tokens': 21},
                      {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 999},
                      {'prompt_tokens': -1, 'completion_tokens': 20, 'total_tokens': 19}):
            self.assertIsNone(inspect_exchange(self.plan(), self.response(usage=usage))['candidate'])
        result = inspect_exchange(self.plan(token_bound=replace(self.plan().bound, count=50)), self.response())
        self.assertIn('qwen_input_token_bound_exceeded', result['diagnostics'])
        self.assertEqual(result['usage']['total_tokens'], 120)

    def test_output_and_total_overrun_keep_usage_but_block_candidate(self):
        for prompt, completion in ((100, 8193), (32700, 100)):
            result = inspect_exchange(self.plan(), self.response(usage={'prompt_tokens': prompt,
                'completion_tokens': completion, 'total_tokens': prompt + completion}))
            self.assertIsNone(result['candidate'])
            self.assertEqual(result['status'], 'review_required')
            self.assertEqual(result['usage']['total_tokens'], prompt + completion)

    def test_reasoning_usage_must_be_absent_or_strict_integer_zero(self):
        for details in ({'reasoning_tokens': True}, {'reasoning_tokens': 1}, {'reasoning_tokens': '0'}, []):
            usage = {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120,
                'completion_tokens_details': details}
            result = inspect_exchange(self.plan(), self.response(usage=usage))
            self.assertIn('qwen_reasoning_usage_unsupported', result['diagnostics'])
            self.assertEqual(result['usage']['total_tokens'], 120)

    def test_tools_reasoning_and_multiple_choices_not_silently_dropped(self):
        for field, value in (('tool_calls', [{}]), ('reasoning_content', 'reasoning'), ('refusal', 'refused')):
            decoded = json.loads(self.response().body)
            decoded['choices'][0]['message'][field] = value
            result = inspect_exchange(self.plan(), Exchange(200, json.dumps(decoded).encode()))
            self.assertIn('qwen_nontext_response_unsupported', result['diagnostics'])
        decoded['choices'] *= 2
        self.assertIsNone(inspect_exchange(self.plan(), Exchange(200, json.dumps(decoded).encode()))['candidate'])

    def test_real_client_cannot_enter_existing_offline_generation_service(self):
        # invoke rejects the type BEFORE reading any DB/attempt or making a call.
        ledger = object.__new__(GenerationService)
        with self.assertRaisesRegex(ValueError, 'generation_offline_client_required'):
            ledger.invoke('a' * 32, QwenHTTPSClient('test-not-a-real-key'))


class ProviderProjectionTests(unittest.TestCase):
    setUp = QwenTransportTests.setUp
    prepare = QwenTransportTests.prepare
    plan = QwenTransportTests.plan
    response = QwenTransportTests.response

    def bundle(self):
        api = load_p1_contracts(fixtures.REPOSITORY).contracts
        plan, key = self.plan(), 'c' * 32
        encode = lambda value: json.dumps(value, allow_nan=False).encode()
        contents = {'request': encode(freeze_provider_contract(api, plan, key)),
            'response': self.response().body, 'candidate': fixtures.CODE.encode()}
        artifacts = {kind: {'path': f'provider-generations/{key}/' + ('candidate.san' if kind == 'candidate' else kind + '.json'),
            'content': content} for kind, content in contents.items()}
        receipt = {'schema_version': 1, 'generation_id': key, 'attempt_id': key + ':generate:1',
            'execution_mode': 'provider_https', 'plan_sha256': plan.fingerprint,
            'file_refs': {kind: {'path': item['path'], 'sha256': sha256(item['content']).hexdigest()}
                for kind, item in artifacts.items()},
            'outcome': inspect_exchange(plan, Exchange(200, contents['response']), provenance='provider_https')}
        artifacts['receipt'] = {'path': f'provider-generations/{key}/receipt.json', 'content': encode(receipt)}
        return api, plan, key, artifacts

    def project(self, bundle, **overrides):
        api, plan, key, artifacts = bundle
        return project_provider_artifact(api, plan, key, **{'artifacts': artifacts,
            'source_bytes': self.source, 'ssm_bytes': self.ssm, **overrides})

    def test_complete_synthetic_bundle_maps_only_generation_revision_not_quality_pass(self):
        bundle = self.bundle()
        result = self.project(bundle)
        wire = result['contract_revision']
        self.assertEqual(wire['origin'], 'generation')
        self.assertIsNone(wire['parent_revision_id'])
        self.assertEqual(wire['artifact']['sha256'], sha256(fixtures.CODE.encode()).hexdigest())
        self.assertEqual(bundle[0].load_contract(wire).to_dict(), wire)
        self.assertEqual(result['usage']['total_tokens'], 120)
        self.assertEqual(result['migration_quality_status'], 'not_run')
        self.assertFalse(result['production_ready'])

    def test_missing_evidence_or_other_path_is_rejected(self):
        for kind in ('request', 'receipt', 'response', 'candidate'):
            bundle = self.bundle()
            del bundle[3][kind]
            with self.subTest(kind=kind), self.assertRaisesRegex(GenerationBoundaryError, 'evidence_missing'):
                self.project(bundle)
        bundle = self.bundle()
        bundle[3]['candidate']['path'] = '../outside.san'
        with self.assertRaisesRegex(GenerationBoundaryError, 'reference_invalid'):
            self.project(bundle)

    def test_exact_source_and_ssm_bytes_required(self):
        for override in ({'source_bytes': self.source + b' '}, {'ssm_bytes': self.ssm + b' '}):
            with self.assertRaisesRegex(GenerationBoundaryError, 'source_evidence_mismatch'):
                self.project(self.bundle(), **override)

    def test_changed_request_snapshot_or_plan_is_not_backfilled(self):
        for field, value in (('generation_id', 'd' * 32), ('plan_sha256', '0' * 64)):
            bundle = self.bundle()
            snapshot = json.loads(bundle[3]['request']['content'])
            snapshot[field] = value
            bundle[3]['request']['content'] = json.dumps(snapshot).encode()
            with self.assertRaisesRegex(GenerationBoundaryError, 'snapshot_mismatch'):
                self.project(bundle)

    def test_offline_receipt_cannot_be_promoted_by_changing_only_execution_mode(self):
        bundle = self.bundle()
        receipt = json.loads(bundle[3]['receipt']['content'])
        receipt['outcome'] = inspect_exchange(bundle[1], self.response())
        bundle[3]['receipt']['content'] = json.dumps(receipt).encode()
        with self.assertRaisesRegex(GenerationBoundaryError, 'response_not_accepted'):
            self.project(bundle)

    def test_receipt_references_and_candidate_bytes_must_match(self):
        bundle = self.bundle()
        bundle[3]['candidate']['content'] += b' '
        with self.assertRaisesRegex(GenerationBoundaryError, 'receipt_reference_mismatch'):
            self.project(bundle)
        receipt = json.loads(bundle[3]['receipt']['content'])
        receipt['file_refs']['candidate']['sha256'] = sha256(bundle[3]['candidate']['content']).hexdigest()
        bundle[3]['receipt']['content'] = json.dumps(receipt).encode()
        with self.assertRaisesRegex(GenerationBoundaryError, 'candidate_mismatch'):
            self.project(bundle)

    def test_unknown_usage_or_truncated_response_has_no_contract_revision(self):
        for fault in ('usage', 'finish'):
            bundle = self.bundle()
            raw = json.loads(bundle[3]['response']['content'])
            if fault == 'usage': raw.pop('usage')
            else: raw['choices'][0]['finish_reason'] = 'length'
            bundle[3]['response']['content'] = json.dumps(raw).encode()
            receipt = json.loads(bundle[3]['receipt']['content'])
            receipt['file_refs']['response']['sha256'] = sha256(bundle[3]['response']['content']).hexdigest()
            receipt['outcome'] = inspect_exchange(bundle[1], Exchange(200, bundle[3]['response']['content']), provenance='provider_https')
            bundle[3]['receipt']['content'] = json.dumps(receipt).encode()
            with self.assertRaisesRegex(GenerationBoundaryError, 'response_not_accepted'):
                self.project(bundle)

    def test_strict_receipt_identity_and_boolean_schema_are_rejected(self):
        for changes in ({'generation_id': 'd' * 32}, {'attempt_id': 'other'}, {'schema_version': True},
                        {'execution_mode': 'offline_transport_test'}, {'plan_sha256': '0' * 64}):
            bundle = self.bundle()
            receipt = json.loads(bundle[3]['receipt']['content'])
            receipt.update(changes)
            bundle[3]['receipt']['content'] = json.dumps(receipt).encode()
            with self.assertRaisesRegex(GenerationBoundaryError, 'receipt_mismatch'):
                self.project(bundle)
