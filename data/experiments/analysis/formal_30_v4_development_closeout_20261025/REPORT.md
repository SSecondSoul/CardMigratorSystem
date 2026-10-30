# formal_30_v4 开发回归结案（2026-10-25）

## 结果与适用范围

`formal_30_v4_targeted` 的最终 checkpoint 为 7/7，`formal_30_v4_deferred_regression` 为 5/5；合计 12/12 个**复用的开发样本**通过自动静态验证与初始 DOM/视觉评估，其中 medium 3 个、complex 9 个。两批样本均来自已知的 v3 失败或超时案例，期间针对这些案例修正了生成/修复 Prompt、校验器、渲染器和确定性修复逻辑。因此，12/12 只能表述为“开发回归结案”，**不能作为未见样本的泛化通过率，也不能与 v3 独立测试结果直接作因果对比**。

所有 12 条最终记录的 `interaction_eval_passed` 均为 `null`。上述通过不代表排序、拖拽、点击、状态联动等人工交互已验证。人工验收须单独留痕；独立评估须在实现及协议冻结后使用未参与调优的样本。

## 统计口径与证据

| 指标 | targeted 终态 | deferred 终态 | 合计 |
| --- | ---: | ---: | ---: |
| 样本数 / 自动通过数 | 7 / 7 | 5 / 5 | 12 / 12 |
| 终态运行内修复轮数 | 8 | 9 | 17 |
| 终态生成 Token | 231,499 | 320,493 | 551,992 |
| 终态修复 Token | 359,671 | 555,028 | 914,699 |
| 终态总 Token | 591,170 | 875,521 | 1,466,691 |

上表 Token 是每个样本**最后一次 checkpoint**的用量之和，**不含**被后来 `--force` 覆盖的失败或审计不通过的运行，也不代表整个研发阶段的累计投入。修复轮数同样只统计最后一次运行。实验日志共记录 28 次已完成的样本运行，另有 1 次 `MonitoringDashboard` 初始生成超时；这不是 29 次独立试验。逐样本运行次数、终态 Token、DOM 指标和快照路径见 [sample_results.csv](sample_results.csv)。可机器读取的来源 SHA-256、批次原始聚合及截至 2026-10-27 已纳入分析的 17 份既有快照校验结果见 [summary.json](summary.json)。

复现分析（不触发 LLM，也不重跑迁移）：

```powershell
python migration_pipeline/analyze_formal_30_v4_development.py
```

脚本会先核对两个批次均完成且通过、样本与聚合一致，并验证最终批次快照、12 份逐样本快照及已纳入的后续失败/复跑快照的 `SHA256SUMS.txt`；校验失败则不生成报告数据。既有冻结文件保持原样。

## 缺陷—修复—结果追溯

下表只概括可在原始日志中追溯的结论；“通过”均指最后一次自动评估，不替代人工交互检查。

