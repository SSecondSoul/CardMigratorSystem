"""G3 transport boundary. Not wired to a live CLI, worker or generation ledger.

No environment/key discovery, redirects, proxy inheritance, retries or tracing.
Explicit permits correlate trusted caller facts; they are NOT authorization or a
durable at-most-once service. That integration must precede any real execution.
"""
from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
import ssl
from urllib import error, request
from urllib.parse import urlsplit

from ..reporting.identity import digest
from ..stages.generation import GenerationBoundaryError, GenerationResponse, check_generation_response, require


ENDPOINT = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
PROFILE = 'qwen-plus-text-nonthinking-g3-v1'


def valid_endpoint(url):
    require(type(url) is str and len(url) <= 240, 'qwen_invalid_endpoint')
    parts = urlsplit(url)
    require(parts.geturl() == url and parts.scheme == 'https' and not parts.username and not parts.password
        and not parts.query and not parts.fragment and parts.path == '/compatible-mode/v1/chat/completions'
        and (parts.netloc == 'dashscope.aliyuncs.com'
             or re.fullmatch(r'ws-[a-z0-9-]+\.cn-beijing\.maas\.aliyuncs\.com', parts.netloc)), 'qwen_invalid_endpoint')
    return url


@dataclass(frozen=True)
class InputTokenBound:
    messages_sha256: str
    model: str
    count: int
    method: str  # exact / upper_bound; estimates must not unlock a real call.
    counter_id: str
    counter_sha256: str
    includes_chat_wrapper: bool


@dataclass(frozen=True)
class CallPermit:
    plan_sha256: str
    attempt_id: str
    # These are declarations from a FUTURE trusted ledger/approval integration,
    # not a user-facing boolean authorization mechanism.
    durable_start_recorded: bool
    explicit_call_approved: bool


@dataclass(frozen=True)
class QwenPlan:
    prepared: object = field(repr=False)
    wire_body: bytes = field(repr=False)
    endpoint: str
    bound: InputTokenBound | None
    fingerprint: str

    def verify(self):
        rebuilt = build_qwen_plan(self.prepared, endpoint=self.endpoint, token_bound=self.bound)
        require(rebuilt.fingerprint == self.fingerprint and rebuilt.wire_body == self.wire_body, 'qwen_plan_drift')
        return self.prepared.payload()

    def preflight(self):
        self.verify()
        require(self.bound is not None, 'qwen_input_token_bound_missing')
        require(self.bound.method in ('exact', 'upper_bound') and self.bound.includes_chat_wrapper is True,
                'qwen_input_token_bound_unverified')
        config = self.prepared.payload()['model_config']
        # Reservation is a token policy, not a currency/price estimate. Strict
        # post-response checks still catch provider overrun or a wrong bound.
        require(self.bound.count + config['max_output_tokens'] <= config['max_total_tokens'], 'qwen_preflight_budget_exceeded')


