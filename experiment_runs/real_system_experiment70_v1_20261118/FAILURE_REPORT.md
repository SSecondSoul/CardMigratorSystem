# real_system_experiment70_v1_20261118 实验结果

状态：paused。已完成 49/70，通过 11，未通过 38，待运行 21。

仅统计本批新任务，不复用网页历史结果；未运行交互场景和人工验收。原始报告、候选、截图和收据保持不变。

## 失败归类与下一轮通用修复

以下按每种错误涉及的样本数统计，同一样本可以涉及多类错误，不等同于独立缺陷数。

- 结构或控件状态 / `rendered_dom_mismatch`：32 个样本（NotificationCard、BudgetThreshold、DeliveryPhaseCard、FileDropIndicator、OtpCodeInput、PasswordStrengthMeter、SearchClearField、StarRatingInput、StatusSwitch、TemperatureDial、TextLengthGauge、TipSplitCalculator、VolumeControl、TodoList、AttendanceRoster、AudioSegmentMarker、BatchRenamer、BreadcrumbNavigator、CourseModuleAccordion、DataPaginationTable、FormRulePlayground、HabitWeekTracker、ImageCropControls、KanbanColumnBoard、MeetingPollScheduler、PlaybackQueue、PollResults、QuizNavigator、ShippingEstimator、SurveyBranchForm、TransferList、WorkoutPlanner）。
- 其他待诊断 / `source_dynamic_assignment_unproven`：17 个样本（BookmarkToggleCard、InlineRename、ThemePreviewToggle、TipSplitCalculator、VolumeControl、AttendanceRoster、AudioSegmentMarker、BreadcrumbNavigator、CourseModuleAccordion、DataPaginationTable、FormRulePlayground、ImageCropControls、MeetingPollScheduler、PlaybackQueue、PollResults、SurveyBranchForm、TransferList）。
- 结构或控件状态 / `template_structure_mismatch`：8 个样本（InlineRename、StatusSwitch、ExpenseTracker、DataPaginationTable、KanbanColumnBoard、PollResults、QuizNavigator、SurveyBranchForm）。
- 结构或控件状态 / `rendered_control_state_mismatch`：6 个样本（TodoList、AttendanceRoster、KanbanColumnBoard、PollResults、QuizNavigator、WorkoutPlanner）。
- 语法或编译运行 / `target_browser_error`：4 个样本（KanbanColumnBoard、PollResults、QuizNavigator、WorkoutPlanner）。
- 静态语义或响应式 / `missing_prop_defaults`：2 个样本（KanbanColumnBoard、QuizNavigator）。
- 模型或调用预算 / `model_output_incomplete`：2 个样本（MonitoringDashboard、TaskManager）。
- 静态语义或响应式 / `hidden_template_reactive_dependency`：1 个样本（ExpenseTracker）。
- 静态语义或响应式 / `vue_props_option`：1 个样本（TodoList）。
- 静态语义或响应式 / `nested_state_mutation`：1 个样本（PlaybackQueue）。
- 静态语义或响应式 / `source_computed_collection_not_landed`：1 个样本（PlaybackQueue）。
- 结构或控件状态 / `dom_child_order_mismatch`：1 个样本（PollResults）。
- 静态语义或响应式 / `invalid_san_computed_namespace_access`：1 个样本（PollResults）。
- 结构或控件状态 / `invalid_san_template_data_store_access`：1 个样本（WorkoutPlanner）。
- 静态语义或响应式 / `missing_prop_dependent_initialization`：1 个样本（WorkoutPlanner）。
- 其他待诊断 / `vue_this_state`：1 个样本（WorkoutPlanner）。

整批完成前不修改迁移实现。完成后逐组检查源 Vue、初始 San、各修复候选和评估证据，区分迁移缺陷、评估误报和环境问题；先用冻结失败产物验证通用修复，再建立 v2 批次回归，不覆盖本批结果。
