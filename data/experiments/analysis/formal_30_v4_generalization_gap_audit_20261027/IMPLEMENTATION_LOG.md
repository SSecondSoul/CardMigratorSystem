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

预运行代码与输入已冻结到[有效快照 v2](../../snapshots/formal_30_v4_generalization_followup_pre_run_20261027_v2/manifest.json)，29 个 payload 的 SHA-256 经独立复核均匹配。首次冻结因 Windows 长路径中断，`formal_30_v4_generalization_followup_pre_run_20261027/` **没有 manifest，不是有效快照**，保留原样且不作为复跑证据。

## 首个定向复跑：RuleBuilder

用户于 2026-10-27 执行 `rule_builder` 后，新批次 checkpoint 显示初版失败（`duplicate_class_attribute`、`nested_state_mutation`、`missing_prop_defaults` 和结构相似度低），一轮 LLM 修复后静态/轻量视觉评估通过，结构及标签/文本相似度均为 1.0，树编辑距离 0；生成 50,060 token，修复 60,554 token，总计 110,614 token。该次**自动结果**已冻结到[独立快照](../../snapshots/formal_30_v4_generalization_followup_rule_builder_automatic_pass_20261027_124838/manifest.json)，8 个 payload 哈希复核一致。随后对冻结 `final.san` 执行 R1 真实浏览器场景，条件组高亮、增加缺值条件行的样式和切换条件组均通过；[结构化检查记录](rule_builder_followup_review.json)。两个手工测试页仅切换到该次冻结的 Vue/San 文件；用户于 2026-10-27 回复“通过”，记为本次指定场景的人工 Vue/San 对照通过。该结论不代表穷尽的行为等价，也不是独立测试集结果。

## 第二个定向复跑：AnalyticsDashboard

用户于 2026-10-27 执行 `analytics_dashboard` 后，同一开发批次 checkpoint 为 **自动失败**：三轮修复耗尽，最终静态校验仍报 `invalid_san_computed_instance_method_call`。`TrendChart` 的 `computed.linePoints` 与 `computed.areaPoints` 仍调用 `this.getX(idx)`、`this.getY(point.value)`；San computed 上下文不能依赖这些组件实例方法。现有修复 Prompt 已明确禁止此模式，但本次模型未消除。最终轻量视觉评估通过、结构相似度 1.0、树编辑距离 0，不可据此覆盖静态失败，也不能推断异步加载后的图表运行正常。生成 67,902 token，修复 171,409 token，总计 239,311 token。

该次失败已冻结到[独立快照](../../snapshots/formal_30_v4_generalization_followup_analytics_dashboard_automatic_fail_20261027_144124/manifest.json)，8 个 payload 的 SHA-256 经独立复核均匹配；[结构化诊断记录](analytics_dashboard_followup_review.json)。当前不进入人工 Vue/San 验收。下一步先针对“computed 调用实例方法”改进通用修复反馈或设计有边界的修复，并在这份冻结失败产物上只读回放验证，然后使用新开发批次复跑；不要用 `--force` 覆盖本次失败 checkpoint。这不是独立测试集结果。

### 聚焦修复提示与单轮探测准备

在通用 `RepairPromptBuilder` 中增加受限分支：仅当静态错误代码集合恰为 `invalid_san_computed_instance_method_call` 且视觉错误为空时，使用较短的聚焦提示，要求把 `computed` 中的实例方法调用改为带显式数据参数的纯函数，同时保留模板、样式和其他行为。其他错误组合仍使用原有完整提示；未改动冻结失败产物，也未实现样本专用的确定性替换。[探测脚本](../../../../migration_pipeline/probe_formal_30_v4_analytics_computed_repair.py)默认只读预检；显式 `--execute` 才调用本地 LLM 一轮、将候选写入独立 probe 目录并运行静态/轻量视觉复验。

冻结失败产物的只读提示回放已命中聚焦分支，未重复灌入完整 SSM；相关 **113/113** 测试通过。[预探测哈希与边界记录](analytics_computed_focus_pre_probe.json)。尚未执行 LLM 探测，因此不能声称这一提示已修复图表或证明新流程自动通过；探测成功后仍需真实浏览器场景与新开发批次验证。

用户执行聚焦单轮探测 v1 后，模型输出的候选静态与轻量视觉评估均通过（结构相似度 1.0，树编辑距离 0；16,941 token）。但代码复核发现模型将供模板调用的 `getX(idx)` / `getY(point.value)` 方法签名改为需要 2/3 个参数，模板未改，异步图表点坐标有成为 `NaN` 的风险。**不能将 v1 判定为运行时或人工通过**。输入、候选、报告和当时的提示实现已冻结到[语义拒收快照](../../snapshots/formal_30_v4_analytics_computed_focus_probe_v1_semantic_reject_20261027_151143/manifest.json)。当前代理浏览器控制接口不可用，未执行浏览器回放；此结论来自可复核的代码签名与调用对照。

聚焦提示 v2 进一步要求保留所有模板所调用方法的参数签名与可观察行为，只给 computed 增加独立纯 helper；真实浏览器场景增加折线图圆点 `cx`/`cy` 有限数值断言，防止只凭 polyline `points` 非空误收此类错误。v2 冻结输入只读预检通过，相关 **114/114** 测试通过；[v2 预探测哈希记录](analytics_computed_focus_v2_pre_probe.json)。尚未执行 v2 LLM 探测。

用户执行聚焦单轮探测 v2 后，新候选静态与轻量视觉评估均通过（结构相似度 1.0，树编辑距离 0；17,048 token）。代码复核表明模板和样式未变，供模板调用的 `getX(index)` / `getY(value)` 签名保留，computed 改为调用独立纯函数。结果及所用实现已冻结到[v2 静态通过快照](../../snapshots/formal_30_v4_analytics_computed_focus_probe_v2_static_pass_20261027_152434/manifest.json)，9 个 payload 的 SHA-256 独立复核一致；[结构化复核记录](analytics_computed_focus_v2_review.json)。114 项相关测试再次通过。两个手工测试页已仅切换组件引用到冻结 Vue 源码与 v2 San 候选，等待浏览器场景和用户人工 Vue/San 对照；**尚不能记作运行时通过或新生成批次通过**。
