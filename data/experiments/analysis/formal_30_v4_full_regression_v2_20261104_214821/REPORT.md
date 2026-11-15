# 当前规则完整 30 样本开发回归：第二批结果

日期：2026-11-04（Asia/Shanghai）。批次 formal_30_v4_full_regression_v2。
原始结果先冻结于 `formal_30_v4_full_regression_v2_results_20261104_214821`，457 文件校验通过；运行协议 frozen/live 351 项通过。

## 总体结果：不是全批通过，也不是单纯模型退化

30 项全部完成，**24/30 = 80% 自动通过，6 项未通过，0 执行异常，0 待处理**。
旧 v3 为 18/30，首次 v4 为 25/30；本批比首次 v4 少 1 项通过（-3.33 个百分点），但两个旧超时样本本次有完整评估，不再属于执行异常。
评估器、规则、Prompt、预算定义、超时及模型采样均不同，不能单因素归因于某条 Prompt。

| 层级 | 旧 v3 | 首次 v4 | 本批 | 本批评估失败 | 执行异常 |
| --- | ---: | ---: | ---: | ---: | ---: |
| simple | 10/10 | 8/10 | 9/10 | 1 | 0 |
| medium | 7/10 | 10/10 | 9/10 | 1 | 0 |
| complex | 1/10 | 7/10 | 6/10 | 4 | 0 |
| 合计 | 18/30 | 25/30 | 24/30 | 6 | 0 |

相对首次 v4：21 保持通过，3 改善通过（BudgetThreshold、TipSplitCalculator、LocalizationWorkspace），4 由通过变为未通过（StockReservationBadge、HabitWeekTracker、RuleBuilder、TripItineraryPlanner），2 仍未通过（TaskManager、MonitoringDashboard，旧状态为执行异常）。
相对旧 v3：17 保持通过、7 改善通过、1 由通过变未通过、5 仍未通过。

## 次数、用量与验收边界

- 运行 17:22:42—18:44:15，墙钟 4893 秒（81 分 33 秒）。
- 初始直接通过 4 项，确定性处理后不调用模型通过 4 项，有模型修复参与的通过 16 项。
- LLM repair 共 26 次；确定性候选共 13 次，均被接受；模型候选发生 5 次回退。
- 生成 855,682、repair 965,862、记录 token 共 **1,821,544**。所有 30 项正常完成；这仍是服务返回的 usage 账目，不是外部账单独立核验。
- 5 项在第 1 次模型候选被拒后停止，不是每项都耗尽 3 次预算。MonitoringDashboard 使用 3 次模型修复，最终因无进展停止。
- 全部 30 项 interaction_eval_passed 为空。本轮没有人工交互通过记录，旧派生候选人工验收不继承到本轮。

逐项核对 summary、repair report、最终代码、全部候选进度签名、回退保留与被拒文件、token 总和及分层计数。没有换用更高 DOM 分数候选或手工修复产物。

## 六项未通过：保留件和被拒候选必须分开看

| 样本 | 原始停止原因 | 保留件问题／DOM | 被拒候选或残留边界 |
| --- | --- | --- | --- |
| StockReservationBadge | 模型候选回归后回退 | methods 包装；DOM 0.7857 | 候选新增 available、warningAt 默认值缺失，门禁拒绝；仍有 methods 包装 |
| HabitWeekTracker | 模型候选回归后回退 | prop schema 问题；DOM 1.0 | 候选新增 habits、dayLabels 默认值缺失并失去视觉通过 |
| TaskManager | 模型候选回归后回退 | 10 条静态诊断；DOM 0.9889 | 候选降至 3 条诊断，但新增 TaskForm.isTagSelected 对 formData 的隐藏依赖；门禁不以总错误减少替代语义保护 |
| RuleBuilder | 模型候选回归后回退 | 重复 class、插值不平衡、4 项 prop 默认值缺失；DOM 0.9818 | 候选仅余 initialGroups 默认值缺失，旧缺陷收缩却被整条消息身份视为新增，存在门禁误判 |
| TripItineraryPlanner | 模型候选回归后回退 | schema、响应式依赖、嵌套修改、接口等；DOM 1.0 | 候选新增 tripName、days、initialItems 默认值缺失并失去视觉通过 |
| MonitoringDashboard | 3 次模型修复后无进展 | nested_state_mutation 与 watcher 持久化诊断；DOM 0.9605 | 已定位克隆识别误报及 try/catch 持久化证明范围问题，详见下节 |

前三轮单样本／人工验收对应不同精确产物，本轮重新生成，不能把旧候选拼接进本批通过数。当前结果也不能概括为“此前修复全部失效”：例如 MonitoringDashboard 的初始化仍为 inited=0、attached=1，父方法接口无缺失。

## 评估器／候选门复核：先校准，不能直接改分

### 1. RuleBuilder：分组诊断文本导致误报新增

保留件缺失字段为 `title, availableFields, initialGroups, readonly`；被拒候选只缺 `initialGroups`，它是前者的真子集。
当前 scheduler 的诊断身份是 `(code, location, message)`，整条消息文字改变后，新消息被计为 introduced_semantic_findings，从而停止。
这是可复核的“旧缺陷缩小却被记为新增”，不是新增字段缺失的证据。
候选仍然有默认值错误，所以不能因此直接判通过或放行所有同码诊断。后续应采用源契约支持的逐字段结构化身份，并保留新增另一字段必须拒绝的反例。

