# formal_30_v1 and formal_30_v2 results analysis

## Evidence and reporting boundary

- v1 snapshot: `formal_30_v1_results_20261015_161053` (115 verified files)
- v2 snapshot: `formal_30_v2_manual_results_20261022_152408` (78 verified files)
- `formal_30_v1` is the independent 30-sample automatic baseline.
- `formal_30_v2` is a post-hoc manual browser diagnosis and targeted-repair layer for 14 registered samples.
- The v2 14/14 manual result must not be described as a 100% automatic success rate on 30 samples.

## formal_30_v1 aggregate

| Metric | Value |
| --- | --- |
| Configured | 30 |
| Completed | 29 |
| Automatic passed | 16 |
| Automatic failed | 13 |
| Execution errors | 1 |
| Pass rate among completed | 55.17% |
| Pass rate among configured | 53.33% |
| Initial passed | 3 |
| Repaired to pass | 13 |
| Repair rounds total / average | 51 / 1.759 |
| Generation / repair / total tokens | 701,340 / 1,767,836 / 2,469,176 |

## Complexity breakdown

| Complexity | Configured | Completed | Passed | Failed | Errors | Completed pass rate | Configured pass rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| simple | 10 | 10 | 9 | 1 | 0 | 90.00% | 90.00% |
| medium | 10 | 10 | 5 | 5 | 0 | 50.00% | 50.00% |
| complex | 10 | 9 | 2 | 7 | 1 | 22.22% | 20.00% |

## formal_30_v2 manual review

- Registered and manually passed: 14/14
- Samples with a v2 code artifact: 11
- Samples confirmed without code modification: 3
- v1 distribution inside the reviewed set: {'execution_error': 1, 'failed': 8, 'passed': 5}
- v1 automatic passes with browser-visible defects: DeliveryPhaseCard, EnergyLoadScheduler

| Sample | Level | v1 auto | v2 changed | Primary category | Manual result | Observed issue |
| --- | --- | --- | --- | --- | --- | --- |
| DeliveryPhaseCard | simple | passed | yes | 循环作用域绑定 | passed | 阶段推进后颜色不随活动阶段变化。 |
| PollResults | medium | passed | no | 未发现差异 | passed | 人工浏览器检查未发现 Vue/San 差异。 |
| ImageCropControls | medium | failed | yes | 初始化或生命周期迁移 | passed | 缺少初始裁剪框；参数不能驱动画布；宽高比锁定样式与功能异常。 |
| AttendanceRoster | medium | passed | no | 未发现差异 | passed | 人工浏览器检查未发现 Vue/San 差异。 |
| InventoryBatchManager | complex | failed | yes | 模板隐藏响应式依赖 | passed | 单行选择和全选后，选择样式不更新。 |
| MediaReviewStudio | complex | failed | yes | 嵌套状态直接修改 | passed | 决策和批注操作不生效，提交批注会触发页面刷新。 |
| EnergyLoadScheduler | complex | passed | yes | 模板隐藏响应式依赖 | passed | 切换运行时段后文字变化，但按钮颜色不更新。 |
| ForecastSimulator | complex | failed | yes | 初始化或生命周期迁移 | passed | 缺少初始模拟结果、图表、汇总和月度明细。 |
| TopologyEditor | complex | execution_error | yes | 嵌套状态直接修改 | passed | 标题缺失，节点移动和连线不生效，模拟日志不持续更新。 |
| DocumentApprovalFlow | complex | passed | no | 未发现差异 | passed | 人工浏览器检查未发现 Vue/San 差异。 |
| CapacityPlanningBoard | complex | failed | yes | 模板语法错误 | passed | 错误的 s-for/trackby 语法导致 San 模板解析失败。 |
| GradebookMatrix | complex | failed | yes | DOM 子节点顺序 | passed | 复选框与百分号相对输入框的位置和 Vue 不一致。 |
| SupportTicketConsole | complex | failed | yes | DOM 子节点顺序 | passed | 内部备注复选框和文字的先后位置与 Vue 不一致。 |
| ExperimentRolloutConsole | complex | failed | yes | 模板隐藏响应式依赖 | passed | 选择胜出版本后，表格行颜色不实时更新。 |

## Primary defect taxonomy

Primary categories are mutually exclusive and support percentage reporting. The CSV sample table also retains non-exclusive multi-label categories for compound defects.

| Primary category | Samples | Share of reviewed set |
| --- | --- | --- |
| 模板隐藏响应式依赖 | 3 | 21.43% |
| 未发现差异 | 3 | 21.43% |
| DOM 子节点顺序 | 2 | 14.29% |
| 初始化或生命周期迁移 | 2 | 14.29% |
| 嵌套状态直接修改 | 2 | 14.29% |
| 循环作用域绑定 | 1 | 7.14% |
| 模板语法错误 | 1 | 7.14% |

## Thesis-ready interpretation

1. The unbiased automatic baseline passed 16 of 30 configured samples (53.33%), or 16 of 29 normally completed samples (55.17%).
2. Difficulty had a strong effect: configured-sample pass rates were 90.00% for simple, 50.00% for medium, and 20.00% for complex components.
3. Repair converted 13 samples from initial failure to automatic pass, but the pipeline still left 13 completed failures and one execution error.
4. Manual browser review covered 14 targeted samples. Eleven required code changes and all 14 passed after recheck.
5. DeliveryPhaseCard and EnergyLoadScheduler had passed the v1 automatic evaluator but still contained browser-visible state-style defects. This demonstrates an evaluator blind spot; it does not establish a false-positive rate for all automatic passes because the manual subset was targeted rather than random.
6. The most frequent mutually exclusive categories in the reviewed set were hidden reactive dependencies and confirmed no-discrepancy cases (three samples each). Compound labels additionally expose lifecycle, event conversion, DOM order, nested mutation, timer, and validator issues.
7. Any Prompt, validator, or migration-rule changes derived from these 14 samples are post-hoc development work. A new untouched holdout is required for an unbiased estimate of the improved system.
