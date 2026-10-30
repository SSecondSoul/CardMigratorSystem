# v4 开发回归收尾与下一轮探索性评估准备（2026-10-30）

## 证据口径

- 历史 `formal_30_v4_targeted` 和 `formal_30_v4_deferred_regression` checkpoint 分别为 7/7、5/5 自动通过，合计 12/12；它们是反复调试后的**开发回归终态**，不是未见样本通过率。原始口径和逐样本谱系见 [`2026-10-25` 收尾报告](../formal_30_v4_development_closeout_20261025/REPORT.md)及其 [`summary.json`](../formal_30_v4_development_closeout_20261025/summary.json)。该旧报告不作追溯修改。
- 此后规则、Prompt 和评估器继续变化，也产生失败探针、自动失败、事后候选和人工复核。不能把不同时间的终态结果相加为新的 12 样本独立实验，也不能删除失败链。四个高优先级缺口和其他八个样本的审计基线见 [`gap_matrix.csv`](../formal_30_v4_generalization_gap_audit_20261027/gap_matrix.csv)。
- 最新 TaskManager 开发回归 `formal_30_v4_task_manager_premount_guard_regression_v1` 为 1/1 自动通过，修复 6 轮，最终静态／视觉错误均为空，结构相似度 0.9889，生成 97,242、修复 145,866、合计 243,108 tokens。原始数据先冻结于[自动结果快照](../../snapshots/formal_30_v4_task_manager_premount_guard_regression_v1_TaskManager_automatic_pass_20261029_232535/manifest.json)，14 个 payload 校验通过。10 月 30 日用户又确认该最终 San 人工通过，[人工快照](../../snapshots/formal_30_v4_task_manager_premount_guard_manual_pass_20261030_141612/manifest.json)的 8 个 payload 校验通过；未提供逐场景浏览器日志，交互自动评估为 `null`。
- 该最终 San 与前一人工通过的离线候选 SHA-256 不同。六轮产物均无被新规则处理的父组件挂载前同值写入，repair history 也无 `removed_parent_premount_identity_writes` 标记；因此**不能把这次成功归因于该规则实际触发**。规则只在冻结旧候选及边界测试上验证过，不得宣称跨组件泛化有效。

## 当前实现与版本边界

最近一次 TaskManager 回归的[预运行快照](../../snapshots/formal_30_v4_task_manager_premount_guard_regression_v1_pre_run_20261029/manifest.json)记录了配置、源码哈希、221/221 单元测试、dry-run 和 26 份实现／测试 payload。2026-10-30 对照当前工作区，这 26 份 payload 字节哈希均一致；快照内 31 个 payload 的 SHA-256 也已校验。它是**该次运行的文件版本证据**，不是 Git 提交或远端推送：冻结时 `worktree_clean=false`，Git HEAD 单独不足以表示实验代码。快照也不能证明运行中本地服务器进程的已加载代码恰好等于磁盘文件；正式下一轮须另行记录服务器进程、配置、模型和启动时间。

现有 [`formal_30_v3` 协议](../../protocols/formal_30_v3_frozen_20261022/PROTOCOL.md) 已在模型调用后禁止修改算法和重新解释结果。新的 v4 修复不能回填 v3 结果；若进行下一轮评估，必须另建协议、批次、输出路径和预运行快照，并明确它的探索性性质。

## 后续样本池初筛，不等于正式冻结

[`formal_30_v3_untouched_holdout.json`](../../../datasets/splits/formal_30_v3_untouched_holdout.json) 中 `remaining_development` 有 31 项：简单 11、中等 10、复杂 10。与该文件的 v3 已选 30 项、父划分的 v1 独立测试样本及 9 个 pilot 样本按 ID 求交均为 0。只读审计的 26 份批次配置、26 份 batch summary 和 123 份 snapshot manifest 中，未发现这 31 个 ID 作为运行样本；另对 262 份迁移脚本、实验分析、Notebook 与测试页按精确 ID 搜索，没有命中。这只能说明目前未发现它们被作为实验样本使用，仍不能排除手工或外部记录中的暴露。

