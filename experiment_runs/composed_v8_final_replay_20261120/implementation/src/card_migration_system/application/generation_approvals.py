"""Auditable local approval of ONE frozen plan; no network, credentials or dispatch.

An approval is not a migration pass. claim reserves the single slot before a
future dispatcher; a consumed record cannot be released or silently reused.
"""
import json
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select

from .generation_preview import prepare_registered_generation
from .generations import require, template_bytes
from .extractions import ExtractionService
from ..adapters.qwen_transport import ENDPOINT
from ..adapters.token_budget import budget_review, build_budget_plan, CATALOG
from ..persistence.database import transaction
from ..persistence.generation_approvals import GenerationApproval as Approval, GenerationApprovalFile as File
from ..persistence.runtime_lock import execution_guard
from ..reporting.identity import digest
from ..stages.extract import json_bytes
from ..stages.generation import PreparedGeneration


PROTOCOL = 'single-generation-plan-approval-v1'
OPTIONS = ('provider', 'model', 'temperature', 'max_output_tokens', 'max_total_tokens', 'timeout_seconds')


@dataclass(frozen=True)
class ClaimedApproval:
    approval_id: str
    plan_sha256: str
    request_sha256: str
    claim_ref: str


def path_for(key, kind):
    return f'generation-approvals/{key}/{kind}.json'


