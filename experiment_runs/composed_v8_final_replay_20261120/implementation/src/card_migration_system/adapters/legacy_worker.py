"""Trusted repository parser/rules subprocess with no credentials or model calls."""
import contextlib
from dataclasses import asdict
import io
import json
from pathlib import Path
import sys
import tempfile


def main():
    root = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(root))
    value = json.loads(sys.stdin.buffer.read(12 * 1024 * 1024))
    from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
    from migration_pipeline.stages.repair import RepairStage
    from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
    with tempfile.TemporaryDirectory(prefix='cardmig-check-') as directory:
        vue = Path(directory) / 'Source.vue'
        vue.write_text(value['source'], encoding='utf-8')
        # The constructor of RepairStage and its .run() are NEVER called.
        with contextlib.redirect_stdout(io.StringIO()):
            if value['action'] == 'validate':
                result = asdict(ValidateStage().run(ValidateStageInput(generated_code=value['code'],
                    ssm=value['ssm'], vue_file_path=str(vue), source_file=str(vue), compile_check=False)))
            elif value['action'] == 'rules':
                code, changes = RepairStage._deterministic_repair_plan(value['code'], value['errors'],
                    value['visual_errors'], value['ssm'], str(vue), enable_residual_v2=True)
                result = {'code': code, 'changes': changes}
            elif value['action'] == 'prop_defaults':
                from migration_pipeline.utils.parent_prop_semantics import parent_prop_semantics
                result = parent_prop_semantics(value['code'], value['source'], repair=True)
            elif value['action'] == 'repair_prompt':
                result = {'prompt': build_repair_prompt(RepairPromptInput(ssm=value['ssm'],
                    current_code=value['code'], vue_source=value['source'], validation_errors=value['errors'],
                    visual_eval_errors=value['visual_errors']))}
            else: raise ValueError('unsupported_stage')
    print(json.dumps({'status': 'completed', 'result': result}, ensure_ascii=True))

if __name__ == '__main__': main()
