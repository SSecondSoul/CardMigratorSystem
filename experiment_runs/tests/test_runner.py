import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'run_experiment.py'
spec = importlib.util.spec_from_file_location('experiment_runner', SCRIPT)
runner = importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def test_snapshot_write_refuses_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'file.json'
            runner.write_once(path, b'first');runner.write_once(path, b'first')
            with self.assertRaisesRegex(ValueError, 'immutable_file_differs'):
                runner.write_once(path, b'changed')
            self.assertEqual(path.read_bytes(), b'first')

    def test_summary_keeps_pending_and_overlapping_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            samples = [{'id': key, 'slug': key, 'component_name': key, 'complexity': complexity}
                       for key, complexity in [('a', 'simple'), ('b', 'medium'), ('c', 'complex')]]
            (folder / 'samples.json').write_bytes(runner.encode(samples))
            (folder / 'checkpoint.json').write_bytes(runner.encode({'status': 'running', 'jobs': {}, 'results': {
                'a': {'status': 'finished', 'passed': True, 'error_codes': [], 'model_calls': 1, 'total_tokens': 10},
                'b': {'status': 'failed', 'passed': False, 'stop_reason': 'repair_budget_exhausted',
                      'error_codes': ['template_structure_mismatch', 'missing_prop_defaults'], 'model_calls': 2, 'total_tokens': 20}}}))
            result = runner.summary(folder)
            self.assertEqual((result['configured'], result['completed'], result['passed'], result['pending']), (3, 2, 1, 1))
            self.assertEqual(result['pass_rate_all_configured'], 1 / 3)
            self.assertEqual(result['known_total_tokens'], 30)
            groups = json.loads((folder / 'failure_groups.json').read_text(encoding='utf-8'))
            self.assertEqual(len(groups), 2)
            self.assertTrue(all(g['samples'][0]['sample_id'] == 'b' for g in groups))

    def test_dataset_selection_validates_only_experiment_inputs(self):
        samples = runner.load_samples(runner.ROOT / 'experiment_dataset')
        self.assertEqual(len(samples), 70)
        self.assertTrue(all(s['subset'] == 'experiment' for s in samples))

    def test_focused_probe_is_explicit_and_keeps_dataset_order(self):
        samples = runner.load_samples(runner.ROOT / 'experiment_dataset')
        selected = runner.select_samples(samples, ['TaskManager', 'MonitoringDashboard'])
        self.assertEqual([s['id'] for s in selected], ['MonitoringDashboard', 'TaskManager'])
        self.assertEqual(len(runner.select_samples(samples)), 70)
        for wanted in ([], ['TaskManager', 'TaskManager'], ['validation_only'], ['../TaskManager']):
            with self.assertRaises(ValueError):
                runner.select_samples(samples, wanted)

    def test_batch_path_and_export_path_cannot_escape(self):
        with self.assertRaises(ValueError):runner.batch_dir('../outside')
        with self.assertRaises(ValueError):runner.inside(runner.ROOT / 'other', runner.RUNS)

    def test_rendered_dom_differences_are_not_compile_failures(self):
        for code in ('rendered_dom_mismatch', 'rendered_control_state_mismatch'):
            self.assertEqual(runner.category(code), '结构或控件状态')
        for code in ('san_render_failed', 'target_browser_error', 'invalid_san_template_syntax'):
            self.assertEqual(runner.category(code), '语法或编译运行')
        self.assertEqual(runner.category('hidden_template_reactive_dependency'), '静态语义或响应式')


if __name__ == '__main__':unittest.main()
