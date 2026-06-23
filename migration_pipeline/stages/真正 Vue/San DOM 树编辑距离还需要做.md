# migration_pipeline/stages 阶段完成情况

## generate 阶段

文件：`migration_pipeline/stages/generate.py`

### 已完成

- 支持输入 Vue 文件路径、Vue 源码或已有 SSM
- 当没有传入 SSM 时，调用 `SSMFactory` 从 Vue 构建 SSM
- 将 SSM 封装为 `GenerationRequest`
- 调用 `generation_client` 请求 generation service
- 获取大模型生成的 San 代码
- 输出 `generated_code`、`generated_file_path`、`ssm`、模型信息、usage
- 提供 `run_from_state()`，为 LangGraph 节点做准备

### 待完成

根据开题报告要求，`generate` 阶段后续需要：

- 多模型 fallback 与重试策略
- 根据 validate/visual_eval 反馈进行上下文增强生成
- prompt 版本管理与生成日志记录
- 批量生成实验入口
- 与 LangGraph `StateGraph` 正式绑定

---

## validate 阶段

文件：`migration_pipeline/stages/validate.py`

### 已完成

- 校验 San SFC 结构：`<template>`、`<script>`、`<style>`
- 校验 San 基础格式：`require('san')`、`DataTypes`、`san.defineComponent`、`initData`
- 调用 `san_compile.py` 检查 San script 可执行性
- 检查 Vue 语法残留：`@click`、`v-if`、`v-for`、`v-model`、`:class`、`export default`、`props:`、`methods: {}`、`this.$emit`、Vue 风格 `this.xxx`
- 检查 San/SSM 基础一致性：组件名、props、data 字段、event handler
- 输出 `validation_passed`、`validation_errors`、`validation_warnings`、`validation_checks`、`san_compile_result`

### 待完成

根据开题报告要求，`validate` 阶段后续需要：

- 生命周期映射校验：`mounted -> attached`、`beforeDestroy -> disposed`
- `dataTypes` 类型准确性校验
- computed/watch 迁移校验
- 事件绑定完整性校验：不仅检查 handler 存在，还要检查模板中 `on-*` 绑定
- 子组件迁移校验
- `migration_hints` 规则落地校验
- 输出结构化错误报告，便于 repair 阶段生成修复 prompt

---

## visual_eval 阶段

文件：`migration_pipeline/stages/visual_eval.py`

### 已完成

- 调用 `vue_render.py` 生成 Vue 渲染快照
- 调用 `san_render.py` 生成 San 渲染快照
- 输出 `html_snapshot`、`dom_snapshot`、`dom_snapshot.tree`
- 调用 `dom_compare.py` 进行 Vue/San DOM tree 对比
- 输出 `tree_edit_distance`、`structure_similarity`、`tag_sequence_similarity`、`text_similarity`
- 输出 `missing_nodes`、`extra_nodes`、`changed_nodes`
- 根据阈值判断结构评估是否通过

### 待完成

根据开题报告要求，`visual_eval` 阶段后续需要：

- 真实浏览器环境渲染（Playwright/Puppeteer）
- 真实 Vue/San runtime 渲染
- 浏览器真实 DOM 抽取
- CSS 计算样式对比
- 截图生成与像素差异计算
- 动态内容归一化（时间、随机值、动画等）
- 多样本批量视觉评估
- 输出可用于论文实验的结构化评估报告

---

## repair 阶段

文件：`migration_pipeline/stages/repair.py`

### 已完成

当前为空占位，尚未实现。

### 待完成

根据开题报告要求，`repair` 阶段需要：

- 接收 `validate` 的 `validation_errors`、`validation_warnings`
- 接收 `visual_eval` 的 `dom_compare_result`、`missing_nodes`、`extra_nodes`、`changed_nodes`
- 将错误与差异整理为修复 prompt
- 调用大模型生成修复后的 San
- 输出 `repaired_code`、`repaired_file_path`、`repair_summary`
- 支持多轮修复与最大修复次数控制
- 形成完整的“生成-校验-反馈-修复”闭环

---

## LangGraph 编排

文件：`migration_pipeline/orchestrator.py`

### 已完成

- 过渡编排层：`run_generate_only()`、`run_generate_and_validate()`、`run_generate_validate_and_visual_eval()`
- 节点方法：`run_generate_node()`、`run_validate_node()`、`run_visual_eval_node()`
- `MigrationPipelineState` 包含 generate、validate、visual_eval 状态字段

### 待完成

根据开题报告要求，后续需要：

- 定义 `StateGraph`
- 注册节点与条件边
- 实现 validate/visual_eval 失败后进入 repair 分支
- 支持最大循环次数
- 每轮状态记录与实验日志导出

---

## 下一步优先级

根据开题报告的“生成-校验-反馈-修复”闭环要求，建议优先顺序：

1. 实现 `repair.py`，消费 validate/visual_eval 的错误报告，生成修复后 San
2. 完善 `validate.py` 的语义一致性校验
3. 升级 `visual_eval.py` 到真实浏览器渲染
4. 将 orchestrator 升级为 LangGraph `StateGraph`
