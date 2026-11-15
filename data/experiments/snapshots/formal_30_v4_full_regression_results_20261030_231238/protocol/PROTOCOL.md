# 当前 v4：完整 30 样本开发回归协议

日期：2026-10-30（Asia/Shanghai）；批次 `formal_30_v4_full_regression`。

## 范围与口径

使用原 v3 的同一份 30 样本列表、顺序和逐字节一致的 Vue 输入，运行当前 v4 的 SSM、generation、repair、验证器及渲染器。简单／中等／复杂各 10 项，每样本最多 **3 轮 repair**。这是已接触样本的完整开发回归，不能当作独立未见测试。

本次直接检验最终 v4 代码在所有 30 项上的自动迁移表现。TaskManager 最近单样本运行使用 6 轮，本批只用 3 轮，不能预先沿用其通过结论。旧 v3 结果为 18 通过、9 失败、3 执行错误；配对比较保留原结果，且由于评估器也发生变化，差异不能全部归因于 Prompt。

冻结包内 `frozen/` 为本次磁盘代码与输入基线。已提交及未提交的有效运行文件都会复制；Git HEAD 单独不代表运行版本。参考 San 不进入生成／repair 请求。v5 探索性评估等待本批完成；若本批后又改动实现，v5 须另建冻结版本。

## 参数和结果

- Provider `qwen`、模型 `qwen-plus`、温度 `0.2`、`LLM_TIMEOUT=240`；generation／repair 客户端超时各 300 秒。
- 保留 `--include-state`，默认健康检查启用；不传 `--sample-id`，不传 `--force`。
- 报告 30 项分母的通过率、正常完成项通过率、分层结果、初次通过、repair 轮数、token 与执行异常；人工交互结果单列。
- 对照旧结果逐样本报告“保持通过／回归失败／改善通过／仍未通过”，执行异常另报。自动通过不代表全部浏览器交互正确。
- 全批保持同一版本；异常恢复使用原命令和 checkpoint。不能挑选重跑替换失败结果；发现缺陷后先冻结原结果，再在后续版本修复。

## 操作者执行

先确认已重启的本地服务器加载冻结代码，使用 `qwen-plus`。在旧服务器终端 Ctrl+C 后，重新设置环境并启动：

```powershell
$env:LLM_PROVIDER = "qwen"
$env:LLM_API_KEY = "<你的密钥>"
$env:LLM_MODEL = "qwen-plus"
$env:LLM_TIMEOUT = "240"
python -m local_server.app
```

在另一终端验证文件，然后启动整批：

```powershell
python data/experiments/protocols/formal_30_v4_full_regression_frozen_20261030/verify_protocol.py --live
python migration_pipeline/run_batch_pipeline.py `
  --config-file migration_pipeline/batch_configs/formal_30_v4_full_regression.json `
  --include-state
```

中断后用同一批处理命令恢复。默认输出分别为 `data/experiments/pipeline/batches/formal_30_v4_full_regression/`、`data/experiments/repair_reports/batches/formal_30_v4_full_regression/` 和 `data/experiments/batch_reports/formal_30_v4_full_regression_summary.json`。

## 本次已验证的边界

冻结脚本执行旧协议完整性校验、全量单元测试及本批 dry-run，原始输出附在此目录。服务器加载版本须由重启操作确认；文件哈希不能证明旧进程已加载相同代码。此冻结脚本没有调用模型。
