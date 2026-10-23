import re
import json
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from migration_pipeline.utils.san_compile import check_san_compile


@dataclass
class ValidationIssue:
    code: str
    message: str
    severity: str = "error"
    location: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationCheck:
    name: str
    passed: bool
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidateStageInput:
    generated_code: str = ""
    generated_file_path: str = ""
    ssm: dict[str, Any] | None = None
    source_file: str = ""
    vue_file_path: str = ""
    strict: bool = False
    compile_check: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def resolve_code(self) -> str:
        if self.generated_code:
            return self.generated_code
        if self.generated_file_path:
            return Path(self.generated_file_path).read_text(encoding="utf-8")
        raise ValueError("ValidateStageInput requires generated_code or generated_file_path")


@dataclass
class ValidateStageResult:
    validation_passed: bool
    validation_errors: list[dict[str, Any]]
    validation_warnings: list[dict[str, Any]]
    validation_checks: list[dict[str, Any]]
    generated_file_path: str = ""
    source_file: str = ""
    validation_summary: str = ""
    san_compile_result: dict[str, Any] | None = None

    def to_state_update(self) -> dict[str, Any]:
        return {
            "validation_passed": self.validation_passed,
            "validation_errors": self.validation_errors,
            "validation_warnings": self.validation_warnings,
            "validation_checks": self.validation_checks,
            "validation_summary": self.validation_summary,
            "san_compile_result": self.san_compile_result,
            "validate_result": asdict(self),
        }


