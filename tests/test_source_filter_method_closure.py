"""Closed native filter methods; evidence is not whole-component acceptance."""
import json
import re
import subprocess
import tempfile
import unittest
from functools import lru_cache
from pathlib import Path

from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.repair_client import RepairResult

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_filter_methods_v1_input_20261115'
ISSUE='source_filter_method_not_landed'
CHANGE='restored_source_native_filter_method'


def fixture():
    b=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'))
    return tuple((ROOT/b[k]['path']).read_text(encoding='utf-8') for k in ['candidate','source'])


@lru_cache(maxsize=1)
def native():
    c,v=fixture();fixed=inspect_semantics(c,v,repair=True)['code']
    p=subprocess.run(['node','migration_pipeline/probe_source_filter_methods_v1.cjs'],cwd=ROOT,
        input=json.dumps({'vue':v,'before':c,'after':fixed,'runtime':str(ROOT/'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js')}),
        capture_output=True,text=True,encoding='utf-8',timeout=40)
    if p.returncode:raise AssertionError(p.stderr+p.stdout)
    return json.loads(p.stdout)


class SourceFilterMethodClosureTests(unittest.TestCase):
    def apply(self,c,v,repair=True):
        r=inspect_semantics(c,v,repair=repair);self.assertNotIn('error',r,r);return r

    def state(self,c,v):return {'generated_code':c,'vue_source':v,'ssm':{},'validation_errors':self.apply(c,v,False)['findings']}

    def test_two_contracts_fixed_point_and_no_source_no_change(self):
        c,v=fixture();old=self.apply(c,v,False)
        self.assertEqual(len(old['filter_method_contracts']),2);self.assertTrue(all(x['repair_eligible'] for x in old['filter_method_contracts']))
        r=self.apply(c,v);self.assertEqual(r['changes'],[CHANGE]);again=self.apply(r['code'],v)
        self.assertEqual(again['code'],r['code']);self.assertEqual(again['changes'],[])
        self.assertTrue(all(x['landed'] and not x['global_helpers_modified'] for x in again['filter_method_contracts']))
        self.assertEqual(self.apply(c,'')['code'],c)

    def test_no_name_allowlist(self):
        c,v=fixture()
        for a,b in [('TripItineraryPlanner','ScheduleBoard'),('removeItem','deleteRecord'),('dayCount','groupSize'),('items','records'),('saved','dirty'),('id','key'),('dayId','groupKey'),('notify','publish'),('setValue','putRoot')]:
            c=re.sub(r'\b'+a+r'\b',b,c);v=re.sub(r'\b'+a+r'\b',b,v)
        c=re.sub(r'(?<![.\w])filter\b','filterDense',c)
        r=self.apply(c,v);self.assertIn(CHANGE,r['changes']);self.assertTrue(all(x['landed'] for x in self.apply(r['code'],v)['filter_method_contracts']))

    def test_unknown_helper_or_extra_effects_detected_but_not_overwritten(self):
        c,v=fixture()
        for a,b,name in [('if (predicate(items[i], i, items))','if (unknown(items[i]))','removeItem'),
                         ('const nextItems = filter(items,','extra();const nextItems = filter(items,','removeItem'),
                         ('return dayCountGetter(items, id);','extra();return dayCountGetter(items, id);','dayCount')]:
            bad=c.replace(a,b);self.assertNotEqual(bad,c);r=self.apply(bad,v)
            self.assertFalse(next(x for x in r['filter_method_contracts'] if x['name']==name)['repair_eligible'])
            self.assertTrue(any(x['code']==ISSUE and name in x['location'] for x in self.apply(r['code'],v,False)['findings']))

    def test_helper_escape_shadowing_and_runtime_mutation_refuse(self):
        c,v=fixture()
        for a,b in [('function filter(items, predicate)','const escaped=filter;function filter(items, predicate)'),
                    ("const items = this.data.get('items');\n        const nextItems",'const items = unknown;\n        const nextItems')]:
            r=self.apply(c.replace(a,b),v);self.assertFalse(next(x for x in r['filter_method_contracts'] if x['name']=='removeItem')['repair_eligible'])
        for prefix in ['const Array=other;','Array.prototype.filter=other;','san.defineComponent=other;']:
            r=self.apply(c.replace('module.exports = san.defineComponent',prefix+'module.exports = san.defineComponent'),v)
            self.assertNotIn(CHANGE,r['changes'])
        self.assertNotIn(CHANGE,self.apply(c.replace("require('san')","require('other')"),v)['changes'])

    def test_changed_source_is_not_guessed(self):
        c,v=fixture()
        for a,b in [('item.id !== id','item.id === id'),("this.setValue('saved', false); this.notify(next);","this.notify(next); this.setValue('saved', false);"),
                    ('this[key] = value;','this[key] = value; this.extra();')]:
            changed=v.replace(a,b);self.assertNotEqual(v,changed)
            r=self.apply(c,changed);self.assertFalse(any(x['name']=='removeItem' for x in r['filter_method_contracts']))

    def test_event_chain_mismatch_missing_or_state_collision_not_repaired(self):
        c,v=fixture()
        for bad in [c.replace("this.fire(name, payload);","this.fire(name, payload); this.extra();"),
                    c.replace('notify(items) {','otherNotify(items) {'),c.replace('            items: [],','            notify: 1, items: [],')]:
            self.assertNotEqual(bad,c);r=self.apply(bad,v)
            self.assertFalse(next(x for x in r['filter_method_contracts'] if x['name']=='removeItem')['repair_eligible'])

    def test_native_local_root_alias_is_already_correct(self):
        c,v=fixture();fixed=self.apply(c,v)['code']
        changed=fixed.replace("dayCount(id){return this.data.get('items').filter","dayCount(id){const rows=this.data.get('items');return rows.filter")
        self.assertNotEqual(changed,fixed);r=self.apply(changed,v);self.assertEqual(r['code'],changed)
        self.assertTrue(all(x['landed'] for x in r['filter_method_contracts']))

    def test_missing_proven_event_forwarders_compose_in_same_transaction(self):
        c,v=fixture()
        missing=c.replace("emitEvent(name, payload) {\n  this.fire(name, payload);\n},\nnotify(items) {\n  this.emitEvent('itinerary-change', items);\n}", '')
        # A dangling target notify call deliberately blocks interface restoration.
        # Exercise atomic addition only where all old target notifications were
        # collapsed to fire, as in the original frozen event-interface case.
        missing=missing.replace('this.notify(next);',"this.fire('itinerary-change',next);")
        self.assertNotEqual(missing,c);r=self.apply(missing,v)
        self.assertIn(CHANGE,r['changes']);self.assertIn('restored_source_event_forwarding_interfaces',r['changes'])
        again=self.apply(r['code'],v);self.assertEqual(again['code'],r['code']);self.assertEqual(again['changes'],[])
        self.assertTrue(all(x['landed'] for x in again['filter_method_contracts']))

    def test_source_emit_and_public_method_data_collisions_refuse(self):
        c,v=fixture()
        changed=v.replace('  methods: {', "  methods: {$emit(name,payload){external(name,payload);},")
        self.assertNotEqual(changed,v)
        self.assertFalse(next(x for x in self.apply(c,changed)['filter_method_contracts'] if x['name']=='removeItem')['repair_eligible'])
        collision=v.replace('        items: [],','        dayCount: 0, items: [],')
        self.assertNotEqual(collision,v);self.assertFalse(any(x['name']=='dayCount' for x in self.apply(c,collision)['filter_method_contracts']))

    def test_independent_gate_rejects_forged_success_and_lost_contract(self):
        c,v=fixture();fixed=self.apply(c,v)['code'];before=self.state(c,v);good=self.state(fixed,v)
        self.assertFalse(candidate_gate(before,good)['should_stop'])
        for bad in [c,fixed.replace('dayCount(id){','otherCount(id){'),fixed.replace('item.id!==id','item.id===id')]:
            self.assertNotEqual(bad,fixed)
            gate=candidate_gate(good,{**self.state(bad,v),'validation_errors':[],'validation_passed':True})
            self.assertTrue(gate['should_stop']);self.assertTrue(gate['waived_source_filter_method_findings'] or gate['lost_source_filter_method_contracts'])

    def test_prepass_and_simulated_model_postprocessing_share_rule(self):
        c,v=fixture();fixed=self.apply(c,v)['code']
        class Client:
            def repair(self,request):return RepairResult(code=c,saved_file_path=request.output_file_path,source_file='',ssm={},provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source.vue';path.write_text(v,encoding='utf-8')
            result,steps=RepairStage._deterministic_repair_plan(c,[{'code':ISSUE}],[],{},str(path))
            self.assertEqual(result,fixed);self.assertIn(('bounded_ast_semantics',CHANGE),steps)
            out=RepairStage(Client()).run(RepairStageInput(ssm={},generated_code=c,vue_file_path=str(path),output_file_path=str(Path(tmp)/'out.san'),metadata={'skip_deterministic_prepass':True}))
            self.assertEqual(out.repaired_code.rstrip(),fixed.rstrip());self.assertIn(CHANGE,out.raw_response['pipeline_postprocessing'])

    def test_prompt_is_bounded_and_keeps_other_diagnostics(self):
        p=build_repair_prompt(RepairPromptInput(ssm={},current_code='',validation_errors=[{'code':ISSUE}]))
        for term in ['sparse holes','snapshot length','record identity','root commit / flag / notification','do not globally replace helpers','waive other diagnostics']:self.assertIn(term,p)

    def test_function_oracles_holes_effects_identity_exceptions_and_count_return(self):
        rows=native()['body'];self.assertEqual(len(rows),22)
        for name,row in rows.items():
            with self.subTest(case=name):self.assertEqual(row['source'],row['after'])
        self.assertEqual(rows['dayCount:sparse']['after']['value'],2)
        for name in ['removeItem:sparse','dayCount:sparse','removeItem:append','dayCount:append']:
            self.assertNotEqual(rows[name]['source'],rows[name]['before'])
        self.assertEqual(rows['removeItem:explicit-null']['after']['error']['name'],'TypeError')
        self.assertEqual(rows['dayCount:throwing-getter']['after']['error']['name'],'RangeError')

    def test_real_sparse_delete_repaired_and_other_boundaries_retained(self):
        r=native();old=r['before']['additional_call_path_probes']['remove'];new=r['after']['additional_call_path_probes']['remove']
        self.assertEqual(old['target']['error']['name'],'TypeError');self.assertEqual(new['source'],new['target'])
        self.assertEqual(new['target']['after']['ids'],[2]);self.assertEqual(len(new['target']['events']),1)
        self.assertIsNone(r['after']['additional_call_path_probes']['public-count']['target']['error'])
        self.assertEqual(len(r['after']['extra_observer']['source']['notices']),3)
        self.assertEqual(len(r['after']['extra_observer']['target']['notices']),1)
        self.assertEqual(r['after']['dynamic_setter']['target']['callableType'],'undefined')

    def test_only_two_method_bodies_change(self):
        c,v=fixture();fixed=self.apply(c,v)['code']
        def erase(text):
            text=re.sub(r'    removeItem\(id\) \{[\s\S]*?\n    \},', 'REMOVEMETHOD,',text)
            text=re.sub(r'    dayCount\(id\) \{[\s\S]*?\n    \},', 'COUNTMETHOD,',text)
            text=re.sub(r'    removeItem\(id\)\{[^\n]*\},', 'REMOVEMETHOD,',text)
            text=re.sub(r'    dayCount\(id\)\{[^\n]*\},', 'COUNTMETHOD,',text)
            return text
        self.assertEqual(erase(c),erase(fixed));self.assertEqual(c.split('</script>')[1:],fixed.split('</script>')[1:])

    def test_real_validation_still_blocks_other_two_issues(self):
        c,v=fixture();b=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'))
        state=json.loads((ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821/repair_reports/complex/TripItineraryPlanner_repair_history.json').read_text(encoding='utf-8'))['state']
        def assess(code):return ValidateStage().run(ValidateStageInput(generated_code=code,ssm=state['ssm'],vue_file_path=str(ROOT/b['source']['path'])))
        before=assess(c);after=assess(self.apply(c,v)['code'])
        self.assertEqual(len(before.validation_errors),4);self.assertEqual(len(after.validation_errors),2)
        self.assertEqual({e['code'] for e in after.validation_errors},{'nested_state_mutation','source_method_interface_not_landed'});self.assertFalse(after.validation_passed)


if __name__=='__main__':unittest.main()
