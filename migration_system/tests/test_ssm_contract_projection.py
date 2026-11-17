"""Source-stage P1 mapping, not a new experiment or re-score of fixture runs."""
from contextlib import redirect_stdout
import io
import json
from unittest.mock import patch
import unittest

from sqlalchemy.orm.attributes import flag_modified

import test_registered_ssm_graph as fixtures
from card_migration_system.adapters.ssm import ExtractionError, SSMExtractor
from card_migration_system.application.service import ServiceError
from card_migration_system.graph.extraction import execute_extraction
from card_migration_system.interfaces.cli import main
from card_migration_system.persistence.backup import create_backup
from card_migration_system.persistence.database import transaction
from card_migration_system.persistence.ssm_extractions import SSMExtraction, SSMExtractionFile
from card_migration_system.reporting.extraction_projection import PROTOCOL, PROJECTOR
from card_migration_system.reporting.identity import digest
from card_migration_system.stages.extract import json_bytes


class SourceContractTests(unittest.TestCase):
    setUp = fixtures.RegisteredGraphTests.setUp
    execute = fixtures.RegisteredGraphTests.execute
    file = fixtures.RegisteredGraphTests.file
    corrupt_registered_json = fixtures.RegisteredGraphTests.corrupt_registered_json

    def mutate_request(self, key, change):
        with transaction(self.service.engine) as session:
            row = session.get(SSMExtraction, key)
            request = json.loads(json.dumps(row.request))
            change(request)
            row.request, row.request_sha256 = request, digest(request)
            flag_modified(row, 'request')
            path = f'ssm-extractions/{key}/request.json'
            content = json_bytes(request)
            self.file(key, 'request').write_bytes(content)  # Controlled corruption in a temporary tree.
            from hashlib import sha256
            session.get(SSMExtractionFile, path).sha256 = sha256(content).hexdigest()

    def legacy(self, key):
        def change(request):
            request['protocol'] = 'registered-ssm-graph-v1'
            request.pop('contract_snapshot')
        self.mutate_request(key, change)

    def test_request_snapshot_is_frozen_before_any_parser_execution(self):
        with patch.object(SSMExtractor, 'extract', side_effect=AssertionError('not called')):
            key = self.ledger.create(run_id=self.run_id)
            report = self.ledger.report(key)
        snapshot = report['request']['contract_snapshot']
        self.assertEqual(report['request']['protocol'], PROTOCOL)
        request = self.service.binding.contracts.load_contract(snapshot['request'])
        self.assertEqual(request.run_id, 'ssm:' + key)
        self.assertNotEqual(request.run_id, self.run_id)
        self.assertEqual(request.sample_id, 'input:' + self.source['input_id'])
        self.assertEqual(request.ssm_schema_version, '3.0')
        self.assertEqual(request.budget.max_total_tokens, 0)
        self.assertEqual(request.budget.max_model_repair_calls, 0)
        for field, description in (('protocol_sha256', 'protocol'), ('prompt_set_sha256', 'prompt_set'),
                                  ('evaluation_policy_sha256', 'evaluation_policy'), ('model_config_sha256', 'model_config')):
            self.assertEqual(getattr(request, field), digest(snapshot['descriptors'][description]))

    def test_prepared_report_is_not_run_without_fake_metrics(self):
        key = self.ledger.create(input_id=self.source['input_id'])
        report = self.ledger.report(key)
        self.assertEqual(report['contract_report']['status'], 'not_run')
        self.assertEqual(report['contract_evaluation']['status'], 'not_run')
        self.assertEqual(report['contract_evaluation']['metrics'], {})
        self.assertIsNone(report['contract_evaluation']['evaluator_version'])
        self.assertIsNone(report['contract_evaluation']['environment_sha256'])

    def test_completed_source_pass_is_not_a_san_revision_or_migration_pass(self):
        key = self.execute()['extraction_id']
        report = self.ledger.report(key)
        evaluation, contract = report['contract_evaluation'], report['contract_report']
        self.assertEqual(evaluation['status'], 'pass')
        self.assertEqual(evaluation['evidence_level'], 'static')
        self.assertEqual(evaluation['evaluator_version'], PROJECTOR)
        self.assertEqual(len(evaluation['environment_sha256']), 64)
        self.assertIsNone(evaluation['revision_id'])
        self.assertEqual(evaluation['coverage'], [])
        self.assertEqual(contract['status'], 'not_run')
        self.assertIsNone(contract['final_revision_id'])
        self.assertEqual(contract['revisions'], [])
        self.assertEqual(contract['repair_decisions'], [])
        self.assertEqual(contract['candidate_decisions'], [])
        self.assertEqual(len(contract['final_results']), 6)
        self.assertTrue(all(result['status'] == 'not_run' for result in contract['final_results'][1:]))
        self.assertEqual(contract['cost']['generation_calls'], 0)
        self.assertEqual(contract['cost']['candidate_rechecks'], 0)
        self.assertIsNone(contract['cost']['elapsed_seconds'])
        self.assertIsNone(contract['cost']['manual_seconds'])
        refs = {item['path'] for item in report['contract_projection']['evidence_index']}
        self.assertEqual(set(evaluation['evidence_refs']), refs)
        self.assertEqual(len(refs), 4)  # Actual source plus request, SSM, receipt.

    def test_received_receipt_maps_source_evidence_without_graph_completion_claim(self):
        key = self.execute(interrupt_after=['extract_ssm'])['extraction_id']
        report = self.ledger.report(key)
        self.assertEqual(report['status'], 'received')
        self.assertEqual(report['contract_evaluation']['status'], 'pass')
        self.assertEqual(report['contract_report']['status'], 'not_run')

    def test_review_keeps_known_source_result_but_blocks_overall_report(self):
        key = self.execute(interrupt_after=['extract_ssm'])['extraction_id']
        self.ledger.review(key, 'controlled_review')
        report = self.ledger.report(key)
        self.assertEqual(report['contract_evaluation']['status'], 'pass')
        self.assertEqual(report['contract_report']['status'], 'blocked')
        self.assertEqual(report['contract_report']['attempt_results'][0]['dimension'], 'extraction_execution')

    def test_failure_origins_and_statuses_never_authorize_target_repair(self):
        cases = [('ssm_script_syntax_error', 'fail', 'source', 'blocked'),
                 ('ssm_script_setup_not_supported', 'unsupported', 'source', 'blocked'),
                 ('ssm_node_missing', 'execution_error', 'infrastructure', 'execution_error'),
                 ('ssm_output_shape_invalid', 'blocked', 'evidence', 'blocked'),
                 ('ssm_future_error', 'unknown', 'unknown', 'blocked')]
        for code, status, origin, overall in cases:
            with self.subTest(code=code):
                with patch.object(SSMExtractor, 'extract', side_effect=ExtractionError(code)):
                    key = self.execute()['extraction_id']
                report = self.ledger.report(key)
                evaluation = report['contract_evaluation']
                self.assertEqual(evaluation['status'], status)
                self.assertEqual(report['contract_report']['status'], overall)
                diagnostic = evaluation['diagnostics'][0]
                self.assertEqual(diagnostic['origin'], origin)
                self.assertTrue(diagnostic['blocking'])
                self.assertEqual(diagnostic['repairability'], 'not_repairable')
                self.assertEqual(report['contract_report']['repair_decisions'], [])

    def test_contracts_roundtrip_through_pinned_p1_loader(self):
        report = self.ledger.report(self.execute()['extraction_id'])
        for field in ('contract_report', 'contract_evaluation'):
            wire = json.loads(json.dumps(report[field]))
            self.assertEqual(self.service.binding.contracts.load_contract(wire).to_dict(), wire)

    def test_missing_new_snapshot_cannot_hide_mapping(self):
        key = self.ledger.create(run_id=self.run_id)
        self.mutate_request(key, lambda request: request.pop('contract_snapshot'))
        with self.assertRaisesRegex(ServiceError, 'ssm_contract_projection_invalid'):
            self.ledger.report(key)

    def test_bool_integer_snapshot_change_is_rejected_even_with_new_outer_hash(self):
        key = self.ledger.create(run_id=self.run_id)
        def corrupt(request):
            request['contract_snapshot']['request']['budget']['max_model_repair_calls'] = False
        self.mutate_request(key, corrupt)
        with self.assertRaisesRegex(ServiceError, 'ssm_contract_projection_invalid'):
            self.ledger.report(key)

    def test_snapshot_source_cannot_be_redirected(self):
        key = self.ledger.create(run_id=self.run_id)
        def corrupt(request):
            request['contract_snapshot']['request']['source']['path'] = '../other.vue'
        self.mutate_request(key, corrupt)
        with self.assertRaisesRegex(ServiceError, 'ssm_contract_projection_invalid'):
            self.ledger.report(key)

    def test_extra_permission_fields_are_not_ignored(self):
        key = self.ledger.create(run_id=self.run_id)
        self.mutate_request(key, lambda request: request.update(external_calls_permitted=True))
        with self.assertRaisesRegex(ServiceError, 'ssm_contract_projection_invalid'):
            self.ledger.report(key)

    def test_missing_ssm_dimension_is_not_a_source_pass(self):
        key = self.execute()['extraction_id']
        self.corrupt_registered_json(key, 'ssm', lambda ssm: ssm.pop('template'))
        with transaction(self.service.engine) as session:
            value = session.get(SSMExtractionFile, f'ssm-extractions/{key}/ssm.json').sha256
        self.corrupt_registered_json(key, 'receipt', lambda receipt: receipt.update(ssm_sha256=value))
        with self.assertRaises(ServiceError):
            self.ledger.report(key)

    def test_missing_runtime_binding_is_not_a_static_source_pass(self):
        key = self.execute()['extraction_id']
        def corrupt(receipt):
            receipt['binding'].pop('runtime')
            receipt['binding_sha256'] = digest(receipt['binding'])
        self.corrupt_registered_json(key, 'receipt', corrupt)
        with self.assertRaisesRegex(ServiceError, 'ssm_contract_projection_invalid'):
            self.ledger.report(key)

    def test_historical_record_gets_evaluation_only_without_request_backfill(self):
        key = self.ledger.create(run_id=self.run_id)
        self.legacy(key)
        execute_extraction(self.service, extraction_id=key)
        before = self.ledger.snapshot(key)
        request_bytes = self.file(key, 'request').read_bytes()
        report = self.ledger.report(key)
        self.assertEqual(report['contract_evaluation']['status'], 'pass')
        self.assertIsNone(report['contract_report'])
        self.assertEqual(report['contract_projection']['status'], 'partial_evaluation_only')
        self.assertNotIn('contract_snapshot', self.ledger.snapshot(key)['request'])
        self.assertEqual(self.ledger.snapshot(key), before)
        self.assertEqual(self.file(key, 'request').read_bytes(), request_bytes)

    def test_injecting_snapshot_into_old_protocol_is_not_backfill(self):
        key = self.ledger.create(run_id=self.run_id)
        self.mutate_request(key, lambda request: request.update(protocol='registered-ssm-graph-v1'))
        with self.assertRaisesRegex(ServiceError, 'ssm_contract_projection_invalid'):
            self.ledger.report(key)

    def test_policy_change_does_not_reinterpret_a_frozen_request(self):
        key = self.ledger.create(run_id=self.run_id)
        with patch('card_migration_system.reporting.extraction_projection.PROJECTOR', 'different-policy'):
            with self.assertRaisesRegex(ServiceError, 'ssm_contract_projection_invalid'):
                self.ledger.report(key)

    def test_invalid_contract_snapshot_prevents_backup(self):
        key = self.execute()['extraction_id']
        self.mutate_request(key, lambda request: request.pop('contract_snapshot'))
        # Outer receipt request pointer is now intentionally stale too; no export may conceal either error.
        with self.assertRaises(ServiceError):
            create_backup(self.settings, backup_id='invalid-contract')

    def test_one_read_snapshot_and_no_parser_on_report(self):
        key = self.execute()['extraction_id']
        with patch.object(self.ledger, 'snapshot', wraps=self.ledger.snapshot) as read:
            with patch.object(SSMExtractor, 'extract', side_effect=AssertionError('read only')):
                self.ledger.report(key)
        self.assertEqual(read.call_count, 1)

    def test_cli_read_report_exposes_contract_values_without_new_execution(self):
        key = self.execute()['extraction_id']
        output = io.StringIO()
        with patch('card_migration_system.interfaces.cli.load_settings', return_value=self.settings), redirect_stdout(output):
            with patch.object(SSMExtractor, 'extract', side_effect=AssertionError('no parser')):
                self.assertEqual(main(['ssm-extraction-report', '--extraction-id', key]), 0)
        self.assertEqual(json.loads(output.getvalue())['contract_report']['status'], 'not_run')


if __name__ == '__main__':
    unittest.main()
