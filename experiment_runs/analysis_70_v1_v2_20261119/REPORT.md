# 70 个组件跨版本问题覆盖分析

本报告保留三个批次及其重复任务，覆盖70个不同组件、72条终态记录。不是同一版本完整70项实验，不计算混合通过率；没有修改旧结论、重发模型调用或修改迁移实现。

## 批次与范围

| 批次 | 配置数 | 完成 | 通过 | 未通过／阻断 | 待运行 |
| --- | ---: | ---: | ---: | ---: | ---: |
| real_system_experiment70_v1_20261118 | 70 | 49 | 11 | 38 | 21 |
| real_system_experiment70_v2_generation_probe_20261118 | 2 | 2 | 0 | 2 | 0 |
| real_system_experiment70_v2_remaining21_20261119 | 21 | 21 | 1 | 20 | 0 |

v1 为未完成的49/70基线，后续21项没有补写到v1；MonitoringDashboard、TaskManager在v2重复运行，旧失败保留。两个v2批次的实现、模型、阈值、props及交互设置一致且样本不重复，合计23个复杂组件，1项通过；这一结果仍不是完整70项通过率。

实际模型调用 196 次；已知 Tokens 4,405,853。未知调用 0 次，返回用量完整。70次已执行初始评估均未直接通过；另两条v1输出截断任务没有初始评估。全部批次未配置代表性交互、未进行本轮人工验收。

## 高频发现

计数针对最后接受父版本的诊断，一个组件可涉及多类；不是独立缺陷数量，也不等于全部已确认误报。

| 检测代码 | 涉及任务 | 不同组件 | 分流 |
| --- | ---: | ---: | --- |
| `rendered_dom_mismatch` | 49 | 49 | 结构与控件 |
| `source_dynamic_assignment_unproven` | 28 | 28 | 源语义契约未证明 |
| `rendered_control_state_mismatch` | 14 | 14 | 结构与控件 |
| `target_browser_error` | 11 | 11 | 初始化与运行时 |
| `template_structure_mismatch` | 11 | 11 | 结构与控件 |
| `vue_this_state` | 5 | 5 | 静态语义或响应式 |
| `missing_prop_defaults` | 4 | 4 | 初始化与运行时 |
| `hidden_template_reactive_dependency` | 3 | 3 | 静态语义或响应式 |
| `nested_state_mutation` | 3 | 3 | 静态语义或响应式 |
| `source_computed_collection_not_landed` | 3 | 3 | 源语义契约未证明 |
| `dom_child_order_mismatch` | 2 | 2 | 结构与控件 |
| `lifecycle_behavior_not_landed` | 2 | 2 | 静态语义或响应式 |

## 主要结论

1. DOM差异49条任务：既有缺失节点、数值文本和错误子节点顺序，也有空class、value等属性差异。当前记录的差异行中，属性／序列化变化166行，缺失新增43行，文本变化12行，标签变化2行；这些是有界诊断行数，不是完整DOM编辑距离或独立缺陷数。不能把全部DOM失败当成评估误报，也不能只看视觉分数通过就放行。

2. 动态赋值契约未证明28条：主要拒绝涉及完整caller不匹配、键调用次数不一致、非普通声明状态键和未知this归属。BookmarkToggleCard的toggle表面上是源setter／emit包装的内联版本，值得专门检查分析器的有限等价覆盖；但必须同时核对值、事件、调用顺序和初始化，不据此全局豁免，也不恢复任意公开键承诺。

3. 初始化与运行时缺陷可独立解释部分失败：11条任务有target_browser_error，包含undefined.map、缺少initData、内联子组件保留Vue methods／props、data store被当数组等发现。它们与首次生成截断是不同问题，应按共同模式修复。

4. 修复并非完全没有效果：共185次候选门决策，接受92次；严格改善不等于最终全维通过。检测到9个与父版本哈希相同的候选，均应归入无效修复反馈；不能算作修复成功。

5. MonitoringDashboard最新候选通过语法，但在浏览器样式采集的300元素记录上限中断，未产生该候选完整评估。报告仍显示旧接受父版本的重复class语法诊断，不能把它当作最新候选全部状态。第一次修复与原代码完全相同；第二次已解除语法错误，后续问题被评估容量遮挡。

6. TaskManager三份候选都保留空 on-dragover 与括号式 s-for 别名错误。逐属性隔离可复现两个解析错误，原报告却定位到模板开头；两轮修复均无语法进展。最终142394 Tokens触发131072软停止线，是未修好之后的费用边界，不是首要缺陷。保持预算，不先增加额度。

7. TripItineraryPlanner的源基准被阻断：冻结浏览器证据显示源页无errors／warnings，却被拦截一个data:image/svg+xml;base64资源。它不是远程URL；当前不能仅据source_baseline_blocked判定Vue业务源码有错。需要独立审查自包含资源与安全拦截策略，同时保留真实外网请求阻断。

8. v2截断修正有效但不等于迁移成功：两个复跑的首次生成均正常stop，输出9130／9464 Tokens；输入Tokens分别从97198降到71385、89069降到64269（26.56%／27.84%）。这是同源不同输出预算与格式策略的观测，不能单独归因全部质量变化。

## 修复顺序与验收

先做P0属性级语法定位、源约束的通用修复以及评估容量／内嵌资源边界；再做P1 DOM分类、默认值与子组件初始化、语义契约证明；最后依据无效候选反馈调整调用策略。具体正反例与证据链接在prioritized_backlog.json。

每组先对冻结产物离线重放；保留真实失败和不支持边界，不降低阈值、不删事件／节点来通过。随后新建小规模真实回归。确认通用修复后，另行冻结统一版本完整70项批次；validation／test继续不运行。LangSmith、训练及数据库部署不作为本轮缺陷的替代修复。

## 可追溯文件

- `runs.json`：72条任务，保留最后接受父版本、最新候选、诊断与停止原因。
- `components.json`：70个组件到各版本任务的映射；不选最好结果替换旧结果。
- `error_groups.json`、`dom_triage.json`、`contract_triage.json`：分组及原始证据定位。
- `source_baseline_observations.json`：源页环境原始记录。
- `source_integrity.json`：全部输入、实现快照、样本导出包与控制文件哈希；生成前后复核。
- `analysis.ipynb`：仅加载上述真实数据，无伪造执行输出。
