# v4 新调度策略针对性开发回归 v1

日期：2026-11-02；批次 formal_30_v4_repair_scheduling_v1。

仅复用 TaskManager、MonitoringDashboard，原 Vue 输入相同；采用 bounded_prepass_v1。旧策略最多 3 个混合 attempt；本版本的最大轮数 **明确改为最多 3 次 LLM repair 调用**，每次之前最多 4 个确定性步骤，最多 12 个确定性步骤。每一步重评估，遇到固定点／重复代码／上限转交 LLM，若归一化已通过则不调用 LLM。循环检测与规则幂等性不是完整等价，本版本未宣称所有规则已经幂等。

这改变了计算预算，不能把新 3 次调用结果与旧 3 混合轮结果当作等成本比较。generation、Prompt、模型、验证器、归一化变换规则本身与前次保持；调度、候选拒收／保留及计数报告改变。legacy 默认路径保持，旧批次／快照不回填。原 30 样本及 v5 冻结协议的 live 代码基线已不再与新实现一致，不能继续当作当前代码可运行协议。

新策略对所有候选应用事件契约与关键错误／视觉通过退化检查，不依赖特定 Prompt 文本标记。拒绝的产物留在单独文件和历史里；LLM 候选被拒后恢复上一候选的代码、路径、验证与视觉状态，停止并保留失败，不把上一份候选自动宣称为通过。确定性候选被拒则保留原候选交给 LLM。TaskManager 离线首次归一化被保守的事件契约检查拒绝（closeModal 包装后追溯不完整）；这是已知限制，不因追求通过而绕过检查。

离线回放证明 TaskManager 能到达 LLM-only 阶段，MonitoringDashboard 第三轮和 BudgetThreshold 第一轮退化候选会被拒并保留上一文件；不代表模型回归已通过。TipSplitCalculator 事件方法契约、LocalizationWorkspace 隐藏语言依赖仍待后续修复，不包含在本次两样本结案结论中。

继续使用 qwen/qwen-plus、温度 0.2、上游 600 秒／两类客户端 660 秒。先在旧服务器 Ctrl+C，然后窗口 A 设置环境密钥并运行：

```powershell
$env:LLM_API_KEY = "<你的密钥>"
python -m migration_pipeline.run_formal_30_v4_repair_scheduling --server
```

窗口 B 执行一次：

```powershell
python -m migration_pipeline.run_formal_30_v4_repair_scheduling --execute
```

launcher 核对 live 哈希并固定环境。--dry-run 可无模型查看计划。运行结束先冻结，不加 --force，不挑选多次结果。输出与 summary 使用批次名对应的独立默认目录。报告 LLM 次数与确定性步数、拒收历史及 token；手工交互结论另列。运行代码的文件基线以 frozen/ 为准，服务器实际加载仍需操作者按上述命令确认。该批是复用开发样本，不是独立测试；v5 暂停。
