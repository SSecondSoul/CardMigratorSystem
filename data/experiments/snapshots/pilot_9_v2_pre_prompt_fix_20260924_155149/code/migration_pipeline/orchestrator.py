from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from migration_pipeline.stages.generate import GenerateStage, GenerateStageInput, GenerateStageResult
from migration_pipeline.stages.repair import RepairStage
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
    dom_compare_result: dict[str, Any] | None = None
    tree_edit_distance: float = 0.0
    structure_similarity: float = 0.0
    tag_sequence_similarity: float = 0.0
    text_similarity: float = 0.0
    visual_eval_result: dict[str, Any] | None = None
    repaired_code: str = ""
    repaired_file_path: str = ""
    repair_prompt: str = ""
    repair_attempt: int = 0
    repair_provider: str = ""
    repair_model: str = ""
    repair_usage: dict[str, Any] = field(default_factory=dict)
    repair_raw_response: dict[str, Any] = field(default_factory=dict)
    repair_summary: str = ""
    repair_result: dict[str, Any] | None = None
    initial_validate_result: dict[str, Any] | None = None
    initial_visual_eval_result: dict[str, Any] | None = None
    repaired_validate_result: dict[str, Any] | None = None
    repaired_visual_eval_result: dict[str, Any] | None = None
    repair_history: list[dict[str, Any]] = field(default_factory=list)
    repair_rounds: int = 0
    max_repair_rounds: int = 3
    final_code: str = ""
    final_file_path: str = ""
    final_validate_result: dict[str, Any] | None = None
    final_visual_eval_result: dict[str, Any] | None = None
    final_passed: bool = False
    stop_reason: str = ""


@dataclass
class MigrationPipelineResult:
    generate: GenerateStageResult
    state: dict[str, Any]
    validate: dict[str, Any] | None = None
    visual_eval: dict[str, Any] | None = None
    repair: dict[str, Any] | None = None