| 样本 | 记录的主要问题与修正方向 | 已完成运行次数 | 终态快照 |
| --- | --- | ---: | --- |
| CourseModuleAccordion | 渲染方法遗漏响应式依赖，且子节点顺序校验未正确读取 Vue 源路径；扩大依赖/顺序检查并调整 Prompt | 2 | `formal_30_v4_course_module_pass_20261022_212133` |
| SchemaMappingWorkbench | `sourceKey` 等表达式触发错误的循环键正则命中，同时 select 的 disabled 条件迁移有误；修正校验与迁移约束 | 1 | `formal_30_v4_schema_mapping_pass_20261022_213243` |
| IncidentResponseBoard | 合法的私有定时器访问及双别名循环被评估器误判；修复状态检查和轻量渲染 | 2 | `formal_30_v4_incident_pass_20261022_231831` |
| RuleBuilder | 缺失 prop 默认值，并把 San Data 当普通对象解构，导致编辑区消失；增加校验和 Prompt 约束 | 1 | `formal_30_v4_rule_builder_pass_20261022_233452` |
| HabitWeekTracker | 双别名循环未被轻量渲染器展开，造成结构假差异；修复循环渲染 | 1 | `formal_30_v4_habit_week_tracker_pass_20261022_234318` |
| PlaybackQueue | 双别名循环的索引未进入比较作用域，产生 disabled 属性假差异；修复渲染器 | 1 | `formal_30_v4_playback_queue_pass_20261022_235049` |
| AnalyticsDashboard | 先遇到服务端超时，后发现循环键、组件 prop 绑定等迁移/校验问题；逐次冻结失败并收紧校验及确定性修复边界 | 4 | `formal_30_v4_analytics_pass_20261023_152047` |
| AccessMatrix | Vue 轻量渲染器未合并静态与动态 class；对已通过 San 做冻结重放，修正比较器假差异 | 1 | `formal_30_v4_deferred_access_matrix_pass_20261023_155031` |
| LocalizationWorkspace | 自动通过产物仍含无效对象式 class 绑定；审计拒收、增设校验与 Prompt 规则后强制复跑 | 2 | `formal_30_v4_deferred_localization_workspace_pass_20261023_163149` |
| TripItineraryPlanner | v3 的响应式依赖、循环键和结构问题，在 v4 修复约束下经一次修复轮通过 | 1 | `formal_30_v4_deferred_trip_itinerary_planner_pass_20261023_165740` |
| TaskManager | 多轮暴露 SSM、循环绑定及组件标识符重命名问题；边界化确定性修复后通过 | 4 | `formal_30_v4_deferred_task_manager_pass_20261023_190805` |
| MonitoringDashboard | 内联子组件方法、生命周期归属、父级 `initData` 冲突及组件注册/渲染问题逐次显现；冻结失败、修复、复跑后通过 | 8，另 1 次生成超时 | `formal_30_v4_deferred_monitoring_dashboard_pass_20261025_124927` |

原始原因、每次失败/复跑过程请以 [`remediation_log.json`](../formal_30_v4_planning_20261022/remediation_log.json) 和 [deferred 实验 Notebook](../../../../notebooks/02-migration-experiments/2026-10-23_formal_30_v4_deferred_regression.ipynb) 为准。特别是 `LocalizationWorkspace` 和 `MonitoringDashboard` 曾有“自动通过但审计发现问题”的中间状态，不应把那些运行当作结案通过。`AccessMatrix` 的终态 summary 保留修正评估器前的结构相似度 0.9766；冻结 San 在评估器修复后的直接重放为 1.0，因此不要把前者解释为生成组件缺陷。

## 下一道验收门槛

先对 9 个 complex 组件逐个做 Vue/San 人工交互对照，记录“通过 / 发现差异 / 因环境无法判断”及操作和截图或日志证据；发现差异时先冻结当前产物，再区分生成缺陷、评估器漏检与测试页问题。建议沿批次原始顺序从 `SchemaMappingWorkbench` 开始，一次只加载一个组件，待人工确认后再切换下一个。三个 medium 组件可随后补充同类人工检查。人工验证完成前，不在论文中写“交互等价”。

完成开发回归及人工复核后，再冻结实现、Prompt、评估器和测试协议，运行**未参与本轮修复的独立样本**。本报告不改变已有正式协议或冻结快照，也不要求推送到远程仓库。

## 人工复核进展（2026-10-26）

- `SchemaMappingWorkbench`：用户确认 Vue/San 人工检查通过。
- `IncidentResponseBoard`：用户确认 Vue/San 人工检查通过。
- `RuleBuilder`：用户发现冻结 San 的“基础条件”选中样式和新增条件行样式与 Vue 不一致，原冻结产物的人工检查**未通过**。当前校验器只报 `duplicate_class_attribute`：按钮和规则行分别把固定 class 与动态 class 输出成两个同名属性。该缺陷说明原 12/12 自动通过不能代替运行时样式验收。通过有边界的零 Token 确定性合并生成独立候选，静态校验、San 编译及初始 DOM 复核通过；用户随后确认**修复候选的人工复核通过**。候选、原件 SHA-256 与修复边界见 [修复报告](../../repair_reports/manual_fixes/formal_30_v4_rule_builder_class_merge.json)。原快照、原批次 summary 均未修改。

逐项人工状态（含原件与修复候选的区分）见 [manual_validation.json](manual_validation.json)。

