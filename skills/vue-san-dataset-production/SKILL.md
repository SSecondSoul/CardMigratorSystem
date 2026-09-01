---
name: vue-san-dataset-production
description: 当用户需要在本仓库中生产、补充、扩展或审查 Vue/San 成对迁移数据集时，务必使用这个 skill。适用于新增组件样本、按 simple/medium/complex 复杂度批量生成 Vue 与 San 对照代码、更新 `data/datasets/dataset_manifest.json`、维护 `data/datasets/features/*` 的场景。该 skill 按 T/D/I/S/C 五维复杂度评分并检查跨样本结构与行为多样性，确保数据结构、文件命名、复杂度标签和清单文件保持一致；暂不处理 `data/datasets/splits/*` 和 `data/datasets/lora/*`。
---

# Vue/San 数据生产 Skill

当用户要求新增或整理 Vue/San 迁移数据时，使用这个 skill。

## 目标

帮助用户按照 `data/datasets` 现有结构生产可用于迁移实验、SSM 提取、LLM 生成和评估的 Vue/San 成对组件数据。

数据生产时要保证：

- Vue 与 San 文件成对存在
- 目录结构符合 `data/datasets/components` 约定
- 复杂度等级符合 T/D/I/S/C 五维评分
- `dataset_manifest.json` 与实际文件同步
- 必要时同步 `features` 相关文件
- 样本能支撑论文中的简单/中等/复杂分层实验
- 同一 Vue/San 组件对保持语义等价，不同组件对具有真实的结构与行为差异

## 核心质量边界

Vue/San 配对内与样本之间采用不同的相似性要求：

- 同一组件对中的 Vue 与 San 必须在数据、DOM 语义、文本、交互、事件和视觉上尽量等价。
- 不同组件对不能只是替换名称、文案、颜色、默认值或领域名词。业务主题不同但状态模型、模板骨架和交互流程相同，仍视为重复样本。
- 复杂度等级表示真实实现复杂度，不能通过机械添加无意义的 `computed`、生命周期、分页、异步方法或子组件来凑分。
- 先设计组件的业务行为与数据模型，再根据实际实现评分；不要先选一个模板，再通过换皮批量复制到同一等级。

## 批量设计门

当一次新增两个或以上样本时，写文件前必须先检查现有数据集，并为整批候选组件建立设计矩阵。至少记录：

| 项目 | 需要明确的内容 |
|------|----------------|
| 数据模型 | 数值、对象、列表、树、分组、时间序列或其他结构 |
| 核心工作流 | 切换、编辑、选择、排序、拖拽、分页、提交或其他流程 |
| 模板结构 | 卡片、表单、列表、主从视图、仪表盘或其他信息架构 |
| 状态变化 | 自增、状态机、派生统计、异步状态、撤销恢复等 |
| 通信方式 | props、emit、输入同步、子组件事件等 |
| 迁移重点 | 指令、动态样式、watch、生命周期、异步、子组件等 |

同批任意两个组件至少要在上表中有两个维度存在实质差异，并且其中至少一个差异来自数据模型、核心工作流或模板结构。仅有主题、文案、颜色和默认数据不同，不满足此要求。

不同复杂度的批次还应满足：

- `simple`：不要全部采用“标题 + 初始数值 + 点击递增”；应覆盖不同的基础状态和单步交互。
- `medium`：不要全部采用“标题 + 初始列表 + 强调色 + 增删筛选”；应覆盖表单、选择、分组、派生计算、列表工作流等不同组合。
- `complex`：不要全部采用“标题 + 负责人 + 刷新间隔 + 记录列表 + 搜索排序分页”；应让信息架构、业务状态和主要逻辑来源不同。

如果候选设计与已有样本或同批样本不满足差异要求，先更换设计，不要开始生成代码。

## 数据目录约定

当前数据集根目录为：

- `data/datasets/`

组件样本放在：

