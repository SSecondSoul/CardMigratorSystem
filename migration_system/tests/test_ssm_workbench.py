"""Read-only source evidence workbench; all records live in a temporary tree."""
import base64
import json
import unittest
from unittest.mock import patch

import test_registered_ssm_graph as fixtures
import test_vertical_slice
from card_migration_system.adapters.ssm import SSMExtractor
from card_migration_system.application.service import ServiceError
from card_migration_system.interfaces.api.app import create_app
from card_migration_system.persistence.database import transaction
from card_migration_system.persistence.ssm_extractions import SSMExtraction


class SsmWorkbenchTests(unittest.TestCase):
    setUp = fixtures.RegisteredGraphTests.setUp
    execute = fixtures.RegisteredGraphTests.execute
    file = fixtures.RegisteredGraphTests.file

    def client(self):
        app = create_app(self.settings, write_token='temporary-read-only-test-token')
        self.addCleanup(app.extensions['migration_service'].close)
        return app.test_client()

    def test_empty_list_is_not_a_successful_extraction(self):
        result = self.ledger.list_records()
        self.assertEqual(result['items'], [])
        self.assertIsNone(result['next_cursor'])
        self.assertEqual(result['evidence_audit'], 'not_performed_in_list')
        self.assertFalse(result['production_ready'])

    def test_pagination_tied_timestamp_no_duplicates_or_fake_quality(self):
        keys = [self.ledger.create(run_id=self.run_id) for _ in range(4)]
        with transaction(self.service.engine) as session:
            for key in keys:
                session.get(SSMExtraction, key).created_at = 100.0
        first = self.ledger.list_records(limit=2)
        second = self.ledger.list_records(limit=2, before=first['next_cursor'])
        self.assertEqual([item['extraction_id'] for item in first['items'] + second['items']], sorted(keys, reverse=True))
        self.assertIsNone(second['next_cursor'])
        for item in first['items']:
            self.assertEqual(item['status'], 'prepared')
            self.assertEqual(item['filename'], 'Counter.vue')
            self.assertEqual(item['referenced_run_id'], self.run_id)
            self.assertNotIn('contract_evaluation', item)
            self.assertNotIn('request', item)

    def test_invalid_limits_and_cursor_types_are_rejected(self):
        for limit in (True, 0, 51, '10'):
            with self.subTest(limit=limit), self.assertRaises(ServiceError):
                self.ledger.list_records(limit=limit)
        bad_values = ['../outside', '=', 'a' * 161, '']
        for value in ([True, 'a' * 32], [-1, 'a' * 32], [float('inf'), 'a' * 32],
                      [1, '../outside'], [1], {'unexpected': 'object'}):
            bad_values.append(base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('='))
        for cursor in bad_values:
            with self.subTest(cursor=cursor), self.assertRaisesRegex(ServiceError, 'invalid_ssm_cursor'):
                self.ledger.list_records(before=cursor)

    def test_http_list_needs_no_token_and_never_invokes_parser(self):
        key = self.ledger.create(input_id=self.source['input_id'])
        before = self.ledger.report(key)
        fixture_before = self.service.report(self.run_id)
        with patch.object(SSMExtractor, 'extract', side_effect=AssertionError('read-only')):
            client = self.client()
            for _ in range(2):
                response = client.get('/api/v1/ssm-extractions?limit=1', base_url=test_vertical_slice.BASE)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['items'][0]['extraction_id'], key)
                self.assertIsNone(response.json['items'][0]['referenced_run_id'])
                detail = client.get(f'/api/v1/ssm-extractions/{key}/report', base_url=test_vertical_slice.BASE)
                self.assertEqual(detail.status_code, 200)
                self.assertEqual(detail.json['contract_evaluation']['status'], 'not_run')
        self.assertEqual(self.ledger.report(key), before)
        self.assertEqual(self.service.report(self.run_id), fixture_before)

    def test_http_invalid_pages_and_host_origin_stay_rejected(self):
        client = self.client()
        for query in ('limit=0', 'limit=51', 'limit=999', 'limit=true', 'limit=-1', 'before=../outside'):
            self.assertEqual(client.get('/api/v1/ssm-extractions?' + query,
                base_url=test_vertical_slice.BASE).status_code, 400)
        self.assertEqual(client.get('/api/v1/ssm-extractions', base_url='http://evil.example:8790').status_code, 403)
        self.assertEqual(client.get('/api/v1/ssm-extractions', base_url=test_vertical_slice.BASE,
            headers={'Origin': 'http://evil.example'}).status_code, 403)
        self.assertEqual(client.post('/api/v1/ssm-extractions', base_url=test_vertical_slice.BASE).status_code, 403)
        self.assertEqual(client.post('/api/v1/ssm-extractions', base_url=test_vertical_slice.BASE,
            headers={'X-Cardmig-Token': 'temporary-read-only-test-token'}).status_code, 405)

    def test_completed_json_download_does_not_upgrade_fixture_run(self):
        key = self.execute()['extraction_id']
        before = self.ledger.report(key)
        fixture_before = self.service.report(self.run_id)
        with patch.object(SSMExtractor, 'extract', side_effect=AssertionError('no second parse')):
            client = self.client()
            report = client.get(f'/api/v1/ssm-extractions/{key}/report', base_url=test_vertical_slice.BASE)
            artifact = client.get(f'/api/v1/ssm-extractions/{key}/artifact', base_url=test_vertical_slice.BASE)
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.json['contract_evaluation']['status'], 'pass')
        self.assertEqual(report.json['migration_quality_status'], 'not_run')
        self.assertEqual(report.json['actual_model_calls'], 0)
        self.assertEqual(artifact.status_code, 200)
        self.assertEqual(artifact.json['schema_version'], '3.0')
        self.assertIn('attachment;', artifact.headers['Content-Disposition'])
        self.assertEqual(self.ledger.report(key), before)
        self.assertEqual(self.service.report(self.run_id), fixture_before)

    def test_list_does_not_attest_bytes_and_corrupt_detail_download_are_blocked(self):
        key = self.execute()['extraction_id']
        self.file(key, 'ssm').write_bytes(b'{}')  # Disposable evidence corruption.
        client = self.client()
        listing = client.get('/api/v1/ssm-extractions', base_url=test_vertical_slice.BASE)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json['evidence_audit'], 'not_performed_in_list')
        for suffix in ('report', 'artifact'):
            response = client.get(f'/api/v1/ssm-extractions/{key}/{suffix}', base_url=test_vertical_slice.BASE)
            self.assertEqual(response.status_code, 409)
            self.assertIn('error', response.json)
            self.assertNotIn('Content-Disposition', response.headers)
