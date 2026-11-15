# MonitoringDashboard 源事件参数、挂载阶段与 watcher 副作用闭环

日期：2026-11-03。性质：重复开发样本的冻结失败产物离线修复，不是新一轮模型迁移或独立测试。

## 问题与证据

来源为 `formal_30_v4_semantic_closure_v2_results_20261103_160541`，297 文件校验通过。

1. 源父模板是 `onKPIClick(kpi)`，源方法接收 kpi；生成的父模板只有 `onKPIClick`，父方法却用 `e.index` 查数组。子组件 `fire('click')` 没有发出带 index 的 payload，参数链不成立。
2. 源 mounted 依次调用业务初始化、启动时钟、启动模拟、按设置启动刷新、显示通知。生成代码把初始化展开调用和前两个计时器提前到 inited。动作不全是丢失，而是执行阶段错误。
3. 本次检查还确认设置 watcher 缺少源代码的 `localStorage.setItem('dashboard_settings', JSON.stringify(newVal))`。仅恢复 watcher 注册不等于保留其副作用。

旧冻结批次当时报告两个静态错误。新检查器在同一原件上额外明确报告 `source_mounted_order_not_landed` 和 `source_watch_persistence_not_landed`；不把新检查结果回填为旧版本当时的诊断或改写旧分数。

## 修改位置与通用边界

本次改动位于 repair 阶段、验证器和候选保护，不是手工修改原始 .san，也没有修改 generation／服务器 Prompt。

- `migration_pipeline/utils/source_phase_semantics.cjs`：基于真实源 Vue 与生成代码 AST，定位导出父组件，不按组件名硬编码。
- 参数修复：仅在源／目标唯一事件、相同循环别名与集合、源处理器可完整理解，且生成错误处理器恰为“数组读取 + e.index 取项 + 等价源方法主体”时，成对恢复绑定和方法参数。额外副作用、不同集合、歧义调用不猜改。
- 阶段修复：仅将可证明等于源 mounted 展开序列的 inited 后缀搬到 attached 前部；保留源命名的 watcher 注册，不改子组件和样式。排序错误可以报告，但不会自动盲目重排；未知前置动作、复杂业务初始化、源 created／beforeMount 等情形拒修。
- watcher 修复：仅在源 handler 与生成 listener 的其余语句经状态读取转换后 AST 一致，且明确只少一个末尾源存储写入时补回。未知表达式、已有不同写入、参数变化、immediate 等额外选项或本地 shadow 的 storage／JSON 不猜改。不是通用 watcher 语义等价证明。
- `stages/repair.py`：确定性预处理及模型返回后的共同规则入口；`utils/repair_prompt.py`：聚焦 Prompt 纳入缺失生命周期映射及新增诊断，明确参数链、阶段顺序、watcher 副作用约束。
- `stages/validate.py` 与 `utils/repair_scheduler.py`：新增源可证明的顺序／存储缺失诊断及同版本候选退化保护，不能用总错误数下降掩盖新缺陷。

## 验证与独立留证

新增 12 项测试，覆盖真实冻结产物、实际 San 事件监听器、挂载调用顺序、作用域隔离、幂等性、歧义／副作用拒修、watcher 正反例及验证器到候选保护的闭环。完整测试 **291/291 通过，116.043 秒**。测试不代表所有组件交互都正确。

离线证据包：`data/experiments/analysis/formal_30_v4_source_phase_closure_v1_20261103`，12 文件校验通过。候选 SHA-256：`28290086017b0568aa39db3936390668ce8ce1b08048a1f27050a424db77c968`。该包保存规则代码、重放脚本、输入摘要、前后评估及候选保护结果；不是完整新模型运行协议。

对同一冻结原件执行三个通用规则后：静态错误清零、San 编译与初始 DOM 评估通过、候选保护不拒收。未改子组件代码／CSS。首次诊断重放的最终相似度为 0.9912；随后封存重放前为 0.9912、后为 0.9825，均在现有通过阈值内，封存以 replay.json 的实际值为准，不择优替换。源组件含随机数据，两次渲染非同一个固定随机输入，不能据此宣称相似度稳定提升或作单因素因果归因。

复现只读重放：

```powershell
python -m migration_pipeline.replay_formal_30_v4_source_phase_closure
python data/experiments/analysis/formal_30_v4_source_phase_closure_v1_20261103/verify_snapshot.py
```

本次模型调用 **0**，未执行浏览器交互测试，未更换人工测试页面引用，未 commit／push。TaskManager 已人工通过候选包 13 文件及原始快照 297 文件再次校验通过。

## 结论及后续

这一步证明“诊断 → 有边界通用修复 → 重新验证 → 候选保护 → 正反例”能关闭这份已知产物的上述缺陷，不证明所有新生成代码都会符合规则，也不证明完整交互等价。原 semantic closure v2 批次仍为 2 项完成、1 项自动通过、1 项失败。

下一步须另建并冻结新协议与 checkpoint，再由操作者只运行 MonitoringDashboard 的新生成／最多 3 次 LLM repair，保留当前 TaskManager 人工通过产物不重生成。新运行结束先冻结再分析，之后再做人工交互验证；完整 30 项回归及其它失败项仍待完成。新代码与新验证器使旧协议 live 基线不再匹配，不允许修改旧冻结包消除差异。
