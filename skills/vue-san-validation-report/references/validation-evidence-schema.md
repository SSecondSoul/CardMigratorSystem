# 验证证据与统计口径

在需要从人工测试过程生成批次问题报告时，使用本参考。它规定信息如何分类和计数，避免报告依赖模糊的聊天记忆。

## 推荐记录结构

如果仓库已经存在批次验证日志，优先读取它。若用户明确要求持久化验证过程，可采用以下 JSON 形状；不要仅为了生成 notebook 而额外创建日志文件。

```json
{
  "schema_version": 1,
  "batch_id": "batch-identifier",
  "recorded_at": "YYYY-MM-DD",
  "design_matrix": "relative/path/to/design_matrix.json",
  "planned_pairs": 30,
  "components": [
    {
      "name": "ComponentName",
      "level": "simple|medium|complex",
      "vue_status": "confirmed|failed|not_checked",
      "san_status": "confirmed|failed|not_checked",
      "confirmed_at": "YYYY-MM-DD|null",
      "issues": ["D1"]
    }
  ],
  "issues": [
    {
      "id": "D1",
      "category": "production_defect",
      "component": "ComponentName",
      "framework": "vue|san|shared|environment",
      "phase": "initial_validation|repair_recheck",
      "symptom": "用户可以观察到的现象",
      "trigger": "复现该现象的操作",
      "root_cause": "有源码证据支持的原因",
      "resolution": "实际采用的解决办法",
      "changed_files": ["relative/path/to/file"],
      "verification": {
        "status": "confirmed_by_user|static_only|not_rechecked|unresolved",
        "date": "YYYY-MM-DD|null",
        "evidence": "确认消息、断言或其他证据"
      }
    }
  ]
}
```

## 分类规则

### production_defect

满足以下条件时计入生产后缺陷：

- 组件批量生产已完成；
- 首次运行或人工交互发现行为、视觉或框架语义不正确；
- 需要修改组件、生成结果或运行配置才能恢复预期行为。

### repair_regression

修复一个问题后新引入的加载失败、布局错误或行为变化。单独统计，不回填为最初生产缺陷。

### expected_behavior

实现符合已声明的业务约束，但界面解释不足或用户容易误解。记录改进建议，不计入缺陷率；若实现与业务约束不一致，则仍属于 `production_defect`。

### remaining_risk

当前组件可能已经通过，但流程仍有复发或证据风险，例如：

- 生成脚本仍会生成修复前代码；
- 元数据仍标记 `not_run`；
- 没有自动化交互回归；
- 结论仅依赖人工观察；
- 测试加载器与正式构建环境不同。

## 计数规则

- **缺陷条数**：只统计 `production_defect` 记录。
- **受影响组件数**：对 production defect 的 `component` 去重。
- **组件受影响率**：受影响组件数 / 批次组件对总数。
- **人工检查覆盖率**：Vue 和 San 均完成检查的组件对数 / 计划组件对总数。
- **修复复核率**：状态为 `confirmed_by_user` 的已修复 production defect / 已修复 production defect。
- **框架分布**：按 `vue`、`san`、`shared`、`environment` 分类；`shared` 不重复计入 Vue 与 San。
- **复杂度分布**：按受影响组件去重后统计，不按缺陷条数统计。

一个底层根因同时造成多个紧密相关表象时，合并为一条缺陷并列出全部现象。若同一组件同时存在响应式依赖问题和布局溢出，应拆为两条，因为根因、修复和研究含义不同。

## 证据等级

从强到弱可记录为：

1. 可重复自动化测试与保存的输出；
2. 用户明确完成 Vue/San 人工复核；
3. 修复后只做静态源码或断言检查；
4. 根据源码推断但未复现；
5. 缺少证据。

报告不能用较弱等级替代较强措辞。例如代码中存在修复片段，只能证明静态修复存在，不能自动写成“交互已通过”。

## Notebook 最低内容

一份适合论文追溯的报告至少说明：

- 批次标识、日期、规模和组件分层；
- 验证流程与证据边界；
- 每条问题的现象、根因、解决办法和状态；
- 统计口径与可复算代码；
- 可复用的迁移或修复模式；
- 修复后仍存在的工程风险；
- 可用于论文的结论与有效性威胁；
- 原始数据、组件、脚本、skill 和 runner 的路径。
