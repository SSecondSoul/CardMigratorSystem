"""Source-only P1 values from audited extraction facts, never a migrated San.

No I/O or backfill. Keep v1 policy definitions stable; use a new version when
changing classification. Legacy requests get an evaluation, not a fake request.
"""
import re

from .identity import digest
from .request_snapshot import DIMENSIONS


PROTOCOL = 'registered-ssm-graph-v2'
PROJECTOR = 'ssm-source-evidence-v1'
SOURCE_ERRORS = ('ssm_sfc_syntax_error', 'ssm_template_syntax_error', 'ssm_script_syntax_error',
                 'ssm_template_required', 'ssm_invalid_utf8', 'ssm_invalid_input')
UNSUPPORTED = ('ssm_script_setup_not_supported', 'ssm_custom_blocks_not_supported',
               'ssm_external_blocks_not_supported', 'ssm_template_language_not_supported',
               'ssm_script_language_not_supported', 'ssm_single_element_root_required')
INFRASTRUCTURE = ('ssm_node_missing', 'ssm_dependency_missing', 'ssm_dependency_version_mismatch',
                  'ssm_extractor_missing', 'ssm_extractor_or_lock_missing', 'ssm_process_unavailable',
                  'ssm_node_timeout', 'ssm_extraction_timeout', 'ssm_worker_failed')
EVIDENCE = ('ssm_output_shape_invalid', 'ssm_worker_invalid_response', 'ssm_runtime_binding_invalid',
            'ssm_source_hash_mismatch', 'ssm_implementation_drift', 'ssm_dependency_drift',
            'ssm_adapter_drift', 'ssm_node_drift', 'ssm_extractor_path_invalid')


def descriptors(request):
    return {
        'protocol': {'id': PROTOCOL, 'source_only': True, 'san_generation_permitted': False,
                     'dependency_resolution': 'not_executed', 'fixture_run_is_reference_only': True},
        'prompt_set': {'mode': 'disabled', 'templates': [], 'real_prompt_execution': False},
        'model_config': {'provider': None, 'external_calls_permitted': False, 'actual_model_calls': 0},
        'evaluation_policy': {'id': PROJECTOR, 'required_dimensions': list(DIMENSIONS),
            'source_pass_scope': 'bound_ssm_v3_artifact_extracted_not_semantic_equivalence_or_coverage',
            'target_evaluators_executed': [],
            'source_errors': list(SOURCE_ERRORS), 'unsupported': list(UNSUPPORTED),
            'infrastructure': list(INFRASTRUCTURE), 'evidence': list(EVIDENCE),
            'unclassified_errors': 'unknown_blocking_no_target_repair'},
    }


def build_snapshot(api, request, source_path):
    """Called before the parser, and reconstructed ONLY for strict validation."""
    values = descriptors(request)
    contract = api.MigrationRequest(
        run_id='ssm:' + request['extraction_id'], sample_id='input:' + request['source']['input_id'],
        source=api.FileFingerprint(path=source_path, sha256=request['source']['source_sha256']),
        protocol_sha256=digest(values['protocol']),
        implementation_sha256=digest(request['binding']),
        prompt_set_sha256=digest(values['prompt_set']),
        evaluation_policy_sha256=digest(values['evaluation_policy']),
        model_config_sha256=digest(values['model_config']), ssm_schema_version='3.0',
        budget=api.Budget(max_model_repair_calls=0, max_rule_steps=0, max_total_tokens=0))
    return {'snapshot_version': 1, 'hash_format': 'canonical_json_utf8_ascii_v1',
            'request': contract.to_dict(), 'descriptors': values}


def require(condition):
    if not condition:
        raise ValueError('ssm_contract_evidence_invalid')


def classification(code):
    if code in SOURCE_ERRORS:
        return 'fail', 'source'
    if code in UNSUPPORTED:
        return 'unsupported', 'source'
    if code in INFRASTRUCTURE:
        return 'execution_error', 'infrastructure'
    if code in EVIDENCE:
        return 'blocked', 'evidence'
    return 'unknown', 'unknown'