对 154 份 repair report／probe 文本按这 31 项的完整 Vue 源路径再搜索，命中数仍为 0。上述 262 份文本扫描发生在本收尾目录创建前，因此不包含本报告。路径审计则发现早期 `pilot_9_v6_full_pipeline_20261013_134016/inputs/` **批量复制了全部 100 份数据集 Vue 源码，其中包含这 31 项**。`stock` 和 `CountdownCard` 的快照输入与当前数据集文件 SHA-256 相同；pilot 批次配置／结果并未将它们列为运行样本。批量封存意味着源码曾在仓库证据包中可见，不能仅凭配置零命中就宣称“绝对未见”；另一方面，它本身也不是模型收到这些源码的证据。新协议应精确定义“未参与模型请求或调参”的判定与可核验证据，而非笼统称“从未出现”。审计数值与 SHA-256 另见 [`AUDIT.json`](AUDIT.json)。

**2026-10-30 补充审计，更正上述“精确 ID 零命中”的适用范围：** 用户表示无法确认是否曾手工用候选组件调参。以候选 `component_name`（而非 `id`）作边界匹配，在三份早期数据集验证 Notebook 中找到 **23/30** 个候选名称：[`09-02`](../../../../notebooks/01-data-exploration/2026-09-02_vue_san_batch_validation_issues.ipynb) 4 个、[`09-04`](../../../../notebooks/01-data-exploration/2026-09-04_vue_san_batch_30_validation_issues.ipynb) 5 个、[`09-10`](../../../../notebooks/01-data-exploration/2026-09-10_vue_san_batch_39_validation_issues.ipynb) 14 个；其中 `ComparisonTable`、`CartSummary`、`RecipeScaler`、`ApiContractWorkbench` 等有缺陷／修复文字记录。复现命中清单可运行 [`audit_formal_30_v5_candidate_exposure.py`](../../../../migration_pipeline/audit_formal_30_v5_candidate_exposure.py)。这些记录属于数据集生产与验证，**不能仅凭被点名就断言这些组件曾进入迁移模型请求或 Prompt 调参**；但也不能再说候选样本“从未被人工查看”。此前的 ID 零命中仅反映命名方式不匹配，不能作为无暴露证明。未被这三份 Notebook 点名的 7 项是 `CountdownCard`、`focus_card`、`hydration_card`、`weather_card`、`stock`、`project_overview`、`smart_dashboard`；这也不等于证明它们未被其他方式接触。严格“独立未见”的资格目前待判定。

用户已在首次模型调用前确定下一轮规模为 **30 项，简单／中等／复杂各 10 项**，每样本最多修复 **3 轮**（沿用 v3 上限）。[`prepare_formal_30_v5_candidate_split.py`](../../../../migration_pipeline/prepare_formal_30_v5_candidate_split.py) 复用 v3 的确定性特征覆盖贪心规则，先比较新增特征数，再比较特征总数，最后按父划分原始顺序打破平局；不使用任何迁移结果。生成的[候选清单](../../../datasets/splits/formal_30_v5_candidate_20261030.json) 最终 SHA-256 为 `5cb5cda78d054feb3c0f7069db886131af8d99a0da671d4c8e8a1323dd80f3db`，排除的唯一简单样本是 `quote_card`。相应的[批次配置草案](../../../../migration_pipeline/batch_configs/formal_30_v5.json) 最终 SHA-256 为 `a5c76795a44751e917c84948efbb3757200e04daf213f4d381113e948a7bba27`，无特征标签的 `stock` 省略可选 `coverage_focus`。这两个哈希相对最初候选版本发生变化，**仅因为补充了探索性证据边界与配置描述；样本列表、顺序和修复轮数没有改变**。最终配置已重新通过批处理 `--dry-run`，规范化配置指纹为 `664a7ff9da1a7d12c45eae9c885b62fa529ec2ac5f192242b6c4b2da8944c011`。若与既有 v1/v3 结果并列，只能描述为不同样本、不同证据等级的描述性比较，不能写成同样本配对提升或严格独立复验。

用户随后选择**保留现有 30 项，但仅作披露早期接触的探索性评估**。因此不再以它们主张严格独立未见的泛化通过率，也不从本轮结果修改已冻结的 v1/v3 结论。后续仍须冻结代码／Prompt／评估器／本地服务器运行环境、评估与异常处理规则；候选清单不是可执行的冻结协议，也没有触发新模型请求。

## 当前停点

本文件是开发收尾和探索性评估准备记录，不是新冻结协议。候选 30 项已预选并记录来源哈希；因已知早期文档接触和用户无法确认手工调参史，**不得作为严格独立测试集执行或报告**。本轮未读取其业务实现用于修改规则，未发起新模型调用，未提交／推送代码。下一道门槛是验证最终配置、锁定实现与环境、建立明确标注“探索性”的协议并预运行校验。
