"""Do not turn finite UI controls into an invented public/state-persistence contract."""
import json
from pathlib import Path
import unittest

from test_parent_dynamic_key_adapter_probe import node, adapt, generic_pair
from migration_pipeline.audit_formal_30_v4_parent_watch_boundaries_v1 import SAN,VUE,VUE_RUNTIME,SAN_RUNTIME
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import PARENT_WATCH_REVIEW_CODES

ROOT=Path(__file__).resolve().parents[1]
PRIOR=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_keys_probe_v1_20261112'
STATIC=ROOT/'migration_pipeline/audit_parent_dynamic_key_contract.cjs'
RUNTIME=ROOT/'migration_pipeline/audit_parent_dynamic_key_reachability_runtime.cjs'


def computed_pair():
    normal,vue=generic_pair()
    assert normal.count('inited(){')==1 and vue.count('methods:{')==1
    normal=normal.replace('inited(){',"computed:{label(){const o=this.data.get('settings');return o.enabled?'on':'off';}},inited(){")
    vue=vue.replace('methods:{',"computed:{label(){const o=this.settings;return o.enabled?'on':'off';}},methods:{")
    candidate=adapt(normal,vue)
    assert candidate['changes'] and not candidate['production_eligible']
    return {'normal':normal,'vue':vue,'candidate':candidate['code']}


def payload():
    return {'normal':SAN.read_text(encoding='utf-8'),'vue':VUE.read_text(encoding='utf-8'),
        'candidate':(PRIOR/'TaskManager_dynamic_key_probe_offline.san').read_text(encoding='utf-8'),
        'generic':computed_pair(),'vueRuntime':VUE_RUNTIME.read_bytes().decode('utf-8'),
        'sanRuntime':SAN_RUNTIME.read_bytes().decode('utf-8')}


class ParentDynamicKeyContractAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload=payload();cls.contract=node(STATIC,{'vue':cls.payload['vue']})
        cls.runtime=node(RUNTIME,cls.payload)

    def phase(self,scenario,variant,phase):
        row=next(r for r in self.runtime['runs'] if r['scenario']==scenario and r['variant']==variant)
        return next(r for r in row['phases'] if r['name']==phase)

    def test_known_ui_four_keys_are_not_a_public_contract(self):
        row=self.contract['writers'][0]
        self.assertEqual(row['observed_ui_keys'],['autoSave','defaultView','notifications','syncInterval'])
        self.assertTrue(row['ui_routes_finite_in_supported_templates'])
        self.assertFalse(row['entry_guard_before_write']);self.assertFalse(row['public_domain_proven'])
        self.assertFalse(self.contract['public_contract_closed'] or self.contract['production_eligible'] or self.contract['code_modified'])

    def test_native_checkbox_and_select_value_evidence(self):
        rows={r['key']:r for r in self.contract['writers'][0]['ui_routes']}
        self.assertEqual(rows['autoSave']['value_kind'],'native_checkbox_boolean')
        self.assertEqual(rows['notifications']['value_kind'],'native_checkbox_boolean')
        self.assertEqual(rows['defaultView']['native_option_values'],['list','board'])
        self.assertEqual(rows['syncInterval']['native_option_values'],['0','30','60','300'])
        self.assertTrue(all(r['prop_bindings']==['settings'] for r in rows.values()))

    def test_json_restore_spread_does_not_prove_flat_scalar_shape(self):
        row=self.contract['writers'][0]
        self.assertTrue(row['initial_flat_scalar'])
        self.assertEqual(len(row['root_replacements']),1)
        replacement=row['root_replacements'][0]
        self.assertEqual(replacement['method'],'loadInitialData');self.assertFalse(replacement['shape_proven'])
        self.assertEqual(replacement['spreads'],['this.settings','data.settings'])
        self.assertIn('whole_root_replacement_shape_unproven',row['review_reasons'])

    def test_aggregate_alias_is_reported_not_treated_as_no_escape(self):
        row=self.contract['writers'][0]
        self.assertTrue(any(r['method']=='saveToLocalStorage' and r['role']=='aggregate_root_alias' for r in row['root_uses']))
        self.assertIn('root_borrowing_requires_consumer_analysis',row['review_reasons'])

    def test_source_locations_resolve_to_evidence(self):
        row=self.contract['writers'][0]
        text=self.payload['vue']
        # Babel/compiler-dom offsets are UTF-16, not Python Unicode code points.
        encoded=text.encode('utf-16-le')
        self.assertEqual(row['location']['offset_unit'],'utf16_code_units')
        self.assertTrue(encoded[row['location']['offset']*2:].decode('utf-16-le').startswith('updateSettings('))
        for route in row['ui_routes']:
            offset=route['location']['offset']
            self.assertTrue(encoded[offset*2:].decode('utf-16-le').startswith(route['expression']))
            self.assertEqual(encoded[:offset*2].decode('utf-16-le').count('\n')+1,route['location']['line'])

    def test_names_are_not_component_special_cases(self):
        vue=self.payload['vue'].replace('settings','preferences').replace('SettingsPanel','PreferencesPanel').replace('updateSettings','changePreferences')
        row=node(STATIC,{'vue':vue})['writers'][0]
        self.assertEqual(row['method'],'changePreferences');self.assertEqual(row['field'],'preferences')
        self.assertEqual(len(row['observed_ui_keys']),4);self.assertFalse(row['public_domain_proven'])

    def test_dynamic_child_event_key_remains_unknown(self):
        vue=self.payload['vue'].replace("$emit('update', 'defaultView',","$emit('update', dynamicKey,")
        row=node(STATIC,{'vue':vue})['writers'][0]
        self.assertFalse(row['ui_routes_finite_in_supported_templates'])
        self.assertTrue(any(r['key'] is None for r in row['ui_routes']))

    def test_new_internal_call_is_included(self):
        vue=self.payload['vue'].replace('loadInitialData() {',"loadInitialData() {this.updateSettings('customFlag',{});")
        row=node(STATIC,{'vue':vue})['writers'][0]
        self.assertEqual(len(row['internal_calls']),1)
        self.assertEqual(row['internal_calls'][0]['caller'],'loadInitialData')

    def test_computed_root_alias_requires_runtime_proof(self):
        row=node(STATIC,{'vue':self.payload['generic']['vue']})['writers'][0]
        self.assertTrue(any(r['role']=='local_root_alias' for r in row['computed_root_reads']))
        self.assertIn('computed_root_identity_notification_requires_runtime_proof',row['review_reasons'])

    def test_pinned_real_runtime_dimensions_and_restored_listener(self):
        self.assertEqual(len(self.runtime['runs']),15)
        self.assertEqual(sum(len(r['phases']) for r in self.runtime['runs']),90)
        self.assertEqual(len(self.runtime['pairs']),60)
        self.assertTrue(self.runtime['rejectionListenerRestored'] and self.runtime['hostPrototypeClean'])
        self.assertEqual(self.runtime['modelRequests'],0);self.assertFalse(self.runtime['productionChanged'])
        self.assertFalse(self.runtime['fullBrowserOrInitialDomEvaluated'])
        for run in self.runtime['runs']:
            self.assertEqual(run['frameworkVersion'],'2.7.16' if run['variant']=='vue_source' else '3.15.6')

    def test_flat_ui_control_matches_source_in_all_variants(self):
        pairs=[p for p in self.runtime['pairs'] if p['scenario']=='flat_ui_control']
        self.assertEqual(len(pairs),12)
        self.assertTrue(all(p['stateEqual'] and p['eventsEqual'] and p['errorsEqual'] for p in pairs))

    def test_nested_restoration_accepted_by_source_and_original_normal_candidate(self):
        for scenario in ['restore_extra_nested_object','restore_declared_object_value']:
            for phase in ['mount_sync','mount_tick']:
                a=self.phase(scenario,'vue_source',phase)
                b=self.phase(scenario,'san_normal_flow',phase)
                self.assertEqual(a['state'],b['state']);self.assertEqual(a['events'],b['events'])
                self.assertEqual(a['state']['taskIds'],[901])

    def test_nested_restoration_is_a_candidate_startup_regression_not_fixed(self):
        for scenario in ['restore_extra_nested_object','restore_declared_object_value']:
            a=self.phase(scenario,'vue_source','mount_tick')
            b=self.phase(scenario,'san_dynamic_candidate','mount_tick')
            self.assertNotEqual(a['state']['taskIds'],b['state']['taskIds'])
            self.assertNotEqual(a['state'],b['state'])

    def test_public_object_write_is_not_restricted_by_ui_controls(self):
        a=self.phase('public_new_object_value','vue_source','action_tick')
        b=self.phase('public_new_object_value','san_dynamic_candidate','action_tick')
        self.assertEqual(a['state']['settings']['extraConfig'],{'theme':'dark'})
        self.assertNotIn('extraConfig',b['state']['settings'])
        self.assertTrue(any(e['message']=='Dynamic-key probe: unsupported key or value' for e in b['errors']))

    def test_computed_dependency_staleness_hypothesis_is_not_observed_in_scalar_control(self):
        for phase in ['action_sync','action_tick']:
            a=self.phase('computed_root_dependency','vue_source',phase)
            normal=self.phase('computed_root_dependency','san_normal_flow',phase)
            b=self.phase('computed_root_dependency','san_dynamic_candidate',phase)
            self.assertEqual(a['state']['label'],normal['state']['label'])
            self.assertEqual(a['state']['label'],'on');self.assertEqual(b['state']['label'],'on')
            self.assertTrue(b['state']['settings']['enabled'])
            self.assertEqual(b['errors'],[])

    def test_candidate_does_not_discharge_production_boundaries(self):
        result=source_parent_watch_semantics(self.payload['candidate'],self.payload['vue'])
        self.assertEqual({r['code'] for r in result['blocked_boundaries']},PARENT_WATCH_REVIEW_CODES)

    def test_repeat_runtime_audit_is_deterministic(self):
        self.assertEqual(node(RUNTIME,self.payload),self.runtime)


if __name__=='__main__':unittest.main()
