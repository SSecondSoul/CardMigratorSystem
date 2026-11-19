"""Documented service-ceiling reservation, NOT a tokenizer or billing guarantee.

For accepted text-only requests we conservatively reserve the ENTIRE documented
context window as input. No character/token ratios or synthetic caller bounds.
Provider enforcement and the reviewed catalog remain explicit assumptions.
"""
from datetime import datetime
import time

from .qwen_transport import InputTokenBound, build_qwen_plan
from ..reporting.identity import digest
from ..stages.generation import GenerationBoundaryError, require


CATALOG = {
    'policy_id': 'model-studio-text-context-ceiling-20261116-v1',
    'provider': 'qwen', 'models': ['qwen-plus', 'qwen-plus-2025-07-28'],
    'endpoint_region': 'cn-beijing', 'context_window': 1000000, 'max_output_tokens': 32768,
    'reviewed_at': '2026-11-16T00:00:00+00:00', 'review_before': '2026-11-23T00:00:00+00:00',
    'sources': ['https://www.alibabacloud.com/help/en/model-studio/qwen-plus',
                'https://help.aliyun.com/zh/model-studio/qwen-plus'],
    'basis': 'entire_context_ceiling_for_successfully_accepted_text_requests_not_exact_count',
    'assumptions': ['provider_enforces_documented_context_limit_including_chat_wrapper',
                    'no_tools_search_media_or_thinking', 'alias_is_reviewed_not_immutable_model_identity'],
}


def build_budget_plan(prepared, *, endpoint, now=None):
    """Build a checkable upper-bound policy; never increase the supplied budget."""
    now = time.time() if now is None else now
    value = prepared.payload()
    config = value['model_config']
    require(config['provider'] == CATALOG['provider'] and config['model'] in CATALOG['models'], 'token_policy_model_not_reviewed')
    require(config['max_output_tokens'] <= CATALOG['max_output_tokens'], 'token_policy_output_limit_exceeded')
    start = datetime.fromisoformat(CATALOG['reviewed_at']).timestamp()
    end = datetime.fromisoformat(CATALOG['review_before']).timestamp()
    require(type(now) in (int, float) and start <= now < end, 'token_policy_catalog_requires_review')
    bound = InputTokenBound(value['prompt']['messages_sha256'], config['model'], CATALOG['context_window'],
        'upper_bound', CATALOG['policy_id'], digest(CATALOG), True)
    plan = build_qwen_plan(prepared, endpoint=endpoint, token_bound=bound)
    return plan


def budget_review(prepared, *, endpoint, now=None):
    plan = build_budget_plan(prepared, endpoint=endpoint, now=now)
    config = prepared.payload()['model_config']
    diagnostics = []
    try:
        plan.preflight()
    except GenerationBoundaryError as error:
        diagnostics.append(str(error))
    return plan, {'policy_id': CATALOG['policy_id'], 'policy_sha256': digest(CATALOG),
        'method': 'documented_context_upper_bound_not_exact_token_count',
        'input_tokens_exact': None, 'reserved_input_tokens': plan.bound.count,
        'max_output_tokens': config['max_output_tokens'],
        'required_total_reservation': plan.bound.count + config['max_output_tokens'],
        'configured_max_total_tokens': config['max_total_tokens'],
        'status': 'blocked' if diagnostics else 'reservation_fits_not_call_approved', 'diagnostics': diagnostics,
        'assumptions': list(CATALOG['assumptions']), 'review_before': CATALOG['review_before'],
        'plan_sha256': plan.fingerprint, 'actual_model_calls': 0, 'production_ready': False}
