"""Full-30 launch boundaries: original strata, fresh inputs and no implicit paid run."""

import json
from collections import Counter
import subprocess
import unittest
from unittest.mock import patch

from migration_pipeline.run_formal_30_v4_full_regression_v2 import (
    BATCH_ID, CONFIG, PROTOCOL, EXPECTED_ENV, batch_command, main,
)
from migration_pipeline.run_batch_pipeline import validate_batch_config
from migration_pipeline.prepare_formal_30_v4_full_regression_v2 import validate_config


class FullRegressionV2ProtocolLaunchTests(unittest.TestCase):
    def config(self):
        return json.loads(CONFIG.read_text(encoding='utf-8'))

    def test_config_runs_all_original_30_including_both_manually_accepted_components(self):
        config = self.config()
        validate_config(config)
        self.assertEqual(len(config['samples']), 30)
        self.assertEqual(Counter(s['complexity'] for s in config['samples']), Counter(simple=10, medium=10, complex=10))
        ids = [s['id'] for s in config['samples']]
        self.assertIn('TaskManager', ids)
        self.assertIn('MonitoringDashboard', ids)
        self.assertEqual(config['max_repair_rounds'], 3)
        self.assertEqual(config['generation_input_policy'], 'fresh_from_vue_not_prior_san')

    def test_reordering_or_excluding_original_samples_is_rejected(self):
        config = self.config()
        config['samples'][0], config['samples'][1] = config['samples'][1], config['samples'][0]
        with self.assertRaises(RuntimeError):
            validate_config(config)
        config = self.config()
        config['samples'].pop()
        with self.assertRaises((RuntimeError, ValueError)):
            validate_config(config)

    def test_budget_or_runtime_environment_changes_are_rejected(self):
        for key, value in (('max_repair_rounds', 6), ('repair_policy', 'legacy'),
                           ('max_normalization_steps_per_llm_call', 10)):
            config = self.config()
            config[key] = value
            with self.assertRaises((RuntimeError, ValueError)):
                validate_config(config)
        config = self.config()
        config['required_launch_environment']['LLM_TIMEOUT'] = '240'
        with self.assertRaises(RuntimeError):
            validate_config(config)

    def test_prior_manual_acceptance_cannot_be_used_as_inherited_input_or_holdout_claim(self):
        for key, value in (('generation_input_policy', 'reuse_prior_san'),
                           ('accepted_candidate_policy', 'skip_accepted_samples'),
                           ('independent_holdout', True),
                           ('source_split_name_is_historical_not_holdout_claim', False)):
            config = self.config()
            config[key] = value
            with self.assertRaises(RuntimeError):
                validate_config(config)

    def test_historical_baseline_metadata_cannot_be_changed(self):
        config = self.config()
        config['baseline_summary_sha256'] = '0' * 64
        with self.assertRaises(RuntimeError):
            validate_config(config)

    def test_command_uses_separate_default_checkpoint_without_force_or_selected_old_output(self):
        command = batch_command()
        self.assertIn(CONFIG.relative_to(CONFIG.parents[2]).as_posix(), command)
        self.assertIn('--include-state', command)
        for arg in ('--force', '--sample-id', '--output-dir', '--report-dir', '--summary-file'):
            self.assertNotIn(arg, command)
        self.assertEqual(batch_command(dry_run=True), command + ['--dry-run'])

    @patch('migration_pipeline.run_formal_30_v4_full_regression_v2.subprocess.run')
    def test_dry_run_only_dispatches_dry_batch_without_server_or_model(self, run):
        run.return_value = subprocess.CompletedProcess([], 0)
        self.assertEqual(main(['--dry-run']), 0)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0], batch_command(dry_run=True))

    @patch('migration_pipeline.run_formal_30_v4_full_regression_v2.subprocess.run')
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

    @patch('migration_pipeline.run_formal_30_v4_full_regression_v2.subprocess.run',
           side_effect=subprocess.CalledProcessError(1, ['verification']))
    def test_failed_verification_never_starts_model_or_server(self, run):
        with self.assertRaises(subprocess.CalledProcessError):
            main(['--execute'])
        self.assertEqual(run.call_count, 1)

    @patch.dict('os.environ', {'LLM_API_KEY': ''})
    @patch('migration_pipeline.run_formal_30_v4_full_regression_v2.subprocess.run')
    def test_missing_key_never_starts_server(self, run):
        run.return_value = subprocess.CompletedProcess([], 0)
        with self.assertRaises(SystemExit):
            main(['--server'])
        self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
