# v4 完整 30 样本回归：超时重试记录

本次 checkpoint 更新时间：`2026-10-30T22:58:15+08:00`。仅 TaskManager、MonitoringDashboard 两条记录变化，其余 28 条 completed 记录逐字段保持一致（其中 25 通过、3 评估未通过）。结果仍为 **25/30 = 83.33%**，2 项执行错误尚无最终评估。

原始重试结果冻结于 `formal_30_v4_full_regression_results_20261030_231238`，校验 359 个文件通过；首次快照 `formal_30_v4_full_regression_results_20261030_215511` 的 359 个文件也校验通过。旧结果及两次错误信息均保留。

| 样本 | 首次异常阶段 | 本次异常阶段 | 本次耗时 |
| --- | --- | --- | ---: |
| TaskManager | repair | generation | 241.047 秒 |
| MonitoringDashboard | generation | generation | 240.703 秒 |

两个异常均为本地 HTTP 400 包装的 `The read operation timed out`。冻结代码中 `QwenClient` 通过非流式 HTTP 请求等待响应，`urlopen(..., timeout=self.timeout)` 使用 `LLM_TIMEOUT`，本协议设为 240 秒；批处理到本地服务的 generation／repair HTTP 超时为 300 秒。约 241 秒的失败与上游读取上限一致。健康检查记录 provider=qwen、model=qwen-plus。

直接终止点可定位为上游读取超时，但现有记录不能区分服务端排队、生成耗时或网络读等待；不能据此断言 Prompt 一定错误、密钥错误或组件最终修复失败。TaskManager 首次有生成和 repair 产物、本次却在生成阶段超时，也不能解释为代码再次退化。

对比两份快照的 102 份 pipeline／repair report 文件，差异文件数为 0。若无差异，当前目录里的 TaskManager 旧产物来自首次执行，不能当成本次重试生成的输出。异常样本没有完整报告，聚合 token 未完整计入其消耗；summary 总 token 保持不变不能解释为重试免费。

## 后续处理边界

本协议已完成一次同条件的超时重试，继续重复相同命令的诊断价值有限。保留原批次的 25 通过、3 评估失败、2 超时，先建立单独的基础设施诊断版本，保持模型、Prompt 与 3 轮上限，考虑把上游超时增至 600 秒，同时把 generation／repair 客户端超时增至 660 秒；两层必须配套，并记录新配置与新输出。它属于条件变化，不能回填本批，也不能直接提高本批通过率。

三个评估失败仍是 BudgetThreshold（repair 模板退化）、TipSplitCalculator（事件辅助方法契约／校验范围待核实）、LocalizationWorkspace（隐藏语言依赖）。后续系统修复采用新的版本和回归配置；v5 探索性评估继续等待。此次仅做记录与诊断，没有改变 Prompt、规则、超时或任何生成产物，也未调用模型。
