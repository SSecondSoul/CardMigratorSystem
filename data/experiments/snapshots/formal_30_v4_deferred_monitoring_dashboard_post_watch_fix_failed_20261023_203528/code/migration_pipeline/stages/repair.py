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
    WRAPPED_SAN_DIRECTIVE_PATTERN = re.compile(
        r"\b(?P<directive>s-if|s-else-if|s-for)\s*=\s*(?P<quote>[\"'])\s*"
        r"(?:\{\{(?P<one_way>.*?)\}\}|\{=(?P<two_way>.*?)=\})\s*(?P=quote)",
        re.IGNORECASE | re.DOTALL,
    )
    METHOD_DEFINITION_PATTERN = re.compile(
        r"(?m)^([ \t]*)([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{"
    )
    STATE_ARRAY_ALIAS_PATTERN = re.compile(
        r"\b(?P<kind>const|let|var)\s+(?P<alias>[A-Za-z_$][\w$]*)\s*=\s*"
        r"this\.data\.get\s*\(\s*(?P<quote>['\"])(?P<field>[A-Za-z_$][\w$]*)"
        r"(?P=quote)\s*\)(?P<fallback>\s*\|\|\s*\[\s*\])?\s*;"
    )
    MUTATING_ARRAY_METHODS = (
        "copyWithin", "fill", "pop", "push", "reverse", "shift", "sort", "splice", "unshift"
    )
    JAVASCRIPT_CONTROL_KEYWORDS = {
        "catch", "do", "for", "if", "switch", "while", "with",
    }

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
            directive_code = self._normalize_wrapped_san_directives(current_code)
            watch_code = self._normalize_misplaced_watch_registration(current_code)
            methods_code = self._normalize_vue_methods_wrapper(current_code)
            array_code = self._normalize_mutated_state_array_aliases(current_code)
            if (
                "invalid_san_directive_interpolation" in error_codes
                and directive_code == deterministic_code
            ):
                normalizer_model = "san_directive_expression_normalizer"
                normalization = "unwrapped_san_directive_expression"
            elif (
                "watch_registration_not_in_lifecycle" in error_codes
                and watch_code == deterministic_code
            ):
                normalizer_model = "san_watch_lifecycle_normalizer"
                normalization = "moved_watch_registration_into_lifecycle"
            elif "vue_methods_wrapper" in error_codes and methods_code == deterministic_code:
                normalizer_model = "san_methods_wrapper_normalizer"
                normalization = "unwrapped_final_top_level_methods_option"
            elif "nested_state_mutation" in error_codes and array_code == deterministic_code:
                normalizer_model = "san_state_array_clone_normalizer"
                normalization = "cloned_state_array_before_local_mutation"
            else:
                normalizer_model = "san_loop_binding_normalizer"
                normalization = "removed_redundant_s_for_key_or_trackby_attribute"
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
        normalized_code = self._normalize_wrapped_san_directives(result.code)
        if normalized_code != result.code:
            result.code = normalized_code
            if isinstance(result.raw_response, dict):
                result.raw_response = {
                    **result.raw_response,
                    "pipeline_postprocessing": [
                        *result.raw_response.get("pipeline_postprocessing", []),
                        "unwrapped_san_directive_expression",
                    ],
                }
        normalized_code = self._normalize_misplaced_watch_registration(result.code)
        if normalized_code != result.code:
            result.code = normalized_code
            if isinstance(result.raw_response, dict):
                result.raw_response = {
                    **result.raw_response,
                    "pipeline_postprocessing": [
                        *result.raw_response.get("pipeline_postprocessing", []),
                        "moved_watch_registration_into_lifecycle",
                    ],
                }
        if any(
            issue.get("code") == "invalid_s_for_key_binding"
            for issue in stage_input.validation_errors
        ):
            result.code = self._normalize_redundant_s_for_attributes(result.code)
        if any(
            issue.get("code") == "nested_state_mutation"
            for issue in stage_input.validation_errors
        ):
            normalized_code = self._normalize_mutated_state_array_aliases(result.code)
            if normalized_code != result.code:
                result.code = normalized_code
                if isinstance(result.raw_response, dict):
                    result.raw_response = {
                        **result.raw_response,
                        "pipeline_postprocessing": [
                            *result.raw_response.get("pipeline_postprocessing", []),
                            "cloned_state_array_before_local_mutation",
                        ],
                    }
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

    @classmethod
    def _normalize_wrapped_san_directives(cls, code: str) -> str:
        def unwrap(match: re.Match[str]) -> str:
            expression = match.group("one_way")
            if expression is None:
                expression = match.group("two_way")
            return (
                f"{match.group('directive')}={match.group('quote')}"
                f"{(expression or '').strip()}{match.group('quote')}"
            )

        return cls.WRAPPED_SAN_DIRECTIVE_PATTERN.sub(unwrap, code)

    @classmethod
    def _normalize_misplaced_watch_registration(cls, code: str) -> str:
        wrapper_pattern = re.compile(r"(?m)^([ \t]*)watch\s*\(\s*\)\s*\{")
        wrapper_match = wrapper_pattern.search(code)
        if not wrapper_match:
            return code

        wrapper_open = code.find("{", wrapper_match.start(), wrapper_match.end())
        wrapper_close = cls._find_matching_js_brace(code, wrapper_open)
        if wrapper_close < 0:
            return code
        wrapper_body = code[wrapper_open + 1:wrapper_close]
        if not re.search(r"\bthis\.watch\s*\(", wrapper_body):
            return code

        target_match = None
        for hook_name in ("inited", "attached"):
            target_match = re.search(
                rf"(?m)^([ \t]*){hook_name}\s*\([^)]*\)\s*\{{",
                code,
            )
            if target_match:
                break
        if not target_match:
            return code

        target_open = code.find("{", target_match.start(), target_match.end())
        target_close = cls._find_matching_js_brace(code, target_open)
        if target_close < 0:
            return code

        body_lines = wrapper_body.splitlines()
        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)
        while body_lines and not body_lines[-1].strip():
            body_lines.pop()
        if not body_lines:
            return code
        body_indent = min(
            len(line) - len(line.lstrip())
            for line in body_lines
            if line.strip()
        )
        target_indent = target_match.group(1) + "  "
        moved_lines = [
            target_indent + line[body_indent:] if line.strip() else ""
            for line in body_lines
        ]
        target_line_start = code.rfind("\n", 0, target_close) + 1
        if not code[target_line_start:target_close].strip():
            insertion_at = target_line_start
            insertion = "\n".join(moved_lines) + "\n"
        else:
            insertion_at = target_close
            insertion = (
                "\n" + "\n".join(moved_lines) + "\n" + target_match.group(1)
            )

        wrapper_end = wrapper_close + 1
        while wrapper_end < len(code) and code[wrapper_end] in " \t":
            wrapper_end += 1
        if wrapper_end < len(code) and code[wrapper_end] == ",":
            wrapper_end += 1

        replacements = [
            (insertion_at, insertion_at, insertion),
            (wrapper_match.start(), wrapper_end, ""),
        ]
        normalized = code
        for start, end, replacement in sorted(replacements, reverse=True):
            normalized = normalized[:start] + replacement + normalized[end:]
        return normalized

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
    def _normalize_mutated_state_array_aliases(cls, code: str) -> str:
        replacements: list[tuple[int, int, str]] = []
        mutator_names = "|".join(cls.MUTATING_ARRAY_METHODS)

        for method_match in cls.METHOD_DEFINITION_PATTERN.finditer(code):
            method_name = method_match.group(2)
            if method_name in cls.JAVASCRIPT_CONTROL_KEYWORDS:
                continue
            opening_index = method_match.end() - 1
            closing_index = cls._find_matching_js_brace(code, opening_index)
            if closing_index < 0:
                continue

            body_start = opening_index + 1
            method_body = code[body_start:closing_index]
            for alias_match in cls.STATE_ARRAY_ALIAS_PATTERN.finditer(method_body):
                alias = alias_match.group("alias")
                field = alias_match.group("field")
                mutation = re.compile(
                    rf"\b{re.escape(alias)}\s*\.\s*(?:{mutator_names})\s*\("
                )
                writeback = re.compile(
                    rf"\bthis\.data\.set\s*\(\s*(['\"]){re.escape(field)}\1\s*,"
                )
                trailing_body = method_body[alias_match.end():]
                if not mutation.search(trailing_body) or not writeback.search(trailing_body):
                    continue

                get_expression = f"this.data.get({alias_match.group('quote')}{field}{alias_match.group('quote')})"
                if alias_match.group("fallback"):
                    get_expression = f"({get_expression} || [])"
                replacement = (
                    f"{alias_match.group('kind')} {alias} = [...{get_expression}];"
                )
                replacements.append((
                    body_start + alias_match.start(),
                    body_start + alias_match.end(),
                    replacement,
                ))

        normalized = code
        for start, end, replacement in reversed(replacements):
            normalized = normalized[:start] + replacement + normalized[end:]
        return normalized

    @classmethod
    def _apply_deterministic_repairs(
        cls,
        code: str,
        validation_errors: list[dict[str, Any]],
        visual_eval_errors: list[dict[str, Any]],
    ) -> str:
        error_codes = {issue.get("code") for issue in validation_errors}
        if "invalid_san_directive_interpolation" in error_codes:
            normalized = cls._normalize_wrapped_san_directives(code)
            if normalized != code:
                return normalized
        if "watch_registration_not_in_lifecycle" in error_codes:
            normalized = cls._normalize_misplaced_watch_registration(code)
            if normalized != code:
                return normalized
        if "vue_methods_wrapper" in error_codes:
            normalized = cls._normalize_vue_methods_wrapper(code)
            if normalized != code:
                return normalized
        if error_codes == {"nested_state_mutation"} and not visual_eval_errors:
            return cls._normalize_mutated_state_array_aliases(code)
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
