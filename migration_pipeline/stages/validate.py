import re
from dataclasses import asdict, dataclass, field
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
    VUE_SCRIPT_PATTERNS = (
        (r"export\s+default", "vue_export_default", "San 脚本应使用 module.exports = san.defineComponent(...)。"),
        (r"\bprops\s*:", "vue_props_option", "San 中 props 应迁移为 dataTypes。"),
        (r"\bmethods\s*:\s*\{", "vue_methods_wrapper", "San 方法应直接定义在组件对象顶层。"),
        (r"\bthis\.\$emit\s*\(", "vue_emit", "Vue 的 this.$emit 应迁移为 San 的 this.fire。"),
        (r"\bthis\.(?!data\b|fire\b|watch\b|ref\b|nextTick\b)([A-Za-z_$][\w$]*)\b(?!\s*\()", "vue_this_state", "San 状态读写应使用 this.data.get()/this.data.set()。"),
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
        self._validate_script_rules(blocks.get("script", ""), issues, checks)
        self._validate_style_rules(blocks.get("style", ""), issues, checks, strict=stage_input.strict)
        san_compile_result = self._validate_san_compile(code, stage_input, issues, checks)
        self._validate_ssm_consistency(code, blocks, ssm, issues, checks)
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
            severity = "warning" if has_proptypes else "error"
            issues.append(ValidationIssue(
                code="missing_data_types",
                message="San 组件未使用 dataTypes。" + ("当前检测到 propTypes，建议统一为 dataTypes。" if has_proptypes else ""),
                severity=severity,
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

    def _validate_script_rules(
        self,
        script: str,
        issues: list[ValidationIssue],
        checks: list[ValidationCheck],
    ) -> None:
        for pattern, code, suggestion in self.VUE_SCRIPT_PATTERNS:
            matches = re.findall(pattern, script)
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
                message="San 单文件组件通常不应保留 <style scoped>。",
                severity="error" if strict else "warning",
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
        hooks = self._expected_lifecycle_hooks(ssm)
        if not hooks:
            return

        expected_mapping = {
            "mounted": "attached",
            "beforeDestroy": "disposed",
            "destroyed": "disposed",
        }
        missing = []
        for source_hook in hooks:
            target_hook = expected_mapping.get(source_hook)
            if target_hook and not re.search(rf"\b{target_hook}\s*\(", script):
                missing.append(f"{source_hook} -> {target_hook}")

        passed = not missing
        checks.append(ValidationCheck(
            name="lifecycle_mapping_consistency",
            passed=passed,
            message="Vue 生命周期已映射到 San 生命周期",
            severity="warning",
        ))
        if missing:
            issues.append(ValidationIssue(
                code="missing_lifecycle_mapping",
                message=f"以下生命周期映射未在 San 中找到：{', '.join(missing)}。",
                severity="warning",
                location="script",
                suggestion="将 Vue 生命周期迁移到对应 San 生命周期，或确认逻辑已合并到其他生命周期中。",
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

        missing = [handler for handler in handlers if not re.search(rf"\bon-[\w:-]+\s*=\s*['\"]{re.escape(handler)}(?:\([^'\"]*\))?['\"]", template)]
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
                    severity="warning",
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
        options = self._script_options(ssm)
        hooks = options.get("lifecycle_hooks", [])
        result = []
        for hook in hooks if isinstance(hooks, list) else []:
            if isinstance(hook, dict):
                name = hook.get("name") or hook.get("hook")
                if name:
                    result.append(name)
            elif isinstance(hook, str):
                result.append(hook)
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