class MigrationPipelineOrchestrator:
    def __init__(
        self,
        generate_stage: GenerateStage | None = None,
        validate_stage: ValidateStage | None = None,
        visual_eval_stage: VisualEvalStage | None = None,
        repair_stage: RepairStage | None = None,
    ):
        self.generate_stage = generate_stage or GenerateStage()
        self.validate_stage = validate_stage or ValidateStage()
        self.visual_eval_stage = visual_eval_stage or VisualEvalStage()
        self.repair_stage = repair_stage or RepairStage()

    def run_generate_only(self, stage_input: GenerateStageInput) -> MigrationPipelineResult:
        generate_result = self.generate_stage.run(stage_input)
        return MigrationPipelineResult(
            generate=generate_result,
            state=self._build_initial_state(stage_input, generate_result),
        )

    def run_generate_and_validate(self, stage_input: GenerateStageInput) -> MigrationPipelineResult:
        generate_result = self.generate_stage.run(stage_input)
        state = self._build_initial_state(stage_input, generate_result)
        validate_result = self.validate_stage.run_from_state(state)
        state.update(validate_result)
        return MigrationPipelineResult(
            generate=generate_result,
            validate=state["validate_result"],
            state=state,
        )

    def run_generate_validate_and_visual_eval(self, stage_input: GenerateStageInput) -> MigrationPipelineResult:
        generate_result = self.generate_stage.run(stage_input)
        state = self._build_initial_state(stage_input, generate_result)
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

    def run_generate_validate_visual_eval_and_repair(self, stage_input: GenerateStageInput) -> MigrationPipelineResult:
        generate_result = self.generate_stage.run(stage_input)
        state = self._build_initial_state(stage_input, generate_result)
        state.update(self.validate_stage.run_from_state(state))
        state.update(self.visual_eval_stage.run_from_state(state))
        repair_update = self.repair_stage.run_from_state(state)
        state.update(repair_update)
        return MigrationPipelineResult(
            generate=generate_result,
            validate=state["validate_result"],
            visual_eval=state["visual_eval_result"],
            repair=state["repair_result"],
            state=state,
        )

    def run_generate_validate_visual_eval_repair_and_recheck(self, stage_input: GenerateStageInput) -> MigrationPipelineResult:
        return self.run_generate_validate_visual_eval_and_repair_loop(
            stage_input=stage_input,
            max_repair_rounds=1,
        )

    def run_generate_validate_visual_eval_and_repair_loop(
        self,
        stage_input: GenerateStageInput,
        max_repair_rounds: int = 3,
    ) -> MigrationPipelineResult:
        generate_result = self.generate_stage.run(stage_input)
        state = self._build_initial_state(stage_input, generate_result)
        state["max_repair_rounds"] = max_repair_rounds
        state["repair_history"] = []
        state["repair_rounds"] = 0

        validate_update = self.validate_stage.run_from_state(state)
        state.update(validate_update)
        state["initial_validate_result"] = state["validate_result"]

        visual_update = self.visual_eval_stage.run_from_state(state)
        state.update(visual_update)
        state["initial_visual_eval_result"] = state["visual_eval_result"]

        while self._should_continue_repair(state, max_repair_rounds):
            repair_update = self.repair_stage.run_from_state(state)
            state.update(repair_update)
            state["repair_rounds"] = state.get("repair_attempt", 0)

            validate_update = self.validate_stage.run_from_state(state)
            state.update(validate_update)
            state["repaired_validate_result"] = state["validate_result"]

            visual_update = self.visual_eval_stage.run_from_state(state)
            state.update(visual_update)
            state["repaired_visual_eval_result"] = state["visual_eval_result"]

            state["repair_history"].append(self._build_repair_history_entry(state))

        self._finalize_state(state, max_repair_rounds)

        return MigrationPipelineResult(
            generate=generate_result,
            validate=state["final_validate_result"],
            visual_eval=state["final_visual_eval_result"],
            repair=state.get("repair_result"),
            state=state,
        )

    def _stage_passed(self, state: dict[str, Any]) -> bool:
        return bool(state.get("validation_passed") and state.get("visual_eval_passed"))

    def _build_initial_state(
        self,
        stage_input: GenerateStageInput,
        generate_result: GenerateStageResult,
    ) -> dict[str, Any]:
        state = generate_result.to_state_update()
        state.update({
            "vue_file_path": stage_input.vue_file_path,
            "vue_source": stage_input.vue_source,
            "source_file": stage_input.source_file or generate_result.source_file,
            "generation_instruction": stage_input.instruction,
            "output_file_path": stage_input.output_file_path,
            "use_node_bridge": stage_input.use_node_bridge,
            "generation_metadata": deepcopy(stage_input.metadata),
        })
        return state

    def _should_continue_repair(self, state: dict[str, Any], max_repair_rounds: int) -> bool:
        return not self._stage_passed(state) and state.get("repair_attempt", 0) < max_repair_rounds

    def _build_repair_history_entry(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "repair_attempt": state.get("repair_attempt", 0),
            "repair_result": deepcopy(state.get("repair_result")),
            "validate_result": deepcopy(state.get("validate_result")),
            "visual_eval_result": deepcopy(state.get("visual_eval_result")),
            "validation_passed": state.get("validation_passed", False),
            "visual_eval_passed": state.get("visual_eval_passed", False),
            "tree_edit_distance": state.get("tree_edit_distance", 0.0),
            "structure_similarity": state.get("structure_similarity", 0.0),
            "tag_sequence_similarity": state.get("tag_sequence_similarity", 0.0),
            "text_similarity": state.get("text_similarity", 0.0),
            "passed": self._stage_passed(state),
        }

    def _finalize_state(self, state: dict[str, Any], max_repair_rounds: int) -> None:
        final_passed = self._stage_passed(state)
        state["final_passed"] = final_passed
        state["final_code"] = state.get("generated_code", "")
        state["final_file_path"] = state.get("generated_file_path", "")
        state["final_validate_result"] = state.get("validate_result")
        state["final_visual_eval_result"] = state.get("visual_eval_result")

        if final_passed:
            state["stop_reason"] = "passed"
        elif state.get("repair_attempt", 0) >= max_repair_rounds:
            state["stop_reason"] = "max_repair_rounds_reached"
        else:
            state["stop_reason"] = "repair_not_required"

    def run_generate_node(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.generate_stage.run_from_state(state)

    def run_validate_node(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.validate_stage.run_from_state(state)

    def run_visual_eval_node(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.visual_eval_stage.run_from_state(state)

    def run_repair_node(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.repair_stage.run_from_state(state)
