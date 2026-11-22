"""Explicit offline extraction probes over registered immutable inputs.

Separate from fixture runs and their P1 reports; no database schema mutation.
"""
import json
import re
from uuid import uuid4

from ..adapters.ssm import ExtractionError, SSMExtractor, source_binding
from ..application.service import Service
from ..application.storage import Storage
from ..persistence.database import transaction
from ..persistence.schema_v1 import Run, SourceInput, Task


def json_bytes(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False).encode('utf-8')


def extract_registered_input(settings, *, input_id=None, run_id=None):
    if (input_id is None) == (run_id is None):
        raise ExtractionError('ssm_one_source_reference_required')
    reference = input_id if input_id is not None else run_id
    if type(reference) is not str or not re.fullmatch(r'[0-9a-f]{32}', reference):
        raise ExtractionError('ssm_invalid_source_reference')
    service = Service(settings)
    try:
        with transaction(service.engine) as session:
            if run_id is not None:
                run = service.get(session, Run, run_id)
                task = service.get(session, Task, run.task_id)
                input_id = task.input_id
            row = service.get(session, SourceInput, input_id)
            source_reference = {'input_id': row.id, 'referenced_run_id': run_id,
                                'filename': row.filename, 'source_sha256': row.sha256}
            source = service.storage.read(row.relative_path, row.sha256)
    finally:
        service.close()
    # Auxiliary offline evidence, NOT a revision/evaluation of the fixture run.
    # This directory is deliberately outside both DBs and the registered-artifact backup.
    storage = Storage(settings.runtime_dir / 'ssm-extractions')
    extraction_id = uuid4().hex
    storage.locate(extraction_id).mkdir(parents=True, exist_ok=False)
    request = {'schema_version': 1, 'extraction_id': extraction_id, 'scope': 'offline_ssm_extraction_probe',
               'source': source_reference, 'actual_model_calls': 0, 'production_ready': False}
    request_sha256 = storage.put(f'{extraction_id}/request.json', json_bytes(request))
    storage.put(f'{extraction_id}/source.vue', source)
    result = {'schema_version': 1, 'extraction_id': extraction_id, 'scope': request['scope'],
              'request_sha256': request_sha256, 'source': source_reference,
              'actual_model_calls': 0, 'langsmith_uploaded': False, 'production_ready': False,
              'migration_quality_status': 'not_run', 'ssm': None, 'binding': None}
    try:
        before = source_binding(settings.repository_root)
        extracted = SSMExtractor(settings.repository_root).extract(source, row.filename, row.sha256)
        if before != extracted['binding']['legacy_files_sha256']:
            raise ExtractionError('ssm_implementation_drift')
        result.update(status='completed', binding=extracted['binding'],
                      binding_sha256=extracted['binding_sha256'], limitations=extracted['limitations'])
        relative = f'{extraction_id}/ssm.json'
        fingerprint = storage.put(relative, json_bytes(extracted['ssm']))
        result['ssm'] = {'relative_path': 'ssm.json', 'sha256': fingerprint}
    except ExtractionError as error:
        result.update(status='blocked', error=str(error))
    # Receipt written last. A missing receipt means incomplete, never implicit success.
    receipt_sha256 = storage.put(f'{extraction_id}/receipt.json', json_bytes(result))
    return {'status': result['status'], 'extraction_id': extraction_id,
            'directory': str(storage.locate(extraction_id)), 'receipt_sha256': receipt_sha256,
            'ssm_sha256': result['ssm']['sha256'] if result['ssm'] else None,
            'error': result.get('error'), 'actual_model_calls': 0, 'production_ready': False}
