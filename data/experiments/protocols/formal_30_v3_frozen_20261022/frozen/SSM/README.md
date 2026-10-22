# SSM 提取链路说明

## 目标

SSM（San Source Model）用于把 Vue 组件提取为结构化中间表示，供后续大模型生成等价 San 组件使用。

当前实现采用“两层架构”：

- **Node AST 层**：负责调用 Vue / Babel 官方解析器，尽可能基于真实 AST 提取结构。
- **Python 组装层**：负责消费 AST 结果或回退结果，统一生成 SSM。

---

## 整体链路

输入一个 `.vue` 文件后，提取流程如下：

1. `SSM/extractors/extract.py`
   - 命令行入口
   - 接收单文件、目录或 stdin 输入

2. `SSM/extractors/factory.py`
   - 总协调器
   - 串联 parser、template/script/style extractor、relation builder
   - 输出最终 SSM JSON / dict

3. `SSM/extractors/vue_parser.py`
   - 先尝试调用 `parse_sfc.cjs`
   - 若 Node 或 npm 依赖不可用，则自动回退到 Python 正则切分
   - 负责统一返回 `template / script / style` 三块内容和可选 `analysis`

4. `SSM/extractors/parse_sfc.cjs`
   - Node 侧 AST bridge
   - 使用以下依赖进行真实 AST 解析：
     - `@vue/compiler-sfc`
     - `@vue/compiler-dom`
     - `@babel/parser`
     - `@babel/traverse`
   - 输出结构化 JSON，供 Python 侧消费

5. `SSM/extractors/template_extractor.py`
   - 优先消费 Node 侧模板 AST 分析结果
   - 否则回退到 HTMLParser + 启发式解析
   - 产出：
     - `dom_tree`
     - `component_refs`
     - `slot_distribution`
     - `directives_registry`
     - `event_bindings`

6. `SSM/extractors/script_extractor.py`
   - 优先消费 Node 侧 Babel AST 分析结果
   - 否则回退到 Python 正则/启发式提取
   - 产出：
     - `props`
     - `data`
     - `computed`
     - `watch`
     - `methods`
     - `lifecycle_hooks`
     - `imports`
     - `top_level_declarations`

7. `SSM/extractors/style_extractor.py`
   - 提取 style block
   - 分析 CSS rules / variables / layout features
   - 补充模板中的静态类名、动态类名、动态 style 绑定

8. `SSM/extractors/relation_builder.py`
   - 负责跨块关联分析
   - 构建：
     - `binding_graph`
     - `event_model`
     - `style_model`
     - `sub_components`
     - `migration_hints`

---

## 当前优先级策略

### 1. AST 驱动优先

当本地已安装以下依赖时：

- `@vue/compiler-sfc`
- `@vue/compiler-dom`
- `@babel/parser`
- `@babel/traverse`

`vue_parser.py` 会优先调用 `parse_sfc.cjs`，走真实 AST 提取链路。

### 2. 回退机制

如果出现以下任一情况：

- Node 不可用
- npm 依赖缺失
- bridge 执行失败
- JSON 解析失败

则自动回退到 Python 侧启发式提取逻辑，保证工具仍可运行。

---

## 文件职责

### `SSM/extractors/parse_sfc.cjs`

唯一的 Node 侧 AST bridge。

职责：

- 解析 Vue SFC descriptor
- 解析 template AST
- 解析 script AST
- 产出中间 `analysis.template` 和 `analysis.script`

它**不直接生成最终 SSM**，只负责提供更精确的 AST 分析结果。

### `SSM/extractors/vue_parser.py`

Python 侧 parser 入口。

职责：

- 调用 `parse_sfc.cjs`
- 管理 fallback
- 统一输出三块源码和分析结果

### `SSM/extractors/factory.py`

最终组装器。

职责：

- 决定 template/script 是走 AST 结果还是 fallback 结果
- 调用 relation builder 做跨块分析
- 组装完整 SSM
- 通过 `schema_module` 选择当前使用的 schema 版本

