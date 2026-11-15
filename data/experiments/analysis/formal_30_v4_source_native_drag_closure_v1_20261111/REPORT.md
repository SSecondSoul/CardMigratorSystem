# 有界原生拖拽方法体闭环 v1（2026-11-11）

本轮不是整批重生成或独立测试。原始成绩仍 24/30、6 失败、0 执行异常、1,821,544 tokens；模型请求 0；不改 canonical San、人工页、旧冻结结果，不 commit/push。

新增 source_native_drag_semantics.py/.cjs：按真实父注册映射唯一不逃逸的内联子组件，不用 TaskManager/方法/字段名特判。完整源 AST 必须证明：单一原生 dragstart 绑定、单事件参数、声明字段的禁用守卫、dataTransfer.setData 字符串格式与字段值、effectAllowed 字符串、单 payload emit 及源顺序。目标仅允许同源 guard/emit 与两条 transfer 操作的有序子集，可消去纯 const 字段别名；未知副作用、错误 MIME/值/guard/payload/次序、重复或非原生绑定、其他调用、动态 this 引用、构造器逃逸/mixins/框架替换均拒绝。源本身不在闭合形态内不发明修复。只替换通过证明的目标方法，保留其余字节。

residual_v2 修复前处理与返回后处理、共享 repair Prompt、Validate、候选保护同步；新增 source_native_drag_not_landed / source_native_drag_analysis_unavailable，补 lost_source_native_drag_contracts。generation/服务器 Prompt、legacy 前处理、父 watch/生命周期均不改。模型遵从 Prompt 效果未测，不把文字约束当修复证据。

新规则初次16项因测试误用 RepairPromptInput 参数失败1项（55.826秒），改正测试参数后16/16（51.475秒）；不隐藏失败，不归为组件回归。历史用例保留旧错误并增加新检测及组合预处理期望，不删旧断言、不篡改冻结原分数。最终独立完整套件 644/644、0失败、0跳过，1140.378 秒，日志 unit_tests.txt，非拼接散测。

累计30个冻结件重做静态/编译，仅 TaskManager 改写，原24个通过件字节未变且仍静态通过。当前 TaskManager 1→0 原生副作用错误，migration_hints_not_landed 警告保留；只重跑它的轻量初始 DOM。真实调度器注入冻结代码、禁止模型：1个确定性步骤、0 LLM、当前自动门通过；不是新批次或全交互验收。

用上轮冻结的San bundle合成事件装置复跑前后：6个拖拽场景保留排序、索引、drop.stop、dragover.prevent、元素身份；恢复 setData(text/plain,index) 与 effectAllowed=move，禁用时均不发生。新测试还记录 transfer→effectAllowed→emit 顺序。此前子工厂/首次props/根监听运行观察完全一致；父生命周期4存储分支与watch观察前后完全一致，父监听时机风险仍存在，不虚报已修复。无浏览器attach/原生手势、无真实存储/应用定时器；San3.15.6不是人工页3.15.3的验证。TripItineraryPlanner 外部渲染依赖仍未证明，不豁免。

运行清单 370 项；SHA覆盖代码、派生件、回放、测试日志、报告。上轮诊断Notebook代码含当时363项实时哈希断言，生产规则更新后该断言应提示漂移；保留历史40个单元，不改写为“旧版本从未失败”。新增单元校验冻结身份与新派生运行事实，不声称旧实时哈希断言仍全绿。下一步应单独建立源Vue异步watch/恢复存储/计时器顺序oracle后处理父监听，暂不付费复跑或准备独立测试。
