# 更长超时诊断：执行完成，组件仍未通过

日期：2026-11-02。来源快照 `formal_30_v4_timeout_diagnostic_v1_results_20261102_173627`（272 文件校验通过）。预运行协议 live 校验通过，旧完整 30 样本结果保持 25 通过、3 评估失败、2 执行超时，未被本诊断替换。

本诊断 **2/2 执行完成、0/2 自动通过、无执行超时**。两个样本均消耗 3 个 repair attempt。qwen/qwen-plus、温度 0.2、原 v4 实现保持；诊断 launcher 设置上游 600 秒、generation／repair 客户端 660 秒。实际服务配置依赖操作者按 launcher 重启，文件哈希与健康检查不能独立证明旧进程的超时值。

| 样本 | 总耗时（秒） | 确定性 repair 轮 | LLM repair 轮 | 停止原因 |
| --- | ---: | ---: | ---: | --- |
| TaskManager | 250.515 | 3 | 0 | max_repair_rounds_reached |
| MonitoringDashboard | 860.859 | 1 | 2 | repair_event_contract_regression |

## TaskManager：三轮预算在 LLM repair 之前耗尽

初次生成有模板、组件注册及响应式等多类问题。三轮确定性处理依次为：

1. 恢复 self-click／原生拖拽语义、展开 methods、补内联组件注册。
2. 规范空事件修饰符处理器、转换源布尔赋值事件。
3. 再次恢复 self-click／原生拖拽语义。

第一类归一化再次出现，表明规则间可能有交互；当前证据不足以断言无限循环。代码显示只要确定性计划改变产物，repair 阶段立即返回，不再进入该轮 LLM 请求；orchestrator 仍把它计作一轮。因此本次 **LLM repair 调用数是 0**，而不是“大模型修了三次仍不会”。

最终仍有 9 类静态错误：内联 Math／成员方法表达式、多个 fire payload、事件语法、循环别名及 trackby、computed 调实例方法、隐藏 tasks 响应式依赖、原地修改数组。初始 DOM 评估最终相似度 0.9889 并通过，不能替代这些语法／交互检查。

## MonitoringDashboard：第三轮被检测为事件契约退化

第 1 轮确定性归一化，第 2、3 轮调用 LLM。第 2 轮后剩 3 类静态问题，DOM 相似度 0.9605；第 3 轮引入 `missing_event_bindings`，触发 `repair_event_contract_regression`，并出现业务 initData 与 San 状态工厂冲突、渲染 `this.initData is not a function`。

最终静态错误为 reserved_init_data_method_collision、event_arguments_not_landed、lifecycle_behavior_not_landed、missing_event_bindings。保护门检测退化并停止、标记未通过；**没有回滚到第 2 轮**，报告 final_file_path 仍指向第 3 轮。第 2 轮本身也没有通过静态验证，不能改取它作为成功结果。

## 用量与证据限制

本次生成 204,063、repair 162,383、合计 **366,446 tokens**；确定性步骤使用 0 个 LLM token，但消耗 repair attempt。两项均有完整报告。原超时执行的未记录用量仍未被本次统计补齐。

本次避免了超时，说明执行层问题暂未复现；单样本总耗时不是每次 HTTP 请求耗时，不能据此证明两项都必须等待超过 240 秒，也不能声称更长超时已修复迁移质量。TaskManager 此前 6 轮单样本成功与本次随机新生成、3 轮混合预算不能直接等同。

## 下一步的开发修复计划

优先审查确定性规则的幂等性、规则间相互覆盖和轮数调度，给残留语义错误进入 LLM 的机会；单独记录确定性步骤数与 LLM 调用数。任何预算定义变化必须预先登记新版本，不能把旧 3 轮结果改写成另一种计数口径。再检查 repair 引入 initData 冲突与事件退化的拒收／候选保留行为，并联合原三个失败项做冻结产物回放。

当前只完成冻结、诊断和实验记录，尚未修改 Prompt、规则、轮数语义或生成产物。下一修复版先本地回放和边界验证，再做新的针对性模型回归，最后检查完整 30 项。v5 仍等待。

复现分析：`python -m migration_pipeline.analyze_formal_30_v4_timeout_diagnostic --snapshot data/experiments/snapshots/formal_30_v4_timeout_diagnostic_v1_results_20261102_173627`。
