# 70 组件通用修复：最新工程与冻结产物复核

本报告核对全部 70 个不同组件的 72 条历史记录。两个重复组件保留各版本，不拼成统一的新实验通过率。
这是已有模型产物的开发复核；新的真实模型调用为 0。源码、模型响应、旧报告和数据库记录未被改写。

## 当前已验证结果

- 当前冻结产物通过 17 条，历史通过 12 条；仍有 55 条未通过／无完整产物。
- 本次追加规则候选 7 条，接受 3 条、拒绝 4 条；退步候选仍回退。
- 174 项关联回归通过，真实模型调用 0。工程测试使用的注入模型客户端不是迁移成功证据。
- **尚未全部修复，不能据此保证下一轮新生成通过率。** 交互未配置仍是 not_run；验证集 20 项、测试集 10 项未运行。

## 各阶段记录数量

以下按 72 条记录计数；历史模型预算／版本并不统一，因此不是同协议通过率比较。

| 阶段 | 历史记录状态 | 当前离线状态 |
| --- | --- | --- |
| compile_runtime | {"pass": 54, "no_accepted_assessment": 2, "fail": 16} | {"pass": 56, "no_accepted_assessment": 2, "fail": 14} |
| static | {"fail": 42, "no_accepted_assessment": 2, "pass": 28} | {"fail": 33, "no_accepted_assessment": 2, "pass": 37} |
| structure | {"fail": 51, "no_accepted_assessment": 2, "pass": 14, "not_run": 5} | {"fail": 49, "no_accepted_assessment": 2, "pass": 17, "not_run": 4} |
| visual | {"pass": 51, "no_accepted_assessment": 2, "fail": 14, "not_run": 5} | {"pass": 53, "no_accepted_assessment": 2, "fail": 13, "not_run": 4} |
| source_baseline | {"pass": 64, "no_accepted_assessment": 2, "not_run": 5, "blocked": 1} | {"pass": 66, "no_accepted_assessment": 2, "not_run": 4} |
| interaction | {"not_run": 70, "no_accepted_assessment": 2} | {"not_run": 70, "no_accepted_assessment": 2} |

## 保留的批次边界

| 批次 | 条数 | 历史通过 | 当前离线通过 |
| --- | ---: | ---: | ---: |
| real_system_experiment70_v1_20261118 | 49 | 11 | 16 |
| real_system_experiment70_v2_generation_probe_20261118 | 2 | 0 | 0 |
| real_system_experiment70_v2_remaining21_20261119 | 21 | 1 | 1 |

## 全部历史问题类别覆盖

涵盖所有修复轮次／拒绝候选中的 49 类诊断，而不只是最终父版本的 38 类。
“当前未报告”可能是历史已经解决，不都归功于本轮修复；逐条保留历史最终是否仍报告。它也不等于记录整体通过。前置阻断不可观测的检查单列。

