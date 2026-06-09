from dataclasses import asdict, dataclass, field
from typing import Any

from migration_pipeline.utils.san_render import render_san_component
from migration_pipeline.utils.vue_render import render_vue_component


@dataclass
class VisualEvalIssue:
    code: str
    message: str
    severity: str = "error"
    location: str = "render"
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VisualEvalStageInput:
    vue_file_path: str | None = None
    vue_source: str | None = None
    generated_code: str = ""
    generated_file_path: str = ""
    source_file: str = ""
    render_props: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_vue_input(self) -> bool:
        return bool(self.vue_source or self.vue_file_path)

    def has_san_input(self) -> bool:
        return bool(self.generated_code or self.generated_file_path)


@dataclass
class VisualEvalStageResult:
    visual_eval_passed: bool
    visual_eval_errors: list[dict[str, Any]]
    visual_eval_warnings: list[dict[str, Any]]
    visual_eval_summary: str
    vue_render_result: dict[str, Any] | None = None
    san_render_result: dict[str, Any] | None = None
    source_file: str = ""
    generated_file_path: str = ""

    def to_state_update(self) -> dict[str, Any]:
        return {
            "visual_eval_passed": self.visual_eval_passed,
            "visual_eval_errors": self.visual_eval_errors,
            "visual_eval_warnings": self.visual_eval_warnings,
            "visual_eval_summary": self.visual_eval_summary,
            "vue_render_result": self.vue_render_result,
            "san_render_result": self.san_render_result,
            "visual_eval_result": asdict(self),
        }


class VisualEvalStage:
    def run(self, stage_input: VisualEvalStageInput) -> VisualEvalStageResult:
        issues: list[VisualEvalIssue] = []
        vue_render_result = None
        san_render_result = None

        if stage_input.has_vue_input():
            vue_render_result = render_vue_component(
                vue_source=stage_input.vue_source,
                vue_file_path=stage_input.vue_file_path,
                props=stage_input.render_props,
            ).to_dict()
            self._collect_render_issues("vue", vue_render_result, issues)
        else:
            issues.append(VisualEvalIssue(
                code="missing_vue_render_input",
                message="visual_eval 需要 vue_source 或 vue_file_path 才能生成 Vue 渲染快照。",
                suggestion="在 pipeline state 中保留源 Vue 文件路径或源码。",
            ))

        if stage_input.has_san_input():
            san_render_result = render_san_component(
                san_source=stage_input.generated_code or None,
                san_file_path=stage_input.generated_file_path or None,
                props=stage_input.render_props,
            ).to_dict()
            self._collect_render_issues("san", san_render_result, issues)
        else:
            issues.append(VisualEvalIssue(
                code="missing_san_render_input",
                message="visual_eval 需要 generated_code 或 generated_file_path 才能生成 San 渲染快照。",
                suggestion="先执行 generate 阶段，或手动传入生成的 San 代码/文件路径。",
            ))

        errors = [issue.to_dict() for issue in issues if issue.severity == "error"]
        warnings = [issue.to_dict() for issue in issues if issue.severity == "warning"]
        passed = not errors
        summary = self._build_summary(passed, errors, warnings, vue_render_result, san_render_result)

        return VisualEvalStageResult(
            visual_eval_passed=passed,
            visual_eval_errors=errors,
            visual_eval_warnings=warnings,
            visual_eval_summary=summary,
            vue_render_result=vue_render_result,
            san_render_result=san_render_result,
            source_file=stage_input.source_file,
            generated_file_path=stage_input.generated_file_path,
        )

    def run_from_state(self, state: dict[str, Any]) -> dict[str, Any]:
        stage_input = VisualEvalStageInput(
            vue_file_path=state.get("vue_file_path"),
            vue_source=state.get("vue_source"),
            generated_code=state.get("generated_code", state.get("generation_code", "")),
            generated_file_path=state.get("generated_file_path", state.get("saved_file_path", "")),
            source_file=state.get("source_file", ""),
            render_props=state.get("visual_eval_render_props", state.get("render_props", {})),
            metadata=state.get("visual_eval_metadata", {}),
        )
        return self.run(stage_input).to_state_update()

    def _collect_render_issues(
        self,
        prefix: str,
        render_result: dict[str, Any],
        issues: list[VisualEvalIssue],
    ) -> None:
        if render_result.get("skipped"):
            issues.append(VisualEvalIssue(
                code=f"{prefix}_render_skipped",
                message=f"{prefix} 渲染被跳过：{render_result.get('reason', '')}",
                severity="warning",
                suggestion="确认 Node 环境可用后重新执行渲染评估。",
            ))
            return

        if not render_result.get("passed"):
            issues.append(VisualEvalIssue(
                code=f"{prefix}_render_failed",
                message=f"{prefix} 渲染失败：{render_result.get('reason', '')}",
                suggestion="根据 render diagnostics 修复组件运行时问题。",
            ))

        for diagnostic in render_result.get("diagnostics", []):
            severity = diagnostic.get("severity", "warning")
            issues.append(VisualEvalIssue(
                code=f"{prefix}_{diagnostic.get('code', 'render_diagnostic')}",
                message=diagnostic.get("message", f"{prefix} 渲染发现问题。"),
                severity=severity,
                suggestion="检查模板表达式、数据初始化、props 或生命周期逻辑。",
            ))

    def _build_summary(
        self,
        passed: bool,
        errors: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
        vue_render_result: dict[str, Any] | None,
        san_render_result: dict[str, Any] | None,
    ) -> str:
        status = "通过" if passed else "未通过"
        vue_nodes = self._node_count(vue_render_result)
        san_nodes = self._node_count(san_render_result)
        return f"渲染评估{status}：Vue 节点数 {vue_nodes}，San 节点数 {san_nodes}，{len(errors)} 个错误，{len(warnings)} 个警告。"

    def _node_count(self, render_result: dict[str, Any] | None) -> int:
        if not render_result:
            return 0
        dom_snapshot = render_result.get("dom_snapshot", {}) or {}
        return int(dom_snapshot.get("node_count", 0) or 0)


def visual_eval(stage_input: VisualEvalStageInput) -> VisualEvalStageResult:
    return VisualEvalStage().run(stage_input)