def project_extraction(api, row, receipt):
    """Caller has audited one DB snapshot and ALL referenced bytes first."""
    key, request = row['id'], row['request']
    fields = {'schema_version', 'protocol', 'extraction_id', 'source', 'binding',
              'actual_model_calls', 'langsmith_uploaded', 'production_ready'}
    if request['protocol'] == PROTOCOL:
        fields.add('contract_snapshot')
    require(set(request) == fields)
    evidence = [{'path': row['source_path'], 'sha256': row['source_sha256']}]
    evidence.extend({'path': file['relative_path'], 'sha256': file['sha256']} for file in row['files'])
    refs = tuple(item['path'] for item in evidence)
    kwargs = dict(evaluation_id=f'ssm:{key}:source', dimension='ssm_extraction',
                  evidence_level=api.EvidenceLevel.STATIC, evidence_refs=refs,
                  reason='No completed extraction receipt; static names the intended evidence category.')
    status, origin = 'not_run', None
    if receipt is not None:
        kwargs['evaluator_version'] = PROJECTOR
        if receipt['status'] == 'completed':
            binding = receipt['binding']
            runtime = binding.get('runtime')
            require(type(runtime) is dict and type(runtime.get('node')) is str
                    and type(runtime.get('python')) is str and type(runtime.get('packages')) is dict
                    and set(runtime['packages']) == {'@vue/compiler-sfc', '@vue/compiler-dom', '@babel/parser', '@babel/traverse'}
                    and all(type(version) is str and version for version in runtime['packages'].values())
                    and type(runtime.get('loaded_module_sha256')) is dict and bool(runtime['loaded_module_sha256']))
            require(all(type(path) is str and path.startswith('node_modules/') and '\\' not in path
                        and '..' not in path.split('/') and type(value) is str and re.fullmatch('[0-9a-f]{64}', value)
                        for path, value in runtime['loaded_module_sha256'].items()))
            require(all(type(binding.get(name)) is str and re.fullmatch('[0-9a-f]{64}', binding[name])
                        for name in ('node_executable_sha256', 'python_executable_sha256')))
            status = 'pass'
            kwargs.update(environment_sha256=digest({'runtime': runtime,
                'node_executable_sha256': binding['node_executable_sha256'],
                'python_executable_sha256': binding['python_executable_sha256']}),
                metrics={'ssm_schema_version': '3.0', 'ssm_sha256': receipt['ssm_sha256']},
                reason='Source-only extraction artifact and registered evidence verified; '
                       'no source semantic equivalence, syntax coverage, San generation or migration pass asserted.')
        else:
            status, origin = classification(receipt['error'])
            kwargs.update(reason=f"Extraction stopped: {receipt['error']}; no target repair authorization.",
                diagnostics=(api.Diagnostic(diagnostic_id=f'ssm:{key}:source-diagnostic',
                    code=receipt['error'], stage='ssm_extraction', origin=api.DiagnosticOrigin(origin),
                    severity=api.Severity.ERROR, blocking=True, repairability=api.Repairability.NOT_REPAIRABLE,
                    location=row['source_path'] if origin == 'source' else '', evidence_refs=refs),))
    evaluation = api.EvaluationResult(status=api.Status(status), **kwargs)
    wire_evaluation = evaluation.to_dict()
    require(digest(api.load_contract(wire_evaluation).to_dict()) == digest(wire_evaluation))
    projection = {'schema_version': 1, 'projector': PROJECTOR, 'scope': 'source_only_no_san_revision',
                  'evidence_index': evidence, 'source_extraction_status': status,
                  'omitted_from_p1': ['ssm_artifact_as_san_revision'], 'production_ready': False}
    if request['protocol'] == 'registered-ssm-graph-v1':
        require('contract_snapshot' not in request)
        projection.update(status='partial_evaluation_only', reason='historical_request_snapshot_missing_no_backfill')
        return {'contract_evaluation': wire_evaluation, 'contract_report': None, 'contract_projection': projection}
    require(request['protocol'] == PROTOCOL)
    # Validation is pure. Never assign the reconstructed snapshot to a historical row.
    require(digest(request.get('contract_snapshot')) == digest(build_snapshot(api, request, row['source_path'])))
    contract_request = api.load_contract(request['contract_snapshot']['request'])
    if row['status'] == 'review_required':
        report_status = api.Status.BLOCKED
    elif receipt is not None and status != 'pass':
        report_status = api.Status.EXECUTION_ERROR if status == 'execution_error' else api.Status.BLOCKED
    else:
        report_status = api.Status.NOT_RUN
    unexecuted = tuple(api.EvaluationResult(evaluation_id=f'ssm:{key}:not-run:{dimension}', dimension=dimension,
        status=api.Status.NOT_RUN, evidence_level=api.EvidenceLevel(level),
        reason='Target migration check not executed; intended category only, no generated San revision.')
        for dimension, level in DIMENSIONS.items() if dimension != 'ssm_extraction')
    review = ()
    if row['status'] == 'review_required':
        review = (api.EvaluationResult(evaluation_id=f'ssm:{key}:execution-review', dimension='extraction_execution',
            status=api.Status.BLOCKED, evidence_level=api.EvidenceLevel.STATIC,
            reason='Extraction execution requires review: ' + row['stop_reason'], evidence_refs=refs),)
    report = api.RunReport(request=contract_request, status=report_status,
        stop_reason=row['stop_reason'] or f"extraction_{row['status']}; migration_not_run",
        required_dimensions=tuple(DIMENSIONS), attempt_results=review, final_results=(evaluation, *unexecuted),
        cost=api.CostRecord(generation_calls=0, model_repair_calls=0, rule_steps=0, candidate_rechecks=0,
                            generation_tokens=0, repair_tokens=0), evidence_refs=refs)
    wire_report = report.to_dict()
    require(digest(api.load_contract(wire_report).to_dict()) == digest(wire_report))
    projection.update(status='validated_source_stage_projection', reason='frozen_request_and_source_evidence_only')
    return {'contract_evaluation': wire_evaluation, 'contract_report': wire_report, 'contract_projection': projection}
