# v4 repair 调度与候选保留修复 v1（2026-11-02）

已实现显式选用的 `bounded_prepass_v1`。新批次 `formal_30_v4_repair_scheduling_v1` 只用于复用开发样本的针对性回归。此次未修改 Prompt、源数据、冻结产物或原始评分。

## 修改与原因

原策略每次确定性处理也消耗一个 repair attempt；冻结 TaskManager 因此用完 3 个 attempt 而没有 LLM repair。新策略在每次 LLM 之前执行最多 4 个确定性步骤，每步验证，固定点／循环／上限后交给 LLM，最多 3 次 LLM repair；分别统计确定性步数和调用数。这一计算预算变化在新协议预先登记，不与旧 3 混合轮作等预算比较。

事件契约检查改为新策略下每次都执行，不依赖 focused prompt 的字符串标记。关键新编译／initData 错误和视觉“通过→不通过”也拒收。LLM 坏候选单独留证，最终状态恢复到上一候选并停止计为失败；归一化坏候选拒收后让 LLM 使用原候选。旧 legacy 调度默认行为保留，生成器和规则变换本身未改。

## 验证与边界

`replay.json` 记录冻结输入的实际离线验证、渲染和哈希，没有模型请求：TaskManager 能到达 LLM-only 阶段；MonitoringDashboard 第 3 轮和 BudgetThreshold 第 1 轮的已知退化会被拒并保留上一文件。TaskManager 首次归一化被事件追溯保守拒收，closeModal self 包装关系尚未被确认，该限制明确保留。不能把这种保守转交当作所有确定性规则幂等性问题已经解决。

边界测试覆盖步数上限、循环、无预算、确定性直接成功、实际 RepairStage 的 LLM-only 路径、事件门不依赖 Prompt、initData 新冲突、归一化退化回退和 LLM 坏候选留证。完整 238/238 测试通过（含新 9 项），新两样本 dry-run 通过；原始输出随协议冻结。新协议封存 255 份 payload，263 项 live 哈希校验通过，模型批次尚未开始。

本地成功不代表新模型回归通过。TipSplitCalculator 事件方法契约、LocalizationWorkspace 隐藏依赖仍待后续修改，BudgetThreshold 的防退化不等于修好所有静态错误。新两样本运行后先冻结，再决定剩余通用修复与新的完整 30 项回归。v5 继续等待；旧冻结包仅作历史证据，不更新其字节或评分。

Notebook：`notebooks/02-migration-experiments/2026-11-02_formal_30_v4_repair_scheduling.ipynb`。新协议：`data/experiments/protocols/formal_30_v4_repair_scheduling_v1_frozen_20261102/PROTOCOL.md`。