- `data/datasets/components/01_simple/<ComponentName>/`
- `data/datasets/components/02_medium/<ComponentName>/`
- `data/datasets/components/03_complex/<ComponentName>/`

每个组件目录下保持 Vue/San 双目录：

```text
data/datasets/components/<complexity_dir>/<ComponentName>/
  vue/
    <component_file>.vue
  san/
    <component_file>.san
```

示例：

```text
data/datasets/components/01_simple/step/
  vue/step.vue
  san/step.san
```

## 必须更新的文件

新增或调整样本时，优先检查并更新：

- `data/datasets/dataset_manifest.json`
  - 记录组件 ID、名称、路径、复杂度、Vue 文件名、San 文件名、状态等
- `data/datasets/components/<level>/<ComponentName>/vue/<file>.vue`
  - Vue 源组件
- `data/datasets/components/<level>/<ComponentName>/san/<file>.san`
  - 对应 San 参考实现

如果样本需要记录复杂度或特征统计，还要检查：

- `data/datasets/features/complexity_tags.json`
  - 记录复杂度五维分数、总分、等级、特征标签
- `data/datasets/features/pattern_tags.json`
  - 记录语法/模式标签，例如 `v-for`、`v-if`、`props`、`emit`、`dynamic-class`
- `data/datasets/features/migration_notes.json`
  - 记录迁移注意事项、人工修正点、已知难点

暂时不要修改：

- `data/datasets/splits/*/manifest.json`
- `data/datasets/lora/*/dataset.jsonl`

不要只新增 Vue/San 文件而忘记 manifest 和复杂度标签。

## Manifest 记录格式

在 `data/datasets/dataset_manifest.json` 的 `components` 数组中新增一项。

推荐字段：

```json
{
  "id": "component_id",
  "name": "中文组件名",
  "path": "components/01_simple/ComponentName/",
  "complexity": "simple",
  "vue_file": "ComponentName.vue",
  "san_file": "ComponentName.san",
  "created_date": "YYYY-MM-DD",
  "status": "vue_ready,san_ready",
  "notes": ""
}
```

注意：

- `path` 指向组件根目录，不包含 `vue/` 或 `san/`
- 实际文件仍放在 `vue/` 和 `san/` 子目录下
- `complexity` 只能使用：`simple`、`medium`、`complex`
- 新增后同步检查 `total_components` 是否等于 `components` 实际数量

## 复杂度评分维度

每个组件按五个维度评分，每个维度 1-3 分：

| 维度 | 代码要素 | 评估指标 | 权重 |
|------|----------|----------|------|
| T: 模板结构 | `<template>` | 节点数、嵌套深度、指令数量 | 1-3分 |
| D: 数据逻辑 | `data`, `computed`, `methods` | 字段数、计算属性数、方法复杂度 | 1-3分 |
| I: 交互行为 | `@click`, `$emit`, 生命周期 | 事件数、自定义事件、钩子 | 1-3分 |
| S: 样式特征 | `<style>`, `:class` | 类数量、动态类、作用域 | 1-3分 |
| C: 组件通信 | `props`, `$emit`, 子组件 | props数、emit事件、子组件数 | 1-3分 |

总分范围：5-15 分。

## 详细评分标准

### T: 模板结构

评估组件 DOM 结构和指令使用情况。

- 1 分：节点数 ≤ 10；嵌套深度 ≤ 3；指令数 ≤ 2；无 `v-for`/`v-if` 嵌套
- 2 分：节点数 11-30；嵌套深度 4-5；指令数 3-5；有单层 `v-for` 或 `v-if`
- 3 分：节点数 ≥ 31；嵌套深度 ≥ 6；指令数 ≥ 6；存在多层 `v-for`/`v-if` 嵌套

### D: 数据逻辑

评估组件数据管理和业务逻辑复杂度。

