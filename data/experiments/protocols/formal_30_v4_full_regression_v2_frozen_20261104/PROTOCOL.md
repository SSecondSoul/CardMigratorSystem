# formal v4：最终规则完整 30 样本开发回归（第二批）

冻结日期：2026-11-04（Asia/Shanghai）。批次 formal_30_v4_full_regression_v2。
v2 是本次完整回归的第二批，不是旧 formal_30_v2，也不是独立测试集。

## 范围、输入与停止规则

沿用原 v3／首次 v4 完整回归的同一份 30 项、原顺序和逐字节一致的 Vue；简单／中等／复杂各 10 项。
TaskManager、MonitoringDashboard 与其余 28 项全部重新提取 SSM、生成一次并在本轮候选上修复。
已人工通过的派生 San 仅作独立历史证据，不作为模型参考答案、输入、分数或跳过依据。
source_split 文件名中的 untouched_holdout 只是历史名称；这 30 项已经用于开发，明确为重复开发回归，不是独立未见测试。

使用全新默认 pipeline、repair reports、summary checkpoint。不加 --force，不传 --sample-id 或旧输出路径。
同一代码版本下中断可用原命令恢复待处理项；不能挑选重跑来替换已记录失败或异常。
发现问题先冻结已观察结果，再在后续版本修复；运行期间不修改冻结代码或覆盖旧 SHA 清单。
代码变化需另建协议，不混用本批后续样本的运行版本。

## 固定预算与环境

每样本最多 3 次 LLM repair，repair_policy=bounded_prepass_v1、semantic_rule_set=residual_v2。
每次模型调用前最多 4 步确定性处理，每样本累计最多 12 步；按 LLM calls 计费轮数，不等同旧版本 3 次混合尝试。
qwen/qwen-plus，客户端 temperature=0.2，LLM_TIMEOUT=600，生成／修复客户端各 660 秒。
通过专用 launcher 在新进程导入设置前固定 API URL、端口、关闭 debug 和上述超时。
没有固定模型或渲染随机种子，服务商实际版本与旧进程是否停止不能由文件哈希独立证明。
不在协议或仓库保存 API key。

## 系统与证据

本步骤不改生产规则，只冻结当前有效实现、配置和运行工具。
冻结前校验原 v3 原始结果 234 文件、首次 v4 完整结果 359、最新单样本原始结果 364、持久化闭环包 16、TaskManager 候选包 13。
当前 317 项代码／输入 inventory 与最后通过的离线闭环一致，30 份 Vue 逐项匹配最初冻结输入。
两份用户验收记录和精确候选另行复制为历史证据；不把人工修复计作原自动端到端成功。
重新执行完整本地测试、无模型持久化回放和 30 项 dry-run；随后校验本协议 frozen/live 哈希。
生成、修复、验证器、门禁、规则、预算和超时均与早期版本存在变化，不作 Prompt 单因素因果结论。

## 结果报告口径

保留旧 v3：18/30 自动通过、9 评估失败、3 执行异常；首次 v4：25/30、3 评估失败、2 执行异常。
本批必须报告 30 项总分母、完成项通过率、每层 10 项分母、首次通过、确定性处理次数／接受拒绝、LLM 次数、token、耗时、异常。
逐样本配对区分保持通过、回归失败、改善通过、仍未通过，执行异常另列，不继承旧结论。
保留所有初始候选、模型和确定性候选、拒绝与回退。不要挑较高 DOM 分数替换最终结果。
自动通过、人工通过和独立测试分列；本批自动通过不等于所有交互已验证。
未披露早期接触的候选池不得改称独立测试；后续探索性评估继续等待本批结果。

## 操作者执行

项目根目录，cardmig 环境。先在旧服务器窗口 Ctrl+C 停止旧服务。

窗口 A：

```powershell
$env:LLM_API_KEY = "你的密钥"
python -m migration_pipeline.run_formal_30_v4_full_regression_v2 --server
```

保持 A 运行，在窗口 B 启动全部 30 项：

```powershell
python -m migration_pipeline.run_formal_30_v4_full_regression_v2 --execute
```

两个入口先做新协议 live 校验；失败停止，不能修改校验清单绕过。
仅看计划可使用 --dry-run。运行完成后先反馈结果，不马上 force 或修改规则。
本批原始结果封存入口（由后续检查调用）：

```powershell
python -m migration_pipeline.freeze_formal_30_v4_full_regression_v2_results
```

当前两个测试页继续保留已验收 MonitoringDashboard 候选；不会因本批计划而切换。
准备／冻结不调用模型、不启动服务器，不意味着新生成已通过。原单样本与全批历史均不改写。
