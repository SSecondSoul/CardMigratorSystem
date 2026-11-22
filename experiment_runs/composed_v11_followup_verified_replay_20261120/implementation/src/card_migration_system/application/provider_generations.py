"""Recorded raw exchanges with durable start/receipt barriers. No live call entry.

Only explicitly injected offline transports are executable in this increment.
No production token counter/approval issuer exists yet; live mode fails closed.
"""
from abc import ABC, abstractmethod
from hashlib import sha256
import json
import re
import time
from uuid import uuid4

from sqlalchemy import select

from .extractions import ExtractionService
from .generation_preview import prepare_registered_generation
from .generations import require, template_bytes
from ..adapters.qwen_transport import (ENDPOINT, Exchange, InputTokenBound, MAX_RESPONSE_BYTES,
    build_qwen_plan, inspect_exchange, unknown_outcome)
from ..persistence.database import transaction
from ..persistence.provider_generations import ProviderGenerationJob as Job, ProviderGenerationAttempt as Attempt, ProviderGenerationFile as File
from ..persistence.runtime_lock import execution_guard
from ..reporting.identity import digest
from ..reporting.provider_generation import freeze_provider_contract
from ..stages.extract import json_bytes
from ..stages.generation import PreparedGeneration


PROTOCOL = 'recorded-qwen-transport-g3-v1'
MODE = 'offline_transport_test'


class RecordedOfflineTransport(ABC):
    """Trusted test injection, NOT a sandbox and never provider evidence."""
    @abstractmethod
    def exchange(self, plan):
        raise NotImplementedError


def restore_plan(request):
    prepared = PreparedGeneration(template_bytes(request['prepared']), request['prepared_sha256'])
    bound = request['token_bound']
    return build_qwen_plan(prepared, endpoint=request['endpoint'],
        token_bound=None if bound is None else InputTokenBound(**bound))


def path_for(key, kind):
    return f'provider-generations/{key}/' + ('candidate.san' if kind == 'candidate' else kind + '.json')


