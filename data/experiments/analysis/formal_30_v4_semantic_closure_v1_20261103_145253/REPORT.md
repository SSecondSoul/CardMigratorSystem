# 有边界语义修复 v1：实际模型回归仍未通过

日期：2026-11-03。运行 14:15:45–14:51:57（UTC+8）。批次 `formal_30_v4_semantic_closure_v1`。原始快照 `formal_30_v4_semantic_closure_v1_results_20261103_145253`（290 文件验证）；冻结时协议 270 项 live 哈希校验通过。仅重复开发样本，不是独立测试。原完整 30 项和历史快照不变。

## 总结

**2/2 执行完成、0/2 自动通过、0 执行错误**。两项都达到 3 次 LLM repair 上限，无候选回退。未做新的人工交互验证，初始 DOM 通过不表示计算或动态功能正确。

| 样本 | LLM repair 调用 | 确定性步骤（均接受） | 最终 DOM 相似度 | 自动结论 |
| --- | ---: | ---: | ---: | --- |
| TaskManager | 3 | 2 | 0.9889 | 未通过 |
| MonitoringDashboard | 3 | 1 | 0.9605 | 未通过 |

生成 204,621、repair 554,944、合计 **759,565 tokens**。TaskManager 总用时 991.610 秒，MonitoringDashboard 1180.015 秒；不是各次请求耗时。与前调度版同为最多 3 次 LLM repair，但前次实际只调用 5 次、本次 6 次，且生成代码不同，不能作等消耗或单因素因果比较。

## TaskManager：包装追溯改善，但出现未拦截的非事件退化

两步确定性处理均被接受：第一步恢复源 self／原生拖拽、解开 directive、展开 methods、补内联组件注册；第二步规范空修饰符事件。closeModal 的源 self 包装被追溯为 onSelfClickCloseModal($event)，此后 LLM 改写为 onModalOverlayClick($event) 也被正确追溯，没有再因此阻止修复。

第一次 LLM 后 4 条问题（3 类），第二次后 2 类，第三次后 3 类：missing_data_types、invalid_san_computed_instance_method_call（isOverdue）、hidden_template_reactive_dependency（getTaskCount 隐藏 tasks 读取）。隐藏依赖在第二次已消除、第三次重新出现；保护门仍接受第三次。

这是现有保护门覆盖不足的直接证据：它检查事件契约、部分关键编译／initData 冲突及视觉通过退化，**没有覆盖所有静态语义缺陷的复发**。此前回退机制不等于对所有问题防退化。第二次候选本身也未通过，不能取它回填成功。

TaskManager 每轮 repair Prompt 约 44 万字符（444145／441376／440707）。missing_data_types 不在当前语义聚焦错误集合内，导致后两次仍进入完整提示而非已有聚焦提示；可从路由条件确认这个触发点，但不能据此断言它是全部失败原因。源码父组件没有 props，整个输出脚本也没有 dataTypes；这是当前格式校验错误，需结合内联子组件 props 契约审查，不能以添加空 dataTypes 或放宽验证来换取通过。

## MonitoringDashboard：旧模式未必复现，剩余是另一种 computed 与生命周期契约

一次确定性处理接受，三次 LLM 后残留分别为 8 条（5 类）、2 类、2 类。第一次 LLM 的后处理实际运行 restored_source_parameterized_event_handler，说明新增规则确已接入；最终没有事件参数丢失、参数化 computed 当方法、self guard、initData 命名冲突等错误码。不能仅凭缺少这些错误码保证全部交互通过，也不能把与不同初始产物的差异全归因于新规则。

最终残留：invalid_san_computed_instance_method_call（getX、getY）和 lifecycle_behavior_not_landed（源 mounted 中 initData 行为契约）。这里是 computed 回调调用组件实例方法，不是前次离线通过的“computed 返回纯算术箭头 formatter”模式，后者的窄规则不应猜测改写此复杂情况。

导出父组件 attached 调用 initDataImpl，但其函数体缺少源 initData 最后的 loadSettings 调用；localStorage 加载被展开移动到了 inited。不能简单断言“完全没有加载设置”，但动作所在时机、调用链与源契约不相同，验证器保持失败，需审查初始化及 watcher 顺序后决定实现，不静默豁免。

## 下一步建议（本次尚未实现）

1. 先补 TaskManager 第二次→第三次的冻结回放用例，把明确已修复的隐藏依赖等语义复发纳入有边界拒收／候选保留；避免只比较总错误数或只拦事件，不把较早失败候选当成功。
2. 审查 dataTypes 契约与聚焦路由，修复 computed 实例方法共享计算和显式响应式依赖；对生命周期按源调用链及时间顺序恢复，添加正反例。
3. 使用本快照离线验证、建立新版本，再运行针对性模型回归，最后完整 30 项回归。不要直接 --force 重抽本批，不把上次离线 MonitoringDashboard 通过当作本次重新生成已通过。v5 继续等待。

本次只冻结、诊断并追加记录；未改运行期 Prompt／规则／checker、未改生成 San／测试页、未提交或推送。

复现：`python -m migration_pipeline.analyze_formal_30_v4_semantic_closure --snapshot data/experiments/snapshots/formal_30_v4_semantic_closure_v1_results_20261103_145253`。
