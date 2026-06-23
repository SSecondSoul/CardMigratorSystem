import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from migration_pipeline.generation_client import GenerationRequest, GenerationResult, create_generation_client
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt


@dataclass
class RepairStageInput:
    ssm: dict[str, Any]
    generated_code: str = ""
    generated_file_path: str = ""
    source_file: str = ""
    output_file_path: str | None = None
    repair_instruction: str = ""
    repair_attempt: int = 1
    validation_errors: list[dict[str, Any]] = field(default_factory=list)
    validation_warnings: list[dict[str, Any]] = field(default_factory=list)
    visual_eval_errors: list[dict[str, Any]] = field(default_factory=list)
    visual_eval_warnings: list[dict[str, Any]] = field(default_factory=list)
    dom_compare_result: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def resolve_current_code(self) -> str:
        if self.generated_code:
            return self.generated_code
        if self.generated_file_path:
            return Path(self.generated_file_path).read_text(encoding="utf-8")
        raise ValueError("RepairStageInput requires generated_code or generated_file_path")

    def resolve_output_file_path(self) -> str | None:
        if self.output_file_path:
            return self.output_file_path
        if self.generated_file_path:
            source_path = Path(self.generated_file_path)
            return str(source_path.with_name(f"{source_path.stem}_repaired{source_path.suffix}"))
        return None


@dataclass
class RepairStageResult:
    repaired_code: str
    repaired_file_path: str
    repair_prompt: str
    repair_attempt: int
    source_file: str = ""
    provider: str = ""
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)
    repair_summary: str = ""

    @classmethod
    def from_generation_result(
        cls,
        result: GenerationResult,
        repair_prompt: str,
        repair_attempt: int,
    ) -> "RepairStageResult":
        return cls(
            repaired_code=result.code,
            repaired_file_path=result.saved_file_path,
            repair_prompt=repair_prompt,
            repair_attempt=repair_attempt,
            source_file=result.source_file,
            provider=result.provider,
            model=result.model,
            usage=result.usage,
            raw_response=result.raw_response,
            repair_summary=f"第 {repair_attempt} 次修复完成，输出文件：{result.saved_file_path}",
        )

    def to_state_update(self) -> dict[str, Any]:
        return {
            "generated_code": self.repaired_code,
            "generated_file_path": self.repaired_file_path,
            "repaired_code": self.repaired_code,
            "repaired_file_path": self.repaired_file_path,
            "repair_prompt": self.repair_prompt,
            "repair_attempt": self.repair_attempt,
            "repair_provider": self.provider,
            "repair_model": self.model,
            "repair_usage": self.usage,
            "repair_raw_response": self.raw_response,
            "repair_summary": self.repair_summary,
            "repair_result": asdict(self),
        }


class RepairStage:
    def __init__(self, generation_client=None):
        self.generation_client = generation_client or create_generation_client()

    def run(self, stage_input: RepairStageInput) -> RepairStageResult:
        current_code = stage_input.resolve_current_code()
        repair_prompt = build_repair_prompt(RepairPromptInput(
            ssm=stage_input.ssm,
            current_code=current_code,
            source_file=stage_input.source_file,
            validation_errors=stage_input.validation_errors,
            validation_warnings=stage_input.validation_warnings,
            visual_eval_errors=stage_input.visual_eval_errors,
            visual_eval_warnings=stage_input.visual_eval_warnings,
            dom_compare_result=stage_input.dom_compare_result,
            extra_instruction=stage_input.repair_instruction,
        ))
        request_data = GenerationRequest(
            ssm=stage_input.ssm,
            source_file=stage_input.source_file,
            instruction=repair_prompt,
            output_file_path=stage_input.resolve_output_file_path(),
            metadata={
                **stage_input.metadata,
                "stage": "repair",
                "repair_attempt": stage_input.repair_attempt,
            },
        )
        result = self.generation_client.generate(request_data)
        result.code = self._strip_code_fences(result.code)
        self._ensure_repaired_file(result.saved_file_path, result.code)
        return RepairStageResult.from_generation_result(
            result=result,
            repair_prompt=repair_prompt,
            repair_attempt=stage_input.repair_attempt,
        )

    def run_from_state(self, state: dict[str, Any]) -> dict[str, Any]:
        ssm = state.get("ssm")
        if not ssm:
            raise ValueError("repair stage requires ssm in state")
        stage_input = RepairStageInput(
            ssm=ssm,
            generated_code=state.get("generated_code", state.get("generation_code", "")),
            generated_file_path=state.get("generated_file_path", state.get("saved_file_path", "")),
            source_file=state.get("source_file", ""),
            output_file_path=state.get("repair_output_file_path"),
            repair_instruction=state.get("repair_instruction", ""),
            repair_attempt=state.get("repair_attempt", 0) + 1,
            validation_errors=state.get("validation_errors", []),
            validation_warnings=state.get("validation_warnings", []),
            visual_eval_errors=state.get("visual_eval_errors", []),
            visual_eval_warnings=state.get("visual_eval_warnings", []),
            dom_compare_result=state.get("dom_compare_result"),
            metadata=state.get("repair_metadata", {}),
        )
        return self.run(stage_input).to_state_update()

    def _strip_code_fences(self, code: str) -> str:
        text = (code or "").strip()
        fence_match = re.match(r"^```[a-zA-Z0-9_-]*\n([\s\S]*?)\n```$", text)
        if fence_match:
            return fence_match.group(1).strip() + "\n"
        return text + ("\n" if text else "")

    def _ensure_repaired_file(self, repaired_file_path: str, repaired_code: str) -> None:
        if not repaired_file_path:
            return
        path = Path(repaired_file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(repaired_code, encoding="utf-8")


def repair_san(stage_input: RepairStageInput) -> RepairStageResult:
    return RepairStage().run(stage_input)
