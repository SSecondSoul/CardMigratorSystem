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
        expected_contract = self._build_expected_contract(prompt_input.ssm)
        ssm_json = self._to_json(prompt_input.ssm)
        current_code = (prompt_input.current_code or "").strip()
        extra_instruction = prompt_input.extra_instruction.strip() or "优先修复 validate 与 visual_eval 报告中指出的问题，保持原有 DOM 结构、文本、class 和样式。"

        return (
            "你是一个 Vue 到 San 迁移修复专家。请根据 SSM、当前 San 代码和校验报告，修复 San 单文件组件。\n"
            "修复目标：输出必须满足下面列出的 San 结构、语法和渲染一致性规则；不要只生成语义上看起来像 San 的代码。\n\n"
            "输出要求：\n"
            "1. 只输出完整 .san 文件内容，不要输出解释、标题或 Markdown 代码围栏。\n"
            "2. 必须包含 <template>、<script>、<style> 三段。\n"
            "3. <script> 中必须使用 const san = require('san')、const DataTypes = san.DataTypes、module.exports = san.defineComponent(...)。\n"
            "4. Vue props 必须迁移为 San dataTypes，禁止在 san.defineComponent 中输出 props: {...}。\n"
            "5. initData() 只能返回稳定默认数据对象；如果 data 依赖 props，必须在 inited() 中用 this.data.get('propName') 读取并 this.data.set(...) 同步。\n"
            "6. 组件状态读写必须使用 this.data.get('field') 和 this.data.set('field', value)，禁止 this.props、this.xxx 状态读写、this.$emit。\n"
            "7. 方法必须直接定义在 san.defineComponent 顶层，禁止保留 Vue 的 methods: {...} 包裹。\n"
            "8. template 必须使用 San 语法：on-click、s-if、s-for；禁止 @click、v-if、v-for、v-model、:class 等 Vue 模板语法。\n"
            "9. style 标签必须写成 <style>，禁止输出 <style scoped>；必须保留原有 class 名和样式内容。\n"
            "10. 不要重新设计组件，不要引入外部依赖，不要删除已有 DOM 节点、文本、class 或样式。\n"
            "11. 如果 DOM 对比报告指出缺失/新增/变化节点，优先修复 template 结构。\n"
            f"12. 补充要求：{extra_instruction}\n\n"
            "修复前请按下面清单自检，但最终不要输出清单：\n"
            "- 是否存在 props:、methods:、this.props、this.$emit、<style scoped>、@click、v-if、v-for、v-model、:class？如果存在，必须改掉。\n"
            "- SSM props 是否全部出现在 dataTypes 中？\n"
            "- SSM data 字段是否全部在 initData 或 this.data.set 中有对应？\n"
            "- SSM 事件 handler 是否同时在 template 的 on-* 和 script 顶层方法中存在？\n\n"
            f"--- Source File ---\n{prompt_input.source_file or 'unknown'}\n\n"
            f"--- Expected San Contract From SSM ---\n{self._to_json(expected_contract)}\n\n"
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

    def _build_expected_contract(self, ssm: dict[str, Any]) -> dict[str, Any]:
        options = self._script_options(ssm)
        return {
            "component_name": self._component_name(ssm, options),
            "props_must_be_dataTypes": self._names_from_items(options.get("props", []), ("name", "prop_name")),
            "data_fields_to_preserve": self._names_from_items(
                options.get("data", []) or options.get("data_fields", []),
                ("name", "field_name"),
            ),
            "computed_to_preserve": self._names_from_items(options.get("computed", []), ("name",)),
            "watch_to_preserve": self._names_from_items(options.get("watch", []), ("expression", "name")),
            "event_handlers_to_define_and_bind": self._event_handlers(ssm),
            "required_san_patterns": [
                "dataTypes: { ... } for props",
                "initData() { return { ... } } for defaults",
                "inited() with this.data.get('propName') and this.data.set(...) when data depends on props",
                "top-level handler methods in san.defineComponent",
                "template events as on-click/on-input/etc.",
                "style tag without scoped",
            ],
            "forbidden_patterns": [
                "props:",
                "methods:",
                "this.props",
                "this.$emit",
                "this.<stateField>",
                "<style scoped>",
                "@click or other Vue event shorthand",
                "v-if/v-for/v-model",
                ":class or other Vue binding shorthand",
            ],
        }

    def _script_options(self, ssm: dict[str, Any]) -> dict[str, Any]:
        script = ssm.get("script", {}) if isinstance(ssm, dict) else {}
        options = script.get("options", {}) if isinstance(script, dict) else {}
        return options if isinstance(options, dict) else {}

    def _component_name(self, ssm: dict[str, Any], options: dict[str, Any]) -> str:
        metadata = ssm.get("metadata", {}) if isinstance(ssm, dict) else {}
        return metadata.get("component_name") or options.get("name") or ""

    def _names_from_items(self, items: Any, keys: tuple[str, ...]) -> list[str]:
        names = []
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict):
                for key in keys:
                    value = item.get(key)
                    if isinstance(value, str) and value:
                        names.append(value)
                        break
            elif isinstance(item, str) and item:
                names.append(item)
        return sorted(set(names))

    def _event_handlers(self, ssm: dict[str, Any]) -> list[str]:
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

    def _to_json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2)


def build_repair_prompt(prompt_input: RepairPromptInput) -> str:
    return RepairPromptBuilder().build(prompt_input)
