import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from migration_pipeline.repair_client import RepairRequest, RepairResult, create_repair_client
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
    def from_repair_result(
        cls,
        result: RepairResult,
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
    OPENING_TAG_PATTERN = re.compile(
        r"<[A-Za-z][A-Za-z0-9:_-]*(?:\s+(?:\"[^\"]*\"|'[^']*'|[^'\">])*)?\s*/?>",
        re.DOTALL,
    )
    ATTRIBUTE_PATTERN = re.compile(
        r"\s+([A-Za-z_:][\w:.-]*)\s*=\s*([\"'])(.*?)\2",
        re.DOTALL,
    )

    def __init__(self, repair_client=None):
        self.repair_client = repair_client or create_repair_client()

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
        deterministic_code = self._apply_deterministic_repairs(
            current_code,
            stage_input.validation_errors,
            stage_input.visual_eval_errors,
        )
        if deterministic_code != current_code:
            error_codes = {issue.get("code") for issue in stage_input.validation_errors}
            methods_unwrapped = "vue_methods_wrapper" in error_codes
            normalizer_model = (
                "san_methods_wrapper_normalizer"
                if methods_unwrapped
                else "san_loop_binding_normalizer"
            )
            normalization = (
                "unwrapped_final_top_level_methods_option"
                if methods_unwrapped
                else "removed_redundant_s_for_key_or_trackby_attribute"
            )
            output_path = stage_input.resolve_output_file_path() or ""
            self._ensure_repaired_file(output_path, deterministic_code)
            return RepairStageResult(
                repaired_code=deterministic_code,
                repaired_file_path=output_path,
                repair_prompt=repair_prompt,
                repair_attempt=stage_input.repair_attempt,
                source_file=stage_input.source_file,
                provider="deterministic",
                model=normalizer_model,
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                raw_response={"normalization": normalization},
                repair_summary=(
                    f"Deterministic structural normalization completed: {output_path}"
                ),
            )
        request_data = RepairRequest(
            ssm=stage_input.ssm,
            repair_prompt=repair_prompt,
            source_file=stage_input.source_file,
            current_code=current_code,
            output_file_path=stage_input.resolve_output_file_path(),
            repair_report=self._build_repair_report(stage_input),
            metadata={
                **stage_input.metadata,
                "stage": "repair",
                "repair_attempt": stage_input.repair_attempt,
            },
        )
        result = self.repair_client.repair(request_data)
        result.code = self._strip_code_fences(result.code)
        if any(
            issue.get("code") == "invalid_s_for_key_binding"
            for issue in stage_input.validation_errors
        ):
            result.code = self._normalize_redundant_s_for_attributes(result.code)
        self._ensure_repaired_file(result.saved_file_path, result.code)
        return RepairStageResult.from_repair_result(
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

    def _build_repair_report(self, stage_input: RepairStageInput) -> dict[str, Any]:
        return {
            "validation_errors": stage_input.validation_errors,
            "validation_warnings": stage_input.validation_warnings,
            "visual_eval_errors": stage_input.visual_eval_errors,
            "visual_eval_warnings": stage_input.visual_eval_warnings,
            "dom_compare_result": stage_input.dom_compare_result or {},
        }

    def _strip_code_fences(self, code: str) -> str:
        text = (code or "").strip()
        fence_match = re.match(r"^```[a-zA-Z0-9_-]*\n([\s\S]*?)\n```$", text)
        if fence_match:
            return fence_match.group(1).strip() + "\n"
        return text + ("\n" if text else "")

    @classmethod
    def _normalize_redundant_s_for_attributes(cls, code: str) -> str:
        def normalize_tag(match: re.Match[str]) -> str:
            tag = match.group(0)
            attributes = list(cls.ATTRIBUTE_PATTERN.finditer(tag))
            s_for = next(
                (item for item in attributes if item.group(1).lower() == "s-for"),
                None,
            )
            if not s_for:
                return tag

            inline_trackby = re.search(r"\btrackby\s+(.+?)\s*$", s_for.group(3))
            if not inline_trackby:
                return tag
            inline_expression = cls._normalize_binding_expression(inline_trackby.group(1))

            redundant = [
                item
                for item in attributes
                if item.group(1).lower() in {"key", "trackby"}
            ]
            if not redundant:
                return tag
            if any(
                cls._normalize_binding_expression(item.group(3)) != inline_expression
                for item in redundant
            ):
                return tag

            chunks: list[str] = []
            cursor = 0
            for item in redundant:
                chunks.append(tag[cursor:item.start()])
                cursor = item.end()
            chunks.append(tag[cursor:])
            return "".join(chunks)

        return cls.OPENING_TAG_PATTERN.sub(normalize_tag, code)

    @staticmethod
    def _normalize_binding_expression(value: str) -> str:
        expression = value.strip()
        if expression.startswith("{{") and expression.endswith("}}"):
            expression = expression[2:-2].strip()
        elif expression.startswith("{=") and expression.endswith("=}"):
            expression = expression[2:-2].strip()
        return expression

    @staticmethod
    def _find_matching_js_brace(code: str, opening_index: int) -> int:
        depth = 0
        quote = ""
        escaped = False
        line_comment = False
        block_comment = False
        index = opening_index

        while index < len(code):
            char = code[index]
            next_char = code[index + 1] if index + 1 < len(code) else ""

            if line_comment:
                if char in "\r\n":
                    line_comment = False
                index += 1
                continue
            if block_comment:
                if char == "*" and next_char == "/":
                    block_comment = False
                    index += 2
                else:
                    index += 1
                continue
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
                index += 1
                continue
            if char == "/" and next_char == "/":
                line_comment = True
                index += 2
                continue
            if char == "/" and next_char == "*":
                block_comment = True
                index += 2
                continue
            if char in {"'", '"', "`"}:
                quote = char
                index += 1
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return index
            index += 1

        return -1

    @classmethod
    def _normalize_vue_methods_wrapper(cls, code: str) -> str:
        pattern = re.compile(r"(?m)^([ \t]*)methods\s*:\s*\{")
        for match in pattern.finditer(code):
            opening_index = code.find("{", match.start(), match.end())
            closing_index = cls._find_matching_js_brace(code, opening_index)
            if closing_index < 0:
                continue

            script_end = code.find("</script>", closing_index)
            if script_end < 0:
                continue

            cursor = closing_index + 1
            while cursor < script_end and code[cursor] in " \t":
                cursor += 1
            if cursor < script_end and code[cursor] == ",":
                cursor += 1
            if not re.fullmatch(r"\s*\}\s*\)\s*;?\s*", code[cursor:script_end]):
                continue

            lines = code[opening_index + 1:closing_index].splitlines()
            while lines and not lines[0].strip():
                lines.pop(0)
            while lines and not lines[-1].strip():
                lines.pop()
            if not lines:
                continue

            indentation = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
            extra_indent = min(indentation) - len(match.group(1))
            if extra_indent <= 0:
                continue
            normalized_lines = [
                line[extra_indent:] if line.strip() else ""
                for line in lines
            ]
            replacement = "\n".join(normalized_lines)
            return code[:match.start()] + replacement + code[cursor:]

        return code

    @classmethod
    def _apply_deterministic_repairs(
        cls,
        code: str,
        validation_errors: list[dict[str, Any]],
        visual_eval_errors: list[dict[str, Any]],
    ) -> str:
        error_codes = {issue.get("code") for issue in validation_errors}
        if "vue_methods_wrapper" in error_codes:
            normalized = cls._normalize_vue_methods_wrapper(code)
            if normalized != code:
                return normalized
        if error_codes == {"invalid_s_for_key_binding"} and not visual_eval_errors:
            return cls._normalize_redundant_s_for_attributes(code)
        return code

    def _ensure_repaired_file(self, repaired_file_path: str, repaired_code: str) -> None:
        if not repaired_file_path:
            return
        path = Path(repaired_file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(repaired_code, encoding="utf-8")


def repair_san(stage_input: RepairStageInput) -> RepairStageResult:
    return RepairStage().run(stage_input)
