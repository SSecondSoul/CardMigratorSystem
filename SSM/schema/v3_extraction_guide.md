# SSM Schema v3 自动提取指南

## 目标

基于 `@vue/compiler-sfc` 和 `@babel/parser`，从任意 `.vue` 文件或 Vue SFC 源码中自动提取结构化数据，输出符合 `SSM_SCHEMA v3` 的 JSON/Python dict，作为大模型生成等价 San 组件的依据。

**不依赖任何外部人工标注文件。** 所有字段均从源码 AST/编译产物中提取。

---

## 依赖

```bash
npm install @vue/compiler-sfc @babel/parser @babel/traverse @babel/types postcss
```

---

## 1. SFC 解析入口

```javascript
import { parse, compileTemplate, compileScript } from '@vue/compiler-sfc';
import * as parser from '@babel/parser';
import traverse from '@babel/traverse';

const source = fs.readFileSync('Component.vue', 'utf-8');
const { descriptor } = parse(source);
```

`descriptor` 包含：
- `descriptor.template` — 模板块
- `descriptor.script` / `descriptor.scriptSetup` — 脚本块
- `descriptor.styles` — 样式块数组

---

## 2. 元信息提取 (`metadata`)

| 字段 | 提取方式 |
|------|---------|
| `component_name` | 优先取 `compileScript(descriptor).name`，不存在时取文件名去 `.vue` |
| `source_file` | 文件系统路径 |
| `sfc_blocks.has_template` | `!!descriptor.template` |
| `sfc_blocks.has_script` | `!!(descriptor.script \|\| descriptor.scriptSetup)` |
| `sfc_blocks.has_style` | `descriptor.styles.length > 0` |
| `sfc_blocks.style_scoped` | `descriptor.styles.some(s => s.scoped)` |
| `sfc_blocks.style_lang` | `descriptor.styles[0]?.lang \|\| 'css'` |

---

## 3. 模板 AST 提取 (`template`)

### 3.1 编译模板

```javascript
const { ast } = compileTemplate({
  source: descriptor.template.content,
  filename: 'Component.vue',
  id: 'xxx' // 用于 scoped CSS
});
```

`ast` 类型为 `@vue/compiler-core` 的 `RootNode`。

### 3.2 遍历 AST 收集节点

递归遍历 `ast.children`，识别节点类型：

| AST type | `node_type` |
|----------|------------|
| `NodeTypes.ELEMENT` (type=1) | `element` |
| `NodeTypes.COMPONENT` (type=1, tag 大写/含连字符) | `component` |
| `NodeTypes.TEXT` (type=2) | `text` |
| `NodeTypes.COMMENT` (type=3) | `comment` |
| `NodeTypes.INTERPOLATION` (type=5) | `interpolation` |

**静态属性**：过滤 `node.props` 中 `type === 6 (ATTRIBUTE)` 的项。

**动态属性/指令**：过滤 `node.props` 中 `type === 7 (DIRECTIVE)` 的项。

| directive `name` | 含义 |
|-----------------|------|
| `bind` | `v-bind:` 或 `:` |
| `on` | `v-on:` 或 `@` |
| `if` / `else` / `else-if` | `v-if` 系列 |
| `for` | `v-for` |
| `model` | `v-model` |
| `show` | `v-show` |
| `slot` | `v-slot` |
| `html` | `v-html` |
| `text` | `v-text` |

**表达式提取**：
- `dir.exp` 为 `@vue/compiler-core` 的 `ExpressionNode`
- 使用 `dir.exp.loc.source` 获取原始表达式字符串
- 遍历 `dir.exp` 子树收集 `Identifier` 节点得到 `dependencies`

**事件绑定**：从 `name === 'on'` 的指令提取：
- `arg.content` → `event_name`
- `modifiers` → `modifiers`
- `exp` → `handler_expression`

**文本插值**：`INTERPOLATION` 节点的 `content` 为表达式 AST。

### 3.3 组件引用 (`component_refs`)

遍历 dom_tree，收集 `node_type === 'component'` 的节点：
- `source_tag` = 原始标签名
- `san_tag` = kebabCase(tag)
- `props_bindings` = 该节点的 `dynamic_attrs` + `static_attrs`（排除事件绑定）
- `event_bindings` = 该节点 `event_bindings` 中 `is_component_event = true` 的项
- `slot_contents` = 该节点的 `children`

### 3.4 插槽 (`slot_distribution`)