### 2. MonitoringDashboard：克隆后的局部写入被当成原始状态别名

最终 simulateDataUpdate 第 622 行为 `this.data.get('kpiData').map(kpi => ({...kpi}))`，逐个创建记录对象。
本方法的四次修改是本地新记录 `.value` 标量属性，并在之后明确 `this.data.set('kpiData', kpiData)`。
独立 AST 检查确认这些具体局部写入的克隆／提交形态。
当前 STATE_ALIAS_PATTERN 仅匹配到 data.get 前缀，将后接 map 的变量也当成原状态引用；其初始别名收集没有应用完整表达式的克隆区分。
这条别名诊断对本例具体写入是误报，但不证明整个组件等价，也不允许对 map(x=>x)、浅数组复制后修改共享深层对象或提交顺序错误一概放行。

### 3. MonitoringDashboard：持久化写入实际存在，不能称为再次丢失

最终 settings watcher 是 `(newValue, oldValue)`，写入实际位于：

```js
try {
  localStorage.setItem('dashboard_settings', JSON.stringify(newValue));
} catch (e) {
  console.error('保存设置失败', e);
}
```

当前只接受源对应的直接尾部写入，遇到 try/catch 记录 `unsupported_callback_effects` 并拒绝自动补写。
因此该诊断并不证明存储写入缺失。保守拒修可防止重复插入，但“missing trailing write”的措辞混淆了缺失与未证明。
源未加 try/catch，异常传播／处理策略发生变化，不能未经审查就宣布完全等价。下一步应拆分 missing／unproven 诊断，建立正常写入与存储抛异常的受控用例，先决定允许的等价范围；不能直接删除 catch 或追加第二条写入。

## 下一步建议（本次未实施修复）

先处理评估器和门禁校准：逐字段默认值身份、具备对象层级与提交顺序证明的克隆识别、持久化缺失／异常包装未证明分离。
用冻结真实案例和安全反例验证后，再分析真正的生成／repair 残留及是否需要新 Prompt／规则；不要先关闭保护门、增加轮数或反复付费复跑。
TaskManager 的新增隐藏依赖及 Stock/Habit/Trip 的新增默认值问题仍需独立处理，不能借校准全局免检。
任何新规则都需独立离线重评与新协议，保留原始 **24/30** 自动分数；不得就此宣布“实际全部通过”。

本次新增只读分析脚本 `migration_pipeline/analyze_formal_30_v4_full_regression_v2.py`，6/6 审计测试通过（3.892 秒），包含真实全批账目、分组缺陷缩小、复制对象／身份 map／深层修改／提交顺序反例。
没有重新完整运行 413 项测试；运行前 407 项结果不改写。
没有修改生产规则、Prompt、生成产物或测试页，未新调用模型或浏览器，未 commit/push。详细账目、哈希和候选门证据见本目录 `summary.json`。

## 30 项配对清单

pass/fail/error 均是对应冻结版本的自动结果，不是重新以当前规则回评旧版本。

| 组件 | 复杂度 | 旧 v3 | 首次 v4 | 本批 | 本批停止原因 |
| --- | --- | --- | --- | --- | --- |
| VolumeControl | simple | pass | pass | pass | passed |
| NotificationCard | simple | pass | pass | pass | passed |
| ReadingProgressCard | simple | pass | pass | pass | passed |
| TextLengthGauge | simple | pass | pass | pass | passed |
| BudgetThreshold | simple | pass | fail | pass | passed |
| OtpCodeInput | simple | pass | pass | pass | passed |
| StockReservationBadge | simple | pass | pass | fail | repair_candidate_regression_rolled_back |
| TipSplitCalculator | simple | pass | fail | pass | passed |
| StatusSwitch | simple | pass | pass | pass | passed |
| SearchClearField | simple | pass | pass | pass | passed |
| BatchRenamer | medium | pass | pass | pass | passed |
| HabitWeekTracker | medium | fail | pass | fail | repair_candidate_regression_rolled_back |
| PlaybackQueue | medium | fail | pass | pass | passed |
| SeatBookingMap | medium | pass | pass | pass | passed |
| BreadcrumbNavigator | medium | pass | pass | pass | passed |
| ShippingEstimator | medium | pass | pass | pass | passed |
| MeetingPollScheduler | medium | pass | pass | pass | passed |
| CourseModuleAccordion | medium | fail | pass | pass | passed |
| DeliveryRouteTimeline | medium | pass | pass | pass | passed |
| AudioSegmentMarker | medium | pass | pass | pass | passed |
| AnalyticsDashboard | complex | error | pass | pass | passed |
| IncidentResponseBoard | complex | fail | pass | pass | passed |
| FleetDispatchConsole | complex | pass | pass | pass | passed |
| TaskManager | complex | error | error | fail | repair_candidate_regression_rolled_back |
| MonitoringDashboard | complex | error | error | fail | no_repair_progress |
| RuleBuilder | complex | fail | pass | fail | repair_candidate_regression_rolled_back |
| AccessMatrix | complex | fail | pass | pass | passed |
| LocalizationWorkspace | complex | fail | fail | pass | passed |
| TripItineraryPlanner | complex | fail | pass | fail | repair_candidate_regression_rolled_back |
| SchemaMappingWorkbench | complex | fail | pass | pass | passed |

