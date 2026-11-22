# v3 与首轮 70 项逐项对照

同源配对；首轮由 v1 的 49 项与 v2 补充 21 项组成，配置不完全相同，不能称单版本基线。v2 两项复跑单独保留。

新一轮真实生成：15/70；未知调用 1 次，已知 Tokens 不包含未知用量。

配对变化：{"fail_to_pass": 5, "fail_to_fail": 53, "pass_to_pass": 10, "pass_to_fail": 2}

此前通过本轮未通过：DeliveryRouteTimeline、SeatBookingMap

此前未通过本轮通过：NotificationCard、BookmarkToggleCard、DeliveryPhaseCard、InlineRename、ThemePreviewToggle

以下为重叠检查发现，不能当成人工独立缺陷数；DOM 属性差异尚未因此获准忽略。

- rendered_dom_mismatch: 49
- source_dynamic_assignment_unproven: 19
- template_structure_mismatch: 12
- rendered_control_state_mismatch: 12
- source_computed_option_not_landed: 10
- duplicate_class_attribute: 10
- target_browser_error: 8
- missing_prop_defaults: 7
- nested_state_mutation: 6
- dom_child_order_mismatch: 5
- invalid_san_template_data_store_access: 4
- invalid_san_computed_namespace_access: 4
- target_script_syntax_error: 3
- source_class_binding_not_landed: 3
- missing_event_handlers: 3
- missing_lifecycle_mapping: 2
- hidden_template_reactive_dependency: 2
- source_render_dependency_not_landed: 2
- watch_registration_not_in_lifecycle: 2
- source_filter_method_not_landed: 2
- source_method_interface_not_landed: 1
- custom_event_not_fire: 1
- vue_this_state: 1
- missing_init_data: 1
- unsupported_san_inline_template_math_global: 1
- invalid_san_computed_instance_method_call: 1
- event_arguments_not_landed: 1
- missing_event_bindings: 1
- missing_watch_migration: 1
- source_dom_event_not_landed: 1
- source_record_update_not_landed: 1
- source_shared_record_projection_not_landed: 1
- source_computed_collection_not_landed: 1

原始失败、候选回退、全部轮次见 pairs.json / diagnostics.json / decisions.json。未调用模型或数据库；未改历史报告。