- `<slot name="xxx">` → 定义插槽，记录 `slot_name` 和 `fallback_content`
- `v-slot:xxx` 或 `#xxx` → 使用插槽，关联到对应组件引用节点
- `slot-scope` / `v-slot` 变量 → 提取到 `scope_bindings`

---

## 4. 脚本 AST 提取 (`script`)

### 4.1 解析脚本

```javascript
const scriptContent = descriptor.script?.content || '';
const babelAst = parser.parse(scriptContent, {
  sourceType: 'module',
  plugins: ['jsx', 'typescript', 'decorators-legacy', 'classProperties']
});
```

### 4.2 提取组件选项对象

遍历 `babelAst.program.body`，查找：
- `ExportDefaultDeclaration` → `export_type = 'default_export'`
- `ExpressionStatement` 且 `left` 为 `module.exports` → `export_type = 'module_exports'`

提取 `declaration` 中的 `ObjectExpression` 作为 `options_ast`。

### 4.3 提取各选项

遍历 `options_ast.properties`，按 `key.name` 分类：

| key | 提取内容 |
|-----|---------|
| `name` | `StringLiteral.value` |
| `components` | 遍历 `ObjectExpression.properties`，每个 property 的 `key.name` 为 registered_name，`value` 为 source_name |
| `props` | 数组语法：提取 `ArrayExpression.elements` 的 StringLiteral；对象语法：提取每个 property 的 key/value |
| `data` | 对象语法：直接提取 properties；函数语法：找到 `ReturnStatement` 中的 `ObjectExpression` 提取 properties |
| `computed` | 提取每个 property，区分 getter/setter（`get`/`set` method 或 `ObjectExpression` 含 `get`/`set`） |
| `watch` | 提取每个 property，识别 `deep`、`immediate`、`handler` |
| `methods` | 提取每个 method/function property |
| `emits` | 数组语法提取字符串；对象语法提取 keys |
| `provide` / `inject` | 提取 keys |
| `filters` | Vue 2 特有，提取每个 property |
| `mixins` / `extends` | 提取引用变量名 |
| 生命周期钩子 | 遍历已知生命周期名称的 keys |

### 4.4 方法体分析

对每个 `methods` 和 `lifecycle_hooks` 中的函数：
- 使用 `babelAst` 遍历函数体 AST
- 识别 `this.xxx` → 记录为 `reads_inferred`
- 识别 `this.xxx = ...` → 记录为 `writes_inferred`
- 识别 `$emit('event', ...)` → 记录为 `emits_inferred`
- 识别 `setInterval`/`setTimeout`/`clearInterval`/`clearTimeout` → 标记 `side_effects_inferred: timer`
- 识别 `localStorage` → 标记 `side_effects_inferred: localStorage`
- 识别 `fetch`/`axios`/`XMLHttpRequest` → 标记 `side_effects_inferred: fetch`

---

## 5. 样式提取 (`styles`)

### 5.1 原始块信息

从 `descriptor.styles` 直接提取：
- `content` / `lang` / `scoped` / `module` / `attrs`

### 5.2 CSS AST 解析

```javascript
import postcss from 'postcss';
const root = postcss.parse(styleContent);
```

遍历 `root.nodes`：
- `type === 'rule'` → 提取 `selectors` 和 `declarations`
- `type === 'atrule'` (media, keyframes) → 标记 `has_media` / `has_keyframes`
- 选择器中包含 `:` → 标记 `has_pseudo`

### 5.3 CSS 变量

正则匹配 `--[\w-]+` 或使用 `postcss` 遍历 `declarations` 提取。

---

## 6. 绑定图构建 (`binding_graph`)

### 6.1 创建节点

从 `script.options` 创建节点：
- `data` 字段 → `kind: data`
- `props` 项 → `kind: prop`
- `computed` 项 → `kind: computed`
- `methods` 项 → `kind: method`
- `external` → `localStorage`, `timer` 等
- 从 `template.dom_tree` 创建 `template_node` 节点

### 6.2 创建边

**模板 → 数据源**：
遍历每个模板节点的 `directives`、`dynamic_attrs`、`text_bindings` 中的 `dependencies`，匹配到 script 中的 data/prop/computed 名，创建 `binds_to` 边。

**方法 → 数据源**：
从 `script.methods` 的 `reads_inferred` 创建 `reads` 边，从 `writes_inferred` 创建 `writes` 边。

**computed → 依赖**：
遍历 computed getter AST 中的 `Identifier`，匹配 data/prop/computed，创建 `depends_on` 边。

**watch → 数据源**：
从 watcher 的 `expression` 创建 `depends_on` 边。

