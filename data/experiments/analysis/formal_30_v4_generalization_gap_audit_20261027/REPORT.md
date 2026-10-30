# formal_30_v4 开发问题通用化缺口审计（2026-10-27）

## 口径与证据

本审计覆盖 12 个**已复用的开发样本**，不是新一轮迁移、独立测试或正式协议冻结。原批次的 12/12 是历史自动 checkpoint；用户最终检查的 12 个 San 版本中，8 个为原冻结自动产物，4 个为事后修复候选。两种“通过”不能合并成原批次的人工通过率。样本选择、文件哈希及边界见[开发人工结案快照](../../snapshots/formal_30_v4_development_manual_closeout_20261027/manifest.json)、[人工验证记录](../formal_30_v4_development_closeout_20261025/manual_validation.json)和[结案报告](../formal_30_v4_development_closeout_20261025/REPORT.md)。本审计对照当前工作区中的 `local_server/api/evaluation_routes.py`、`migration_pipeline/utils/repair_prompt.py`、`migration_pipeline/stages/validate.py`、`migration_pipeline/stages/repair.py` 及其 104 项现有回归测试；结案快照留存了审计前的这些代码版本。

下表的“通用覆盖”只说明当前代码存在相应规则、测试或既有开发复跑证据，**不等于**新流水线已经从原输入自动重现事后候选。机器可读取的逐样本条目见 [gap_matrix.csv](gap_matrix.csv)。

审计后实施的第一条通用规则 G1 单独记在[实现记录](IMPLEMENTATION_LOG.md)；本表保留实施前的缺口判断，以便论文区分“发现问题”和“后来补规则”。

| 样本 | 主要问题发生阶段 | 通用覆盖及未闭环点 | 状态 |
| --- | --- | --- | --- |
| `CourseModuleAccordion` | 生成、校验 | 渲染方法的响应式参数与 DOM 子节点顺序已增设通用检查；定向复跑和人工检查通过。 | 已在开发复跑覆盖 |
| `SchemaMappingWorkbench` | 校验、生成 | 排除 `sourceKey` 等属性名误判，并约束 select 的 disabled 条件不能吸收相邻按钮条件；定向复跑通过。 | 已在开发复跑覆盖 |
| `IncidentResponseBoard` | 评估器 | 私有定时器与双别名循环的误判已修正；定向复跑通过。 | 已在开发复跑覆盖 |
| `RuleBuilder` | 生成、校验、修复 | prop 默认值和 Data-store 解构已有检查；重复 `class` 已有边界化通用合并及测试。但原自动产物的人工样式检查失败，通用合并尚无新的流水线自动产出/人工验收。 | 待端到端复跑 |
| `HabitWeekTracker` | 评估器 | 双别名循环渲染已修正；定向复跑通过。 | 已在开发复跑覆盖 |
| `PlaybackQueue` | 评估器 | 循环 index 的作用域和 disabled 比较已修正；定向复跑通过。 | 已在开发复跑覆盖 |
| `AnalyticsDashboard` | 生成、校验、运行时、视觉 | 非法外部 `require`、子组件 Data-store、computed 实例方法、内联事件及 Math/style 表达式已有通用约束。但三次自动通过均被浏览器检查否决；最终视觉修复是样本专用重放候选。 | 高优先级，待端到端复跑 |
| `AccessMatrix` | 评估器 | 静态与动态 class 合并后的比较已在冻结文件上重放验证；旧 checkpoint 的指标仍保留旧评估口径。 | 已在开发重放覆盖 |
| `LocalizationWorkspace` | 生成、校验 | 对象式 class 绑定已增设通用拒收规则和 Prompt 约束；复跑及人工检查通过。 | 已在开发复跑覆盖 |
| `TripItineraryPlanner` | 生成、校验、修复 | 响应式依赖、循环键与结构约束已随 v4 定向修复复跑通过。 | 已在开发复跑覆盖 |
| `TaskManager` | 生成、校验、修复、运行时 | 外部依赖、computed 上下文、事件语法、内联格式化、`initData` 数据访问、多参数事件已有部分通用约束；但后续自动复跑失败，设置 payload 与标签选中响应式样式最终由样本专用重放候选修好。 | 高优先级，待端到端复跑 |
| `MonitoringDashboard` | 生成、校验、修复、运行时、测试页 | 内联方法、生命周期、`initData` 冲突、组件注册、事件语法和 Math 插值已有通用约束或安全修复；原自动产物仍未通过人工复核。设置弹窗语义、日志格式化的通用检测尚未证明，Vue 测试页图表差异另属未结的对照工具限制。 | 高优先级，待端到端复跑 |

