"""Workbench read pagination/static security. Disposable DB, never migration evidence."""
import base64
import unittest

import test_vertical_slice as fixtures
from card_migration_system.application.service import ServiceError
from card_migration_system.persistence.database import transaction
from card_migration_system.persistence.schema_v1 import Run


class WorkbenchApiTests(unittest.TestCase):
    setUp = fixtures.VerticalSliceTests.setUp
    enqueue = fixtures.VerticalSliceTests.enqueue
    app = fixtures.VerticalSliceTests.app

    def test_run_page_order_cursor_and_status_filter(self):
        identifiers = [self.enqueue()[0] for _ in range(4)]
        self.service.cancel(identifiers[1])
        first = self.service.list_runs(limit=2)
        second = self.service.list_runs(limit=2, before=first["next_cursor"])
        self.assertEqual([item["run_id"] for item in first["items"] + second["items"]], list(reversed(identifiers)))
        self.assertIsNone(second["next_cursor"])
        filtered = self.service.list_runs(status="cancelled")
        self.assertEqual([item["run_id"] for item in filtered["items"]], [identifiers[1]])
        self.assertTrue(all(not item["production_ready"] and item["outcome"] == "not_run" for item in first["items"]))

    def test_cursor_tie_uses_id_without_duplicates(self):
        identifiers = [self.enqueue()[0] for _ in range(3)]
        with transaction(self.service.engine) as session:
            for identifier in identifiers:
                session.get(Run, identifier).created_at = 12345.0
        found, cursor = [], None
        for _ in range(3):
            page = self.service.list_runs(limit=1, before=cursor)
            found.extend(item["run_id"] for item in page["items"])
            cursor = page["next_cursor"]
        self.assertEqual(found, sorted(identifiers, reverse=True))
        self.assertIsNone(cursor)

    def test_invalid_page_filter_and_cursor_rejected(self):
        for value in (True, 0, 51, "10"):
            with self.subTest(limit=value), self.assertRaises(ServiceError):
                self.service.list_runs(limit=value)
        for status in ("pass", "unknown", "finished;drop"):
            with self.subTest(status=status), self.assertRaises(ServiceError):
                self.service.list_runs(status=status)
        for value in ("../outside", "=", "a" * 161, base64.urlsafe_b64encode(b'[true,"id"]').decode().rstrip('=')):
            with self.subTest(cursor=value), self.assertRaises(ServiceError):
                self.service.list_runs(before=value)

    def test_run_page_queries_are_read_only(self):
        run_id, _ = self.enqueue()
        before = self.service.report(run_id)
        for _ in range(3):
            self.service.list_runs()
        self.assertEqual(self.service.report(run_id), before)

    def test_http_page_and_invalid_query(self):
        self.enqueue()
        client = self.app().test_client()
        response = client.get('/api/v1/runs?limit=1&status=queued', base_url=fixtures.BASE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["items"]), 1)
        self.assertEqual(client.get('/api/v1/runs?limit=999', base_url=fixtures.BASE).status_code, 400)
        self.assertEqual(client.get('/api/v1/runs?status=pass', base_url=fixtures.BASE).status_code, 400)

    def test_root_missing_build_is_explicit_not_fake_ready(self):
        response = self.app().test_client().get('/', base_url=fixtures.BASE)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["error"]["code"], "frontend_not_built")

    def test_compiled_root_csp_same_origin_and_no_source_tree_fallback(self):
        target = self.project / 'frontend/dist'
        (target / 'assets').mkdir(parents=True)
        (target / 'index.html').write_text('<!doctype html><div id="app"></div>', encoding='utf-8')
        (target / 'assets/app.js').write_text('console.log("fixture")', encoding='utf-8')
        client = self.app().test_client()
        root = client.get('/', base_url=fixtures.BASE)
        self.assertEqual(root.status_code, 200)
        self.assertIn("script-src 'self'", root.headers['Content-Security-Policy'])
        self.assertIn("frame-ancestors 'none'", root.headers['Content-Security-Policy'])
        self.assertEqual(root.headers['Cache-Control'], 'no-store')
        root.close()
        asset = client.get('/assets/app.js', base_url=fixtures.BASE)
        self.assertEqual(asset.status_code, 200)
        asset.close()
        for path in ('/src/App.vue', '/.env', '/api/v1/not-a-route', '/assets/../index.html'):
            response = client.get(path, base_url=fixtures.BASE)
            self.assertEqual(response.status_code, 404)
            self.assertIsNone(response.headers.get('Access-Control-Allow-Origin'))

    def test_frontend_and_list_keep_host_origin_guards(self):
        client = self.app().test_client()
        for path in ('/', '/api/v1/runs'):
            self.assertEqual(client.get(path, base_url='http://evil.example:8790').status_code, 403)
            self.assertEqual(client.get(path, base_url=fixtures.BASE, headers={'Origin': 'https://evil.example'}).status_code, 403)


if __name__ == '__main__':
    unittest.main()
