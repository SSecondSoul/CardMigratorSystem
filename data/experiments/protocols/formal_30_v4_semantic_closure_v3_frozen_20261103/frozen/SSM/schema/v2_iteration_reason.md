# SSM Schema v2 迭代原因

## 背景

`SSM/schema/v1.py` 只描述了基础模板节点、脚本字段、样式规则和少量检索扩展，适合作为组件摘要，但不足以直接指导大模型稳定生成等价 San 组件。结合 `data/datasets/components` 中 simple、medium、complex 三类组件，以及 `complexity_tags.json`、`pattern_tags.json`、`migration_notes.json` 和 `dataset_manifest.json`，组件迁移实际需要保留更多可执行语义。

## 数据集暴露出的关键问题

- 复杂组件不仅有 DOM 层级，还包含内联子组件、父子 props、子组件 `$emit`、SVG 图表、模态框、拖拽、通知、定时器和 localStorage。
- Vue 模板大量使用 `v-if`、`v-for`、`v-bind`、`v-on`、`v-model`、动态 `:class`、动态 `:style`，这些语法都不能直接复制到 San。
- `migration_notes.json` 反复指出 San 迁移的关键差异：`@click` 到 `on-click`、`$emit` 到 `this.fire`、`this.xxx` 到 `this.data.get/set`、`mounted/beforeDestroy` 到 `attached/disposed`。
- 中复杂组件常包含 PascalCase/短横线子组件命名差异，若 schema 不记录组件引用和注册名，大模型容易生成无法识别的 San 子组件。
- 样式不仅是 CSS 文本，还包含静态类名、动态类名、动态样式、hover/状态样式和 scoped CSS，对视觉还原有直接影响。

## v2 的主要增强

- 新增 `component_identity`：关联 `dataset_manifest.json` 中的组件 id、路径、复杂度、源/目标文件和迁移状态。
- 新增 `feature_profile`：融合复杂度评分、pattern tags、feature tags 和 migration patterns，帮助模型识别迁移风险。
- 强化 `template_structure_tree`：要求描述 DOM 节点层次、子组件引用、插槽分布、动态属性、文本插值和指令迁移策略。
- 新增 `data_binding_graph`：追踪 props、data、computed、watch 与模板、方法、外部状态之间的绑定边，明确 San 的 `dataTypes`、`initData`、`computed` 与 `this.data.get/set` 方案。
- 新增 `event_interaction_table`：记录 DOM 事件、自定义事件、修饰符、处理函数签名、payload、读写字段和副作用，避免交互迁移丢失。
- 强化 `style_feature_set`：结构化记录静态类名、动态类名绑定、动态 style、scoped CSS、关键 CSS rules、视觉 token 和布局特征。
- 新增 `script_model`：补充内联子组件、生命周期、异步逻辑、副作用清理和组件注册信息。
- 新增 `migration_knowledge`：把迁移笔记中的共性规则沉淀为生成 San 代码时的强约束。
- 新增 `generation_contract`：定义大模型生成 San 组件时必须保留的行为、输出要求和质量检查点。

## 为什么这些字段必要

- 模板结构树解决“生成什么 DOM/子组件结构”的问题。
- 数据绑定图解决“哪些状态驱动哪些模板和逻辑”的问题。
- 事件交互表解决“用户操作、子组件事件和方法副作用如何串起来”的问题。
- 样式特征集解决“动态视觉状态和 scoped 样式如何保真”的问题。
- 迁移知识和生成契约解决“Vue 语义如何稳定落到 San 语法”的问题。

v2 因此从 v1 的“组件摘要 schema”升级为“可用于 San 代码生成的迁移语义 schema”。