class ValidateStage:
    SAN_REQUIRED_BLOCKS = ("template", "script", "style")
    VUE_TEMPLATE_PATTERNS = (
        (r"@[\w:-]+\s*=", "vue_event_shorthand", "San 模板中不应保留 Vue 事件简写，请迁移为 on-event。"),
        (r"\bv-if\s*=", "vue_v_if", "San 模板中不应保留 v-if，请迁移为 s-if。"),
        (r"\bv-else-if\s*=", "vue_v_else_if", "San 模板中不应保留 v-else-if，请迁移为 s-else-if。"),
        (r"\bv-else\b", "vue_v_else", "San 模板中不应保留 v-else，请迁移为 s-else。"),
        (r"\bv-for\s*=", "vue_v_for", "San 模板中不应保留 v-for，请迁移为 s-for。"),
        (r"\bv-model\s*=", "vue_v_model", "San 模板中不应保留 v-model，请迁移为 value + on-input。"),
        (r"\B:[\w:-]+\s*=", "vue_bind_shorthand", "San 模板中不应保留 Vue 属性绑定简写，请迁移为 San 表达式属性。"),
    )
    # San's {= ... =} syntax is a two-way binding.  It is only valid for an
    # assignable data path (for example, an input value).  Boolean/selection
    # attributes are derived state and must use one-way {{ ... }} interpolation;
    # otherwise the lightweight renderer treats the expression as a literal
    # attribute and the browser can receive the wrong disabled/checked state.
    DERIVED_ATTRIBUTE_TWO_WAY_PATTERN = re.compile(
        r"\b(?:disabled|checked|selected)\s*=\s*(?:\"[^\"]*\{=[^\"]*=\}[^\"]*\"|'[^']*\{=[^']*=\}[^']*')",
        re.IGNORECASE,
    )
    S_FOR_OPEN_TAG_PATTERN = re.compile(
        r"<[^>]*\bs-for\s*=\s*(?:\"[^\"]*\"|'[^']*')[^>]*>",
        re.IGNORECASE,
    )
    S_FOR_ATTRIBUTE_PATTERN = re.compile(
        r"\bs-for\s*=\s*([\"'])(.*?)\1",
        re.IGNORECASE | re.DOTALL,
    )
    TEMPLATE_ATTRIBUTE_PATTERN = re.compile(
        r"(?:^|\s)([A-Za-z_:][\w:.-]*)\s*=\s*([\"'])(.*?)\2",
        re.DOTALL,
    )
    LOOP_INDEX_IDENTIFIERS = {"index", "idx", "$index"}
    REACTIVE_RENDER_DIRECTIVES = {"s-if", "s-else-if", "s-for"}
    NATIVE_HTML_TAGS = {
        "a", "abbr", "address", "article", "aside", "audio", "b", "blockquote",
        "body", "br", "button", "canvas", "caption", "code", "col", "colgroup",
        "data", "datalist", "dd", "del", "details", "dialog", "div", "dl", "dt",
        "em", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2",
        "h3", "h4", "h5", "h6", "header", "hr", "html", "i", "iframe", "img",
        "input", "ins", "kbd", "label", "legend", "li", "main", "mark", "menu",
        "meter", "nav", "ol", "optgroup", "option", "output", "p", "picture",
        "pre", "progress", "q", "s", "section", "select", "small", "source", "span",
        "strong", "sub", "summary", "sup", "table", "tbody", "td", "template",
        "textarea", "tfoot", "th", "thead", "time", "tr", "track", "u", "ul",
        "video", "wbr",
    }
    TEMPLATE_INTERPOLATION_PATTERN = re.compile(r"\{\{(.*?)\}\}|\{=(.*?)=\}", re.DOTALL)
    TEMPLATE_METHOD_CALL_PATTERN = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(([^()]*)\)")
    DATA_GET_PATTERN = re.compile(
        r"\bthis\.data\.get\s*\(\s*(['\"])([A-Za-z_$][\w$]*)\1\s*\)"
    )
    METHOD_DEFINITION_PATTERN = re.compile(
        r"\b([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{"
    )
    STATE_ALIAS_PATTERN = re.compile(
        r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
        r"this\.data\.get\s*\(\s*(['\"])([A-Za-z_$][\w$]*)\2\s*\)"
    )
    LOCAL_ASSIGNMENT_PATTERN = re.compile(
        r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*([^;\n]+)"
    )
    MUTATING_ARRAY_METHODS = (
        "copyWithin", "fill", "pop", "push", "reverse", "shift", "sort", "splice", "unshift"
    )
    JAVASCRIPT_CONTROL_KEYWORDS = {
        "catch", "do", "for", "if", "switch", "while", "with",
    }
    VUE_SCRIPT_PATTERNS = (
        (r"export\s+default", "vue_export_default", "San 脚本应使用 module.exports = san.defineComponent(...)。"),
        (r"\bprops\s*:", "vue_props_option", "San 中 props 应迁移为 dataTypes。"),
        (r"\bmethods\s*:\s*\{", "vue_methods_wrapper", "San 方法应直接定义在组件对象顶层。"),
        (r"\bwatch\s*:\s*\{", "vue_watch_option", "Vue watch 配置不会被 San 自动注册，请在 inited/attached 中使用 this.watch(...)。"),
        (r"\bthis\.\$emit\s*\(", "vue_emit", "Vue 的 this.$emit 应迁移为 San 的 this.fire。"),
        (r"\bthis\.(?!_|data\b|fire\b|watch\b|ref\b|nextTick\b)([A-Za-z_$][\w$]*)\b(?!\s*\()", "vue_this_state", "San 状态读写应使用 this.data.get()/this.data.set()。"),
    )

    SAN_DATA_STORE_PATTERNS = (
        (
            r"\b(?:const|let|var)\s*\{[^}\n]+\}\s*=\s*this\.data\b(?!\s*\.)",
            "invalid_san_data_destructuring",
            "San this.data is a Data store, not a plain object; read each field with this.data.get('field').",
        ),
    )

    def run(self, stage_input: ValidateStageInput) -> ValidateStageResult:
        code = stage_input.resolve_code()
        ssm = stage_input.ssm or {}
        issues: list[ValidationIssue] = []
        checks: list[ValidationCheck] = []

        blocks = self._extract_blocks(code)
        self._validate_sfc_blocks(blocks, issues, checks)
        self._validate_san_script(blocks.get("script", ""), issues, checks)
        self._validate_template_rules(blocks.get("template", ""), issues, checks)
        self._validate_loop_scope_bindings(
            blocks.get("template", ""),
            blocks.get("script", ""),
            ssm,
            stage_input,
            issues,
            checks,
        )
        self._validate_script_rules(blocks.get("script", ""), ssm, issues, checks)
        self._validate_template_reactive_dependencies(
            blocks.get("template", ""),
            blocks.get("script", ""),
            issues,
            checks,
        )
        self._validate_nested_state_mutations(blocks.get("script", ""), issues, checks)
        self._validate_dom_child_order(code, stage_input, issues, checks)
        self._validate_style_rules(blocks.get("style", ""), issues, checks, strict=stage_input.strict)
        san_compile_result = self._validate_san_compile(code, stage_input, issues, checks)
        self._validate_ssm_consistency(code, blocks, ssm, issues, checks)
        self._validate_prop_defaults_landing(blocks.get("script", ""), ssm, issues, checks)
        self._validate_prop_dependent_data_initialization(blocks.get("script", ""), ssm, issues, checks)
        self._validate_data_initial_values(san_compile_result, ssm, issues, checks)
        self._validate_event_arguments_landing(blocks.get("template", ""), ssm, issues, checks)
        self._validate_custom_event_migration(blocks.get("script", ""), ssm, issues, checks)
        self._validate_datatypes_accuracy(blocks.get("script", ""), ssm, issues, checks)
        self._validate_lifecycle_mapping(blocks.get("script", ""), ssm, issues, checks)
        self._validate_event_binding_completeness(blocks.get("template", ""), ssm, issues, checks)
        self._validate_computed_watch_migration(blocks.get("script", ""), ssm, issues, checks)
        self._validate_migration_hints_landing(blocks, ssm, issues, checks)

        errors = [issue.to_dict() for issue in issues if issue.severity == "error"]
        warnings = [issue.to_dict() for issue in issues if issue.severity == "warning"]
        validation_passed = not errors
        summary = self._build_summary(validation_passed, errors, warnings, checks)

        return ValidateStageResult(
            validation_passed=validation_passed,
            validation_errors=errors,
            validation_warnings=warnings,
            validation_checks=[check.to_dict() for check in checks],
            generated_file_path=stage_input.generated_file_path,
            source_file=stage_input.source_file,
            validation_summary=summary,
            san_compile_result=san_compile_result,
        )

    def run_from_state(self, state: dict[str, Any]) -> dict[str, Any]:
        stage_input = ValidateStageInput(
            generated_code=state.get("generated_code", state.get("generation_code", "")),
            generated_file_path=state.get("generated_file_path", state.get("saved_file_path", "")),
            ssm=state.get("ssm"),
            source_file=state.get("source_file", ""),
            vue_file_path=state.get("vue_file_path", "") or "",
            strict=state.get("validation_strict", False),
            compile_check=state.get("validation_compile_check", True),
            metadata=state.get("validation_metadata", {}),
        )
        return self.run(stage_input).to_state_update()

    def _validate_sfc_blocks(
        self,
        blocks: dict[str, str],
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        for block_name in self.SAN_REQUIRED_BLOCKS:
            passed = bool(blocks.get(block_name, "").strip())
            checks.append(ValidationCheck(
                name=f"sfc_{block_name}_block",
                passed=passed,
                message=f"包含 <{block_name}> 块" if passed else f"缺少 <{block_name}> 块",
            ))
            if not passed:
                issues.append(ValidationIssue(
                    code=f"missing_{block_name}_block",
                    message=f"生成结果缺少 <{block_name}> 块。",
                    location=block_name,
                    suggestion=f"补齐 San 单文件组件的 <{block_name}>...</{block_name}>。",
                ))

    def _validate_san_script(
        self,
        script: str,
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        required_patterns = (
            ("require_san", r"const\s+san\s*=\s*require\(['\"]san['\"]\)", "显式引入 san"),
            ("require_datatypes", r"const\s+DataTypes\s*=\s*san\.DataTypes", "显式声明 DataTypes"),
            ("define_component", r"module\.exports\s*=\s*san\.defineComponent\s*\(", "使用 san.defineComponent 导出组件"),
            ("init_data", r"\binitData\s*\(", "定义 initData()"),
        )
        for name, pattern, message in required_patterns:
            passed = bool(re.search(pattern, script))
            checks.append(ValidationCheck(name=name, passed=passed, message=message))
            if not passed:
                issues.append(ValidationIssue(
                    code=f"missing_{name}",
                    message=f"San 脚本未满足要求：{message}。",
                    location="script",
                    suggestion="按 San 组件格式补齐脚本结构。",
                ))

        has_datatypes = bool(re.search(r"\bdataTypes\s*:", script))
        has_proptypes = bool(re.search(r"\bpropTypes\s*:", script))
        checks.append(ValidationCheck(
            name="data_types_option",
            passed=has_datatypes,
            message="使用 dataTypes 描述组件入参",
        ))
        if not has_datatypes:
            issues.append(ValidationIssue(
                code="missing_data_types",
                message="San 组件未使用 dataTypes。" + ("当前检测到 propTypes，必须改为 dataTypes。" if has_proptypes else ""),
                location="script",
                suggestion="将 Vue props 迁移为 San dataTypes。",
            ))

    def _validate_template_rules(
        self,
        template: str,
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        for pattern, code, suggestion in self.VUE_TEMPLATE_PATTERNS:
            matches = re.findall(pattern, template)
            passed = not matches
            checks.append(ValidationCheck(
                name=f"no_{code}",
                passed=passed,
                message=f"未残留 {code}",
            ))
            if matches:
                issues.append(ValidationIssue(
                    code=code,
                    message=f"San template 中检测到 {len(matches)} 处 Vue 模板语法残留。",
                    location="template",
                    suggestion=suggestion,
                ))

        invalid_derived_bindings = self.DERIVED_ATTRIBUTE_TWO_WAY_PATTERN.findall(template)
        binding_count = len(invalid_derived_bindings)
        binding_passed = binding_count == 0
        checks.append(ValidationCheck(
            name="derived_attributes_use_one_way_binding",
            passed=binding_passed,
            message="disabled/checked/selected 使用 {{ ... }} 单向插值，而不是 {= ... =} 双向绑定",
        ))
        if not binding_passed:
            issues.append(ValidationIssue(
                code="invalid_dynamic_attribute_binding",
                message=(
                    f"San 模板中检测到 {binding_count} 处 derived 属性使用 {{= ... =}} 双向绑定；"
                    "disabled、checked、selected 必须使用 {{ ... }} 单向插值。"
                ),
                location="template",
                suggestion="例如将 disabled=\"{= page === 1 =}\" 改为 disabled=\"{{ page === 1 }}\"。",
            ))

        custom_component_two_way_bindings = []
        for tag_match in re.finditer(
            r"<([A-Za-z][\w-]*)\b([^>]*)>", template, re.DOTALL
        ):
            tag_name = tag_match.group(1).lower()
            if tag_name in self.NATIVE_HTML_TAGS:
                continue
            for attribute in self.TEMPLATE_ATTRIBUTE_PATTERN.finditer(tag_match.group(2)):
                if "{=" in attribute.group(3):
                    custom_component_two_way_bindings.append(
                        (tag_name, attribute.group(1))
                    )

        custom_binding_passed = not custom_component_two_way_bindings
        checks.append(ValidationCheck(
            name="custom_component_props_use_one_way_binding",
            passed=custom_binding_passed,
            message="普通自定义组件 props 使用 {{ ... }} 单向绑定，而不是 {= ... =}",
        ))
        if not custom_binding_passed:
            issues.append(ValidationIssue(
                code="invalid_component_prop_two_way_binding",
                message=(
                    "San 模板中检测到普通自定义组件 props 使用双向绑定："
                    + ", ".join(
                        f"<{tag}>.{attribute}"
                        for tag, attribute in custom_component_two_way_bindings
                    )
                    + "。Vue :prop 是单向绑定，不能无依据升级为双向绑定。"
                ),
                location="template",
                suggestion=(
                    "将 value=\"{= stat.value =}\" 等普通组件属性改为 "
                    "value=\"{{ stat.value }}\"；{= ... =} 仅用于源 Vue v-model 对应的可赋值表单路径。"
                ),
            ))

        s_for_tags_with_separate_identity = [
            tag for tag in self.S_FOR_OPEN_TAG_PATTERN.findall(template)
            if any(
                attribute.group(1).lower() in {"key", "trackby"}
                for attribute in self.TEMPLATE_ATTRIBUTE_PATTERN.finditer(tag)
            )
        ]
        s_for_key_passed = not s_for_tags_with_separate_identity
        checks.append(ValidationCheck(
            name="s_for_uses_inline_trackby",
            passed=s_for_key_passed,
            message="Vue :key 使用 San s-for 内联 trackby 迁移，而不是独立 key 属性",
        ))
        if not s_for_key_passed:
            issues.append(ValidationIssue(
                code="invalid_s_for_key_binding",
                message=(
                    f"San 模板中检测到 {len(s_for_tags_with_separate_identity)} 个 s-for 节点"
                    "使用独立 key 或 trackby 属性；San 要求将 trackby 写入 s-for 表达式，"
                    "否则可能导致循环作用域、节点状态或 class 不刷新。"
                ),
                location="template",
                suggestion=(
                    "将 s-for=\"task in tasks\" key=\"{{ task.id }}\" 或 "
                    "s-for=\"task in tasks\" trackby=\"task.id\" 改为 "
                    "s-for=\"task in tasks trackby task.id\"，并删除独立属性。"
                ),
            ))

        interpolation_open = template.count("{{") + template.count("{=")
        interpolation_close = template.count("}}") + template.count("=}")
        interpolation_passed = interpolation_open == interpolation_close
        checks.append(ValidationCheck(
            name="template_interpolations_balanced",
            passed=interpolation_passed,
            message="San 模板插值分隔符完整闭合",
        ))
        if not interpolation_passed:
            issues.append(ValidationIssue(
                code="unbalanced_template_interpolation",
                message=(
                    f"San 模板插值分隔符不匹配：开放标记 {interpolation_open} 个，"
                    f"闭合标记 {interpolation_close} 个。"
                ),
                location="template",
                suggestion="检查 {{ expression }} 或 {= assignable.path =} 是否缺少结束分隔符。",
            ))

    def _validate_script_rules(
        self,
        script: str,
        ssm: dict[str, Any],
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        patterns = (*self.VUE_SCRIPT_PATTERNS, *self.SAN_DATA_STORE_PATTERNS)
        for pattern, code, suggestion in patterns:
            matches = re.findall(pattern, script)
            if code == "vue_this_state":
                state_fields = self._known_component_state_fields(script, ssm)
                matches = [name for name in matches if name in state_fields]
            passed = not matches
            checks.append(ValidationCheck(
                name=f"no_{code}",
                passed=passed,
                message=f"未残留 {code}",
            ))
            if matches:
                issues.append(ValidationIssue(
                    code=code,
                    message=f"San script 中检测到 {len(matches)} 处 Vue 写法残留。",
                    location="script",
                    suggestion=suggestion,
                ))

    def _validate_loop_scope_bindings(
        self,
        template: str,
        script: str,
        ssm: dict[str, Any],
        stage_input: ValidateStageInput,
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        source_index_aliases = self._source_loop_index_aliases(
            stage_input.vue_file_path or stage_input.source_file
        )
        state_fields = self._known_component_state_fields(script, ssm)
        findings: list[tuple[str, str]] = []

        for loop_number, tag in enumerate(self.S_FOR_OPEN_TAG_PATTERN.findall(template)):
            loop_match = self.S_FOR_ATTRIBUTE_PATTERN.search(tag)
            if not loop_match:
                continue

            loop_expression = loop_match.group(2).strip()
            declaration_match = re.match(
                r"^\s*\(?\s*([^)]*?)\s*\)?\s+in\s+.+$",
                loop_expression,
                re.DOTALL,
            )
            if not declaration_match:
                continue

            declared = {
                alias.strip()
                for alias in declaration_match.group(1).split(",")
                if re.fullmatch(r"[A-Za-z_$][\w$]*", alias.strip())
            }
            candidates = set(self.LOOP_INDEX_IDENTIFIERS)
            if loop_number < len(source_index_aliases) and source_index_aliases[loop_number]:
                candidates.add(source_index_aliases[loop_number])

            expression_values = []
            for attribute_match in self.TEMPLATE_ATTRIBUTE_PATTERN.finditer(tag):
                attribute_name = attribute_match.group(1).lower()
                attribute_value = attribute_match.group(3)
                if attribute_name == "s-for":
                    continue
                if (
                    "{{" in attribute_value
                    or "{=" in attribute_value
                    or attribute_name.startswith("on-")
                    or attribute_name in {"s-if", "s-else-if"}
                ):
                    expression_values.append(attribute_value)

            expression_text = " ".join(expression_values)
            for candidate in sorted(candidates):
                if candidate in declared or candidate in state_fields:
                    continue
                if re.search(rf"(?<![\w$]){re.escape(candidate)}(?![\w$])", expression_text):
                    findings.append((candidate, loop_expression))

        checks.append(ValidationCheck(
            name="loop_scope_variables_declared",
            passed=not findings,
            message=(
                "s-for 标签表达式使用的循环索引变量均已声明"
                if not findings
                else f"检测到 {len(findings)} 个未在 s-for 中声明的循环索引变量"
            ),
        ))

        for variable, loop_expression in findings:
            issues.append(ValidationIssue(
                code="unbound_loop_scope_variable",
                message=(
                    f"s-for=\"{loop_expression}\" 所在标签使用了循环变量 {variable}，"
                    "但该变量没有在 s-for 的别名列表中声明，运行时表达式不会获得当前循环索引。"
                ),
                location="template",
                suggestion=(
                    f"在 s-for 中显式声明索引别名，例如将 item in items 改为 "
                    f"item, {variable} in items，并保持 Vue v-for 的循环项和索引别名一致。"
                ),
            ))

    def _source_loop_index_aliases(self, source_file: str) -> list[str]:
        if not source_file:
            return []
        source_path = Path(source_file)
        if not source_path.is_file():
            return []

        try:
            source = source_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return []

        template = self._extract_block(source, "template")
        aliases = []
        for match in re.finditer(
            r"\bv-for\s*=\s*([\"'])(.*?)\1",
            template,
            re.IGNORECASE | re.DOTALL,
        ):
            expression = match.group(2)
            declaration = re.match(r"^\s*\(?\s*([^)]*?)\s*\)?\s+in\s+.+$", expression, re.DOTALL)
            if not declaration:
                aliases.append("")
                continue
            names = [name.strip() for name in declaration.group(1).split(",")]
            aliases.append(names[1] if len(names) > 1 else "")
        return aliases

    def _known_component_state_fields(self, script: str, ssm: dict[str, Any]) -> set[str]:
        fields = {
            match.group(2)
            for match in re.finditer(
                r"\bthis\.data\.(?:get|set)\s*\(\s*(['\"])([A-Za-z_$][\w$]*)\1",
                script,
            )
        }

        init_data_body = self._extract_function_body(script, "initData")
        fields.update(
            match.group(1)
            for match in re.finditer(
                r"(?:^|[,{]\s*)([A-Za-z_$][\w$]*)\s*:",
                init_data_body,
                re.MULTILINE,
            )
        )

        options = self._script_options(ssm)
        for collection_name in ("props", "data", "data_fields", "computed"):
            for item in options.get(collection_name, []) if isinstance(options, dict) else []:
                if isinstance(item, str):
                    fields.add(item)
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("field_name") or item.get("prop_name")
                    if isinstance(name, str) and name:
                        fields.add(name)
        return fields

    def _validate_template_reactive_dependencies(
        self,
        template: str,
        script: str,
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        findings: dict[tuple[str, str], set[str]] = {}

        def inspect_expression(binding_name: str, expression: str) -> None:
            for call_match in self.TEMPLATE_METHOD_CALL_PATTERN.finditer(expression):
                method_name = call_match.group(1)
                method_body = self._extract_function_body(script, method_name)
                if not method_body:
                    continue

                reactive_reads = {
                    match.group(2)
                    for match in self.DATA_GET_PATTERN.finditer(method_body)
                }
                hidden_reads = {
                    field
                    for field in reactive_reads
                    if not re.search(rf"\b{re.escape(field)}\b", expression)
                }
                if hidden_reads:
                    findings.setdefault((binding_name, method_name), set()).update(hidden_reads)

        for attribute_match in self.TEMPLATE_ATTRIBUTE_PATTERN.finditer(template):
            attribute_name = attribute_match.group(1).lower()
            attribute_value = attribute_match.group(3)
            expressions = {
                interpolation.group(1) or interpolation.group(2) or ""
                for interpolation in self.TEMPLATE_INTERPOLATION_PATTERN.finditer(attribute_value)
            }
            if attribute_name in self.REACTIVE_RENDER_DIRECTIVES:
                expressions.add(attribute_value)
            for expression in expressions:
                inspect_expression(attribute_name, expression)

        for text_match in re.finditer(r">([^<]+)<", template, re.DOTALL):
            for interpolation in self.TEMPLATE_INTERPOLATION_PATTERN.finditer(text_match.group(1)):
                expression = interpolation.group(1) or interpolation.group(2) or ""
                inspect_expression("text", expression)

        checks.append(ValidationCheck(
            name="template_reactive_dependencies_visible",
            passed=not findings,
            message=(
                "模板渲染表达式的方法调用没有隐藏 San 响应式字段依赖"
                if not findings
                else f"检测到 {len(findings)} 个模板渲染方法调用隐藏 San 响应式字段依赖"
            ),
        ))

        for (attribute_name, method_name), fields in sorted(findings.items()):
            field_list = ", ".join(sorted(fields))
            issues.append(ValidationIssue(
                code="hidden_template_reactive_dependency",
                message=(
                    f"模板 {attribute_name} 渲染表达式调用 {method_name}(...)，但该方法内部隐藏读取响应式字段："
                    f"{field_list}。这些字段变化时，San 可能不会重新计算该绑定。"
                ),
                location="template/script",
                suggestion=(
                    f"在模板表达式中直接引用 {field_list}，或将这些字段作为参数显式传给 "
                    f"{method_name}(...)。"
                ),
            ))

    def _validate_nested_state_mutations(
        self,
        script: str,
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        findings: dict[str, set[str]] = {}

        for method_name, method_body in self._iter_method_bodies(script):
            aliases: dict[str, set[str]] = {
                match.group(1): {match.group(3)}
                for match in self.STATE_ALIAS_PATTERN.finditer(method_body)
            }

            changed = True
            while changed:
                changed = False
                for assignment in self.LOCAL_ASSIGNMENT_PATTERN.finditer(method_body):
                    target = assignment.group(1)
                    expression = assignment.group(2)
                    if target in aliases or self._is_detached_copy_expression(expression):
                        continue
                    source_fields: set[str] = set()
                    for alias, fields in aliases.items():
                        if re.search(rf"\b{re.escape(alias)}\b", expression):
                            source_fields.update(fields)
                    if source_fields:
                        aliases[target] = source_fields
                        changed = True

            mutated_fields: set[str] = set()
            mutator_names = "|".join(self.MUTATING_ARRAY_METHODS)
            for alias, fields in aliases.items():
                alias_path = rf"\b{re.escape(alias)}(?:\s*(?:\.[A-Za-z_$][\w$]*|\[[^\]\n]+\]))*"
                alias_nested_path = rf"\b{re.escape(alias)}(?:\s*(?:\.[A-Za-z_$][\w$]*|\[[^\]\n]+\]))+"
                property_assignment = re.compile(
                    alias_nested_path + r"\s*(?:\+\+|--|[+\-*/%]?=(?!=))"
                )
                mutating_call = re.compile(
                    alias_path + rf"\s*\.\s*(?:{mutator_names})\s*\("
                )
                object_assign = re.compile(
                    rf"\bObject\.assign\s*\(\s*{alias_path}\s*,"
                )
                delete_property = re.compile(rf"\bdelete\s+{alias_path}")
                if any(pattern.search(method_body) for pattern in (
                    property_assignment,
                    mutating_call,
                    object_assign,
                    delete_property,
                )):
                    mutated_fields.update(fields)

            direct_property_assignment = re.compile(
                r"this\.data\.get\s*\(\s*(['\"])([A-Za-z_$][\w$]*)\1\s*\)"
                r"(?:\s*(?:\.[A-Za-z_$][\w$]*|\[[^\]\n]+\]))+\s*"
                r"(?:\+\+|--|[+\-*/%]?=(?!=))"
            )
            direct_mutating_call = re.compile(
                r"this\.data\.get\s*\(\s*(['\"])([A-Za-z_$][\w$]*)\1\s*\)"
                r"(?:\s*(?:\.[A-Za-z_$][\w$]*|\[[^\]\n]+\]))*"
                rf"\s*\.\s*(?:{mutator_names})\s*\("
            )
            for pattern in (direct_property_assignment, direct_mutating_call):
                mutated_fields.update(match.group(2) for match in pattern.finditer(method_body))

            if mutated_fields:
                findings.setdefault(method_name, set()).update(mutated_fields)

        checks.append(ValidationCheck(
            name="reactive_state_uses_data_updates",
            passed=not findings,
            message=(
                "响应式对象和数组通过 San data API 更新"
                if not findings
                else f"检测到 {len(findings)} 个方法直接修改响应式对象或数组"
            ),
        ))

        for method_name, fields in sorted(findings.items()):
            field_list = ", ".join(sorted(fields))
            issues.append(ValidationIssue(
                code="nested_state_mutation",
                message=(
                    f"方法 {method_name}(...) 直接修改了来自 San data 的对象或数组引用："
                    f"{field_list}。原地修改可能绕过响应式更新。"
                ),
                location="script",
                suggestion=(
                    "使用 map、filter、concat、Object.assign({}, ...) 或对象展开创建新对象/数组，"
                    f"然后通过 this.data.set(...) 写回 {field_list}；不要直接修改其属性或调用 push/splice。"
                ),
            ))

    def _validate_dom_child_order(
        self,
        code: str,
        stage_input: ValidateStageInput,
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        source_name = stage_input.vue_file_path or stage_input.source_file
        source_path = Path(source_name) if source_name else None
        if not source_path or not source_path.is_file():
            return

        try:
            source_code = source_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return

        source_template = self._extract_block(source_code, "template")
        generated_template = self._extract_block(code, "template")
        source_tree = self._parse_template_order(source_template)
        generated_tree = self._parse_template_order(generated_template)
        mismatches = []
        if source_tree and generated_tree:
            self._collect_dom_order_mismatches(source_tree, generated_tree, "/", mismatches)

        checks.append(ValidationCheck(
            name="dom_child_order_consistency",
            passed=not mismatches,
            message=(
                "Vue 与 San 模板直接子节点顺序一致"
                if not mismatches
                else f"检测到 {len(mismatches)} 处 Vue/San 直接子节点顺序变化"
            ),
        ))
        if mismatches:
            examples = "; ".join(
                f"{item['path']}: Vue {item['source']} / San {item['generated']}"
                for item in mismatches[:5]
            )
            issues.append(ValidationIssue(
                code="dom_child_order_mismatch",
                message=f"San 模板改变了 Vue 节点的直接子节点顺序：{examples}。",
                location="template",
                suggestion=(
                    "保持 Vue 原始 DOM 子节点顺序，尤其是 input/checkbox 与相邻文字、百分号、"
                    "label 文本的先后关系；不要依赖 CSS 排序替代 DOM 顺序。"
                ),
            ))

    def _parse_template_order(self, template: str):
        if not template.strip():
            return None

        class OrderNode:
            def __init__(self, tag):
                self.tag = tag
                self.tokens = []
                self.children = []

        class OrderParser(HTMLParser):
            VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

            def __init__(self):
                super().__init__(convert_charrefs=False)
                self.root = None
                self.stack = []

            def handle_starttag(self, tag, attrs):
                node = OrderNode(tag.lower())
                if self.stack:
                    self.stack[-1].tokens.append(("element", node.tag))
                    self.stack[-1].children.append(node)
                else:
                    self.root = node
                if tag.lower() not in self.VOID_TAGS:
                    self.stack.append(node)

            def handle_startendtag(self, tag, attrs):
                self.handle_starttag(tag, attrs)
                if self.stack and self.stack[-1].tag == tag.lower():
                    self.stack.pop()

            def handle_endtag(self, tag):
                for index in range(len(self.stack) - 1, -1, -1):
                    if self.stack[index].tag == tag.lower():
                        del self.stack[index:]
                        break

            def handle_data(self, data):
                normalized = self._normalize_text(data)
                if normalized and self.stack:
                    self.stack[-1].tokens.append(("text", normalized))

            def handle_entityref(self, name):
                self.handle_data(f"&{name};")

            def handle_charref(self, name):
                self.handle_data(f"&#{name};")

            @staticmethod
            def _normalize_text(text):
                text = re.sub(r"\s+", " ", text).strip()
                text = re.sub(r"\{\{\s*([^{}]*?)\s*\}\}", r"{{\1}}", text)
                text = re.sub(r"\{=\s*([^{}]*?)\s*=\}", r"{=\1=}", text)
                return text

        parser = OrderParser()
        try:
            parser.feed(template)
            parser.close()
        except Exception:
            return None
        return parser.root

    def _collect_dom_order_mismatches(self, source_node, generated_node, path, mismatches):
        if source_node.tag != generated_node.tag:
            mismatches.append({
                "path": path,
                "source": source_node.tag,
                "generated": generated_node.tag,
            })
            return
        if source_node.tokens != generated_node.tokens:
            source_signature = [token[1] for token in source_node.tokens]
            generated_signature = [token[1] for token in generated_node.tokens]
            if sorted(source_signature, key=str) == sorted(generated_signature, key=str):
                mismatches.append({
                    "path": path + source_node.tag,
                    "source": source_signature,
                    "generated": generated_signature,
                })

        child_count = min(len(source_node.children), len(generated_node.children))
        for index in range(child_count):
            child_path = f"{path}{source_node.tag}[{index}]/"
            self._collect_dom_order_mismatches(
                source_node.children[index],
                generated_node.children[index],
                child_path,
                mismatches,
            )

    def _iter_method_bodies(self, script: str):
        for match in self.METHOD_DEFINITION_PATTERN.finditer(script):
            method_name = match.group(1)
            if method_name in self.JAVASCRIPT_CONTROL_KEYWORDS:
                continue
            method_body = self._extract_braced_body(script, match.end() - 1)
            if method_body:
                yield method_name, method_body

    def _is_detached_copy_expression(self, expression: str) -> bool:
        return bool(re.search(
            r"\.(?:map|filter|slice|concat)\s*\(|\bArray\.from\s*\(|"
            r"\bObject\.assign\s*\(\s*\{\s*\}|\[[^\]\n]*\.\.\.|"
            r"\{[^}\n]*\.\.\.",
            expression,
        ))

    def _validate_style_rules(
        self,
        style: str,
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
        strict: bool,
    ) -> None:
        scoped_style = bool(re.search(r"<style\b[^>]*\bscoped\b", style))
        checks.append(ValidationCheck(
            name="style_without_scoped",
            passed=not scoped_style,
            message="San style 不使用 scoped",
            severity="warning",
        ))
        if scoped_style:
            issues.append(ValidationIssue(
                code="san_style_scoped",
                message="San 单文件组件不应保留 <style scoped>。",
                location="style",
                suggestion="将 <style scoped> 改为 <style>，同时保留样式内容。",
            ))

    def _validate_san_compile(
        self,
        code: str,
        stage_input: ValidateStageInput,
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> dict[str, Any] | None:
        if not stage_input.compile_check:
            checks.append(ValidationCheck(
                name="san_compile_check",
                passed=True,
                message="已按配置跳过 San 编译校验",
                severity="warning",
            ))
            return None

        result = check_san_compile(
            san_source=code,
            san_file_path=stage_input.generated_file_path or None,
        )
        checks.append(ValidationCheck(
            name="san_compile_check",
            passed=result.passed,
            message="San script 可执行校验通过" if result.passed else "San script 可执行校验失败",
            severity="warning" if result.skipped else "error",
        ))

        for diagnostic in result.diagnostics:
            severity = diagnostic.get("severity", "error")
            if result.skipped:
                severity = "warning"
            issues.append(ValidationIssue(
                code=diagnostic.get("code", "san_compile_diagnostic"),
                message=diagnostic.get("message", "San 编译校验发现问题。"),
                severity=severity,
                location="script",
                suggestion="根据编译错误修正 San script 语法或组件导出结构。",
            ))
        return result.to_dict()

    def _validate_ssm_consistency(
        self,
        code: str,
        blocks: dict[str, str],
        ssm: dict[str, Any],
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        component_name = self._expected_component_name(ssm)
        if component_name:
            passed = bool(re.search(rf"name\s*:\s*['\"]{re.escape(component_name)}['\"]", blocks.get("script", "")))
            checks.append(ValidationCheck(
                name="component_name_consistency",
                passed=passed,
                message=f"组件名与 SSM 一致：{component_name}",
                severity="warning",
            ))
            if not passed:
                issues.append(ValidationIssue(
                    code="component_name_mismatch",
                    message=f"生成的 San 组件未声明与 SSM 一致的 name：{component_name}。",
                    severity="warning",
                    location="script",
                    suggestion="在 san.defineComponent 对象中补充或修正 name。",
                ))

        expected_props = self._expected_props(ssm)
        if expected_props:
            missing_props = [prop for prop in expected_props if not re.search(rf"\b{re.escape(prop)}\s*:\s*DataTypes\.", blocks.get("script", ""))]
            passed = not missing_props
            checks.append(ValidationCheck(
                name="props_to_datatypes_consistency",
                passed=passed,
                message="SSM props 已迁移为 dataTypes",
            ))
            if missing_props:
                issues.append(ValidationIssue(
                    code="missing_datatypes_for_props",
                    message=f"以下 SSM props 未在 dataTypes 中声明：{', '.join(missing_props)}。",
                    location="script",
                    suggestion="为每个 props 补充对应 DataTypes 类型声明。",
                ))

        expected_data = self._expected_data_fields(ssm)
        if expected_data:
            missing_data = [field for field in expected_data if not re.search(rf"['\"]?{re.escape(field)}['\"]?\s*:", blocks.get("script", ""))]
            passed = not missing_data
            checks.append(ValidationCheck(
                name="data_fields_consistency",
                passed=passed,
                message="SSM data 字段在 San 脚本中有对应初始化或声明",
                severity="warning",
            ))
            if missing_data:
                issues.append(ValidationIssue(
                    code="missing_data_fields",
                    message=f"以下 SSM data 字段在 San 脚本中未找到明显对应：{', '.join(missing_data)}。",
                    severity="warning",
                    location="script",
                    suggestion="检查 initData、computed 或 this.data.set 是否保留源组件状态。",
                ))

        expected_handlers = self._expected_event_handlers(ssm)
        if expected_handlers:
            missing_handlers = [handler for handler in expected_handlers if not re.search(rf"\b{re.escape(handler)}\s*\(", blocks.get("script", ""))]
            passed = not missing_handlers
            checks.append(ValidationCheck(
                name="event_handlers_consistency",
                passed=passed,
                message="SSM 事件处理函数在 San 脚本中存在",
            ))
            if missing_handlers:
                issues.append(ValidationIssue(
                    code="missing_event_handlers",
                    message=f"以下 SSM 事件处理函数未在 San 脚本中找到：{', '.join(missing_handlers)}。",
                    location="script",
                    suggestion="补齐事件处理方法，并在模板中通过 on-event 绑定。",
                ))

    def _validate_prop_defaults_landing(
        self,
        script: str,
        ssm: dict[str, Any],
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        props = self._script_options(ssm).get("props", [])
        defaulted_props = []
        for prop in props if isinstance(props, list) else []:
            if not isinstance(prop, dict) or "default" not in prop:
                continue
            default_value = prop.get("default")
            if default_value is None or str(default_value).strip() in {"", "undefined"}:
                continue
            name = prop.get("name") or prop.get("prop_name")
            if name:
                defaulted_props.append(str(name))
        if not defaulted_props:
            return
        init_data_body = self._extract_function_body(script, "initData")
        missing = [
            name for name in defaulted_props
            if not re.search(rf"(?:^|[,{{])\s*['\"]?{re.escape(name)}['\"]?\s*:", init_data_body)
        ]
        checks.append(ValidationCheck(
            name="prop_defaults_in_init_data",
            passed=not missing,
            message="Vue props 默认值已迁移到 San initData",
        ))
        if missing:
            issues.append(ValidationIssue(
                code="missing_prop_defaults",
                message=f"以下带默认值的 Vue props 未在 San initData 中落地：{', '.join(missing)}。",
                location="script",
                suggestion="将 SSM props.default 的等价值作为同名字段加入 initData 返回对象。",
            ))

    def _validate_data_initial_values(
        self,
        san_compile_result: dict[str, Any] | None,
        ssm: dict[str, Any],
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        data_fields = self._script_options(ssm).get("data", [])
        expected = {
            str(field.get("name") or field.get("field_name")): field.get("default_value")
            for field in data_fields if isinstance(data_fields, list)
            if isinstance(field, dict)
            and (field.get("name") or field.get("field_name"))
            and field.get("default_value_static") is True
        }
        if not expected:
            return

        actual = (san_compile_result or {}).get("initial_data")
        if not isinstance(actual, dict):
            checks.append(ValidationCheck(
                name="data_initial_values_equivalent",
                passed=False,
                message="无法取得 San initData 的结构化结果",
                severity="warning",
            ))
            issues.append(ValidationIssue(
                code="data_initial_values_unavailable",
                message="SSM 包含可静态验证的 data 初始值，但未取得 San initData 结果。",
                severity="warning",
                location="script",
                suggestion="确认 Node 编译校验可运行，且 initData 返回可序列化对象。",
            ))
            return

        mismatches = []
        for name, expected_value in expected.items():
            if name not in actual or not self._values_equivalent(expected_value, actual[name]):
                mismatches.append({
                    "field": name,
                    "expected": expected_value,
                    "actual": actual.get(name, "<missing>"),
                })

        checks.append(ValidationCheck(
            name="data_initial_values_equivalent",
            passed=not mismatches,
            message="Vue data 初始值与 San initData 等价",
        ))
        if mismatches:
            issues.append(ValidationIssue(
                code="data_initial_value_mismatch",
                message=(
                    "以下 data 初始值与 SSM 不等价："
                    + json.dumps(mismatches, ensure_ascii=False, separators=(",", ":"))
                ),
                location="script",
                suggestion="按 SSM data_initial_values_to_preserve 精确保留完整初始值。",
            ))

    def _validate_prop_dependent_data_initialization(
        self,
        script: str,
        ssm: dict[str, Any],
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        options = self._script_options(ssm)
        prop_names = set(self._expected_props(ssm))
        dependent_fields: dict[str, set[str]] = {}
        for item in options.get("data", []) if isinstance(options.get("data", []), list) else []:
            if not isinstance(item, dict):
                continue
            field_name = item.get("name") or item.get("field_name")
            expression = str(item.get("default_value_expression") or "")
            dependencies = {
                name for name in prop_names
                if re.search(rf"\bthis\.{re.escape(name)}\b", expression)
            }
            if field_name and dependencies:
                dependent_fields[str(field_name)] = dependencies

        if not dependent_fields:
            return

        inited_body = self._extract_function_body(script, "inited")
        missing = []
        for field_name, dependencies in sorted(dependent_fields.items()):
            writes_field = bool(re.search(
                rf"\bthis\.data\.set\s*\(\s*['\"]{re.escape(field_name)}['\"]",
                inited_body,
            ))
            missing_reads = [
                dependency for dependency in sorted(dependencies)
                if not re.search(
                    rf"\bthis\.data\.get\s*\(\s*['\"]{re.escape(dependency)}['\"]",
                    inited_body,
                )
            ]
            if not writes_field or missing_reads:
                missing.append(
                    f"{field_name} <- {', '.join(sorted(dependencies))}"
                )

        checks.append(ValidationCheck(
            name="prop_dependent_data_initialized_in_inited",
            passed=not missing,
            message="依赖 props 的 data 已在 San inited 中初始化",
        ))
        if missing:
            issues.append(ValidationIssue(
                code="missing_prop_dependent_initialization",
                message=f"以下 prop 派生 data 未在 inited() 中完整初始化：{'; '.join(missing)}。",
                location="script",
                suggestion=(
                    "initData() 先返回稳定占位值，再在 inited() 中使用 this.data.get('propName') "
                    "读取 prop、创建独立副本，并通过 this.data.set('field', value) 写入派生 data。"
                ),
            ))

    def _values_equivalent(self, expected: Any, actual: Any) -> bool:
        if isinstance(expected, bool) or isinstance(actual, bool):
            return type(expected) is type(actual) and expected == actual
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            return expected == actual
        if isinstance(expected, dict) and isinstance(actual, dict):
            return expected.keys() == actual.keys() and all(
                self._values_equivalent(expected[key], actual[key])
                for key in expected
            )
        if isinstance(expected, list) and isinstance(actual, list):
            return len(expected) == len(actual) and all(
                self._values_equivalent(expected_item, actual_item)
                for expected_item, actual_item in zip(expected, actual)
            )
        return type(expected) is type(actual) and expected == actual

    def _validate_event_arguments_landing(
        self,
        template: str,
        ssm: dict[str, Any],
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        expected = self._expected_event_expressions(ssm)
        if not expected:
            return
        missing = []
        for event_name, expression in expected:
            pattern = rf"on-{re.escape(event_name)}\s*=\s*['\"]\s*{re.escape(expression)}\s*['\"]"
            if not re.search(pattern, template):
                missing.append(f"{event_name}:{expression}")
        bypassed = bool(re.search(r"\bdata-args\s*=|\.getAttribute\s*\(", template))
        checks.append(ValidationCheck(
            name="event_arguments_consistency",
            passed=not missing and not bypassed,
            message="SSM 事件调用参数已在 San template 中完整保留",
        ))
        if missing or bypassed:
            detail = f"缺失：{', '.join(missing)}。" if missing else ""
            if bypassed:
                detail += "检测到 data-args/getAttribute 绕行。"
            issues.append(ValidationIssue(
                code="event_arguments_not_landed",
                message="San 事件绑定未完整保留源事件参数。" + detail,
                location="template",
                suggestion="直接使用 on-event=\"handler(arg)\" 保留 SSM handler_expression。",
            ))

    def _validate_custom_event_migration(
        self,
        script: str,
        ssm: dict[str, Any],
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        source_methods = self._script_options(ssm).get("methods", [])
        source_uses_emit = any(
            isinstance(method, dict) and "$emit" in str(method.get("body", ""))
            for method in source_methods if isinstance(source_methods, list)
        )
        if not source_uses_emit:
            return
        has_fire = bool(re.search(r"\bthis\.fire\s*\(", script))
        has_dispatch = bool(re.search(r"\bthis\.dispatch\s*\(", script))
        checks.append(ValidationCheck(
            name="custom_event_fire_consistency",
            passed=has_fire and not has_dispatch,
            message="Vue $emit 已迁移为 San this.fire",
        ))
        if not has_fire or has_dispatch:
            issues.append(ValidationIssue(
                code="custom_event_not_fire",
                message="源组件使用了 Vue $emit，但 San 未正确使用 this.fire，或错误使用了 this.dispatch。",
                location="script",
                suggestion="将自定义事件迁移为 this.fire(eventName, payload)，不要使用 this.dispatch。",
            ))

    def _validate_datatypes_accuracy(
        self,
        script: str,
        ssm: dict[str, Any],
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        expected = self._expected_prop_types(ssm)
        if not expected:
            return

        mismatches = []
        for prop_name, vue_type in expected.items():
            san_type = self._vue_type_to_datatype(vue_type)
            if not san_type:
                continue
            pattern = rf"\b{re.escape(prop_name)}\s*:\s*DataTypes\.{re.escape(san_type)}\b"
            if not re.search(pattern, script):
                mismatches.append(f"{prop_name}: {vue_type} -> DataTypes.{san_type}")

        passed = not mismatches
        checks.append(ValidationCheck(
            name="datatypes_accuracy",
            passed=passed,
            message="San dataTypes 类型与 SSM props 类型一致",
        ))
        if mismatches:
            issues.append(ValidationIssue(
                code="datatypes_type_mismatch",
                message=f"以下 props 的 dataTypes 类型不匹配：{', '.join(mismatches)}。",
                location="script",
                suggestion="根据 Vue props type 修正 San dataTypes 类型声明。",
            ))

    def _validate_lifecycle_mapping(
        self,
        script: str,
        ssm: dict[str, Any],
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        hooks = self._expected_lifecycle_items(ssm)
        if not hooks:
            return

        expected_mapping = {
            "beforeCreate": "compiled",
            "created": "inited",
            "beforeMount": "created",
            "mounted": "attached",
            "beforeDestroy": "disposed",
            "destroyed": "disposed",
            "activated": "attached",
            "deactivated": "disposed",
        }
        missing = []
        behavior_missing = []
        options = self._script_options(ssm)
        known_fields = set(self._expected_props(ssm))
        known_fields.update(self._expected_data_fields(ssm))
        known_fields.update(self._expected_computed_names(ssm))
        known_methods = set(self._expected_method_names(ssm))

        for hook in hooks:
            source_hook = hook["source_hook"]
            target_hook = hook.get("target_hook") or expected_mapping.get(source_hook)
            if target_hook and not re.search(rf"\b{target_hook}\s*\(", script):
                missing.append(f"{source_hook} -> {target_hook}")
                continue
            if not target_hook:
                continue

            source_body = hook.get("body", "")
            target_body = self._extract_function_body(script, target_hook)
            target_body_for_matching = target_body
            for alias in re.findall(
                r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*this\s*;",
                target_body,
            ):
                target_body_for_matching = re.sub(
                    rf"\b{re.escape(alias)}\.",
                    "this.",
                    target_body_for_matching,
                )
            requirements = []

            for field_name in re.findall(
                r"\bthis\.setValue\s*\(\s*['\"]([A-Za-z_$][\w$]*)['\"]",
                source_body,
            ):
                landed = bool(re.search(
                    rf"(?:this\.setValue|this\.data\.set)\s*\(\s*['\"]{re.escape(field_name)}['\"]",
                    target_body_for_matching,
                ))
                if not landed:
                    requirements.append(f"写入字段 {field_name}")

            for field_name in known_fields:
                if not re.search(rf"\bthis\.{re.escape(field_name)}\b", source_body):
                    continue
                reads_or_writes = bool(re.search(
                    rf"this\.data\.(?:get|set)\s*\(\s*['\"]{re.escape(field_name)}['\"]",
                    target_body_for_matching,
                ))
                if not reads_or_writes:
                    requirements.append(f"访问字段 {field_name}")

            for method_name in known_methods:
                if not re.search(rf"\bthis\.{re.escape(method_name)}\s*\(", source_body):
                    continue
                if method_name == "setValue":
                    continue
                if not re.search(
                    rf"\bthis\.{re.escape(method_name)}\s*\(",
                    target_body_for_matching,
                ):
                    requirements.append(f"调用方法 {method_name}()")

            for side_effect in ("setTimeout", "setInterval", "clearTimeout", "clearInterval"):
                if re.search(rf"\b{side_effect}\s*\(", source_body) and not re.search(
                    rf"\b{side_effect}\s*\(", target_body_for_matching
                ):
                    requirements.append(f"保留 {side_effect}()")

            if requirements:
                behavior_missing.append(
                    f"{source_hook} -> {target_hook}: {', '.join(sorted(set(requirements)))}"
                )

        passed = not missing
        checks.append(ValidationCheck(
            name="lifecycle_mapping_consistency",
            passed=passed,
            message="Vue 生命周期已映射到 San 生命周期",
        ))
        if missing:
            issues.append(ValidationIssue(
                code="missing_lifecycle_mapping",
                message=f"以下生命周期映射未在 San 中找到：{', '.join(missing)}。",
                location="script",
                suggestion="将 Vue 生命周期迁移到对应 San 生命周期，或确认逻辑已合并到其他生命周期中。",
            ))

        checks.append(ValidationCheck(
            name="lifecycle_behavior_consistency",
            passed=not behavior_missing,
            message="Vue 生命周期中的初始化、方法调用和副作用已在 San 钩子中保留",
        ))
        if behavior_missing:
            issues.append(ValidationIssue(
                code="lifecycle_behavior_not_landed",
                message=f"以下生命周期行为未完整迁移：{'; '.join(behavior_missing)}。",
                location="script",
                suggestion=(
                    "在对应 San 生命周期中保留源钩子的状态初始化、方法调用和定时器创建/清理；"
                    "不要只保留空的 inited/attached/disposed 方法。"
                ),
            ))

    def _validate_event_binding_completeness(
        self,
        template: str,
        ssm: dict[str, Any],
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        handlers = self._expected_event_handlers(ssm)
        if not handlers:
            return

        bound_handlers = self._bound_event_handlers(template)
        missing = [handler for handler in handlers if handler not in bound_handlers]
        passed = not missing
        checks.append(ValidationCheck(
            name="event_binding_completeness",
            passed=passed,
            message="SSM 事件 handler 已在 San template 中绑定",
        ))
        if missing:
            issues.append(ValidationIssue(
                code="missing_event_bindings",
                message=f"以下事件 handler 在 San template 中没有找到对应 on-* 绑定：{', '.join(missing)}。",
                location="template",
                suggestion="在模板中补充对应 on-click/on-input 等 San 事件绑定。",
            ))

    def _bound_event_handlers(self, template: str) -> set[str]:
        """Return handler names from on-* attributes, including calls with quoted args."""
        handlers: set[str] = set()
        attribute_pattern = re.compile(
            r"\bon-[\w:-]+\s*=\s*([\"'])(.*?)\1",
            re.DOTALL,
        )
        handler_pattern = re.compile(r"^\s*([A-Za-z_$][\w$]*)\s*(?:\(|$)")
        for match in attribute_pattern.finditer(template):
            handler_match = handler_pattern.match(match.group(2))
            if handler_match:
                handlers.add(handler_match.group(1))
        return handlers

    def _validate_computed_watch_migration(
        self,
        script: str,
        ssm: dict[str, Any],
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        computed_names = self._expected_computed_names(ssm)
        watch_expressions = self._expected_watch_expressions(ssm)

        if computed_names:
            missing_computed = [name for name in computed_names if not re.search(rf"\b{name}\s*\(", script)]
            checks.append(ValidationCheck(
                name="computed_migration_consistency",
                passed=not missing_computed,
                message="SSM computed 字段已在 San 中保留",
                severity="warning",
            ))
            if missing_computed:
                issues.append(ValidationIssue(
                    code="missing_computed_migration",
                    message=f"以下 computed 未在 San script 中找到明显对应：{', '.join(missing_computed)}。",
                    severity="warning",
                    location="script",
                    suggestion="将 Vue computed 迁移为 San computed 方法，或确认其逻辑已等价内联。",
                ))

        if watch_expressions:
            missing_watch = [expr for expr in watch_expressions if not re.search(rf"this\.watch\s*\(\s*['\"]{re.escape(expr)}['\"]", script)]
            checks.append(ValidationCheck(
                name="watch_migration_consistency",
                passed=not missing_watch,
                message="SSM watch 字段已在 San 中保留",
                severity="warning",
            ))
            if missing_watch:
                issues.append(ValidationIssue(
                    code="missing_watch_migration",
                    message=f"以下 watch 未在 San script 中找到 this.watch 对应：{', '.join(missing_watch)}。",
                    location="script",
                    suggestion="在 San inited/attached 中使用 this.watch 迁移 Vue watch，或确认逻辑已等价处理。",
                ))

    def _validate_migration_hints_landing(
        self,
        blocks: dict[str, str],
        ssm: dict[str, Any],
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        hints = ssm.get("migration_hints", {}) if isinstance(ssm, dict) else {}
        if not isinstance(hints, dict) or not hints:
            return

        script = blocks.get("script", "")
        template = blocks.get("template", "")
        missing = []

        patterns = hints.get("detected_patterns", [])
        pattern_text = " ".join(
            str(pattern.get(key, ""))
            for pattern in patterns if isinstance(pattern, dict)
            for key in ("pattern_id", "pattern_name", "san_strategy")
        )

        if ("event" in pattern_text.lower() or "事件" in pattern_text) and self._expected_event_handlers(ssm):
            if not re.search(r"\bon-[\w:-]+\s*=", template):
                missing.append("事件绑定策略未落地：San template 中没有 on-* 绑定")

        if ("emit" in pattern_text.lower() or "$emit" in pattern_text or "自定义事件" in pattern_text) and self._expected_emits(ssm):
            if "this.fire" not in script:
                missing.append("自定义事件策略未落地：San script 中没有 this.fire")

        data_plan = hints.get("data_access_conversion_plan", {})
        if isinstance(data_plan, dict) and data_plan:
            for field_name, plan in data_plan.items():
                if not isinstance(plan, dict):
                    continue
                read_plan = plan.get("read_plan")
                write_plan = plan.get("write_plan")
                if read_plan and re.search(rf"\b{re.escape(field_name)}\b", script) and f"this.data.get('{field_name}')" not in script:
                    missing.append(f"data 读取策略未落地：{field_name} 应使用 this.data.get('{field_name}')")
                if write_plan and re.search(rf"\b{re.escape(field_name)}\b", script) and f"this.data.set('{field_name}'" not in script:
                    missing.append(f"data 写入策略未落地：{field_name} 应使用 this.data.set('{field_name}', ...)")

        checks.append(ValidationCheck(
            name="migration_hints_landing",
            passed=not missing,
            message="SSM migration_hints 已在 San 中落地",
            severity="warning",
        ))
        if missing:
            issues.append(ValidationIssue(
                code="migration_hints_not_landed",
                message="；".join(missing),
                severity="warning",
                location="script/template",
                suggestion="根据 SSM migration_hints 补齐 San 迁移策略。",
            ))

    def _extract_blocks(self, code: str) -> dict[str, str]:
        return {
            "template": self._extract_block(code, "template"),
            "script": self._extract_block(code, "script"),
            "style": self._extract_block_with_tag(code, "style"),
        }

    def _extract_block(self, code: str, tag: str) -> str:
        match = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", code, re.DOTALL | re.IGNORECASE)
        return match.group(1) if match else ""

    def _extract_block_with_tag(self, code: str, tag: str) -> str:
        match = re.search(rf"<{tag}\b[^>]*>.*?</{tag}>", code, re.DOTALL | re.IGNORECASE)
        return match.group(0) if match else ""

    def _extract_function_body(self, script: str, function_name: str) -> str:
        match = re.search(rf"\b{re.escape(function_name)}\s*\([^)]*\)\s*{{", script)
        if not match:
            return ""
        return self._extract_braced_body(script, match.end() - 1)

    def _extract_braced_body(self, script: str, start: int) -> str:
        depth = 0
        quote = ""
        escaped = False
        for index in range(start, len(script)):
            char = script[index]
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
                continue
            if char in {"'", '"', "`"}:
                quote = char
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return script[start + 1:index]
        return ""

    def _expected_component_name(self, ssm: dict[str, Any]) -> str:
        metadata = ssm.get("metadata", {}) if isinstance(ssm, dict) else {}
        script = ssm.get("script", {}) if isinstance(ssm, dict) else {}
        options = script.get("options", {}) if isinstance(script, dict) else {}
        return metadata.get("component_name") or options.get("name") or ""

    def _expected_props(self, ssm: dict[str, Any]) -> list[str]:
        options = self._script_options(ssm)
        props = options.get("props", [])
        result = []
        for prop in props if isinstance(props, list) else []:
            if isinstance(prop, dict):
                name = prop.get("name") or prop.get("prop_name")
                if name:
                    result.append(name)
            elif isinstance(prop, str):
                result.append(prop)
        return result

    def _expected_data_fields(self, ssm: dict[str, Any]) -> list[str]:
        options = self._script_options(ssm)
        data_fields = options.get("data", []) or options.get("data_fields", [])
        result = []
        for field in data_fields if isinstance(data_fields, list) else []:
            if isinstance(field, dict):
                name = field.get("name") or field.get("field_name")
                if name:
                    result.append(name)
            elif isinstance(field, str):
                result.append(field)
        return result

    def _expected_event_handlers(self, ssm: dict[str, Any]) -> list[str]:
        handlers: set[str] = set()
        event_model = ssm.get("event_model", {}) if isinstance(ssm, dict) else {}
        for group_name in ("dom_events", "custom_events"):
            for event in event_model.get(group_name, []) if isinstance(event_model, dict) else []:
                if not isinstance(event, dict):
                    continue
                for key in ("handler", "handler_name", "method", "method_name"):
                    value = event.get(key)
                    if isinstance(value, str) and value:
                        handlers.add(value)

        template = ssm.get("template", {}) if isinstance(ssm, dict) else {}
        for binding in template.get("event_bindings", []) if isinstance(template, dict) else []:
            if not isinstance(binding, dict):
                continue
            value = binding.get("handler") or binding.get("handler_name") or binding.get("method")
            if isinstance(value, str) and value:
                handlers.add(value)
        return sorted(handlers)

    def _expected_event_expressions(self, ssm: dict[str, Any]) -> list[tuple[str, str]]:
        result: set[tuple[str, str]] = set()
        template = ssm.get("template", {}) if isinstance(ssm, dict) else {}

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for binding in node.get("event_bindings", []) if isinstance(node.get("event_bindings"), list) else []:
                    if not isinstance(binding, dict) or not binding.get("arguments"):
                        continue
                    event_name = binding.get("event_name") or binding.get("event")
                    expression = binding.get("handler_expression") or binding.get("expression")
                    if isinstance(event_name, str) and isinstance(expression, str):
                        result.add((event_name, expression))
                for child in node.get("children", []) if isinstance(node.get("children"), list) else []:
                    walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)

        walk(template.get("dom_tree", template) if isinstance(template, dict) else template)
        return sorted(result)

    def _expected_prop_types(self, ssm: dict[str, Any]) -> dict[str, str]:
        options = self._script_options(ssm)
        props = options.get("props", [])
        result = {}
        for prop in props if isinstance(props, list) else []:
            if isinstance(prop, dict):
                name = prop.get("name") or prop.get("prop_name")
                prop_type = prop.get("type") or prop.get("value_type_inferred")
                if name and prop_type:
                    result[name] = str(prop_type)
        return result

    def _expected_lifecycle_hooks(self, ssm: dict[str, Any]) -> list[str]:
        return [item["source_hook"] for item in self._expected_lifecycle_items(ssm)]

    def _expected_lifecycle_items(self, ssm: dict[str, Any]) -> list[dict[str, str]]:
        options = self._script_options(ssm)
        hooks = options.get("lifecycle_hooks", [])
        result = []
        for hook in hooks if isinstance(hooks, list) else []:
            if isinstance(hook, dict):
                source_hook = hook.get("vue_hook") or hook.get("name") or hook.get("hook")
                if source_hook:
                    result.append({
                        "source_hook": str(source_hook),
                        "target_hook": str(hook.get("san_hook") or ""),
                        "body": str(hook.get("body_full") or hook.get("body") or ""),
                    })
            elif isinstance(hook, str):
                result.append({
                    "source_hook": hook,
                    "target_hook": "",
                    "body": "",
                })
        return result

    def _expected_method_names(self, ssm: dict[str, Any]) -> list[str]:
        methods = self._script_options(ssm).get("methods", [])
        result = []
        for method in methods if isinstance(methods, list) else []:
            if isinstance(method, dict):
                name = method.get("name") or method.get("method_name")
                if name:
                    result.append(str(name))
            elif isinstance(method, str):
                result.append(method)
        return result

    def _expected_computed_names(self, ssm: dict[str, Any]) -> list[str]:
        options = self._script_options(ssm)
        computed = options.get("computed", [])
        result = []
        for item in computed if isinstance(computed, list) else []:
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    result.append(name)
            elif isinstance(item, str):
                result.append(item)
        return result

    def _expected_watch_expressions(self, ssm: dict[str, Any]) -> list[str]:
        options = self._script_options(ssm)
        watch = options.get("watch", [])
        result = []
        for item in watch if isinstance(watch, list) else []:
            if isinstance(item, dict):
                expr = item.get("expression") or item.get("name")
                if expr:
                    result.append(expr)
            elif isinstance(item, str):
                result.append(item)
        return result

    def _expected_emits(self, ssm: dict[str, Any]) -> list[str]:
        options = self._script_options(ssm)
        emits = options.get("emits", [])
        result = []
        for item in emits if isinstance(emits, list) else []:
            if isinstance(item, dict):
                name = item.get("event") or item.get("event_name") or item.get("name")
                if name:
                    result.append(name)
            elif isinstance(item, str):
                result.append(item)
        return result

    def _vue_type_to_datatype(self, vue_type: str) -> str:
        normalized = str(vue_type).strip().lower()
        mapping = {
            "string": "string",
            "number": "number",
            "boolean": "bool",
            "bool": "bool",
            "array": "array",
            "object": "object",
            "function": "func",
        }
        return mapping.get(normalized, "")

    def _script_options(self, ssm: dict[str, Any]) -> dict[str, Any]:
        script = ssm.get("script", {}) if isinstance(ssm, dict) else {}
        options = script.get("options", {}) if isinstance(script, dict) else {}
        return options if isinstance(options, dict) else {}

    def _build_summary(
        self,
        validation_passed: bool,
        errors: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
        checks: list[ValidationCheck],
    ) -> str:
        passed_checks = sum(1 for check in checks if check.passed)
        total_checks = len(checks)
        status = "通过" if validation_passed else "未通过"
        return f"San 静态校验{status}：{passed_checks}/{total_checks} 项检查通过，{len(errors)} 个错误，{len(warnings)} 个警告。"


def validate_san(stage_input: ValidateStageInput) -> ValidateStageResult:
    return ValidateStage().run(stage_input)
