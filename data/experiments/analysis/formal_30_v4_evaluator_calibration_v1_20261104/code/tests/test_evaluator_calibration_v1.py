"""Field identities, bounded cloned-record proof, and persistence review boundary."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput, ValidationIssue
from migration_pipeline.utils.detached_record_semantics import proven_record_copies
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt

ROOT = Path(__file__).resolve().parents[1]
BODY = "const rows=this.data.get('records').map(row=>({...row})); rows[0].amount=Math.max(0,rows[0].amount+1); this.data.set('records',rows);"


def mutation_issues(body, signature='update()', prefix=''):
    script = prefix + 'const c={' + signature + '{' + body + '}};'
    issues, checks = [], []
    ValidateStage()._validate_nested_state_mutations(script, issues, checks)
    return [i.to_dict() for i in issues]


def defaults(names, message='grouped message'):
    return {'code': 'missing_prop_defaults', 'location': 'script', 'message': message,
            'details': {'contract': 'prop_defaults_v1', 'affected_fields': names}}


def gate_state(errors):
    return {'generated_code': '<template><div></div></template><script></script>',
            'validation_errors': errors, 'visual_eval_passed': True, 'ssm': {}}


def watcher_fixture():
    vue = """<template><div></div></template><script>export default {data(){return {settings:{enabled:false}};},
watch:{settings:{handler(value){if(value.enabled){this.start();}
localStorage.setItem('prefs',JSON.stringify(value));},deep:true}},methods:{start(){}}}</script>"""
    san = """<script>const san=require('san');module.exports=san.defineComponent({
initData(){return {settings:{enabled:false}};},start(){},inited(){
this.watch('settings',next=>{if(next.enabled){this.start();} WRITE });}});</script>"""
    return vue, san


class EvaluatorCalibrationV1Tests(unittest.TestCase):
    def test_validator_emits_structured_fields_without_changing_other_issue_shapes(self):
        issues = []
        ssm = {'script': {'options': {'props': [{'name': n, 'default': '[]'} for n in ('title', 'rows')]}}}
        ValidateStage()._validate_prop_defaults_landing('initData(){return {title:1};}', ssm, issues, [])
        self.assertEqual(issues[0].to_dict()['details'], {'contract': 'prop_defaults_v1', 'affected_fields': ['rows']})
        self.assertNotIn('details', ValidationIssue('x', 'y').to_dict())

    def test_shrinking_group_is_progress_not_pass_or_regression(self):
        before = gate_state([defaults(['title', 'rows'], 'old')])
        after = gate_state([defaults(['rows'], 'different localized message')])
        self.assertFalse(candidate_gate(before, after)['should_stop'])
        self.assertTrue(after['validation_errors'])

    def test_new_field_same_count_or_fewer_total_errors_still_rejects(self):
        for names in (['new'], ['rows', 'new']):
            gate = candidate_gate(gate_state([defaults(['title', 'rows'])]), gate_state([defaults(names)]))
            self.assertTrue(gate['should_stop'])
            self.assertIn('prop.default:new', [i['message'] for i in gate['introduced_semantic_findings']])

    def test_legacy_malformed_or_changed_scope_is_not_waived(self):
        original = defaults(['title', 'rows'], 'old')
        cases = [dict(defaults(['rows']), details=None), dict(defaults(['rows']), details='bad'),
                 dict(defaults(['rows']), details={'contract': 'unknown', 'affected_fields': ['rows']}),
                 dict(defaults(['rows']), location='script.child')]
        for issue in cases:
            with self.subTest(issue=issue):
                self.assertTrue(candidate_gate(gate_state([original]), gate_state([issue]))['should_stop'])

    def test_record_clone_scalar_writes_then_commit_are_not_nested_state_mutations(self):
        self.assertEqual(mutation_issues(BODY), [])
        self.assertEqual(mutation_issues(BODY.replace('rows', 'items').replace('amount', 'count')), [])

    def test_identity_map_and_shallow_array_copies_do_not_detach_records(self):
        for init in ("this.data.get('records').map(row=>row)", "this.data.get('records').slice()",
                     "[...this.data.get('records')]", "this.data.get('records').filter(row=>true)"):
            body = BODY.replace("this.data.get('records').map(row=>({...row}))", init)
            # Direct this.data.get prefix cases must be reported. The spread
            # form is checked at the proof boundary (existing regex has no alias).
            script = 'const c={update(){' + body + '}};'
            self.assertFalse(proven_record_copies(body, script))
            if not init.startswith('['):
                self.assertIn('nested_state_mutation', [i['code'] for i in mutation_issues(body)])

    def test_deeper_writes_escape_reassignment_shadowing_and_unknown_calls_stay_errors(self):
        for body in (BODY.replace('rows[0].amount=', 'rows[0].nested.amount='),
                     BODY.replace('rows[0].amount=', 'publish(rows);rows[0].amount='),
                     BODY.replace('const rows=', 'let rows=').replace('rows[0].amount=', 'rows=[];rows[0].amount='),
                     BODY.replace('rows[0].amount=', '{let rows=this.data.get("other");rows[0].amount=2;}rows[0].amount='),
                     BODY.replace('Math.max(0,rows[0].amount+1)', 'unknown(rows[0].amount)'),
                     BODY.replace('rows[0].amount=', 'setTimeout(()=>rows[0].amount=3);rows[0].amount=')):
            with self.subTest(body=body):
                self.assertIn('nested_state_mutation', [i['code'] for i in mutation_issues(body)])

    def test_missing_early_conditional_or_wrong_field_commit_is_not_proven(self):
        write = "this.data.set('records',rows);"
        for body in (BODY.replace(write, ''), write + BODY.replace(write, ''),
                     BODY.replace(write, "if(ok){" + write + '}'), BODY.replace(write, "this.data.set('other',rows);"),
                     BODY.replace('rows[0].amount=', 'if(skip)return;rows[0].amount=')):
            with self.subTest(body=body):
                self.assertIn('nested_state_mutation', [i['code'] for i in mutation_issues(body)])

    def test_outer_scope_and_method_parameter_shadowed_math_are_not_assumed_pure(self):
        self.assertTrue(mutation_issues(BODY, signature='update(Math)'))
        self.assertTrue(mutation_issues(BODY, prefix='const Math=custom;'))

    def test_direct_original_state_mutation_is_not_hidden_by_a_safe_clone(self):
        body = BODY + "const shared=this.data.get('records');shared[0].amount=2;"
        self.assertTrue(mutation_issues(body))

    def test_proof_failure_retains_diagnostic(self):
        with patch('migration_pipeline.utils.detached_record_semantics.subprocess.run', side_effect=OSError):
            proven_record_copies.cache_clear()
            self.assertTrue(mutation_issues(BODY))
        proven_record_copies.cache_clear()

    def test_missing_write_still_has_deterministic_restore(self):
        vue, san = watcher_fixture()
        code = san.replace('WRITE', '')
        result = inspect_semantics(code, vue, repair=True)
        self.assertIn('source_watch_persistence_not_landed', [f['code'] for f in result['findings']])
        self.assertEqual(result['changes'], ['restored_source_watch_persistence'])
        self.assertEqual(inspect_semantics(result['code'], vue)['findings'], [])

    def test_wrapped_conditional_duplicate_or_dynamic_write_is_unproven_not_missing(self):
        vue, san = watcher_fixture()
        write = "localStorage.setItem('prefs',JSON.stringify(next));"
        for extra in ('try{' + write + '}catch(e){}', 'if(next.enabled){' + write + '}',
                      write + write, "localStorage.setItem(key,JSON.stringify(next));"):
            with self.subTest(extra=extra):
                code = san.replace('WRITE', extra)
                result = inspect_semantics(code, vue, repair=True)
                self.assertEqual([f['code'] for f in result['findings']], ['source_watch_persistence_unproven'])
                self.assertFalse(result['watcher_contracts'][0]['repairable'])
                self.assertEqual(result['code'], code)
                self.assertEqual(result['changes'], [])

    def test_unproven_watch_write_stays_in_gate_and_focused_prompt(self):
        vue, san = watcher_fixture()
        code = san.replace('WRITE', "try{localStorage.setItem('prefs',JSON.stringify(next));}catch(e){}")
        errors = inspect_semantics(code, vue)['findings']
        self.assertTrue(candidate_gate(gate_state([]), gate_state(errors))['should_stop'])
        prompt = build_repair_prompt(RepairPromptInput(ssm={}, current_code=code, vue_source=vue, validation_errors=errors))
        for text in ('Source watcher contract evidence', 'not permission to append', 'throwing storage behavior'):
            self.assertIn(text, prompt)

    def test_normal_storage_writes_match_but_throwing_storage_behavior_differs(self):
        # Controlled fixture only; never execute raw generated SFC or real storage.
        js = """function check(wrapped,fail){const writes=[];let escaped=false;
const localStorage={setItem(k,v){if(fail)throw Error('storage blocked');writes.push([k,v]);}};
const value={enabled:true};try{if(wrapped){try{localStorage.setItem('prefs',JSON.stringify(value));}catch(e){}}
else{localStorage.setItem('prefs',JSON.stringify(value));}}catch(e){escaped=true;}
return {writes,escaped};}process.stdout.write(JSON.stringify({normal:[check(false,false),check(true,false)],
throwing:[check(false,true),check(true,true)]}));"""
        proc = subprocess.run(['node', '-e', js], cwd=ROOT, text=True, encoding='utf-8', capture_output=True, check=True)
        data = json.loads(proc.stdout)
        self.assertEqual(data['normal'][0], data['normal'][1])
        self.assertEqual([x['escaped'] for x in data['throwing']], [True, False])

    def frozen_case(self, name):
        snapshot = ROOT / 'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821'
        state = json.loads((snapshot / f'repair_reports/complex/{name}_repair_history.json').read_text(encoding='utf-8'))['state']
        vue = snapshot / f'protocol/frozen/data/datasets/components/03_complex/{name}/vue/{name}.vue'
        def assess(code, visual):
            val = ValidateStage().run(ValidateStageInput(generated_code=code, ssm=state['ssm'], vue_file_path=str(vue)))
            return {'generated_code': code, 'ssm': state['ssm'], 'vue_file_path': str(vue),
                    'visual_eval_passed': visual, **val.to_state_update()}
        return state, assess

    def test_frozen_rule_builder_can_progress_but_still_fails_default_validation(self):
        state, assess = self.frozen_case('RuleBuilder')
        before = assess(state['final_code'], state['final_visual_eval_result']['visual_eval_passed'])
        entry = state['repair_history'][0]
        after = assess(entry['repair_result']['repaired_code'], entry['visual_eval_passed'])
        self.assertFalse(candidate_gate(before, after)['should_stop'])
        self.assertFalse(after['validation_passed'])
        self.assertEqual(after['validation_errors'][0]['details']['affected_fields'], ['initialGroups'])

    def test_frozen_monitoring_clone_diagnostic_clears_but_wrapped_persistence_still_fails(self):
        state, assess = self.frozen_case('MonitoringDashboard')
        after = assess(state['final_code'], state['final_visual_eval_result']['visual_eval_passed'])
        self.assertEqual([e['code'] for e in after['validation_errors']], ['source_watch_persistence_unproven'])
        self.assertFalse(after['validation_passed'])


if __name__ == '__main__':
    unittest.main()
