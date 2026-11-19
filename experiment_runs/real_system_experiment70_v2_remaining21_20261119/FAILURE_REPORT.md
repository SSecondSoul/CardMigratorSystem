# real_system_experiment70_v2_remaining21_20261119 实验结果

状态：completed。已完成 21/21，通过 1，未通过 20，待运行 0。

仅统计本批新任务，不复用网页历史结果；未运行交互场景和人工验收。原始报告、候选、截图和收据保持不变。

## 失败归类与下一轮通用修复

以下按每种错误涉及的样本数统计，同一样本可以涉及多类错误，不等同于独立缺陷数。

- 结构或控件状态 / `rendered_dom_mismatch`：17 个样本（AccessMatrix、AnalyticsDashboard、CapacityPlanningBoard、CrisisCommunicationHub、DocumentApprovalFlow、EnergyLoadScheduler、ExperimentRolloutConsole、FleetDispatchConsole、GradebookMatrix、IncidentResponseBoard、InventoryBatchManager、MediaReviewStudio、SchemaMappingWorkbench、SupportTicketConsole、TripItineraryPlanner、WarehousePickingWave、WorkflowDiagramEditor）。
- 其他待诊断 / `source_dynamic_assignment_unproven`：11 个样本（CapacityPlanningBoard、CrisisCommunicationHub、DocumentApprovalFlow、EnergyLoadScheduler、FleetDispatchConsole、GradebookMatrix、IncidentResponseBoard、InventoryBatchManager、SupportTicketConsole、TripItineraryPlanner、WarehousePickingWave）。
- 结构或控件状态 / `rendered_control_state_mismatch`：8 个样本（AccessMatrix、AnalyticsDashboard、CapacityPlanningBoard、EnergyLoadScheduler、ExperimentRolloutConsole、InventoryBatchManager、SchemaMappingWorkbench、TripItineraryPlanner）。
- 语法或编译运行 / `target_browser_error`：7 个样本（AccessMatrix、AnalyticsDashboard、CapacityPlanningBoard、EnergyLoadScheduler、ExperimentRolloutConsole、InventoryBatchManager、TripItineraryPlanner）。
- 其他待诊断 / `vue_this_state`：4 个样本（AccessMatrix、CapacityPlanningBoard、ExperimentRolloutConsole、InventoryBatchManager）。
- 结构或控件状态 / `template_structure_mismatch`：3 个样本（AnalyticsDashboard、CapacityPlanningBoard、TripItineraryPlanner）。
- 静态语义或响应式 / `missing_prop_defaults`：2 个样本（AnalyticsDashboard、TripItineraryPlanner）。
- 静态语义或响应式 / `nested_state_mutation`：2 个样本（AnalyticsDashboard、TripItineraryPlanner）。
- 静态语义或响应式 / `lifecycle_behavior_not_landed`：2 个样本（CapacityPlanningBoard、InventoryBatchManager）。
- 静态语义或响应式 / `hidden_template_reactive_dependency`：2 个样本（ExperimentRolloutConsole、TripItineraryPlanner）。
- 静态语义或响应式 / `source_computed_collection_not_landed`：2 个样本（ExperimentRolloutConsole、TripItineraryPlanner）。
- 其他待诊断 / `source_render_dependency_not_landed`：2 个样本（ExperimentRolloutConsole、TripItineraryPlanner）。
- 语法或编译运行 / `target_script_syntax_error`：2 个样本（LocalizationWorkspace、TopologyEditor）。
- 结构或控件状态 / `dom_child_order_mismatch`：1 个样本（AccessMatrix）。
- 静态语义或响应式 / `missing_prop_dependent_initialization`：1 个样本（AccessMatrix）。
- 视觉或样式 / `san_style_scoped`：1 个样本（AccessMatrix）。
- 其他待诊断 / `duplicate_class_attribute`：1 个样本（AnalyticsDashboard）。
- 其他待诊断 / `invalid_san_data_store_array_access`：1 个样本（AnalyticsDashboard）。
- 静态语义或响应式 / `missing_event_handlers`：1 个样本（AnalyticsDashboard）。
- 其他待诊断 / `missing_init_data`：1 个样本（AnalyticsDashboard）。
- 静态语义或响应式 / `missing_lifecycle_mapping`：1 个样本（AnalyticsDashboard）。
- 结构或控件状态 / `unsupported_san_inline_template_math_global`：1 个样本（AnalyticsDashboard）。
- 静态语义或响应式 / `vue_methods_wrapper`：1 个样本（AnalyticsDashboard）。
- 静态语义或响应式 / `vue_props_option`：1 个样本（AnalyticsDashboard）。
- 静态语义或响应式 / `watch_registration_not_in_lifecycle`：1 个样本（AnalyticsDashboard）。
- 静态语义或响应式 / `event_arguments_not_landed`：1 个样本（CapacityPlanningBoard）。
- 静态语义或响应式 / `invalid_s_for_key_binding`：1 个样本（CapacityPlanningBoard）。
- 静态语义或响应式 / `missing_event_bindings`：1 个样本（CapacityPlanningBoard）。
- 其他待诊断 / `missing_watch_migration`：1 个样本（InventoryBatchManager）。
- 静态语义或响应式 / `source_dom_event_not_landed`：1 个样本（MediaReviewStudio）。
- 语法或编译运行 / `target_sfc_syntax_error`：1 个样本（RuleBuilder）。
- 静态语义或响应式 / `source_filter_method_not_landed`：1 个样本（TripItineraryPlanner）。
- 其他待诊断 / `source_parent_initialization_not_landed`：1 个样本（TripItineraryPlanner）。
- 其他待诊断 / `source_record_update_not_landed`：1 个样本（TripItineraryPlanner）。
- 其他待诊断 / `source_shared_record_projection_not_landed`：1 个样本（TripItineraryPlanner）。

整批完成前不修改迁移实现。完成后逐组检查源 Vue、初始 San、各修复候选和评估证据，区分迁移缺陷、评估误报和环境问题；先用冻结失败产物验证通用修复，再建立 v2 批次回归，不覆盖本批结果。