### `SSM/schema/__init__.py`

schema 版本统一入口。

职责：

- 维护 schema 版本到模块路径的映射
- 提供默认 schema 版本
- 提供 `resolve_schema_module()`，支持按版本名、模块路径或模块对象解析 schema

---

## Schema 版本切换

当前默认 schema 版本定义在：

- `SSM/schema/__init__.py`
  - `DEFAULT_SCHEMA_VERSION = "v3"`

版本映射定义在：

- `SSM/schema/__init__.py`
  - `SCHEMA_MODULES = { "v1": "SSM.schema.v1", "v2": "SSM.schema.v2", "v3": "SSM.schema.v3" }`

### 1. 修改默认版本

如果你后续新增了 `SSM/schema/v4.py`，并希望整个提取链路默认切到 `v4`，只需要：

1. 在 `SCHEMA_MODULES` 中注册新版本
2. 修改 `DEFAULT_SCHEMA_VERSION`

示例：

```python
SCHEMA_MODULES = {
    "v1": "SSM.schema.v1",
    "v2": "SSM.schema.v2",
    "v3": "SSM.schema.v3",
    "v4": "SSM.schema.v4",
}

DEFAULT_SCHEMA_VERSION = "v4"
```

### 2. 单次指定 schema 版本

在代码里可以直接切换：

```python
from SSM.extractors import SSMFactory

factory = SSMFactory(schema_module="v3")
ssm = factory.build_from_file("path/to/component.vue")
```

这里的 `schema_module` 支持三种形式：

- 版本名：`"v3"`
- 完整模块路径：`"SSM.schema.v3"`
- 已导入的模块对象

### 3. 使用顶层便捷函数切换版本

```python
from SSM.extractors import build_ssm

ssm = build_ssm(
    "path/to/component.vue",
    is_path=True,
    schema_module="v3",
)
```

### 4. 当前默认行为

如果你不显式传 `schema_module`：

- `SSMFactory()` 会自动使用 `SSM/schema/__init__.py` 里的默认版本
- `build_ssm(...)` 也会自动使用默认版本

### 5. 注意事项

目前 schema 切换入口已经统一，但要真正“可切换可运行”，目标 schema 模块需要提供与当前 extractor 约定一致的接口，至少包括：

- `SSM_SCHEMA_VERSION`
- `SSM_SCHEMA_NAME`
- `build_ssm_metadata(...)`
- `build_san_generation_contract()`
- `build_ssm_shell()`

否则 `SSM/extractors/factory.py` 会在初始化时校验失败。

---

## 运行方式

### 语法检查

```bash
npm run check:ssm
```

用途：检查 `SSM/extractors` 和 `SSM/schema` 下 Python 文件是否存在语法错误。

### 提取单文件

```bash
npm run extract:ssm -- path/to/component.vue
```

### 提取目录

```bash
npm run extract:ssm -- --dir path/to/components --output-dir tmp/ssm
```

### 从 stdin 提取

```bash
cat component.vue | npm run extract:ssm -- --stdin
```

---

## 依赖安装

如需启用真实 AST 驱动链路，请安装：

```bash
npm install
```

当前 `package.json` 已包含：

- `@vue/compiler-sfc`
- `@vue/compiler-dom`
- `@babel/parser`
- `@babel/traverse`

---

## 输出结构示例

一个典型的 SSM 输出顶层结构如下：