| 诊断 | 原记录 | 仍出现 | 当前未报告 | 前置阻断未观测 |
| --- | ---: | ---: | ---: | ---: |
| `custom_event_not_fire` | 2 | 0 | 2 | 0 |
| `dom_child_order_mismatch` | 6 | 2 | 4 | 0 |
| `duplicate_class_attribute` | 1 | 0 | 1 | 0 |
| `event_arguments_not_landed` | 1 | 1 | 0 | 0 |
| `hidden_template_reactive_dependency` | 7 | 2 | 5 | 0 |
| `invalid_dynamic_attribute_binding` | 1 | 0 | 1 | 0 |
| `invalid_s_for_key_binding` | 11 | 1 | 10 | 0 |
| `invalid_san_computed_namespace_access` | 1 | 1 | 0 | 0 |
| `invalid_san_data_store_array_access` | 1 | 1 | 0 | 0 |
| `invalid_san_directive_interpolation` | 1 | 0 | 1 | 0 |
| `invalid_san_event_handler_syntax` | 1 | 0 | 1 | 0 |
| `invalid_san_init_data_store_access` | 1 | 0 | 1 | 0 |
| `invalid_san_template_data_store_access` | 4 | 1 | 3 | 0 |
| `lifecycle_behavior_not_landed` | 3 | 2 | 1 | 0 |
| `missing_component_registration` | 2 | 0 | 2 | 0 |
| `missing_event_bindings` | 2 | 1 | 1 | 0 |
| `missing_event_handlers` | 3 | 1 | 2 | 0 |
| `missing_init_data` | 1 | 1 | 0 | 0 |
| `missing_lifecycle_mapping` | 2 | 1 | 1 | 0 |
| `missing_prop_defaults` | 63 | 2 | 61 | 0 |
| `missing_prop_dependent_initialization` | 2 | 2 | 0 | 0 |
| `missing_watch_migration` | 2 | 1 | 1 | 0 |
| `nested_state_mutation` | 6 | 3 | 3 | 0 |
| `rendered_control_position_mismatch` | 4 | 0 | 4 | 0 |
| `rendered_control_state_mismatch` | 39 | 12 | 27 | 0 |
| `rendered_dom_mismatch` | 62 | 47 | 15 | 0 |
| `san_style_scoped` | 1 | 1 | 0 | 0 |
| `source_class_binding_not_landed` | 5 | 0 | 5 | 0 |
| `source_computed_collection_not_landed` | 3 | 2 | 1 | 0 |
| `source_dom_event_not_landed` | 2 | 1 | 1 | 0 |
| `source_dom_loop_not_landed` | 10 | 0 | 10 | 0 |
| `source_dynamic_assignment_unproven` | 37 | 17 | 20 | 0 |
| `source_filter_method_not_landed` | 1 | 1 | 0 | 0 |
| `source_method_interface_not_landed` | 3 | 0 | 3 | 0 |
| `source_parent_initialization_not_landed` | 1 | 1 | 0 | 0 |
| `source_record_update_not_landed` | 1 | 1 | 0 | 0 |
| `source_render_dependency_not_landed` | 6 | 1 | 5 | 0 |
| `source_shared_record_projection_not_landed` | 1 | 1 | 0 | 0 |
| `target_browser_error` | 30 | 9 | 21 | 0 |
| `target_script_syntax_error` | 4 | 2 | 2 | 0 |
| `target_sfc_syntax_error` | 5 | 0 | 5 | 0 |
| `target_template_syntax_error` | 2 | 1 | 1 | 0 |
| `template_structure_mismatch` | 17 | 8 | 9 | 0 |
| `unbalanced_template_interpolation` | 1 | 0 | 1 | 0 |
| `unsupported_san_inline_template_math_global` | 1 | 1 | 0 | 0 |
| `vue_methods_wrapper` | 1 | 0 | 1 | 0 |
| `vue_props_option` | 2 | 1 | 1 | 0 |
| `vue_this_state` | 5 | 5 | 0 | 0 |
| `watch_registration_not_in_lifecycle` | 1 | 1 | 0 | 0 |

## 通用性与仍未完成的闭环

规则按源码 AST 形状、注册关系、完整调用体和字段证明匹配，不以组件名或业务方法名分支。生成仍为完整 SSM＋模型；有界规则只修复当前生成代码。
模板条件分支投影纠正、工厂字符串误报纠正属于评估器修复；真实缺失文本／节点、控件值／属性、事件参数／初始化与 computed 遗漏仍保留失败。
新增 source_computed_option_not_landed 检查会揭示以前漏报的普通方法／字段误映射；只对完整函数体与源 getter 翻译相同、无未知捕获／写入／方法调用者的候选自动搬迁。未证明的行为进入模型修复，不能直接放行。
内联数组 props 和纯字面量 data 工厂必须与源定义匹配才改写；已有 initData、默认值冲突、未知代码和歧义注册不覆盖。
DOM value／checked 属性差异仍严格保留；未将同一时刻 live value 相同当作属性契约等价，也未接入失败的 attr-value 候选。
复杂子组件、未知动态键／捕获、source/target caller 不一致、真实结构／控件缺失仍需后续有界规则与模型修复验证，详见 [逐记录遗留](remaining.json)。

## 原始证据与下一步

[本轮重放](../general_repairs_v5_computed_options_complete_20261119/summary.json) · [72 条详情](../general_repairs_v5_computed_options_complete_20261119/results.json) · [覆盖矩阵](coverage.json)
重放协议固定实现指纹。改变代码的候选用真实浏览器重新捕获；未改变代码的 DOM／像素复用已核验的同源同目标捕获，并重新执行解析、静态检查，不伪称全新运行。
需要 API／Worker 使用同一新代码重启后，另立不可变新批次再检验模型生成效果；旧失败和成本不得重写。无需再次初始化云数据库。
