"""Shared generation/repair prompt boundary and leakage-aware few-shot selection."""
from hashlib import sha256
import json
from pathlib import Path

from .generation import build_generation_messages, compact_generation_context
from ..application.service import ServiceError
from ..reporting.identity import digest


def examples(settings, profile, source_sha256, source_group, exclude_groups=()):
    learning = profile['learning']
    count = learning['few_shot_count']
    if not count: return []
    manifest = Path(learning['few_shot_manifest'])
    if not manifest.is_absolute(): manifest = settings.project_root / manifest
    if not manifest.is_file(): raise ServiceError('few_shot_manifest_missing')
    payload = json.loads(manifest.read_text(encoding='utf-8'))
    if payload.get('schema_version') != 1: raise ServiceError('invalid_few_shot_manifest')
    candidates = []
    excluded = set(exclude_groups) | {source_group}
    for item in payload['examples']:
        if item['split'] != 'train' or item['source_sha256'] == source_sha256 or item['group'] in excluded: continue
        if digest(item['ssm']) != item['ssm_sha256'] or sha256(item['san'].encode()).hexdigest() != item['san_sha256']:
            raise ServiceError('few_shot_hash_mismatch')
        candidates.append(item)
    selected = sorted(candidates, key=lambda item: item['id'])[:count]
    if len(selected) < count: raise ServiceError('few_shot_insufficient_isolated_examples')
    return selected


def generation_messages(settings, ssm, selected, *, strategy='ssm', source=''):
    if strategy == 'direct':
        messages = [{'role': 'system', 'content': 'Migrate Vue to a complete San SFC. Output only <template>, <script> (CommonJS require("san")), <style>. Preserve semantics.'},
                    {'role': 'user', 'content': source}]
        pins = {}
        context = {'policy': 'direct_source_unchanged'}
    else:
        messages, pins = build_generation_messages(settings.repository_root, ssm)
        messages, context = compact_generation_context(messages, ssm)
    demonstrations = []
    for item in selected:
        demonstrations.extend([{'role': 'user', 'content': json.dumps(item['ssm'], ensure_ascii=False)},
                               {'role': 'assistant', 'content': item['san']}])
    return [messages[0], *demonstrations, *messages[1:]], {'legacy_prompt_pins': pins, 'generation_context': context,
        'examples': [{k: item[k] for k in ('id', 'group', 'source_sha256', 'ssm_sha256', 'san_sha256')} for item in selected],
        'strategy': strategy}