- 1 分：`data` 字段 ≤ 3；无 `computed`；`methods` ≤ 2；无异步操作
- 2 分：`data` 字段 4-8；`computed` 1-2 个；`methods` 3-5 个；有简单业务逻辑
- 3 分：`data` 字段 ≥ 9；`computed` ≥ 3；`methods` ≥ 6；有异步或复杂聚合逻辑

### I: 交互行为

评估用户交互和事件处理复杂度。

- 1 分：事件数 ≤ 1；无自定义事件；无生命周期钩子
- 2 分：事件数 2-4；有自定义事件；有 1 个生命周期钩子
- 3 分：事件数 ≥ 5；多级自定义事件；生命周期钩子 ≥ 2 个

### S: 样式特征

评估样式复杂度和动态性。

- 1 分：类名 ≤ 5；无动态类名；无作用域样式
- 2 分：类名 6-15；简单动态类 1-2 个；有 `scoped`
- 3 分：类名 ≥ 16；复杂动态类 ≥ 3 个；有主题切换或复杂动态样式

### C: 组件通信

评估组件与外部组件或父子组件之间的通信复杂度。

- 1 分：`props` ≤ 2；无 `emit`；无子组件
- 2 分：`props` 3-5；`emit` 1-2 个；子组件 ≤ 1 个
- 3 分：`props` ≥ 6；`emit` ≥ 3 个；子组件 ≥ 2 个

## 复杂度分级

根据五维总分分级：

| 等级 | 总分范围 | 特征 | 迁移难度 | 典型组件 |
|------|----------|------|----------|----------|
| 简单 | 5-8分 | 扁平结构、基础数据、少量交互 | 低 | 天气卡片、股票卡片、步数卡片 |
| 中等 | 9-12分 | 嵌套结构、计算属性、多个事件 | 中 | 待办卡片、登录表单、开销追踪器 |
| 复杂 | 13-15分 | 深层嵌套、复杂逻辑、多组件通信 | 高 | 仪表盘、图表卡片、任务管理器 |

同一等级的组件可以总分相近，但复杂度来源应尽量分散。例如一个中等组件可以偏重模板与交互，另一个可以偏重数据逻辑与通信。批量生产时检查 T/D/I/S/C 分布，不要让同等级样本全部使用相同五维分数和 feature 组合。

## 生产 Vue/San 样本时的要求

### Vue 文件要求

Vue 样本应该：

- 使用单文件组件结构，顺序固定为：`<template>`、`<script>`、`<style scoped>`。
- `<script>` 中统一使用 CommonJS 导出：`module.exports = { ... };`，不要使用 `export default`。
- 组件对象中显式包含 `name`，名称使用 PascalCase，例如 `StepCard`、`CountdownCard`。
- `props` 使用 Vue Options API 对象写法，优先写成 `{ type, default }` 结构；需要说明时可在字段上方写简短中文注释。
- `data` 使用 `data() { return { ... }; }`，字段默认值应稳定、可序列化；如依赖 props，可使用 `this.xxx` 初始化。
- `computed`、`watch`、生命周期、`methods` 都使用 Vue 2 Options API 风格，保持与现有样本一致。
- 事件绑定优先使用简写 `@click="handler"`、`@input="handler"`、`@change="handler"`，属性绑定使用 `:class`、`:value`、`:key` 等简写。
- 子组件如果是样本内部定义，优先在 `<script>` 顶部用 `const ChildName = { ... };` 定义，再在主组件 `components` 中注册。
- 模板 class 命名使用短横线风格，例如 `step-card`、`card-header`、`time-display`。
- `<style scoped>` 样式自包含，不依赖外部 CSS；优先保留卡片宽度、间距、圆角、阴影、字体、hover/transition 等视觉特征。
- 能清晰体现目标复杂度等级，并尽量覆盖迁移研究需要的典型语法：
  - `props`
  - `data`
  - `computed`
  - `methods`
  - `watch`
  - 生命周期
  - `v-if`
  - `v-for`
  - `v-bind` / `:`
  - `v-on` / `@`
  - `v-model`
  - `:class`
  - `:style`
  - `$emit`
  - 子组件
