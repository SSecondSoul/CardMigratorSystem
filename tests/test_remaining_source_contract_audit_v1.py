"""Evidence tests, including expected negative observations, not component acceptance."""
import json
import subprocess
import unittest
from functools import lru_cache
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_remaining_contract_audit_v1_input_20261115'


def fixture():
    b=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'))
    return tuple((ROOT/b[k]['path']).read_text(encoding='utf-8') for k in ['candidate','source'])


@lru_cache(maxsize=32)
def inspect(code,vue,native=False):
    p=subprocess.run(['node','migration_pipeline/audit_remaining_source_contracts_v1.cjs'],cwd=ROOT,
        input=json.dumps({'code':code,'vue':vue,'run_native':native,'runtime':str(ROOT/'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js')}),
        text=True,encoding='utf-8',capture_output=True,timeout=30)
    if p.returncode:raise AssertionError(p.stderr+p.stdout)
    return json.loads(p.stdout)


def projection(result):
    # Preserve raw engine-specific computed-store traffic separately. Project
    # only program root commits / notify / event and all observer callbacks.
    return {**result,'trace':[r for r in result['trace'] if r['phase']!='runtime_internal_store']}


class RemainingSourceContractAuditTests(unittest.TestCase):
    def test_fourteen_literal_root_calls_are_counts_not_semantic_equivalence(self):
        r=inspect(*fixture())['static'];self.assertEqual(r['source_call_count'],14)
        self.assertTrue(r['all_known_calls_literal_declared']);self.assertTrue(r['site_counts_match']);self.assertTrue(r['supplied_sfc_calls_closed'])
        self.assertFalse(r['rhs_and_timing_equivalence_proven']);self.assertFalse(r['external_consumers_checked']);self.assertFalse(r['validation_exemption_granted'])

    def test_helper_and_fields_not_component_name_allowlisted(self):
        c,v=fixture()
        for a,b in [('TripItineraryPlanner','ScheduleBoard'),('setValue','putRoot'),('items','records'),('saved','dirtyFlag')]:c=c.replace(a,b);v=v.replace(a,b)
        r=inspect(c,v)['static'];self.assertEqual(r['helper'],'putRoot');self.assertEqual(r['source_call_count'],14);self.assertTrue(r['site_counts_match'])

    def test_dynamic_or_unknown_key_is_not_reported_as_closed(self):
        c,v=fixture()
        for value in ['field',"'unknownField'","'draft.start'"]:
            r=inspect(c,v.replace("this.setValue('activeDayId', id)",f'this.setValue({value}, id)'))['static']
            self.assertFalse(r['all_known_calls_literal_declared']);self.assertFalse(r['supplied_sfc_calls_closed'])

    def test_reference_escape_dynamic_dispatch_and_template_use_are_visible(self):
        c,v=fixture()
        for addition,field in [('const ref=this.setValue;','source_reference_escapes'),('this[handler](1);','dynamic_instance_accesses'),('this?.[handler](1);','dynamic_instance_accesses'),('external(this);','instance_escapes')]:
            changed=v.replace('    selectDay(id) {','    selectDay(id) {'+addition)
            self.assertNotEqual(changed,v);r=inspect(c,changed)['static'];self.assertTrue(r[field]);self.assertFalse(r['supplied_sfc_calls_closed'])
        r=inspect(c,v.replace('@click="save"','@click="setValue"'))['static'];self.assertTrue(r['template_mentions_helper']);self.assertFalse(r['supplied_sfc_calls_closed'])

    def test_unknown_or_ambiguous_setter_is_not_guessed(self):
        c,v=fixture()
        for changed in [v.replace('this[key] = value;','this[key] = value; this.extra();'),v.replace('setValue(key, value) {','setValue(key, value, extra) {')]:
            self.assertEqual(inspect(c,changed)['static']['status'],'unassessed')
        self.assertEqual(inspect(c.replace('san.defineComponent({','other({'),v)['static']['status'],'unassessed')

    def test_missing_target_root_write_is_not_hidden(self):
        c,v=fixture();changed=c.replace("this.data.set('saved',false);this.notify(next);","this.notify(next);")
        self.assertNotEqual(changed,c);r=inspect(changed,v)['static'];self.assertFalse(r['site_counts_match'])

    def test_static_mode_does_not_execute_generated_script(self):
        c,v=fixture();r=inspect(c.replace("const san = require('san');","throw new Error('must not execute');const san = require('san');"),v)
        self.assertEqual(r['static']['status'],'assessed');self.assertNotIn('native',r)

    def test_component_move_cases_match_only_at_declared_projection(self):
        r=inspect(*fixture(),True)['native']['component_only'];self.assertEqual(len(r),5)
        for name,pair in r.items():
            with self.subTest(case=name):self.assertEqual(projection(pair['source']),projection(pair['target']))
        forward=r['forward'];self.assertNotEqual(forward['source']['trace'],forward['target']['trace'])
        self.assertEqual(forward['target']['immediate']['visibleIds'],[2,1]);self.assertEqual(forward['target']['sameNested'],[True,True,True])
        self.assertEqual([x['phase'] for x in projection(forward['target'])['trace']],['root_commit','root_commit','notify','event'])

    def test_external_observer_counterexample_is_retained_not_waived(self):
        pair=inspect(*fixture(),True)['native']['extra_observer']
        self.assertEqual(len(pair['source']['notices']),3);self.assertEqual(len(pair['target']['notices']),1)
        self.assertEqual(pair['source']['notices'][0]['starts'],['10:00','10:00','14:00'])
        self.assertNotEqual(projection(pair['source']),projection(pair['target']))
        self.assertEqual(pair['source']['immediate'],pair['target']['immediate'])

    def test_naive_dynamic_store_adapter_is_observably_not_source_assignment(self):
        r=inspect(*fixture(),True)['native']['dynamic_setter']
        self.assertEqual(r['source']['literalInstanceKey'],'literal');self.assertEqual(r['source']['nestedStart'],r['source']['originalNestedStart'])
        self.assertEqual(r['naivePathStore']['nestedStart'],'literal');self.assertFalse(r['naivePathStore']['literalInstanceKeyPresent'])
        self.assertFalse(r['source']['lateDeclared']);self.assertEqual(r['target']['callableType'],'undefined');self.assertFalse(r['production_adapter_installed'])

    def test_actual_source_remove_click_still_fails_after_computed_repair(self):
        r=inspect(*fixture(),True)['native']['additional_call_path_probes']['remove']
        self.assertIsNone(r['source']['error']);self.assertEqual(r['source']['after']['ids'],[2]);self.assertEqual(len(r['source']['events']),1)
        self.assertEqual(r['target']['error']['name'],'TypeError');self.assertEqual(r['target']['after']['ids'],[1,2]);self.assertEqual(r['target']['events'],[])

    def test_public_counter_helper_mismatch_is_not_confused_with_private_template_copy(self):
        r=inspect(*fixture(),True)['native']['additional_call_path_probes']['public-count']
        self.assertIsNone(r['source']['error']);self.assertEqual(r['target']['error']['name'],'TypeError')
        self.assertIn('private',r['scope'])


if __name__=='__main__':unittest.main()