class GenerationApprovalService:
    def __init__(self, service, *, clock=time.time):
        self.service, self.clock = service, clock
        self.engine, self.storage, self.settings = service.engine, service.storage, service.settings

    def preview(self, extraction_id, *, endpoint=ENDPOINT, **options):
        prepared = prepare_registered_generation(self.service, extraction_id, **options)
        _, review = budget_review(prepared, endpoint=endpoint, now=self.clock())
        return {**review, 'extraction_id': extraction_id, 'persistent_registration': False,
            'external_calls_permitted': False, 'usage': None}

    def create(self, extraction_id, idempotency_key, *, endpoint=ENDPOINT, expires_in=900, **options):
        require(type(idempotency_key) is str and re.fullmatch('[A-Za-z0-9_-]{1,80}', idempotency_key), 'approval_invalid_idempotency_key')
        require(type(expires_in) is int and 60 <= expires_in <= 3600, 'approval_invalid_expiry')
        prepared = prepare_registered_generation(self.service, extraction_id, **options)
        now = self.clock()
        plan, review = budget_review(prepared, endpoint=endpoint, now=now)
        plan.preflight()  # Original configured budget unchanged; no silent limit increase.
        intent = {'protocol': PROTOCOL, 'schema_version': 1, 'prepared': prepared.payload(),
            'prepared_sha256': prepared.request_sha256, 'endpoint': plan.endpoint, 'plan_sha256': plan.fingerprint,
            'budget_review': review, 'policy': json.loads(json.dumps(CATALOG)), 'expires_in': expires_in,
            'max_calls': 1, 'dispatch_enabled': False}
        with execution_guard(self.settings.runtime_dir), transaction(self.engine) as session:
            existing = session.scalar(select(Approval).where(Approval.extraction_id == extraction_id, Approval.idempotency_key == idempotency_key))
            if existing:
                request = existing.request
                require(digest(request) == existing.request_sha256, 'approval_request_hash_mismatch')
                require(digest(request['intent']) == digest(intent), 'approval_idempotency_conflict')
                return existing.id
            key = uuid4().hex
            deadline = min(now + expires_in, datetime.fromisoformat(CATALOG['review_before']).timestamp())
            request = {'approval_id': key, 'idempotency_key': idempotency_key, 'extraction_id': extraction_id,
                'created_at': now, 'expires_at': deadline, 'intent': intent}
            path = path_for(key, 'request')
            fingerprint = self.storage.put(path, json_bytes(request))
            session.add(Approval(id=key, extraction_id=extraction_id, idempotency_key=idempotency_key, request=request,
                request_sha256=digest(request), status='pending', created_at=now, expires_at=deadline))
            session.flush()
            session.add(File(approval_id=key, kind='request', relative_path=path, sha256=fingerprint))
        return key

    def snapshot(self, key):
        require(type(key) is str and re.fullmatch('[0-9a-f]{32}', key), 'approval_invalid_id')
        with transaction(self.engine) as session:
            row = self.service.get(session, Approval, key)
            value = {name: getattr(row, name) for name in ('id', 'extraction_id', 'idempotency_key', 'request', 'request_sha256', 'status', 'created_at', 'expires_at')}
            value['files'] = [{name: getattr(file, name) for name in ('kind', 'relative_path', 'sha256')}
                for file in session.scalars(select(File).where(File.approval_id == key).order_by(File.kind))]
        return value

    def report(self, key):
        row = self.snapshot(key)
        request = row['request']
        require(type(request) is dict and digest(request) == row['request_sha256'], 'approval_request_hash_mismatch')
        require(set(request) == {'approval_id', 'idempotency_key', 'extraction_id', 'created_at', 'expires_at', 'intent'}
            and request['approval_id'] == key and request['extraction_id'] == row['extraction_id']
            and request['idempotency_key'] == row['idempotency_key'], 'approval_request_invalid')
        for name in ('created_at', 'expires_at'):
            require(type(request[name]) in (int, float) and math.isfinite(request[name])
                and request[name] == row[name], 'approval_time_invalid')
        intent = request['intent']
        require(type(intent) is dict and set(intent) == {'protocol', 'schema_version', 'prepared', 'prepared_sha256', 'endpoint',
            'plan_sha256', 'budget_review', 'policy', 'expires_in', 'max_calls', 'dispatch_enabled'}
            and type(intent['schema_version']) is int and intent['schema_version'] == 1 and intent['protocol'] == PROTOCOL
            and type(intent['max_calls']) is int and intent['max_calls'] == 1 and intent['dispatch_enabled'] is False
            and type(intent['expires_in']) is int and 60 <= intent['expires_in'] <= 3600, 'approval_intent_invalid')
        prepared = PreparedGeneration(template_bytes(intent['prepared']), intent['prepared_sha256'])
        # Replay at the recorded creation time, not today's catalog/expiry. Frozen
        # policy is checked against this implemented policy, not arbitrary caller JSON.
        require(digest(intent['policy']) == digest(CATALOG), 'approval_policy_not_supported')
        plan, review = budget_review(prepared, endpoint=intent['endpoint'], now=row['created_at'])
        plan.preflight()
        require(intent['plan_sha256'] == plan.fingerprint and digest(review) == digest(intent['budget_review']), 'approval_plan_mismatch')
        end = datetime.fromisoformat(CATALOG['review_before']).timestamp()
        require(row['expires_at'] == min(row['created_at'] + intent['expires_in'], end)
            and row['created_at'] < row['expires_at'], 'approval_time_invalid')
        values = prepared.payload()
        source = ExtractionService(self.service).report(row['extraction_id'])
        index = {(f['path'], f['sha256']) for f in source['contract_projection']['evidence_index']}
        require(values['ssm']['extraction_id'] == row['extraction_id'] and source['status'] == 'completed'
            and source['request_sha256'] == values['ssm']['request_sha256']
            and (values['source']['path'], values['source']['sha256']) in index
            and (values['ssm']['path'], values['ssm']['sha256']) in index, 'approval_source_mismatch')
        files = {f['kind']: f for f in row['files']}
        require(len(files) == len(row['files']) and 'request' in files, 'approval_files_invalid')
        raw = {}
        for kind, file in files.items():
            require(file['relative_path'] == path_for(key, kind), 'approval_reference_invalid')
            raw[kind] = json.loads(self.storage.read(file['relative_path'], file['sha256']))
        require(digest(raw['request']) == row['request_sha256'], 'approval_file_request_mismatch')
        for kind in set(raw) - {'request'}:
            action = raw[kind]
            require(type(action) is dict and set(action) == {'approval_id', 'request_sha256', 'kind', 'at', 'plan_sha256'}
                and action['approval_id'] == key and action['request_sha256'] == row['request_sha256']
                and action['kind'] == kind and action['plan_sha256'] == plan.fingerprint
                and type(action['at']) in (int, float) and math.isfinite(action['at'])
                and row['created_at'] <= action['at'], 'approval_action_invalid')
        expected = {'pending': {'request'}, 'approved': {'request', 'approval'},
            'consumed': {'request', 'approval', 'claim'}}
        if row['status'] == 'revoked':
            require(set(raw) in ({'request', 'revocation'}, {'request', 'approval', 'revocation'}), 'approval_state_mismatch')
        else:
            require(set(raw) == expected.get(row['status']), 'approval_state_mismatch')
        if 'approval' in raw:
            require(raw['approval']['at'] < row['expires_at'], 'approval_action_after_expiry')
        if 'claim' in raw:
            require(raw['approval']['at'] <= raw['claim']['at'] < row['expires_at'], 'approval_action_after_expiry')
        if 'revocation' in raw and 'approval' in raw:
            require(raw['revocation']['at'] >= raw['approval']['at'], 'approval_action_order_invalid')
        return {**row, 'plan_sha256': plan.fingerprint, 'budget_review': review,
            'expired': self.clock() >= row['expires_at'], 'slots_reserved': 1 if 'claim' in raw else 0,
            'actual_model_calls': None if 'claim' in raw else 0, 'usage': None, 'dispatch_enabled': False,
            'scope': 'local_single_plan_approval_not_model_execution', 'production_ready': False}

    def verify_current(self, key):
        report = self.report(key)
        frozen = report['request']['intent']['prepared']
        require(digest(frozen['implementation']) == digest(self.service.implementation_binding()), 'approval_execution_binding_drift')
        prepared = prepare_registered_generation(self.service, report['extraction_id'],
            **{k: frozen['model_config'][k] for k in OPTIONS})
        require(prepared.request_sha256 == report['request']['intent']['prepared_sha256'], 'approval_execution_binding_drift')
        build_budget_plan(prepared, endpoint=report['request']['intent']['endpoint'], now=self.clock()).preflight()
        require(not report['expired'], 'approval_expired')
        return report

    def _action(self, report, kind, status, session):
        row = self.service.get(session, Approval, report['id'])
        require(row.status == report['status'] and row.request_sha256 == report['request_sha256'], 'approval_state_conflict')
        value = {'approval_id': row.id, 'request_sha256': row.request_sha256, 'kind': kind,
            'at': self.clock(), 'plan_sha256': report['plan_sha256']}
        require(type(value['at']) in (int, float) and math.isfinite(value['at']) and value['at'] >= row.created_at,
            'approval_time_invalid')
        if kind in ('approval', 'claim'):
            require(value['at'] < row.expires_at, 'approval_expired')
        path = path_for(row.id, kind)
        fingerprint = self.storage.put(path, json_bytes(value))
        session.add(File(approval_id=row.id, kind=kind, relative_path=path, sha256=fingerprint))
        row.status = status

    def approve(self, key, *, expected_request_sha256, confirm_single_call=False):
        require(confirm_single_call is True, 'approval_explicit_single_call_confirmation_required')
        with execution_guard(self.settings.runtime_dir):
            report = self.verify_current(key)
            require(type(expected_request_sha256) is str and expected_request_sha256 == report['request_sha256'], 'approval_expected_request_mismatch')
            if report['status'] == 'approved':
                return report
            require(report['status'] == 'pending', 'approval_not_pending')
            with transaction(self.engine) as session:
                self._action(report, 'approval', 'approved', session)
            return self.report(key)

    def revoke(self, key, *, expected_request_sha256):
        with execution_guard(self.settings.runtime_dir):
            report = self.report(key)  # May revoke expired or drifted unconsumed grants.
            require(expected_request_sha256 == report['request_sha256'], 'approval_expected_request_mismatch')
            if report['status'] == 'revoked':
                return report
            require(report['status'] in ('pending', 'approved'), 'approval_already_consumed')
            with transaction(self.engine) as session:
                self._action(report, 'revocation', 'revoked', session)
            return self.report(key)

    def claim(self, key, *, expected_plan_sha256):
        """Reserve once, no dispatch. Integration with raw-response ledger is pending."""
        with execution_guard(self.settings.runtime_dir):
            report = self.verify_current(key)
            require(report['status'] == 'approved', 'approval_not_available')
            require(expected_plan_sha256 == report['plan_sha256'], 'approval_expected_plan_mismatch')
            with transaction(self.engine) as session:
                self._action(report, 'claim', 'consumed', session)
            # Not a transport CallPermit: reserving approval is NOT a durable
            # provider attempt-start record. The future dispatcher must commit
            # that separate start before constructing a sendable permit.
            return ClaimedApproval(key, report['plan_sha256'], report['request_sha256'], path_for(key, 'claim'))
