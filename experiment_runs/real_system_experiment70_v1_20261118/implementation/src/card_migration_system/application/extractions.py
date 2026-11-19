"""Registered real extraction facts, independently audited from fixture runs."""
import base64
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import time
from uuid import uuid4

from sqlalchemy import and_, or_, select

from ..adapters.ssm import ExtractionError, SSMExtractor, source_binding
from ..persistence.database import transaction
from ..persistence.schema_v1 import Run, SourceInput, Task
from ..persistence.ssm_extractions import SSMExtraction, SSMExtractionFile
from ..reporting.identity import digest
from ..reporting.extraction_projection import PROTOCOL, build_snapshot, project_extraction
from ..stages.extract import json_bytes
from .service import Service, ServiceError


def require(condition, code='ssm_registered_evidence_invalid'):
    if not condition:
        raise ServiceError(code)


class ExtractionService:
    def __init__(self, service: Service):
        self.service = service
        self.settings, self.storage, self.engine = service.settings, service.storage, service.engine

    def binding(self):
        bridge = Path(__file__).resolve().parents[1] / 'adapters/ssm_bridge.cjs'
        return {'system': self.service.implementation_binding(),
                'legacy_files_sha256': source_binding(self.settings.repository_root),
                'bridge_sha256': sha256(bridge.read_bytes()).hexdigest()}

    def list_records(self, *, limit=10, before=None):
        """Ledger metadata only; listing never parses, resumes, or attests evidence."""
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ServiceError('invalid_page_size', 400)
        statement = select(SSMExtraction, SourceInput.filename).join(
            SourceInput, SSMExtraction.input_id == SourceInput.id)
        if before is not None:
            try:
                if type(before) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', before):
                    raise ValueError()
                stamp, key = json.loads(base64.urlsafe_b64decode(before + '=' * (-len(before) % 4)))
                if (type(stamp) not in (float, int) or not math.isfinite(stamp) or stamp < 0
                        or type(key) is not str or not re.fullmatch('[0-9a-f]{32}', key)):
                    raise ValueError()
            except (ValueError, TypeError, UnicodeError) as error:
                raise ServiceError('invalid_ssm_cursor', 400) from error
            statement = statement.where(or_(SSMExtraction.created_at < stamp,
                and_(SSMExtraction.created_at == stamp, SSMExtraction.id < key)))
        with transaction(self.engine) as session:
            rows = session.execute(statement.order_by(SSMExtraction.created_at.desc(),
                SSMExtraction.id.desc()).limit(limit + 1)).all()
            page = rows[:limit]
            items = [{'extraction_id': row.id, 'input_id': row.input_id,
                      'referenced_run_id': row.referenced_run_id, 'filename': filename,
                      'status': row.status, 'created_at': row.created_at} for row, filename in page]
            cursor = None
            if len(rows) > limit:
                last = page[-1][0]
                cursor = base64.urlsafe_b64encode(json.dumps([last.created_at, last.id],
                    separators=(',', ':')).encode()).decode().rstrip('=')
        return {'items': items, 'next_cursor': cursor, 'evidence_audit': 'not_performed_in_list',
                'scope': 'registered_source_extraction_only_not_migration', 'production_ready': False}

    def create(self, *, input_id=None, run_id=None):
        require((input_id is None) != (run_id is None), 'ssm_one_source_reference_required')
        reference = input_id if input_id is not None else run_id
        require(type(reference) is str and re.fullmatch('[0-9a-f]{32}', reference), 'ssm_invalid_source_reference')
        with transaction(self.engine) as session:
            if run_id is not None:
                run = self.service.get(session, Run, run_id)
                input_id = self.service.get(session, Task, run.task_id).input_id
            source = self.service.get(session, SourceInput, input_id)
            reference = {'input_id': input_id, 'referenced_run_id': run_id,
                         'filename': source.filename, 'source_sha256': source.sha256}
            self.storage.read(source.relative_path, source.sha256)
        key = uuid4().hex
        request = {'schema_version': 1, 'protocol': PROTOCOL, 'extraction_id': key,
                   'source': reference, 'binding': self.binding(), 'actual_model_calls': 0,
                   'langsmith_uploaded': False, 'production_ready': False}
        request['contract_snapshot'] = build_snapshot(self.service.binding.contracts, request, source.relative_path)
        path = f'ssm-extractions/{key}/request.json'
        fingerprint = self.storage.put(path, json_bytes(request))
        with transaction(self.engine) as session:
            session.add(SSMExtraction(id=key, input_id=input_id, referenced_run_id=run_id,
                status='prepared', request_sha256=digest(request), request=request,
                stop_reason='', created_at=time.time()))
            session.add(SSMExtractionFile(extraction_id=key, kind='request', relative_path=path, sha256=fingerprint))
        return key

    def snapshot(self, key):
        require(type(key) is str and re.fullmatch('[0-9a-f]{32}', key), 'ssm_invalid_extraction_id')
        with transaction(self.engine) as session:
            row = self.service.get(session, SSMExtraction, key)
            source = self.service.get(session, SourceInput, row.input_id)
            if row.referenced_run_id is not None:
                run = self.service.get(session, Run, row.referenced_run_id)
                require(self.service.get(session, Task, run.task_id).input_id == row.input_id)
            result = {name: getattr(row, name) for name in ('id', 'input_id', 'referenced_run_id', 'status',
                      'request_sha256', 'request', 'stop_reason', 'created_at')}
            result['source_path'], result['source_sha256'], result['filename'] = source.relative_path, source.sha256, source.filename
            result['files'] = [{'kind': item.kind, 'relative_path': item.relative_path, 'sha256': item.sha256}
                              for item in session.scalars(select(SSMExtractionFile).where(
                                  SSMExtractionFile.extraction_id == key).order_by(SSMExtractionFile.kind))]
        return result

    def report(self, key):
        row = self.snapshot(key)
        request = row['request']
        require(type(request) is dict and digest(request) == row['request_sha256'], 'ssm_request_hash_mismatch')
        expected_source = {'input_id': row['input_id'], 'referenced_run_id': row['referenced_run_id'],
                           'filename': row['filename'], 'source_sha256': row['source_sha256']}
        require(request.get('extraction_id') == key and request.get('protocol') in ('registered-ssm-graph-v1', PROTOCOL)
                and digest(request.get('source')) == digest(expected_source))
        require(type(request.get('schema_version')) is int and request['schema_version'] == 1
                and type(request.get('actual_model_calls')) is int and request['actual_model_calls'] == 0
                and request.get('langsmith_uploaded') is False and request.get('production_ready') is False)
        frozen = request.get('binding')
        require(type(frozen) is dict and set(frozen) == {'system', 'legacy_files_sha256', 'bridge_sha256'}
                and type(frozen['system']) is dict and type(frozen['legacy_files_sha256']) is dict
                and bool(frozen['legacy_files_sha256']) and type(frozen['bridge_sha256']) is str
                and re.fullmatch('[0-9a-f]{64}', frozen['bridge_sha256']))
        self.storage.read(row['source_path'], row['source_sha256'])
        files = {item['kind']: item for item in row['files']}
        require(len(files) == len(row['files']) and 'request' in files)
        raw = {}
        for kind, file in files.items():
            require(file['relative_path'] == f'ssm-extractions/{key}/{kind}.json')
            raw[kind] = self.storage.read(file['relative_path'], file['sha256'])
        require(digest(json.loads(raw['request'])) == row['request_sha256'])
        receipt = None
        if row['status'] in ('prepared', 'started'):
            require(set(files) == {'request'})
        if 'receipt' in files:
            receipt = json.loads(raw['receipt'])
            require(type(receipt) is dict and receipt.get('extraction_id') == key
                    and receipt.get('request_sha256') == row['request_sha256']
                    and digest(receipt.get('source')) == digest(expected_source))
            require(type(receipt.get('actual_model_calls')) is int and receipt['actual_model_calls'] == 0
                    and receipt.get('langsmith_uploaded') is False and receipt.get('production_ready') is False
                    and receipt.get('migration_quality_status') == 'not_run')
            if receipt.get('status') == 'completed':
                require(set(files) == {'request', 'ssm', 'receipt'}
                        and receipt.get('ssm_sha256') == files['ssm']['sha256'])
                ssm = json.loads(raw['ssm'])
                require(type(ssm) is dict and ssm.get('schema_version') == '3.0'
                        and all(type(ssm.get(name)) is dict for name in
                                ('metadata', 'template', 'script', 'styles', 'binding_graph', 'event_model', 'style_model'))
                        and ssm.get('metadata', {}).get('source_file') == row['filename'])
                binding = receipt.get('binding')
                require(type(binding) is dict and digest(binding) == receipt.get('binding_sha256')
                        and digest(binding.get('legacy_files_sha256')) == digest(request['binding']['legacy_files_sha256']))
            else:
                require(receipt.get('status') == 'blocked' and set(files) == {'request', 'receipt'}
                        and receipt.get('ssm_sha256') is None and receipt.get('binding') is None
                        and type(receipt.get('error')) is str and re.fullmatch('ssm_[a-z_]{1,80}', receipt['error']))
        if row['status'] in ('received', 'completed', 'blocked'):
            require(receipt is not None)
        if row['status'] in ('completed', 'blocked'):
            require(row['status'] == receipt['status'])
            expected_reason = 'ssm_extracted_not_migration_pass' if row['status'] == 'completed' else receipt['error']
            require(row['stop_reason'] == expected_reason)
        try:
            contract = project_extraction(self.service.binding.contracts, row, receipt)
        except (ValueError, KeyError, TypeError) as error:
            raise ServiceError('ssm_contract_projection_invalid') from error
        return {'schema_version': 1, 'extraction_id': key, 'status': row['status'],
                'stop_reason': row['stop_reason'], 'request_sha256': row['request_sha256'],
                'request': request, 'files': row['files'], 'receipt': receipt,
                'scope': 'registered_source_extraction_only_not_migration',
                'migration_quality_status': 'not_run', 'actual_model_calls': 0,
                'langsmith_uploaded': False, 'production_ready': False, **contract}

    def verify_binding(self, key):
        result = self.report(key)
        require(digest(result['request']['binding']) == digest(self.binding()), 'ssm_execution_binding_drift')
        return result

    def extract(self, key):
        result = self.verify_binding(key)
        if result['receipt'] is not None:
            return result['receipt']  # Committed response reused; never call the parser again.
        with transaction(self.engine) as session:
            row = self.service.get(session, SSMExtraction, key)
            require(row.status == 'prepared', 'ssm_unresolved_attempt_requires_review')
            row.status = 'started'
            source = self.service.get(session, SourceInput, row.input_id)
            source_bytes = self.storage.read(source.relative_path, source.sha256)
        request = result['request']
        receipt = {'schema_version': 1, 'extraction_id': key, 'request_sha256': result['request_sha256'],
                   'source': request['source'], 'actual_model_calls': 0, 'langsmith_uploaded': False,
                   'production_ready': False, 'migration_quality_status': 'not_run',
                   'binding': None, 'ssm_sha256': None}
        artifacts = []
        try:
            extracted = SSMExtractor(self.settings.repository_root).extract(source_bytes, source.filename, source.sha256)
            require(digest(request['binding']) == digest(self.binding()), 'ssm_execution_binding_drift')
            require(digest(extracted['binding']['legacy_files_sha256']) == digest(request['binding']['legacy_files_sha256']),
                    'ssm_execution_binding_drift')
            fingerprint = self.storage.put(f'ssm-extractions/{key}/ssm.json', json_bytes(extracted['ssm']))
            artifacts.append(('ssm', fingerprint))
            receipt.update(status='completed', binding=extracted['binding'],
                           binding_sha256=extracted['binding_sha256'], ssm_sha256=fingerprint,
                           limitations=extracted['limitations'])
        except ExtractionError as error:
            receipt.update(status='blocked', error=str(error))
        fingerprint = self.storage.put(f'ssm-extractions/{key}/receipt.json', json_bytes(receipt))
        artifacts.append(('receipt', fingerprint))
        with transaction(self.engine) as session:
            row = self.service.get(session, SSMExtraction, key)
            require(row.status == 'started', 'ssm_attempt_state_conflict')
            for kind, fingerprint in artifacts:
                session.add(SSMExtractionFile(extraction_id=key, kind=kind,
                            relative_path=f'ssm-extractions/{key}/{kind}.json', sha256=fingerprint))
            row.status = 'received'
        return receipt

    def finish(self, key):
        result = self.verify_binding(key)
        require(result['receipt'] is not None, 'ssm_receipt_required')
        status = result['receipt']['status']
        reason = 'ssm_extracted_not_migration_pass' if status == 'completed' else result['receipt']['error']
        with transaction(self.engine) as session:
            row = self.service.get(session, SSMExtraction, key)
            row.status, row.stop_reason = status, reason
        return status

    def review(self, key, reason):
        with transaction(self.engine) as session:
            row = self.service.get(session, SSMExtraction, key)
            if row.status not in ('completed', 'blocked'):
                row.status, row.stop_reason = 'review_required', reason

    def download(self, key):
        report = self.report(key)
        require(report['status'] == 'completed', 'ssm_not_completed')
        file = next(item for item in report['files'] if item['kind'] == 'ssm')
        return self.storage.read(file['relative_path'], file['sha256'])
