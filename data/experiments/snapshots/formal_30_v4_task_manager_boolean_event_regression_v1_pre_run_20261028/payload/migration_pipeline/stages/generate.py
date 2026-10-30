from dataclasses import asdict, dataclass, field
from typing import Any

from SSM.extractors.factory import SSMFactory
from migration_pipeline.generation_client import GenerationRequest, GenerationResult, create_generation_client


@dataclass
class GenerateStageInput:
    vue_file_path: str | None = None
    vue_source: str | None = None
    ssm: dict[str, Any] | None = None
    source_file: str = ""
    instruction: str = ""
    output_file_path: str | None = None
    use_node_bridge: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def resolve_source_file(self) -> str:
        return self.source_file or self.vue_file_path or "inline.vue"

    def to_generation_request(self, ssm: dict[str, Any]) -> GenerationRequest:
        return GenerationRequest(
            ssm=ssm,
            source_file=self.resolve_source_file(),
            instruction=self.instruction,
            output_file_path=self.output_file_path,
            metadata=self.metadata,
        )


@dataclass
class GenerateStageResult:
    source_file: str
    ssm: dict[str, Any]
    generation_code: str
    saved_file_path: str
    provider: str
    model: str
    usage: dict[str, Any]
    raw_response: dict[str, Any]

    @classmethod
    def from_generation_result(cls, result: GenerationResult) -> "GenerateStageResult":
        return cls(
            source_file=result.source_file,
            ssm=result.ssm,
            generation_code=result.code,
            saved_file_path=result.saved_file_path,
            provider=result.provider,
            model=result.model,
            usage=result.usage,
            raw_response=result.raw_response,
        )

    def to_state_update(self) -> dict[str, Any]:
        return {
            **GenerationResult(
                source_file=self.source_file,
                ssm=self.ssm,
                code=self.generation_code,
                saved_file_path=self.saved_file_path,
                provider=self.provider,
                model=self.model,
                usage=self.usage,
                raw_response=self.raw_response,
            ).to_state_update(),
            "generate_result": asdict(self),
        }


class GenerateStage:
    def __init__(self, generation_client=None):
        self.generation_client = generation_client or create_generation_client()

    def run(self, stage_input: GenerateStageInput) -> GenerateStageResult:
        ssm = stage_input.ssm or self._build_ssm(stage_input)
        request_data = stage_input.to_generation_request(ssm)
        result = self.generation_client.generate(request_data)
        return GenerateStageResult.from_generation_result(result)

    def run_from_state(self, state: dict[str, Any]) -> dict[str, Any]:
        stage_input = GenerateStageInput(
            vue_file_path=state.get("vue_file_path"),
            vue_source=state.get("vue_source"),
            ssm=state.get("ssm"),
            source_file=state.get("source_file", ""),
            instruction=state.get("generation_instruction", state.get("instruction", "")),
            output_file_path=state.get("output_file_path"),
            use_node_bridge=state.get("use_node_bridge", True),
            metadata=state.get("generation_metadata", {}),
        )
        return self.run(stage_input).to_state_update()

    def _build_ssm(self, stage_input: GenerateStageInput) -> dict[str, Any]:
        factory = SSMFactory(use_node_bridge=stage_input.use_node_bridge)
        if stage_input.vue_source:
            source_file = stage_input.resolve_source_file()
            return factory.build(
                stage_input.vue_source,
                file_path=source_file,
                source_file=source_file,
            )
        if stage_input.vue_file_path:
            return factory.build_from_file(stage_input.vue_file_path)
        raise ValueError("GenerateStageInput requires one of: ssm, vue_source, vue_file_path")


def generate_san(stage_input: GenerateStageInput) -> GenerateStageResult:
    return GenerateStage().run(stage_input)
