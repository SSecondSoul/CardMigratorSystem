from dataclasses import dataclass, field
from typing import Any

from migration_pipeline.stages.generate import GenerateStage, GenerateStageInput, GenerateStageResult
from migration_pipeline.stages.validate import ValidateStage
from migration_pipeline.stages.visual_eval import VisualEvalStage


@dataclass
class MigrationPipelineState:
    vue_file_path: str | None = None
    vue_source: str | None = None
    ssm: dict[str, Any] | None = None
    source_file: str = ""
    generation_instruction: str = ""
    output_file_path: str | None = None
    use_node_bridge: bool = True
    generation_metadata: dict[str, Any] = field(default_factory=dict)
    generated_code: str = ""
    generated_file_path: str = ""
    generation_provider: str = ""
    generation_model: str = ""
    generation_usage: dict[str, Any] = field(default_factory=dict)
    generation_raw_response: dict[str, Any] = field(default_factory=dict)
    generate_result: dict[str, Any] | None = None
    validation_passed: bool = False
    validation_errors: list[dict[str, Any]] = field(default_factory=list)
    validation_warnings: list[dict[str, Any]] = field(default_factory=list)
    validation_checks: list[dict[str, Any]] = field(default_factory=list)
    validation_summary: str = ""
    san_compile_result: dict[str, Any] | None = None
    validate_result: dict[str, Any] | None = None
    visual_eval_passed: bool = False
    visual_eval_errors: list[dict[str, Any]] = field(default_factory=list)
    visual_eval_warnings: list[dict[str, Any]] = field(default_factory=list)
    visual_eval_summary: str = ""
    vue_render_result: dict[str, Any] | None = None
    san_render_result: dict[str, Any] | None = None
    visual_eval_result: dict[str, Any] | None = None


@dataclass
class MigrationPipelineResult:
    generate: GenerateStageResult
    state: dict[str, Any]
    validate: dict[str, Any] | None = None
    visual_eval: dict[str, Any] | None = None


class MigrationPipelineOrchestrator:
    def __init__(
        self,
        generate_stage: GenerateStage | None = None,
        validate_stage: ValidateStage | None = None,
        visual_eval_stage: VisualEvalStage | None = None,
    ):
        self.generate_stage = generate_stage or GenerateStage()
        self.validate_stage = validate_stage or ValidateStage()
        self.visual_eval_stage = visual_eval_stage or VisualEvalStage()

    def run_generate_only(self, stage_input: GenerateStageInput) -> MigrationPipelineResult:
        generate_result = self.generate_stage.run(stage_input)
        return MigrationPipelineResult(
            generate=generate_result,
            state=generate_result.to_state_update(),
        )

    def run_generate_and_validate(self, stage_input: GenerateStageInput) -> MigrationPipelineResult:
        generate_result = self.generate_stage.run(stage_input)
        state = generate_result.to_state_update()
        validate_result = self.validate_stage.run_from_state(state)
        state.update(validate_result)
        return MigrationPipelineResult(
            generate=generate_result,
            validate=state["validate_result"],
            state=state,
        )

    def run_generate_validate_and_visual_eval(self, stage_input: GenerateStageInput) -> MigrationPipelineResult:
        generate_result = self.generate_stage.run(stage_input)
        state = generate_result.to_state_update()
        validate_update = self.validate_stage.run_from_state(state)
        state.update(validate_update)
        visual_eval_update = self.visual_eval_stage.run_from_state(state)
        state.update(visual_eval_update)
        return MigrationPipelineResult(
            generate=generate_result,
            validate=state["validate_result"],
            visual_eval=state["visual_eval_result"],
            state=state,
        )

    def run_generate_node(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.generate_stage.run_from_state(state)

    def run_validate_node(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.validate_stage.run_from_state(state)

    def run_visual_eval_node(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.visual_eval_stage.run_from_state(state)
