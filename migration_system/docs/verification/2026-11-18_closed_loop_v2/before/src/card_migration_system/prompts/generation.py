"""Pinned, internal generation builder; never read the parent server or pipeline.

Trusted repository code only, not a sandbox. Hash both complete source texts
before compiling the single allowlisted builder. No uploaded code is compiled.
"""
import ast
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


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
