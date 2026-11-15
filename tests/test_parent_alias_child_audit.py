"""Native parent/child propagation counterexamples, not browser/manual acceptance."""
import json
from pathlib import Path
import unittest

from test_parent_dynamic_key_adapter_probe import node,generic_pair
from test_parent_dynamic_key_object_values_v3 import adapt
from migration_pipeline.audit_formal_30_v4_parent_watch_boundaries_v1 import VUE_RUNTIME,SAN_RUNTIME
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import PARENT_WATCH_REVIEW_CODES

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'migration_pipeline/audit_parent_alias_child_runtime.cjs'


def fixture():
    normal,vue=generic_pair()
    before="{enabled:true}"
    initial="{enabled:true,extra:{name:'initial',items:[{value:1}]}}"
    restored="{enabled:false,extra:{name:'initial',items:[{value:1}]}}"
    assert normal.count(before)==1 and vue.count(before)==1
    normal=normal.replace(before,initial).replace("this.data.set('settings',{enabled:false});","this.data.set('settings',"+restored+");")
    vue=vue.replace(before,initial).replace('this.settings={enabled:false};','this.settings='+restored+';')
    v3=adapt(normal,vue);assert v3['changes'] and not v3['production_eligible']
    return {'normal':normal,'vue':vue,'v3':v3['code']}


MINI_DOM_CHECK=r"""
const {miniDOM}=require('./migration_pipeline/audit_parent_alias_child_runtime.cjs');const d=miniDOM(),h=d.host();
const a=d.document.createElement('span'),b=d.document.createTextNode('one'),c=d.document.createComment('hidden');
h.appendChild(a);a.appendChild(b);a.appendChild(c);const before=h.textContent;
b.nodeValue='two';const after=h.textContent;const clone=a.cloneNode(true);h.insertBefore(clone,a);h.removeChild(a);
let rejected=false;try{h.innerHTML='<script>unexpected</script>';}catch(e){rejected=true;}
process.stdout.write(JSON.stringify({before,after,cloned:h.textContent,owner:a.ownerDocument===d.document,
 siblings:clone.nextSibling===null,detached:a.parentNode===null,rejected}));
"""


class ParentAliasChildAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=fixture();cls.payload={**cls.fixture,'vueRuntime':VUE_RUNTIME.read_bytes().decode('utf-8'),
                                         'sanRuntime':SAN_RUNTIME.read_bytes().decode('utf-8')}
        cls.actual=node(RUNTIME,cls.payload)

    def frame(self,scenario,variant='v3',phase='action_tick'):
        return next(p for r in self.actual['runs'] if r['scenario']==scenario and r['variant']==variant for p in r['frames'] if p['name']==phase)

    def test_actual_runtime_dimensions(self):
        self.assertEqual(len(self.actual['runs']),27)
        self.assertEqual(sum(len(r['frames']) for r in self.actual['runs']),108)
        self.assertEqual(len(self.actual['pairs']),72)
        self.assertTrue(self.actual['rejectionListenerRestored'])
        self.assertEqual(self.actual['modelRequests'],0);self.assertFalse(self.actual['productionIntegrationEnabled'])

    def test_real_native_children_attached_on_limited_dom_not_mocked_framework_data(self):
        for run in self.actual['runs']:
            self.assertTrue(run['nativeParentAndChildAttached'])
            self.assertTrue(run['boundary']['nativePropBinding'] and run['boundary']['nativeDOMTextWrites'])
            self.assertTrue(run['boundary']['minimalDOMAdapter'])
            for flag in ['frameworkDataMocked','browser','cssLayoutTested','canonicalTaskManagerChildTested']:
                self.assertFalse(run['boundary'][flag])
            self.assertEqual(run['frameworkVersion'],'2.7.16' if run['variant']=='vue_source' else '3.15.6')

    def test_mount_control_all_variants_have_child_and_actual_text(self):
        for scenario in self.actual['scenarios']:
            for variant in ['vue_source','normal','v3']:
                frame=self.frame(scenario,variant,'mount_tick')
                self.assertEqual(frame['state']['domText'],'false|initial|1|1')
                self.assertEqual(frame['state']['child']['computed'],'false|initial|1|1')
                self.assertTrue(frame['state']['child']['sharesRoot'])

    def test_public_scalar_write_parent_state_matches_but_v3_child_stays_stale(self):
        source=self.frame('writer_scalar','vue_source');v3=self.frame('writer_scalar')
        self.assertEqual(source['state']['parentSettings'],v3['state']['parentSettings'])
        self.assertEqual(source['state']['domText'],'true|initial|1|1')
        self.assertEqual(v3['state']['domText'],'false|initial|1|1')
        self.assertTrue(v3['state']['child']['raw']['enabled'])
        self.assertEqual(v3['state']['child']['computed'],'false|initial|1|1')

    def test_public_object_write_parent_state_matches_but_v3_child_stays_stale(self):
        source=self.frame('writer_object','vue_source');v3=self.frame('writer_object')
        self.assertEqual(source['state']['parentSettings'],v3['state']['parentSettings'])
        self.assertEqual(source['state']['domText'],'false|object|1|8')
        self.assertEqual(v3['state']['domText'],'false|initial|1|1')
        self.assertEqual(v3['state']['child']['raw']['extra']['name'],'object')

    def test_normal_clone_control_updates_child_after_public_writer(self):
        for scenario in ['writer_scalar','writer_object']:
            self.assertEqual(self.frame(scenario,'vue_source')['state']['domText'],self.frame(scenario,'normal')['state']['domText'])

    def test_borrowed_property_changes_raw_state_without_target_watch_effect(self):
        for scenario in ['borrowed_existing_property','borrowed_array_push','borrowed_nested_item']:
            source=self.frame(scenario,'vue_source')
            self.assertEqual([e['name'] for e in source['events']],['recount'])
            for variant in ['normal','v3']:
                target=self.frame(scenario,variant)
                self.assertEqual(target['state']['parentSettings'],source['state']['parentSettings'])
                self.assertEqual(target['state']['count'],source['state']['count'])
                self.assertEqual(target['events'],[])
                self.assertNotEqual(target['state']['domText'],source['state']['domText'])

    def test_borrowed_array_and_nested_item_native_source_observation(self):
        self.assertEqual(self.frame('borrowed_array_push','vue_source')['state']['domText'],'false|initial|2|1')
        self.assertEqual(self.frame('borrowed_nested_item','vue_source')['state']['domText'],'false|initial|1|9')

    def test_new_key_is_deliberately_nonreactive_in_vue2_not_a_missing_target_fix(self):
        for variant in ['vue_source','normal','v3']:
            frame=self.frame('borrowed_new_key_control',variant)
            self.assertEqual(frame['events'],[])
            self.assertEqual(frame['state']['domText'],'false|initial|1|1')
            self.assertEqual(frame['state']['parentSettings']['extra']['newFlag'],'new')

    def test_same_value_control_all_variants_have_no_extra_watch(self):
        for variant in ['vue_source','normal','v3']:
            frame=self.frame('control_same_value',variant)
            self.assertEqual(frame['events'],[]);self.assertEqual(frame['state']['domText'],'false|initial|1|1')

    def test_whole_root_replacement_control_proves_native_prop_update_route_runs(self):
        for variant in ['vue_source','normal','v3']:
            frame=self.frame('control_root_replacement',variant)
            self.assertEqual(frame['state']['domText'],'true|replaced|1|7')
            self.assertEqual([e['name'] for e in frame['events']],['recount'])
            self.assertTrue(frame['state']['child']['sharesRoot'])

    def test_san_data_api_nested_control_updates_child_unlike_raw_alias(self):
        for variant in ['vue_source','normal','v3']:
            frame=self.frame('control_data_api_nested',variant)
            self.assertEqual(frame['state']['domText'],'false|api|1|1')
            self.assertEqual([e['name'] for e in frame['events']],['recount'])

    def test_no_runtime_error_misclassified_as_semantic_mismatch(self):
        for run in self.actual['runs']:
            self.assertEqual(run['errors'],[])
            self.assertTrue(all(not p['errors'] and not p['warnings'] for p in run['frames']))

    def test_dom_adapter_has_consistent_text_identity_and_rejects_unimplemented_html_parser(self):
        result=node(MINI_DOM_CHECK,{})
        self.assertEqual(result,{'before':'one','after':'two','cloned':'two','owner':True,'siblings':True,'detached':True,'rejected':True})

    def test_production_boundaries_remain_unwaived(self):
        r=source_parent_watch_semantics(self.fixture['v3'],self.fixture['vue'])
        # This synthetic fixture has no storage side effects: only the dynamic-key boundary applies.
        self.assertEqual({b['code'] for b in r['blocked_boundaries']},{'source_parent_watch_dynamic_key_unproven'})
        frozen=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_keys_probe_v3_20261112'
        prior=json.loads((frozen/'audit.json').read_text(encoding='utf-8'))
        vue_path=ROOT/next(p for p in prior['source_inputs'] if p.endswith('.vue'))
        actual=source_parent_watch_semantics(prior['candidate']['code'],vue_path.read_text(encoding='utf-8'))
        self.assertEqual({b['code'] for b in actual['blocked_boundaries']},PARENT_WATCH_REVIEW_CODES)

    def test_audit_repeats_deterministically(self):
        self.assertEqual(node(RUNTIME,self.payload),self.actual)


if __name__=='__main__':unittest.main()
