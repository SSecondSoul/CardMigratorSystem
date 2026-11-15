"""Freeze/launch boundaries: one sample, fresh output paths, no implicit model run."""

import json
import copy
import subprocess
import unittest
from unittest.mock import patch

from migration_pipeline.run_formal_30_v4_semantic_closure_v5 import (
    BATCH_ID, CONFIG, PROTOCOL, EXPECTED_ENV, batch_command, main,
)
from migration_pipeline.run_batch_pipeline import validate_batch_config
from migration_pipeline.prepare_formal_30_v4_semantic_closure_v5 import OUTPUT, validate_offline


class MethodInterfaceProtocolLaunchTests(unittest.TestCase):
    def offline(self):
        return json.loads((OUTPUT / 'replay.json').read_text(encoding='utf-8'))

    def test_prior_offline_proof_covers_startup_api_and_no_new_trigger(self):
        validate_offline(self.offline())

    def test_offline_proof_refuses_new_permission_trigger(self):
        evidence = self.offline()
        evidence['cases'][1]['method_contract']['target_references']['count'] = 1
        with self.assertRaisesRegex(RuntimeError, 'no-new-trigger'):
            validate_offline(evidence)

    def test_offline_proof_refuses_missing_interface_and_duplicate_startup(self):
        for path, key, value in (
            ('method_contract', 'status', 'missing'),
            ('startup_contract', 'inited_direct_calls', 1),
        ):
            with self.subTest(contract=path):
                evidence = copy.deepcopy(self.offline())
                evidence['cases'][2][path][key] = value
                with self.assertRaisesRegex(RuntimeError, 'closure'):
                    validate_offline(evidence)

    def test_offline_proof_cannot_be_relabelled_as_model_or_browser_success(self):
        for key, value in (('model_requests', 1), ('browser_permission_request_performed', True),
                           ('browser_interaction_test_performed', True), ('original_summary_modified', True)):
            with self.subTest(field=key):
                evidence = self.offline()
                evidence[key] = value
                with self.assertRaisesRegex(RuntimeError, 'boundary'):
                    validate_offline(evidence)

    def test_config_excludes_task_manager_and_preserves_three_call_budget(self):
        config = json.loads(CONFIG.read_text(encoding='utf-8'))
        validate_batch_config(config)
        self.assertEqual(config['batch_id'], BATCH_ID)
        self.assertEqual(config['prior_result_snapshot'], 'formal_30_v4_semantic_closure_v4_results_20261103_204227')
        self.assertEqual(config['classification'], 'startup_method_interface_closure_single_sample_development_regression')
        self.assertEqual(config['required_launch_environment'], EXPECTED_ENV)
        self.assertEqual([s['id'] for s in config['samples']], ['MonitoringDashboard'])
        self.assertEqual(config['expected_counts'], {'simple': 0, 'medium': 0, 'complex': 1})
        self.assertEqual(config['max_repair_rounds'], 3)
        self.assertEqual(config['repair_policy'], 'bounded_prepass_v1')
        self.assertEqual(config['semantic_rule_set'], 'residual_v2')
        self.assertFalse(config['independent_holdout'])
        self.assertEqual(config['generation_input_policy'], 'fresh_from_vue_not_prior_san')

    def test_command_uses_separate_default_checkpoint_without_force_or_selected_old_output(self):
        command = batch_command()
        self.assertIn(CONFIG.relative_to(CONFIG.parents[2]).as_posix(), command)
        self.assertIn('--include-state', command)
        for arg in ('--force', '--sample-id', '--output-dir', '--report-dir', '--summary-file'):
            self.assertNotIn(arg, command)
        self.assertEqual(batch_command(dry_run=True), command + ['--dry-run'])

    @patch('migration_pipeline.run_formal_30_v4_semantic_closure_v5.subprocess.run')
    def test_dry_run_only_dispatches_dry_batch_without_server_or_model(self, run):
        run.return_value = subprocess.CompletedProcess([], 0)
        self.assertEqual(main(['--dry-run']), 0)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0], batch_command(dry_run=True))

    @patch('migration_pipeline.run_formal_30_v4_semantic_closure_v5.subprocess.run')
    def test_execute_verifies_live_before_batch_and_overrides_child_timeouts(self, run):
        run.return_value = subprocess.CompletedProcess([], 0)
        self.assertEqual(main(['--execute']), 0)
        self.assertEqual(run.call_count, 2)
        first, second = run.call_args_list
        self.assertEqual(first.args[0][1:], [str(PROTOCOL / 'verify_protocol.py'), '--live'])
        self.assertTrue(first.kwargs['check'])
        self.assertEqual(second.args[0], batch_command())
        self.assertEqual(second.kwargs['env']['LLM_TIMEOUT'], '600')
        self.assertEqual(second.kwargs['env']['MIGRATION_REPAIR_TIMEOUT'], '660')
        for name, value in EXPECTED_ENV.items():
            self.assertEqual(second.kwargs['env'][name], value)

    @patch('migration_pipeline.run_formal_30_v4_semantic_closure_v5.subprocess.run',
           side_effect=subprocess.CalledProcessError(1, ['verification']))
    def test_failed_verification_never_starts_model_or_server(self, run):
        with self.assertRaises(subprocess.CalledProcessError):
            main(['--execute'])
        self.assertEqual(run.call_count, 1)

    @patch.dict('os.environ', {'LLM_API_KEY': ''})
    @patch('migration_pipeline.run_formal_30_v4_semantic_closure_v5.subprocess.run')
    def test_missing_key_never_starts_server(self, run):
        run.return_value = subprocess.CompletedProcess([], 0)
        with self.assertRaises(SystemExit):
            main(['--server'])
        self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