- `AnalyticsDashboard`：用户在加载冻结 San 时遇到 `require('./StatCard')` 报错，**原自动通过记录已被人工审计否决，尚未开展交互检查**。原产物还引用三个同样缺失的子组件。新校验/编译/渲染重放明确失败，并报告多项迁移问题；完整来源 SHA-256、错误码及隔离复跑配置见 [审计记录](analytics_dashboard_manual_audit.json)。原始 7/7、12/12 仍是历史 checkpoint 的原始计数，不能再解释为全部样本运行时可用。新运行必须单独记录，不改写原快照或 summary。

隔离复跑 `formal_30_v4_analytics_manual_followup` 随后自动通过（1/1、2 轮修复、151,932 Token），已先冻结为 `formal_30_v4_analytics_manual_followup_automatic_pass_20261026_152546`，17 个 payload 校验通过。对冻结输入和产物再次独立运行当时的静态、编译和初始 DOM 评估，均通过且初始 DOM 指标为 1.0 / 1.0 / 1.0、编辑距离 0；仅有 `require('san')`，四个子组件在文件内定义。但用户浏览器检查报错 `TypeError: this.data.map is not a function`，**此隔离复跑的自动通过同样被人工审计否决**。内联 `TrendChart` 把 San Data store 当作 Vue 的 `data` 数组使用；新静态规则在该冻结产物中检出 4 处 `map`、2 处 `length`，另检出直接读取 `this.maxValue`/`this.minValue` 两个 computed 值。本次浏览器失败不是原始 12 样本 checkpoint 的新增正式测试结果。

第二次隔离复跑 `formal_30_v4_analytics_runtime_followup` 自动通过（1/1、3 轮修复、236,684 Token），已冻结为 `formal_30_v4_analytics_runtime_followup_automatic_pass_20261026_160213`，18 个 payload 校验通过。对冻结副本独立重放静态验证、San 编译及初始 DOM 评估均通过（结构、标签、文本相似度均为 1.0，编辑距离 0）；新产物的 `TrendChart` 已通过 `this.data.get('data')` 读取数组，并通过 `this.data.get('maxValue')` 等读取 computed 值。但用户报告加载遮罩持续显示，本地浏览器诊断在 2 秒后也复现了 `TypeError: this.getX is not a function`：图表已有 30 个点、洞察 4 条、活动 15 条，遮罩仍在。`TrendChart` 的 computed 中调用了 San computed 上下文不可用的组件方法 `this.getX()`/`this.getY()`，因此**第三份自动通过产物同样被人工审计否决**。这不是原始 12 样本 checkpoint 或独立测试集的新正式结果。

已从该冻结产物生成独立的 `AnalyticsDashboard_computed_context.san` 修复候选，来源、哈希、精确重放脚本及验证结果见 [修复报告](../../repair_reports/manual_fixes/formal_30_v4_analytics_computed_context.json)。候选把 computed 内的坐标计算改为传入数据的纯函数；当前校验器在冻结产物上报告 `invalid_san_computed_instance_method_call`，在候选上通过。本地 San 3.15.6 浏览器诊断在 2 秒后不再显示遮罩，且数据仍完整。用户随后提供 `VM573:63` 的 `this.getX` 堆栈，与旧冻结产物一致，而测试页当前引用的候选不含该调用，故需避开旧页面/响应缓存。同时其控制台的 `mouseenter listen fail` 警告提示了另一个确实存在的内联事件赋值错误；已从第一候选生成新的 `AnalyticsDashboard_computed_context_and_hover.san`，来源和哈希见 [第二修复报告](../../repair_reports/manual_fixes/formal_30_v4_analytics_hover.json)。第二候选本地浏览器诊断显示加载遮罩消失、数据完整、鼠标移入图表点后提示出现，且未捕获异常或警告，但用户随后指出百分比数值与洞察标签背景缺失，故第二候选未通过人工视觉检查。

