"""Durable, explicitly offline generation attempts. No model transport/default client."""
from hashlib import sha256
import json
import re
import time
from uuid import uuid4

from sqlalchemy import select

from .extractions import ExtractionService
from .generation_preview import prepare_registered_generation
from .service import ServiceError
from ..adapters.generation import GenerationResponse, OfflineGenerationClient
from ..persistence.database import transaction
from ..persistence.generations import (GenerationJob, GenerationAttempt, GenerationFile, GenerationCandidate)
from ..reporting.identity import digest
from ..stages.extract import json_bytes
from ..stages.generation import (GenerationBoundaryError, PreparedGeneration, check_generation_response,
                                 run_offline_generation)


PROTOCOL = 'registered-offline-generation-g2-v1'


def require(condition, code='generation_registered_evidence_invalid'):
    if not condition:
        raise ServiceError(code)


def template_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def prepared_from(request):
    return PreparedGeneration(template_bytes(request['prepared']), request['prepared_sha256'])


class GenerationService:
    def __init__(self, service):
        self.service = service
        self.settings, self.storage, self.engine = service.settings, service.storage, service.engine

    def create(self, extraction_id, idempotency_key, **options):
        require(type(idempotency_key) is str and re.fullmatch('[A-Za-z0-9_-]{1,80}', idempotency_key),
                'generation_invalid_idempotency_key')
        prepared = prepare_registered_generation(self.service, extraction_id, **options)
        values = prepared.payload()
        with transaction(self.engine) as session:
            existing = session.scalar(select(GenerationJob).where(GenerationJob.extraction_id == extraction_id,
                GenerationJob.idempotency_key == idempotency_key))
            if existing:
                require(existing.request.get('prepared_sha256') == prepared.request_sha256,
                        'generation_idempotency_conflict')
                return existing.id
            key = uuid4().hex
            request = {'schema_version': 1, 'protocol': PROTOCOL, 'generation_id': key,
                'idempotency_key': idempotency_key, 'prepared': values,
                'prepared_sha256': prepared.request_sha256, 'client_mode': 'offline_client_test',
                'external_calls_permitted': False, 'persistent_registration': True}
            path = f'generations/{key}/request.json'
            fingerprint = self.storage.put(path, json_bytes(request))
            session.add(GenerationJob(id=key, extraction_id=extraction_id, input_id=values['source']['input_id'],
                idempotency_key=idempotency_key, status='prepared', request=request, request_sha256=digest(request),
                stop_reason='', created_at=time.time()))
            session.flush()  # Explicit parent-before-file order; no ORM relationship cascade.
            session.add(GenerationFile(job_id=key, kind='request', relative_path=path, sha256=fingerprint))
        return key

    def snapshot(self, key):
        require(type(key) is str and re.fullmatch('[0-9a-f]{32}', key), 'generation_invalid_id')
        with transaction(self.engine) as session:
            job = self.service.get(session, GenerationJob, key)
            row = {name: getattr(job, name) for name in ('id', 'extraction_id', 'input_id', 'idempotency_key',
                'status', 'request', 'request_sha256', 'stop_reason', 'created_at')}
            attempt = session.scalar(select(GenerationAttempt).where(GenerationAttempt.job_id == key))
            row['attempt'] = None if attempt is None else {name: getattr(attempt, name) for name in
                ('id', 'job_id', 'request_sha256', 'status', 'started_at')}
            row['files'] = [{name: getattr(file, name) for name in ('relative_path', 'sha256', 'kind')}
                for file in session.scalars(select(GenerationFile).where(GenerationFile.job_id == key).order_by(GenerationFile.kind))]
            candidate = session.scalar(select(GenerationCandidate).where(GenerationCandidate.job_id == key))
            row['candidate'] = None if candidate is None else {name: getattr(candidate, name) for name in
                ('id', 'job_id', 'relative_path', 'sha256', 'parent_id', 'source_kind')}
        return row

    def report(self, key):
        row = self.snapshot(key)
        request = row['request']
        require(type(request) is dict and digest(request) == row['request_sha256'], 'generation_request_hash_mismatch')
        require(set(request) == {'schema_version', 'protocol', 'generation_id', 'idempotency_key', 'prepared',
            'prepared_sha256', 'client_mode', 'external_calls_permitted', 'persistent_registration'})
        require(type(request['schema_version']) is int and request['schema_version'] == 1
            and request['protocol'] == PROTOCOL and request['generation_id'] == key
            and request['idempotency_key'] == row['idempotency_key'] and request['client_mode'] == 'offline_client_test'
            and request['external_calls_permitted'] is False and request['persistent_registration'] is True)
        prepared = prepared_from(request)
        try:
            values = prepared.payload()
        except (ValueError, KeyError, TypeError):
            raise ServiceError('generation_prepared_evidence_invalid') from None
        require(values['ssm']['extraction_id'] == row['extraction_id'] and values['source']['input_id'] == row['input_id'])
        source = ExtractionService(self.service).report(row['extraction_id'])
        require(source['status'] == 'completed' and source['request_sha256'] == values['ssm']['request_sha256']
                and source['request']['source']['input_id'] == row['input_id']
                and source['request']['source']['source_sha256'] == values['source']['sha256'])
        index = {(item['path'], item['sha256']) for item in source['contract_projection']['evidence_index']}
        require((values['source']['path'], values['source']['sha256']) in index
                and (values['ssm']['path'], values['ssm']['sha256']) in index)
        files = {file['kind']: file for file in row['files']}
        require(len(files) == len(row['files']) and 'request' in files)
        raw = {}
        for kind, file in files.items():
            suffix = 'candidate.san' if kind == 'candidate' else kind + '.json'
            require(file['relative_path'] == f'generations/{key}/{suffix}')
            raw[kind] = self.storage.read(file['relative_path'], file['sha256'])
        require(digest(json.loads(raw['request'])) == row['request_sha256'])
        attempt, candidate = row['attempt'], row['candidate']
        if attempt is not None:
            require(attempt['id'] == key + ':generate:1' and attempt['job_id'] == key
                    and attempt['request_sha256'] == row['request_sha256'])
        if row['status'] == 'prepared':
            require(attempt is None and set(files) == {'request'} and candidate is None)
        if row['status'] == 'started':
            require(attempt is not None and attempt['status'] == 'started' and set(files) == {'request'} and candidate is None)
        if row['status'] == 'review_required':
            require(attempt is None or attempt['status'] == 'review_required')
        receipt = None
        if 'receipt' in files:
            receipt = json.loads(raw['receipt'])
            require(type(receipt) is dict and set(receipt) == {'schema_version', 'generation_id', 'attempt_id',
                'request_sha256', 'status', 'error', 'candidate', 'usage', 'budget_status', 'actual_model_calls',
                'offline_client_invocations', 'langsmith_uploaded', 'migration_quality_status', 'production_ready'})
            require(type(receipt['schema_version']) is int and receipt['schema_version'] == 1
                and receipt['generation_id'] == key and attempt is not None and receipt['attempt_id'] == attempt['id']
                and receipt['request_sha256'] == row['request_sha256']
                and type(receipt['actual_model_calls']) is int and receipt['actual_model_calls'] == 0
                and type(receipt['offline_client_invocations']) is int and receipt['offline_client_invocations'] == 1
                and receipt['langsmith_uploaded'] is False and receipt['production_ready'] is False
                and receipt['migration_quality_status'] == 'not_run')
            if receipt['status'] == 'completed':
                require(set(files) == {'request', 'receipt', 'candidate'} and candidate is not None
                    and candidate['id'] == key + ':candidate:1' and candidate['job_id'] == key
                    and candidate['parent_id'] is None and candidate['source_kind'] == 'offline_client_test'
                    and candidate['relative_path'] == files['candidate']['relative_path']
                    and candidate['sha256'] == files['candidate']['sha256']
                    and digest(receipt['candidate']) == digest(candidate) and receipt['error'] is None)
                config = values['model_config']
                try:
                    checked = check_generation_response(prepared, GenerationResponse(raw['candidate'].decode('utf-8'),
                        config['provider'], config['model'], 'stop', **receipt['usage']))
                except (ValueError, TypeError, KeyError, UnicodeError):
                    raise ServiceError('generation_candidate_evidence_invalid') from None
                require(checked['candidate']['sha256'] == candidate['sha256']
                    and digest(checked['usage']) == digest(receipt['usage']) and checked['budget_status'] == receipt['budget_status'])
            else:
                require(receipt['status'] == 'blocked' and set(files) == {'request', 'receipt'} and candidate is None
                    and receipt['candidate'] is None and type(receipt['error']) is str
                    and re.fullmatch('generation_[a-z_]{1,80}', receipt['error'])
                    and digest(receipt['usage']) == digest({'input_tokens': None, 'output_tokens': None})
                    and receipt['budget_status'] == 'usage_unknown')
        else:
            require(set(files) == {'request'} and candidate is None)
        if row['status'] in ('received', 'completed', 'blocked'):
            require(receipt is not None and attempt is not None and attempt['status'] == 'received')
        if row['status'] in ('completed', 'blocked'):
            reason = 'offline_candidate_registered_not_migration_pass' if receipt['status'] == 'completed' else receipt['error']
            require(row['status'] == receipt['status'] and row['stop_reason'] == reason)
        return {'schema_version': 1, 'generation_id': key, 'status': row['status'], 'stop_reason': row['stop_reason'],
            'request_sha256': row['request_sha256'], 'request': request, 'attempt': attempt, 'files': row['files'],
            'candidate': candidate, 'receipt': receipt, 'actual_model_calls': 0,
            'offline_client_invocations': 1 if receipt else None if attempt else 0,
            'generation_slots_reserved': 1 if attempt else 0,
            'client_outcome': 'received' if receipt else 'unknown' if attempt else 'not_started',
            'persistent_registration': True, 'contract_revision': None, 'langsmith_uploaded': False,
            'production_ready': False, 'migration_quality_status': 'not_run', 'scope': 'registered_offline_generation_only'}

    def verify_binding(self, key):
        result = self.report(key)
        frozen = result['request']['prepared']
        require(digest(frozen['implementation']) == digest(self.service.implementation_binding()), 'generation_execution_binding_drift')
        # Checks current trusted Prompt bytes and all current source refs, without parsing Vue again.
        config = frozen['model_config']
        current = prepare_registered_generation(self.service, frozen['ssm']['extraction_id'],
            **{name: config[name] for name in ('provider', 'model', 'temperature', 'max_output_tokens', 'max_total_tokens', 'timeout_seconds')})
        require(current.request_sha256 == result['request']['prepared_sha256'], 'generation_execution_binding_drift')
        return result

    def invoke(self, key, client):
        require(isinstance(client, OfflineGenerationClient), 'generation_offline_client_required')
        result = self.verify_binding(key)
        if result['receipt'] is not None:
            return result['receipt']
        require(result['status'] == 'prepared' and result['attempt'] is None, 'generation_unresolved_attempt_requires_review')
        attempt_id = key + ':generate:1'
        with transaction(self.engine) as session:
            row = self.service.get(session, GenerationJob, key)
            require(row.status == 'prepared', 'generation_attempt_state_conflict')
            session.add(GenerationAttempt(id=attempt_id, job_id=key, request_sha256=row.request_sha256,
                                          status='started', started_at=time.time()))
            row.status = 'started'
        receipt = {'schema_version': 1, 'generation_id': key, 'attempt_id': attempt_id,
            'request_sha256': result['request_sha256'], 'status': 'blocked', 'error': None, 'candidate': None,
            'usage': {'input_tokens': None, 'output_tokens': None}, 'budget_status': 'usage_unknown',
            'actual_model_calls': 0, 'offline_client_invocations': 1, 'langsmith_uploaded': False,
            'migration_quality_status': 'not_run', 'production_ready': False}
        candidate = None
        artifacts = []
        try:
            checked = run_offline_generation(prepared_from(result['request']), client)
            self.verify_binding(key)  # A return is not allowed to hide source/implementation drift.
            path = f'generations/{key}/candidate.san'
            fingerprint = self.storage.put(path, checked['candidate']['code'].encode('utf-8'))
            candidate = {'id': key + ':candidate:1', 'job_id': key, 'relative_path': path, 'sha256': fingerprint,
                         'parent_id': None, 'source_kind': 'offline_client_test'}
            artifacts.append(('candidate', path, fingerprint))
            receipt.update(status='completed', candidate=candidate, usage=checked['usage'], budget_status=checked['budget_status'])
        except GenerationBoundaryError as error:
            if str(error) == 'generation_client_outcome_unknown_no_retry':
                self.review(key, str(error))
                raise ServiceError(str(error)) from None
            receipt['error'] = str(error)
        fingerprint = self.storage.put(f'generations/{key}/receipt.json', json_bytes(receipt))
        artifacts.append(('receipt', f'generations/{key}/receipt.json', fingerprint))
        with transaction(self.engine) as session:
            row = self.service.get(session, GenerationJob, key)
            require(row.status == 'started', 'generation_attempt_state_conflict')
            for kind, path, fingerprint in artifacts:
                session.add(GenerationFile(job_id=key, kind=kind, relative_path=path, sha256=fingerprint))
            session.flush()
            if candidate is not None:
                session.add(GenerationCandidate(**candidate))
            self.service.get(session, GenerationAttempt, attempt_id).status = 'received'
            row.status = 'received'
        return receipt

    def finish(self, key):
        result = self.verify_binding(key)
        receipt = result['receipt']
        require(receipt is not None, 'generation_receipt_required')
        reason = 'offline_candidate_registered_not_migration_pass' if receipt['status'] == 'completed' else receipt['error']
        with transaction(self.engine) as session:
            job = self.service.get(session, GenerationJob, key)
            job.status, job.stop_reason = receipt['status'], reason
            self.service.get(session, GenerationAttempt, receipt['attempt_id']).status = 'received'
        return receipt['status']

    def review(self, key, reason):
        with transaction(self.engine) as session:
            job = self.service.get(session, GenerationJob, key)
            if job.status not in ('completed', 'blocked'):
                job.status, job.stop_reason = 'review_required', reason
                attempt = session.scalar(select(GenerationAttempt).where(GenerationAttempt.job_id == key))
                if attempt:
                    attempt.status = 'review_required'

    def download(self, key):
        result = self.report(key)
        require(result['status'] == 'completed' and result['candidate'] is not None, 'generation_not_completed')
        candidate = result['candidate']
        return self.storage.read(candidate['relative_path'], candidate['sha256'])
