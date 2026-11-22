import json
from typing import Any

CLASS_BINDING_RULE = (
    "Object-style Vue :class bindings must be converted to a San string expression. "
    "Each template element must have exactly one class attribute; merge static and dynamic classes. "
    "Class binding contract (parent AND every inline child): use one class attribute per element. "
    "Convert every literal-key Vue :class object entry to its complete conditional string, "
    "preserving all keys, conditions, dependencies and static classes. For example "
    "class=\"task-manager {{ isDarkMode ? 'dark-theme' : '' }} {{ isCompactMode ? 'compact-mode' : '' }}\". "
    "Never emit class=\"base {{ 'dark-theme': isDarkMode, 'compact-mode': isCompactMode }}\" "
    "or class=\"{{ { active: flag } }}\" or class=\"{{{ selected: condition }}}\" triple-brace object syntax. San may accept only a literal "
    "prefix without reporting a compile error; compile success is not full-expression or behavior proof. "
    "Do not replace conditions with always-on class tokens. Do not guess dynamic keys, spreads or "
    "unmapped source scopes; keep unsupported cases explicit for review.\n"
)

def _build_generation_prompt(ssm: dict[str, Any], extra_instruction: str = "") -> str:
    ssm_json = json.dumps(ssm, ensure_ascii=False, indent=2)
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
    class_attribute_rule = (
        "Each template element must have exactly one class attribute: merge static and dynamic classes "
        "into that single attribute instead of emitting duplicate class attributes.\n"
    )
    directive_rule = (
        "San s-if/s-else-if/s-for directive values use raw expressions: "
        "s-if=\"showSettings\" and s-for=\"item in items trackby item.id\". "
        "Never use s-if=\"{{showSettings}}\", s-if=\"{= showSettings =}\", "
        "or s-for=\"{{item in items}}\".\n"
    )
    watch_rule = (
        "Register Vue watchers by calling this.watch(...) directly inside San inited() or attached(). "
        "Never hide this.watch(...) inside an uncalled top-level watch() method. "
        "San this.watch(path, listener) needs a FUNCTION listener; never pass a Vue object "
        "descriptor such as {handler() {}, immediate: true, deep: true} directly. Preserve its "
        "immediate/deep behavior explicitly rather than dropping it.\n"
    )
    component_rule = (
        "Every component in script.options.components must have a defined JavaScript identifier before "
        "the parent san.defineComponent call. For an inline Vue component, migrate its complete "
        "inline_definition.source_code to const SourceName = san.defineComponent({...}) and register "
        "that exact identifier; never invent an undefined camelCase replacement. A hyphenated "
        "custom-element name is a quoted registry KEY, not a JavaScript variable: write "
        "const StatCard = san.defineComponent({...}) and components: {'stat-card': StatCard}, "
        "never const stat-card. Explicitly pass a child custom-event payload with $event in the "
        "parent handler binding when needed; keep modal-content clicks from closing a backdrop-only modal. "
        "This is a standalone .san file: do not use require('./Child') or any other external require.\n"
    )
    reserved_method_rule = (
        "If a Vue business method is named initData, rename that business method in San because "
        "initData is San's state factory. Update every call to the renamed method and preserve mounted "
        "calls inside attached(), not in inited().\n"
    )
    return CLASS_BINDING_RULE + data_access_rule + class_attribute_rule + directive_rule + watch_rule + component_rule + reserved_method_rule + (
        "请仅基于给定 SSM 生成可运行、可直接落盘的 San 单文件组件代码。\n"
        "输出要求：\n"
        "1. 直接输出完整 .san 文件内容，必须包含 <template>、<script>、<style> 三段，不要输出解释或 Markdown 代码围栏。\n"
        "2. <script> 必须包含 const san = require('san')、const DataTypes = san.DataTypes，并使用 module.exports = san.defineComponent(...) 导出。\n"
        "3. 必须输出来自 metadata.component_name 的 name。Vue props 必须迁移为 dataTypes，并使用标准 DataTypes 类型，禁止保留 props 或 propTypes。\n"
        "4. initData 必须精确保留 Vue props default 和 data() 的类型、数值、嵌套对象与数组内容；依赖 props 的内部状态应在 inited/attached 中通过 this.data.get/set 同步。\n"
        "5. 状态和 computed 必须通过 this.data.get/set 访问；禁止 this.props、this.computed.foo()、this.xxx 状态访问以及直接修改嵌套对象或数组。更新嵌套状态时创建新值并写回根字段。\n"
        "6. 父组件以及每一个内联子组件的 methods 都必须直接定义在各自 san.defineComponent 对象顶层，任何组件中都禁止保留 Vue 的 methods: {} 包裹。Vue this.$emit(...) 或 emitEvent 包装调用必须迁移为 this.fire(...)，禁止用 this.dispatch(...) 代替自定义事件。\n"
        "7. template 使用 San 的 on-*、s-if、s-for 语法，完整保留 DOM 结构、文本、class、子节点顺序以及方法调用的全部参数。事件参数不得丢失或改用 data-args/getAttribute 绕行。\n"
        "8. Vue v-for 的循环项和索引别名必须完整迁移；:key 必须写入 s-for 的 trackby 子句，例如 s-for=\"task in tasks trackby task.id\"，禁止独立 key 属性，也禁止写成独立 trackby=\"task.id\" 属性。\n"
        "9. {= assignable.path =} 只用于源 Vue v-model 对应的原生 input/select/textarea 可赋值路径；Vue :prop 和普通自定义组件 props 必须使用 {{ ... }} 单向插值，例如 value=\"{{ stat.value }}\"。方法、computed、disabled、checked、selected 等派生表达式也使用 {{ ... }}，例如 disabled=\"{{ expression }}\"，禁止 disabled=\"{= expression =}\"。所有插值必须完整闭合。\n"
        "10. value、checked、selected、disabled 等关键属性必须逐元素保留 Vue 原表达式，禁止把相邻或同级元素的条件合并进来。例如 select 的 :disabled=\"previewMode\" 必须迁移为 disabled=\"{{ previewMode }}\"，不能误用旁边按钮的 !canConnect || previewMode。\n"
        "11. class、style、checked、selected、disabled、s-if、s-for 和文本插值调用普通方法时，响应式依赖必须出现在模板表达式中或作为参数显式传入。必须保留 SSM/Vue 表达式中的完整参数，例如 s-if=\"isOpen(module.id, openIds)\"、s-for=\"lesson in visibleLessons(module.lessons, completedIds, unfinishedOnly) trackby lesson.id\"。\n"
        "12. 完整迁移 created/mounted/beforeDestroy/destroyed 和 watch 行为；必须把 this.watch(...) 直接放入 San inited() 或 attached()，禁止放进未被生命周期调用的普通 watch() 方法，也不能保留空钩子。\n"
        "13. 复用 style_model 中的 class、selector 和 css_rules；使用 <style>，禁止 <style scoped>。不要重新设计组件或编造业务逻辑。\n\n"
        f"补充要求：{extra_instruction or '保持完整 SFC、显式 DataTypes、原始样式和可直接运行的 San 代码。'}\n\n"
        "--- SSM ---\n"
        f"{ssm_json}"
    )
