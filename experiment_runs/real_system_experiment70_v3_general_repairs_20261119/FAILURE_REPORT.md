# real_system_experiment70_v3_general_repairs_20261119 实验结果

状态：completed。已完成 70/70，通过 15，未通过 55，待运行 0。

仅统计本批新任务，不复用网页历史结果；未运行交互场景和人工验收。原始报告、候选、截图和收据保持不变。

## 失败归类与下一轮通用修复

以下按每种错误涉及的样本数统计，同一样本可以涉及多类错误，不等同于独立缺陷数。

- 结构或控件状态 / `rendered_dom_mismatch`：49 个样本（BudgetThreshold、FileDropIndicator、OtpCodeInput、SearchClearField、StarRatingInput、StatusSwitch、TemperatureDial、TextLengthGauge、TipSplitCalculator、VolumeControl、ExpenseTracker、TodoList、AttendanceRoster、AudioSegmentMarker、BatchRenamer、BreadcrumbNavigator、CourseModuleAccordion、DataPaginationTable、FormRulePlayground、HabitWeekTracker、ImageCropControls、KanbanColumnBoard、MeetingPollScheduler、PlaybackQueue、PollResults、QuizNavigator、ShippingEstimator、SurveyBranchForm、TransferList、WorkoutPlanner、AccessMatrix、AnalyticsDashboard、CapacityPlanningBoard、CrisisCommunicationHub、DocumentApprovalFlow、EnergyLoadScheduler、ExperimentRolloutConsole、FleetDispatchConsole、GradebookMatrix、IncidentResponseBoard、InventoryBatchManager、LocalizationWorkspace、MediaReviewStudio、RuleBuilder、SchemaMappingWorkbench、SupportTicketConsole、TripItineraryPlanner、WarehousePickingWave、WorkflowDiagramEditor）。
- 其他待诊断 / `source_dynamic_assignment_unproven`：19 个样本（AudioSegmentMarker、DeliveryRouteTimeline、ImageCropControls、KanbanColumnBoard、MeetingPollScheduler、PollResults、SeatBookingMap、ShippingEstimator、TransferList、CrisisCommunicationHub、DocumentApprovalFlow、FleetDispatchConsole、GradebookMatrix、IncidentResponseBoard、InventoryBatchManager、LocalizationWorkspace、SupportTicketConsole、TripItineraryPlanner、WarehousePickingWave）。
- 结构或控件状态 / `template_structure_mismatch`：12 个样本（StatusSwitch、TipSplitCalculator、BatchRenamer、DataPaginationTable、FormRulePlayground、ImageCropControls、KanbanColumnBoard、PollResults、AccessMatrix、CapacityPlanningBoard、MediaReviewStudio、RuleBuilder）。
- 结构或控件状态 / `rendered_control_state_mismatch`：12 个样本（TipSplitCalculator、TodoList、BatchRenamer、FormRulePlayground、KanbanColumnBoard、PollResults、AccessMatrix、CapacityPlanningBoard、GradebookMatrix、MediaReviewStudio、RuleBuilder、SchemaMappingWorkbench）。
- 语法或编译运行 / `target_browser_error`：8 个样本（BatchRenamer、PollResults、AccessMatrix、CapacityPlanningBoard、GradebookMatrix、MediaReviewStudio、RuleBuilder、SchemaMappingWorkbench）。
- 静态语义或响应式 / `missing_prop_defaults`：7 个样本（TipSplitCalculator、BatchRenamer、FormRulePlayground、PollResults、AnalyticsDashboard、GradebookMatrix、MediaReviewStudio）。
- 结构或控件状态 / `dom_child_order_mismatch`：5 个样本（TipSplitCalculator、BatchRenamer、PollResults、AccessMatrix、LocalizationWorkspace）。
- 静态语义或响应式 / `nested_state_mutation`：4 个样本（PlaybackQueue、AnalyticsDashboard、MediaReviewStudio、TripItineraryPlanner）。
- 语法或编译运行 / `target_script_syntax_error`：3 个样本（PasswordStrengthMeter、MonitoringDashboard、TopologyEditor）。
- 静态语义或响应式 / `missing_event_handlers`：3 个样本（ExpenseTracker、HabitWeekTracker、AnalyticsDashboard）。
- 静态语义或响应式 / `source_computed_option_not_landed`：3 个样本（AttendanceRoster、DocumentApprovalFlow、WarehousePickingWave）。
- 静态语义或响应式 / `missing_lifecycle_mapping`：2 个样本（VolumeControl、AnalyticsDashboard）。
- 静态语义或响应式 / `hidden_template_reactive_dependency`：2 个样本（ExpenseTracker、ExperimentRolloutConsole）。
- 结构或控件状态 / `invalid_san_template_data_store_access`：2 个样本（ExpenseTracker、KanbanColumnBoard）。
- 静态语义或响应式 / `source_class_binding_not_landed`：2 个样本（ExpenseTracker、MediaReviewStudio）。
- 其他待诊断 / `source_render_dependency_not_landed`：2 个样本（ExpenseTracker、ExperimentRolloutConsole）。
- 静态语义或响应式 / `watch_registration_not_in_lifecycle`：2 个样本（ExpenseTracker、AnalyticsDashboard）。
- 静态语义或响应式 / `custom_event_not_fire`：1 个样本（TipSplitCalculator）。
- 静态语义或响应式 / `source_method_interface_not_landed`：1 个样本（TipSplitCalculator）。
- 模型或调用预算 / `model_response_unknown_no_automatic_retry`：1 个样本（TaskManager）。
- 其他待诊断 / `vue_this_state`：1 个样本（AccessMatrix）。
- 其他待诊断 / `duplicate_class_attribute`：1 个样本（AnalyticsDashboard）。
- 静态语义或响应式 / `invalid_san_computed_instance_method_call`：1 个样本（AnalyticsDashboard）。
- 其他待诊断 / `missing_init_data`：1 个样本（AnalyticsDashboard）。
- 结构或控件状态 / `unsupported_san_inline_template_math_global`：1 个样本（AnalyticsDashboard）。
- 静态语义或响应式 / `event_arguments_not_landed`：1 个样本（CapacityPlanningBoard）。
- 静态语义或响应式 / `invalid_san_computed_namespace_access`：1 个样本（CapacityPlanningBoard）。
- 静态语义或响应式 / `missing_event_bindings`：1 个样本（CapacityPlanningBoard）。
- 其他待诊断 / `missing_watch_migration`：1 个样本（InventoryBatchManager）。
- 静态语义或响应式 / `source_dom_event_not_landed`：1 个样本（MediaReviewStudio）。
- 静态语义或响应式 / `source_computed_collection_not_landed`：1 个样本（TripItineraryPlanner）。
- 静态语义或响应式 / `source_filter_method_not_landed`：1 个样本（TripItineraryPlanner）。
- 其他待诊断 / `source_record_update_not_landed`：1 个样本（TripItineraryPlanner）。
- 其他待诊断 / `source_shared_record_projection_not_landed`：1 个样本（TripItineraryPlanner）。

整批完成前不修改迁移实现。完成后逐组检查源 Vue、初始 San、各修复候选和评估证据，区分迁移缺陷、评估误报和环境问题；先用冻结失败产物验证通用修复，再建立 v2 批次回归，不覆盖本批结果。
