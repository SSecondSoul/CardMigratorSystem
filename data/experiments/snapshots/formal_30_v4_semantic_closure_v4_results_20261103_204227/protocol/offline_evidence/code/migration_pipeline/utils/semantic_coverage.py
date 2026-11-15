"""A proven latent finding stays an error, but is not called newly introduced."""

import json
import re
import subprocess
from collections import Counter
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=32)
def _proof(before, after, ssm_json):
    try:
        p = subprocess.run(['node', str(Path(__file__).with_suffix('.cjs'))],
            input=json.dumps({'before': before, 'after': after, 'ssm': json.loads(ssm_json)}),
            capture_output=True, text=True, encoding='utf-8', check=True, timeout=15)
        return json.loads(p.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {'status': 'unproven', 'pairs': [], 'error': type(exc).__name__}


def latent_semantic_findings(before, after, introduced, *, vue_source=''):
    relevant = {identity: count for identity, count in introduced.items()
                if identity[0] in {'hidden_template_reactive_dependency', 'source_watch_persistence_not_landed'}}
    evidence = {'status': 'not_needed', 'proven_pairs': []}
    if not relevant:
        return Counter(), evidence
    proof = _proof(before['generated_code'], after['generated_code'],
                   json.dumps(before.get('ssm') or {}, sort_keys=True, ensure_ascii=False))
    evidence = {k: v for k, v in proof.items() if k != 'before_code'}
    if not proof.get('before_code'):
        return Counter(), evidence
    # Isolated analysis only: no compile/render/evaluation of recovered JS.
    from migration_pipeline.stages.validate import ValidateStage
    script = ValidateStage()._extract_blocks(proof['before_code']).get('script', '')
    issues, checks = [], []
    ValidateStage()._validate_inline_template_reactive_dependencies(script, issues, checks)
    candidates = Counter()
    for issue in issues:
        match = re.search(r'模板 (\w+) 渲染表达式调用 ([A-Za-z_$][\w$]*)\(', issue.message)
        if not match:
            continue
        binding, method = match.groups()
        for pair in proof['pairs']:
            if (issue.location == f"script.{pair['before_name']}.template"
                    and method == pair['method'] and binding == pair['binding']):
                identity = (issue.code, f"script.{pair['after_name']}.template", issue.message)
                candidates[identity] += 1
    if proof.get('parent_inited_unchanged') and vue_source:
        from migration_pipeline.utils.bounded_semantics import inspect_semantics
        assessed = inspect_semantics(proof['before_code'], vue_source, ssm=before.get('ssm'))
        for finding in assessed.get('findings', []):
            if finding['code'] == 'source_watch_persistence_not_landed':
                candidates[(finding['code'], finding['location'], finding['message'])] += 1
    return candidates & Counter(relevant), evidence
