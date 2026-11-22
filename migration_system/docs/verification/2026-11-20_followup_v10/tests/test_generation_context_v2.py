"""Lossless generation formatting and output-ceiling regressions, no network."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import MagicMock, patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from card_migration_system.adapters.model import ModelExchange, QwenModel, inspect_response
from card_migration_system.config import load_settings
from card_migration_system.prompts.generation import (PromptBindingError, build_generation_messages,
                                                    compact_generation_context)
from card_migration_system.prompts.migration import generation_messages
from card_migration_system.reporting.identity import digest
from card_migration_system.runtime import profile


class GenerationContextTests(unittest.TestCase):
    def setUp(self):
        self.ssm = {'schema_version': '3.0', 'metadata': {'component_name': 'DifferentName'},
                    'script': {'methods': {'update': {'body': 'this[key] = value;\n  keep spaces;'}}},
                    'template': {'text': '中文  文本\n --- SSM ---\n'},
                    'style_model': {'css': 'pre::after { content: "a  b"; }'},
                    'defaults': [None, False, 0, '', [], {}, '😀', -0.0]}

    def test_exact_roundtrip_preserves_every_value_and_rule(self):
        messages, _ = build_generation_messages(PROJECT / 'engine', self.ssm)
        before = deepcopy(messages)
        result, audit = compact_generation_context(messages, self.ssm)
        prefix, body = result[-1]['content'].rsplit('--- SSM ---\n', 1)
        old_prefix, _ = before[-1]['content'].rsplit('--- SSM ---\n', 1)
        self.assertEqual(prefix, old_prefix)
        self.assertEqual(json.loads(body), self.ssm)
        self.assertEqual(digest(json.loads(body)), audit['ssm_sha256'])
        self.assertEqual(result[0], before[0])
        self.assertEqual(messages, before)
        self.assertLess(audit['after_chars'], audit['before_chars'])
        self.assertIn('this[key] = value;\\n  keep spaces;', body)
        self.assertIn('a  b', body)

    def test_boundary_mismatch_is_not_guessed_or_silently_truncated(self):
        messages, _ = build_generation_messages(PROJECT / 'engine', self.ssm)
        for bad in ([], [{'role': 'assistant', 'content': messages[-1]['content']}],
                    [{'role': 'user', 'content': messages[-1]['content'] + '\nextra'}]):
            with self.assertRaisesRegex(PromptBindingError, 'boundary_mismatch'):
                compact_generation_context(bad, self.ssm)
        with self.assertRaises(ValueError):
            compact_generation_context(messages, {'not_json': float('nan')})

    def test_production_builder_records_policy_and_keeps_few_shot_exact(self):
        example = {'id': 'ex', 'group': 'train', 'source_sha256': 'a' * 64,
                   'ssm_sha256': 'b' * 64, 'san_sha256': 'c' * 64, 'ssm': {'data': '  '}, 'san': 'example'}
        messages, audit = generation_messages(SimpleNamespace(repository_root=PROJECT / 'engine'),
                                             self.ssm, [example])
        self.assertEqual(messages[1:3], [{'role': 'user', 'content': json.dumps(example['ssm'], ensure_ascii=False)},
                                        {'role': 'assistant', 'content': 'example'}])
        self.assertEqual(audit['generation_context']['policy'], 'generation-lossless-json-v2')
        self.assertTrue(audit['generation_context']['all_ssm_values_preserved'])
        direct, audit = generation_messages(None, self.ssm, [], strategy='direct', source='a  b\n')
        self.assertEqual(direct[-1]['content'], 'a  b\n')
        self.assertEqual(audit['generation_context']['policy'], 'direct_source_unchanged')

    def test_larger_ceiling_still_rejects_truncated_model_output(self):
        body = {'model': 'qwen-plus', 'choices': [{'finish_reason': 'length',
                'message': {'role': 'assistant', 'content': '<template></template><script></script><style>'}}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 32768, 'total_tokens': 32868}}
        result = inspect_response(ModelExchange(200, json.dumps(body).encode()), 'qwen-plus')
        self.assertEqual(result['error'], 'model_output_incomplete')
        self.assertFalse(result['valid'])
        self.assertEqual(result['usage']['completion_tokens'], 32768)

    def test_wire_request_uses_v2_ceiling_without_enabling_thinking_or_retries(self):
        conf = profile(load_settings())
        self.assertEqual(conf['model']['max_output_tokens'], 32768)
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value = SimpleNamespace(status=200, read=lambda _: b'{}')
        with patch.dict('os.environ', {conf['model']['api_key_env']: 'offline-placeholder'}), \
             patch('card_migration_system.adapters.model.request.build_opener', return_value=opener):
            QwenModel(conf).exchange([{'role': 'user', 'content': 'offline'}])
        opener.open.assert_called_once()
        payload = json.loads(opener.open.call_args.args[0].data)
        self.assertEqual(payload['max_tokens'], 32768)
        self.assertFalse(payload['enable_thinking'])
        self.assertFalse(payload['stream'])
        self.assertEqual(conf['model']['usage_stop_tokens'], 131072)
        self.assertEqual(conf['model']['max_calls'], 4)


if __name__ == '__main__':
    unittest.main()
