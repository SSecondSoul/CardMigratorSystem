"""Generic boundaries plus immutable failed-job replays. No cloud calls."""
from copy import deepcopy
from hashlib import sha256
import json
import unittest

from test_semantic_comparison_v1 import SOURCE,TARGET,inspect
from test_modular_system import PROJECT
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.adapters.ssm import SSMExtractor
from card_migration_system.stages.evaluation import assess,candidate_decision
from card_migration_system.stages.dom_comparison import proven_control_diagnostic_refinement
from card_migration_system.prompts.repair_context import relevant_ssm

FROZEN=PROJECT/'docs/verification/2026-11-18_closed_loop_v2'
COMPUTED_SOURCE='''<template><p>{{percent}}</p></template><script>export default {
data(){return {items:[1,2]}},computed:{
total(){return this.items.length},percent(){return this.total*10}}}</script><style>p{color:red}</style>'''
COMPUTED_TARGET='''<template><p>{{percent}}</p></template><script>
const san=require('san');const DataTypes=san.DataTypes;
module.exports=san.defineComponent({dataTypes:{},initData(){return {items:[1,2]}},computed:{
total(){return this.data.get('items').length},percent(){return this.computed.total*10}}});
</script><style>p{color:red}</style>'''


def assignment_proof(source_value,target_value):
    source=SOURCE.replace("change(){this.assignField('value',2)}",
        "change(message){this.assignField('value',"+source_value+")}")
    target=TARGET.replace("change(){this.assignField('value',2)}",
        "change(message){this.assignField('value',"+target_value+")}")
    item=next(c for c in inspect(source,target)['method_contracts'] if c.get('dynamic_assignment'))
    return item['dynamic_assignment']['scoped_proof']


class OrdinaryObjectComparisonTests(unittest.TestCase):
    def test_quoted_keys_and_shorthand_are_generic(self):
        for name in ('message','payload','anotherName'):
            # Rename the complete source and target, not a component whitelist.
            a='{id:Date.now(),message}';b='{"id":Date.now(),"message":message}'
            proof=assignment_proof(a,b)
            self.assertEqual(proof['status'],'proven_for_source_internal_calls',proof)
            self.assertFalse(proof['arbitrary_key_semantics_proven'])
            source=SOURCE.replace('change(){this.assignField(\'value\',2)}',
                'change('+name+'){this.assignField(\'value\',{'+name+'})}')
            target=TARGET.replace('change(){this.assignField(\'value\',2)}',
                'change('+name+'){this.assignField(\'value\',{"'+name+'":'+name+'})}')
            self.assertNotIn('source_dynamic_assignment_unproven',[f['code'] for f in inspect(source,target)['findings']])

    def test_order_effects_computed_keys_accessors_spreads_and_values_are_not_erased(self):
        pairs=[('{a:Date.now(),b:Date.now()}','{b:Date.now(),a:Date.now()}'),
               ('{a:message}','{["a"]:message}'),('{get a(){return message}}','{a:message}'),
               ('{...message,a:1}','{a:1,...message}'),('{a:message}','{a:0}'),
               ('{a:1,a:2}','{a:2,a:1}')]
        for a,b in pairs:
            with self.subTest(a=a,b=b):self.assertEqual(assignment_proof(a,b)['status'],'unproven')

    def test_proto_shorthand_is_not_a_prototype_setter(self):
        # Ordinary own __proto__ data property versus special prototype setter.
        a=SOURCE.replace('change(){this.assignField(\'value\',2)}',
            'change(__proto__){this.assignField(\'value\',{__proto__})}')
        b=TARGET.replace('change(){this.assignField(\'value\',2)}',
            'change(__proto__){this.assignField(\'value\',{"__proto__":__proto__})}')
        self.assertIn('source_dynamic_assignment_unproven',[f['code'] for f in inspect(a,b)['findings']])


