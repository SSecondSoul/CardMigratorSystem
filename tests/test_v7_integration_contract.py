"""No runtime, browser, model or external service required."""
from copy import deepcopy
import unittest

from migration_pipeline.utils.v7_integration_contract import (
    V7_APPLICATION_SCOPE, MANIFEST_ERROR_POLICY, evaluate_v7_application_scope,
)


def manifest():
    return {'san_adapter': 'v7-parent-watch-report-only',
            'application_error_policy': MANIFEST_ERROR_POLICY,
            'frameworks': {'vue': {'version': '2.7.16'}, 'san': {'version': '3.15.6'}}}


class V7IntegrationContractTests(unittest.TestCase):
    def test_exact_opt_in_accepts_declaration_but_never_production(self):
        result = evaluate_v7_application_scope(deepcopy(V7_APPLICATION_SCOPE), manifest())
        self.assertTrue(result['application_scope_accepted'])
        self.assertFalse(result['production_eligible'])
        self.assertFalse(result['source_equivalence_proven'])
        self.assertFalse(result['runtime_callback_purity_proven'])

    def test_no_missing_fields_or_unknown_capabilities(self):
        for key in V7_APPLICATION_SCOPE:
            declaration = deepcopy(V7_APPLICATION_SCOPE); declaration.pop(key)
            self.assertFalse(evaluate_v7_application_scope(declaration, manifest())['application_scope_accepted'])
        declaration = {**deepcopy(V7_APPLICATION_SCOPE), 'allow_unproven_semantics': True}
        self.assertFalse(evaluate_v7_application_scope(declaration, manifest())['application_scope_accepted'])

    def test_other_environments_ancestors_reactive_or_async_handlers_stay_blocked(self):
        for key, value in [('environment', 'ssr'), ('ancestor_policy', 'dynamic-capture-chain'),
                           ('global_error_policy', 'swallow-all'), ('handler_scheduling', 'async'),
                           ('tracking_policy', 'reactive-state-access'), ('san_adapter', 'none'),
                           ('schema_version', True)]:
            declaration = {**deepcopy(V7_APPLICATION_SCOPE), key: value}
            self.assertFalse(evaluate_v7_application_scope(declaration, manifest())['application_scope_accepted'])

    def test_framework_versions_exact_and_complete(self):
        for versions in ({'vue': '2.7.16'}, {'vue': '2.7.16', 'san': '3.15.3'},
                         {'vue': '2.7.16', 'san': '3.15.6', 'other': '1'}):
            declaration = {**deepcopy(V7_APPLICATION_SCOPE), 'framework_versions': versions}
            self.assertFalse(evaluate_v7_application_scope(declaration, manifest())['application_scope_accepted'])

    def test_manifest_cannot_disagree_with_application_declaration(self):
        for key, value in [('san_adapter', 'none'), ('application_error_policy', 'arbitrary')]:
            data = {**manifest(), key: value}
            self.assertFalse(evaluate_v7_application_scope(V7_APPLICATION_SCOPE, data)['application_scope_accepted'])
        data = manifest(); data['frameworks']['san']['version'] = '3.15.3'
        self.assertFalse(evaluate_v7_application_scope(V7_APPLICATION_SCOPE, data)['application_scope_accepted'])

    def test_null_and_malformed_inputs_do_not_opt_in(self):
        for declaration in (None, [], 'browser', {}):
            self.assertFalse(evaluate_v7_application_scope(declaration, manifest())['application_scope_accepted'])
        for data in (None, [], {}, {'frameworks': {}}, {'frameworks': ['wrong']}, {'frameworks': 'wrong'}):
            self.assertFalse(evaluate_v7_application_scope(V7_APPLICATION_SCOPE, data)['application_scope_accepted'])

    def test_result_and_input_cannot_mutate_the_contract(self):
        declaration = deepcopy(V7_APPLICATION_SCOPE); data = manifest()
        original = deepcopy((declaration, data))
        result = evaluate_v7_application_scope(declaration, data)
        result['supported_declaration']['framework_versions']['san'] = 'wrong'
        self.assertEqual((declaration, data), original)
        self.assertEqual(V7_APPLICATION_SCOPE['framework_versions']['san'], '3.15.6')


if __name__ == '__main__':
    unittest.main()