- 不引入无法在实验环境中稳定运行的外部依赖。

### San 文件要求

San 参考实现应该：

- 与 Vue 组件在结构、文本、交互、样式上尽量等价。
- 使用完整 `.san` 单文件组件形式，顺序固定为：`<template>`、`<script>`、`<style>`。
- `<script>` 中显式使用：
  - `const san = require('san');`
  - `const DataTypes = san.DataTypes;`
  - `module.exports = san.defineComponent({ ... });`
- 组件对象中显式包含 `name`，与 Vue 组件名保持一致。
- `props` 统一迁移为 `dataTypes`，类型使用 `DataTypes.string`、`DataTypes.number`、`DataTypes.bool`、`DataTypes.array`、`DataTypes.object` 等。
- `data` 统一迁移为 `initData()`，返回稳定默认值。
- 如果 data 字段依赖 props，优先在 `inited()` 中使用 `this.data.set(...)` 同步。
- 事件绑定使用 San 语法，例如 `on-click="handler"`，不要保留 Vue 的 `@click`。
- 状态读写使用 `this.data.get()` / `this.data.set()`，不要使用 `this.xxx` 直接读写状态。
- 方法优先直接定义在 `san.defineComponent` 顶层，不要保留 Vue 风格的 `methods: {}` 包裹。
- Vue 的 `$emit` 迁移为 San 的 `this.fire(...)`。
- 生命周期映射到 San 语义，例如 `mounted` -> `attached`，`beforeDestroy` -> `disposed`。
- San `<style>` 不写 `scoped`，但要完整保留 Vue 样式内容、class 名、布局、颜色、文本和交互视觉效果。

## 重复样本判定

生成每个组件后，忽略组件名称、自然语言文案、颜色、CSS 常量和默认数据，比较它与现有样本及同批样本的以下特征：

1. public props 的名称、类型和职责
2. 模板节点层级、主要区域和指令分布
3. data、computed、watch、methods 与生命周期的组成
4. 核心交互流程和状态转换
5. feature 标签与主要迁移难点

出现以下任一情况时，判定为重复样本并重新设计：

- props 结构、模板骨架和逻辑组成三项同时基本相同。
- 上述五项中有四项基本相同。
- 删除文案、颜色和默认常量后，只剩少量标识符差异。
- 新样本没有带来新的状态模型、交互流程、模板结构或迁移模式，只改变了业务主题。

简单组件代码量较少，允许局部语法相似，但核心状态或交互必须不同。不能为了通过检查而只重命名字段、拆分方法或移动 DOM 节点；重设计必须改变组件的实际语义行为。

## 数据生产步骤

### 1. 盘点现有样本并规划批次

搜索 manifest、组件源码和 features 文件，了解已有组件的数据模型、交互、模板骨架和迁移模式。

批量任务先完成设计矩阵并检查候选之间的差异。单个任务也要与现有样本比较，避免重复已有结构。

### 2. 选择复杂度等级并设计行为

先确定要新增的是：

- `simple`：放入 `components/01_simple/`
- `medium`：放入 `components/02_medium/`
- `complex`：放入 `components/03_complex/`

选择能体现复杂度且与现有样本不同的组件行为，例如：

- 简单：天气卡片、步数卡片、通知卡片、名言卡片
- 中等：待办列表、登录表单、开销追踪、股票卡片
- 复杂：仪表盘、监控面板、任务管理器、分析报表

主题名称只用于表达语义，不能代替数据模型、工作流和模板结构设计。设计确定后，根据实际预期实现估算 T/D/I/S/C；代码完成后再复核评分。

### 3. 创建目录与文件

按结构创建：

```text
data/datasets/components/<level>/<ComponentName>/vue/<file>.vue
data/datasets/components/<level>/<ComponentName>/san/<file>.san
```

### 4. 编写 Vue 与 San 对照实现

先写 Vue，再写 San 参考实现。

