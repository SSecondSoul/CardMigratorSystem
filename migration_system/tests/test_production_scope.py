"""A bounded usable chain does not grant the unfinished proxy contract admission."""
from copy import deepcopy
import unittest

from test_modular_system import ModularFixture
from card_migration_system.contracts.production_scope import production_scope
from card_migration_system.interfaces.api.app import create_app
from card_migration_system.application.service import ServiceError
from card_migration_system.reporting.identity import digest


class ProductionScopeTests(ModularFixture, unittest.TestCase):
    def test_scope_is_server_owned_and_snapshotted_in_request_and_report(self):
        key = self.enqueue()
        expected = production_scope()
        self.assertEqual(self.service.job(key).request['support_scope'], expected)
        result = self.run_graph(key)
        self.assertEqual(result['support_scope'], expected)
        self.assertEqual(result['request_sha256'], digest(result['request']))
        self.assertEqual(result['status'], 'finished')
        self.assertEqual(result['assessment']['dimensions']['interaction'], 'not_run')
        self.assertFalse(result['support_scope']['full_public_instance_compatibility'])
        self.assertFalse(result['support_scope']['experimental_public_instance_runtime_enabled'])
        self.assertFalse(result['support_scope']['source_ast_rule_generation_enabled'])
        self.assertEqual(result['support_scope']['runtime_admission'],'not_enabled_in_production')
        self.assertEqual(result['support_scope']['id'],'san-supported-migration-v3')

    def test_client_cannot_select_an_unimplemented_contract_or_waive_checks(self):
        with self.assertRaises(ServiceError):
            self.enqueue(support_scope={'id': 'full-proxy', 'allow_unsupported': True})

    def test_readiness_exposes_current_scope_without_changing_historical_requests(self):
        key = self.enqueue()
        request = deepcopy(self.service.job(key).request)
        app = create_app(self.settings, write_token='scope-test-token-at-least-24-chars')
        self.addCleanup(app.extensions['migration_service'].close)
        client = app.test_client()
        response = client.get('/api/v1/system/readiness', base_url='http://127.0.0.1:8790')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['support_scope'], production_scope())
        self.assertEqual(self.service.job(key).request, request)

    def test_legacy_request_is_not_rewritten_or_relabelled_by_new_report(self):
        key = self.enqueue()
        legacy = deepcopy(self.service.job(key).request)
        legacy.pop('support_scope')
        self.service.update(key, request=legacy, request_sha256=digest(legacy))
        report = self.service.report(key)
        self.assertIsNone(report['support_scope'])
        self.assertNotIn('support_scope', self.service.job(key).request)

    def test_mutating_a_returned_scope_does_not_change_future_requests(self):
        snapshot = production_scope()
        snapshot['exports'].clear()
        snapshot['full_public_instance_compatibility'] = True
        self.assertEqual(production_scope()['exports'], ['export default', 'module.exports'])
        self.assertFalse(production_scope()['full_public_instance_compatibility'])


if __name__ == '__main__':
    unittest.main()
