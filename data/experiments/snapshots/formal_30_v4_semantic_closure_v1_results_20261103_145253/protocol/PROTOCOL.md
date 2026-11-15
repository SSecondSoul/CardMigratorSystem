# 有边界语义闭环开发回归 v1

日期：2026-11-02。批次 formal_30_v4_semantic_closure_v1。TaskManager、MonitoringDashboard 为重复开发样本，不是独立测试集。原始 Vue 与前次输入相同，旧结果与冻结包不改写。

## 变更与边界

generation／服务器 Prompt 不变；repair Prompt、确定性规则、候选事件追溯检查改变。新增 AST helper 只解析代码，不执行生成代码；解析失败或超出边界保持不变。

事件包装只有在原 Vue 明确含对应 click.self、父组件包装体仅含 target/currentTarget 相等分支且调用原无参方法时才可追溯。带额外副作用、错误目标或错误实参不放行。San 裸处理器由解析器注入默认 $event，handler() 不传参；显式 wrapper($event) 是规范化而非裸处理器原本无效的证据。此前关于裸处理器不传参的判断已由真实 San listener 测试更正。

参数化 computed 只对内联子组件中返回纯算术箭头函数且没有其它用途／隐藏依赖的模式转换为普通方法。事件参数恢复仅对完整 SSM 源方法体可安全还原的小型同步处理器：参数／字面量、参数属性读取、对已声明根状态赋值、调用已存在组件方法。复杂控制流、未知全局、嵌套写入、不明确绑定保持不变，交给 LLM。

新规则用于 repair 确定性计划及 LLM 返回后处理；每轮仍重新静态与 DOM 评估，保护门与未通过标准保持。不宣称所有旧问题已被通用规则修复。

## 运行预算与证据

沿用 bounded_prepass_v1：每样本最多 3 次 LLM repair，每次之前最多 4 次确定性处理，总计至多 12 步；generation 1 次。qwen/qwen-plus，温度 0.2，上游 600 秒、两类客户端 660 秒。与上一调度批预算相同，但生成随机性、规则和 Prompt 同时变更，不作单因素因果推断；与原 3 混合 attempt 更不是等预算。按全部 token、拒收／回退分别记录。

冻结前执行完整测试、三份失败产物离线回放和 dry-run。MonitoringDashboard 冻结最终产物经新规则静态和初始 DOM 通过，不等同新生成的模型批通过或人工交互通过。TaskManager 最终候选仍四类问题、曾拒收候选仍两类问题；只证明合法 self 包装不会因追溯缺口被拒。

## 操作者执行

停止旧服务。在窗口 A 设置环境 LLM_API_KEY，然后运行：
`python -m migration_pipeline.run_formal_30_v4_semantic_closure --server`

窗口 B 运行一次：
`python -m migration_pipeline.run_formal_30_v4_semantic_closure --execute`

不加 --force。不自动复跑挑选结果。运行结束先冻结原始输出，再诊断、人工交互确认。此次只准备，不调用模型。旧 30 项历史分数不修改，之后仍需完整 30 项回归；v5 探索性评估等待。
