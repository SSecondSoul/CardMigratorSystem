# repair 调度策略 v1：执行完成，语义修复未闭环

> 后续更正（2026-11-02）：真实 San 事件测试证实，裸 handler 默认注入 $event，handler() 才不传参数。因此下文“未显式传 $event”的观察不能作为功能缺失证据。旧保护门确有包装追溯覆盖缺口，旧产物也仍有其它静态错误，原失败评分不变。后续修复见 `../formal_30_v4_semantic_closure_v1_20261102/REPORT.md`；原始快照未修改。

日期：2026-11-02。批次 `formal_30_v4_repair_scheduling_v1`，2026-11-02 18:32:32–19:04:47（UTC+8）。先冻结后诊断：`formal_30_v4_repair_scheduling_v1_results_20261102_224614`，283 文件哈希验证通过；冻结时协议 263 项 live 校验通过。

## 实际结果

两项执行完成、零执行错误、**0/2 自动通过**。两项初始 DOM 评估最终均通过，不代表交互或静态迁移正确。此次没有进行新的人工交互确认。

| 样本 | LLM repair 调用 | 确定性步骤 | 最终 DOM 相似度 | 自动结论 |
| --- | ---: | ---: | ---: | --- |
| TaskManager | 2 | 2 (0 接受) | 0.9889 | 未通过 |
| MonitoringDashboard | 3 | 3 (3 接受) | 0.9605 | 未通过 |

TaskManager 总用时 757.109 秒，MonitoringDashboard 1177.797 秒。生成 204,452、repair 543,361，合计 **747,813 tokens**，包含被拒的第二次 TaskManager repair。此次预算为最多 3 次 LLM repair，而前轮为 3 个混合 attempt；这是不同预算、不同随机新生成结果，不能作等成本因果比较，也不能用本轮替换原完整 30 项的结论。

## TaskManager：调用路径修复生效，事件追溯存在覆盖缺口

两次确定性候选均被拒（新增 1 个无法追溯的 `click:closeModal`），随后均实际进入 LLM。第一次 LLM 后剩四类错误：事件语法、self-click guard、computed 中的 isOverdue 实例方法调用、getTaskCount 隐藏 tasks 依赖。

第二次 LLM 后静态错误减少到两类：事件语法、computed 实例方法调用；但事件追溯从 0 个 unresolved 变为 1 个。保护门据此拒收，停止并把 final 恢复为 `TaskManager_repaired.san`，而不是第二次文件。最终代码、文件哈希、静态和视觉评估均已核对匹配第一轮；拒收产物、评估和 token 在历史中保留，仍计失败。

代码中存在 `handleModalBackdropClick(e)`，带 target/currentTarget 相等检查并调用 closeModal。当前追溯器只识别直接绑定及少量命名别名，无法据该包装证明与原 `@click.self` 等价；而模板绑定没有显式传 `$event`。因此本轮不能把“无法追溯”直接解释为真实功能删除，也不能直接认定为纯误报或人工放行。下一步应检查包装函数传参、分支和调用语义，并为等价包装及不等价包装增加正反例测试。

## MonitoringDashboard：3 次 LLM 后仍有明确残留

三个确定性步骤均被接受，三次 LLM 分别产生 5、4、2 类错误。未发生候选回退；最终文件确实是第三轮，DOM 相似度 0.9605。

1. `invalid_san_inline_computed_method_invocation`：requestChart 的 computed `barWidth()` 返回函数，但模板仍使用 `barWidth(data.length)`。需修复参数化计算的落地方式，而不是删除检查。
2. `event_arguments_not_landed`：绑定变为无参数 onKPIClick 和 changePeriod，未保留源 `onKPIClick(kpi)`、`changePeriod(period.value)`；方法依赖 `this.event.target` 取 data-*。不能仅凭初始 DOM 通过证明这条事件链可用，需要显式传参并验证真实事件／payload。

## 已证明与未证明

已证明本轮 LLM-only 路径可达，确定性步骤与 LLM 次数分开计数，TaskManager 的拒收与回退证据一致。未证明迁移质量已经合格；保守追溯拒收可能阻断有效改写，原规则与 checker 的协调还需边界测试。原 BudgetThreshold、TipSplitCalculator、LocalizationWorkspace 事项不属于本次两样本结案。

## 建议下一步（尚未实施）

先用本次冻结产物做无模型回放：审查事件包装追溯和显式传参规则，修复 computed 参数化计算及事件 payload 的通用落地，再添加反例防止误放行。涉及 Prompt／规则／checker 的改动应建新版本并记录，不改本轮冻结包或原始 San，不降低通过标准。局部回归通过后再完整跑 30 项，v5 探索性评估继续等待。当前不建议直接强制重跑同批，也不把 DOM 通过当成人工通过。

复现：`python -m migration_pipeline.analyze_formal_30_v4_repair_scheduling --snapshot data/experiments/snapshots/formal_30_v4_repair_scheduling_v1_results_20261102_224614`。
