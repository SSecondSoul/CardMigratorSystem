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
        data_access_rule = (
            "San data access rule: never destructure this.data or treat it as a plain object. "
            "Read fields separately, for example const initialGroups = "
            "this.data.get('initialGroups'), then write state with this.data.set(...).\n"
        )
        class_binding_rule = (
            "Object-style Vue :class bindings must be converted to a San string expression. "
            "Never emit class=\"{{{ selected: condition }}}\"; use a ternary string expression "
            "such as class=\"{{ condition ? 'selected' : '' }}\" and concatenate multiple "
            "conditional class names. Each template element must have exactly one class attribute; "
            "merge static and dynamic classes into that single attribute.\n"
        )

        return data_access_rule + class_binding_rule + (
            "你是一个 Vue 到 San 迁移修复专家。请根据 SSM、当前 San 代码和校验报告，修复 San 单文件组件。\n"
            "修复目标：输出必须满足下面列出的 San 结构、语法和渲染一致性规则；不要只生成语义上看起来像 San 的代码。\n\n"
            "输出要求：\n"
            "1. 只输出完整 .san 文件内容，不要输出解释、标题或 Markdown 代码围栏。\n"
            "2. 必须包含 <template>、<script>、<style> 三段。\n"
            "3. <script> 中必须使用 const san = require('san')、const DataTypes = san.DataTypes、module.exports = san.defineComponent(...)。\n"
            "4. Vue props 必须迁移为 San dataTypes，禁止在 san.defineComponent 中输出 props: {...}。\n"
            "5. initData() 只能返回稳定默认数据对象；Vue props 的 default（包括数组/对象工厂默认值）必须作为同名字段落入 initData；Vue data() 的全部初始值必须精确等价地保留，包括嵌套对象、数组、数字和启用项集合，不得用空字符串、空数组或删减后的集合替代；如果内部 data 依赖 props，必须在 inited() 中用 this.data.get('propName') 读取并 this.data.set(...) 同步。\n"
            "6. 组件状态读写必须使用 this.data.get('field') 和 this.data.set('field', value)；禁止直接修改 this.data.get(...) 或 computed 返回的对象/数组及其子对象，例如 selectedAsset.decision = value、note.resolved = true、nodes.push(node)、edges.splice(...)、node.status = status；必须用 map、filter、concat、Object.assign({}, ...) 或对象展开创建新的对象/数组，再通过 this.data.set('assets', nextAssets)、this.data.set('nodes', nextNodes) 等方式写回根字段；San computed 的结果也在 data store 中，computed 之间的依赖以及普通方法读取 computed 时必须使用 this.data.get('computedName')，禁止 this.computed.foo()；Vue 的 this.$emit(...) 或 emitEvent 包装方法必须迁移为 this.fire(...)，禁止 this.props、this.xxx 状态读写、this.$emit 和用 this.dispatch(...) 代替自定义事件。\n"
            "7. 方法必须直接定义在 san.defineComponent 顶层，禁止保留 Vue 的 methods: {...} 包裹。\n"
            "8. template 必须使用 San 语法：on-click、s-if、s-for；保留事件调用的全部参数，例如 on-click=\"move(-1)\"、on-click=\"select(task.id)\"；Vue v-for 的循环项和索引别名必须完整迁移，如果模板表达式使用 index，就必须显式写成 s-for=\"phase, index in phases trackby phase.key\"，禁止只声明 phase 却继续引用未绑定的 index；Vue v-for 的 :key 必须写入 s-for 的 trackby 子句，例如 s-for=\"task in tasks trackby task.id\"，禁止输出独立 key=\"{{ task.id }}\"、key=\"{= task.id =}\" 或 trackby=\"task.id\" 属性；所有 {{ ... }} 和 {= ... =} 插值必须完整闭合；双向绑定 {= assignable.path =} 只用于源 Vue v-model 对应的原生 input/select/textarea 可赋值路径；Vue :prop 和普通自定义组件 props 必须保持单向 {{ ... }}，例如 value=\"{{ stat.value }}\"，禁止写成 value=\"{= stat.value =}\"；方法调用、computed、disabled、checked、selected 等派生表达式也必须使用单向插值，例如 checked=\"{{ isEnabled(rule.id, enabled) }}\" 和 disabled=\"{{ expression }}\"，禁止 disabled=\"{= expression =}\"；class、style、checked、selected、disabled 等属性、s-if/s-for 指令以及文本插值调用普通方法时，不得把响应式依赖只隐藏在方法内部的 this.data.get(...) 中；必须保留 Vue 模板表达式中的完整参数，或将依赖字段显式传入，例如 class=\"{{ rowClass(row, winnerId, leaderId) }}\"、class=\"{{ slotClass(device.id, hour, schedule) }}\"、s-if=\"isOpen(module.id, openIds)\"、s-for=\"lesson in visibleLessons(module.lessons, completedIds, unfinishedOnly) trackby lesson.id\"、checked=\"{{ isSelected(row.id, selectedIds) }}\"；禁止丢失参数、使用 data-args/getAttribute 绕行，或保留 @click、v-if、v-for、v-model、:class 等 Vue 模板语法。\n"
            "9. style 标签必须写成 <style>，禁止输出 <style scoped>；必须保留原有 class 名和样式内容。\n"
            "10. 不要重新设计组件，不要引入外部依赖，不要删除已有 DOM 节点、文本、class 或样式。\n"
            "11. Vue 生命周期必须完整迁移：created 中的 prop 派生状态初始化放入 inited，mounted 中的初始方法调用和副作用放入 attached，beforeDestroy/destroyed 中的定时器或监听清理放入 disposed；不能只保留空钩子或只保留钩子名称。依赖 prop 的 data 不得在 initData() 中使用 this.propName 初始化，必须先返回稳定占位值，再在 inited() 中用 this.data.get('propName') 读取、复制并通过 this.data.set(...) 写入。Vue watch: {...} 不会被 San 自动注册，必须在 inited/attached 中使用 this.watch('field', handler)。\n"
            "12. 如果 DOM 对比报告指出缺失/新增/变化节点，优先修复 template 结构。\n"
            "13. 必须保留 Vue template 的 DOM 子节点顺序；元素和文本都存在但顺序改变仍属于错误。特别检查 label/th/footer 中 input 或 checkbox 与相邻文字、百分号、按钮的先后关系，不要用 CSS order 或 flex 排序掩盖模板顺序差异。\n"
            "14. value、checked、selected、disabled 等关键属性必须逐元素保留 Vue 原表达式，禁止把相邻或同级元素的条件合并进来。例如 select 的 :disabled=\"previewMode\" 必须迁移为 disabled=\"{{ previewMode }}\"，不能误用旁边按钮的 !canConnect || previewMode。\n"
            f"15. 补充要求：{extra_instruction}\n\n"
            "修复前请按下面清单自检，但最终不要输出清单：\n"
            "- 是否存在 props:、methods:、this.props、this.$emit、this.dispatch、<style scoped>、@click、v-if、v-for、v-model、:class？如果存在，必须改掉。\n"
            "- SSM props 是否全部出现在 dataTypes 中？\n"
            "- 带 default 的 Vue props 是否以同名字段和等价默认值出现在 initData 中？\n"
            "- Vue data() 中每个初始值是否精确保留了原始类型、嵌套内容、数组元素和数值，而不是空值或删减值？\n"
            "- computed 之间以及普通方法中是否只通过 this.data.get('computedName') 读取 computed，且完全不存在 this.computed.foo()？\n"
            "- 是否直接修改了 this.data.get(...) 或 computed 返回的对象、数组、数组元素及嵌套属性，或对其调用 push/splice/sort？所有此类更新是否改为创建新值并通过 this.data.set(...) 写回根字段？\n"
            "- created/mounted/beforeDestroy/destroyed 是否分别完整迁移到 inited/attached/disposed，且源钩子中的初始化、方法调用、定时器创建和清理均已保留？\n"
            "- 依赖 prop 的 data 是否在 inited() 中通过 this.data.get('propName') 初始化；所有 Vue watch 是否使用 this.watch(...) 实际注册，而不是保留 watch: {...}？\n"
            "- DOM 子节点顺序是否与 Vue 完全一致，尤其是 input/checkbox 与文字、百分号、按钮的相邻顺序？\n"
            "- 所有 {= ... =} 是否都来自源 Vue v-model 的原生表单可赋值路径；Vue :prop 和普通自定义组件 props 是否保持 {{ ... }} 单向绑定；disabled、checked、selected、方法调用和 computed 等派生表达式是否使用 {{ ... }}？\n"
            "- value、checked、selected、disabled 是否逐元素保留了 Vue 原表达式，而没有合并相邻元素的条件？\n"
            "- class、style、checked、selected、disabled、s-if、s-for 和文本插值中调用的普通方法是否隐藏读取了响应式字段？Vue 原表达式中的 openIds、completedIds、unfinishedOnly 等参数是否完整保留并显式传入？\n"
            "- Vue v-for 的循环项和索引别名是否完整迁移；模板中使用的 index/idx/$index 是否已在对应 s-for 中显式声明？所有 {{ ... }} 和 {= ... =} 是否完整闭合；Vue v-for 的 :key 是否迁移为 s-for 内联 trackby，且不存在独立 key 或 trackby 属性？\n"
            "- 事件绑定中的参数是否完整保留，且没有 data-args/getAttribute 绕行？\n"
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
            "data_initial_values_to_preserve": self._data_initial_values(options),
            "computed_logic_to_preserve": self._logic_items(options.get("computed", []), "getter_body_full", "getter_body"),
            "method_logic_to_preserve": self._logic_items(options.get("methods", []), "body_full", "body"),
            "computed_to_preserve": self._names_from_items(options.get("computed", []), ("name",)),
            "watch_to_preserve": self._names_from_items(options.get("watch", []), ("expression", "name")),
            "event_handlers_to_define_and_bind": self._event_handlers(ssm),
            "required_san_patterns": [
                "dataTypes: { ... } for props",
                "initData() { return { ... } } for defaults",
                "never destructure this.data; read each field with this.data.get('field')",
                "all Vue data() initial values preserved exactly, including nested objects, arrays, numbers, and enabled-item collections",
                "inited() with this.data.get('propName') and this.data.set(...) when data depends on props",
                "created/mounted/beforeDestroy/destroyed lifecycle behavior preserved in inited/attached/disposed, including initialization, method calls, and timer cleanup",
                "Vue watchers registered with this.watch(...) in a San lifecycle hook, never left as a watch: {...} option",
                "DOM child order preserved exactly, especially input/checkbox relative to adjacent text, percent signs, and buttons",
                "computed values must be read with this.data.get('computedName') from methods and other computed functions",
                "nested objects and arrays from this.data.get(...) or computed values are updated immutably and written back with this.data.set(...) instead of property assignment or push/splice",
                "two-way binding only for native form assignable paths originating from Vue v-model; Vue :prop and ordinary custom-component props remain one-way {{ ... }} bindings",
                "disabled/checked/selected use one-way {{ ... }} interpolation, never {= ... =}",
                "Vue object-style :class bindings are converted to San string expressions using ternaries and concatenation",
                "each template element has exactly one class attribute, with static and dynamic classes merged",
                "critical value/checked/selected/disabled expressions remain attached to the same source element and never absorb conditions from adjacent elements",
                "reactive values used by class/style/checked/selected/disabled/s-if/s-for/text method calls must appear in the template expression or be passed explicitly as method arguments",
                "every loop item/index alias referenced by a loop element is declared in s-for, for example phase, index in phases",
                "all interpolation delimiters are balanced and Vue v-for :key is migrated as an inline s-for trackby clause, never a separate key or trackby attribute",
                "top-level handler methods in san.defineComponent",
                "template events as on-click/on-input/etc.",
                "style tag without scoped",
            ],
            "forbidden_patterns": [
                "props:",
                "methods:",
                "this.props",
                "this.$emit",
                "this.computed.foo()",
                "this.<stateField>",
                "const { field } = this.data or any other direct destructuring of the San data store",
                "direct property assignment or mutating array methods on values returned by this.data.get(...) or computed state",
                "empty lifecycle hooks that omit source initialization, method calls, or timer cleanup",
                "Vue watch: {...} option without this.watch(...) registration",
                "reordered DOM children hidden by CSS order or flex layout",
                "{= methodCall(...) =} or other two-way binding to a derived expression",
                "disabled=\"{= expression =}\", checked=\"{= expression =}\", or selected=\"{= expression =}\"",
                "class=\"{{{ selected: condition }}}\" or any other Vue object literal inside a San class interpolation",
                "duplicate class attributes on the same template element",
                "template presentation methods that hide reactive this.data.get(...) dependencies",
                "references to index, idx, $index, or a Vue v-for index alias that is not declared by the corresponding s-for",
                "unbalanced interpolation delimiters or a separate key attribute on an s-for element",
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

    def _data_initial_values(self, options: dict[str, Any]) -> list[dict[str, Any]]:
        values = []
        items = options.get("data", []) or options.get("data_fields", [])
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("field_name")
            if not name:
                continue
            entry = {
                "name": name,
                "expression": item.get("default_value_expression")
                or item.get("default_value_summary", ""),
                "statically_evaluated": bool(item.get("default_value_static", False)),
            }
            if item.get("default_value_static", False):
                entry["value"] = item.get("default_value")
            values.append(entry)
        return values

    def _logic_items(self, items: Any, full_key: str, fallback_key: str) -> list[dict[str, Any]]:
        result = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            result.append({
                "name": item["name"],
                "source": item.get(full_key) or item.get(fallback_key, ""),
                "source_is_complete": bool(item.get(full_key)),
            })
        return result

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
