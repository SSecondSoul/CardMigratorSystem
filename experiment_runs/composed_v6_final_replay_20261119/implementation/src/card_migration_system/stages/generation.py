"""Sealed source/SSM/prompt/model request and offline response checks.

G1 only: transient candidates, no registered version, graph, or paid call.
Shape checks are NOT San syntax, semantic, visual, or interaction evaluation.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re

from ..adapters.generation import GenerationResponse, OfflineGenerationClient
from ..prompts.generation import PINS, build_generation_messages
from ..reporting.identity import digest


PROTOCOL = 'san-generation-boundary-g1'
MAX_PROMPT_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 2 * 1024 * 1024


class GenerationBoundaryError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise GenerationBoundaryError(code)


def is_sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def is_id(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{32}', value) is not None


def model_configuration(provider, model, *, max_output_tokens=8192, timeout_seconds=240,
                        max_total_tokens=32768, temperature=0.0):
    # An allowlist of fields, not a provider connection configuration. No keys,
    # endpoints, arbitrary headers or additional instructions in this boundary.
    require(type(provider) is str and re.fullmatch('[A-Za-z][A-Za-z0-9_-]{0,39}', provider), 'generation_invalid_provider')
    require(type(model) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:/-]{0,99}', model), 'generation_invalid_model')
    require(type(max_output_tokens) is int and 16 <= max_output_tokens <= 65536, 'generation_invalid_output_budget')
    require(type(max_total_tokens) is int and max_output_tokens <= max_total_tokens <= 2000000,
            'generation_invalid_total_budget')
    require(type(timeout_seconds) is int and 1 <= timeout_seconds <= 300, 'generation_invalid_timeout')
    require(type(temperature) in (float, int) and math.isfinite(temperature) and 0 <= temperature <= 2,
            'generation_invalid_temperature')
    return {'provider': provider, 'model': model, 'temperature': float(temperature),
            'max_output_tokens': max_output_tokens, 'timeout_seconds': timeout_seconds,
            'max_total_tokens': max_total_tokens, 'max_generation_calls': 1,
            'max_repair_calls': 0, 'max_rule_steps': 0}


@dataclass(frozen=True)
class PreparedGeneration:
    payload_bytes: bytes
    request_sha256: str

    def payload(self):
        require(type(self.payload_bytes) is bytes and sha256(self.payload_bytes).hexdigest() == self.request_sha256,
                'generation_request_hash_mismatch')
        try:
            value = json.loads(self.payload_bytes)
        except (ValueError, UnicodeError):
            raise GenerationBoundaryError('generation_invalid_request') from None
        require(type(value) is dict and set(value) == {'protocol', 'source', 'ssm', 'implementation', 'prompt',
                'model_config', 'request_scope', 'external_calls_permitted', 'persistent_registration'},
                'generation_invalid_request')
        require(value['protocol'] == PROTOCOL and value['external_calls_permitted'] is False
                and value['persistent_registration'] is False and value['request_scope'] == 'offline_boundary_only',
                'generation_execution_not_authorized')
        source, ssm = value['source'], value['ssm']
        require(type(source) is dict and set(source) == {'input_id', 'filename', 'path', 'sha256'}
                and is_id(source['input_id']) and is_sha(source['sha256'])
                and type(source['filename']) is str and re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,100}\\.vue', source['filename'])
                and source['path'] == f"inputs/{source['input_id']}/{source['filename']}", 'generation_invalid_source_reference')
        require(type(ssm) is dict and set(ssm) == {'extraction_id', 'request_sha256', 'path', 'sha256', 'schema_version'}
                and is_id(ssm['extraction_id']) and is_sha(ssm['request_sha256']) and is_sha(ssm['sha256'])
                and ssm['schema_version'] == '3.0'
                and ssm['path'] == f"ssm-extractions/{ssm['extraction_id']}/ssm.json", 'generation_invalid_ssm_reference')
        implementation = value['implementation']
        require(type(implementation) is dict and set(implementation) == {'implementation_sha256', 'dependency_lock_sha256',
                'p1_sha256', 'mode', 'fixture_protocol'}
                and all(is_sha(implementation[name]) for name in ('implementation_sha256', 'dependency_lock_sha256', 'p1_sha256'))
                and implementation['mode'] == 'development_stub' and implementation['fixture_protocol'] == 'p2b-control-v1',
                'generation_invalid_implementation')
        config = value['model_config']
        require(type(config) is dict, 'generation_invalid_model_config')
        try:
            checked = model_configuration(**{key: config[key] for key in ('provider', 'model', 'temperature',
                'max_output_tokens', 'timeout_seconds', 'max_total_tokens')})
        except (KeyError, TypeError):
            raise GenerationBoundaryError('generation_invalid_model_config') from None
        require(digest(checked) == digest(config), 'generation_invalid_model_config')
        prompt = value['prompt']
        require(type(prompt) is dict and set(prompt) == {'messages', 'messages_sha256', 'source_pins'},
                'generation_invalid_prompt')
        require(digest(prompt['source_pins']) == digest(PINS), 'generation_prompt_pin_mismatch')
        require(digest(prompt['messages']) == prompt['messages_sha256'], 'generation_prompt_hash_mismatch')
        require(type(prompt['messages']) is list and len(prompt['messages']) == 2
                and all(type(message) is dict and set(message) == {'role', 'content'}
                        and type(message['content']) is str and bool(message['content']) for message in prompt['messages'])
                and [message['role'] for message in prompt['messages']] == ['system', 'user'], 'generation_invalid_prompt')
        return value  # Fresh detached values on every read.


def prepare_generation(*, repository_root, extraction_report, ssm_bytes, source_bytes, source_path, implementation,
                       provider, model, max_output_tokens=8192, timeout_seconds=240, max_total_tokens=32768,
                       temperature=0.0):
    report = extraction_report
    require(type(report) is dict and report.get('status') == 'completed'
            and report.get('migration_quality_status') == 'not_run'
            and type(report.get('contract_evaluation')) is dict and report['contract_evaluation'].get('status') == 'pass'
            and type(report.get('receipt')) is dict and report['receipt'].get('status') == 'completed',
            'generation_completed_extraction_required')
    require(report.get('actual_model_calls') == 0 and type(report.get('actual_model_calls')) is int
            and report.get('production_ready') is False and report.get('langsmith_uploaded') is False,
            'generation_invalid_source_scope')
    source = report['request']['source']
    require(type(source_bytes) is bytes and sha256(source_bytes).hexdigest() == source['source_sha256'],
            'generation_source_hash_mismatch')
    files = [file for file in report['files'] if file['kind'] == 'ssm']
    require(len(files) == 1 and type(ssm_bytes) is bytes and sha256(ssm_bytes).hexdigest() == files[0]['sha256'],
            'generation_ssm_hash_mismatch')
    require(files[0]['relative_path'] == f"ssm-extractions/{report['extraction_id']}/ssm.json",
            'generation_ssm_reference_mismatch')
    require(any(item['path'] == source_path and item['sha256'] == source['source_sha256']
                for item in report['contract_projection']['evidence_index']), 'generation_source_reference_mismatch')
    try:
        ssm = json.loads(ssm_bytes)
    except (ValueError, UnicodeError):
        raise GenerationBoundaryError('generation_invalid_ssm') from None
    require(type(ssm) is dict and ssm.get('schema_version') == '3.0'
            and ssm.get('metadata', {}).get('source_file') == source['filename'], 'generation_invalid_ssm')
    config = model_configuration(provider, model, max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds, max_total_tokens=max_total_tokens, temperature=temperature)
    messages, pins = build_generation_messages(repository_root, ssm)
    require(len(json.dumps(messages, ensure_ascii=True).encode()) <= MAX_PROMPT_BYTES, 'generation_prompt_too_large')
    payload = {'protocol': PROTOCOL, 'source': {'input_id': source['input_id'], 'filename': source['filename'],
        'path': source_path, 'sha256': source['source_sha256']},
        'ssm': {'extraction_id': report['extraction_id'], 'request_sha256': report['request_sha256'],
                'path': files[0]['relative_path'], 'sha256': files[0]['sha256'], 'schema_version': '3.0'},
        'implementation': implementation, 'prompt': {'messages': messages, 'messages_sha256': digest(messages),
        'source_pins': pins}, 'model_config': config, 'request_scope': 'offline_boundary_only',
        'external_calls_permitted': False, 'persistent_registration': False}
    content = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()
    result = PreparedGeneration(content, sha256(content).hexdigest())
    result.payload()
    return result


def run_offline_generation(prepared, client):
    require(isinstance(client, OfflineGenerationClient), 'generation_offline_client_required')
    request = prepared.payload()
    config = request['model_config']
    # No automatic retry, even for test doubles. Durable call-start/receipt
    # accounting must precede any future real transport implementation.
    try:
        response = client.generate(prepared.payload())
    except Exception:
        raise GenerationBoundaryError('generation_client_outcome_unknown_no_retry') from None
    return check_generation_response(prepared, response)


def check_generation_response(prepared, response):
    """Pure replay of output checks; never invokes a client or executes San."""
    config = prepared.payload()['model_config']
    require(type(response) is GenerationResponse, 'generation_invalid_response')
    require(response.provider == config['provider'] and response.model == config['model'], 'generation_model_identity_mismatch')
    require(response.finish_reason == 'stop', 'generation_incomplete_output')
    for count in (response.input_tokens, response.output_tokens):
        require(count is None or (type(count) is int and count >= 0), 'generation_invalid_usage')
    if response.output_tokens is not None:
        require(response.output_tokens <= config['max_output_tokens'], 'generation_output_budget_exceeded')
    if response.input_tokens is not None and response.output_tokens is not None:
        require(response.input_tokens + response.output_tokens <= config['max_total_tokens'], 'generation_total_budget_exceeded')
    require(type(response.code) is str, 'generation_invalid_output')
    try:
        content = response.code.encode('utf-8')
    except UnicodeError:
        raise GenerationBoundaryError('generation_invalid_output') from None
    require(0 < len(content) <= MAX_OUTPUT_BYTES and '\x00' not in response.code, 'generation_invalid_output')
    require(re.fullmatch(r'\s*<template>[\s\S]+?</template>\s*<script>[\s\S]+?</script>\s*<style>[\s\S]*?</style>\s*',
                         response.code) is not None, 'generation_output_not_plain_sfc')
    return {'schema_version': 1, 'request_sha256': prepared.request_sha256, 'status': 'offline_response_checked',
        'candidate': {'code': response.code, 'sha256': sha256(content).hexdigest(), 'size_bytes': len(content),
                      'provenance': 'offline_client_test', 'parent_revision_id': None},
        'usage': {'input_tokens': response.input_tokens, 'output_tokens': response.output_tokens},
        'budget_status': 'usage_checked' if response.input_tokens is not None and response.output_tokens is not None else 'usage_unknown',
        'actual_model_calls': 0, 'offline_client_invocations': 1, 'langsmith_uploaded': False,
        'migration_quality_status': 'not_run', 'production_ready': False, 'persistent_registration': False,
        'contract_revision': None, 'limitations': ['shape_only_not_san_compile', 'no_durable_receipt_or_version',
            'no_real_transport_or_token_preflight', 'timeout_is_configuration_not_in_process_enforcement']}
