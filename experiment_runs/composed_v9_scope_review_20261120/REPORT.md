# 通用修复v9最终复核：明确区分规则效果与作用域校验修正

2026-11-20。只使用冻结实验源码／SSM／有效San产物；真实模型调用0、云库访问0、用户服务未重启。

## 结果

- 首轮混合70项仍12/70（v1的49项＋v2补充21项），真实模型v3仍15/70；不改写历史结果。
- v8有效离线35/70；v9主规则版本完成70项登记、69份有效代码重新评估（66份基线真实浏览器、3份脚本语法失败），为42/70，新增8项，但CourseModuleAccordion被局部module计数误报错误判失败。该完整42/70结果及原实现已冻结。
- 最后只修正父方法元数据的词法归属：最终有效离线 **43/70**，原通过现未通过：无。
- 相对v8新增通过：BatchRenamer、DataPaginationTable、FileDropIndicator、PollResults、SearchClearField、StatusSwitch、TipSplitCalculator、VolumeControl。
- 仍有27项未闭合；其中1项未知模型调用无完整产物不重试。不是新的生成通过率、独立测试或全部功能等价。

## 修复链与验证

主版本已接入导出父组件生命周期AST识别、最小纯初始化恢复及整份代码绑定的窄门、合法value绑定空白、原生属性／文本span恢复、class真实序列化。支持明确的export default和顶层唯一未遮蔽module.exports对象，未知组件覆盖／祖先展开／循环作用域等继续拒绝。生成与修复共享约束v6；仍是完整SSM＋模型，未恢复整组件规则生成／公开实例代理，预算及质量阈值不变。
主规则版本249项同版关联回归通过；实际回放后发现CourseModuleAccordion误报，再修正仅1个元数据函数：只计未被词法绑定遮蔽的module/exports引用，局部循环／回调变量不算导出逃逸，真正全局别名／San命名空间修改仍拒绝。保留2项修复前RED（1失败、1通过），修正后既有7项＋新增2项共9项AST专项在当前版本通过。249与9属于不同实现版本，明确分列，不虚报为258项同版通过。
最后一轮无任何组件代码修改或新规则提案。完整重新进行语法及静态检查：仅引擎元数据函数及其清单两文件变化，AST差异证明其余程序节点不变。源／目标代码、props、动作、阈值及全部渲染实现相同，才显式复用原真实浏览器捕获；不把旧恢复门证据重新授权。
- 当前新增真实浏览器捕获：1；明确复用v9相同代码捕获：65；3份脚本语法失败仍按语法优先停止，1项无产物。
- CourseModuleAccordion在当前版本额外做真实浏览器确认；独立目录系统再次实际运行通过（真实AST／LangGraph／API／下载／浏览器，模型为记录响应替身、云调用0）。
- 历史7166文件、v9主回放955文件前后哈希不变；旧失败、拒绝候选、中止预检、249项验证及42/70均保留。

## 剩余问题

见remaining.json、failure_analysis.json：6项动态赋值契约仍需watch／timer／调用体闭环，4项嵌套写回、3份损坏脚本、控件／DOM／SVG真实差异及尚未证明的渲染依赖等继续保留。源代码合法但证明不足，与生成代码真实缺陷分开分析，不以删除诊断或提高额度代替修复。

- rendered_dom_mismatch: 18个组件
- source_dynamic_assignment_unproven: 6个组件
- template_structure_mismatch: 5个组件
- rendered_control_state_mismatch: 4个组件
- nested_state_mutation: 4个组件
- target_script_syntax_error: 3个组件
- missing_event_handlers: 3个组件
- hidden_template_reactive_dependency: 2个组件
- source_class_binding_not_landed: 2个组件
- source_render_dependency_not_landed: 2个组件
- watch_registration_not_in_lifecycle: 2个组件
- missing_prop_defaults: 2个组件
- rendered_control_position_mismatch: 2个组件
- target_browser_error: 2个组件
- invalid_san_template_data_store_access: 1个组件
- model_response_unknown_no_automatic_retry: 1个组件
- duplicate_class_attribute: 1个组件
- invalid_san_computed_instance_method_call: 1个组件
- missing_init_data: 1个组件
- missing_lifecycle_mapping: 1个组件
- unsupported_san_inline_template_math_global: 1个组件
- event_arguments_not_landed: 1个组件
- missing_event_bindings: 1个组件
- missing_watch_migration: 1个组件
- dom_child_order_mismatch: 1个组件
- source_dom_event_not_landed: 1个组件
- source_computed_collection_not_landed: 1个组件
- source_filter_method_not_landed: 1个组件
- source_record_update_not_landed: 1个组件
- source_shared_record_projection_not_landed: 1个组件
- source_computed_option_not_landed: 1个组件

计数按组件内诊断去重，可重叠，不是人工独立缺陷数。下一步仍应在冻结失败产物上继续通用修复；本报告不建议立即启动另一次70项付费试跑来代替规则闭环。

## 证据入口

- ../composed_v9_scope_reassessment_20261120/：最终逐项静态检查、代码哈希、明确的捕获来源、当前额外浏览器确认及实现快照。
- ../composed_v9_verified_replay_20261120/、../composed_v9_review_20261120/：主规则版本完整原始42/70及249项同版回归。
- migration_system/docs/verification/2026-11-20_followup_v9/scope_red/与scope_verified/：同断言的RED／GREEN；tests_main_249.json与tests_current_9.json分别保留版本。
- ../composed_v9_final_replay_20261120/STOPPED.md：18项中止预检及CommonJS覆盖修正前实现，未混入最终统计。
