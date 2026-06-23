import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RepairPromptInput:
    ssm: dict[str, Any]
    current_code: str
    source_file: str = ""
    validation_errors: list[dict[str, Any]] = field(default_factory=list)
    validation_warnings: list[dict[str, Any]] = field(default_factory=list)
    visual_eval_errors: list[dict[str, Any]] = field(default_factory=list)
    visual_eval_warnings: list[dict[str, Any]] = field(default_factory=list)
    dom_compare_result: dict[str, Any] | None = None
    extra_instruction: str = ""


class RepairPromptBuilder:
    def build(self, prompt_input: RepairPromptInput) -> str:
        report = self._build_repair_report(prompt_input)
        ssm_json = self._to_json(prompt_input.ssm)
        current_code = (prompt_input.current_code or "").strip()
        extra_instruction = prompt_input.extra_instruction.strip() or "优先修复 validate 与 visual_eval 报告中指出的问题，保持原有 DOM 结构、文本、class 和样式。"

        return (
            "你是一个 Vue 到 San 迁移修复专家。请根据 SSM、当前 San 代码和校验报告，修复 San 单文件组件。\n"
            "输出要求：\n"
            "1. 只输出完整 .san 文件内容，不要输出解释、标题或 Markdown 代码围栏。\n"
            "2. 必须包含 <template>、<script>、<style> 三段。\n"
            "3. <script> 中必须使用 const san = require('san')、const DataTypes = san.DataTypes、module.exports = san.defineComponent(...)。\n"
            "4. 必须保留并修正组件 name、dataTypes、initData、生命周期、事件绑定、this.data.get/set、this.fire 等 San 写法。\n"
            "5. 不要重新设计组件，不要引入外部依赖，不要删除已有样式和 class。\n"
            "6. 如果 DOM 对比报告指出缺失/新增/变化节点，优先修复 template 结构。\n"
            f"7. 补充要求：{extra_instruction}\n\n"
            f"--- Source File ---\n{prompt_input.source_file or 'unknown'}\n\n"
            f"--- SSM ---\n{ssm_json}\n\n"
            f"--- Current San Code ---\n{current_code}\n\n"
            f"--- Repair Report ---\n{self._to_json(report)}\n"
        )

    def _build_repair_report(self, prompt_input: RepairPromptInput) -> dict[str, Any]:
        return {
            "validation": {
                "errors": self._compact_issues(prompt_input.validation_errors),
                "warnings": self._compact_issues(prompt_input.validation_warnings),
            },
            "visual_eval": {
                "errors": self._compact_issues(prompt_input.visual_eval_errors),
                "warnings": self._compact_issues(prompt_input.visual_eval_warnings),
                "dom_compare": self._compact_dom_compare(prompt_input.dom_compare_result or {}),
            },
        }

    def _compact_issues(self, issues: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
        compacted = []
        for issue in issues[:limit]:
            compacted.append({
                "code": issue.get("code", ""),
                "message": issue.get("message", ""),
                "severity": issue.get("severity", ""),
                "location": issue.get("location", ""),
                "suggestion": issue.get("suggestion", ""),
            })
        return compacted

    def _compact_dom_compare(self, dom_compare: dict[str, Any]) -> dict[str, Any]:
        if not dom_compare:
            return {}
        return {
            "tree_edit_distance": dom_compare.get("tree_edit_distance"),
            "structure_similarity": dom_compare.get("structure_similarity"),
            "tag_sequence_similarity": dom_compare.get("tag_sequence_similarity"),
            "text_similarity": dom_compare.get("text_similarity"),
            "summary": dom_compare.get("summary", ""),
            "missing_nodes": self._compact_nodes(dom_compare.get("missing_nodes", [])),
            "extra_nodes": self._compact_nodes(dom_compare.get("extra_nodes", [])),
            "changed_nodes": self._compact_nodes(dom_compare.get("changed_nodes", [])),
        }

    def _compact_nodes(self, nodes: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
        compacted = []
        for node in nodes[:limit]:
            compacted.append({
                "path": node.get("path", ""),
                "reason": node.get("reason", ""),
                "cost": node.get("cost", 0),
                "vue_node": node.get("vue_node"),
                "san_node": node.get("san_node"),
            })
        return compacted

    def _to_json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2)


def build_repair_prompt(prompt_input: RepairPromptInput) -> str:
    return RepairPromptBuilder().build(prompt_input)
