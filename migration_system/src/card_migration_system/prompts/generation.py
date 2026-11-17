"""Pinned, pure legacy generation builder; never import the server or old pipeline.

Trusted repository code only, not a sandbox. Hash both complete source texts
before compiling the single allowlisted builder. No uploaded code is compiled.
"""
import ast
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


PINS = {
    'local_server/api/evaluation_routes.py': '71818205059132bb15330aa4d474ec4269ebed19b8337a9ea00ef3d459972548',
    'migration_pipeline/utils/class_binding_contract.py': 'bf83e708c7e6c11713f246a3ec9f16f02aba8276020faac770a1a5243de23e66',
}
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
    assignments = [node.value for node in trees['migration_pipeline/utils/class_binding_contract.py'].body
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'CLASS_BINDING_RULE'
                                               for target in node.targets)]
    functions = [node for node in trees['local_server/api/evaluation_routes.py'].body
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