class ProviderGenerationService:
    def __init__(self, service):
        self.service = service
        self.engine, self.storage, self.settings = service.engine, service.storage, service.settings

    def create(self, extraction_id, idempotency_key, *, token_bound=None, endpoint=ENDPOINT,
               execution_mode=MODE, **options):
        # No booleans, model key or synthetic counter can enable live execution.
        require(execution_mode == MODE, 'provider_live_counter_and_approval_not_integrated')
        require(type(idempotency_key) is str and re.fullmatch('[A-Za-z0-9_-]{1,80}', idempotency_key), 'provider_invalid_idempotency_key')
        prepared = prepare_registered_generation(self.service, extraction_id, **options)
        plan = build_qwen_plan(prepared, endpoint=endpoint, token_bound=token_bound)
        plan.preflight()
        spec = {'protocol': PROTOCOL, 'schema_version': 1, 'execution_mode': MODE,
            'prepared': prepared.payload(), 'prepared_sha256': prepared.request_sha256,
            'endpoint': plan.endpoint, 'token_bound': vars(token_bound), 'plan_sha256': plan.fingerprint,
            'external_calls_permitted': False, 'persistent_registration': True}
        with transaction(self.engine) as session:
            existing = session.scalar(select(Job).where(Job.extraction_id == extraction_id, Job.idempotency_key == idempotency_key))
            if existing:
                require(digest(existing.request) == existing.request_sha256 and existing.request['generation_id'] == existing.id,
                    'provider_request_hash_mismatch')
                current = {name: value for name, value in existing.request.items() if name not in ('generation_id', 'idempotency_key')}
                require(digest(current) == digest(spec), 'provider_idempotency_conflict')
                return existing.id
            key = uuid4().hex
            request = {**spec, 'generation_id': key, 'idempotency_key': idempotency_key}
            snapshot = freeze_provider_contract(self.service.binding.contracts, plan, key)
            # A P1-shaped request in an OFFLINE bundle is not a real execution request.
            registered = []
            for kind, value in (('plan', request), ('request', snapshot)):
                path = path_for(key, kind)
                registered.append((kind, path, self.storage.put(path, json_bytes(value))))
            session.add(Job(id=key, extraction_id=extraction_id, idempotency_key=idempotency_key, request=request,
                request_sha256=digest(request), status='prepared', stop_reason='', created_at=time.time()))
            session.flush()
            for kind, path, fingerprint in registered:
                session.add(File(job_id=key, kind=kind, relative_path=path, sha256=fingerprint))
        return key

    def snapshot(self, key):
        require(type(key) is str and re.fullmatch('[0-9a-f]{32}', key), 'provider_invalid_id')
        with transaction(self.engine) as session:
            job = self.service.get(session, Job, key)
            row = {name: getattr(job, name) for name in ('id', 'extraction_id', 'idempotency_key', 'request', 'request_sha256', 'status', 'stop_reason')}
            attempt = session.scalar(select(Attempt).where(Attempt.job_id == key))
            row['attempt'] = None if attempt is None else {name: getattr(attempt, name) for name in ('id', 'job_id', 'status', 'request_sha256', 'started_at')}
            row['files'] = [{name: getattr(file, name) for name in ('kind', 'relative_path', 'sha256')}
                for file in session.scalars(select(File).where(File.job_id == key).order_by(File.kind))]
        return row

    def report(self, key):
        row = self.snapshot(key)
        request = row['request']
        require(type(request) is dict and digest(request) == row['request_sha256'], 'provider_request_hash_mismatch')
        require(set(request) == {'protocol', 'schema_version', 'execution_mode', 'prepared', 'prepared_sha256',
            'endpoint', 'token_bound', 'plan_sha256', 'external_calls_permitted', 'persistent_registration',
            'generation_id', 'idempotency_key'}, 'provider_request_invalid')
        require(type(request['schema_version']) is int and request['schema_version'] == 1 and request['protocol'] == PROTOCOL
            and request['execution_mode'] == MODE and request['external_calls_permitted'] is False
            and request['persistent_registration'] is True and request['generation_id'] == key
            and request['idempotency_key'] == row['idempotency_key'], 'provider_request_invalid')
        plan = restore_plan(request)
        plan.preflight()
        require(plan.fingerprint == request['plan_sha256'], 'provider_plan_mismatch')
        values = plan.prepared.payload()
        require(values['ssm']['extraction_id'] == row['extraction_id'], 'provider_source_mismatch')
        source = ExtractionService(self.service).report(row['extraction_id'])
        index = {(item['path'], item['sha256']) for item in source['contract_projection']['evidence_index']}
        require(source['status'] == 'completed' and source['request_sha256'] == values['ssm']['request_sha256']
            and (values['source']['path'], values['source']['sha256']) in index
            and (values['ssm']['path'], values['ssm']['sha256']) in index, 'provider_source_mismatch')
        files = {file['kind']: file for file in row['files']}
        require(len(files) == len(row['files']) and {'plan', 'request'} <= set(files), 'provider_files_invalid')
        raw = {}
        for kind, file in files.items():
            require(file['relative_path'] == path_for(key, kind), 'provider_reference_invalid')
            raw[kind] = self.storage.read(file['relative_path'], file['sha256'])
        require(digest(json.loads(raw['plan'])) == row['request_sha256'], 'provider_plan_file_mismatch')
        require(digest(json.loads(raw['request'])) == digest(freeze_provider_contract(self.service.binding.contracts, plan, key)), 'provider_snapshot_mismatch')
        attempt, receipt = row['attempt'], None
        if attempt:
            require(attempt['id'] == key + ':generate:1' and attempt['job_id'] == key
                and attempt['request_sha256'] == row['request_sha256'], 'provider_attempt_mismatch')
        if 'receipt' in raw:
            receipt = json.loads(raw['receipt'])
            require(type(receipt) is dict and set(receipt) == {'schema_version', 'generation_id', 'attempt_id', 'execution_mode',
                'plan_sha256', 'http_status', 'file_refs', 'outcome'} and type(receipt['schema_version']) is int
                and receipt['schema_version'] == 2 and receipt['generation_id'] == key and attempt is not None
                and receipt['attempt_id'] == attempt['id'] and receipt['execution_mode'] == MODE
                and receipt['plan_sha256'] == plan.fingerprint, 'provider_receipt_mismatch')
            refs = {kind: {'path': file['relative_path'], 'sha256': file['sha256']}
                for kind, file in files.items() if kind in ('request', 'response', 'candidate')}
            require(digest(receipt['file_refs']) == digest(refs), 'provider_receipt_reference_mismatch')
            if 'response' in raw:
                require(type(receipt['http_status']) is int, 'provider_http_status_invalid')
                checked = inspect_exchange(plan, Exchange(receipt['http_status'], raw['response']))
            else:
                require(receipt['http_status'] is None, 'provider_http_status_invalid')
                checked = unknown_outcome(plan, 'qwen_transport_outcome_unknown', provenance=MODE)
            require(digest(checked) == digest(receipt['outcome']), 'provider_response_mismatch')
            if checked['candidate']:
                require(set(files) == {'plan', 'request', 'response', 'receipt', 'candidate'}
                    and raw['candidate'] == checked['candidate']['code'].encode('utf-8'), 'provider_candidate_mismatch')
            else:
                require(set(files) == ({'plan', 'request', 'receipt', 'response'} if 'response' in raw else {'plan', 'request', 'receipt'}), 'provider_unexpected_candidate')
        else:
            require(set(files) == {'plan', 'request'}, 'provider_unregistered_receipt')
        if row['status'] == 'prepared':
            require(attempt is None and receipt is None, 'provider_state_mismatch')
        elif row['status'] == 'started':
            require(attempt is not None and attempt['status'] == 'started' and receipt is None, 'provider_state_mismatch')
        elif row['status'] == 'review_required':
            require(attempt is None or attempt['status'] == 'review_required', 'provider_state_mismatch')
        else:
            require(receipt is not None and attempt is not None and attempt['status'] == 'received', 'provider_state_mismatch')
            if row['status'] in ('completed', 'blocked'):
                require((row['status'], row['stop_reason']) == self.conclusion(receipt), 'provider_stop_reason_mismatch')
        outcome = None if receipt is None else receipt['outcome']
        return {**row, 'receipt': receipt, 'candidate': None if outcome is None else outcome['candidate'],
            'usage': None if outcome is None else outcome['usage'], 'actual_model_calls': 0,
            'transport_invocations': 1 if receipt else None if attempt else 0, 'slots_reserved': 1 if attempt else 0,
            'contract_revision': None, 'migration_quality_status': 'not_run', 'production_ready': False,
            'langsmith_uploaded': False, 'scope': 'registered_offline_transport_protocol_not_real_generation'}

    @staticmethod
    def conclusion(receipt):
        if receipt['outcome']['candidate']:
            return 'completed', 'offline_exchange_registered_not_migration_pass'
        if receipt['outcome']['usage'] is None:
            return 'review_required', 'provider_usage_or_outcome_unknown'
        return 'blocked', 'provider_response_rejected'

    def verify_binding(self, key):
        report = self.report(key)
        frozen = report['request']['prepared']
        require(digest(frozen['implementation']) == digest(self.service.implementation_binding()), 'provider_execution_binding_drift')
        config = frozen['model_config']
        prepared = prepare_registered_generation(self.service, report['extraction_id'],
            **{name: config[name] for name in ('provider', 'model', 'temperature', 'max_output_tokens', 'max_total_tokens', 'timeout_seconds')})
        require(prepared.request_sha256 == report['request']['prepared_sha256'], 'provider_execution_binding_drift')
        return report

    def invoke(self, key, transport):
        require(isinstance(transport, RecordedOfflineTransport), 'provider_offline_transport_required')
        with execution_guard(self.settings.runtime_dir):
            return self._invoke_locked(key, transport)

    def _invoke_locked(self, key, transport):
        report = self.verify_binding(key)
        if report['receipt'] is not None:
            return report['receipt']
        require(report['status'] == 'prepared' and report['attempt'] is None, 'provider_unresolved_attempt_requires_review')
        plan = restore_plan(report['request'])
        with transaction(self.engine) as session:
            job = self.service.get(session, Job, key)
            require(job.status == 'prepared', 'provider_attempt_state_conflict')
            session.add(Attempt(id=key + ':generate:1', job_id=key, request_sha256=job.request_sha256,
                status='started', started_at=time.time()))
            job.status = 'started'
        exchange = None
        try:
            exchange = transport.exchange(plan)
        except Exception:
            pass  # Unknown outcome, no raw exception/credential/source echoed.
        valid_exchange = type(exchange) is Exchange and type(exchange.status) is int and type(exchange.body) is bytes
        # Bound storage even for a broken trusted test transport. HTTPS reads use the same cap.
        if valid_exchange:
            exchange = Exchange(exchange.status, exchange.body[:MAX_RESPONSE_BYTES + 1])
            outcome = inspect_exchange(plan, exchange)
        else:
            outcome = unknown_outcome(plan, 'qwen_transport_outcome_unknown', provenance=MODE)
        registered = []
        refs = {'request': next({'path': f['relative_path'], 'sha256': f['sha256']} for f in report['files'] if f['kind'] == 'request')}
        for kind, content in ((('response', exchange.body),) if valid_exchange else ()):
            path = path_for(key, kind)
            fingerprint = self.storage.put(path, content)
            registered.append((kind, path, fingerprint))
            refs[kind] = {'path': path, 'sha256': fingerprint}
        if outcome['candidate']:
            path = path_for(key, 'candidate')
            fingerprint = self.storage.put(path, outcome['candidate']['code'].encode('utf-8'))
            registered.append(('candidate', path, fingerprint))
            refs['candidate'] = {'path': path, 'sha256': fingerprint}
        receipt = {'schema_version': 2, 'generation_id': key, 'attempt_id': key + ':generate:1',
            'execution_mode': MODE, 'plan_sha256': plan.fingerprint, 'http_status': exchange.status if valid_exchange else None,
            'file_refs': refs, 'outcome': outcome}
        path = path_for(key, 'receipt')
        registered.append(('receipt', path, self.storage.put(path, json_bytes(receipt))))
        # Persist known response BEFORE checking implementation drift. A drift must
        # never lose already incurred usage or cause a second dispatch.
        with transaction(self.engine) as session:
            job = self.service.get(session, Job, key)
            require(job.status == 'started', 'provider_attempt_state_conflict')
            for kind, path, fingerprint in registered:
                session.add(File(job_id=key, kind=kind, relative_path=path, sha256=fingerprint))
            self.service.get(session, Attempt, key + ':generate:1').status = 'received'
            job.status = 'received'
        return receipt

    def finish(self, key):
        with execution_guard(self.settings.runtime_dir):
            return self._finish_locked(key)

    def _finish_locked(self, key):
        report = self.verify_binding(key)
        require(report['receipt'] is not None, 'provider_receipt_required')
        status, reason = self.conclusion(report['receipt'])
        with transaction(self.engine) as session:
            job = self.service.get(session, Job, key)
            job.status, job.stop_reason = status, reason
            self.service.get(session, Attempt, key + ':generate:1').status = 'review_required' if status == 'review_required' else 'received'
        return status

    def review(self, key, reason):
        with transaction(self.engine) as session:
            job = self.service.get(session, Job, key)
            if job.status not in ('completed', 'blocked'):
                job.status, job.stop_reason = 'review_required', reason
                attempt = session.scalar(select(Attempt).where(Attempt.job_id == key))
                if attempt:
                    attempt.status = 'review_required'
