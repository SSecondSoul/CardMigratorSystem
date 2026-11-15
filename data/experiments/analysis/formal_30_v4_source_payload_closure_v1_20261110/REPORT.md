# 源自定义事件双端单 payload 闭环 v1（2026-11-10，部分修复）

原始批次仍为 24/30、6 失败、0 执行异常、1,821,544 tokens。输入是前一 DOM 闭环冻结派生件及已披露累计输入，不是重新生成批次、独立测试或人工通过。真实模型请求 0，标准产物/人工测试页不改。

新增 source_payload_semantics.py/.cjs，以完整 Vue SFC 的真实子组件注册和 SSM inline_definition AST 一致为前提，按源元素结构、循环/条件作用域证明 source inline emit 与目标 method/direct fire 参数逐项相同，再用实际父接收方法形参命名对象字段。只支持 2–4 个普通形参和简单参数路径。所有同事件发送入口和对应父实例一起修改；接收方法签名/方法体/其他调用保持原字节。拒绝未知 handler、冲突别名、构造器逃逸、多余消费者、源/目标动态或额外 emitter、destructuring、动态模板和结构不匹配；这些 unsupported/review 不是等价通过。

本冻结 TaskManager 有 4 个 settings-panel.update 发送入口、1 个父实例。打包 key/value，并把父绑定改为 updateSettings($event.key,$event.value)。不是只把 fire 改成对象而让父方法继续接收错位参数。已有 syncInterval 数值转换及英文键名通知保留源行为；不擅自汉化源文案。规则没有 TaskManager 组件名分支。

residual_v2 确定性前处理、模型返回后处理、共享 repair Prompt、验证器及候选保护均接入。新增 source_event_payload_not_landed/source_event_payload_analysis_unavailable；只修一端仍诊断，丢失已映射契约或反向重引入缺陷拒绝。事件追溯只接受双端源码证明的明确解包绑定，不按别名猜测。

开发首轮 15 项中 2 失败（33.727 秒）：未声明的其他注册别名边界不足；stub 后处理会追加末尾换行导致过强的全文断言。前者收紧为同一规范化源标签别名，后者仅忽略已有格式化末尾换行，不放宽协议断言。后续 15/15 通过（32.613 秒）。扩展组合执行 60 项中 2 失败（98.453 秒）来自历史 DOM/formatter 精确诊断数预期；保留旧 9 类与逐节点 DOM 诊断，只另核对新增 payload 残留，组合前处理则必须确实闭合两端。这些是开发控制台摘要，不冒充保留了原始失败完整日志。

最终完整测试 533/533、0 失败，645.017 秒；完整日志另存。真实 San fire/listener 夹具验证对象解包和冻结件的默认视图、两个 false 布尔值、syncInterval 字符串转数字；仅构造不 attach，未启动浏览器、初始化/存储/同步 hook，也不证明整套设置 UI 已通过。stub 后处理不是模型调用。

另一次 24 项定向检查中 1 失败（56.696 秒）：历史 MonitoringDashboard 非法 JavaScript 产物在新增分析器下正确保留 analysis_unavailable，但旧精确诊断集合未列入。仅追加该不可证明诊断，保留原编译失败及所有旧错误，不追改原冻结结果。真实设置入口和两项历史组合用例另有 3/3 通过（28.020 秒）。最终完整结果以本次完整日志为准。

30 个累计输入重新静态验证/编译，仅 TaskManager 新改写；原始 24 通过件字节不变且仍静态通过。仅 TaskManager 重做轻量初始 DOM，其余视觉标志沿用前层冻结结果，不将累计修补拼成新分数。先前 5 类静态残留中的 multi-argument fire 关闭；新验证又将同一事件的双端契约列为一条重叠诊断，当前输入按新验证为 6→4，不是原始实验曾有 6 类错误。仍有 Math/成员模板调用、隐藏响应依赖、任务原地修改，validation_passed=false。

正向候选接受、逆向拒绝、固定点、前处理一致均验证。原始及前层 SHA 不改。新 San 仅留在本目录，不继承旧人工确认。下一步处理渲染显式依赖、moveTask 复制/提交顺序，并继续审查初始化/拖拽方法体；不要立即付费复跑或验收仍失败的中间件。
