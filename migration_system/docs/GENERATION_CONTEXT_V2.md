# 生成输入与输出预算 v2（2026-11-18）

## 原因与边界

真实系统实验 v1 在第 48 项 MonitoringDashboard、第 49 项 TaskManager 的首次生成阶段分别返回 `finish_reason=length`，输出均为 8192 Tokens，HTTP 均为 200。代码截断在 CSS 中间，尚未进入评估或修复。这不是数据库问题，也不能归为修复预算用尽。

v1 保留为**已完成 49/70，暂停，21 项未运行**。11 项通过、38 项失败或阻断；不把它写成已完成的 70 项实验。既有请求、结果、图片、失败收据、实现快照和 8192 上限不改写。当前源码已经升级，不能用新实现继续旧指纹的 v1；若要完成原配置基线，必须另行恢复其完整冻结实现及配置，不可绕过指纹检查。

## 通用修改

1. **仅改变 JSON 的序列化格式**：生产生成入口在调用原有固定版本的 Prompt builder 后，将末尾完整 SSM JSON 改为无缩进格式。所有键、值、字符串内部空白、模板、方法体、默认值、CSS、内联子组件和契约均保留；不把 SSM 换成源码，不截断字段。
2. **规则和示例不变**：原 builder、其哈希绑定、指令内容及 few-shot 选择逻辑保持原样。`direct` 基线不做 SSM 精简。生成证据 `prompt-selection.json.generation_context` 保存策略、SSM 哈希、指令哈希和前后字符／字节数。
3. **每次调用的输出上限提高到 32768**：`configs/system.toml` 中修改 `max_output_tokens`，生成及模型修复共同使用。保持 qwen-plus、温度 0、非思考、240 秒超时、最多 4 次调用／3 轮修复和 131072 已知用量停止线不变。停止线是软停止，不是硬账单上限；提高输出上限不代表每次一定输出满额。
4. **拒绝截断的逻辑保留**：`finish_reason=length` 仍不得成为有效候选，不自动拼接、续写或重试。未知调用仍需审查。更高上限不能保证全部复杂组件一定生成完整，也没有自动延长超时。

阿里云官方模型页列出 qwen-plus 最大输出长度为 32768（北京区）；本次查阅日期 2026-11-18：[qwen-plus 模型信息](https://help.aliyun.com/zh/model-studio/qwen-plus)。实际调用与结算以提供方响应为准。

## 无损重放结果

已验证 49 份 v1 的首次生成请求，并核验各样本导出包 SHA-256。原始证据目录保持只读。末尾 SSM 在前后 JSON 解析后具有相同内容哈希，生成规则与示例保留。

| 组件 | 原生成提示字符数 | 新字符数 | 字符减少 |
| --- | ---: | ---: | ---: |
| MonitoringDashboard | 386554 | 250319 | 35.24% |
| TaskManager | 361788 | 228711 | 36.78% |

49 份主生成提示合计从 3681212 减到 2423488 字符。**这些不是新模型的 Tokens，也不是费用或迁移正确率改善的证明**。没有发起新的模型调用。

检测到的长字符串重复在 `duplicates-audit.json` 中记录了哈希和字段路径，但本版**不删除这些重复语义内容**：方法定义、调用摘要和内联组件源码在不同分区可能承担不同职责。先采取无损格式压缩，避免引入新的引用解释协议或漏掉语义。完整 SSM 原件和评估输入不变。

专项测试共 57 次测试执行通过（生成上下文 5、批次控制器 6、生成边界 18、复用对照 5、安全预算 13、修复上下文 10）。扩展 `test_modular*.py` 首次执行 102 项、100 项通过：一项旧超限测试固定使用 9000 Tokens，已改为当前上限＋1，安全测试全量复跑通过；另一项界面冒烟仍等待 `.migration-main .text-button` 超时，独立复跑同样失败，已单列保留，没有修改前端或放宽断言掩盖失败。不能宣称扩展套件全部通过。详细结果见外部验证目录 `tests.json`。

外部实验目录中的证据：

- `experiment_runs/generation_context_v2_verification_20261118/report.json`
- 两个组件各自的 `messages.json`、`context.json`、`duplicates-audit.json`
- `experiment_runs/real_system_experiment70_v2_generation_probe_20261118/`：仅两个组件的新开发验证批次，已冻结、未提交任务。

上述外部目录仅是本仓库实验收集器，不是 migration_system 的运行依赖。

## 下一步真实验证

先在原来的 Worker 窗口 Ctrl+C，保留该终端已有的 `LLM_API_KEY`，从仓库根目录重启：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py migration-worker --config configs/mysql_multi_user.local.toml
```

然后在另一个终端启动**新的两项验证**，不是复用旧任务或伪装完整 70 项重跑：

```powershell
& migration_system/.venv/Scripts/python.exe experiment_runs/run_experiment.py run --execute --batch real_system_experiment70_v2_generation_probe_20261118
```

控制器须找到匹配新实现的 Worker 才提交。全 70 个实验组件仍全部排除为 few-shot 来源；每个样本使用新任务和新幂等键，验证集／测试集不运行。两个组件均收集完整真实证据后再决定是否另建完整 v2 批次，不提前宣称质量通过。

若 Worker 仍旧，控制器会暂停而不提交；重启后可用相同命令恢复，已完成任务不自动重跑。不要执行 v1 的恢复命令，也不要在验证期间修改冻结源码或配置。