```json
{
  "schema_version": "3.0",
  "schema_name": "San Source Model (Generic)",
  "metadata": {
    "component_name": "TodoList",
    "source_file": "components/TodoList.vue",
    "source_framework": "Vue",
    "target_framework": "San",
    "sfc_blocks": {
      "has_template": true,
      "has_script": true,
      "has_style": true,
      "style_scoped": true,
      "style_lang": "css"
    }
  },
  "template": {
    "dom_tree": {},
    "component_refs": [],
    "slot_distribution": [],
    "directives_registry": [],
    "event_bindings": []
  },
  "script": {
    "export_info": {},
    "options": {},
    "imports": [],
    "top_level_declarations": []
  },
  "styles": {
    "style_blocks": [],
    "css_rules": [],
    "css_variables": [],
    "layout_features_inferred": [],
    "static_classes": [],
    "dynamic_class_bindings": [],
    "dynamic_style_bindings": []
  },
  "binding_graph": {
    "nodes": [],
    "edges": [],
    "data_fields_usage": []
  },
  "event_model": {
    "dom_events": [],
    "custom_events": []
  },
  "style_model": {},
  "sub_components": [],
  "migration_hints": {},
  "san_generation_contract": {}
}
```

### 关键字段说明

- `metadata`：组件元信息与 SFC block 状态
- `template.dom_tree`：模板结构树，是后续还原 SAN 模板层级的基础
- `template.component_refs`：子组件引用列表，用于父子组件通信和注册映射
- `script.options`：Vue options API 的核心结构抽取结果
- `styles.style_blocks`：原始 style block 列表
- `binding_graph`：数据字段、模板节点、方法之间的依赖关系图
- `event_model`：DOM 事件与自定义事件模型
- `style_model`：模板绑定与 CSS 规则关联后的视觉语义模型
- `migration_hints`：自动推断出的 Vue → San 迁移提示

---

## 调试与排错

### 1. 判断当前是否走 AST 链路

如果已安装依赖且 `parse_sfc.cjs` 可用，则 `vue_parser.py` 会优先使用 Node AST bridge。

常见判断方法：

- 提取结果更完整，尤其是 `component_refs`、`methods`、`lifecycle_hooks` 会更稳定
- 若 AST 依赖缺失，会自动回退，不会直接报错退出

### 2. 单独测试 Node bridge

可以直接运行：

```bash
node SSM/extractors/parse_sfc.cjs < component.vue
```

如果依赖缺失，会返回：

```json
{
  "error": "missing_dependencies",
  "missing": {
    "compilerSfc": true,
    "compilerDom": true,
    "babelParser": true,
    "babelTraverse": true
  }
}
```

### 3. 常见问题

**问题：`npm run extract:ssm` 能跑，但结果像是回退版，不够精确**
- 原因：AST 依赖未安装，或 Node bridge 不可用
- 处理：执行 `npm install`

**问题：`component_refs` 为空**
- 原因：当前可能走的是启发式路径，或者模板中组件标签不符合预期
- 处理：先确认 AST 依赖是否安装，再检查模板中的子组件标签命名

**问题：`reads_inferred` / `writes_inferred` 不够准确**
- 原因：当前版本仍在从“启发式 + 部分 AST 驱动”继续演进
- 处理：优先确保走 AST 路径；复杂表达式场景仍需继续增强

**问题：Node 命令报 `package.json` 解析错误**
- 原因：根目录 `package.json` 格式非法或为空
- 处理：先修复 `package.json`，再执行 Node 侧 bridge

### 4. 推荐调试顺序

1. 先跑 `npm run check:ssm`
2. 再跑单文件提取：

```bash
npm run extract:ssm -- path/to/component.vue
```

3. 如果怀疑 AST 没启用，再单独测试：

```bash
node SSM/extractors/parse_sfc.cjs < path/to/component.vue
```

---

## 当前实现说明

当前版本已经支持：

- 基础 SFC 拆分
- 模板结构提取
- script 选项提取
- 样式规则提取
- 跨块依赖与事件模型构建
- AST 优先、启发式回退
- Node AST bridge 与 Python fallback 双通路

当前仍在持续优化的方向：

- 更完整的 template AST 覆盖
- 更精准的 script 读写分析
- 更强的自定义事件 payload 推断
- 更稳的子组件注册与引用配对
- 更准确的 scoped slot / 复杂指令处理
