"""Local approval/budget evidence only; never provider network or real permissions."""
from contextlib import closing, redirect_stdout
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import sqlite3
import unittest
from unittest.mock import patch

import test_generation_boundary as fixtures
from card_migration_system.adapters.qwen_transport import ENDPOINT, QwenHTTPSClient
from card_migration_system.adapters.token_budget import budget_review, build_budget_plan
from card_migration_system.application.generation_approvals import GenerationApprovalService, ClaimedApproval, path_for
from card_migration_system.application.service import Service, ServiceError
from card_migration_system.interfaces.cli import main
from card_migration_system.persistence.backup import create_backup, verify_backup, restore_backup
from card_migration_system.persistence.database import initialize, engine_for, transaction, HEAD
from card_migration_system.persistence.generation_approvals import GenerationApproval as Approval, GenerationApprovalFile as File, metadata
from card_migration_system.reporting.identity import digest


NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc).timestamp()
RESERVATION = 1008192


class TokenBudgetTests(unittest.TestCase):
    setUp = fixtures.GenerationBoundaryTests.setUp
    prepare = fixtures.GenerationBoundaryTests.prepare

    def test_default_budget_is_not_silently_increased_and_exact_usage_is_unknown(self):
        prepared = self.prepare()
        plan, result = budget_review(prepared, endpoint=ENDPOINT, now=NOW)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['configured_max_total_tokens'], 32768)
        self.assertEqual(result['required_total_reservation'], RESERVATION)
        self.assertEqual(plan.bound.count, 1000000)
        self.assertIsNone(result['input_tokens_exact'])
        self.assertEqual(result['actual_model_calls'], 0)
        self.assertFalse(result['production_ready'])

    def test_explicit_large_reservation_fits_but_does_not_approve_call(self):
        plan, result = budget_review(self.prepare(max_total_tokens=RESERVATION), endpoint=ENDPOINT, now=NOW)
        self.assertEqual(result['status'], 'reservation_fits_not_call_approved')
        plan.preflight()
        self.assertEqual(plan.bound.method, 'upper_bound')
        self.assertTrue(plan.bound.includes_chat_wrapper)
        self.assertTrue(result['assumptions'])

    def test_unreviewed_model_output_cap_and_catalog_expiry_fail_closed(self):
        for kwargs, at in (({'model': 'qwen-plus-2099-01-01'}, NOW),
                           ({'max_output_tokens': 65536}, NOW), ({}, NOW + 8 * 86400), ({}, NOW - 86400)):
            with self.assertRaises(ValueError):
                build_budget_plan(self.prepare(**kwargs), endpoint=ENDPOINT, now=at)

    def test_model_and_messages_are_bound_to_policy_not_caller_count(self):
        prepared = self.prepare(model='qwen-plus-2025-07-28', max_total_tokens=RESERVATION)
        plan = build_budget_plan(prepared, endpoint=ENDPOINT, now=NOW)
        self.assertEqual(plan.bound.model, 'qwen-plus-2025-07-28')
        self.assertEqual(plan.bound.messages_sha256, prepared.payload()['prompt']['messages_sha256'])
        with self.assertRaises(TypeError):
            build_budget_plan(prepared, endpoint=ENDPOINT, now=NOW, count=1)


