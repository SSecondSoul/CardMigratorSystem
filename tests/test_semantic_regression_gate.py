"""Semantic recurrence must not hide behind fewer total diagnostics."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.replay_formal_30_v4_repair_scheduling import ReplayGenerate, ReplayCandidate
from migration_pipeline.stages.generate import GenerateStageInput
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.validate import ValidateStage
from migration_pipeline.stages.visual_eval import VisualEvalStage


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/experiments/snapshots/formal_30_v4_semantic_closure_v1_results_20261103_145253'


def issue(code, message='finding', location='template/script'):
    return {'code': code, 'message': message, 'location': location}


def state(errors):
    return {'generated_code': '<template><div></div></template><script></script>',
            'validation_errors': errors, 'visual_eval_passed': True, 'ssm': {}}


class SemanticRegressionGateTests(unittest.TestCase):
    def test_reintroduced_hidden_dependency_is_rejected_even_with_fewer_total_errors(self):
        before = state([issue('missing_data_types'), issue('other'), issue('other2')])
        after = state([issue('missing_data_types'), issue('hidden_template_reactive_dependency')])
        gate = candidate_gate(before, after)
        self.assertTrue(gate['should_stop'])
        self.assertEqual(gate['decision'], 'reject')
        self.assertEqual([i['code'] for i in gate['introduced_semantic_findings']], ['hidden_template_reactive_dependency'])

    def test_unchanged_or_removed_findings_are_not_rejected(self):
        errors = [issue('hidden_template_reactive_dependency'), issue('missing_data_types')]
        self.assertFalse(candidate_gate(state(errors), state(errors))['should_stop'])
        self.assertFalse(candidate_gate(state(errors), state(errors[:1]))['should_stop'])

    def test_different_finding_of_same_family_cannot_replace_old_one_silently(self):
        before = state([issue('hidden_template_reactive_dependency', 'methodA hides tasks')])
        after = state([issue('hidden_template_reactive_dependency', 'methodB hides selected')])
        self.assertTrue(candidate_gate(before, after)['should_stop'])

    def test_new_computed_lifecycle_and_datatypes_findings_are_rejected(self):
        for code in ('invalid_san_computed_instance_method_call', 'lifecycle_behavior_not_landed',
                     'missing_data_types', 'missing_prop_defaults'):
            with self.subTest(code=code):
                self.assertTrue(candidate_gate(state([]), state([issue(code)]))['should_stop'])

    def test_unknown_family_does_not_get_an_unreviewed_gate(self):
        self.assertFalse(candidate_gate(state([]), state([issue('future_diagnostic')]))['should_stop'])

    def test_frozen_second_to_third_round_is_now_rejected(self):
        report = json.loads((SOURCE / 'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))
        source_state = report['state']
        before, after = source_state['repair_history'][1:3]
        vue = SOURCE / 'protocol/frozen/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue'
        def item(entry):
            return {**state(entry['validate_result']['validation_errors']), 'ssm': source_state['ssm'],
                    'generated_code': entry['repair_result']['repaired_code'], 'vue_file_path': str(vue)}
        gate = candidate_gate(item(before), item(after))
        self.assertTrue(gate['should_stop'])
        self.assertEqual([i['code'] for i in gate['introduced_semantic_findings']], ['hidden_template_reactive_dependency'])

    def test_actual_frozen_loop_stops_before_the_now_unproven_parent_scope(self):
        source_state = json.loads((SOURCE / 'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']
        before, after = [h['repair_result']['repaired_code'] for h in source_state['repair_history'][1:3]]
        vue = SOURCE / 'protocol/frozen/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue'
        with tempfile.TemporaryDirectory() as directory:
            generate = ReplayGenerate(source_state, before, Path(directory) / 'before.san')
            repair = ReplayCandidate(after, Path(directory) / 'rejected.san')
            orchestrator = MigrationPipelineOrchestrator(generate, ValidateStage(), VisualEvalStage(), repair)
            with patch.object(RepairStage, '_deterministic_repair_plan', side_effect=lambda code, *_: (code, [])):
                result = orchestrator.run_generate_validate_visual_eval_and_repair_loop(
                    GenerateStageInput(vue_file_path=str(vue), metadata={'repair_policy': 'bounded_prepass_v1'}),
                    max_repair_rounds=3).state
            self.assertFalse(result['final_passed'])
            self.assertFalse(result['retained_previous_candidate'])
            self.assertEqual(result['final_code'], before)
            self.assertEqual(Path(result['final_file_path']).read_text(encoding='utf-8'), before)
            self.assertFalse((Path(directory)/'rejected.san').exists())
            self.assertEqual(result['llm_repair_calls'],0)
            self.assertEqual(result['stop_reason'],'source_parent_watch_scope_requires_review')

    def test_actual_loop_restores_previous_failed_candidate_and_keeps_rejected_evidence(self):
        # Keep the original acceptance/rollback contract exercised with actual
        # validators, independently of the earlier TaskManager review boundary.
        before="""<template><div>{{title}}</div></template><script>
const san=require('san');const DataTypes=san.DataTypes;
module.exports=san.defineComponent({initData(){return {title:'title'};},
getTitle(){return this.data.get('title');}});</script><style></style>"""
        after=before.replace('{{title}}','{{getTitle()}}')
        with tempfile.TemporaryDirectory() as directory:
            vue=Path(directory)/'source.vue'
            vue.write_text("<template><div>{{title}}</div></template><script>module.exports={data(){return {title:'title'};}};</script><style></style>",encoding='utf-8')
            generate=ReplayGenerate({'source_file':str(vue),'ssm':{}},before,Path(directory)/'before.san')
            repair=ReplayCandidate(after,Path(directory)/'rejected.san')
            with patch.object(RepairStage,'_deterministic_repair_plan',side_effect=lambda code,*_: (code,[])):
                result=MigrationPipelineOrchestrator(generate,ValidateStage(),VisualEvalStage(),repair).run_generate_validate_visual_eval_and_repair_loop(
                    GenerateStageInput(vue_file_path=str(vue),metadata={'repair_policy':'bounded_prepass_v1'}),max_repair_rounds=3).state
            self.assertFalse(result['final_passed'])
            self.assertTrue(result['retained_previous_candidate'])
            self.assertEqual(result['final_code'],before)
            self.assertEqual(Path(result['final_file_path']).read_text(encoding='utf-8'),before)
            self.assertEqual(Path(result['rejected_candidate_file']).read_text(encoding='utf-8'), after)
            self.assertEqual(result['stop_reason'], 'repair_candidate_regression_rolled_back')
            self.assertTrue(result['repair_history'][-1]['repair_regression_rejected'])


if __name__ == '__main__':
    unittest.main()
