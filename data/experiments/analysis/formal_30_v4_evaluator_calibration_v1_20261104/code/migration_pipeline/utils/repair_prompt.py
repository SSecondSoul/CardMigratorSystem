import json
import re
from dataclasses import dataclass, field
from typing import Any
from migration_pipeline.utils.residual_semantics import residual_semantics


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
    vue_source: str = ""


class RepairPromptBuilder:
    INITDATA_COMPUTED_RESIDUAL_CODES = frozenset({
        "invalid_san_init_data_store_access",
        "invalid_san_computed_instance_method_call",
    })
    EVENT_COMPUTED_REACTIVITY_CODES = frozenset({
        "invalid_san_event_handler_syntax",
        "invalid_san_computed_instance_method_call",
        "hidden_template_reactive_dependency",
    })
    EVENT_COMPUTED_RESIDUAL_CODES = frozenset({
        "invalid_san_event_handler_syntax",
        "invalid_san_computed_instance_method_call",
    })
    INLINE_INIT_COMPUTED_LIFECYCLE_CODES = frozenset({
        "invalid_san_init_data_store_access",
        "missing_inline_prop_dependent_initialization",
        "invalid_san_computed_instance_method_call",
        "hidden_template_reactive_dependency",
        "lifecycle_behavior_not_landed",
    })
    INLINE_INIT_COMPUTED_REACTIVITY_CODES = frozenset({
        "invalid_san_init_data_store_access",
        "missing_inline_prop_dependent_initialization",
        "invalid_san_computed_instance_method_call",
        "hidden_template_reactive_dependency",
    })
    EVENT_RESIDUAL_CODES = frozenset({
        "missing_event_handlers",
        "missing_event_bindings",
        "event_arguments_not_landed",
    })
    SEMANTIC_RESIDUAL_CODES = frozenset({
        "source_watch_persistence_not_landed",
        "source_watch_persistence_unproven",
        "source_mounted_order_not_landed",
        "source_startup_phase_not_landed",
        "source_method_interface_not_landed",
        "source_method_trigger_added",
        "missing_lifecycle_mapping",
        "invalid_san_textarea_binding",
        "missing_data_types",
        "missing_self_click_guard",
        "invalid_san_event_handler_syntax",
        "invalid_san_init_data_store_access",
        "invalid_san_computed_instance_method_call",
        "hidden_template_reactive_dependency",
        "invalid_san_inline_computed_method_invocation",
        "event_arguments_not_landed",
        "noncallable_san_watch_listener",
        "invalid_san_multi_argument_fire",
        "unsupported_san_inline_template_math_global",
        "nested_state_mutation",
        "lifecycle_behavior_not_landed",
    })

    def build(self, prompt_input: RepairPromptInput) -> str:
        prompt = self._build(prompt_input)
        if any(e.get("code") in {"source_watch_persistence_not_landed", "source_watch_persistence_unproven"}
               for e in prompt_input.validation_errors):
            from migration_pipeline.utils.bounded_semantics import inspect_semantics
            evidence = inspect_semantics(prompt_input.current_code, prompt_input.vue_source,
                                         ssm=prompt_input.ssm).get("watcher_contracts", []) if prompt_input.vue_source else []
            prompt += ("\nSource watcher contract evidence (full AST-extracted source handler, not a truncated "
                       "SSM preview; do not invent an absent contract):\n" + self._to_json(evidence) + "\n")
        methods = (((prompt_input.ssm or {}).get("script") or {}).get("options") or {}).get("methods") or []
        names = [m["name"] for m in methods if isinstance(m, dict) and isinstance(m.get("name"), str)]
        if names:
            prompt += ("\nSource method interface preservation: retain callable parent methods even when unused by "
                "the current template or lifecycle. A renamed body alone does not prove the original public "
                "interface is retained; preserve a callable wrapper where appropriate. San reserved-name "
                "collisions require a proven mapping, never overwrite the San initData factory. Do not add "
                "UI/lifecycle calls to previously unreferenced methods, including permission requests.\n"
                f"Source method names: {self._to_json(names)}\n")
        return prompt

    def _build(self, prompt_input: RepairPromptInput) -> str:
        error_codes = {issue.get("code") for issue in prompt_input.validation_errors}
        if (
            len(error_codes) >= 2
            and error_codes <= self.EVENT_RESIDUAL_CODES
            and not prompt_input.visual_eval_errors
        ):
            return self._build_event_residual_prompt(prompt_input)
        if (
            error_codes == {"invalid_san_computed_instance_method_call"}
            and not prompt_input.visual_eval_errors
        ):
            return self._build_computed_method_call_prompt(prompt_input)
        if (
            error_codes == self.INITDATA_COMPUTED_RESIDUAL_CODES
            and not prompt_input.visual_eval_errors
        ):
            return self._build_initdata_computed_residual_prompt(prompt_input)
        if (
            error_codes == {"missing_inline_prop_dependent_initialization"}
            and not prompt_input.visual_eval_errors
        ):
            return self._build_inline_prop_initialization_prompt(prompt_input)
        if (
            error_codes == self.EVENT_COMPUTED_REACTIVITY_CODES
            and not prompt_input.visual_eval_errors
        ):
            return self._build_event_computed_reactivity_prompt(prompt_input)
        if (
            error_codes == self.EVENT_COMPUTED_RESIDUAL_CODES
            and not prompt_input.visual_eval_errors
        ):
            return self._build_event_computed_residual_prompt(prompt_input)
        if (
            error_codes == self.INLINE_INIT_COMPUTED_LIFECYCLE_CODES
            and not prompt_input.visual_eval_errors
        ):
            return self._build_inline_init_computed_lifecycle_prompt(prompt_input)
        if (
            error_codes == self.INLINE_INIT_COMPUTED_REACTIVITY_CODES
            and not prompt_input.visual_eval_errors
        ):
            return self._build_inline_init_computed_reactivity_prompt(prompt_input)
        if (
            (len(error_codes) >= 2 or error_codes in (
                {"missing_data_types"}, {"hidden_template_reactive_dependency"}, {"lifecycle_behavior_not_landed"},
                {"missing_lifecycle_mapping"}, {"source_watch_persistence_not_landed"},
                {"source_watch_persistence_unproven"},
                {"source_mounted_order_not_landed"}, {"source_startup_phase_not_landed"},
                {"source_method_interface_not_landed"}, {"source_method_trigger_added"}))
            and error_codes <= self.SEMANTIC_RESIDUAL_CODES
            and not prompt_input.visual_eval_errors
        ):
            return self._build_semantic_residual_prompt(prompt_input)
        report = self._build_repair_report(prompt_input)
        expected_contract = self._build_expected_contract(prompt_input.ssm)
        ssm_json = self._to_json(prompt_input.ssm)
        current_code = (prompt_input.current_code or "").strip()
        extra_instruction = prompt_input.extra_instruction.strip() or "优先修复 validate 与 visual_eval 报告中指出的问题，保持原有 DOM 结构、文本、class 和样式。"
        data_access_rule = (
            "San data access rule: never destructure this.data or treat it as a plain object. "
            "Read fields separately, for example const initialGroups = "
            "this.data.get('initialGroups'), then write state with this.data.set(...). "
            "This also applies inside every inline child: if a Vue prop is named data, "
            "use this.data.get('data').map(...) and this.data.get('data').length, "
            "never this.data.map(...) or this.data.length. San initData runs before this.data "
            "exists, including in inline children: never read this.data or prop values there; "
            "return defaults and copy props into derived state in inited(), watching the prop "
            "if it can change. Computed values must be read with this.data.get('computedName'), "
            "not this.computedName. San computed callbacks "
            "do not receive the full component instance: never call this.getX() or any other "
            "component method inside computed; use pure helper functions with explicit data arguments. "
            "In every inline child template, on-* handlers must call component methods, not assign "
            "state directly: use on-mouseenter=\"setHoveredIndex(index)\" with a method that "
            "calls this.data.set('hoveredIndex', index), never on-mouseenter=\"hoveredIndex = index\". "
            "San this.fire(name, payload) carries one payload: do not pass separate key and value "
            "arguments. Fire {key, value} and unpack $event.key/$event.value in the parent binding. "
            "San event attributes must have a nonempty method handler. Put modifiers in the event "
            "value, for example on-submit=\"prevent:handleSubmit\" and "
            "on-click=\"stop:handleClick\", never on-submit.prevent or on-click.stop. "
            "For loop item and index aliases use s-for=\"item, index in items trackby item.id\", "
            "never Vue's parenthesized (item, index) tuple. "
            "Computed entries are values, not callable formatters: when an inline child template "
            "uses formatDate(task.dueDate) or formatTrend(trend), define a top-level child method "
            "accepting that argument, not computed: { formatDate() { ... } }. "
            "Do not call Math.abs(...) directly inside inline San template interpolation; call a "
            "component method such as formatChange(change). Avoid member calls in inline child render expressions: "
            "move collection checks and string formatting into top-level child methods, passing every reactive "
            "receiver and argument explicitly. Convert Vue object-style bindings "
            "to CSS strings, for example style=\"{{ 'background-color: ' + insight.color + ';' }}\".\n"
        )
        class_binding_rule = (
            "Object-style Vue :class bindings must be converted to a San string expression. "
            "Never emit class=\"{{{ selected: condition }}}\"; use a ternary string expression "
            "such as class=\"{{ condition ? 'selected' : '' }}\" and concatenate multiple "
            "conditional class names. Each template element must have exactly one class attribute; "
            "merge static and dynamic classes into that single attribute.\n"
        )
        directive_rule = (
            "San s-if/s-else-if/s-for directive values use raw expressions: "
            "s-if=\"showSettings\" and s-for=\"item in items trackby item.id\". "
            "Never use s-if=\"{{showSettings}}\", s-if=\"{= showSettings =}\", "
            "or s-for=\"{{item in items}}\".\n"
        )
        component_rule = (
            "Define every JavaScript identifier used in the San components registry. For each SSM "
            "component whose definition_location is inline, migrate inline_definition.source_code "
            "to a complete local san.defineComponent definition before the parent component; never "
            "replace a source identifier with an undefined placeholder. Custom-element tag names "
            "with hyphens are STRING KEYS, never JavaScript variables: use "
            "const StatCard = san.defineComponent({...}) and components: {'stat-card': StatCard}, "
            "not const stat-card or components: {'stat-card': stat-card}. Verify every registry "
            "value names a declared identifier. For child custom events, explicitly forward the "
            "single payload with on-save=\"saveSettings($event)\" when the parent handler needs it. "
            "Preserve modal backdrop-only close behavior: clicks inside modal content must not close it. "
            "This is a standalone San "
            "file: never use require('./Child') or another external require for an inline child.\n"
        )
        watch_listener_rule = (
            "San this.watch(path, listener) requires a callable second argument. Never pass a "
            "Vue watch descriptor such as {handler() {}, immediate: true, deep: true} directly; "
            "extract a function callback and preserve immediate/deep behavior deliberately. "
            "An object listener may compile but fails at runtime with listener.call is not a function.\n"
        )
        reserved_method_rule = (
            "If Vue defines a business method named initData, rename that business method in San, "
            "update all calls, and preserve mounted calls in attached(). San initData must remain only "
            "the state factory that returns defaults.\n"
        )

        return data_access_rule + class_binding_rule + directive_rule + component_rule + watch_listener_rule + reserved_method_rule + (
            "你是一个 Vue 到 San 迁移修复专家。请根据 SSM、当前 San 代码和校验报告，修复 San 单文件组件。\n"
            "修复目标：输出必须满足下面列出的 San 结构、语法和渲染一致性规则；不要只生成语义上看起来像 San 的代码。\n\n"
            "输出要求：\n"
            "1. 只输出完整 .san 文件内容，不要输出解释、标题或 Markdown 代码围栏。\n"
            "2. 必须包含 <template>、<script>、<style> 三段。\n"
            "3. <script> 中必须使用 const san = require('san')、const DataTypes = san.DataTypes、module.exports = san.defineComponent(...)。\n"
            "4. Vue props 必须迁移为 San dataTypes，禁止在 san.defineComponent 中输出 props: {...}。\n"
            "5. initData() 只能返回稳定默认数据对象；Vue props 的 default（包括数组/对象工厂默认值）必须作为同名字段落入 initData；Vue data() 的全部初始值必须精确等价地保留，包括嵌套对象、数组、数字和启用项集合，不得用空字符串、空数组或删减后的集合替代；如果内部 data 依赖 props，必须在 inited() 中用 this.data.get('propName') 读取并 this.data.set(...) 同步。\n"
            "6. 组件状态读写必须使用 this.data.get('field') 和 this.data.set('field', value)；禁止直接修改 this.data.get(...) 或 computed 返回的对象/数组及其子对象，例如 selectedAsset.decision = value、note.resolved = true、nodes.push(node)、edges.splice(...)、node.status = status；必须用 map、filter、concat、Object.assign({}, ...) 或对象展开创建新的对象/数组，再通过 this.data.set('assets', nextAssets)、this.data.set('nodes', nextNodes) 等方式写回根字段；San computed 的结果也在 data store 中，computed 之间的依赖以及普通方法读取 computed 时必须使用 this.data.get('computedName')，禁止 this.computed.foo()；Vue 的 this.$emit(...) 或 emitEvent 包装方法必须迁移为 this.fire(...)，禁止 this.props、this.xxx 状态读写、this.$emit 和用 this.dispatch(...) 代替自定义事件。\n"
            "7. 父组件以及每一个内联子组件的方法都必须直接定义在各自 san.defineComponent 顶层；逐个检查所有组件对象，任何位置都禁止保留 Vue 的 methods: {...} 包裹。\n"
            "8. template 必须使用 San 语法：on-click、s-if、s-for；保留事件调用的全部参数，例如 on-click=\"move(-1)\"、on-click=\"select(task.id)\"；Vue v-for 的循环项和索引别名必须完整迁移，如果模板表达式使用 index，就必须显式写成 s-for=\"phase, index in phases trackby phase.key\"，禁止只声明 phase 却继续引用未绑定的 index；Vue v-for 的 :key 必须写入 s-for 的 trackby 子句，例如 s-for=\"task in tasks trackby task.id\"，禁止输出独立 key=\"{{ task.id }}\"、key=\"{= task.id =}\" 或 trackby=\"task.id\" 属性；所有 {{ ... }} 和 {= ... =} 插值必须完整闭合；双向绑定 {= assignable.path =} 只用于源 Vue v-model 对应的原生 input/select/textarea 可赋值路径；Vue :prop 和普通自定义组件 props 必须保持单向 {{ ... }}，例如 value=\"{{ stat.value }}\"，禁止写成 value=\"{= stat.value =}\"；方法调用、computed、disabled、checked、selected 等派生表达式也必须使用单向插值，例如 checked=\"{{ isEnabled(rule.id, enabled) }}\" 和 disabled=\"{{ expression }}\"，禁止 disabled=\"{= expression =}\"；class、style、checked、selected、disabled 等属性、s-if/s-for 指令以及文本插值调用普通方法时，不得把响应式依赖只隐藏在方法内部的 this.data.get(...) 中；必须保留 Vue 模板表达式中的完整参数，或将依赖字段显式传入，例如 class=\"{{ rowClass(row, winnerId, leaderId) }}\"、class=\"{{ slotClass(device.id, hour, schedule) }}\"、s-if=\"isOpen(module.id, openIds)\"、s-for=\"lesson in visibleLessons(module.lessons, completedIds, unfinishedOnly) trackby lesson.id\"、checked=\"{{ isSelected(row.id, selectedIds) }}\"；禁止丢失参数、使用 data-args/getAttribute 绕行，或保留 @click、v-if、v-for、v-model、:class 等 Vue 模板语法。\n"
            "9. style 标签必须写成 <style>，禁止输出 <style scoped>；必须保留原有 class 名和样式内容。\n"
            "10. 不要重新设计组件，不要引入外部依赖，不要删除已有 DOM 节点、文本、class 或样式。\n"
            "11. Vue 生命周期必须完整迁移：created 中的 prop 派生状态初始化放入 inited，mounted 中的初始方法调用和副作用放入 attached，beforeDestroy/destroyed 中的定时器或监听清理放入 disposed；不能只保留空钩子或只保留钩子名称。依赖 prop 的 data 不得在 initData() 中使用 this.propName 初始化，必须先返回稳定占位值，再在 inited() 中用 this.data.get('propName') 读取、复制并通过 this.data.set(...) 写入。Vue watch: {...} 不会被 San 自动注册，必须把 this.watch('field', handler) 调用直接放在 inited() 或 attached() 内；禁止定义未被生命周期调用的普通 watch() 方法来包裹 this.watch(...)。\n"
            "12. 如果 DOM 对比报告指出缺失/新增/变化节点，优先修复 template 结构。\n"
            "13. 必须保留 Vue template 的 DOM 子节点顺序；元素和文本都存在但顺序改变仍属于错误。特别检查 label/th/footer 中 input 或 checkbox 与相邻文字、百分号、按钮的先后关系，不要用 CSS order 或 flex 排序掩盖模板顺序差异。\n"
            "14. value、checked、selected、disabled 等关键属性必须逐元素保留 Vue 原表达式，禁止把相邻或同级元素的条件合并进来。例如 select 的 :disabled=\"previewMode\" 必须迁移为 disabled=\"{{ previewMode }}\"，不能误用旁边按钮的 !canConnect || previewMode。\n"
            f"15. 补充要求：{extra_instruction}\n\n"
            "修复前请按下面清单自检，但最终不要输出清单：\n"
            "- 父组件和每一个内联子组件中是否存在 props:、methods:、this.props、this.$emit、this.dispatch、<style scoped>、@click、v-if、v-for、v-model、:class？如果存在，必须改掉。\n"
            "- SSM props 是否全部出现在 dataTypes 中？\n"
            "- 带 default 的 Vue props 是否以同名字段和等价默认值出现在 initData 中？\n"
            "- Vue data() 中每个初始值是否精确保留了原始类型、嵌套内容、数组元素和数值，而不是空值或删减值？\n"
            "- computed 之间以及普通方法中是否只通过 this.data.get('computedName') 读取 computed，且完全不存在 this.computed.foo()？\n"
            "- 是否直接修改了 this.data.get(...) 或 computed 返回的对象、数组、数组元素及嵌套属性，或对其调用 push/splice/sort？所有此类更新是否改为创建新值并通过 this.data.set(...) 写回根字段？\n"
            "- created/mounted/beforeDestroy/destroyed 是否分别完整迁移到 inited/attached/disposed，且源钩子中的初始化、方法调用、定时器创建和清理均已保留？\n"
            "- 依赖 prop 的 data 是否在 inited() 中通过 this.data.get('propName') 初始化；所有 Vue watch 是否直接在 inited()/attached() 内使用 this.watch(...) 实际注册，而不是保留 watch: {...} 或未调用的普通 watch() 方法？\n"
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

    def _build_computed_method_call_prompt(self, prompt_input: RepairPromptInput) -> str:
        """Focus a single-error repair on computed callbacks, without a redundant SSM dump."""
        current_code = (prompt_input.current_code or "").strip()
        extra_instruction = prompt_input.extra_instruction.strip()
        return (
            "You are repairing a standalone San single-file component. The ONLY reported "
            "validation error is invalid_san_computed_instance_method_call. The visual "
            "comparison has no reported errors. Repair every computed callback in every "
            "san.defineComponent (including inline children) that calls this.someMethod(...). "
            "San computed callbacks do not have those component instance methods. "
            "Read reactive inputs with this.data.get('field') inside computed, then pass "
            "the values as explicit arguments to pure JavaScript helper functions outside "
            "the component or local pure functions inside that computed callback. "
            "Do not merely remove `this.`: an unbound method name would still fail. "
            "Preserve the observable behavior of methods called by the template. If a "
            "render method internally reads reactive fields with this.data.get(...), "
            "make those dependencies explicit in the template call and update the method "
            "signature together. For example, change getX(idx) to getX(idx, data.length) "
            "and getY(point.value) to getY(point.value, maxValue, minValue), while preserving "
            "their coordinates. Never change a method signature without changing every "
            "corresponding template call. Use distinct pure helpers in computed callbacks. "
            "Do not use this.getX(...), this.getY(...), or ANY this.method(...) inside "
            "computed. Preserve the calculation, its empty-data behavior, and template "
            "methods used by rendering. Apart from explicit dependency arguments, keep "
            "template, styles, component registrations, "
            "state defaults, and unrelated behavior unchanged. Return the COMPLETE .san "
            "file with <template>, <script>, and <style>; output no explanation or code fence.\n"
            "Before responding, inspect every computed block again and ensure no "
            "this.method(...) calls remain.\n"
            f"Additional instruction: {extra_instruction or 'Preserve all existing behavior.'}\n"
            f"Validation errors:\n{self._to_json(self._compact_issues(prompt_input.validation_errors))}\n"
            f"Current San code:\n{current_code}\n"
        )

    def _build_initdata_computed_residual_prompt(self, prompt_input: RepairPromptInput) -> str:
        """Constrain the two-error repair to initialization and computed semantics."""
        ssm = prompt_input.ssm if isinstance(prompt_input.ssm, dict) else {}
        options = (ssm.get("script") or {}).get("options") or {}
        issue_text = " ".join(str(item.get("message") or "") for item in prompt_input.validation_errors)
        source_children = []
        for item in (options.get("components", []) if isinstance(options, dict) else []):
            if not isinstance(item, dict):
                continue
            source_name = item.get("source_name") or item.get("registered_name")
            inline = item.get("inline_definition") or {}
            if (isinstance(source_name, str) and source_name in issue_text
                    and isinstance(inline, dict) and inline.get("source_code")):
                source_children.append({
                    "name": source_name,
                    "source_code": inline["source_code"],
                })
        source_methods = [
            {"name": item.get("name"), "body": item.get("body_full") or item.get("body")}
            for item in (options.get("methods", []) if isinstance(options, dict) else [])
            if isinstance(item, dict) and item.get("name")
            and re.search(rf"\b{re.escape(item['name'])}\b", issue_text)
        ]
        lifecycle = [
            {"vue_hook": item.get("vue_hook"), "san_hook": item.get("san_hook"),
             "body": item.get("body")}
            for item in (options.get("lifecycle_hooks", []) if isinstance(options, dict) else [])
            if isinstance(item, dict) and item.get("vue_hook") in {"created", "mounted"}
        ]
        extra = prompt_input.extra_instruction.strip() or "Preserve the source lifecycle order."
        return (
            "Repair ONLY the two remaining validation error families in this standalone San file: "
            "invalid_san_init_data_store_access and invalid_san_computed_instance_method_call. "
            "The current visual comparison has no reported errors. Return the COMPLETE .san file "
            "with no Markdown fence or explanation. Keep template, CSS, component registrations, "
            "events, state defaults, and unrelated methods unchanged.\n"
            "1. San initData runs before this.data exists. In every affected component, return "
            "stable defaults without this.data or instance method calls. If a Vue data field "
            "depends on a prop, initialize that field in San inited() using this.data.get('prop') "
            "and this.data.set('field', value), BEFORE registering its prop watcher. The watcher "
            "must continue to update the field on later prop changes. Preserve the helper's "
            "fallback values and copying semantics. Do not move this work to attached().\n"
            "2. A San computed callback cannot call this.someMethod(...). If the source method "
            "is pure, extract its exact calculation into a script-level pure function; call that "
            "function from computed, while retaining a component method that delegates to the "
            "same pure function for existing non-computed callers. Do not replace `this.method` "
            "with an undefined bare identifier. If the method reads reactive state, pass every "
            "required value explicitly. Preserve edge cases and date/time semantics.\n"
            "3. Do not add pre-mount writes to parent state fields loaded by source mounted() "
            "methods. If a prior candidate already added such an unrelated write, remove it. "
            "Do not alter the source mounted action order in San attached().\n"
            "Before responding, inspect all initData and computed blocks again. Do not claim "
            "success by changing validators or deleting behavior.\n"
            f"Additional instruction: {extra}\n"
            f"Validation errors:\n{self._to_json(self._compact_issues(prompt_input.validation_errors))}\n"
            f"Relevant source children:\n{self._to_json(source_children)}\n"
            f"Relevant source methods:\n{self._to_json(source_methods)}\n"
            f"Source lifecycle:\n{self._to_json(lifecycle)}\n"
            f"Current San code:\n{(prompt_input.current_code or '').strip()}\n"
        )

    def _build_inline_prop_initialization_prompt(self, prompt_input: RepairPromptInput) -> str:
        """Focus on first-mount prop state without changing unrelated behavior."""
        ssm = prompt_input.ssm if isinstance(prompt_input.ssm, dict) else {}
        options = (ssm.get("script") or {}).get("options") or {}
        issue_text = " ".join(str(item.get("message") or "") for item in prompt_input.validation_errors)
        source_children = []
        for item in options.get("components", []) if isinstance(options, dict) else []:
            if not isinstance(item, dict):
                continue
            source_name = item.get("source_name") or item.get("registered_name")
            inline = item.get("inline_definition") or {}
            if (isinstance(source_name, str) and source_name in issue_text
                    and isinstance(inline, dict) and inline.get("source_code")):
                source_children.append({"name": source_name, "source_code": inline["source_code"]})
        return (
            "Repair ONLY missing_inline_prop_dependent_initialization in this standalone "
            "San file. Return the COMPLETE .san file with no Markdown fence or explanation. "
            "The source Vue child data() creates prop-derived state on first creation; "
            "a San this.watch callback does NOT run for an initial prop value. For every "
            "named child in the validation error, keep initData() free of this.data access "
            "and retain stable defaults. In the child's inited(), BEFORE this.watch(...), "
            "read each initial prop using this.data.get('prop'), call the existing copy/helper "
            "logic, and this.data.set('field', result). Keep its watcher for later prop changes. "
            "Do not initialize parent mounted-loaded state early. Preserve all templates, CSS, "
            "component registrations, events, computed, parent lifecycle and unrelated methods. "
            "Never solve this by removing a prop, data field, or watcher.\n"
            f"Validation errors:\n{self._to_json(self._compact_issues(prompt_input.validation_errors))}\n"
            f"Relevant source children:\n{self._to_json(source_children)}\n"
            f"Additional instruction: {prompt_input.extra_instruction.strip() or 'Preserve source behavior.'}\n"
            f"Current San code:\n{(prompt_input.current_code or '').strip()}\n"
        )

    def _build_event_computed_reactivity_prompt(self, prompt_input: RepairPromptInput) -> str:
        """Constrain a three-error residual to event, computed and binding semantics."""
        ssm = prompt_input.ssm if isinstance(prompt_input.ssm, dict) else {}
        options = (ssm.get("script") or {}).get("options") or {}
        methods = [
            {"name": item.get("name"), "body": item.get("body_full") or item.get("body")}
            for item in (options.get("methods", []) if isinstance(options, dict) else [])
            if isinstance(item, dict) and item.get("name") in {"isOverdue", "getTaskCount"}
        ]
        source_events = [
            {"event_name": item.get("event_name"),
             "handler_expression": item.get("handler_expression"),
             "modifiers": item.get("modifiers")}
            for item in (ssm.get("template") or {}).get("event_bindings", [])
            if isinstance(item, dict) and item.get("event_name")
        ]
        extra = prompt_input.extra_instruction.strip() or "Preserve all source behavior."
        return (
            "Repair ONLY these three remaining static error families in this standalone "
            "San file: invalid_san_event_handler_syntax, "
            "invalid_san_computed_instance_method_call, and "
            "hidden_template_reactive_dependency. Return the COMPLETE .san file with no "
            "Markdown fence or explanation. Preserve existing template structure, CSS, "
            "component registrations, initial prop-derived state, event contracts, "
            "lifecycle order, and unrelated methods.\n"
            "1. For an empty on-* binding that corresponds to a source Vue modifier-only "
            "event, use San's value modifier plus a named component no-op method. Do not "
            "leave an empty handler or invent a business side effect. Keep neighboring "
            "drag/drop bindings unchanged.\n"
            "2. San computed callbacks cannot call this.someMethod(...). If that method "
            "is pure, extract its exact calculation into a script-level helper and call "
            "the helper from computed. Retain a component method delegating to that "
            "helper for non-computed callers. Preserve date and edge-case behavior.\n"
            "3. A method called from template interpolation must receive its reactive "
            "dependencies as explicit template arguments. Pass the state field to the "
            "template method and use that argument inside the method, rather than "
            "reading the same field through this.data.get there. Preserve every branch.\n"
            "Do not move source mounted() writes into inited(), remove watchers, alter "
            "inline child first-prop initialization, or silence validators.\n"
            f"Additional instruction: {extra}\n"
            f"Validation errors:\n{self._to_json(self._compact_issues(prompt_input.validation_errors))}\n"
            f"Relevant source methods:\n{self._to_json(methods)}\n"
            f"Source event bindings:\n{self._to_json(source_events)}\n"
            f"Current San code:\n{(prompt_input.current_code or '').strip()}\n"
        )

    def _build_event_computed_residual_prompt(self, prompt_input: RepairPromptInput) -> str:
        """Constrain the two-error case without changing unrelated event contracts."""
        ssm = prompt_input.ssm if isinstance(prompt_input.ssm, dict) else {}
        options = (ssm.get("script") or {}).get("options") or {}
        error_text = " ".join(
            str(item.get("message", "")) for item in prompt_input.validation_errors
            if isinstance(item, dict)
        )
        methods = [
            {"name": item.get("name"), "body": item.get("body_full") or item.get("body")}
            for item in (options.get("methods", []) if isinstance(options, dict) else [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
            and re.search(rf"\b{re.escape(item['name'])}\b", error_text)
        ]
        events = [
            {"event_name": item.get("event_name"),
             "handler_expression": item.get("handler_expression"),
             "modifiers": item.get("modifiers")}
            for item in (ssm.get("template") or {}).get("event_bindings", [])
            if isinstance(item, dict) and item.get("event_name")
        ]
        return (
            "Repair ONLY these two remaining static error families in this standalone San "
            "file: invalid_san_event_handler_syntax and "
            "invalid_san_computed_instance_method_call. Return the COMPLETE .san file "
            "without a Markdown fence or explanation. Preserve the existing DOM, CSS, "
            "component registration, prop initialization, lifecycle, and all unrelated behavior.\n"
            "1. Replace only the reported empty on-* binding with a nonempty San handler. "
            "For a Vue modifier-only event, express the modifier in the San event value "
            "and use a named no-op method when no business handler exists. Do not add "
            "business side effects or change neighboring event bindings.\n"
            "2. San computed callbacks cannot call component instance methods through "
            "this. Extract the existing pure calculation into a script-level helper with "
            "the same logic, call that helper from computed, and retain a delegating "
            "component method for other callers. Preserve all edge cases.\n"
            "3. Do not rename, wrap, remove, or relocate any other on-* binding or "
            "handler, including modal overlay and close-button events. A different "
            "handler name is not evidence of equivalent event behavior.\n"
            f"Additional instruction: {prompt_input.extra_instruction.strip() or 'Preserve source behavior.'}\n"
            f"Validation errors:\n{self._to_json(self._compact_issues(prompt_input.validation_errors))}\n"
            f"Source methods:\n{self._to_json(methods)}\n"
            f"Source event bindings:\n{self._to_json(events)}\n"
            f"Current San code:\n{(prompt_input.current_code or '').strip()}\n"
        )

    def _build_inline_init_computed_lifecycle_prompt(
        self, prompt_input: RepairPromptInput
    ) -> str:
        """Constrain five residuals to first-prop, computed, binding, and hook semantics."""
        ssm = prompt_input.ssm if isinstance(prompt_input.ssm, dict) else {}
        options = (ssm.get("script") or {}).get("options") or {}
        error_text = " ".join(
            str(item.get("message", "")) for item in prompt_input.validation_errors
            if isinstance(item, dict)
        )
        methods = [
            {"name": item.get("name"), "body": item.get("body_full") or item.get("body")}
            for item in (options.get("methods", []) if isinstance(options, dict) else [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
            and re.search(rf"\b{re.escape(item['name'])}\b", error_text)
        ]
        lifecycle = [
            {"vue_hook": item.get("vue_hook"), "san_hook": item.get("san_hook"),
             "body": item.get("body")}
            for item in (options.get("lifecycle_hooks", []) if isinstance(options, dict) else [])
            if isinstance(item, dict) and item.get("vue_hook") in {"mounted", "beforeDestroy"}
        ]
        children = []
        component_models = (
            (options.get("components", []) if isinstance(options, dict) else []) or []
        ) + (ssm.get("sub_components", []) or [])
        for item in component_models:
            if not isinstance(item, dict):
                continue
            names = [item.get("source_name"), item.get("registered_name"), item.get("name")]
            if not any(
                isinstance(name, str) and re.search(rf"\b{re.escape(name)}\b", error_text, re.I)
                for name in names
            ):
                continue
            definition = item.get("inline_definition") or {}
            if not isinstance(definition, dict) or not definition.get("source_code"):
                continue
            children.append({
                "source_name": item.get("source_name"),
                "registered_name": item.get("registered_name"),
                "source_code": definition["source_code"],
            })
        return (
            "Repair ONLY these five remaining static error families in the complete San file: "
            "invalid_san_init_data_store_access, missing_inline_prop_dependent_initialization, "
            "invalid_san_computed_instance_method_call, hidden_template_reactive_dependency, "
            "and lifecycle_behavior_not_landed. Return the COMPLETE .san file with no "
            "Markdown fence or explanation. Do not change DOM order, CSS, event bindings, "
            "component registrations, or unrelated methods.\n"
            "1. In every affected inline child, initData() runs before this.data exists: "
            "return only independent default state there. In inited(), copy the already "
            "available prop into derived state before use, then watch the prop for later "
            "changes. The very first prop value must be reflected, not just later updates. "
            "Preserve the source copy/default logic and clone mutable arrays.\n"
            "2. A San computed callback cannot call this.someMethod(). Extract the same "
            "pure calculation into a script-level helper and call it from computed. "
            "Keep a delegating component method for non-computed callers, without changing "
            "date, null, or completed-item edge cases.\n"
            "3. A template-invoked count or formatter method must receive each reactive "
            "field it depends on as an explicit template argument. Use that argument "
            "inside the method; do not hide a this.data.get(...) read of the same field. "
            "Preserve filter branch and count semantics.\n"
            "4. Preserve source lifecycle order: register watches and perform only safe "
            "prop-derived setup in inited(); place source Vue mounted actions in San "
            "attached() in their original order. Keep cleanup in disposed(). Do not "
            "duplicate startup side effects across hooks.\n"
            "5. Do not rename, wrap, remove, or relocate existing on-* bindings or "
            "handlers, including modal overlay, close-button, and drag/drop events. "
            "Do not silence validation or invent alternative source behavior.\n"
            f"Additional instruction: {prompt_input.extra_instruction.strip() or 'Preserve source behavior.'}\n"
            f"Validation errors:\n{self._to_json(self._compact_issues(prompt_input.validation_errors))}\n"
            f"Relevant source methods:\n{self._to_json(methods)}\n"
            f"Source lifecycle hooks:\n{self._to_json(lifecycle)}\n"
            f"Affected inline child definitions:\n{self._to_json(children)}\n"
            f"Current San code:\n{(prompt_input.current_code or '').strip()}\n"
        )

    def _build_inline_init_computed_reactivity_prompt(self, prompt_input: RepairPromptInput) -> str:
        """Constrain the exact four-error first-prop/computed/reactivity residual."""
        ssm = prompt_input.ssm if isinstance(prompt_input.ssm, dict) else {}
        options = (ssm.get("script") or {}).get("options") or {}
        issue_text = " ".join(str(item.get("message") or "") for item in prompt_input.validation_errors)
        children = []
        for item in options.get("components", []) if isinstance(options, dict) else []:
            if not isinstance(item, dict):
                continue
            name = item.get("source_name") or item.get("registered_name")
            inline = item.get("inline_definition") or {}
            if (isinstance(name, str) and name in issue_text
                    and isinstance(inline, dict) and inline.get("source_code")):
                children.append({"name": name, "source_code": inline["source_code"]})
        methods = [
            {"name": item.get("name"), "body": item.get("body_full") or item.get("body")}
            for item in (options.get("methods", []) if isinstance(options, dict) else [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
            and re.search(rf"\b{re.escape(item['name'])}\b", issue_text)
        ]
        return (
            "Repair ONLY these four remaining static error families in the complete San file: "
            "invalid_san_init_data_store_access, missing_inline_prop_dependent_initialization, "
            "invalid_san_computed_instance_method_call, and hidden_template_reactive_dependency. "
            "Return the COMPLETE .san file without a Markdown fence or explanation. "
            "Preserve DOM order, CSS, component registrations, all events (including native "
            "dragstart/dragend, custom drag-start/drag-end and guarded overlay clicks), and "
            "the existing parent lifecycle order. Do not introduce unrelated changes.\n"
            "1. In each affected inline child, initData() must return independent defaults "
            "without reading this.data or props. In inited(), copy the first prop value "
            "into derived state using this.data.get('prop') and this.data.set(...), then "
            "retain a watcher for subsequent prop changes. Preserve source cloning and defaults.\n"
            "2. San computed callbacks must call pure script-level helpers with explicit "
            "arguments, not this.someMethod(...). Retain an equivalent component method "
            "for non-computed callers and preserve edge-case semantics.\n"
            "3. A template-invoked method must receive any reactive state dependency as an "
            "explicit template argument. Use that argument inside the method; preserve all "
            "filter branches, count behavior and event bindings.\n"
            "Do not silence validation by deleting a prop, method, watcher or template "
            "binding, and do not move mounted behavior into inited().\n"
            f"Additional instruction: {prompt_input.extra_instruction.strip() or 'Preserve source behavior.'}\n"
            f"Validation errors:\n{self._to_json(self._compact_issues(prompt_input.validation_errors))}\n"
            f"Relevant source children:\n{self._to_json(children)}\n"
            f"Relevant source methods:\n{self._to_json(methods)}\n"
            f"Current San code:\n{(prompt_input.current_code or '').strip()}\n"
        )

    def _build_event_residual_prompt(self, prompt_input: RepairPromptInput) -> str:
        """Repair event contracts with exact source expressions and method bodies."""
        ssm = prompt_input.ssm if isinstance(prompt_input.ssm, dict) else {}
        template_model = ssm.get("template", {})
        bindings = template_model.get("event_bindings", []) if isinstance(template_model, dict) else []
        source_events = [
            {
                "event_name": item.get("event_name"),
                "handler_expression": item.get("handler_expression"),
                "arguments": item.get("arguments", []),
            }
            for item in bindings if isinstance(item, dict) and item.get("handler_expression")
        ][:80]
        event_names = {
            expression.split("(", 1)[0]
            for item in source_events
            if isinstance(expression := item["handler_expression"], str)
            and re.fullmatch(r"[A-Za-z_$][\w$]*(?:\(.*\))?", expression)
        }
        script_model = ssm.get("script", {})
        options = script_model.get("options", {}) if isinstance(script_model, dict) else {}
        methods = options.get("methods", []) if isinstance(options, dict) else []
        source_methods = [
            {"name": item["name"], "body": item.get("body_full") or item.get("body", "")}
            for item in methods if isinstance(item, dict) and item.get("name") in event_names
        ][:80]
        return (
            "You are repairing ONLY the remaining event contract errors in a standalone San "
            "single-file component. Return the COMPLETE .san file, with no explanation or code fence. "
            "Preserve existing DOM order, text, CSS, state defaults, lifecycle order, array writeback, "
            "inline child contracts, and unrelated behavior.\n"
            "For each source event expression below, locate the corresponding outer-template "
            "San binding and its parent method. Preserve the source method name and argument "
            "expression exactly for callable source handlers. If the current candidate uses a "
            "handle-prefixed alias, compare its body with the full source method body below; "
            "restore the source-named method and update its binding and internal calls only after "
            "preserving the source behavior. A name change alone is NOT proof of equivalence. "
            "Do not introduce duplicate handlers or invent an alias to silence validation.\n"
            "For source assignments such as showSettings = true/false, retain a declared San "
            "handler that performs this.data.set(...); do not put an assignment in on-*. "
            "Preserve child custom-event names and payloads; pass $event explicitly when a "
            "parent method consumes the child payload. Keep source argument expressions such as "
            "on-click=\"choose(item)\" and on-click=\"setMode(option.value)\" "
            "rather than dropping their arguments. Do not change child templates merely to make "
            "a parent name match.\n"
            "Before returning, check every source event against the parent template, script "
            "method declaration, calls, child forwarding, and argument shape. If a source method "
            "is absent, implement its behavior from the source body; do not create a no-op.\n"
            f"Additional instruction: {prompt_input.extra_instruction.strip() or 'Preserve source behavior.'}\n"
            f"Validation errors:\n{self._to_json(self._compact_issues(prompt_input.validation_errors))}\n"
            f"Source event expressions:\n{self._to_json(source_events)}\n"
            f"Source event method bodies:\n{self._to_json(source_methods)}\n"
            f"Current San code:\n{(prompt_input.current_code or '').strip()}\n"
        )

    def _build_semantic_residual_prompt(self, prompt_input: RepairPromptInput) -> str:
        """Focus late repairs on remaining semantic errors without a full SSM dump."""
        template_model = prompt_input.ssm.get("template", {}) if isinstance(prompt_input.ssm, dict) else {}
        event_bindings = template_model.get("event_bindings", []) if isinstance(template_model, dict) else []
        source_events = [
            {
                "event_name": item.get("event_name"),
                "handler_expression": item.get("handler_expression"),
            }
            for item in event_bindings if isinstance(item, dict)
            and item.get("handler_expression")
        ][:80]
        current_code = (prompt_input.current_code or "").strip()
        extra_instruction = prompt_input.extra_instruction.strip()
        return (
            "You are repairing a standalone San single-file component. The current code already "
            "has no reported visual comparison errors, but ALL listed semantic validation errors "
            "must be fixed together. Keep the existing DOM order, text, CSS, component registry, "
            "state defaults, and unrelated behavior unchanged. Return the COMPLETE .san file, "
            "with no explanation or code fence.\n"
            "Do not reintroduce a diagnostic already absent from the current candidate. "
            "For missing dataTypes, declare real source prop schemas on the corresponding "
            "components; an empty dataTypes object is not a substitute for source child props. "
            "Do not add a fictitious parent prop contract when the parent has no props.\n"
            "1. Every on-* value must be a valid San method invocation. Never leave an empty "
            "handler, a direct assignment such as on-click=\"open = true\", or Vue .stop/.prevent "
            "attributes. Add a top-level component method using this.data.set(...) for state "
            "changes. Preserve .self/backdrop-only behavior with a source-matched target/currentTarget guard.\n"
            "When using a backdrop guard wrapper, bind wrapper($event) explicitly and compare "
            "that parameter's target/currentTarget before calling the original close method. "
            "A bare San handler gets default $event, but handler() has no arguments; "
            "never assume the component exposes this.event.\n"
            "For source textarea v-model, use value=\"{= assignable.path =}\" and an empty textarea body. "
            "Never put {= path =} in textarea text; do not erase real literal user-facing content.\n"
            "2. Compare each source event expression below with the corresponding San binding. "
            "Keep callable source handler names AND every argument unchanged when the source "
            "expression is valid; do not add a handle- prefix or rename handlers throughout "
            "the component merely to rewrite code. A source assignment is not a callable "
            "handler and must become a named method without dropping the event. "
            "For a key modifier such as on-keyup.enter, use San's value modifier "
            "on-keyup=\"enter:addComment\" or an equivalent declared key-guard handler. "
            "In an inline child, preserve fire(...) event forwarding and its payload; "
            "if a forwarding method is needed, declare it in that child. "
            "For example, on-click=\"choose(item.id)\" must not become "
            "on-click=\"choose\". Pass $event explicitly to a parent method that consumes "
            "a child custom-event payload. San this.fire(name, payload) carries ONE payload; "
            "encode multiple values as an object and unpack them in the parent.\n"
            "Do not replace source arguments with data-* attributes, getAttribute(), JSON "
            "round-trips or this.event. Restore the binding AND the method parameters together: "
            "on-click=\"choose(item)\" requires choose(item), not choose() reading this.event.\n"
            "A native/custom click event does not imply an index field. If the source passes a loop item, "
            "preserve that item binding and the matching method parameter together; do not read $event.index "
            "unless the child actually emits that documented payload.\n"
            "3. San initData runs before this.data exists. Return stable default values there; "
            "copy prop-derived state in inited() with this.data.get/set. Every this.watch(path, "
            "listener) listener must be a function, not a Vue descriptor object.\n"
            "4. San computed callbacks cannot call this.calculatePoint(), this.checkStatus(), or any other "
            "component instance method. Move shared math to pure helper functions and pass "
            "reactive inputs explicitly. Preserve chart coordinates and empty-data behavior. "
            "A parameterized formatter called in an inline child template must be a top-level "
            "child method, not a computed value invoked as a method. "
            "If a computed returns a function such as width() { return n => 800/n-4; }, "
            "make it a child method width(n) { return 800/n-4; } and preserve all call arguments. "
            "Never call Math directly inside an inline child template; move the calculation to a child method with "
            "explicit reactive arguments.\n"
            "5. If a template calls a method for class, text, style, or geometry and that method "
            "reads additional this.data.get(...) fields, add those reactive fields to the template "
            "call arguments and update the method signature together. Do not merely suppress the "
            "validator or change one side of the call.\n"
            "6. Never mutate an object or array retrieved from this.data.get(...) in place. "
            "Create a new object or array and write it back with this.data.set(...), preserving "
            "the original operation's ordering and side effects.\n"
            "7. Preserve every source lifecycle action: move Vue initialization and method calls "
            "to the corresponding San inited()/attached() hook and timer cleanup to disposed(). "
            "Keep actions from a Vue mounted() hook in the same order in San attached(), "
            "unless a specific data-only initialization must run in inited() and its timing "
            "change is justified. Do not replace those actions with empty lifecycle hooks.\n"
            "Preserve watcher side effects as well as their registration, including source persistence writes. "
            "A renamed current-value parameter or an unused old-value parameter does not remove the source "
            "persistence obligation. Use the target listener's current-value binding in JSON.stringify; "
            "preserve its existing parameters, conditions and effect order. Do not add duplicate storage "
            "writes or move persistence into a new UI/lifecycle trigger. If scope/effect equivalence is "
            "unproven, address the reported watcher contract from source evidence, not a guessed blanket write. "
            "A source_watch_persistence_unproven diagnostic means a possible write already exists; "
            "it is not permission to append another write. Compare normal and throwing storage behavior; "
            "do not silently remove try/catch or declare exception-policy differences equivalent. "
            "Do not start timers in inited() merely to satisfy startup checks, or run initialization twice. "
            "If a source initializer runs once in mounted(), its San alias must run once in attached(): "
            "move a proven misplaced call out of inited(), do not merely append another call in attached(). "
            "Preserve watcher registrations and unrelated methods; unknown lifecycle effects require review.\n"
            "Before responding, inspect the parent AND every inline child for each reported error "
            "and verify that source event arguments remain present.\n"
            f"Additional instruction: {extra_instruction or 'Preserve source behavior.'}\n"
            f"Validation errors:\n{self._to_json(self._compact_issues(prompt_input.validation_errors))}\n"
            f"Source event expressions:\n{self._to_json(source_events)}\n"
            f"Source event method bodies:\n{self._to_json(self._source_event_method_bodies(prompt_input))}\n"
            f"Source prop contracts:\n{self._to_json(residual_semantics(current_code, prompt_input.ssm)['source_prop_contracts'])}\n"
            f"Source lifecycle actions and called methods:\n{self._to_json(self._source_lifecycle_evidence(prompt_input))}\n"
            f"Reported source method interface bodies:\n{self._to_json(self._source_interface_evidence(prompt_input))}\n"
            f"Current San code:\n{current_code}\n"
        )

    @staticmethod
    def _source_interface_evidence(prompt_input: RepairPromptInput) -> list[dict[str, Any]]:
        names = {i.get('location', '').removeprefix('script.methods.') for i in prompt_input.validation_errors
                 if i.get('code') in {'source_method_interface_not_landed', 'source_method_trigger_added'}}
        methods = (((prompt_input.ssm or {}).get('script') or {}).get('options') or {}).get('methods') or []
        return [{k:m.get(k) for k in ('name','params','body_full','body','is_async')}
                for m in methods if isinstance(m,dict) and m.get('name') in names]

    @staticmethod
    def _source_lifecycle_evidence(prompt_input: RepairPromptInput) -> dict[str, Any]:
        options = ((prompt_input.ssm or {}).get("script") or {}).get("options") or {}
        hooks = options.get("lifecycle_hooks") or []
        methods = {m.get("name"): m for m in options.get("methods", []) if isinstance(m, dict)}
        pending = [name for hook in hooks if isinstance(hook, dict)
                   for name in re.findall(r"\bthis\.([A-Za-z_$][\w$]*)\s*\(", hook.get("body") or "")]
        selected = {}
        while pending:
            name = pending.pop(0)
            if name in selected or name not in methods:
                continue
            method = methods[name]
            body = method.get("body_full") or method.get("body") or ""
            selected[name] = {"name": name, "params": method.get("params"), "body": body}
            pending.extend(re.findall(r"\bthis\.([A-Za-z_$][\w$]*)\s*\(", body))
        return {"hooks": hooks, "methods": list(selected.values()),
                "boundary": "Preserve source hook timing and call order; loading settings in inited instead of attached may change watcher and startup behavior."}

    @staticmethod
    def _source_event_method_bodies(prompt_input: RepairPromptInput) -> list[dict[str, Any]]:
        ssm = prompt_input.ssm or {}
        bindings = (ssm.get("template") or {}).get("event_bindings") or []
        names = {str(item.get("handler_name") or (item.get("handler_expression") or "").split("(", 1)[0]).strip()
                 for item in bindings if isinstance(item, dict)}
        methods = ((ssm.get("script") or {}).get("options") or {}).get("methods") or []
        return [{"name": m.get("name"), "params": m.get("params"), "body": m.get("body_full") or m.get("body")}
                for m in methods if isinstance(m, dict) and m.get("name") in names]

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
                **({"details": issue["details"]} if issue.get("details") else {}),
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
            "components_to_define_and_register": self._component_contracts(options),
            "reserved_san_method_collisions": sorted(
                set(self._names_from_items(options.get("methods", []), ("name",)))
                & {"initData"}
            ),
            "event_handlers_to_define_and_bind": self._event_handlers(ssm),
            "required_san_patterns": [
                "dataTypes: { ... } for props",
                "initData() { return { ... } } for defaults",
                "never destructure this.data; read each field with this.data.get('field')",
                "all Vue data() initial values preserved exactly, including nested objects, arrays, numbers, and enabled-item collections",
                "inited() with this.data.get('propName') and this.data.set(...) when data depends on props",
                "created/mounted/beforeDestroy/destroyed lifecycle behavior preserved in inited/attached/disposed, including initialization, method calls, and timer cleanup",
                "Vue watchers registered by calling this.watch(...) directly inside San inited() or attached()",
                "every inline Vue subcomponent migrated from inline_definition.source_code to a defined local san.defineComponent identifier and registered under its source tag",
                "standalone San output imports only require('san'); no require('./Child') or other external module",
                "Vue business method initData renamed to avoid collision with San initData, with mounted call sites preserved in attached",
                "DOM child order preserved exactly, especially input/checkbox relative to adjacent text, percent signs, and buttons",
                "computed values must be read with this.data.get('computedName') from methods and other computed functions",
                "nested objects and arrays from this.data.get(...) or computed values are updated immutably and written back with this.data.set(...) instead of property assignment or push/splice",
                "two-way binding only for native form assignable paths originating from Vue v-model; Vue :prop and ordinary custom-component props remain one-way {{ ... }} bindings",
                "disabled/checked/selected use one-way {{ ... }} interpolation, never {= ... =}",
                "Vue object-style :class bindings are converted to San string expressions using ternaries and concatenation",
                "each template element has exactly one class attribute, with static and dynamic classes merged",
                "critical value/checked/selected/disabled expressions remain attached to the same source element and never absorb conditions from adjacent elements",
                "reactive values used by class/style/checked/selected/disabled/s-if/s-for/text method calls must appear in the template expression or be passed explicitly as method arguments",
                "inline child render expressions call top-level child methods with explicit reactive receiver and arguments instead of member methods",
                "every loop item/index alias referenced by a loop element is declared in s-for, for example phase, index in phases",
                "all interpolation delimiters are balanced and Vue v-for :key is migrated as an inline s-for trackby clause, never a separate key or trackby attribute",
                "San s-if/s-else-if/s-for directive values use raw expressions without {{ ... }} or {= ... =} wrappers",
                "top-level handler methods in the parent and every inline child san.defineComponent",
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
                "this.data.map(...), this.data.length, or other array operations directly on the San data store, including inline children",
                "this.getX(...) or any other component instance method call inside a San computed callback",
                "on-mouseenter=\"hoveredIndex = index\" or other state assignments in inline child event bindings",
                "Math.abs(...) directly in an inline San template, or style=\"{{ { backgroundColor: color } }}\" Vue object style binding",
                "member calls such as collection.includes(item) or entry.label.toUpperCase() inside inline child render interpolation",
                "direct property assignment or mutating array methods on values returned by this.data.get(...) or computed state",
                "empty lifecycle hooks that omit source initialization, method calls, or timer cleanup",
                "Vue watch: {...} option or an uncalled top-level watch() method that hides this.watch(...) outside inited()/attached()",
                "undefined identifiers in the components registry",
                "require('./Child') or any other external require in the standalone San output",
                "a Vue business initData method overwriting or being confused with San's initData state factory",
                "reordered DOM children hidden by CSS order or flex layout",
                "{= methodCall(...) =} or other two-way binding to a derived expression",
                "disabled=\"{= expression =}\", checked=\"{= expression =}\", or selected=\"{= expression =}\"",
                "class=\"{{{ selected: condition }}}\" or any other Vue object literal inside a San class interpolation",
                "duplicate class attributes on the same template element",
                "template presentation methods that hide reactive this.data.get(...) dependencies",
                "references to index, idx, $index, or a Vue v-for index alias that is not declared by the corresponding s-for",
                "unbalanced interpolation delimiters or a separate key attribute on an s-for element",
                "s-if=\"{{showSettings}}\", s-if=\"{= showSettings =}\", or s-for=\"{{item in items}}\"",
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

    def _component_contracts(self, options: dict[str, Any]) -> list[dict[str, Any]]:
        result = []
        for item in options.get("components", []) if isinstance(options, dict) else []:
            if not isinstance(item, dict):
                continue
            result.append({
                "registered_name": item.get("registered_name", ""),
                "source_name": item.get("source_name", ""),
                "definition_location": item.get("definition_location", "unknown"),
                "inline_definition": item.get("inline_definition"),
            })
        return result

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
