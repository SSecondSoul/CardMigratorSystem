# v4 超时诊断 v1：600／660 秒

日期：2026-11-02（Asia/Shanghai）。批次 `formal_30_v4_timeout_diagnostic_v1`。

## 目的和解释范围

仅复用 TaskManager、MonitoringDashboard 两项，在相同 v4 源码、Prompt、qwen/qwen-plus、温度 0.2、最多 3 轮 repair 下，将上游非流式读取超时从 240 秒增至 600 秒，将两类批处理 HTTP 客户端从 300 秒增至 660 秒。采用新的生成路径、repair report 和 checkpoint。

原完整回归及同条件重试均为 25 通过、3 评估失败、2 执行超时；原结果保留。这是改变超时条件的诊断，不能将新通过项回填原批次，不能宣称严格独立泛化。LLM 随机输出不同，若成功，只能说明更长超时条件下本次运行完成，不能仅凭一次结果证明失败唯一根因是时间不足。

旧 TaskManager 产物和任何参考 San 都不作为本次生成输入。先冻结本次原始结果再诊断。一次运行完成或发生异常后交回检查，暂不自行反复重试，不加 --force。3 项原评估失败仍留在后续修复清单中，v5 等待。

## 配置生效方式

JSON 中 required_launch_environment 是记录性字段，原批处理不会从中设置超时。必须使用专用 launcher，它在新子进程导入配置前设置环境：LLM_TIMEOUT=600、MIGRATION_GENERATION_TIMEOUT=660、MIGRATION_REPAIR_TIMEOUT=660，固定原默认的 provider/model/API 地址。仓库全局默认值未改。

## 两个 PowerShell 窗口

先在旧服务器终端 Ctrl+C。窗口 A 激活 cardmig、进入仓库根目录，设置密钥后启动：

```powershell
$env:LLM_API_KEY = "<你的密钥>"
python -m migration_pipeline.run_formal_30_v4_timeout_diagnostic --server
```

密钥只存在环境中，不写入仓库。launcher 会先核对协议 live 哈希并打印非密钥配置，然后启动新的本地服务器。健康检查只能返回 provider/model，不证明已存在旧进程的超时；因此必须真正停止旧服务并用 --server 重启。若 8787 端口占用，不继续执行模型批次。

窗口 B 激活 cardmig、进入仓库根目录，先验证计划，再执行一次：

```powershell
python -m migration_pipeline.run_formal_30_v4_timeout_diagnostic --dry-run
python -m migration_pipeline.run_formal_30_v4_timeout_diagnostic --execute
```

--execute 会再次核对 live 哈希，并通过健康检查后启动独立批次；不会复跑原 28 个 completed 样本。两个样本都从原 Vue 重新生成，不接续旧 repair 步。上游调用可能接近 10 分钟，整批会更久。

## 记录与输出

- 配置：migration_pipeline/batch_configs/formal_30_v4_timeout_diagnostic_v1.json
- pipeline：data/experiments/pipeline/batches/formal_30_v4_timeout_diagnostic_v1/
- reports：data/experiments/repair_reports/batches/formal_30_v4_timeout_diagnostic_v1/
- summary：data/experiments/batch_reports/formal_30_v4_timeout_diagnostic_v1_summary.json
- Notebook：notebooks/02-migration-experiments/2026-11-02_formal_30_v4_timeout_diagnostic.ipynb

报告生成／repair 失败阶段、耗时、实际返回模型、轮数及可获得 token，异常请求用量缺失单列。健康检查、启动终端非密钥设置和服务器实际重启需由操作者确认；文件包不能独立证明运行进程配置。

原运行代码／源输入与旧冻结字节一致性、旧快照校验、完整单元测试和新批次 dry-run 结果随本文件封存。首次模型请求后保持本诊断的参数和实现不变；任何新修复或参数变化另建版本。
