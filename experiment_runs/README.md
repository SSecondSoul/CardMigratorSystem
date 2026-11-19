# 当前真实迁移系统的实验批次

综合分析已生成：[70 个组件跨版本问题覆盖报告](analysis_70_v1_v2_20261119/REPORT.md) 与 [分析 Notebook](analysis_70_v1_v2_20261119/analysis.ipynb)。保留 72 条任务到 70 个组件的映射，包含分版本统计、原始证据校验和通用修复优先级，不计算混合通过率。可只读重算（输出内容不同则要求新建分析版本）：

```powershell
& migration_system/.venv/Scripts/python.exe experiment_runs/analyze_coverage.py
```

2026-11-19：按用户确认，新增 [剩余 21 项补充批次](real_system_experiment70_v2_remaining21_20261119/README.md)。与 v2 两项验证采用相同冻结实现和配置，补充 v1 未运行的 21 个不同组件；保留 v1 的 49 项和 v2 两项重复结果，不拼接为统一版本 70 项通过率。当前不要改迁移规则，先完成问题覆盖。

2026-11-18 生成输出检查后：v1 保留在 49/70（11 通过、38 未通过或阻断、21 未运行），没有混入新配置。当前新建 `real_system_experiment70_v2_generation_probe_20261118` 仅含两个截断组件，配置已冻结但未调用模型。修改与重启／验证命令见 [生成输入与输出预算 v2](../migration_system/docs/GENERATION_CONTEXT_V2.md)。不要用当前新实现恢复旧 v1。

仅运行 `experiment_dataset/experiment` 的 70 个组件（简单 24、中等 23、复杂 23），不运行 validation/test。每批单独目录，不覆盖数据集、历史结果或此前网页任务。

## 执行方案

1. 校验全部实验 Vue 哈希，冻结当前系统代码、生成／修复提示、依赖锁、模型／浏览器配置、样本顺序和源码副本。
2. 使用真实系统的 `Service`／`MigrationService`，逐个提交给当前在线且版本一致的云库 Worker。策略 SSM＋修复，最多 3 轮；默认 props、无预设交互场景，不将交互未测试计为通过。不会读取数据集中参考 San 作为模型输入。
3. 每个样本新建任务；中断恢复只查本批幂等键和任务 ID，不重新生成已经完成的结果，不自动重发结果未知的模型调用。模型、每次输出和每样本用量停止线沿用冻结配置，最多 280 次调用；这不是硬账单上限。
4. 将完整报告、所有候选 San、SSM、提示／修复上下文、请求／响应收据、浏览器证据、截图、差异图和 SHA-256 按样本复制到本批目录。云库原记录保留。
5. 自动生成逐样本 CSV、总体／分复杂度统计、错误分组和失败报告。完整跑完基线后，区分真实迁移缺陷、评估误报和环境问题，再集中做通用修复；先离线重放冻结失败，再另建 v2 回归，不覆盖 v1。

本批采用现有受信任本机批处理 CLI 的无个人账号任务模式，不修改管理员额度或个人任务记录。云库中仍是实际 `migration_jobs`／`migration_model_calls`／`migration_files`；管理员可通过任务 ID 或 API 的 `scope=all` 查阅，默认“我的任务”列表不包含这些 CLI 实验。不是开发夹具或假模型。

## 命令

从仓库根目录执行。先准备一次，再运行：

```powershell
& migration_system/.venv/Scripts/python.exe experiment_runs/run_experiment.py prepare
& migration_system/.venv/Scripts/python.exe experiment_runs/run_experiment.py run --execute
```

查看状态无需模型密钥，也不提交任务：

```powershell
& migration_system/.venv/Scripts/python.exe experiment_runs/run_experiment.py status
```

`run` 自身不读取模型密钥，调用由已有真实 Worker 完成。只有匹配冻结版本的 Worker 在线才继续。代码／配置变化、Worker 长时间离线、未知调用或缺少凭据会暂停，不把未完成样本排除统计。普通组件迁移失败会记录并继续下一个。

单独准备针对性开发验证时可在 **prepare** 指定实验样本 ID，不能在已有批次运行时临时改选择：

```powershell
& migration_system/.venv/Scripts/python.exe experiment_runs/run_experiment.py prepare --batch 你的新批次名 --samples MonitoringDashboard TaskManager
```

针对性批次的分母为实际选择数，不是 70；全部 70 个实验组件仍排除为 few-shot 来源。不加 `--samples` 的新 prepare 仍为完整 70 项。prepare 仅校验／冻结本地文件，不写云库、不调用模型。

## 输出

```text
real_system_experiment70_v1_20261118/
  protocol.json                 固定实验配置与实现指纹
  dataset_manifest.json         原始实验集清单
  implementation/               当前系统与内部引擎实现快照
  implementation_sha256.json    实现快照哈希
  inputs/                       70 个 Vue 冻结输入
  checkpoint.json               本批任务 ID 与恢复进度
  summary.json                  总体及分复杂度统计
  sample_results.csv            每个样本一行，包含待运行样本
  failure_groups.json           错误代码、类别与样本对应
  FAILURE_REPORT.md             失败汇总与通用修复下一步
  samples/<序号_样本>/
    report.json                 云库终态报告导出
    artifacts/                  全部登记产物，包含各轮评估图片
    SHA256SUMS.txt               该样本导出文件完整性
```

运行期间不要修改迁移源码、规则、Prompt 或系统配置；前端文案可独立修改，但不影响本轮评估口径。不要启动第二个批次控制器。需要停止追加任务时，在批次目录创建名为 `STOP` 的空文件；当前已执行任务不被强制取消。恢复前先核对 `pause_reason`，处理问题或明确移除 STOP，然后重用同一个 `run --execute`，不要重新 prepare。

原始提示、响应和源码属于实验资料，不公开上传。数据库密码、模型密钥和 DPAPI 文件不会复制进实验目录。