## 事后候选的具体通用化边界

1. **RuleBuilder（P1）**：`duplicate_class_attribute` 在校验器中被识别；修复阶段只在它是唯一静态错误、没有视觉错误且可以安全合并时跳过 LLM。已有正反例与冻结原件测试，见[修复报告](../../repair_reports/manual_fixes/formal_30_v4_rule_builder_class_merge.json)。缺的不是继续手改样本，而是证明新流水线会实际命中该通用分支，且自动产物经人工复核可用。
2. **AnalyticsDashboard（P0）**：既有冻结自动结果及两次后续自动通过均出现浏览器运行或显示问题。`unsupported_san_module_require`、Data-store 数组误用、computed 调实例方法、内联 `Math` 与对象式 style 等已被当前校验/Prompt 部分覆盖；加载完成、KPI 和洞察背景还需运行时场景复核。仅有[最终候选修复报告](../../repair_reports/manual_fixes/formal_30_v4_analytics_visual_bindings.json)的用户通过，不能认作通用流水线复跑成功。完整失败链见[人工审计](../formal_30_v4_development_closeout_20261025/analytics_dashboard_manual_audit.json)。
3. **TaskManager（P0）**：多参数 `fire` 现有通用校验和 Prompt 建议，但标签选中样式的响应式更新不能靠把 `selectedTagMap` 这一业务字段写成通用规则。应抽象为“交互状态变化后 class 依赖必须可追踪”，用无关业务字段的正反例测试，再做新一轮开发集自动复跑；设置 select/checkbox 和新建/编辑弹窗需人工场景复核。见[修复报告](../../repair_reports/manual_fixes/formal_30_v4_task_manager_settings_tags.json)与[人工审计](../formal_30_v4_development_closeout_20261025/task_manager_manual_audit.json)。
4. **MonitoringDashboard（P0）**：直接状态赋值事件、内联 `Math.abs` 已有通用拒收信号，但弹窗仅点背景关闭、保存 payload、日志等级标签等行为不是静态初始 DOM 相似度可证明的。应优先补通用事件/模板表达式规则的正反例及交互场景，而不是把 `showSettings` 或 `log.level.toUpperCase` 硬编码进通用规则。见[修复报告](../../repair_reports/manual_fixes/formal_30_v4_monitoring_settings_kpi_logs.json)与[人工审计](../formal_30_v4_development_closeout_20261025/monitoring_dashboard_manual_audit.json)。Vue 手工测试页只渲染一张图的差异暂不改动，但不能据此宣称图表完全等价。

## 下一道开发门槛

先为 P0/P1 缺口写与业务字段无关的正反例及跨样本回归；只对有安全边界的语法/结构错误做确定性修复，其余由校验信号和修复 Prompt 驱动。之后创建**新的开发修复版本**：先定向复跑上述 4 个样本，再用其余 8 个样本检查回退；分别报告自动结果、浏览器人工结果、修复轮数和 Token。若自动结果仍失败，保留失败并分析，不将事后候选倒填为流水线通过，也不以追求开发集 12/12 为由无限调参。需要 LLM 的复跑交由用户执行。

只有上述开发验证和未解限制被记录后，才另行固定实现与正式协议并运行未参与调优的独立测试集。独立测试结果不得用于本轮规则的边测边调。