class GenerationApprovalTests(unittest.TestCase):
    execute = fixtures.RegisteredPreviewTests.execute

    def setUp(self):
        fixtures.RegisteredPreviewTests.setUp(self)
        self.extraction_id = self.execute()['extraction_id']
        self.now = NOW
        self.approvals = GenerationApprovalService(self.service, clock=lambda: self.now)

    def create(self, key='one', **options):
        return self.approvals.create(self.extraction_id, key, **{'provider': 'qwen', 'model': 'qwen-plus',
            'max_total_tokens': RESERVATION, **options})

    def approve(self, key, **overrides):
        report = self.approvals.report(key)
        return self.approvals.approve(key, **{'expected_request_sha256': report['request_sha256'],
            'confirm_single_call': True, **overrides})

    def test_preview_is_read_only_and_blocked_default_budget_has_no_rows(self):
        before = self.ledger.report(self.extraction_id)
        review = self.approvals.preview(self.extraction_id, provider='qwen', model='qwen-plus')
        self.assertEqual(review['status'], 'blocked')
        self.assertFalse(review['persistent_registration'])
        with self.assertRaises(ValueError): self.create(max_total_tokens=32768)
        with transaction(self.service.engine) as session:
            from sqlalchemy import select
            self.assertEqual(list(session.scalars(select(Approval.id))), [])
        self.assertEqual(self.ledger.report(self.extraction_id), before)

    def test_create_is_pending_idempotent_and_binds_full_request(self):
        key = self.create()
        self.assertEqual(self.create(), key)
        report = self.approvals.report(key)
        self.assertEqual(report['status'], 'pending')
        self.assertEqual(report['request']['intent']['max_calls'], 1)
        self.assertFalse(report['dispatch_enabled'])
        self.assertEqual(report['actual_model_calls'], 0)
        self.assertIsNone(report['usage'])
        self.assertTrue(report['request']['intent']['prepared']['prompt']['messages'])
        with self.assertRaisesRegex(ServiceError, 'idempotency_conflict'):
            self.create(timeout_seconds=120)

    def test_approve_requires_exact_request_hash_and_explicit_boolean(self):
        key = self.create()
        for changes in ({'expected_request_sha256': '0' * 64}, {'confirm_single_call': False}, {'confirm_single_call': 1}):
            with self.assertRaises(ServiceError): self.approve(key, **changes)
        self.assertEqual(self.approvals.report(key)['status'], 'pending')
        approved = self.approve(key)
        self.assertEqual(approved['status'], 'approved')
        self.assertEqual(self.approve(key), approved)
        self.assertEqual({f['kind'] for f in approved['files']}, {'request', 'approval'})

    def test_claim_cannot_happen_before_approval_or_for_another_plan(self):
        key = self.create()
        plan = self.approvals.report(key)['plan_sha256']
        with self.assertRaisesRegex(ServiceError, 'not_available'):
            self.approvals.claim(key, expected_plan_sha256=plan)
        self.approve(key)
        with self.assertRaisesRegex(ServiceError, 'expected_plan_mismatch'):
            self.approvals.claim(key, expected_plan_sha256='0' * 64)
        self.assertEqual(self.approvals.report(key)['slots_reserved'], 0)

    def test_consumption_is_once_and_is_not_a_transport_start_permit(self):
        key = self.create()
        report = self.approve(key)
        claimed = self.approvals.claim(key, expected_plan_sha256=report['plan_sha256'])
        self.assertIs(type(claimed), ClaimedApproval)
        report = self.approvals.report(key)
        self.assertEqual(report['status'], 'consumed')
        self.assertEqual(report['slots_reserved'], 1)
        self.assertIsNone(report['actual_model_calls'])
        with self.assertRaisesRegex(ServiceError, 'not_available'):
            self.approvals.claim(key, expected_plan_sha256=report['plan_sha256'])
        with self.assertRaisesRegex(ValueError, 'call_permit_required'):
            QwenHTTPSClient('not-a-real-key', network_enabled=True).send(None, claimed)

    def test_expiry_does_not_silently_renew_same_key(self):
        key = self.create(expires_in=60)
        self.now += 60
        self.assertTrue(self.approvals.report(key)['expired'])
        self.assertEqual(self.create(expires_in=60), key)
        with self.assertRaisesRegex(ServiceError, 'expired'): self.approve(key)

    def test_expiry_between_verification_and_action_does_not_commit_approval(self):
        key = self.create(expires_in=60)
        original = self.approvals._action
        def late(*args):
            self.now += 61
            return original(*args)
        with patch.object(self.approvals, '_action', side_effect=late), self.assertRaisesRegex(ServiceError, 'expired'):
            self.approve(key)
        self.assertEqual(self.approvals.report(key)['status'], 'pending')

    def test_approved_expired_grant_cannot_be_consumed(self):
        key = self.create(expires_in=60)
        report = self.approve(key)
        self.now += 61
        with self.assertRaisesRegex(ServiceError, 'expired'):
            self.approvals.claim(key, expected_plan_sha256=report['plan_sha256'])

    def test_unconsumed_can_be_revoked_after_expiry_but_consumed_cannot(self):
        key = self.create(expires_in=60)
        report = self.approve(key)
        self.now += 61
        revoked = self.approvals.revoke(key, expected_request_sha256=report['request_sha256'])
        self.assertEqual(revoked['status'], 'revoked')
        self.assertEqual(self.approvals.revoke(key, expected_request_sha256=report['request_sha256']), revoked)
        other = self.create('other')
        approved = self.approve(other)
        self.approvals.claim(other, expected_plan_sha256=approved['plan_sha256'])
        with self.assertRaisesRegex(ServiceError, 'already_consumed'):
            self.approvals.revoke(other, expected_request_sha256=approved['request_sha256'])

    def test_implementation_drift_blocks_approval_without_rewriting_history(self):
        key = self.create()
        before = self.approvals.report(key)
        altered = {**self.service.implementation_binding(), 'implementation_sha256': '0' * 64}
        with patch.object(self.service, 'implementation_binding', return_value=altered):
            with self.assertRaisesRegex(ServiceError, 'binding_drift'): self.approve(key)
            self.assertEqual(self.approvals.report(key), before)

    def test_concurrent_claims_reserve_one_slot_only(self):
        key = self.create()
        report = self.approve(key)
        def claim(_):
            try:
                return self.approvals.claim(key, expected_plan_sha256=report['plan_sha256'])
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(claim, range(3)))
        self.assertEqual(sum(type(value) is ClaimedApproval for value in results), 1)
        self.assertEqual(self.approvals.report(key)['slots_reserved'], 1)

    def test_request_rehashed_at_all_outer_layers_cannot_change_policy_or_call_count(self):
        for mutation in (lambda i: i.update(max_calls=True), lambda i: i.update(dispatch_enabled=True),
                         lambda i: i['policy'].update(context_window=1)):
            key = self.create(str(id(mutation)))
            path = self.settings.artifact_dir / path_for(key, 'request')
            value = json.loads(path.read_bytes())
            mutation(value['intent'])
            raw = json.dumps(value).encode()
            path.write_bytes(raw)
            with transaction(self.service.engine) as session:
                row = session.get(Approval, key)
                row.request, row.request_sha256 = value, digest(value)
                session.get(File, path_for(key, 'request')).sha256 = sha256(raw).hexdigest()
            with self.assertRaises(ValueError): self.approvals.report(key)

    def test_revoke_requires_expected_fingerprint_and_wrong_grant_never_approves(self):
        key = self.create()
        with self.assertRaisesRegex(ServiceError, 'expected_request_mismatch'):
            self.approvals.revoke(key, expected_request_sha256='0' * 64)
        report = self.approvals.report(key)
        self.approvals.revoke(key, expected_request_sha256=report['request_sha256'])
        with self.assertRaisesRegex(ServiceError, 'not_pending'): self.approve(key)

    def test_cli_prepare_approve_and_report_still_never_dispatch(self):
        actual = GenerationApprovalService
        def run(args):
            output = io.StringIO()
            with patch('card_migration_system.interfaces.cli.load_settings', return_value=self.settings), \
                    patch('card_migration_system.application.generation_approvals.GenerationApprovalService', side_effect=lambda s: actual(s, clock=lambda: self.now)), \
                    patch('socket.socket.connect', side_effect=AssertionError('no network')), redirect_stdout(output):
                self.assertEqual(main(args), 0)
            return json.loads(output.getvalue())
        created = run(['prepare-generation-approval', '--extraction-id', self.extraction_id, '--provider', 'qwen',
            '--model', 'qwen-plus', '--max-total-tokens', str(RESERVATION), '--idempotency-key', 'cli-approved'])
        self.assertEqual(created['status'], 'pending')
        self.assertNotIn('request', created)
        approved = run(['approve-generation-plan', '--approval-id', created['id'], '--expected-request-sha256',
            created['request_sha256'], '--confirm-single-call'])
        self.assertEqual(approved['status'], 'approved')
        self.assertFalse(approved['dispatch_enabled'])
        self.assertEqual(approved['actual_model_calls'], 0)
        self.assertEqual(run(['generation-approval-report', '--approval-id', created['id']])['status'], 'approved')

    def test_rehashed_wrong_identity_boolean_calls_or_action_time_are_rejected(self):
        for change in (lambda v: v.update(approval_id='0' * 32), lambda v: v.update(plan_sha256='0' * 64),
                       lambda v: v.update(at=True), lambda v: v.update(request_sha256='0' * 64)):
            key = self.create(str(id(change)))
            self.approve(key)
            path = self.settings.artifact_dir / path_for(key, 'approval')
            value = json.loads(path.read_bytes())
            change(value)
            raw = json.dumps(value).encode()
            path.write_bytes(raw)  # Disposable corruption test only.
            with transaction(self.service.engine) as session:
                session.get(File, path_for(key, 'approval')).sha256 = sha256(raw).hexdigest()
            with self.assertRaises(ValueError): self.approvals.report(key)

    def test_backup_restore_keeps_consumed_slot_and_does_not_dispatch(self):
        key = self.create()
        report = self.approve(key)
        self.approvals.claim(key, expected_plan_sha256=report['plan_sha256'])
        create_backup(self.settings, backup_id='approved-slot')
        self.assertEqual(verify_backup(self.settings, 'approved-slot')['status'], 'backup_verified')
        settings = replace(self.settings, runtime_dir=self.project / 'var/approval-restored',
            artifact_dir=self.settings.artifact_dir / 'approval-restored')
        restore_backup(settings, 'approved-slot')
        restored = Service(settings)
        self.addCleanup(restored.close)
        approvals = GenerationApprovalService(restored, clock=lambda: self.now)
        self.assertEqual(approvals.report(key), self.approvals.report(key))
        with self.assertRaisesRegex(ServiceError, 'not_available'):
            approvals.claim(key, expected_plan_sha256=report['plan_sha256'])

    def test_cli_budget_review_does_not_print_full_messages_or_source(self):
        output = io.StringIO()
        actual = GenerationApprovalService
        with patch('card_migration_system.interfaces.cli.load_settings', return_value=self.settings), \
                patch('card_migration_system.application.generation_approvals.GenerationApprovalService', side_effect=lambda s: actual(s, clock=lambda: self.now)), \
                redirect_stdout(output):
            code = main(['generation-budget-review', '--extraction-id', self.extraction_id, '--provider', 'qwen', '--model', 'qwen-plus'])
        self.assertEqual(code, 2)  # Expected budget block, not a model execution error.
        result = json.loads(output.getvalue())
        self.assertEqual(result['required_total_reservation'], RESERVATION)
        self.assertNotIn('messages', result)
        self.assertNotIn('source_code', result)
        self.assertFalse(result['persistent_registration'])

    def test_upgrade_0005_preserves_ssm_and_recorded_exchange_request(self):
        from card_migration_system.application.provider_generations import ProviderGenerationService
        from test_provider_generation_ledger import ProviderLedgerTests
        # Reuse only its explicit temporary-source creation helper, not test methods.
        self.provider = ProviderGenerationService(self.service)
        key = ProviderLedgerTests.create(self, 'before-0006')
        before = self.provider.report(key)
        self.service.close()
        engine = engine_for(self.settings.business_database)
        try:
            with engine.begin() as connection:
                # Reconstruct the historical schema in this disposable fixture:
                # 0007 tables must not survive a forged 0005 version marker.
                from card_migration_system.persistence.migrations import metadata as migration_metadata
                migration_metadata.drop_all(connection)
                metadata.drop_all(connection)
                connection.exec_driver_sql("UPDATE alembic_version SET version_num='0005_provider_generation'")
        finally:
            engine.dispose()
        initialize(self.settings)
        self.service = Service(self.settings)
        self.addCleanup(self.service.close)
        self.assertEqual(ProviderGenerationService(self.service).report(key), before)
        with closing(sqlite3.connect(self.settings.business_database)) as connection:
            self.assertEqual(connection.execute('SELECT version_num FROM alembic_version').fetchone()[0], HEAD)