针对这两个差异，新建 `AnalyticsDashboard_visual_bindings.san` 第三候选，详见[视觉绑定修复报告](../../repair_reports/manual_fixes/formal_30_v4_analytics_visual_bindings.json)。内联 `StatCard` 使用组件方法计算绝对值，不再在 San 模板中直接访问 `Math`；`InsightList` 将背景色绑定序列化为 CSS 字符串，不再套用 Vue 的对象式样式绑定。冻结来源未改写。静态验证、San 编译和初始 DOM 评估通过；本地 San 3.15.6 浏览器显示四项变化值为 `12.5%`、`2.3%`、`0.7%`、`18.9%`，首个洞察背景计算值为 `rgb(16, 185, 129)`，加载遮罩消失。用户于 2026-10-26 确认该候选人工检查通过。已补充通用校验和生成/修复提示；这一样本级修复不计入独立正式测试结果。

后续人工检查中，`AccessMatrix`、`LocalizationWorkspace`、`TripItineraryPlanner` 由用户逐项确认通过；`TaskManager` 冻结产物则在加载时报告 `仅支持 require("san")，当前: ./StatCard`。核查发现它还引用 `./TaskItem`、`./TaskDetail`、`./TaskForm`、`./SettingsPanel`，而单文件测试页中均不存在。现行校验器和初始 DOM 评估对该冻结产物分别报错，故历史自动通过记录也不能解释为该样本运行时可用。详见 [TaskManager 人工审计](task_manager_manual_audit.json)；原快照和 summary 保持不变，后续复跑作为单独的开发样本记录。首次隔离复跑在生成请求阶段发生约 240 秒的读取超时，未生成 San 文件；该执行错误已另行冻结为 `formal_30_v4_task_manager_manual_followup_generation_timeout_20261026_201844`，不计为模型生成或迁移质量失败。

`TaskManager` 隔离续跑完成 1/1，但三轮修复后未通过（生成 96,864、修复 241,266、合计 338,130 Token）；最终静态错误仅剩 `invalid_san_computed_instance_method_call`，初始 DOM 评估通过。该失败已冻结为 `formal_30_v4_task_manager_manual_followup_failed_20261026_203625`，没有覆盖旧快照。从冻结文件生成独立的 `TaskManager_computed_pure_helper.san` 候选：把 `filteredTasks` 调用的逾期判断提为纯函数，详见[修复报告](../../repair_reports/manual_fixes/formal_30_v4_task_manager_computed_context.json)。候选的静态校验、编译和初始 DOM 评估通过，但人工浏览器检查尚待完成；不得把它计为自动通过或独立测试集结果。

用户在第一候选的 San 测试页报告 `[SAN FATAL] expect an ident:`，因此第一候选未通过人工加载。用本地 San 3.15.6 解析器复现后，发现空 `on-dragover` 处理器、Vue 风格 `on-submit.prevent`/`on-click.stop` 修饰符和带括号的 `(task, index)` 循环别名均未正确迁移。新增通用静态规则和生成/修复提示；从第一候选精确重放得到 `TaskManager_template_syntax.san` 第二候选，详情见[模板修复报告](../../repair_reports/manual_fixes/formal_30_v4_task_manager_template_syntax.json)。第二候选的主模板与五个内联子模板均通过实际 San 解析器检查，静态及初始 DOM 评估通过，99 项回归测试通过；但后续人工视觉检查发现内联显示值缺失。旧候选、冻结失败证据与历史计数均未改写。

第二候选可加载，但用户发现统计卡片每个状态的变化数值，以及任务项的优先级与日期缺失，故它也未通过人工视觉检查。内联子组件把需要参数的 `formatTrend(trend)`、`getPriorityLabel(task.priority)` 和 `formatDate(task.dueDate)` 错迁为 computed 值，模板却按方法调用；任务详情还存在同类 `formatTime(comment.time)` 问题。针对这一类别增加通用校验与生成/修复提示，并从第二候选精确重放得到 `TaskManager_inline_format_methods.san` 第三候选，见[格式化方法修复报告](../../repair_reports/manual_fixes/formal_30_v4_task_manager_inline_format_methods.json)。第三候选的静态校验、初始 DOM 评估和实际 San 模板解析通过，修复时的 100 项回归测试通过；但后续人工检查发现弹窗内容不符。此候选不计入原 12 样本自动 checkpoint 或独立正式测试结果。

