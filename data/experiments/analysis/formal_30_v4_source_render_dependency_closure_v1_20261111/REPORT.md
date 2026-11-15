# 父模板只读渲染依赖 DAG 闭环 v1（2026-11-11，部分修复）

原始批次仍为 24/30、6 失败、0 执行异常、1,821,544 tokens。这是接续源内联渲染调用冻结派生件的离线开发回归，不是独立测试或新生成批次；本轮模型请求 0，不改标准 San 与人工测试页，不继承人工通过，不回填原始分数。

问题：父模板 getTaskCount(filter.value) 隐藏 tasks，且其 overdue 分支间接调用 isOverdue。只改根方法或只加 Prompt 不能证明整条调用链响应性。新增 source_render_dependency_semantics.py/.cjs，按完整 Vue、导出 San 父组件、同路径/作用域/静态 class/邻接文本的根调用映射，建立无环只读方法图；规范化 Vue 字段读和 San data.get 及顶层 const 数据别名后，比较完整函数体、分支、参数与所有实例调用边。

有界规则只接受源证明的数组 filter、Math 纯操作与新建局部 Date 的指定方法；拒绝递归、未知/外部调用、突变、传统函数回调、未知数组、全局遮蔽/显式重写、上下文漂移和依赖字段被循环别名遮蔽。Date 仍按原调用时刻求值，不发明时钟字段或自动刷新定时器，也不声称已证明环境原型绝对未被外部代码篡改。

保留公开 getTaskCount/isOverdue 签名、函数体及全部脚本调用者；增加私有只读图副本，把 tasks 经模板根及所有需要它的内部调用显式传递。原方法区和 CSS 不改，验证重分析需证明完整副本，而不是看辅助函数名或错误数减少。现有已显式传依赖的公共方法也须完整体/参数/调用边证明，不能只凭名称豁免。

修复前处理、stub 模型后处理、共享 repair Prompt、验证器、候选保护一致接入。新增 source_render_dependency_not_landed / source_render_dependency_analysis_unavailable；丢失已匹配绑定或引入错误均拒绝，正向进展可接受。旧非 residual_v2 前处理不启用新规则。generation/服务器 Prompt 未改，本轮无需启动服务器。

开发首轮 18 项测试 1 error（33.642 秒）：测试夹具方法 state 与真实冻结类状态同名冲突；改夹具名为 fixture_state，不放宽生产规则。随后 19/19（43.572 秒）通过。测试包含真实安装 San 的公开解析/求值器与 data.set、显式间接依赖、公开调用者、固定时钟下六个任务分支、无效日期、参数/字段/图体篡改、未知调用/突变拒绝、正反向保护、前后处理与 legacy 边界。这些控制台摘要不是保存了完整开发失败日志的声明。

完整套件 573/573、0 失败，760.131 秒；输出 unit_tests.txt。30 个累计输入重做静态验证/编译，仅 TaskManager 改写；原始 24 个通过件字节未变且仍静态通过。TaskManager 只重做轻量初始 DOM，其余视觉标记沿用前层，不冒充浏览器全交互复验。

TaskManager 当前校验从 3 条到 1 条：旧 hidden_template_reactive_dependency 与新重叠源契约诊断关闭，仍有 moveTask 的 nested_state_mutation，validation_passed=false。因此不是整个组件通过，也不切换人工页面。正向候选接受、反向拒绝、固定点、组合前处理等于独立规则已复核。

跨样本审查：LocalizationWorkspace 的 translationFor(record,language) 已显式带 language，完整 AST 证明后原字节保留。TripItineraryPlanner 是原始失败样本的既有 parent-props 离线派生件；dayCount 经外部 dayCountGetter/filter 隐藏 items，超出本规则实例 DAG 范围。新增校验暴露这一既有未证明路径，派生件现行 validation_passed=false；未改其字节、不豁免、不称本次修复引入回归，也不继续沿用此前派生件的整体验证通过结论。原始 24/30 不受其影响。

历史精确诊断断言只补新契约/组合步骤，保留旧诊断和 fail-closed 要求；旧冻结报告不改。event-v3 单例额外复核 1 项失败（8.805 秒），是精确错误集合漏列新计数契约，真实位置为 template/div[0]/div[2]/div[0]/div[1]/button[0]/span[0]#text:0@getTaskCount。核对后只补错误码及该位置，仍要求 prepare fail closed，不修改规则豁免；保留此开发失败摘要，不冒称保存完整失败日志。

首次历史组合检查为 197 项、1 失败（292.172 秒），唯一失败同为上述 event-v3 精确集合。修正断言后的 event-v3 与 MonitoringDashboard 第三次历史件复测 2/2（17.243 秒）通过；不将 196/197 拼为完整通过，之后从稳定清单重跑完整套件。开发只读 30 项预检期间更新过测试/重放脚本，因此清单一致性保护按设计拒绝该预检完成，不写冻结成功包，最终重放须重新执行。

清单 355 项，SHA256SUMS 覆盖本包代码、报告、测试日志与中间 San。下一步优先闭合任务移动的不可变更新，再审查初始化/拖拽实际行为；Trip 外部辅助函数另列待审查，不以继续付费试跑代替闭环。
