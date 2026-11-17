"""Read-only preview over audited registered SSM, no persistence or model calls."""
from .extractions import ExtractionService
from .service import Service
from ..stages.generation import prepare_generation


def prepare_registered_generation(service, extraction_id, **model_options):
    ledger = ExtractionService(service)
    report = ledger.report(extraction_id)
    source = ledger.snapshot(extraction_id)
    return prepare_generation(repository_root=service.settings.repository_root, extraction_report=report,
        ssm_bytes=ledger.download(extraction_id), source_bytes=service.storage.read(source['source_path'], source['source_sha256']),
        source_path=source['source_path'], implementation=service.implementation_binding(), **model_options)


def generation_preview(settings, extraction_id, **model_options):
    service = Service(settings)
    try:
        prepared = prepare_registered_generation(service, extraction_id, **model_options)
        request = prepared.payload()
        return {'status': 'generation_request_preview', 'extraction_id': extraction_id,
            'request_sha256': prepared.request_sha256, 'prompt_sha256': request['prompt']['messages_sha256'],
            'source_sha256': request['source']['sha256'], 'ssm_sha256': request['ssm']['sha256'],
            'model_config': request['model_config'], 'actual_model_calls': 0, 'langsmith_uploaded': False,
            'external_calls_permitted': False, 'persistent_registration': False, 'production_ready': False,
            'migration_quality_status': 'not_run', 'scope': 'read_only_preview_not_a_registered_generation'}
    finally:
        service.close()
