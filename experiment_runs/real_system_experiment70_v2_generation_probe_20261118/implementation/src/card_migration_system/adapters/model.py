"""One explicit request, no retries. Persist start/response in application before use."""
from dataclasses import dataclass
import json
import os
import re
import ssl
from urllib import request, error
from .qwen_transport import valid_endpoint
from ..application.service import ServiceError


@dataclass
class ModelExchange:
    status: int
    body: bytes


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


class QwenModel:
    def __init__(self, profile): self.profile = profile

    def preflight(self):
        config = self.profile['model']
        if not config['network_enabled']: raise ServiceError('model_network_disabled')
        key = os.environ.get(config['api_key_env'], '')
        if not key or '\r' in key or '\n' in key: raise ServiceError('model_api_key_missing')
        valid_endpoint(config['endpoint'])

    def exchange(self, messages):
        self.preflight()
        config = self.profile['model']
        body = json.dumps({'model': config['model'], 'messages': messages, 'temperature': 0,
            'max_tokens': config['max_output_tokens'], 'enable_thinking': False, 'stream': False}).encode()
        if len(body) > 4 * 1024 * 1024: raise ServiceError('model_request_too_large')
        req = request.Request(config['endpoint'], data=body, headers={
            'Content-Type': 'application/json', 'Authorization': 'Bearer ' + os.environ[config['api_key_env']]})
        opener = request.build_opener(request.ProxyHandler({}), NoRedirect(),
            request.HTTPSHandler(context=ssl.create_default_context()))
        try:
            with opener.open(req, timeout=config['timeout_seconds']) as response:
                return ModelExchange(response.status, response.read(4 * 1024 * 1024 + 1))
        except error.HTTPError as failure:
            return ModelExchange(failure.code, failure.read(4 * 1024 * 1024 + 1))
        except Exception:
            # Do not expose API key or echo source from a transport exception.
            raise ServiceError('model_response_unknown_no_automatic_retry') from None


def inspect_response(exchange, model):
    result = {'valid': False, 'usage': None, 'error': 'invalid_model_response', 'code': None}
    if len(exchange.body) > 4 * 1024 * 1024: return result
    try:
        payload = json.loads(exchange.body)
        usage = payload.get('usage')
        if (isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0 for k in
            ('prompt_tokens', 'completion_tokens', 'total_tokens')) and
            usage['prompt_tokens'] + usage['completion_tokens'] == usage['total_tokens']): result['usage'] = usage
        if exchange.status != 200: return {**result, 'error': 'provider_http_error'}
        choices = payload['choices']
        if len(choices) != 1 or choices[0]['finish_reason'] != 'stop': return {**result, 'error': 'model_output_incomplete'}
        message = choices[0]['message']
        code = message['content']
        if payload.get('model') != model or message.get('role') != 'assistant' or message.get('tool_calls') or message.get('refusal') or message.get('reasoning_content'):
            return result
        if not isinstance(code, str) or not code.strip() or len(code.encode()) > 2 * 1024 * 1024: return result
        code = re.sub(r'^```[^\n]*\n|\n```\s*$', '', code.strip())
        if not all(re.search(r'<' + tag + r'\b', code) for tag in ('template', 'script', 'style')): return result
        return {**result, 'valid': True, 'error': None, 'code': code}
    except (ValueError, KeyError, TypeError, IndexError): return result
