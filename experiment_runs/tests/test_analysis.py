import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'analyze_coverage.py'
spec = importlib.util.spec_from_file_location('coverage_analysis', SCRIPT)
analysis = importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def sample():
    return {'id': 'same', 'component_name': 'SameCard', 'complexity': 'simple',
            'vue_sha256': 'a' * 64, 'slug': '001_same'}


def report():
    return {'migration_id': 'b' * 32, 'status': 'blocked', 'stop_reason': 'style_capacity_exceeded',
            'model_calls_started': 0, 'unknown_calls': 0,
            'usage': {'complete': True, 'known_total_tokens': 0},
            'assessment': {'passed': False, 'revision_sha256': 'old',
                           'diagnostics': [{'code': 'target_sfc_syntax_error'}]},
            'state': {'round': 2, 'decisions': []}}


class AnalysisTests(unittest.TestCase):
    def test_dom_triage_does_not_turn_attribute_differences_into_passes(self):
        self.assertIn('尚未获准忽略', analysis.dom_kind({'expected': 'input|value=1', 'actual': 'input|'}))
        self.assertEqual(analysis.dom_kind({'expected': '#text:1', 'actual': None}), '节点或文本缺失新增')
        self.assertEqual(analysis.dom_kind({'expected': '#text:1', 'actual': '#text:2'}), '文本内容变化')
        self.assertEqual(analysis.dom_kind({'expected': 'div|', 'actual': 'span|'}), '元素标签变化')

    def test_runtime_differences_prevent_single_v2_version_claim(self):
        first = {key: {} for key in ('binding', 'runtime_profile', 'strategy', 'max_repair_rounds', 'props', 'actions', 'thresholds')}
        second = json.loads(json.dumps(first))
        self.assertTrue(analysis.same_v2_protocol(first, second))
        second['runtime_profile'] = {'model': {'max_output_tokens': 8192}}
        self.assertFalse(analysis.same_v2_protocol(first, second))

    def test_latest_unevaluated_candidate_does_not_overwrite_old_assessment(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            put(folder / 'evaluations/0.json', report()['assessment'])
            put(folder / 'revisions/0.json', {'number': 0, 'parent': None, 'origin': 'generation', 'file': {'sha256': 'old'}})
            put(folder / 'revisions/2.json', {'number': 2, 'parent': 'old', 'origin': 'model_repair', 'file': {'sha256': 'new'}})
            row = analysis.analyze_record('batch', sample(), report(), folder)
            self.assertFalse(row['latest_revision_evaluated'])
            self.assertEqual(row['assessment_revision_sha256'], 'old')
            self.assertEqual(row['latest_revision_sha256'], 'new')
            self.assertEqual(row['stop_reason'], 'style_capacity_exceeded')

    def test_noop_detection_uses_code_hash_not_changed_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            put(folder / 'revisions/1.json', {'number': 1, 'parent': 'same', 'origin': 'model_repair', 'file': {'sha256': 'same'}})
            row = analysis.analyze_record('batch', sample(), report(), folder)
            self.assertEqual(row['no_op_candidates'], [{'number': 1, 'origin': 'model_repair'}])

    def test_repeated_component_keeps_both_runs_and_has_no_mixed_pass_rate(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            first = analysis.analyze_record(analysis.BATCHES[0], sample(), report(), folder)
            second_report = report();second_report['status'] = 'finished';second_report['assessment']['passed'] = True
            second = analysis.analyze_record(analysis.BATCHES[1], sample(), second_report, folder)
            details = {first['run_key']: {'report': report()}, second['run_key']: {'report': second_report}}
            protocol = {key: {} for key in ('binding', 'runtime_profile', 'strategy', 'max_repair_rounds', 'props', 'actions', 'thresholds')}
            result = analysis.aggregate([first, second], details, [], {key: protocol for key in analysis.BATCHES})
            summary, components = result[:2]
            self.assertEqual(summary['unique_components'], 1)
            self.assertEqual(summary['terminal_run_records'], 2)
            self.assertIsNone(summary['combined_70_pass_rate'])
            self.assertEqual(len(components['same']), 2)
            self.assertFalse(components['same'][0]['passed'])
            self.assertTrue(components['same'][1]['passed'])

    def test_missing_receipt_is_not_zero_usage(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = report();value['model_calls_started'] = 1
            with self.assertRaisesRegex(ValueError, 'call_receipts_not_complete'):
                analysis.analyze_record('batch', sample(), value, Path(temporary))

    def test_declared_unknown_receipt_remains_incomplete(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = report();value['model_calls_started'] = value['unknown_calls'] = 1
            value['usage']['complete'] = False
            row = analysis.analyze_record('batch', sample(), value, Path(temporary))
            self.assertEqual(row['missing_receipts_unknown_outcome'], 1)
            self.assertFalse(row['usage_complete'])
            value['usage']['complete'] = True
            with self.assertRaisesRegex(ValueError, 'unknown_call_cannot'):
                analysis.analyze_record('batch', sample(), value, Path(temporary))

    def test_output_is_immutable_and_evidence_paths_cannot_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary);path = folder / 'report.json'
            analysis.write_once(path, {'actual': 1});analysis.write_once(path, {'actual': 1})
            with self.assertRaisesRegex(ValueError, 'create_new_analysis_version'):
                analysis.write_once(path, {'actual': 2})
            with self.assertRaisesRegex(ValueError, 'escapes_root'):
                analysis.inside(folder / '../outside', folder)


if __name__ == '__main__':
    unittest.main()
