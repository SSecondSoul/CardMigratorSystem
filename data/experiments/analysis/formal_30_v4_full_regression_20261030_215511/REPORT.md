# v4 完整 30 样本开发回归：本次执行结果

来源：`formal_30_v4_full_regression_results_20261030_215511`，359 个文件校验通过；原始报告、代码和预运行协议均已封存。此报告记录这一执行快照，后续基础设施重试另留记录。

30 项均已尝试：25 通过、3 项评估未通过、2 项执行错误；28 项正常完成。全部 30 项分母通过率为 **25/30 = 83.33%**，正常完成项通过率为 25/28 = 89.29%。旧 v3 为 18/30 = 60.00%；本次增加 7 项，描述性变化 +23.33 个百分点。

| 层级 | 旧 v3 通过／配置数 | 当前 v4 通过／配置数 | 当前评估失败 | 当前执行错误 |
| --- | ---: | ---: | ---: | ---: |
| simple | 10/10 | 8/10 | 2 | 0 |
| medium | 7/10 | 10/10 | 0 | 0 |
| complex | 1/10 | 7/10 | 1 | 2 |

配对结果：16 保持通过、9 改善为通过、2 由通过变为未通过、3 仍未通过／执行错误。运行上限均为 3 轮；最近 TaskManager 的 6 轮单样本成功不能替代本次结果。

## 五项未通过的证据

- **BudgetThreshold**：旧 v3 通过；本次初始 DOM 相似度 1.0。首次 repair 把模板的 `remaining`、`statusText` 改为 `this.data.get(...)`，最终渲染警告明确提示 `this.data` 未定义，最终结构相似度 0.75；3 轮耗尽。观察到 repair 产物引入模板回退，尚未修正本批输出。
- **TipSplitCalculator**：旧 v3 通过；本次静态 `custom_event_not_fire` 未消除，2 轮后因无进展停止，DOM 相似度 1.0。源组件唯一 `$emit` 位于没有内部调用的通用 `emitEvent` 方法，生成代码移除了该方法。当前检查未区分可达事件行为与公开辅助方法保留；需审查契约／校验范围，不能直接解释为界面事件丢失，也未据此改写失败评分。
- **LocalizationWorkspace**：3 轮后仍有 `hidden_template_reactive_dependency`。模板 `translationFor(record)` 隐藏读取 `language`；初始 DOM 相似度 1.0 不能证明切换语言时正确更新。
- **TaskManager**：repair HTTP 请求返回 `The read operation timed out`，保留了初始及两份 repair 产物，但没有完整最终报告。此项属于执行错误，不能推断为 3 轮内修复通过或失败。
- **MonitoringDashboard**：generation HTTP 请求返回相同超时，执行约 240.75 秒，属于执行错误，没有最终评估。

这两次 HTTP 400 的响应体写明上游读超时；不应将它们等同于组件语法失败或 API 密钥缺失。相同命令、相同协议的 checkpoint 恢复会跳过全部 28 条 `completed` 记录（其中包括 3 条失败），仅重新执行两个 `error` 样本的链路；它不会从 TaskManager 中断的 repair 步恢复。

## 用量与限制

summary 记录生成 650,037、repair 1,092,872、合计 **1,742,909 tokens**，repair 43 轮。这些聚合只包含正常完成的 28 项，未完整纳入 TaskManager 等异常执行的已发生用量，不能作为全批实际花费，也不能据此宣称成本降低。

本批为复用已接触样本的开发回归。模型采样及评估器变化都会影响结果，两个由通过变未通过的样本是本次观察到的退化，尚不能单凭一次运行归因到某条 Prompt。全部 28 个完成项的自动交互结果为空；自动通过不等于浏览器交互全部通过。启动健康检查记录 qwen/qwen-plus，磁盘代码 live 校验通过，但服务器进程加载字节没有独立证明。

## 下一步

先按原命令、不加 `--force` 恢复两个超时样本并保留本次快照。重试不得改模型、Prompt、轮数或超时。之后再封存新的执行状态、分析三项评估失败；系统修改须建立后续版本。v5 探索性评估继续等待这一步结果。

## 全部 30 项配对清单

| 组件 | 复杂度 | 旧 v3 | 当前 v4 | 观察结果 |
| --- | --- | --- | --- | --- |
| VolumeControl | simple | pass | pass | 保持通过 |
| NotificationCard | simple | pass | pass | 保持通过 |
| ReadingProgressCard | simple | pass | pass | 保持通过 |
| TextLengthGauge | simple | pass | pass | 保持通过 |
| BudgetThreshold | simple | pass | fail | 由通过变未通过 |
| OtpCodeInput | simple | pass | pass | 保持通过 |
| StockReservationBadge | simple | pass | pass | 保持通过 |
| TipSplitCalculator | simple | pass | fail | 由通过变未通过 |
| StatusSwitch | simple | pass | pass | 保持通过 |
| SearchClearField | simple | pass | pass | 保持通过 |
| BatchRenamer | medium | pass | pass | 保持通过 |
| HabitWeekTracker | medium | fail | pass | 改善为通过 |
| PlaybackQueue | medium | fail | pass | 改善为通过 |
| SeatBookingMap | medium | pass | pass | 保持通过 |
| BreadcrumbNavigator | medium | pass | pass | 保持通过 |
| ShippingEstimator | medium | pass | pass | 保持通过 |
| MeetingPollScheduler | medium | pass | pass | 保持通过 |
| CourseModuleAccordion | medium | fail | pass | 改善为通过 |
| DeliveryRouteTimeline | medium | pass | pass | 保持通过 |
| AudioSegmentMarker | medium | pass | pass | 保持通过 |
| AnalyticsDashboard | complex | error | pass | 改善为通过 |
| IncidentResponseBoard | complex | fail | pass | 改善为通过 |
| FleetDispatchConsole | complex | pass | pass | 保持通过 |
| TaskManager | complex | error | error | 仍未通过／执行错误 |
| MonitoringDashboard | complex | error | error | 仍未通过／执行错误 |
| RuleBuilder | complex | fail | pass | 改善为通过 |
| AccessMatrix | complex | fail | pass | 改善为通过 |
| LocalizationWorkspace | complex | fail | fail | 仍未通过／执行错误 |
| TripItineraryPlanner | complex | fail | pass | 改善为通过 |
| SchemaMappingWorkbench | complex | fail | pass | 改善为通过 |

复现本报告（只读冻结证据，不调用模型）：`python -m migration_pipeline.analyze_formal_30_v4_full_regression --snapshot data/experiments/snapshots/formal_30_v4_full_regression_results_20261030_215511`。逐样本错误与哈希见 `summary.json`。