class ComputedNamespaceTests(unittest.TestCase):
    def codes(self,result):return [f['code'] for f in result['findings']]

    def test_known_source_computed_value_read_is_diagnosed_repaired_and_idempotent(self):
        for name in ('total','renamedMetric'):
            source=COMPUTED_SOURCE.replace('total',name);target=COMPUTED_TARGET.replace('total',name)
            initial=inspect(source,target)
            self.assertIn('invalid_san_computed_namespace_access',self.codes(initial))
            self.assertEqual(initial['code'],target)
            repaired=inspect(source,target,True)
            self.assertIn('source_declared_computed_namespace_value_read',repaired['changes'])
            self.assertIn('this.data.get("'+name+'")',repaired['code'])
            self.assertNotIn('invalid_san_computed_namespace_access',self.codes(inspect(source,repaired['code'])))
            self.assertEqual(inspect(source,repaired['code'],True)['code'],repaired['code'])

    def test_calls_writes_unknown_keys_and_unproven_sources_do_not_get_rewritten(self):
        for expr in ('this.computed.total()','this.computed.total=3','this.computed.total++',
                     'delete this.computed.total','this.computed[key]','this.computed.missing'):
            target=COMPUTED_TARGET.replace('this.computed.total*10',expr)
            result=inspect(COMPUTED_SOURCE,target,True)
            self.assertIn('invalid_san_computed_namespace_access',self.codes(result))
            self.assertEqual(result['code'],target,expr)
        self.assertEqual(inspect('',COMPUTED_TARGET,True)['code'],COMPUTED_TARGET)

    def test_comments_strings_foreign_receiver_and_nested_this_are_not_diagnosed(self):
        for expr in ("'this.computed.total'",'other.computed.total',
                     '(function(){return this.computed.total})()',
                     '(/* this.computed.total */ this.data.get("total"))'):
            target=COMPUTED_TARGET.replace('this.computed.total*10',expr)
            self.assertNotIn('invalid_san_computed_namespace_access',self.codes(inspect(COMPUTED_SOURCE,target)))

    def test_inline_children_are_diagnosed_but_not_given_parent_source_proof(self):
        code=COMPUTED_TARGET.replace("module.exports=", "const child=san.defineComponent({computed:{total(){return 1},percent(){return this.computed.total}}});module.exports=")
        result=inspect(COMPUTED_SOURCE,code,True)
        self.assertIn('return this.computed.total',result['code'])
        child=next(f for f in result['findings'] if f['code']=='invalid_san_computed_namespace_access' and f['details']['component']=='inline_child')
        self.assertFalse(child['details']['source_declared_read_repairable'])

    def test_store_override_or_runtime_extension_refuses_automatic_repair(self):
        for addition in ('data:{},','mixins:[],','extends:other,','inited(){this.data={}},'):
            code=COMPUTED_TARGET.replace('dataTypes:{},','dataTypes:{},'+addition)
            self.assertEqual(inspect(COMPUTED_SOURCE,code,True)['code'],code)

    def test_production_validator_rule_and_prompt_projection_use_same_diagnostic(self):
        ssm=SSMExtractor(PROJECT/'engine').extract(COMPUTED_SOURCE.encode(),'Renamed.vue',sha256(COMPUTED_SOURCE.encode()).hexdigest())['ssm']
        report=legacy_stage(PROJECT/'engine','validate',source=COMPUTED_SOURCE,code=COMPUTED_TARGET,ssm=ssm)
        self.assertIn('invalid_san_computed_namespace_access',[e['code'] for e in report['validation_errors']])
        repair=legacy_stage(PROJECT/'engine','rules',source=COMPUTED_SOURCE,code=COMPUTED_TARGET,ssm=ssm,errors=report['validation_errors'])
        self.assertNotIn('this.computed.total',repair['code'])
        selected,_=relevant_ssm(ssm,{'diagnostics':[{'code':'invalid_san_computed_namespace_access'}],'dimensions':{'visual':'pass'}})
        self.assertIn('script',selected)


class DiagnosticRefinementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=FROZEN/'jobs/42acb66baae046dc84c8dc862e321abc'
        request=json.loads((p/'request.json').read_bytes())['request'];ssm=json.loads((p/'ssm.json').read_bytes())['ssm']
        cls.reports=[]
        for n in (1,2):
            raw=json.loads((p/f'evaluations/{n}/raw.json').read_bytes())
            cls.reports.append(assess(raw['static'],raw['browser'],request['actions'],request['thresholds'],ssm))

    def test_real_persistent_wrapper_diagnostic_refinement_allows_progress_not_pass(self):
        before,after=deepcopy(self.reports)
        decision=candidate_decision(before,after)
        self.assertTrue(decision['accepted'],decision);self.assertFalse(decision['migration_passed'])
        self.assertEqual(after['dimensions']['structure'],'fail')
        self.assertIn('dom_child_order_mismatch',[e['code'] for e in after['diagnostics']])

    def test_missing_old_version_or_truncated_evidence_remains_fail_closed(self):
        for change in ('missing','incomplete','source_changed','new_wrapper','new_identity'):
            before,after=deepcopy(self.reports)
            if change=='missing':before.pop('control_gate_evidence')
            elif change=='incomplete':after['control_gate_evidence']['complete']=False
            elif change=='source_changed':after['control_gate_evidence']['source_snapshot']='changed'
            elif change=='new_wrapper':after['control_gate_evidence']['target'][-1]['parent_shape']='changed'
            else:after['control_gate_evidence']['target'][-1]['identity']='changed'
            self.assertFalse(proven_control_diagnostic_refinement(before,after),change)
            self.assertFalse(candidate_decision(before,after)['accepted'],change)

    def test_no_new_diagnostics_or_passing_dimension_losses_are_waived(self):
        for change in ('new_diagnostic','runtime_regression','no_dom_progress','no_count_restoration'):
            before,after=deepcopy(self.reports)
            if change=='new_diagnostic':after['diagnostics'].append({'code':'genuine_new_defect'})
            elif change=='runtime_regression':after['dimensions']['compile_runtime']='fail'
            elif change=='no_dom_progress':after['dom_ted']=before['dom_ted']
            else:after['initial_control_state']['target_count']-=1
            self.assertFalse(candidate_decision(before,after)['accepted'],change)

    def test_frozen_inputs_still_match_original_hashes(self):
        manifest=json.loads((FROZEN/'FREEZE.json').read_bytes())
        for name,expected in manifest['files'].items():
            self.assertEqual(sha256((FROZEN/name).read_bytes()).hexdigest(),expected,name)


if __name__=='__main__':unittest.main()
