# 通用化规则实现记录（2026-10-27）

## G1：内联子组件渲染表达式的成员方法调用

动因是两个互不相关的开发集人工缺陷：`TaskManager` 的标签选中 class 使用 `formData.tags.includes(tag)` 后未随操作稳定刷新，`MonitoringDashboard` 的日志等级文本使用 `log.level.toUpperCase()` 后显示缺失。两者都把对象或数组成员方法直接放在内联 San 模板的 `{{ ... }}` 渲染表达式中。原样本和事后候选的路径及 SHA-256 见[结案人工记录](../formal_30_v4_development_closeout_20261025/manual_validation.json)与各自[TaskManager 修复报告](../../repair_reports/manual_fixes/formal_30_v4_task_manager_settings_tags.json)、[MonitoringDashboard 修复报告](../../repair_reports/manual_fixes/formal_30_v4_monitoring_settings_kpi_logs.json)。

本次在 `migration_pipeline/stages/validate.py` 增加 `unsupported_san_inline_template_member_call`：仅检查内联子组件模板的插值，忽略字符串字面量；`Math.*` 保留由既有专门错误码报告。对其余成员调用，要求改为子组件顶层方法，并把接收者和响应式参数从模板显式传入。生成 Prompt、流水线修复 Prompt 和服务端备用修复 Prompt 增加同一约束。**没有**把标签、日志、`includes` 或 `toUpperCase` 做成样本专用确定性替换；这种改写可能改变业务语义，应由有校验反馈的生成/修复阶段完成。

验证：先新增测试并确认其在修改校验器前失败；之后正反例、两份历史失败产物与各自通过候选的回放测试通过。完整 `python -m unittest tests.test_migration_pipeline_regressions tests.test_repair_prompt_and_loop` 为 **108/108 通过**；对结案快照中 12 个当前受检 San 文件做只读重放，新增错误码 **0 项误报**。历史的 `MonitoringDashboard` methods-wrapper 回归因现在额外检测到日志成员调用而更新了预期错误集合，原失败快照和产物均未更改。

边界：这只证明一种跨样本的静态拒收信号与 Prompt 约束；**尚未证明**新流水线能从 Vue 原输入自动生成四个事后修复候选的等效结果，也不能验证弹窗、异步加载、表单事件或完整 Vue/San 对等。下一步仍需开发集定向复跑及运行时交互检查；独立测试集尚未使用。

## R1：真实浏览器运行时验收场景

新增独立[验收页](../../../../tests/manual/formal-30-v4-runtime-acceptance.html)、[场景配置](../../../../migration_pipeline/interaction_configs/formal_30_v4_runtime_acceptance.json)和[配置测试](../../../../tests/test_formal_30_v4_runtime_acceptance.py)，不修改原 Vue/San 手工测试页或冻结产物。场景覆盖：`RuleBuilder` 的条件组/新增行 class 与背景；`AnalyticsDashboard` 的初始加载和手动刷新遮罩、统计百分比、折线点位、洞察背景及活动；`TaskManager` 的设置 select/checkbox、任务新建/编辑及标签样式；`MonitoringDashboard` 的 KPI 百分比、日志等级、双图容器及设置保存回显。页面可输入新的 San 产物相对路径复用同一场景。

2026-10-27 在本地真实 Edge/San runtime 冒烟：四个结案快照的已人工检查候选均通过；四个对应的历史自动产物均被拒收——`RuleBuilder` 缺少初始高亮 class，`AnalyticsDashboard` 报浏览器运行时错误且加载态残留，`TaskManager` 引用不存在的 `./StatCard`，`MonitoringDashboard` KPI 变化百分比缺失。新增配置测试与现有静态回归合计 **111/111 通过**。这些是开发集历史产物的浏览器场景检查，**不是新流水线自动生成成功、不是完整视觉等价、也不是独立测试集结果**。特别是 `MonitoringDashboard` 的 Vue 手工测试页图表数量差异仍未解决。

启动项目根目录静态服务后打开 `http://127.0.0.1:8765/tests/manual/formal-30-v4-runtime-acceptance.html`；选择样本，默认加载已人工检查候选。复跑后将输入框改为新批次 San 相对路径再运行场景。浏览器结果需要连同产物路径、批次 summary、修复历史和人工复核结论另行冻结；仅凭此页“通过”不能写作正式 30 样本结果。

## 下一轮开发集复跑入口

[独立批次配置](../../../../migration_pipeline/batch_configs/formal_30_v4_generalization_followup.json)只包含上述四个**已参与调优的开发样本**，输入指向 v3 冻结 Vue 源码并核对 SHA-256，批次 ID/summary 与历史结果隔离。`--dry-run` 已通过；该批次尚未执行 LLM。运行前用 `migration_pipeline/freeze_formal_30_v4_generalization_followup_pre_run.py` 复制本地实现、场景与输入并校验哈希。建议先单样本 `rule_builder`，确认新的自动产物及运行时场景，再继续其余三个 P0 样本，最后检查另外八个开发样本是否回退。不要使用 `--force` 覆写已完成 checkpoint，也不要把本轮结果并入原 v4 自动通过率。
