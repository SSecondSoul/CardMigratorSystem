"""Partial native-assignment fix; observer counterexamples must remain visible."""
import json
import unittest

from migration_pipeline.audit_source_property_assignment_v8 import candidates, ADAPTER
from migration_pipeline.audit_v7_dynamic_shape import payload, node, ROOT, RUNTIME, OUT as NEGATIVE
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate


class SourcePropertyAssignmentV8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.input = payload(); cls.candidate = candidates(cls.input)
        cls.observed = node(ROOT / RUNTIME, {**cls.input, **{n: r['code'] for n, r in cls.candidate.items()}})
        cls.baseline = json.loads((NEGATIVE / 'observations.json').read_text(encoding='utf-8'))

    def assert_fixed(self, scenario):
        rows = [p for p in self.observed['pairs'] if p['scenario'] == scenario]
        self.assertTrue(rows); self.assertTrue(all(p['equal'] for p in rows), rows)

    def test_opt_in_only_no_production_eligibility(self):
        result = node(ROOT / ADAPTER, {'code': self.input['san'], 'vue': self.input['vue']})
        self.assertEqual(result['code'], self.input['san']); self.assertEqual(result['changes'], [])
        self.assertFalse(result['production_eligible'])
        self.assertFalse(self.candidate['san']['production_eligible'])

    def test_requires_full_v7_source_structure_not_marker_names(self):
        broken = self.input['san'].replace('pending[index]=false;', 'pending[index]=true;')
        self.assertNotEqual(broken, self.input['san'])
        result = node(ROOT / ADAPTER, {'code': broken, 'vue': self.input['vue'], 'experimental': True})
        self.assertEqual(result['code'], broken); self.assertEqual(result['changes'], [])

    def test_reapplication_refuses_without_mutation(self):
        code = self.candidate['san']['code']
        result = node(ROOT / ADAPTER, {'code': code, 'vue': self.input['vue'], 'experimental': True})
        self.assertEqual(result['code'], code); self.assertEqual(result['changes'], [])

    def test_numeric_property_key_fixed(self): self.assert_fixed('numeric_key')
    def test_symbol_property_key_fixed_including_source_notification_throw(self): self.assert_fixed('symbol_key')
    def test_existing_coerced_key_fixed(self): self.assert_fixed('coerced_existing_key')
    def test_new_coerced_key_fixed(self): self.assert_fixed('coerced_new_key')
    def test_throwing_conversion_preserves_original_category(self): self.assert_fixed('throwing_key_coercion')
    def test_new_symbol_value_no_longer_rejected(self): self.assert_fixed('new_symbol_value')
    def test_source_numeric_rhs_remains_correct(self): self.assert_fixed('source_rhs_number_conversion')

    def test_no_regression_in_any_previously_equal_comparison(self):
        self.assertEqual(len(self.observed['pairs']), 116)
        for before, after in zip(self.baseline['pairs'], self.observed['pairs']):
            self.assertEqual((before['subject'], before['scenario'], before['phase']), (after['subject'], after['scenario'], after['phase']))
            if before['equal']: self.assertTrue(after['equal'], after)

    def test_partial_improvement_does_not_hide_value_or_subscription_gaps(self):
        self.assertEqual(sum(not p['equal'] for p in self.observed['pairs']), 18)
        self.assertEqual({p['scenario'] for p in self.observed['pairs'] if not p['equal']},
                         {'date_value', 'frozen_value', 'sparse_array_value', 'delete_then_mutate_detached_alias',
                          'redefine_then_mutate_detached_alias', 'nonenumerable_then_mutate_alias'})

    def test_generic_subject_is_fixed_too_not_task_named(self):
        self.assertEqual(self.candidate['genericSan']['writers'][0]['method'], 'assign')
        self.assertEqual(self.candidate['san']['writers'][0]['method'], 'updateSettings')
        self.assert_fixed('existing_changed_value')

    def test_template_css_and_every_other_script_property_untouched(self):
        script = r'''
const fs=require('fs'),parser=require('@babel/parser'),i=JSON.parse(fs.readFileSync(0,'utf8'));
const {parentOf,key}=require('./migration_pipeline/utils/inline_identifier_recovery.cjs');
const {same}=require('./migration_pipeline/utils/source_render_call_semantics.cjs');
const block=s=>/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(s);
const a=parser.parse(block(i.before)[1]),b=parser.parse(block(i.after)[1]);
const names=new Set(i.names);const one=parentOf(a),two=parentOf(b);
one.properties=one.properties.filter(p=>!names.has(key(p)));two.properties=two.properties.filter(p=>!names.has(key(p)));
process.stdout.write(JSON.stringify({otherScriptSame:same(a,b),outerSame:i.before.replace(block(i.before)[1],'SCRIPT')===i.after.replace(block(i.after)[1],'SCRIPT')}));
'''
        # node() here accepts paths, so use the shared test helper for inline JS.
        from test_parent_dynamic_key_adapter_probe import node as eval_node
        for name, row in self.candidate.items():
            result = eval_node(script, {'before': self.input[name], 'after': row['code'], 'names': [w['method'] for w in row['writers']]})
            self.assertEqual(result, {'otherScriptSame': True, 'outerSame': True})

    def test_native_source_assignment_order_and_strict_failure(self):
        from test_parent_dynamic_key_adapter_probe import node as eval_node
        data = self.input
        source = data['genericVue'].replace('this.settings[key]=value;', 'this.settings[key]=Number(value);')
        target = data['genericSan'].replace('.write(0,key,value)', '.write(0,key,Number(value))')
        self.assertNotEqual(source, data['genericVue']); self.assertNotEqual(target, data['genericSan'])
        candidate = node(ROOT / ADAPTER, {'code': target, 'vue': source, 'experimental': True})
        self.assertTrue(candidate['changes'], candidate['reviews'])
        script = r'''
const fs=require('fs'),parser=require('@babel/parser'),i=JSON.parse(fs.readFileSync(0,'utf8'));
const {parentOf}=require('./migration_pipeline/utils/inline_identifier_recovery.cjs');
const {one,print}=require('./migration_pipeline/utils/source_render_call_semantics.cjs');
const ast=parser.parse(/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(i.code)[1]);
const method=one(parentOf(ast),'assign'),object=Function('return ({'+print(method)+'})')();
const trace=[],settings={};object.data={get:()=>settings};
object.assign({toString(){trace.push('key');return 'count';}},{valueOf(){trace.push('rhs');return 7;}});
const sourceTrace=[],source=Function('"use strict";return ({settings:{},assign(key,value){this.settings[key]=Number(value);}})')();
source.assign({toString(){sourceTrace.push('key');return 'count';}},{valueOf(){sourceTrace.push('rhs');return 7;}});
let strictType;object.data={get:()=>Object.freeze({count:0})};try{object.assign('count',2);}catch(e){strictType=e.name;}
process.stdout.write(JSON.stringify({trace,sourceTrace,count:settings.count,sourceCount:source.settings.count,strictType,directives:method.body.directives.map(d=>d.value.value)}));
'''
        result = eval_node(script, {'code': candidate['code']})
        self.assertEqual(result['trace'], result['sourceTrace'])
        self.assertEqual(result['count'], result['sourceCount'])
        self.assertEqual(result, {'trace': ['rhs', 'key'], 'sourceTrace': ['rhs', 'key'], 'count': 7,
                                  'sourceCount': 7, 'strictType': 'TypeError', 'directives': ['use strict']})

    def test_production_three_blockers_and_independent_forged_pass_refusal(self):
        result = source_parent_watch_semantics(self.candidate['san']['code'], self.input['vue'])
        self.assertEqual(len(result['findings']), 3)
        before = {'generated_code': self.input['san'], 'vue_source': self.input['vue'],
                  'validation_errors': source_parent_watch_semantics(self.input['san'], self.input['vue'])['findings']}
        gate = candidate_gate(before, {**before, 'generated_code': self.candidate['san']['code'], 'validation_errors': [], 'validation_passed': True})
        self.assertTrue(gate['should_stop']); self.assertEqual(len(gate['waived_source_parent_watch_boundaries']), 2)


if __name__ == '__main__': unittest.main()