保证两者：

- DOM 层级尽量对应
- 文本内容一致
- 数据初始值一致
- 点击/输入/emit 行为一致
- 样式视觉效果一致

### 5. 执行跨样本重复检查

按“重复样本判定”比较源码和特征。批量任务要同时比较现有数据集与本批所有候选，不能只和前一个组件比较。

若未通过，重做组件的数据模型、工作流或模板结构，再重新生成 Vue/San 对；不要通过更换文案、颜色、默认值或标识符规避检查。

### 6. 更新 dataset manifest

更新 `data/datasets/dataset_manifest.json`：

- 新增 component 记录
- 更新 `total_components`
- 确认 `path`、`vue_file`、`san_file` 与实际文件一致

### 7. 更新复杂度与特征文件

按需更新：

- `data/datasets/features/complexity_tags.json`
- `data/datasets/features/pattern_tags.json`
- `data/datasets/features/migration_notes.json`

复杂度记录建议包含：

```json
{
  "component_name": "ComponentName",
  "complexity_score": {
    "template": 1,
    "data_logic": 1,
    "interaction": 1,
    "styling": 1,
    "communication": 1
  },
  "total_score": 5,
  "level": "simple",
  "features": ["props", "scoped"]
}
```

feature 与 migration notes 应反映组件真实实现。不要为结构重复的组件伪造不同标签或不同迁移说明。

### 8. 暂不更新 split 与 LoRA 数据

当前这个 skill 暂时只负责组件样本、总 manifest 和 features 相关文件。

不要在本 skill 流程中修改：

- `data/datasets/splits/*/manifest.json`
- `data/datasets/splits/*/pairs/`
- `data/datasets/lora/*/dataset.jsonl`

如果用户后续明确要维护训练集、验证集、测试集或 LoRA 数据，应单独建立或使用专门的数据集划分 / LoRA 数据生产流程。

### 9. 做完整验证

至少检查：

- Vue 文件存在
- San 文件存在
- manifest 中路径能对应实际文件
- `total_components` 与实际组件记录数一致
- 复杂度分数总和正确
- level 与总分范围一致
- Vue/San 组件名称和文件名不冲突
- Vue/San 配对内的 props 类型、初始数据、DOM 语义、交互和事件对应
- 本批设计矩阵中的差异真实反映在源码中
- 归一化忽略文案、颜色和默认常量后，没有命中重复样本判定规则
- 同等级样本没有全部采用相同五维分数与 feature 组合

## 推荐输出格式

完成数据生产后，按下面格式汇报：

```text
已新增数据样本：
- 组件：xxx
- 等级：simple/medium/complex
- 核心数据模型：...
- 主要交互/工作流：...
- 模板结构：...
- 关键迁移模式：...
- 与同批及已有样本的主要差异：...
- 五维评分：T=1, D=1, I=1, S=1, C=1，总分=5
- Vue 文件：...
- San 文件：...
- 已更新：dataset_manifest.json、complexity_tags.json 等
- 验证结果：...
```

## 高风险点

重点避免：

- 只新增 Vue，忘记 San
- 只新增文件，忘记 `dataset_manifest.json`
- `dataset_manifest.json.total_components` 与实际数量不一致
- manifest 中 `vue_file` / `san_file` 文件名与真实文件不一致
- 复杂度等级和总分不匹配
- Vue 与 San 视觉结构不等价
- 将同一代码骨架批量替换名称、文案、颜色或默认数据后当作不同样本
- 为达到目标等级机械堆叠无实际语义的指令、方法、生命周期、分页或子组件
- 只检查单个样本是否合规，不检查同批样本及现有数据集的结构重复
- 通过改名、拆分方法或移动节点掩盖重复，而没有改变真实数据模型和交互流程
- San 代码仍使用 Vue 写法，例如 `methods: {}`、`this.xxx`、`props` 字符串类型
- 引入外部依赖导致样本无法稳定运行或截图
