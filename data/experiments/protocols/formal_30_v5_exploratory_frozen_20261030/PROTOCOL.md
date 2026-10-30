# formal_30_v5 探索性评估协议（文件冻结版）

冻结日期：2026-10-30（Asia/Shanghai）。本协议锁定文件版本；**服务器进程配置仍须在首次模型请求前由操作者确认**。

## 目的与证据等级

本批使用 v4 开发改进后的迁移系统，对 30 个样本进行探索性评估（简单／中等／复杂各 10）。候选中 23 项曾在早期数据集验证 Notebook 被点名，操作者无法确认是否还有手工迁移调参接触。因此它**不是严格独立未见测试集**，不得与 v1/v3 拼接为独立通过率，也不得宣称同样本配对提升。早期接触、选择算法和原始审计保存在本协议的 `frozen/` 目录中。

仅 Vue 源码进入迁移输入；参考 San 仅为事后分析封存，不得进入生成／修复请求。本轮结果不得用于改写 v1/v3 的既有结论。

## 固定设置与主结果

- 批次 `formal_30_v5`，每样本最多 3 轮 repair；配置与样本顺序以 `frozen/migration_pipeline/batch_configs/formal_30_v5.json` 为准。
- Provider `qwen`，模型 `qwen-plus`，客户端温度 `0.2`；`LLM_TIMEOUT=240`，生成和 repair HTTP 超时均为 300 秒。
- 保留 `--include-state`；默认健康检查启用；自动最终通过率以 30 个配置样本为分母，并另报正常完成样本通过率。
- 分层通过率、初始通过数、repair 转通过数、轮数、token、执行异常、最终静态及视觉错误码分别报告。人工浏览器检查另列，不覆盖自动结果。
- 模型无固定 seed；不挑选多次重跑的最佳结果。未预注册确定性交互场景时，不得把自动通过表述成全部交互正确。

## 冻结和偏差规则

首次模型请求之后不得更改样本、Prompt、SSM、生成／repair／验证／渲染／评估器、阈值、模型、温度、超时和修复轮数。基础设施中断可用完全相同的命令和 checkpoint 恢复；**不加 `--force`，不单独重跑失败样本替换结果**。若发现系统或评估器缺陷，保留本批原始结果，修复后建立新批次／协议版本。原始自动结果冻结后再诊断。

## 启动门槛（暂勿跳过）

在仓库根目录先运行：

```powershell
python data/experiments/protocols/formal_30_v5_exploratory_frozen_20261030/verify_protocol.py --live
python -m unittest discover -s tests -p "test_*.py"
python migration_pipeline/run_batch_pipeline.py --config-file migration_pipeline/batch_configs/formal_30_v5.json --include-state --dry-run
```

随后在**新** PowerShell 窗口启动本地服务，以确保加载磁盘上的冻结代码。仅在当前窗口设置密钥，勿写入文件：

```powershell
$env:LLM_PROVIDER = "qwen"
$env:LLM_API_KEY = "<你的密钥>"
$env:LLM_MODEL = "qwen-plus"
$env:LLM_TIMEOUT = "240"
python -m local_server.app
```

操作者须确认健康检查、服务启动时间和以上非密钥配置；文件校验**不能证明已运行进程加载了这些字节**。完成确认之前不得启动模型批次。

## 后续运行命令（仅启动门槛满足后）

在另一个已激活 `cardmig` 的 PowerShell 窗口：

```powershell
python migration_pipeline/run_batch_pipeline.py --config-file migration_pipeline/batch_configs/formal_30_v5.json --include-state
```

使用默认独立输出：`data/experiments/pipeline/batches/formal_30_v5/`、`data/experiments/repair_reports/batches/formal_30_v5/`、`data/experiments/batch_reports/formal_30_v5_summary.json`。如发生基础设施中断，仅用同一命令恢复。
