"""New user-approved scope is a protocol, never a retroactive production waiver."""
from hashlib import sha256
import json
from pathlib import Path
import unittest
from historical_lineage import assert_current_research_source,assert_production_lineage

PROJECT = Path(__file__).resolve().parents[1]
CONTRACT_FILE = PROJECT / 'docs/SAN_BUSINESS_INSTANCE_CONTRACT_V1.json'


class SanBusinessContractPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(CONTRACT_FILE.read_bytes())

    def test_new_scope_is_explicit_and_does_not_reclassify_history(self):
        self.assertEqual(self.policy['contract_id'], 'san-business-instance-v1')
        self.assertTrue(self.policy['authorization']['changes_prior_acceptance_scope'])
        self.assertFalse(self.policy['authorization']['retroactive_success_reclassification'])
        evidence = self.policy['migration_of_evidence']
        for key in ['old_results_mutable', 'old_model_usage_and_denominators_mutable',
                    'old_finite_tests_are_new_contract_completion_proof']:
            self.assertFalse(evidence[key], key)
        self.assertTrue(evidence['cross_contract_rates_must_be_reported_separately'])

    def test_target_is_san_not_a_wrapped_original_vue_component(self):
        target = self.policy['target']
        self.assertEqual(target['component_and_dom_runtime'], 'San')
        self.assertTrue(target['standalone_reactivity_kernel_allowed'])
        for key in ['vue_component_runtime_allowed', 'vue_renderer_allowed',
                    'mount_original_vue_as_target_allowed', 'additional_user_metadata_required']:
            self.assertFalse(target[key], key)

    def test_arbitrary_business_keys_are_not_reduced_to_fixed_calls(self):
        policy = self.policy['business_key_policy']
        self.assertIn('all JavaScript PropertyKey', policy['domain'])
        self.assertIn('never coerced', policy['symbols'])
        self.assertIn('never a caller-key whitelist', policy['declared_state_keys'])
        self.assertFalse(policy['fixed_call_site_key_restriction_allowed'])
        self.assertFalse(policy['arbitrary_value_type_weakening_allowed'])

    def test_public_capabilities_are_requirements_not_private_exclusions(self):
        self.assertEqual(set(self.policy['public_api_inventory']), {
            '$data', '$props', '$attrs', '$slots', '$refs', '$parent', '$root', '$el',
            '$options', '$emit', '$forceUpdate', '$nextTick', '$watch'})
        self.assertEqual(len(self.policy['required_public_behavior']), 10)
        exclusions = self.policy['excluded_equivalence_requirements']
        self.assertEqual(len(exclusions), 3)
        self.assertTrue(all(name.startswith('vue_private_') for name in exclusions))

    def test_private_dependencies_cannot_be_silently_stubbed_or_approved(self):
        policy = self.policy['private_dependency_policy']
        self.assertTrue(policy['scope_exclusion_is_not_source_approval'])
        self.assertTrue(policy['explicit_source_dependency_must_be_reported'])
        self.assertTrue(policy['unknown_access_is_not_automatically_safe'])
        self.assertTrue(policy['public_methods_using_private_dependencies_cannot_be_waived'])
        self.assertFalse(policy['silent_stub_or_fake_vnode_allowed'])

    def test_no_production_admission_is_granted_by_a_document(self):
        status = self.policy['status']
        self.assertEqual(status['protocol'], 'accepted_scope_not_implemented_release')
        self.assertFalse(status['new_contract_complete'])
        self.assertFalse(status['production_admission_eligible'])
        self.assertFalse(status['production_gate_changed_by_this_document'])
        self.assertEqual(status['production_source_gate'], 'source_dynamic_key_contract_unsupported')
        self.assertEqual(len(self.policy['integration_obligations']), 7)

    def test_old_seals_and_engine_remain_intact_after_explicit_production_scope_version(self):
        for version in range(1, 8):
            directory = PROJECT / f'docs/verification/2026-11-17_public_instance_proxy_v{version}'
            sums = json.loads((directory / 'SHA256SUMS.json').read_bytes())
            for name, digest in sums.items():
                self.assertEqual(sha256((directory / name).read_bytes()).hexdigest(), digest)
                assert_current_research_source(self,version,name,digest)
        assert_production_lineage(self)


if __name__ == '__main__':
    unittest.main()
