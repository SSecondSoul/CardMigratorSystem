# 剩余 21 项补充问题收集批次

按用户 2026-11-19 的指令启动。保留 v1 已完成的 49 项和 v2 两项重复验证，选取实验集清单中未出现在 v1 已完成记录里的 21 个组件，全部为复杂组件，按原清单顺序运行。

本批绑定、模型配置、Prompt、评估阈值和预算与 `real_system_experiment70_v2_generation_probe_20261118` 相同：完整语义 SSM 的无损紧凑 JSON、qwen-plus、每次最多 32768 输出 Tokens、最多 3 轮修复／4 次调用、131072 已知用量软停止线、默认 props、未配置交互。不启用 LangSmith，不修改生成／修复规则或评估容量。验证集和测试集不运行。

每项建立新任务，不重跑 MonitoringDashboard、TaskManager，不复用或覆盖旧任务。所有 70 个实验组件的名称和 ID 继续排除为 few-shot 来源。普通质量失败与已知容量阻断会保存后继续下一项；未知调用、输出不完整、版本漂移等安全条件仍按原控制器暂停，不能保证忽略所有错误一直运行。

`coverage-provenance.json` 保存选择规则及旧协议、进度、报告和 SHA 清单的启动前哈希。准备后已复核旧文件未变。

本批独立统计分母为 21。完成后与旧结果一起用于覆盖 70 个不同组件的问题分类，**不得把跨 v1／v2 的结果拼成统一版本 70 项通过率**，也不以重复样本较好的结果替换旧失败。

从仓库根目录查看状态：

```powershell
& migration_system/.venv/Scripts/python.exe experiment_runs/run_experiment.py status --batch real_system_experiment70_v2_remaining21_20261119
```

若已核查暂停原因并获准恢复，使用原批次，不重新 prepare：

```powershell
& migration_system/.venv/Scripts/python.exe experiment_runs/run_experiment.py run --execute --batch real_system_experiment70_v2_remaining21_20261119
```

运行期间不要修改冻结的系统源码、模型／浏览器配置、Prompt 或阈值。全部完成后再统一分析并确定通用修复，不把原始结果改判为修复后结果。