def build_qwen_plan(prepared, *, endpoint=ENDPOINT, token_bound=None):
    value = prepared.payload()
    config = value['model_config']
    require(config['provider'] == 'qwen' and re.fullmatch(r'qwen-plus(?:-\d{4}-\d{2}-\d{2})?', config['model']),
            'qwen_model_profile_unsupported')
    endpoint = valid_endpoint(endpoint)
    if token_bound is not None:
        require(type(token_bound) is InputTokenBound and type(token_bound.count) is int and token_bound.count >= 0
            and token_bound.messages_sha256 == value['prompt']['messages_sha256'] and token_bound.model == config['model']
            and type(token_bound.counter_id) is str and re.fullmatch('[A-Za-z0-9_.:-]{1,100}', token_bound.counter_id)
            and type(token_bound.counter_sha256) is str and re.fullmatch('[0-9a-f]{64}', token_bound.counter_sha256)
            and token_bound.method in ('exact', 'upper_bound', 'estimate')
            and type(token_bound.includes_chat_wrapper) is bool, 'qwen_invalid_token_bound')
    body = {'model': config['model'], 'messages': value['prompt']['messages'], 'temperature': config['temperature'],
        'max_tokens': config['max_output_tokens'], 'stream': False, 'enable_thinking': False}
    wire = json.dumps(body, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()
    bound_values = None if token_bound is None else vars(token_bound)
    fingerprint = digest({'profile': PROFILE, 'prepared_sha256': prepared.request_sha256,
        'endpoint': endpoint, 'wire_sha256': sha256(wire).hexdigest(), 'input_bound': bound_values,
        'timeout_seconds': config['timeout_seconds']})
    return QwenPlan(prepared, wire, endpoint, token_bound, fingerprint)


@dataclass(frozen=True)
class Exchange:
    status: int
    body: bytes = field(repr=False)


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class QwenHTTPSClient:
    """Explicit credential in memory only. Not an OfflineGenerationClient."""
    def __init__(self, api_key, *, network_enabled=False):
        require(type(api_key) is str and re.fullmatch('[!-~]{8,512}', api_key), 'qwen_invalid_credential')
        require(type(network_enabled) is bool, 'qwen_invalid_network_setting')
        self._api_key = api_key
        self._network_enabled = network_enabled
        self._used_attempts = set()

    def __repr__(self):
        return 'QwenHTTPSClient(credential=<redacted>)'

    def send(self, plan, permit):
        require(self._network_enabled is True, 'qwen_network_disabled')
        require(type(plan) is QwenPlan and type(permit) is CallPermit and permit.plan_sha256 == plan.fingerprint
            and type(permit.attempt_id) is str and re.fullmatch('[0-9a-f]{32}:generate:1', permit.attempt_id)
            and permit.durable_start_recorded is True and permit.explicit_call_approved is True,
            'qwen_call_permit_required')
        plan.preflight()
        require(permit.attempt_id not in self._used_attempts, 'qwen_attempt_already_used')
        self._used_attempts.add(permit.attempt_id)  # Even unknown outcomes consume the local slot.
        try:
            exchange = self._post(plan)
        except Exception:
            return unknown_outcome(plan, 'qwen_transport_outcome_unknown', provenance='provider_https')
        return inspect_exchange(plan, exchange, provenance='provider_https')

    def _post(self, plan):
        # No default system proxy/cookie handler; verify TLS; never forward
        # Authorization to a redirect. Error bodies are not echoed or logged.
        opener = request.build_opener(request.ProxyHandler({}), NoRedirect(),
            request.HTTPSHandler(context=ssl.create_default_context()))
        req = request.Request(plan.endpoint, data=plan.wire_body, method='POST', headers={
            'Authorization': 'Bearer ' + self._api_key, 'Content-Type': 'application/json', 'Accept': 'application/json'})
        timeout = plan.prepared.payload()['model_config']['timeout_seconds']
        try:
            response = opener.open(req, timeout=timeout)
        except error.HTTPError as exc:
            response = exc
        with response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            return Exchange(response.status, raw)


def unknown_outcome(plan, code, *, provenance):
    return {'schema_version': 1, 'plan_sha256': plan.fingerprint, 'provenance': provenance,
        'status': 'review_required', 'diagnostics': [code], 'response_sha256': None, 'provider_response_id': None,
        'actual_model': None, 'finish_reason': None, 'usage': None, 'candidate': None,
        'transport_attempts': 1, 'actual_model_calls': 0 if provenance == 'offline_transport_test' else None,
        'migration_quality_status': 'not_run', 'production_ready': False}


def inspect_exchange(plan, exchange, *, provenance='offline_transport_test'):
    """Pure response replay. Test provenance is default and never promotable."""
    require(provenance in ('offline_transport_test', 'provider_https'), 'qwen_invalid_provenance')
    value = plan.verify()
    result = unknown_outcome(plan, 'qwen_invalid_response', provenance=provenance)
    if type(exchange) is not Exchange or type(exchange.body) is not bytes or type(exchange.status) is not int:
        return result
    result['response_sha256'] = sha256(exchange.body).hexdigest()
    if len(exchange.body) > MAX_RESPONSE_BYTES:
        result['diagnostics'] = ['qwen_response_too_large']
        return result
    if exchange.status != 200:
        result['diagnostics'] = ['qwen_http_error']
        return result  # No guessing token usage or zero charge from an HTTP status.
    try:
        decoded = json.loads(exchange.body)
        if type(decoded) is not dict:
            return result
        response_id = decoded.get('id')
        if type(response_id) is str and re.fullmatch('[A-Za-z0-9_-]{1,180}', response_id):
            result['provider_response_id'] = response_id
        actual_model = decoded.get('model')
        if type(actual_model) is str and re.fullmatch('[A-Za-z0-9_.:/-]{1,100}', actual_model):
            result['actual_model'] = actual_model
        usage = decoded.get('usage')
        if (type(usage) is dict and all(type(usage.get(name)) is int and usage[name] >= 0
                for name in ('prompt_tokens', 'completion_tokens', 'total_tokens'))
                and usage['total_tokens'] == usage['prompt_tokens'] + usage['completion_tokens']):
            result['usage'] = {name: usage[name] for name in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
        choices = decoded.get('choices')
        if type(choices) is not list or len(choices) != 1 or type(choices[0]) is not dict:
            return result
        choice = choices[0]
        message = choice.get('message')
        if type(message) is not dict or message.get('role') != 'assistant':
            return result
        finish = choice.get('finish_reason')
        result['finish_reason'] = finish if finish in ('stop', 'length', 'content_filter', 'tool_calls') else None
        result['actual_model_calls'] = 0 if provenance == 'offline_transport_test' else 1
        codes = []
        if result['actual_model'] != value['model_config']['model']:
            codes.append('qwen_model_identity_mismatch')
        if result['provider_response_id'] is None:
            codes.append('qwen_response_identity_missing')
        if result['usage'] is None:
            codes.append('qwen_usage_missing_or_invalid')
        if message.get('tool_calls') or message.get('function_call') or message.get('refusal') or message.get('reasoning_content'):
            codes.append('qwen_nontext_response_unsupported')
        details = usage.get('completion_tokens_details') if type(usage) is dict else None
        if details is not None:
            reasoning = details.get('reasoning_tokens', 0) if type(details) is dict else None
            if type(reasoning) is not int or reasoning != 0:
                codes.append('qwen_reasoning_usage_unsupported')
        # Known usage survives invalid content, truncation and budget failure.
        if result['usage'] is not None:
            try:
                plan.preflight()
            except GenerationBoundaryError as exc:
                codes.append(str(exc))
            if plan.bound is not None and result['usage']['prompt_tokens'] > plan.bound.count:
                codes.append('qwen_input_token_bound_exceeded')
            try:
                checked = check_generation_response(plan.prepared, GenerationResponse(message.get('content'), 'qwen',
                    result['actual_model'], finish, result['usage']['prompt_tokens'], result['usage']['completion_tokens']))
            except GenerationBoundaryError as exc:
                codes.append(str(exc))
            else:
                if not codes:
                    result['candidate'] = {**checked['candidate'], 'provenance': provenance}
                    result['status'] = 'response_checked_not_migration_pass'
        result['diagnostics'] = codes or ([] if result['candidate'] else ['qwen_invalid_response'])
        return result
    except (ValueError, TypeError, KeyError):
        return result
