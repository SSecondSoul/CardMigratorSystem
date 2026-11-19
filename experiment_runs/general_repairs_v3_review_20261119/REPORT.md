# 通用修复 v3：冻结产物离线重放复核

这是已有产物的开发重放，不是 70 项新生成实验，不合并 v1／v2 的通过率。真实模型调用为 **0**。

- 覆盖 70 个不同组件、72 条运行记录、38 类历史诊断。
- 当前离线通过 15 条；规则实际修改 13 条；遗留 57 条。
- 3 条历史未通过记录在当前检查通过；0 条历史通过记录未复现通过（逐项保留，不删样本）。
- 原始冻结文件完整性：True；实现重放期间未变动：True。

## 全部历史诊断类别覆盖

“未再出现”只描述这次重测中的该诊断，不表示其他维度／全部交互／任意输入等价。

| 诊断 | 原记录 | 仍出现 | 未再出现 | 因前置阻断未观测 |
| --- | ---: | ---: | ---: | ---: |
| `rendered_dom_mismatch` | 49 | 48 | 1 | 0 |
| `source_dynamic_assignment_unproven` | 28 | 18 | 10 | 0 |
| `rendered_control_state_mismatch` | 14 | 11 | 3 | 0 |
| `target_browser_error` | 11 | 8 | 3 | 0 |
| `template_structure_mismatch` | 11 | 11 | 0 | 0 |
| `vue_this_state` | 5 | 5 | 0 | 0 |
| `missing_prop_defaults` | 4 | 1 | 3 | 0 |
| `hidden_template_reactive_dependency` | 3 | 2 | 1 | 0 |
| `nested_state_mutation` | 3 | 3 | 0 | 0 |
| `source_computed_collection_not_landed` | 3 | 3 | 0 | 0 |
| `dom_child_order_mismatch` | 2 | 2 | 0 | 0 |
| `lifecycle_behavior_not_landed` | 2 | 2 | 0 | 0 |
| `missing_prop_dependent_initialization` | 2 | 2 | 0 | 0 |
| `source_render_dependency_not_landed` | 2 | 1 | 1 | 0 |
| `target_script_syntax_error` | 2 | 2 | 0 | 0 |
| `target_sfc_syntax_error` | 2 | 0 | 2 | 0 |
| `vue_props_option` | 2 | 2 | 0 | 0 |
| `duplicate_class_attribute` | 1 | 0 | 1 | 0 |
| `event_arguments_not_landed` | 1 | 1 | 0 | 0 |
| `invalid_s_for_key_binding` | 1 | 1 | 0 | 0 |
| `invalid_san_computed_namespace_access` | 1 | 1 | 0 | 0 |
| `invalid_san_data_store_array_access` | 1 | 1 | 0 | 0 |
| `invalid_san_template_data_store_access` | 1 | 1 | 0 | 0 |
| `missing_event_bindings` | 1 | 1 | 0 | 0 |
| `missing_event_handlers` | 1 | 1 | 0 | 0 |
| `missing_init_data` | 1 | 1 | 0 | 0 |
| `missing_lifecycle_mapping` | 1 | 1 | 0 | 0 |
| `missing_watch_migration` | 1 | 1 | 0 | 0 |
| `san_style_scoped` | 1 | 1 | 0 | 0 |
| `source_dom_event_not_landed` | 1 | 0 | 1 | 0 |
| `source_filter_method_not_landed` | 1 | 1 | 0 | 0 |
| `source_parent_initialization_not_landed` | 1 | 1 | 0 | 0 |
| `source_record_update_not_landed` | 1 | 1 | 0 | 0 |
| `source_shared_record_projection_not_landed` | 1 | 1 | 0 | 0 |
| `target_template_syntax_error` | 1 | 1 | 0 | 0 |
| `unsupported_san_inline_template_math_global` | 1 | 1 | 0 | 0 |
| `vue_methods_wrapper` | 1 | 0 | 1 | 0 |
| `watch_registration_not_in_lifecycle` | 1 | 1 | 0 | 0 |

## 遗留项与下一步

详见 [逐记录遗留清单](remaining.json)。DOM value 属性、真实缺失节点／文字／控件、未知动态键，以及内联 Vue 语法等仍失败的情况不放行。
先完成必要的通用规则／证明修订与反例验证；重启当前云库配置的 API／Worker 后，再冻结新批次做真实模型实验。不要恢复旧实现检查点或直接提高预算。

## 原始证据

[重放摘要](../general_repairs_v3_final_replay_20261119/summary.json) · [72 条原始重放记录](../general_repairs_v3_final_replay_20261119/results.json) · [覆盖矩阵](coverage.json)

自动通过仍只代表已配置 props／检查场景；本批未配置的交互和人工确认不能由离线结果代替。
