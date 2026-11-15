import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from migration_pipeline.repair_client import RepairRequest, RepairResult, create_repair_client
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.utils.source_event_semantics import repair_source_events
from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.parent_prop_semantics import parent_prop_semantics
from migration_pipeline.utils.source_template_semantics import source_template_semantics
from migration_pipeline.utils.source_dom_semantics import source_dom_semantics
from migration_pipeline.utils.source_payload_semantics import source_payload_semantics
from migration_pipeline.utils.source_render_call_semantics import source_render_call_semantics
from migration_pipeline.utils.source_render_dependency_semantics import source_render_dependency_semantics
from migration_pipeline.utils.source_array_transaction_semantics import source_array_transaction_semantics
from migration_pipeline.utils.source_child_initialization_semantics import source_child_initialization_semantics
from migration_pipeline.utils.residual_semantics import residual_semantics
from migration_pipeline.utils.textarea_binding import textarea_binding
from migration_pipeline.utils.inline_identifier_recovery import recover_inline_identifiers
from migration_pipeline.utils.stateful_helper_semantics import explicit_helper_dependencies
from migration_pipeline.stages.validate import ValidateStage


@dataclass
class RepairStageInput:
    ssm: dict[str, Any]
    generated_code: str = ""
    generated_file_path: str = ""
    source_file: str = ""
    vue_file_path: str = ""
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
        vue = (Path(stage_input.vue_file_path).read_text(encoding="utf-8")
               if stage_input.vue_file_path and Path(stage_input.vue_file_path).is_file() else "")
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
            vue_source=vue,
        ))
        deterministic_code, deterministic_repairs = (current_code, [])
        if not stage_input.metadata.get("skip_deterministic_prepass", False):
            deterministic_code, deterministic_repairs = self._deterministic_repair_plan(
                current_code,
                stage_input.validation_errors,
                stage_input.visual_eval_errors,
                stage_input.ssm,
                stage_input.vue_file_path,
                **({"enable_residual_v2": True} if stage_input.metadata.get("semantic_rule_set") == "residual_v2" else {}),
            )
        if deterministic_code != current_code:
            normalizer_model = (
                deterministic_repairs[0][0]
                if len(deterministic_repairs) == 1
                else "san_combined_structural_normalizer"
            )
            normalization_names = [item[1] for item in deterministic_repairs]
            normalization = (
                normalization_names[0]
                if len(normalization_names) == 1
                else "combined_structural_normalization"
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
                raw_response={
                    "normalization": normalization,
                    "normalizations": normalization_names,
                },
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
        normalized_code = self._normalize_simple_template_syntax(result.code)
        if normalized_code != result.code:
            result.code = normalized_code
            if isinstance(result.raw_response, dict):
                result.raw_response = {
                    **result.raw_response,
                    "pipeline_postprocessing": [
                        *result.raw_response.get("pipeline_postprocessing", []),
                        "normalized_simple_san_template_syntax",
                    ],
                }
        normalized_code = self._normalize_empty_modifier_handlers(result.code)
        if normalized_code != result.code:
            result.code = normalized_code
            if isinstance(result.raw_response, dict):
                result.raw_response = {
                    **result.raw_response,
                    "pipeline_postprocessing": [
                        *result.raw_response.get("pipeline_postprocessing", []),
                        "normalized_empty_san_modifier_handlers",
                    ],
                }
        normalized_code = self._normalize_duplicate_class_attributes(result.code)
        if normalized_code != result.code:
            result.code = normalized_code
            if isinstance(result.raw_response, dict):
                result.raw_response = {
                    **result.raw_response,
                    "pipeline_postprocessing": [
                        *result.raw_response.get("pipeline_postprocessing", []),
                        "merged_static_and_dynamic_class_attributes",
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
        normalized_code = self._normalize_vue_methods_wrapper(result.code)
        if normalized_code != result.code:
            result.code = normalized_code
            if isinstance(result.raw_response, dict):
                result.raw_response = {
                    **result.raw_response,
                    "pipeline_postprocessing": [
                        *result.raw_response.get("pipeline_postprocessing", []),
                        "unwrapped_san_component_methods_options",
                    ],
                }
        normalized_code = self._normalize_parent_reserved_init_data(result.code)
        if normalized_code != result.code:
            result.code = normalized_code
            if isinstance(result.raw_response, dict):
                result.raw_response = {
                    **result.raw_response,
                    "pipeline_postprocessing": [
                        *result.raw_response.get("pipeline_postprocessing", []),
                        "renamed_parent_business_initData",
                    ],
                }
        normalized_code = self._normalize_missing_component_registration(
            result.code,
            stage_input.ssm,
        )
        if normalized_code != result.code:
            result.code = normalized_code
            if isinstance(result.raw_response, dict):
                result.raw_response = {
                    **result.raw_response,
                    "pipeline_postprocessing": [
                        *result.raw_response.get("pipeline_postprocessing", []),
                        "registered_defined_inline_components",
                    ],
                }
        normalized_code = self._normalize_unresolved_source_event_alias(
            result.code, stage_input.ssm,
        )
        if normalized_code != result.code:
            result.code = normalized_code
            if isinstance(result.raw_response, dict):
                result.raw_response = {
                    **result.raw_response,
                    "pipeline_postprocessing": [
                        *result.raw_response.get("pipeline_postprocessing", []),
                        "restored_unresolved_source_event_handler",
                    ],
                }
        normalized_code = self._normalize_source_boolean_assignment_events(
            result.code, stage_input.ssm,
        )
        if normalized_code != result.code:
            result.code = normalized_code
            if isinstance(result.raw_response, dict):
                result.raw_response = {
                    **result.raw_response,
                    "pipeline_postprocessing": [
                        *result.raw_response.get("pipeline_postprocessing", []),
                        "converted_source_boolean_assignment_events",
                    ],
                }
        normalized_code = self._normalize_misplaced_mounted_first_call(
            result.code, stage_input.ssm,
        )
        if normalized_code != result.code:
            result.code = normalized_code
            if isinstance(result.raw_response, dict):
                result.raw_response = {
                    **result.raw_response,
                    "pipeline_postprocessing": [
                        *result.raw_response.get("pipeline_postprocessing", []),
                        "restored_mounted_first_call_order",
                    ],
                }
        normalized_code = self._normalize_parent_premount_noop_writes(
            result.code, stage_input.ssm,
        )
        if normalized_code != result.code:
            result.code = normalized_code
            if isinstance(result.raw_response, dict):
                result.raw_response = {
                    **result.raw_response,
                    "pipeline_postprocessing": [
                        *result.raw_response.get("pipeline_postprocessing", []),
                        "removed_parent_premount_identity_writes",
                    ],
                }
        if any(
            issue.get("code") == "invalid_s_for_key_binding"
            for issue in stage_input.validation_errors
        ):
            result.code = self._normalize_redundant_s_for_attributes(result.code)
        if stage_input.metadata.get('semantic_rule_set') != 'residual_v2' and any(
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
            normalized_code = self._normalize_terminal_state_array_splice(
                result.code, stage_input.ssm,
            )
            if normalized_code != result.code:
                result.code = normalized_code
                if isinstance(result.raw_response, dict):
                    result.raw_response = {
                        **result.raw_response,
                        "pipeline_postprocessing": [
                            *result.raw_response.get("pipeline_postprocessing", []),
                            "cloned_and_committed_terminal_state_array_splice",
                        ],
                    }
        if stage_input.metadata.get('semantic_rule_set') == 'residual_v2':
            for transform in (lambda code: recover_inline_identifiers(code, stage_input.ssm), explicit_helper_dependencies):
                changed = transform(result.code)
                if changed['code'] != result.code:
                    result.code = changed['code']
                    raw = result.raw_response if isinstance(result.raw_response, dict) else {}
                    result.raw_response = {**raw, 'pipeline_postprocessing': [
                        *raw.get('pipeline_postprocessing', []), *changed['changes']]}
        semantic = inspect_semantics(result.code, vue, repair=True, ssm=stage_input.ssm)
        if semantic["code"] != result.code:
            result.code = semantic["code"]
            raw = result.raw_response if isinstance(result.raw_response, dict) else {}
            result.raw_response = {
                **raw,
                "pipeline_postprocessing": [
                    *raw.get("pipeline_postprocessing", []),
                    *semantic["changes"],
                ],
            }
        if stage_input.metadata.get("semantic_rule_set") == "residual_v2":
            template = source_template_semantics(result.code, vue, repair=True)
            if template["code"] != result.code:
                result.code = template["code"]
                raw = result.raw_response if isinstance(result.raw_response, dict) else {}
                result.raw_response = {**raw, "pipeline_postprocessing": [
                    *raw.get("pipeline_postprocessing", []), *template["changes"]]}
            props = parent_prop_semantics(result.code, vue, repair=True)
            if props["code"] != result.code:
                result.code = props["code"]
                raw = result.raw_response if isinstance(result.raw_response, dict) else {}
                result.raw_response = {**raw, "pipeline_postprocessing": [
                    *raw.get("pipeline_postprocessing", []), *props["changes"]]}
            dom = source_dom_semantics(result.code, vue, stage_input.ssm, repair=True)
            if dom['code'] != result.code:
                result.code = dom['code']
                raw = result.raw_response if isinstance(result.raw_response, dict) else {}
                result.raw_response = {**raw, 'pipeline_postprocessing': [
                    *raw.get('pipeline_postprocessing', []), *dom['changes']]}
            payload = source_payload_semantics(result.code, vue, stage_input.ssm, repair=True)
            if payload['code'] != result.code:
                result.code = payload['code']
                raw = result.raw_response if isinstance(result.raw_response, dict) else {}
                result.raw_response = {**raw, 'pipeline_postprocessing': [
                    *raw.get('pipeline_postprocessing', []), *payload['changes']]}
            render_calls = source_render_call_semantics(result.code, vue, stage_input.ssm, repair=True)
            if render_calls['code'] != result.code:
                result.code = render_calls['code']
                raw = result.raw_response if isinstance(result.raw_response, dict) else {}
                result.raw_response = {**raw, 'pipeline_postprocessing': [
                    *raw.get('pipeline_postprocessing', []), *render_calls['changes']]}
            dependencies = source_render_dependency_semantics(result.code, vue, repair=True)
            if dependencies['code'] != result.code:
                result.code = dependencies['code']
                raw = result.raw_response if isinstance(result.raw_response, dict) else {}
                result.raw_response = {**raw, 'pipeline_postprocessing': [
                    *raw.get('pipeline_postprocessing', []), *dependencies['changes']]}
            transactions = source_array_transaction_semantics(result.code, vue, repair=True)
            if transactions['code'] != result.code:
                result.code = transactions['code']
                raw = result.raw_response if isinstance(result.raw_response, dict) else {}
                result.raw_response = {**raw, 'pipeline_postprocessing': [
                    *raw.get('pipeline_postprocessing', []), *transactions['changes']]}
            child_startup = source_child_initialization_semantics(result.code, vue, repair=True)
            if child_startup['code'] != result.code:
                result.code = child_startup['code']
                raw = result.raw_response if isinstance(result.raw_response, dict) else {}
                result.raw_response = {**raw, 'pipeline_postprocessing': [
                    *raw.get('pipeline_postprocessing', []), *child_startup['changes']]}
            residual = residual_semantics(result.code, stage_input.ssm, repair=True)
            if residual["code"] != result.code:
                result.code = residual["code"]
                raw = result.raw_response if isinstance(result.raw_response, dict) else {}
                result.raw_response = {**raw, "pipeline_postprocessing": [
                    *raw.get("pipeline_postprocessing", []), *residual["changes"]]}
        textarea = textarea_binding(result.code, repair=True) if '<textarea' in result.code.lower() else {'code': result.code}
        if textarea['code'] != result.code:
            result.code = textarea['code']
            raw = result.raw_response if isinstance(result.raw_response, dict) else {}
            result.raw_response = {**raw, 'pipeline_postprocessing': [
                *raw.get('pipeline_postprocessing', []), *textarea['changes']]}
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
            vue_file_path=state.get("vue_file_path", "") or "",
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
    def _normalize_duplicate_class_attributes(cls, code: str) -> str:
        """Merge only an unambiguous static class plus one San class interpolation."""
        template = re.search(r"<template\b[^>]*>(.*?)</template\s*>", code, re.I | re.S)
        if not template:
            return code

        def merge_tag(match: re.Match[str]) -> str:
            tag = match.group(0)
            classes = [
                attribute for attribute in cls.ATTRIBUTE_PATTERN.finditer(tag)
                if attribute.group(1).lower() == "class"
            ]
            if len(classes) != 2:
                return tag
            static = [
                attribute for attribute in classes
                if "{{" not in attribute.group(3) and "{=" not in attribute.group(3)
            ]
            if len(static) != 1 or not static[0].group(3).strip():
                return tag
            dynamic = classes[0] if classes[1] is static[0] else classes[1]
            interpolation = re.fullmatch(r"\s*\{\{\s*(.*?)\s*\}\}\s*", dynamic.group(3), re.S)
            if not interpolation:
                return tag
            quote = static[0].group(2)
            expression = interpolation.group(1).strip()
            if not expression or quote in expression:
                return tag
            combined = f"{static[0].group(3).strip()} {{{{{expression}}}}}"
            replacements = (
                (static[0].start(), static[0].end(), f" class={quote}{combined}{quote}"),
                (dynamic.start(), dynamic.end(), ""),
            )
            for start, end, replacement in sorted(replacements, reverse=True):
                tag = tag[:start] + replacement + tag[end:]
            return tag

        normalized_template = cls.OPENING_TAG_PATTERN.sub(merge_tag, template.group(1))
        normalized = code[:template.start(1)] + normalized_template + code[template.end(1):]

        def merge_inline_template(match: re.Match[str]) -> str:
            return (
                match.group(1)
                + cls.OPENING_TAG_PATTERN.sub(merge_tag, match.group(2))
                + match.group(3)
            )

        # Inline san.defineComponent children carry backtick templates inside
        # the script block; the outer SFC template check cannot see them.
        return re.sub(
            r"(\btemplate\s*:\s*`)([\s\S]*?)(`)",
            merge_inline_template,
            normalized,
        )

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

    @staticmethod
    def _normalize_simple_template_syntax(code: str) -> str:
        """Normalize only unambiguous San event modifiers and loop aliases.

        This intentionally does not translate assignments, empty handlers,
        non-keyboard .enter modifiers, or arbitrary JavaScript expressions.
        """
        identifier = r"[A-Za-z_$][\w$]*"
        modifier_name = re.compile(r"(on-[\w-]+)\.(prevent|stop|enter)")
        simple_handler = re.compile(rf"{identifier}")
        simple_argument = rf"(?:{identifier}(?:\.{identifier})*|-?\d+(?:\.\d+)?|'[^'\\]*'|\"[^\"\\]*\")"
        simple_method_call = re.compile(
            rf"(?P<name>{identifier})\(\s*(?:{simple_argument}(?:\s*,\s*{simple_argument})*)?\s*\)"
        )
        tuple_prefix = re.compile(
            rf"\s*\(\s*(?P<item>{identifier})\s*,\s*"
            rf"(?P<index>{identifier})\s*\)\s+in\b"
        )

        def normalize_template(template: str) -> str:
            def normalize_tag(tag_match: re.Match[str]) -> str:
                tag = tag_match.group(0)
                replacements: list[tuple[int, int, str]] = []
                for attribute in RepairStage.ATTRIBUTE_PATTERN.finditer(tag):
                    name, quote, value = attribute.group(1, 2, 3)
                    raw = attribute.group(0)
                    modifier = modifier_name.fullmatch(name)
                    method_call = simple_method_call.fullmatch(value)
                    safe_handler = bool(
                        simple_handler.fullmatch(value)
                        or (
                            method_call
                            and "$event" not in value
                            and method_call.group("name") not in {"dispatch", "emit"}
                        )
                    )
                    safe_modifier = bool(
                        modifier
                        and (
                            modifier.group(2) != "enter"
                            or modifier.group(1) in {"on-keyup", "on-keydown", "on-keypress"}
                        )
                    )
                    if safe_modifier and safe_handler:
                        replacement = raw.replace(name, modifier.group(1), 1)
                        replacement = replacement.replace(
                            f"{quote}{value}{quote}",
                            f"{quote}{modifier.group(2)}:{value}{quote}",
                            1,
                        )
                    elif name == "s-for" and (tuple_match := tuple_prefix.match(value)):
                        loop = (
                            f"{tuple_match.group('item')}, {tuple_match.group('index')} in"
                            f"{value[tuple_match.end():]}"
                        )
                        replacement = raw.replace(
                            f"{quote}{value}{quote}", f"{quote}{loop}{quote}", 1
                        )
                    else:
                        continue
                    replacements.append((attribute.start(), attribute.end(), replacement))
                for start, end, replacement in reversed(replacements):
                    tag = tag[:start] + replacement + tag[end:]
                return tag

            return RepairStage.OPENING_TAG_PATTERN.sub(normalize_tag, template)

        opaque_spans = [
            (match.start(), match.end())
            for match in re.finditer(
                r"<(?:script|style)\b[^>]*>[\s\S]*?</(?:script|style)\s*>",
                code,
                flags=re.IGNORECASE,
            )
        ]

        def normalize_outer_template(match: re.Match[str]) -> str:
            if any(start <= match.start() < end for start, end in opaque_spans):
                return match.group(0)
            return match.group(1) + normalize_template(match.group(2)) + match.group(3)

        code = re.sub(
            r"(<template\b[^>]*>)([\s\S]*?)(</template\s*>)",
            normalize_outer_template,
            code,
            flags=re.IGNORECASE,
        )
        return re.sub(
            r"(\btemplate\s*:\s*`)([\s\S]*?)(`)",
            lambda match: match.group(1) + normalize_template(match.group(2)) + match.group(3),
            code,
        )

    @classmethod
    def _normalize_empty_modifier_handlers(cls, code: str) -> str:
        """Scope a no-op method to components with empty .stop/.prevent attrs.

        Bare modifiers and modifiers with an empty quoted handler are equivalent
        here. Existing nonempty handlers, including fire(...), are left for
        contextual repair.
        """
        empty_modifier = re.compile(
            r"(?<![\w:=-])on-(?P<event>[A-Za-z][\w-]*)\."
            r"(?P<modifier>stop|prevent)(?![\w.-])"
            r"(?:\s*=\s*(?P<quote>['\"])(?P=quote))?(?=\s|/?>)"
        )

        def normalize_template(template: str, method_name: str) -> tuple[str, bool]:
            changed = False

            def normalize_tag(match: re.Match[str]) -> str:
                nonlocal changed
                tag = match.group(0)
                valued_attributes = list(cls.ATTRIBUTE_PATTERN.finditer(tag))
                replacements: list[tuple[int, int, str]] = []
                for attribute in empty_modifier.finditer(tag):
                    event_name = attribute.group("event")
                    modifier = attribute.group("modifier")
                    containing = next(
                        (valued for valued in valued_attributes
                         if valued.start() <= attribute.start() < valued.end()),
                        None,
                    )
                    if containing and not (
                        containing.start(1) == attribute.start()
                        and containing.end() == attribute.end()
                        and containing.group(1) == f"on-{event_name}.{modifier}"
                        and containing.group(3) == ""
                    ):
                        continue
                    if re.search(rf"\bon-{re.escape(event_name)}\s*=", tag):
                        continue
                    replacements.append((
                        attribute.start(), attribute.end(),
                        f'on-{event_name}="{modifier}:{method_name}"',
                    ))
                for start, end, replacement in reversed(replacements):
                    tag = tag[:start] + replacement + tag[end:]
                    changed = True
                return tag

            return cls.OPENING_TAG_PATTERN.sub(normalize_tag, template), changed

        def unique_method(component: str) -> str:
            candidate = "__migrationNoopEvent"
            suffix = 2
            while re.search(rf"\b{re.escape(candidate)}\b", component):
                candidate = f"__migrationNoopEvent{suffix}"
                suffix += 1
            return candidate

        def append_method(component: str, method_name: str) -> str:
            if not component.endswith("}"):
                return component
            body = component[:-1].rstrip()
            if not body or body.endswith("{"):
                separator = ""
            elif body.endswith(","):
                separator = ""
            else:
                separator = ","
            return f"{body}{separator}\n  {method_name}() {{}}\n}}"

        component_openings = list(re.finditer(r"\bsan\.defineComponent\s*\(\s*\{", code))
        for opening in reversed(component_openings):
            object_open = code.find("{", opening.start())
            object_close = cls._find_matching_js_brace(code, object_open)
            if object_close < 0:
                continue
            component = code[object_open:object_close + 1]
            template_match = re.search(r"(\btemplate\s*:\s*`)([\s\S]*?)(`)", component)
            if not template_match:
                continue
            method_name = unique_method(component)
            template, changed = normalize_template(template_match.group(2), method_name)
            if not changed:
                continue
            component = (
                component[:template_match.start(2)] + template
                + component[template_match.end(2):]
            )
            code = (
                code[:object_open]
                + append_method(component, method_name)
                + code[object_close + 1:]
            )

        outer = re.search(r"(<template\b[^>]*>)([\s\S]*?)(</template\s*>)", code, re.I)
        parent = re.search(r"\bmodule\.exports\s*=\s*san\.defineComponent\s*\(\s*\{", code)
        if not outer or not parent:
            return code
        parent_open = code.find("{", parent.start())
        parent_close = cls._find_matching_js_brace(code, parent_open)
        if parent_close < 0:
            return code
        method_name = unique_method(code[parent_open:parent_close + 1])
        template, changed = normalize_template(outer.group(2), method_name)
        if not changed:
            return code
        code = code[:outer.start(2)] + template + code[outer.end(2):]
        parent = re.search(r"\bmodule\.exports\s*=\s*san\.defineComponent\s*\(\s*\{", code)
        parent_open = code.find("{", parent.start())
        parent_close = cls._find_matching_js_brace(code, parent_open)
        component = code[parent_open:parent_close + 1]
        return (
            code[:parent_open]
            + append_method(component, method_name)
            + code[parent_close + 1:]
        )

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
    def _js_brace_depth_at(
        cls,
        code: str,
        start: int,
        end: int,
        initial_depth: int = 1,
    ) -> int | None:
        depth = initial_depth
        quote = ""
        escaped = False
        line_comment = False
        block_comment = False
        index = start

        while index < end:
            char = code[index]
            next_char = code[index + 1] if index + 1 < end else ""
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
            index += 1

        if quote or line_comment or block_comment:
            return None
        return depth

    @classmethod
    def _normalize_vue_methods_wrapper(cls, code: str) -> str:
        component_ranges: list[tuple[int, int]] = []
        for component_match in re.finditer(
            r"\bsan\.defineComponent\s*\(\s*\{",
            code,
        ):
            object_open = code.rfind("{", component_match.start(), component_match.end())
            object_close = cls._find_matching_js_brace(code, object_open)
            if object_close >= 0:
                component_ranges.append((object_open, object_close))

        pattern = re.compile(r"(?m)^([ \t]*)methods\s*:\s*\{")
        replacements: list[tuple[int, int, str]] = []
        for match in pattern.finditer(code):
            component_range = next(
                (
                    (object_open, object_close)
                    for object_open, object_close in component_ranges
                    if object_open < match.start() < object_close
                    and cls._js_brace_depth_at(
                        code,
                        object_open + 1,
                        match.start(),
                    ) == 1
                ),
                None,
            )
            if component_range is None:
                continue

            opening_index = code.find("{", match.start(), match.end())
            closing_index = cls._find_matching_js_brace(code, opening_index)
            if closing_index < 0 or closing_index >= component_range[1]:
                continue

            cursor = closing_index + 1
            while cursor < component_range[1] and code[cursor] in " \t":
                cursor += 1
            has_trailing_comma = False
            if cursor < component_range[1] and code[cursor] == ",":
                has_trailing_comma = True
                cursor += 1

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
            if has_trailing_comma:
                replacement += ","
            replacements.append((match.start(), cursor, replacement))

        normalized = code
        for start, end, replacement in reversed(replacements):
            normalized = normalized[:start] + replacement + normalized[end:]
        return normalized

    @classmethod
    def _normalize_parent_premount_noop_writes(
        cls, code: str, ssm: dict[str, Any] | None,
    ) -> str:
        """Remove identity writes only for state loaded by source mounted calls.

        The value must have no other use in the exported parent's inited hook.
        Unknown source shape, created hooks, or ambiguous syntax fail closed.
        """
        if not isinstance(ssm, dict):
            return code
        options = (ssm.get("script") or {}).get("options") or {}
        if not isinstance(options, dict):
            return code
        hooks = options.get("lifecycle_hooks") or []
        if not isinstance(hooks, list) or any(
            isinstance(hook, dict) and hook.get("vue_hook") == "created"
            for hook in hooks
        ):
            return code
        mounted = [hook for hook in hooks if isinstance(hook, dict)
                   and hook.get("vue_hook") == "mounted"
                   and hook.get("san_hook") == "attached"]
        if len(mounted) != 1:
            return code
        source_data = {item.get("name") for item in options.get("data", [])
                       if isinstance(item, dict) and item.get("name")}
        methods = {item.get("name"): item for item in options.get("methods", [])
                   if isinstance(item, dict) and item.get("name")}
        mounted_body = mounted[0].get("body") or ""
        fields: set[str] = set()
        for name in re.findall(r"\bthis\.([A-Za-z_$][\w$]*)\s*\(", mounted_body):
            method = methods.get(name)
            if method:
                fields.update(method.get("writes_inferred") or [])
        fields &= source_data
        if not fields:
            return code
        parents = list(re.finditer(
            r"\bmodule\.exports\s*=\s*san\.defineComponent\s*\(\s*\{", code,
        ))
        if len(parents) != 1:
            return code
        parent_open = code.find("{", parents[0].start(), parents[0].end())
        parent_close = cls._find_matching_js_brace(code, parent_open)
        if parent_close < 0:
            return code
        hook_pattern = re.compile(r"(?m)^[ \t]*inited\s*\(\s*\)\s*\{")
        parent_hooks = [match for match in hook_pattern.finditer(
            code, parent_open + 1, parent_close,
        ) if cls._js_brace_depth_at(code, parent_open + 1, match.start()) == 1]
        if len(parent_hooks) != 1:
            return code
        opening = parent_hooks[0].end() - 1
        closing = cls._find_matching_js_brace(code, opening)
        if closing < 0 or closing > parent_close:
            return code
        body = code[opening + 1:closing]
        removals: list[tuple[int, int]] = []
        for field in sorted(fields):
            if not isinstance(field, str) or not re.fullmatch(r"[A-Za-z_$][\w$]*", field):
                continue
            escaped = re.escape(field)
            getter = re.compile(
                rf"(?m)^[ \t]*const {escaped} = this\.data\.get\('{escaped}'\);[ \t]*(?:\r?\n|$)"
            )
            setter = re.compile(
                rf"(?m)^[ \t]*this\.data\.set\('{escaped}', {escaped}\);[ \t]*(?:\r?\n|$)"
            )
            gets = list(getter.finditer(body))
            sets = list(setter.finditer(body))
            if len(gets) != 1 or len(sets) != 1 or gets[0].end() > sets[0].start():
                continue
            if any(cls._js_brace_depth_at(body, 0, match.start()) != 1
                   for match in (*gets, *sets)):
                continue
            remaining = body[:gets[0].start()] + body[gets[0].end():sets[0].start()] + body[sets[0].end():]
            remaining_without_quoted_paths = re.sub(
                r'''(?s)'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"''',
                "", remaining,
            )
            remaining_without_quoted_paths = re.sub(
                r"(?m)^[ \t]*//[^\r\n]*", "", remaining_without_quoted_paths,
            )
            if re.search(rf"\b{escaped}\b", remaining_without_quoted_paths):
                continue
            removals.extend((match.start(), match.end()) for match in (*gets, *sets))
        normalized = body
        for start, end in sorted(removals, reverse=True):
            normalized = normalized[:start] + normalized[end:]
        return code[:opening + 1] + normalized + code[closing:]

    @classmethod
    def _normalize_parent_reserved_init_data(cls, code: str) -> str:
        component_matches = list(re.finditer(
            r"\bmodule\.exports\s*=\s*san\.defineComponent\s*\(\s*\{",
            code,
        ))
        if not component_matches:
            return code
        component_match = component_matches[-1]
        object_open = code.rfind("{", component_match.start(), component_match.end())
        object_close = cls._find_matching_js_brace(code, object_open)
        if object_close < 0:
            return code

        def top_level_methods(name: str) -> list[re.Match[str]]:
            matches = []
            for candidate in re.finditer(
                rf"(?m)^([ \t]*){re.escape(name)}\s*\([^)]*\)\s*\{{",
                code,
            ):
                if object_open < candidate.start() < object_close and cls._js_brace_depth_at(
                    code,
                    object_open + 1,
                    candidate.start(),
                ) == 1:
                    matches.append(candidate)
            return matches

        init_data_matches = top_level_methods("initData")
        init_impl_matches = top_level_methods("initDataImpl")
        method_match = None
        old_name = ""
        extra_renames: list[tuple[int, int, str]] = []

        if len(init_data_matches) > 1:
            # Keep San's state factory (the first definition) and rename the
            # later Vue business method.
            method_match = init_data_matches[-1]
            old_name = "initData"
        elif len(init_data_matches) == 1:
            # A lone method returning an object is already San's state
            # factory.  A lone imperative method is the Vue business method.
            candidate = init_data_matches[0]
            candidate_open = candidate.end() - 1
            candidate_close = cls._find_matching_js_brace(code, candidate_open)
            body = code[candidate_open + 1:candidate_close] if candidate_close >= 0 else ""
            if not re.search(r"\breturn\s*\{", body):
                method_match = candidate
                old_name = "initData"
        elif len(init_impl_matches) > 1:
            # A previous normalization may have renamed the business method
            # to initDataImpl while the generated state factory already used
            # that name.  Restore the first definition to San's reserved
            # initData() state factory, then rename only the later duplicate.
            first = init_impl_matches[0]
            extra_renames.append((
                first.start() + len(first.group(1)),
                first.start() + len(first.group(1)) + len("initDataImpl"),
                "initData",
            ))
            method_match = init_impl_matches[-1]
            old_name = "initDataImpl"

        if method_match is None:
            return code

        used_names = {
            match.group(2)
            for match in re.finditer(
                r"(?m)^([ \t]*)([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{",
                code[object_open + 1:object_close],
            )
        }
        new_name = "initDataImpl" if old_name == "initData" else "initializeDashboardData"
        suffix = 2
        while new_name in used_names and new_name != old_name:
            new_name = f"initializeDashboardData{suffix}"
            suffix += 1

        replacement_start = method_match.start() + len(method_match.group(1))
        renames = [
            *extra_renames,
            (replacement_start, replacement_start + len(old_name), new_name),
        ]
        normalized = code
        for start, end, replacement in sorted(renames, reverse=True):
            normalized = normalized[:start] + replacement + normalized[end:]
        # Recompute the exported range after renaming, then update only calls
        # belonging to that parent component.
        component_matches = list(re.finditer(
            r"\bmodule\.exports\s*=\s*san\.defineComponent\s*\(\s*\{",
            normalized,
        ))
        parent_match = component_matches[-1]
        parent_open = normalized.rfind("{", parent_match.start(), parent_match.end())
        parent_close = cls._find_matching_js_brace(normalized, parent_open)
        if parent_close < 0:
            return code
        parent = normalized[parent_open:parent_close + 1]
        parent = re.sub(
            rf"\bthis\.{re.escape(old_name)}\s*\(",
            f"this.{new_name}(",
            parent,
        )
        return normalized[:parent_open] + parent + normalized[parent_close + 1:]

    @classmethod
    def _normalize_missing_component_registration(
        cls,
        code: str,
        ssm: dict[str, Any],
    ) -> str:
        options = ((ssm.get("script") or {}).get("options") or {}) if isinstance(ssm, dict) else {}
        component_items = options.get("components") or []
        if not isinstance(component_items, list) or not component_items:
            return code

        components: list[tuple[str, str]] = []
        for item in component_items:
            if not isinstance(item, dict):
                continue
            tag = item.get("registered_name") or item.get("name") or ""
            source_name = item.get("source_name") or ""
            if not tag or not source_name:
                return code
            candidates = [
                source_name[:1].lower() + source_name[1:],
                re.sub(
                    r"-([a-zA-Z])",
                    lambda match: match.group(1).upper(),
                    str(tag),
                ),
            ]
            identifier = next(
                (
                    candidate
                    for candidate in candidates
                    if re.search(
                        rf"\bconst\s+{re.escape(candidate)}\s*=\s*san\.defineComponent\s*\(",
                        code,
                    )
                ),
                None,
            )
            if not identifier:
                return code
            components.append((str(tag), identifier))

        parent_matches = list(re.finditer(
            r"\bmodule\.exports\s*=\s*san\.defineComponent\s*\(\s*\{",
            code,
        ))
        if not parent_matches:
            return code
        parent_match = parent_matches[-1]
        parent_open = code.rfind("{", parent_match.start(), parent_match.end())
        parent_close = cls._find_matching_js_brace(code, parent_open)
        if parent_close < 0:
            return code

        components_match = None
        for candidate in re.finditer(r"(?m)^([ \t]*)components\s*:\s*\{", code):
            if not (parent_open < candidate.start() < parent_close):
                continue
            if cls._js_brace_depth_at(code, parent_open + 1, candidate.start()) == 1:
                components_match = candidate
        entries = components
        if components_match:
            components_open = code.find("{", components_match.start(), components_match.end())
            components_close = cls._find_matching_js_brace(code, components_open)
            if components_close < 0:
                return code
            existing_tags = {
                match.group(1)
                for match in re.finditer(
                    r"['\"]([^'\"]+)['\"]\s*:",
                    code[components_open + 1:components_close],
                )
            }
            entries = [item for item in components if item[0] not in existing_tags]
            if not entries:
                return code
            insertion = "\n" + ",\n".join(
                f"{components_match.group(1)}  {json_tag!r}: {identifier}"
                for json_tag, identifier in entries
            ) + "\n" + components_match.group(1)
            body = code[components_open + 1:components_close]
            if body.strip():
                insertion = "," + insertion
            return code[:components_close] + insertion + code[components_close:]

        indent_match = re.search(r"(?m)^([ \t]+)\S", code[parent_open + 1:parent_close])
        indent = indent_match.group(1) if indent_match else "  "
        block = "\n" + indent + "components: {\n"
        block += ",\n".join(
            f"{indent}  {tag!r}: {identifier}"
            for tag, identifier in entries
        )
        block += "\n" + indent + "},"
        return code[:parent_open + 1] + block + code[parent_open + 1:]

    @classmethod
    def _normalize_unresolved_source_event_alias(
        cls, code: str, ssm: dict[str, Any] | None,
    ) -> str:
        """Restore an exact source handler when only an undeclared handle-alias is bound.

        This does not rename declared handlers or infer behavior from similar names.
        Only an outer-template binding and a declared parent method are eligible.
        """
        if not isinstance(ssm, dict):
            return code
        template_model = ssm.get("template", {})
        source_bindings = {
            (item.get("event_name"), item.get("handler_expression"))
            for item in template_model.get("event_bindings", [])
            if isinstance(item, dict)
            and re.fullmatch(r"[A-Za-z_$][\w$]*", item.get("handler_expression") or "")
        } if isinstance(template_model, dict) else set()
        if not source_bindings:
            return code

        outer = re.search(r"(<template\b[^>]*>)([\s\S]*?)(</template\s*>)", code, re.I)
        parent = re.search(r"\bmodule\.exports\s*=\s*san\.defineComponent\s*\(\s*\{", code)
        if not outer or not parent:
            return code
        object_open = code.find("{", parent.start(), parent.end())
        object_close = cls._find_matching_js_brace(code, object_open)
        if object_close < 0:
            return code
        parent_methods = {
            match.group(2)
            for match in cls.METHOD_DEFINITION_PATTERN.finditer(code, object_open + 1, object_close)
            if cls._js_brace_depth_at(code, object_open + 1, match.start()) == 1
        }
        if not parent_methods:
            return code

        def normalize_tag(match: re.Match[str]) -> str:
            tag = match.group(0)
            replacements: list[tuple[int, int, str]] = []
            for attribute in cls.ATTRIBUTE_PATTERN.finditer(tag):
                name, quote, alias = attribute.group(1, 2, 3)
                if not name.startswith("on-") or alias in parent_methods:
                    continue
                alias_match = re.fullmatch(r"handle([A-Z][A-Za-z0-9_$]*)", alias)
                if not alias_match:
                    continue
                suffix = alias_match.group(1)
                source_name = suffix[0].lower() + suffix[1:]
                if (name[3:], source_name) not in source_bindings or source_name not in parent_methods:
                    continue
                replacements.append((
                    attribute.start(3), attribute.end(3), source_name,
                ))
            for start, end, replacement in reversed(replacements):
                tag = tag[:start] + replacement + tag[end:]
            return tag

        normalized = cls.OPENING_TAG_PATTERN.sub(normalize_tag, outer.group(2))
        return code[:outer.start(2)] + normalized + code[outer.end(2):]

    @classmethod
    def _normalize_source_boolean_assignment_events(
        cls, code: str, ssm: dict[str, Any] | None,
    ) -> str:
        """Convert only source-corroborated boolean data assignments in outer events.

        Arbitrary assignments, computed fields, child templates, and unknown
        parent state remain untouched. Reuse an existing exact setter when safe.
        """
        if not isinstance(ssm, dict):
            return code
        template_model = ssm.get("template", {})
        bindings = template_model.get("event_bindings", []) if isinstance(template_model, dict) else []
        assignment = re.compile(r"\s*([A-Za-z_$][\w$]*)\s*=\s*(true|false)\s*")
        source_assignment_counts = Counter(
            (item.get("event_name"), parsed.group(1), parsed.group(2))
            for item in bindings if isinstance(item, dict)
            if (parsed := assignment.fullmatch(str(item.get("handler_expression") or "")))
        )
        if not source_assignment_counts:
            return code
        script_model = ssm.get("script", {})
        options = script_model.get("options", {}) if isinstance(script_model, dict) else {}
        source_data = {
            item.get("name") for item in options.get("data", [])
            if isinstance(item, dict) and item.get("name")
        } if isinstance(options, dict) else set()
        outer = re.search(r"(<template\b[^>]*>)([\s\S]*?)(</template\s*>)", code, re.I)
        parent = re.search(r"\bmodule\.exports\s*=\s*san\.defineComponent\s*\(\s*\{", code)
        if not outer or not parent or not source_data:
            return code
        parent_open = code.find("{", parent.start(), parent.end())
        parent_close = cls._find_matching_js_brace(code, parent_open)
        if parent_close < 0:
            return code
        parent_body = code[parent_open + 1:parent_close]
        data_types_match = re.search(r"\bdataTypes\s*:\s*\{", parent_body)
        if not data_types_match:
            return code
        type_open = parent_open + 1 + data_types_match.end() - 1
        type_close = cls._find_matching_js_brace(code, type_open)
        if type_close < 0 or type_close > parent_close:
            return code
        boolean_fields = {
            match.group(1) for match in re.finditer(
                r"\b([A-Za-z_$][\w$]*)\s*:\s*DataTypes\.bool\b",
                code[type_open + 1:type_close],
            )
        } & source_data
        parent_methods: dict[str, str] = {}
        for method in cls.METHOD_DEFINITION_PATTERN.finditer(code, parent_open + 1, parent_close):
            if cls._js_brace_depth_at(code, parent_open + 1, method.start()) != 1:
                continue
            method_close = cls._find_matching_js_brace(code, method.end() - 1)
            if method_close < 0 or method_close > parent_close:
                continue
            parent_methods[method.group(2)] = code[method.end():method_close]
        init_body = parent_methods.get("initData", "")
        boolean_fields = {
            field for field in boolean_fields
            if re.search(rf"\b{re.escape(field)}\s*:\s*(?:true|false)\b", init_body)
        }
        if not boolean_fields:
            return code
        candidate_assignment_counts: Counter[tuple[str, str, str]] = Counter()
        for tag_match in cls.OPENING_TAG_PATTERN.finditer(outer.group(2)):
            for attribute in cls.ATTRIBUTE_PATTERN.finditer(tag_match.group(0)):
                parsed = assignment.fullmatch(attribute.group(3))
                if attribute.group(1).startswith("on-") and parsed:
                    key = (attribute.group(1)[3:], parsed.group(1), parsed.group(2))
                    if key in source_assignment_counts:
                        candidate_assignment_counts[key] += 1
        if any(candidate_assignment_counts[key] != source_assignment_counts[key]
               for key in candidate_assignment_counts):
            return code
        new_methods: dict[str, tuple[str, str]] = {}

        def normalize_tag(match: re.Match[str]) -> str:
            tag = match.group(0)
            replacements: list[tuple[int, int, str]] = []
            for attribute in cls.ATTRIBUTE_PATTERN.finditer(tag):
                name, quote, value = attribute.group(1, 2, 3)
                parsed = assignment.fullmatch(value)
                if not name.startswith("on-") or not parsed:
                    continue
                field, literal = parsed.group(1, 2)
                if ((name[3:], field, literal) not in source_assignment_counts
                        or field not in boolean_fields):
                    continue
                setter = re.compile(
                    rf"\s*this\.data\.set\(\s*['\"]{re.escape(field)}['\"]\s*,\s*{literal}\s*\);?\s*"
                )
                existing = [method_name for method_name, body in parent_methods.items()
                            if setter.fullmatch(body)]
                if len(existing) == 1:
                    method_name = existing[0]
                elif existing:
                    continue
                else:
                    method_name = f"__migrationSet{field[0].upper()}{field[1:]}{literal.title()}"
                    if method_name in parent_methods or re.search(
                        rf"\b{re.escape(method_name)}\s*\(", parent_body
                    ):
                        continue
                    new_methods[method_name] = (field, literal)
                replacements.append((attribute.start(3), attribute.end(3), method_name))
            for start, end, replacement in reversed(replacements):
                tag = tag[:start] + replacement + tag[end:]
            return tag

        normalized_template = cls.OPENING_TAG_PATTERN.sub(normalize_tag, outer.group(2))
        if normalized_template == outer.group(2):
            return code
        normalized = code[:outer.start(2)] + normalized_template + code[outer.end(2):]
        if not new_methods:
            return normalized
        parent = re.search(r"\bmodule\.exports\s*=\s*san\.defineComponent\s*\(\s*\{", normalized)
        parent_open = normalized.find("{", parent.start(), parent.end())
        parent_close = cls._find_matching_js_brace(normalized, parent_open)
        significant_end = len(normalized[:parent_close].rstrip())
        separator = "" if normalized[significant_end - 1] == "," else ","
        methods_text = separator + "\n" + ",\n".join(
            f"  {name}() {{\n    this.data.set('{field}', {literal});\n  }}"
            for name, (field, literal) in sorted(new_methods.items())
        )
        return normalized[:significant_end] + methods_text + normalized[significant_end:]

    @classmethod
    def _normalize_misplaced_mounted_first_call(
        cls, code: str, ssm: dict[str, Any] | None,
    ) -> str:
        """Restore proven mounted calls from inited to attached.

        An empty attached hook permits moving the complete contiguous source
        call sequence. Otherwise only a final misplaced first call may move
        before the already-present second call. Unknown statements fail closed.
        """
        if not isinstance(ssm, dict):
            return code
        script_model = ssm.get("script", {})
        options = script_model.get("options", {}) if isinstance(script_model, dict) else {}
        hooks = options.get("lifecycle_hooks", []) if isinstance(options, dict) else []
        mounted = [
            hook for hook in hooks
            if isinstance(hook, dict)
            and hook.get("vue_hook") == "mounted"
            and hook.get("san_hook") == "attached"
        ]
        if len(mounted) != 1:
            return code
        source_body = mounted[0].get("body", "")
        source_open = source_body.find("{")
        if source_open < 0 or cls._find_matching_js_brace(source_body, source_open) < 0:
            return code
        source_calls = [
            (match.group(1), match.group(2).strip())
            for match in re.finditer(
                r"\bthis\.([A-Za-z_$][\w$]*)\s*\(([^()]*)\)", source_body
            )
            if cls._js_brace_depth_at(source_body, source_open + 1, match.start()) == 1
        ]
        if (len(source_calls) < 2
                or source_calls[0][1] or source_calls[1][1]
                or source_calls[0][0] in [name for name, _ in source_calls[1:]]):
            return code
        first, second = source_calls[0][0], source_calls[1][0]
        parent = re.search(r"\bmodule\.exports\s*=\s*san\.defineComponent\s*\(\s*\{", code)
        if not parent:
            return code
        parent_open = code.find("{", parent.start(), parent.end())
        parent_close = cls._find_matching_js_brace(code, parent_open)
        if parent_close < 0:
            return code

        def hook_range(name: str) -> tuple[int, int] | None:
            matches = []
            pattern = re.compile(rf"(?m)^[ \t]*{re.escape(name)}\s*\(\s*\)\s*\{{")
            for match in pattern.finditer(code, parent_open + 1, parent_close):
                if cls._js_brace_depth_at(code, parent_open + 1, match.start()) != 1:
                    continue
                opening = match.end() - 1
                closing = cls._find_matching_js_brace(code, opening)
                if closing < 0 or closing > parent_close:
                    return None
                matches.append((opening + 1, closing))
            return matches[0] if len(matches) == 1 else None

        inited_range = hook_range("inited")
        attached_range = hook_range("attached")
        if not inited_range or not attached_range:
            return code
        inited_body = code[slice(*inited_range)]
        attached_body = code[slice(*attached_range)]
        first_call = re.compile(
            rf"(?m)^[ \t]*this\.{re.escape(first)}\s*\(\s*\)\s*;[ \t]*(?:\r?\n|$)"
        )
        first_matches = list(first_call.finditer(inited_body))
        if len(first_matches) != 1 or re.search(
            rf"\bthis\.{re.escape(first)}\s*\(", attached_body
        ):
            return code
        first_match = first_matches[0]
        if cls._js_brace_depth_at(inited_body, 0, first_match.start()) != 1:
            return code
        if not attached_body.strip():
            call_statement = re.compile(
                r"\s*this\.([A-Za-z_$][\w$]*)\s*\(([^()]*)\)\s*;"
            )

            def complete_call_sequence(body: str) -> list[tuple[str, str]] | None:
                calls: list[tuple[str, str]] = []
                cursor = 0
                while cursor < len(body):
                    match = call_statement.match(body, cursor)
                    if not match:
                        return calls if not body[cursor:].strip() else None
                    calls.append((match.group(1), match.group(2).strip()))
                    cursor = match.end()
                return calls

            source_close = cls._find_matching_js_brace(source_body, source_open)
            source_sequence = complete_call_sequence(
                source_body[source_open + 1:source_close]
            )
            inited_sequence = complete_call_sequence(inited_body[first_match.start():])
            if source_sequence and inited_sequence == source_sequence and len(source_sequence) >= 2:
                statement_start = first_match.start()
                prefix = inited_body[:statement_start]
                comment_match = re.search(r"(?m)^[ \t]*//[^\r\n]*\r?\n$", prefix)
                if comment_match and comment_match.end() == len(prefix):
                    statement_start = comment_match.start()
                statement = inited_body[statement_start:].rstrip()
                replacements = [
                    (inited_range[0] + statement_start, inited_range[1], ""),
                    (attached_range[0], attached_range[0], "\n" + statement),
                ]
                normalized = code
                for start, end, replacement in sorted(replacements, reverse=True):
                    normalized = normalized[:start] + replacement + normalized[end:]
                return normalized
        trailing = inited_body[first_match.end():]
        if re.sub(r"(?m)^[ \t]*//[^\r\n]*$", "", trailing).strip():
            return code
        if not re.match(
            rf"\s*this\.{re.escape(second)}\s*\(", attached_body
        ):
            return code

        statement_start = first_match.start()
        prefix = inited_body[:statement_start]
        comment_match = re.search(r"(?m)^[ \t]*//[^\r\n]*\r?\n$", prefix)
        if comment_match and comment_match.end() == len(prefix):
            statement_start = comment_match.start()
        statement = inited_body[statement_start:first_match.end()].rstrip("\r\n")
        attached_insertion = "\n" + statement
        replacements = [
            (inited_range[0] + statement_start, inited_range[0] + first_match.end(), ""),
            (attached_range[0], attached_range[0], attached_insertion),
        ]
        normalized = code
        for start, end, replacement in sorted(replacements, reverse=True):
            normalized = normalized[:start] + replacement + normalized[end:]
        return normalized

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
    def _normalize_terminal_state_array_splice(
        cls, code: str, ssm: dict[str, Any] | None,
    ) -> str:
        """Clone and commit one source-corroborated splice sequence in a single if block.

        This is deliberately narrower than arbitrary mutable-array repair: it
        refuses unknown control flow, multiple mutated aliases, pre-existing
        writeback, or a splice count differing from the full source method.
        """
        if not isinstance(ssm, dict):
            return code
        script_model = ssm.get("script", {})
        options = script_model.get("options", {}) if isinstance(script_model, dict) else {}
        source_methods = {
            item.get("name"): item.get("body_full") or item.get("body", "")
            for item in options.get("methods", [])
            if isinstance(item, dict) and item.get("name")
        } if isinstance(options, dict) else {}
        if not source_methods:
            return code
        parent = re.search(r"\bmodule\.exports\s*=\s*san\.defineComponent\s*\(\s*\{", code)
        if not parent:
            return code
        parent_open = code.find("{", parent.start(), parent.end())
        parent_close = cls._find_matching_js_brace(code, parent_open)
        if parent_close < 0:
            return code
        all_mutators = "|".join(cls.MUTATING_ARRAY_METHODS)
        replacements: list[tuple[int, int, str]] = []

        for method in cls.METHOD_DEFINITION_PATTERN.finditer(code, parent_open + 1, parent_close):
            method_name = method.group(2)
            source_body = source_methods.get(method_name)
            if not source_body or cls._js_brace_depth_at(code, parent_open + 1, method.start()) != 1:
                continue
            body_open = method.end() - 1
            body_close = cls._find_matching_js_brace(code, body_open)
            if body_close < 0 or body_close > parent_close:
                continue
            body = code[body_open + 1:body_close]
            aliases = list(cls.STATE_ARRAY_ALIAS_PATTERN.finditer(body))
            mutation_aliases = [
                item for item in aliases
                if re.search(
                    rf"\b{re.escape(item.group('alias'))}\s*\.\s*(?:{all_mutators})\s*\(",
                    body[item.end():],
                )
            ]
            if len(mutation_aliases) != 1:
                continue
            alias_match = mutation_aliases[0]
            alias, field = alias_match.group("alias"), alias_match.group("field")
            source_splices = re.findall(
                rf"\bthis\.{re.escape(field)}\s*\.\s*splice\s*\(", source_body
            )
            if not source_splices or re.search(
                rf"\bthis\.data\.set\s*\(\s*['\"]{re.escape(field)}['\"]\s*,", body
            ):
                continue
            mutator_calls = list(re.finditer(
                rf"\b{re.escape(alias)}\s*\.\s*(?:{all_mutators})\s*\(", body
            ))
            lines = list(re.finditer(
                rf"(?m)^[ \t]*(?:const\s+\[[^\]\r\n]+\]\s*=\s*)?"
                rf"{re.escape(alias)}\.splice\([^;\r\n()]*\);[ \t]*(?:\r?\n|$)",
                body,
            ))
            if (len(lines) != len(source_splices)
                    or len(mutator_calls) != len(lines)
                    or any(".splice" not in item.group(0) for item in mutator_calls)):
                continue
            if any(cls._js_brace_depth_at(body, 0, line.start()) is None for line in lines):
                continue
            enclosing_blocks: list[tuple[int, int]] = []
            for conditional in re.finditer(r"\bif\s*\([^()]*\)\s*\{", body):
                conditional_open = conditional.end() - 1
                conditional_close = cls._find_matching_js_brace(body, conditional_open)
                if (conditional_close >= 0
                        and all(conditional_open < line.start() < conditional_close for line in lines)):
                    enclosing_blocks.append((conditional_open, conditional_close))
            if not enclosing_blocks:
                continue
            block_open, block_close = min(enclosing_blocks, key=lambda item: item[1] - item[0])
            if (any(cls._js_brace_depth_at(body, block_open + 1, line.start()) is None
                    for line in lines)
                    or re.search(r"\b(?:return|throw|await|yield|break|continue)\b",
                                 body[lines[0].start():block_close])):
                continue
            if re.search(
                rf"\bthis\.data\.get\s*\(\s*['\"]{re.escape(field)}['\"]\s*\)",
                body[alias_match.end():],
            ):
                continue

            get_expression = f"this.data.get({alias_match.group('quote')}{field}{alias_match.group('quote')})"
            if alias_match.group("fallback"):
                get_expression = f"({get_expression} || [])"
            clone = f"{alias_match.group('kind')} {alias} = [...{get_expression}];"
            last_line = lines[-1]
            indent = re.match(r"[ \t]*", last_line.group(0)).group(0)
            commit = f"{indent}this.data.set({alias_match.group('quote')}{field}{alias_match.group('quote')}, {alias});\n"
            replacements.extend([
                (body_open + 1 + alias_match.start(), body_open + 1 + alias_match.end(), clone),
                (body_open + 1 + last_line.end(), body_open + 1 + last_line.end(), commit),
            ])

        normalized = code
        for start, end, replacement in sorted(replacements, reverse=True):
            normalized = normalized[:start] + replacement + normalized[end:]
        return normalized

    @classmethod
    def _apply_deterministic_repairs(
        cls,
        code: str,
        validation_errors: list[dict[str, Any]],
        visual_eval_errors: list[dict[str, Any]],
    ) -> str:
        return cls._deterministic_repair_plan(
            code,
            validation_errors,
            visual_eval_errors,
        )[0]

    @classmethod
    def _deterministic_repair_plan(
        cls,
        code: str,
        validation_errors: list[dict[str, Any]],
        visual_eval_errors: list[dict[str, Any]],
        ssm: dict[str, Any] | None = None,
        vue_file_path: str = "",
        *, enable_residual_v2: bool = False,
    ) -> tuple[str, list[tuple[str, str]]]:
        error_codes = {issue.get("code") for issue in validation_errors}
        normalized = code
        applied: list[tuple[str, str]] = []

        if enable_residual_v2:
            vue = (Path(vue_file_path).read_text(encoding="utf-8")
                   if vue_file_path and Path(vue_file_path).is_file() else "")
            template = source_template_semantics(normalized, vue, repair=True)
            if template["code"] != normalized:
                normalized = template["code"]
                applied.extend(("source_template_bindings", name) for name in template["changes"])
            props = parent_prop_semantics(normalized, vue, repair=True)
            if props["code"] != normalized:
                normalized = props["code"]
                applied.extend(("source_parent_prop_contracts", name) for name in props["changes"])
            dom = source_dom_semantics(normalized, vue, ssm, repair=True)
            if dom['code'] != normalized:
                normalized = dom['code']
                applied.extend(('source_scoped_dom_contracts', name) for name in dom['changes'])
            payload = source_payload_semantics(normalized, vue, ssm, repair=True)
            if payload['code'] != normalized:
                normalized = payload['code']
                applied.extend(('source_single_payload_contracts', name) for name in payload['changes'])
            render_calls = source_render_call_semantics(normalized, vue, ssm, repair=True)
            if render_calls['code'] != normalized:
                normalized = render_calls['code']
                applied.extend(('source_render_operand_contracts', name) for name in render_calls['changes'])
            dependencies = source_render_dependency_semantics(normalized, vue, repair=True)
            if dependencies['code'] != normalized:
                normalized = dependencies['code']
                applied.extend(('source_readonly_render_graph', name) for name in dependencies['changes'])
            transactions = source_array_transaction_semantics(normalized, vue, repair=True)
            if transactions['code'] != normalized:
                normalized = transactions['code']
                applied.extend(('source_array_transaction_contracts', name) for name in transactions['changes'])
            child_startup = source_child_initialization_semantics(normalized, vue, repair=True)
            if child_startup['code'] != normalized:
                normalized = child_startup['code']
                applied.extend(('source_child_startup_contracts', name) for name in child_startup['changes'])
            if 'invalid_inline_component_identifier' in error_codes:
                recovery = recover_inline_identifiers(normalized, ssm)
                if recovery['code'] != normalized:
                    normalized = recovery['code']
                    applied.extend(('source_registered_identifier_recovery', name) for name in recovery['changes'])
            if error_codes & {'hidden_template_reactive_dependency', 'invalid_san_computed_instance_method_call'}:
                helpers = explicit_helper_dependencies(normalized)
                if helpers['code'] != normalized:
                    normalized = helpers['code']
                    applied.extend(('readonly_helper_dependencies', name) for name in helpers['changes'])

        if 'invalid_san_textarea_binding' in error_codes:
            textarea = textarea_binding(normalized, repair=True)
            if textarea['code'] != normalized:
                normalized = textarea['code']
                applied.append(('textarea_value_normalizer', 'normalized_textarea_value_binding'))

        if enable_residual_v2:
            residual = residual_semantics(normalized, ssm, repair=True)
            if residual["code"] != normalized:
                normalized = residual["code"]
                applied.extend(("residual_v2_ast", name) for name in residual["changes"])

        if error_codes & {"missing_self_click_guard", "invalid_san_inline_computed_method_invocation", "event_arguments_not_landed",
                          "lifecycle_behavior_not_landed", "missing_lifecycle_mapping", "source_watch_persistence_not_landed",
                          "source_watch_persistence_unproven",
                          "source_mounted_order_not_landed", "source_startup_phase_not_landed",
                          "source_method_interface_not_landed", "source_method_trigger_added"}:
            vue = (Path(vue_file_path).read_text(encoding="utf-8")
                   if vue_file_path and Path(vue_file_path).is_file() else "")
            semantic = inspect_semantics(normalized, vue, repair=True, ssm=ssm)
            if semantic["code"] != normalized:
                normalized = semantic["code"]
                applied.extend(("bounded_ast_semantics", name) for name in semantic["changes"])

        if error_codes & {"missing_self_click_guard", "native_drag_event_misbound"}:
            vue = (Path(vue_file_path).read_text(encoding="utf-8")
                   if vue_file_path and Path(vue_file_path).is_file() else "")
            candidate = repair_source_events(normalized, error_codes, ValidateStage.NATIVE_HTML_TAGS, vue)
            if candidate != normalized:
                normalized = candidate
                applied.append((
                    "source_event_semantics_normalizer",
                    "restored_self_click_and_native_drag_semantics",
                ))

        if "invalid_san_directive_interpolation" in error_codes:
            candidate = cls._normalize_wrapped_san_directives(normalized)
            if candidate != normalized:
                normalized = candidate
                applied.append((
                    "san_directive_expression_normalizer",
                    "unwrapped_san_directive_expression",
                ))
        if (error_codes
                and error_codes <= {
                    "invalid_san_event_handler_syntax", "invalid_san_for_alias_syntax",
                    "duplicate_class_attribute",
                }
                and not visual_eval_errors):
            candidate = cls._normalize_simple_template_syntax(normalized)
            if candidate != normalized:
                normalized = candidate
                applied.append((
                    "san_template_syntax_normalizer",
                    "normalized_simple_san_template_syntax",
                ))
        if "invalid_san_event_handler_syntax" in error_codes and not visual_eval_errors:
            candidate = cls._normalize_empty_modifier_handlers(normalized)
            if candidate != normalized:
                normalized = candidate
                applied.append((
                    "san_empty_modifier_handler_normalizer",
                    "normalized_empty_san_modifier_handlers",
                ))
            candidate = cls._normalize_source_boolean_assignment_events(normalized, ssm)
            if candidate != normalized:
                normalized = candidate
                applied.append((
                    "san_source_boolean_event_normalizer",
                    "converted_source_boolean_assignment_events",
                ))
        if "watch_registration_not_in_lifecycle" in error_codes:
            candidate = cls._normalize_misplaced_watch_registration(normalized)
            if candidate != normalized:
                normalized = candidate
                applied.append((
                    "san_watch_lifecycle_normalizer",
                    "moved_watch_registration_into_lifecycle",
                ))
        if "vue_methods_wrapper" in error_codes:
            candidate = cls._normalize_vue_methods_wrapper(normalized)
            if candidate != normalized:
                normalized = candidate
                applied.append((
                    "san_methods_wrapper_normalizer",
                    "unwrapped_san_component_methods_options",
                ))
        if "reserved_init_data_method_collision" in error_codes:
            candidate = cls._normalize_parent_reserved_init_data(normalized)
            if candidate != normalized:
                normalized = candidate
                applied.append((
                    "san_reserved_init_data_normalizer",
                    "renamed_parent_business_initData",
                ))
        if "missing_component_registration" in error_codes and ssm:
            candidate = cls._normalize_missing_component_registration(normalized, ssm)
            if candidate != normalized:
                normalized = candidate
                applied.append((
                    "san_component_registration_normalizer",
                    "registered_defined_inline_components",
                ))
        if ("duplicate_class_attribute" in error_codes
                and error_codes <= {
                    "duplicate_class_attribute",
                    "invalid_san_event_handler_syntax",
                    "invalid_san_for_alias_syntax",
                }
                and not visual_eval_errors):
            candidate = cls._normalize_duplicate_class_attributes(normalized)
            if candidate != normalized:
                normalized = candidate
                applied.append((
                    "san_duplicate_class_normalizer",
                    "merged_static_and_dynamic_class_attributes",
                ))
        if not enable_residual_v2 and error_codes == {"nested_state_mutation"} and not visual_eval_errors:
            candidate = cls._normalize_mutated_state_array_aliases(normalized)
            if candidate != normalized:
                normalized = candidate
                applied.append((
                    "san_state_array_clone_normalizer",
                    "cloned_state_array_before_local_mutation",
                ))
        if error_codes == {"invalid_s_for_key_binding"} and not visual_eval_errors:
            candidate = cls._normalize_redundant_s_for_attributes(normalized)
            if candidate != normalized:
                normalized = candidate
                applied.append((
                    "san_loop_binding_normalizer",
                    "removed_redundant_s_for_key_or_trackby_attribute",
                ))
        return normalized, applied

    def _ensure_repaired_file(self, repaired_file_path: str, repaired_code: str) -> None:
        if not repaired_file_path:
            return
        path = Path(repaired_file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(repaired_code, encoding="utf-8")


def repair_san(stage_input: RepairStageInput) -> RepairStageResult:
    return RepairStage().run(stage_input)
