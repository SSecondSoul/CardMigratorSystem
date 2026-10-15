# formal_30_v1 正式实验协议（冻结版）

冻结日期：2026-10-15（Asia/Shanghai）  
协议 ID：`formal_30_v1_frozen_20261015`  
代码基线：`4c18a4b6a908139a285648be2f81b7ec8a75196c`

## 1. 实验目的与数据边界

本实验评估 Vue 2 单文件组件经 SSM、LLM 生成、静态校验、DOM 结构评估和最多三轮 repair 后迁移为 San 组件的效果。

- 数据集共 100 对组件。
- 开发集 70 个：9 个 pilot 调优样本和 61 个未进入测试集的样本。
- 独立测试集 30 个：simple、medium、complex 各 10 个。
- pilot_9_v2-v6 使用过的 9 个样本不得进入独立测试集。
- 30 个测试样本的原始 Vue 是正式输入。
- 配对的参考 San 仅作为封存答案；正式自动运行结束前，禁止将其用于 prompt、repair、规则调整、样本剔除或人工纠错。

## 2. 固定系统与参数

- LLM provider：`qwen`
- LLM model：`qwen-plus`
- API：DashScope OpenAI-compatible chat completions 默认地址
- temperature：`0.2`
- generation timeout：`300` 秒
- repair timeout：`300` 秒
- LLM HTTP timeout：`120` 秒
- 最大 repair 轮数：`3`
- DOM structure similarity 阈值：`0.95`
- DOM text similarity 阈值：`0.8`
- 健康检查：启用
- 报告状态：使用 `--include-state` 保留完整过程证据
- 模型 API 不支持固定 seed，因此需将模型随机性列为实验局限；不得通过挑选多次运行中的最佳结果消除随机性。

## 3. 主评估口径

所有 30 个样本均进入主评估，禁止事后删除失败样本。报告至少包含：

1. 初次生成通过率与最终通过率；
2. simple、medium、complex 分层通过率；
3. repair 后转为通过的样本数、总轮数和平均轮数；
4. generation、repair 与总 token；
5. stop reason、静态错误码与视觉错误码分布；
6. execution error 单独统计，不得算作通过，也不得从分母移除；
7. 结构、标签和文本相似度等原始指标保留在逐样本报告中。

`final_passed` 是自动主结果。当前 formal 配置未预置确定性交互场景，因此自动通过不能表述为“全部交互正确”。

## 4. 人工验证口径

自动运行完成后，再对下列预注册的 9 个代表样本进行真实浏览器人工对照，每个复杂度 3 个：

- simple：`password_strength_meter`、`session_timeout_notice`、`delivery_phase_card`
- medium：`poll_results`、`image_crop_controls`、`attendance_roster`
- complex：`inventory_batch_manager`、`media_review_studio`、`energy_load_scheduler`

人工验证记录初始渲染、主要状态变化、动态样式、禁用状态和核心交互。人工结果作为次级结果单独报告，不覆盖自动结果，也不得据此修改本批输出后重新计分。

## 5. 冻结与偏差规则

正式运行开始后，以下内容不得改变：测试样本、Vue 输入、SSM 提取器、generation/repair prompt、validator、renderer、相似度阈值、模型、temperature 和最大 repair 轮数。

- 网络中断、限流或服务进程退出属于基础设施异常。可用同一命令从 checkpoint 继续，必须记录中断与恢复时间。
- 不得使用 `--force`，避免覆盖已完成样本并引入选择性重跑。
- 不得只重跑失败样本来替换正式结果。
- 如果发现算法或评估器缺陷，本批按原协议保留结果；修复后必须建立新的配置和协议版本，例如 `formal_30_v2`。
- 任何不可避免的协议偏差都必须写入最终报告，说明原因、时间和影响，原始结果不得删除。

## 6. 正式运行命令

先在一个 PowerShell 终端配置密钥并启动服务（密钥不得写入仓库）：

```powershell
$env:LLM_API_KEY="<secret>"
$env:LLM_PROVIDER="qwen"
$env:LLM_MODEL="qwen-plus"
python -m local_server.app
```

在另一个已激活 `cardmig` 环境的 PowerShell 终端运行：

```powershell
python migration_pipeline/run_batch_pipeline.py `
  --config-file migration_pipeline/batch_configs/formal_30_v1.json `
  --include-state
```

若发生可恢复的基础设施中断，使用完全相同的命令继续。checkpoint 会跳过状态为 completed 的样本。

## 7. 固定输出位置

- 生成代码：`data/experiments/pipeline/batches/formal_30_v1/`
- 逐样本报告：`data/experiments/repair_reports/batches/formal_30_v1/`
- 汇总 checkpoint：`data/experiments/batch_reports/formal_30_v1_summary.json`
- 人工验证记录：应新建在 `data/experiments/manual_validation/`，不得修改自动报告。

## 8. 完整性校验

正式运行前执行：

```powershell
python data/experiments/protocols/formal_30_v1_frozen_20261015/verify_protocol.py --live
```

只有协议包校验和与 live 文件均通过，才允许开始正式实验。