**事件 → 方法**：
从 `event_model.dom_events` 的 `handler_name` 关联到 `script.methods`。

---

## 7. 事件模型构建 (`event_model`)

### 7.1 DOM 事件

从 `template.dom_tree` 收集所有 `event_bindings`，其中 `is_component_event === false`：
- `dom_event_name` = `event_name`
- `handler_name` = 解析 handler_expression 提取的标识符
- 从 `script.methods` 中查找对应方法，填充 `reads`、`writes`、`side_effects`

### 7.2 自定义事件

**子组件 emit**：
遍历 `script.methods`，查找 `$emit('eventName', payload)` 调用：
- `event_name` = 第一个参数字符串
- `emit_points` = 包含该调用的方法名
- `source_component` = 当前组件名

**父组件监听**：
从 `template.component_refs` 的 `event_bindings` 中，收集 `is_component_event === true` 的项：
- `listener_handler` = handler_name
- `target_component` = 当前组件名
- `listener_node_id` = 组件引用的 node_id

将同一 `event_name` 的 emit 和 listen 配对，构建 `custom_events`。

---

## 8. 样式模型构建 (`style_model`)

### 8.1 静态类名

遍历 `template.dom_tree`，收集 `static_attrs.class`，去重后生成 `static_classes`。

### 8.2 动态类名/样式

从 `template.dom_tree` 的 `dynamic_attrs` 中过滤 `target_attr === 'class'` 或 `'style'`：
- `expression_type`：分析 AST 类型（`ObjectExpression` → object, `ArrayExpression` → array, `ConditionalExpression` → ternary, 其他 → string/unknown）
- `possible_classes`：对 object 类型，提取 keys；对 array 类型，提取字符串元素

### 8.3 CSS 规则关联

将 `styles.css_rules` 中的 `related_classes` 与 `static_classes` / `dynamic_class_bindings` 中的类名匹配，建立关联。

### 8.4 布局特征推断

扫描 CSS declarations：
- `display: flex` → `flex`
- `display: grid` → `grid`
- `position: absolute/fixed` → `absolute/fixed`
- `svg` 标签选择器 → `svg`
- `@media` → `responsive`
- `position: fixed/absolute` + `background: rgba` → `modal-overlay`

---

## 9. 子组件提取 (`sub_components`)

从 `script.options.components` 和 `template.component_refs` 交叉分析：

1. **内联子组件**：在 script AST 中查找变量声明，其值为 `ObjectExpression` 且含 `template`/`props`/`data` 等 Vue 选项字段。
2. **导入组件**：从 `script.imports` 匹配 components 中的引用。
3. 对内联子组件，递归执行步骤 3-8，生成摘要。

---

## 10. 迁移提示生成 (`migration_hints`)

完全基于 AST 特征自动推断，不读取外部文件。

遍历 `template.directives_registry` 和 `script.options`，匹配预定义规则（见 `v3.py` 中 `auto_detected_list`），生成 `detected_patterns`。

为每个 data/prop 字段生成 `data_access_conversion_plan`：
- `read_plan` = `this.data.get('fieldName')`
- `write_plan` = `this.data.set('fieldName', value)`（若是 data 字段）
- `init_plan` = 根据 `initialized_from_props` / `initialized_from_external` 生成

---

## 11. 输出格式

提取工具最终输出一个 Python dict / JSON，严格符合 `SSM_SCHEMA v3` 结构。示例：

```python
{
    "schema_version": "3.0",
    "metadata": { ... },
    "template": { "dom_tree": [...], "component_refs": [...], ... },
    "script": { "options": { ... }, "imports": [...], ... },
    "styles": { "style_blocks": [...], "css_rules": [...], ... },
    "binding_graph": { "nodes": [...], "edges": [...], ... },
    "event_model": { "dom_events": [...], "custom_events": [...] },
    "style_model": { ... },
    "sub_components": [...],
    "migration_hints": { "detected_patterns": [...], ... },
    "san_generation_contract": { ... }
}
```

---

## 12. 错误处理与降级

| 场景 | 处理 |
|------|------|
| 模板解析失败 | 记录错误，返回空 `dom_tree`，保留 script/styles |
| 脚本解析失败（如非标准 JS） | 使用正则降级提取 `export default` 块，或标记为 `unknown` |
| 缺少 `script` 块 | `script` 字段置空对象，binding_graph/event_model 为空 |
| 缺少 `template` 块 | `template` 字段置空对象，component_refs 为空 |
| CSS 解析失败 | 保留原始 `content`，`css_rules` 为空数组 |
