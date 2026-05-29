---
name: schema-iteration-checklist
description: 当用户想在这个仓库里迭代、重构、扩展、版本化或审查 SSM schema 时，务必使用这个 skill。适用于新增/删除/重命名 schema 字段、引入新 schema 版本（如 v4）、分析 schema 改动会影响哪些文件、或把 schema 演进经验整理成可执行 checklist 的场景。这个 skill 用于确保 schema 变更能够在 `SSM/schema`、`SSM/extractors` 以及下游消费者（如 `local_server`、`migration_pipeline`）之间保持一致。
---

# Schema 迭代 Checklist

当你需要在这个仓库中处理 schema 演进问题时，使用这个 skill。

## 目标

帮助用户安全、系统地修改 SSM schema，确保：

- schema 定义本身仍然是唯一权威来源
- extractor 输出始终与 schema 保持一致
- schema 版本切换机制持续可用
- 下游生成链路与 pipeline 不会因为 schema 变更而静默失效

## 核心原则

把 `SSM/schema/*.py` 视为结构形状的唯一真源。

在迭代 schema 时：

- 先在 `SSM/schema/*.py` 中定义或修改结构
- 在 `SSM/schema/__init__.py` 中注册或切换版本
- extractor 只负责补字段值，不负责重新定义最终 schema 的形状
- 同时检查读取该 SSM 的下游消费者

如果某个结构已经在 schema builder 中定义过，就不要让 extractors 再次“拥有”这份最终结构定义。

## Checklist

### 1. 先给 schema 改动分类

先识别当前改动属于哪一种：

- 新增字段
- 删除字段
- 重命名字段
- 把字段移动到新的 section
- 把一个字段拆成多个字段
- 把多个字段合并成一个字段
- 新增 schema 版本，例如 `v4`
- 修改的是 guidance / contract 字段，而不是 factual extraction 字段

还要判断这个字段属于哪一类：

- `facts`：直接从源码提取出来的事实字段
- `derived`：根据事实字段推导出来的字段
- `guidance`：迁移提示、生成约束、策略建议等字段

这个分类会直接决定后续需要修改哪一层 extractor。

### 2. 修改 schema 定义

永远先从 schema 文件开始：

- 如果修改当前版本，改 `SSM/schema/v3.py`
- 如果引入新版本，新增类似 `SSM/schema/v4.py`

修改 schema 时，确认该模块仍然暴露 extractor 所依赖的 builder 接口：

- `SSM_SCHEMA_VERSION`
- `SSM_SCHEMA_NAME`
- `build_ssm_metadata(...)`
- `build_san_generation_contract()`
- `build_ssm_shell()`

如果新版本还承载了更多结构化 builder，也应继续把它们保留在 schema 层作为权威定义。

### 3. 注册或切换 schema 版本入口

检查 `SSM/schema/__init__.py`。

按需更新：

- `SCHEMA_MODULES`
- `DEFAULT_SCHEMA_VERSION`
- 其他版本解析相关逻辑

如果用户希望整个仓库默认切到新版本，这一步就是统一切换入口。

### 4. 检查 factory 顶层装配

检查 `SSM/extractors/factory.py`。

确认：

- 顶层 SSM shell 仍然和 schema builder 保持一致
- metadata 组装仍然是通过 schema builder 完成的
- generation contract 仍然来自 schema 模块
- schema 校验逻辑仍然反映了当前 builder 接口要求
- schema 版本切换仍然通过 `schema_module` 正常工作

如果本次改动只影响结构定义、不影响具体提取逻辑，那么这里可能是唯一需要调整的 extractor 文件。

### 5. 检查 template 提取层

当 schema 变更涉及以下字段时，检查 `SSM/extractors/template_extractor.py`：

- `template.dom_tree`
- `template.component_refs`
- `template.slot_distribution`
- `template.directives_registry`
- `template.event_bindings`
- `template.directives[*].migration_note`

这里只修改“字段值是如何产生的”逻辑，不要在这里重新定义 schema 结构。

### 6. 检查 script 提取层

当 schema 变更涉及以下字段时，检查 `SSM/extractors/script_extractor.py`：

- `script.export_info`
- `script.options.props`
- `script.options.data`
- `script.options.computed`
- `script.options.watch`
- `script.options.methods`
- `script.options.lifecycle_hooks`
- `script.imports`
- `script.top_level_declarations`

### 7. 检查 style 提取层

当 schema 变更涉及以下字段时，检查 `SSM/extractors/style_extractor.py`：

- `styles.style_blocks`
- `styles.css_rules`
- `styles.css_variables`
- `styles.layout_features_inferred`
- 静态/动态 class 与 style 绑定摘要

### 8. 检查跨块推导模型

当 schema 变更涉及以下字段时，检查 `SSM/extractors/relation_builder.py`：

- `binding_graph`
- `event_model`
- `style_model`
- `sub_components`
- `migration_hints`
- `data_access_conversion_plan`

如果可以，最终结构仍然要通过 schema 层 builder 输出，而不是在 relation builder 中手写 dict 形状。

### 9. 检查 schema-builder 对齐情况

改完之后，确认最终输出结构仍然是从 schema 层发出来的，而不是被 extractors 私下重新定义了一份。

尤其重点检查：

- 顶层 shell
- metadata
- migration hint 对象
- generation contract
- relation-builder 的汇总结构

### 10. 检查版本切换兼容性

至少验证这些路径：

- `SSMFactory()`
- `SSMFactory(schema_module="v3")`
- `SSMFactory(schema_module="SSM.schema.v3")`
- 如果有需要，再验证 module object 注入方式

如果新增了版本，也要验证它能通过 `SSM.schema.resolve_schema_module(...)` 被正确解析。

### 11. 检查下游消费者

schema 变更可能影响消费方。至少检查：

- `local_server/api/evaluation_routes.py`
- `migration_pipeline/stages/generate.py`

如果附近还有 prompt 构造逻辑或生成消费逻辑也依赖了这些字段，也要一起检查。

### 12. 更新文档

schema 行为变更后，按需更新：

- `SSM/README.md`
- `SSM/schema/v3_extraction_guide.md`
- 如果涉及版本切换，再补版本切换说明

### 13. 做 focused verification

至少做完下面这些验证：

- 对改动文件做 Python 语法检查
- 用一个小型 Vue 组件抽一份 SSM
- 检查生成出来的 JSON 结构
- 验证新增 / 重命名 / 删除字段是否符合预期
- 验证下游生成链路仍然能读取这份 SSM，没有明显 break

## 高风险点

对下面这些失败模式要特别警惕：

- 改了 schema 定义，但忘了同步 extractor 填值逻辑
- 改了 extractor 输出，但忘了同步 schema builder
- 新增了 schema 版本，但忘了更新 `SSM/schema/__init__.py`
- 重命名字段后，没有检查 `local_server` 或 `migration_pipeline`
- extractor 中重新引入了手写 schema 结构

## 推荐输出方式

在帮助用户处理 schema 迭代问题时，尽量按下面顺序给出结果：

1. 改动分类
2. 必改文件
3. 建议复查文件
4. 下游消费者影响
5. 验证计划

如果你实际修改了代码，最终汇报也尽量按这个顺序总结，方便用户快速检查改动是否完整。
