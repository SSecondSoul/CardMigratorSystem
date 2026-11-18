"""Local browser auth boundaries; temporary SQLite only, no model calls."""
import time
import os
import unittest
from unittest.mock import patch

import test_vertical_slice as fixtures


class BrowserSessionTests(unittest.TestCase):
    setUp = fixtures.VerticalSliceTests.setUp
    app = fixtures.VerticalSliceTests.app
    bootstrap_headers = {"X-Cardmig-Session": "bootstrap", "Sec-Fetch-Site": "same-origin"}
    body = {"filename": "Card.vue", "source": "<template><p>Local test</p></template>"}

    def bootstrap(self, client):
        return client.get('/api/v1/browser-session', base_url=fixtures.BASE, headers=self.bootstrap_headers)

    def write(self, client, **headers):
        return client.post('/api/v1/inputs', base_url=fixtures.BASE, json=self.body, headers=headers)

    def test_bootstrap_cookie_is_http_only_strict_and_contains_no_script_token(self):
        client = self.app().test_client()
        response = self.bootstrap(client)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['csrf_token']), 43)
        self.assertEqual(response.json['expires_in'], 28800)
        cookie = response.headers['Set-Cookie']
        for required in ('HttpOnly', 'SameSite=Strict', 'Path=/api/v1', 'Max-Age=28800'):
            self.assertIn(required, cookie)
        self.assertNotIn(fixtures.TOKEN, cookie + response.get_data(as_text=True))
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(self.bootstrap(client).json['csrf_token'], response.json['csrf_token'])

    def test_session_and_csrf_are_both_required_for_writes(self):
        app = self.app();client = app.test_client()
        csrf = self.bootstrap(client).json['csrf_token']
        self.assertEqual(self.write(client).status_code, 403)
        self.assertEqual(self.write(client, **{'X-Cardmig-CSRF': 'wrong'}).json['error']['code'], 'browser_csrf_required')
        self.assertEqual(self.write(app.test_client(), **{'X-Cardmig-CSRF': csrf}).json['error']['code'], 'browser_session_required')
        self.assertEqual(self.write(client, **{'X-Cardmig-CSRF': csrf}).status_code, 201)

    def test_cross_origin_navigation_and_preflight_cannot_bootstrap(self):
        client = self.app().test_client()
        for headers in ({}, {'X-Cardmig-Session': 'bootstrap', 'Origin': 'https://foreign.example'},
                        {'X-Cardmig-Session': 'bootstrap', 'Sec-Fetch-Site': 'cross-site'},
                        {'X-Cardmig-Session': 'bootstrap', 'Sec-Fetch-Site': 'same-site'}):
            response = client.get('/api/v1/browser-session', base_url=fixtures.BASE, headers=headers)
            self.assertEqual(response.status_code, 403)
            self.assertNotIn('Set-Cookie', response.headers)
            self.assertNotIn('Access-Control-Allow-Origin', response.headers)
        response = client.options('/api/v1/browser-session', base_url=fixtures.BASE,
                                  headers={'Origin': 'https://foreign.example', 'Access-Control-Request-Headers': 'X-Cardmig-Session'})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('Access-Control-Allow-Origin', response.headers)

    def test_foreign_writes_fail_even_with_valid_credentials(self):
        client = self.app().test_client();csrf = self.bootstrap(client).json['csrf_token']
        for extra in ({'Origin': 'https://foreign.example'}, {'Sec-Fetch-Site': 'cross-site'}, {'Sec-Fetch-Site': 'same-site'}):
            self.assertEqual(self.write(client, **{'X-Cardmig-CSRF': csrf, **extra}).status_code, 403)

    def test_clients_are_isolated_and_cookie_tampering_fails(self):
        app = self.app();first = app.test_client();second = app.test_client()
        csrf = self.bootstrap(first).json['csrf_token'];other = self.bootstrap(second).json['csrf_token']
        self.assertNotEqual(csrf, other)
        self.assertEqual(self.write(second, **{'X-Cardmig-CSRF': csrf}).status_code, 403)
        first.set_cookie('cardmig_session_8790', 'tampered', domain='127.0.0.1', path='/api/v1')
        self.assertEqual(self.write(first, **{'X-Cardmig-CSRF': csrf}).status_code, 403)

    def test_expired_session_is_rejected_then_can_be_reestablished(self):
        client = self.app().test_client()
        with patch('itsdangerous.timed.TimestampSigner.get_timestamp', return_value=int(time.time()) - 30000):
            csrf = self.bootstrap(client).json['csrf_token']
        self.assertEqual(self.write(client, **{'X-Cardmig-CSRF': csrf}).json['error']['code'], 'browser_session_required')
        fresh = self.bootstrap(client).json['csrf_token']
        self.assertNotEqual(csrf, fresh)
        self.assertEqual(self.write(client, **{'X-Cardmig-CSRF': fresh}).status_code, 201)

    def test_restart_and_other_port_invalidate_session(self):
        app = self.app();client = app.test_client();csrf = self.bootstrap(client).json['csrf_token']
        cookie = client.get_cookie('cardmig_session_8790', domain='127.0.0.1', path='/api/v1').value
        restarted = self.app().test_client()
        restarted.set_cookie('cardmig_session_8790', cookie, domain='127.0.0.1', path='/api/v1')
        self.assertEqual(self.write(restarted, **{'X-Cardmig-CSRF': csrf}).status_code, 403)
        app.config['ALLOWED_PORT'] = 8791
        client.set_cookie('cardmig_session_8791', cookie, domain='127.0.0.1', path='/api/v1')
        response = client.post('/api/v1/inputs', base_url='http://127.0.0.1:8791', json=self.body, headers={'X-Cardmig-CSRF': csrf})
        self.assertEqual(response.status_code, 403)

    def test_script_token_remains_supported_and_invalid_explicit_token_does_not_fallback(self):
        client = self.app().test_client()
        self.assertEqual(self.write(client, **{'X-Cardmig-Token': fixtures.TOKEN}).status_code, 201)
        csrf = self.bootstrap(client).json['csrf_token']
        self.assertEqual(self.write(client, **{'X-Cardmig-Token': 'wrong', 'X-Cardmig-CSRF': csrf}).status_code, 403)
        self.assertEqual(client.get('/api/v1/runs', base_url=fixtures.BASE).status_code, 200)

    def test_serve_generates_internal_token_when_unset_and_preserves_explicit_script_token(self):
        from card_migration_system.interfaces.cli import main
        from card_migration_system.interfaces.api.app import create_app
        for supplied in ('', fixtures.TOKEN):
            with patch.dict(os.environ, {'CARDMIG_SYSTEM_WRITE_TOKEN': supplied}), \
                    patch('werkzeug.serving.make_server') as server, \
                    patch('card_migration_system.interfaces.api.app.create_app', wraps=create_app) as factory:
                self.assertEqual(main(['serve', '--project-root', str(self.project)]), 0)
                value = factory.call_args.kwargs['write_token']
                self.assertGreaterEqual(len(value), 24)
                if supplied:
                    self.assertEqual(value, supplied)
                server.return_value.__enter__.return_value.serve_forever.assert_called_once()


if __name__ == '__main__':
    unittest.main()
