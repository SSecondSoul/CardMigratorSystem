# 通用修复 v7：控件属性与恢复运行后的候选门

2026-11-19。v7 是本轮修复迭代号，不是公开实例代理 v7，也不是新的模型实验批次。

## 已验证的结果

- 真实模型 v3 批次仍为 **15/70**；本轮没有调用模型或修改历史报告。
- 对 70 项冻结产物做通用规则复核，有效离线通过从 v6 的 **28/70 → 33/70**；原通过无回退，仍有 **37 项未解决**。
- 新增离线通过：DocumentApprovalFlow、OtpCodeInput、SurveyBranchForm、TemperatureDial、TextLengthGauge。它们是规则覆盖结果，不是组件名称白名单。
- **205 项关联回归通过**，包含真实浏览器正例及拒绝误修的反例。仓库外独立副本的真实 SSM AST、持久化 LangGraph、API／前端／下载及浏览器检查通过；模型明确使用记录响应替身，云调用 0，原数据库未更新。
- 核对 **7,166 个历史文件**，哈希不变。40 项复用 v6 相同代码的冻结捕获并明确标注，25 项保存新浏览器证据，其余为未变父版本／无完整产物；这不是所有组件的当前运行时全量重拍。

## 修改位置与边界

| 问题 | 实现 | 保留边界 |
| --- | --- | --- |
| Vue `:value` 同时设置原生 property 和 attribute，而 San 通常只设置 property | `browser/attribute-syntax.mjs` 对源匹配的普通 input／textarea 简单状态绑定补充原生 `VALUE` 属性反射；空值移除 attribute，原有 value、双向绑定和事件保留 | 不套用到 v-model、select、checkbox/radio/file、动态类型、未知表达式或 SVG |
| 实现别名被算成额外模板绑定 | `browser/evaluate.mjs` 仅在 VALUE 与 value 表达式完全相同时合并其模板表示 | 不删真实 DOM 属性差异，不忽略 live 控件状态；真实 DOM、清空、输入、表单 reset 均验证 |
| 把 computed 值的 `.filter()`／`.map()` 等也当成 getter 调用 | `engine/.../bounded_semantics.cjs` 对已声明源 getter 的直接只读集合消费修正为 `this.data.get(name)` | getter 本身的调用、写入、mutator、动态／optional 调用、未知源声明继续拒绝 |
| 补齐默认值恢复运行，却被首次显现的控件位置诊断拒绝 | `adapters/browser.py` 用现有源 prop 默认值规则生成整份代码指纹；`stages/dom_comparison.py` 验证其与候选逐字节一致；`stages/evaluation.py` 只细化该诊断谱系 | 源／props／actions／运行时变化、缺失旧证据、额外模板／方法／样式改动、新错误、原通过维度回退仍拒绝 |

恢复门不是“运行恢复就自动接受”。它要求整份候选恰好是已证明的默认值规则产物，且 runtime 从 fail 到 pass、控件值与数量匹配、DOM 有进展。**结构位置错误及 structure fail 继续保留**。

真实 BatchRenamer、PollResults、GradebookMatrix 的隔离默认值规则测试均恢复 runtime，允许继续修复，但 0 项被算为完整迁移通过。MediaReviewStudio 补齐默认值后仍有初始化错误，照常保留失败。完整组合提案如果还包含额外变动，不满足这个窄证明，仍可能被拒；不能把隔离正例冒充生产全路径已经闭合。

## 仍需继续处理

1. **依赖 props 的 data 初始化时序**。San 在 initData 合并传入数据并创建 store 后计算 computed，随后才进入 inited。源 data 中 clone 集合并派生选择值，不等于先给集合 null、再在 inited 初始化。本轮只定位了该根因，没有随意加 `|| []` 或读取尚不存在的 `this.data` 来掩盖它。
2. select 初始空选中、boolean 控件属性及真实结构／控件差异仍未闭合。
3. 跨方法动态键流、响应式写入、未知 getter／内联组件、语法及事件等继续逐项记录，未降低质量阈值。
4. TaskManager 的未知调用没有产物，仍未自动重试，也不当作零费用。

生成仍为完整 SSM＋模型；这轮没有改生成／修复 Prompt，没有整体源 AST 确定性生成、公开实例代理接入、预算扩张或组件名特判。用户 API／Worker 尚未重启，不能把旧服务新建的任务说成 v7。当前不建议直接再启动 70 项付费模型重跑。

## 记录

- [完整离线报告](../../experiment_runs/composed_v7_review_20261119/REPORT.md)与 [Notebook](../../experiment_runs/composed_v7_review_20261119/analysis.ipynb)。`remaining.json` 保留全部 37 项及诊断。
- 根目录 `experiment_runs/composed_v7_verified_replay_20261119/`：规则、候选、门禁、截图、复用来源与实现快照；原串行预检目录有 STOPPED 标记，不当成完整批次。
- 根目录 `experiment_runs/default_recovery_v7_20261119/`：4 个真实失败产物的隔离规则验证，恢复 runtime 3 个、完整迁移新增 0 个。
- `docs/verification/2026-11-19_general_repairs_v1/test-results-composed_v7_verified.json`：205 项关联回归。
- `var/refactor-verification/composed_v7_20261119.json`：仓库外独立运行验证，模型为明确替身。
