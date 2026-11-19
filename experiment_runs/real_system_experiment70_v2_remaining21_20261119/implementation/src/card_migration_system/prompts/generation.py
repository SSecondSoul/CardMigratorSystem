"""Pinned, internal generation builder; never read the parent server or pipeline.

Trusted repository code only, not a sandbox. Hash both complete source texts
before compiling the single allowlisted builder. No uploaded code is compiled.
"""
import ast
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from ..reporting.identity import digest


PINS = {'prompts/generation_builder.py': '4c20260e79a35b0d9f16d5d1ba943b84642eb563784bda1f293e4c9f1c450aa2'}
SYSTEM = 'You are an expert Vue-to-San code generator. Output only San component code.'


class PromptBindingError(ValueError):
    pass


def build_generation_messages(repository_root, ssm):
    root = Path(repository_root).resolve()
    sources = {}
    for name, expected in PINS.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise PromptBindingError('generation_prompt_path_invalid')
        try:
            source = path.read_text(encoding='utf-8').replace('\r\n', '\n').replace('\r', '\n')
        except (OSError, UnicodeError):
            raise PromptBindingError('generation_prompt_source_missing') from None
        if sha256(source.encode()).hexdigest() != expected:
            raise PromptBindingError('generation_prompt_source_drift')
        sources[name] = source
    trees = {name: ast.parse(value) for name, value in sources.items()}
    assignments = [node.value for node in trees['prompts/generation_builder.py'].body
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'CLASS_BINDING_RULE'
                                               for target in node.targets)]
    functions = [node for node in trees['prompts/generation_builder.py'].body
        if isinstance(node, ast.FunctionDef) and node.name == '_build_generation_prompt']
    if len(assignments) != 1 or len(functions) != 1:
        raise PromptBindingError('generation_prompt_builder_missing')
    namespace = {'json': json, 'Any': Any, 'CLASS_BINDING_RULE': ast.literal_eval(assignments[0])}
    module = ast.Module(body=functions, type_ignores=[])
    exec(compile(module, '<pinned-generation-builder>', 'exec'), namespace)
    # Round-trip detaches caller-owned SSM values; the trusted builder is pure.
    detached = json.loads(json.dumps(ssm, allow_nan=False))
    messages = [{'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': namespace['_build_generation_prompt'](detached)}]
    return messages, dict(PINS)


def compact_generation_context(messages, ssm):
    """Remove JSON formatting only, never fields, source text, or semantic rules.

    Keep the pinned experiment builder intact. Fail closed if its SSM boundary
    changes; guessing a substring could otherwise modify instructions or code.
    The caller persists the returned manifest alongside the actual request.
    """
    detached = json.loads(json.dumps(messages, ensure_ascii=False, allow_nan=False))
    original = json.dumps(ssm, ensure_ascii=False, indent=2, allow_nan=False)
    suffix = '--- SSM ---\n' + original
    if (not detached or detached[-1].get('role') != 'user'
            or not isinstance(detached[-1].get('content'), str)
            or not detached[-1]['content'].endswith(suffix)):
        raise PromptBindingError('generation_ssm_boundary_mismatch')
    compact = json.dumps(ssm, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    if digest(json.loads(compact)) != digest(ssm):
        raise PromptBindingError('generation_ssm_roundtrip_mismatch')
    prefix = detached[-1]['content'][:-len(original)]
    before = detached[-1]['content']
    detached[-1]['content'] = prefix + compact
    after = detached[-1]['content']
    return detached, {
        'policy': 'generation-lossless-json-v2',
        'ssm_sha256': digest(ssm),
        'instructions_sha256': sha256(prefix.encode()).hexdigest(),
        'before_message_sha256': sha256(before.encode()).hexdigest(),
        'after_message_sha256': sha256(after.encode()).hexdigest(),
        'before_chars': len(before), 'after_chars': len(after),
        'before_utf8_bytes': len(before.encode()), 'after_utf8_bytes': len(after.encode()),
        'all_ssm_values_preserved': True,
        'token_reduction': 'not_measured_offline_characters_are_not_tokens',
    }
