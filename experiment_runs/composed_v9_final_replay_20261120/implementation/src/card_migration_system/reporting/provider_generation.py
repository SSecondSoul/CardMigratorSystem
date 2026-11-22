"""G3 pure contract projection, NOT wired into G2 or a live registered service.

Caller must obtain bytes from a future audited provider ledger. These hashes
prove consistency, not who produced bytes or that a snapshot predates a call.
Tests use synthetic complete evidence, never experimental/model-run evidence.
"""
from hashlib import sha256
import json
import re

from ..adapters.qwen_transport import Exchange, inspect_exchange
from ..reporting.identity import digest
from ..stages.generation import require


POLICY = 'provider-generation-artifact-projection-g3-v1'


def freeze_provider_contract(api, plan, generation_id):
    require(type(generation_id) is str and re.fullmatch('[0-9a-f]{32}', generation_id), 'provider_invalid_generation_id')
    values = plan.verify()
    request = api.MigrationRequest(run_id='generation:' + generation_id, sample_id='input:' + values['source']['input_id'],
        source=api.FileFingerprint(path=values['source']['path'], sha256=values['source']['sha256']),
        protocol_sha256=digest({'id': POLICY, 'generation_only': True, 'quality_pass_permitted': False}),
        implementation_sha256=digest(values['implementation']), prompt_set_sha256=digest(values['prompt']),
        evaluation_policy_sha256=digest({'id': POLICY, 'target_checks': 'not_run'}),
        model_config_sha256=digest({'config': values['model_config'], 'endpoint': plan.endpoint,
            'wire_sha256': sha256(plan.wire_body).hexdigest()}), ssm_schema_version='3.0',
        budget=api.Budget(max_model_repair_calls=0, max_rule_steps=0,
            max_total_tokens=values['model_config']['max_total_tokens'],
            max_elapsed_seconds=values['model_config']['timeout_seconds']))
    return {'snapshot_version': 1, 'policy': POLICY, 'generation_id': generation_id,
        'plan_sha256': plan.fingerprint, 'contract_request': request.to_dict()}


def project_provider_artifact(api, plan, generation_id, *, artifacts, source_bytes, ssm_bytes):
    """Consistency check of a supplied immutable bundle, not a registration API."""
    plan.preflight()
    values = plan.verify()
    require(type(artifacts) is dict and set(artifacts) == {'request', 'receipt', 'response', 'candidate'},
            'provider_evidence_missing')
    refs = {}
    for kind, artifact in artifacts.items():
        suffix = 'candidate.san' if kind == 'candidate' else kind + '.json'
        path = f'provider-generations/{generation_id}/{suffix}'
        require(type(artifact) is dict and set(artifact) == {'path', 'content'}
            and artifact['path'] == path and type(artifact['content']) is bytes, 'provider_evidence_reference_invalid')
        refs[kind] = {'path': path, 'sha256': sha256(artifact['content']).hexdigest()}
    require(type(source_bytes) is bytes and sha256(source_bytes).hexdigest() == values['source']['sha256']
        and type(ssm_bytes) is bytes and sha256(ssm_bytes).hexdigest() == values['ssm']['sha256'], 'provider_source_evidence_mismatch')
    snapshot = json.loads(artifacts['request']['content'])
    require(digest(snapshot) == digest(freeze_provider_contract(api, plan, generation_id)), 'provider_snapshot_mismatch')
    api.load_contract(snapshot['contract_request'])
    receipt = json.loads(artifacts['receipt']['content'])
    require(type(receipt) is dict and set(receipt) == {'schema_version', 'generation_id', 'attempt_id', 'execution_mode',
            'plan_sha256', 'file_refs', 'outcome'} and type(receipt['schema_version']) is int
        and receipt['schema_version'] == 1 and receipt['generation_id'] == generation_id
        and receipt['attempt_id'] == generation_id + ':generate:1' and receipt['execution_mode'] == 'provider_https'
        and receipt['plan_sha256'] == plan.fingerprint, 'provider_receipt_mismatch')
    require(digest(receipt['file_refs']) == digest({kind: refs[kind] for kind in ('request', 'response', 'candidate')}),
            'provider_receipt_reference_mismatch')
    checked = inspect_exchange(plan, Exchange(200, artifacts['response']['content']), provenance='provider_https')
    require(digest(checked) == digest(receipt['outcome']) and checked['provenance'] == 'provider_https'
        and checked['status'] == 'response_checked_not_migration_pass' and checked['actual_model_calls'] == 1
        and checked['usage'] is not None and not checked['diagnostics'], 'provider_response_not_accepted')
    require(checked['candidate']['code'].encode('utf-8') == artifacts['candidate']['content'], 'provider_candidate_mismatch')
    evidence = [values['source']['path'], values['ssm']['path'], *(refs[kind]['path'] for kind in refs)]
    revision = api.ArtifactRevision(revision_id='generation:' + generation_id + ':initial',
        artifact=api.FileFingerprint(**refs['candidate']), origin=api.ArtifactOrigin.GENERATION,
        parent_revision_id=None, request_ref=refs['request']['path'], evidence_refs=tuple(evidence))
    wire = revision.to_dict()
    require(digest(api.load_contract(wire).to_dict()) == digest(wire), 'provider_contract_roundtrip_failed')
    return {'contract_revision': wire, 'usage': checked['usage'], 'migration_quality_status': 'not_run',
        'scope': 'generation_artifact_only_not_quality_pass', 'production_ready': False}