第三候选在人工检查中暴露新建／编辑任务弹窗内容不符：`TaskForm.initData()` 在 San 创建 `this.data` 之前读取该 store，且把 `createFormData` 错放在 computed 中当方法调用；弹窗遮罩还会响应表单内部冒泡的点击，与 Vue 的 `@click.self` 不一致。第三候选因此未通过人工检查。新增通用 `invalid_san_init_data_store_access` 静态规则及生成／修复提示；从第三候选按哈希精确重放得到 `TaskManager_form_initialization.san` 第四候选，详情见[表单初始化修复报告](../../repair_reports/manual_fixes/formal_30_v4_task_manager_form_initialization.json)。第四候选通过静态校验、初始 DOM 评估、主模板及五个内联模板的 San 解析，并以 San 实例验证编辑回填与新建默认值；修复时的 101 项回归测试通过，但后续人工检查发现设置和标签差异。它不计入原自动 checkpoint 或独立测试集。

第四候选继续人工检查时，用户发现设置下拉框选中后为空、勾选框取消后无法再次勾选、任务表单标签选中后颜色不变，因此第四候选也未通过。设置面板在模板中调用多参数 `fire('update', key, value)`，但 San 自定义事件只承载一个 payload，父组件亦未显式解包 `$event`；表单标签的 class 未随标签状态稳定刷新。新增通用 `invalid_san_inline_event_payload` 静态规则及生成／修复提示。从第四候选按哈希精确重放得到 `TaskManager_settings_tags.san` 第五候选，改为设置子组件发出 `{key, value}` 并在父组件解包，同时显式维护响应式标签选中映射。详情见[设置与标签修复报告](../../repair_reports/manual_fixes/formal_30_v4_task_manager_settings_tags.json)。第五候选通过静态校验、初始 DOM 评估、六个 San 模板解析、子组件事件与标签状态实例测试，以及 103 项回归测试；用户于 2026-10-26 确认人工检查通过。该结论仅属于复用开发集的事后候选，不改写原自动 checkpoint，也不计入独立正式测试集。

下一项 `MonitoringDashboard` 使用审计确认的冻结自动结果 `formal_30_v4_deferred_monitoring_dashboard_pass_20261025_124927` 进行人工检查，用户发现设置按钮无法打开、KPI 变化百分值缺失、日志等级标识看似缺失，因此该冻结自动结果的人工复核**未通过**。Vue 与 San 源码均生成 CPU、内存两张实时曲线且都使用 `Math.random()`；用户确认两页仅随机数值或线形不同，故不把这一项计为迁移缺陷。Vue 日志条目本身没有独立图标，实际需对齐的是彩色 INFO/WARNING/ERROR 等级标识。完整审计见 [MonitoringDashboard 人工审计](monitoring_dashboard_manual_audit.json)。

从冻结原件按哈希精确重放得到 `MonitoringDashboard_settings_kpi_logs.san` 候选：设置入口和关闭逻辑改为 San 方法，保存事件传递明确 payload 并阻止表单原生提交；KPI 百分值和日志等级大写改为子组件方法。详情见[修复报告](../../repair_reports/manual_fixes/formal_30_v4_monitoring_settings_kpi_logs.json)。候选通过静态校验、初始 DOM 评估、主模板及七个内联模板解析、实例级设置和格式化检查，以及 104 项回归测试；用户于 2026-10-26 确认 **San 组件人工通过**。Vue 手工测试页虽然源码声明两张图，页面只呈现一张；用户决定本轮不处理 Vue 页面，因此**不能据此宣称图表的 Vue/San 完全一致**。这项结果仅属于开发集事后修复候选的人工确认，原冻结快照和批次 summary 均未改写。

2026-10-27，三个 medium 样本 `CourseModuleAccordion`、`HabitWeekTracker`、`PlaybackQueue` 已依次获用户人工确认通过，所用 San 文件均为各自 v4 冻结通过产物，路径与 SHA-256 见 [manual_validation.json](manual_validation.json)。至此 12 个开发回归样本均有**当前被检查 San 版本**的用户报告通过记录；其中部分 complex 样本仅在事后修复候选上通过，不能倒填为原冻结自动产物的人工通过。`MonitoringDashboard` 的 Vue 测试页图表差异仍未解决，因此这 12 条记录也不能合并表述为 12/12 的完整 Vue/San 交互等价，更不能当作独立正式测试集结果。
