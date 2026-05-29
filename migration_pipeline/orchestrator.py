from dataclasses import dataclass, field
from typing import Any

from migration_pipeline.stages.generate import GenerateStage, GenerateStageInput, GenerateStageResult


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


@dataclass
class MigrationPipelineResult:
    generate: GenerateStageResult
    state: dict[str, Any]


class MigrationPipelineOrchestrator:
    def __init__(self, generate_stage: GenerateStage | None = None):
        self.generate_stage = generate_stage or GenerateStage()

    def run_generate_only(self, stage_input: GenerateStageInput) -> MigrationPipelineResult:
        generate_result = self.generate_stage.run(stage_input)
        return MigrationPipelineResult(
            generate=generate_result,
            state=generate_result.to_state_update(),
        )

    def run_generate_node(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.generate_stage.run_from_state(state)
