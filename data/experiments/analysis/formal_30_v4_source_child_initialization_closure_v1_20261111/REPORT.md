# 注册子组件工厂／首次 props／watch 闭环 v1（2026-11-11）

本轮从源数组事务冻结件继续，不重新生成、不改 canonical San 或测试页、不继承人工通过，不是独立测试。原始成绩仍为 24/30、6 失败、0 执行异常、1,821,544 tokens；模型请求 0，不回填分数。

旧初始化 regex 只看到读取 task 与写入 formData，未证明值的类型/工厂语义。既有 inline formatter 规则只允许模板调用而拒绝脚本提及，故未覆盖源 createFormData(task) 被生成成 computed 返回函数的分支；inited 调 this.computed.createFormData(task) 写入函数而非对象。watch() 又覆盖 San 框架方法且不是自动注册钩子。上述在前层冻结输入即可复现，并非移动修复引入的回归；原有静态零错误不能追认为完整通过。

新增 source_child_initialization_semantics.py/.cjs。按完整 Vue 的真实父注册和唯一、不逃逸、同标签别名的子构造器映射；复用 registered AST 辅助函数，不靠组件名特判。只支持完整单参数纯新对象工厂、单个 prop→派生字段初始化、对应单个无 deep/immediate 的源 watcher。规范化单 return 条件表达式与唯一 if/else-return，并比较全部对象字段、spread/数组副本、默认值及参数。拒绝未知调用/闭包/突变、返回原对象、工厂体不符、未知生命周期/监听效果、重复注册、其他脚本/模板调用、构造器逃逸、mixins/extends 等不明确分支，不做全局 computed/watch 替换。

恢复工厂为顶层可调用方法；在 inited 先按首次 props 创建派生对象，再使用 San 内建 watch 注册一次，移除仅包含该源监听的 watch 方法。未知钩子内容保留原字节并拒绝自动修复，不强行移动。新对象与 tags 副本保留源浅拷贝语义，不声称深克隆。

本地已安装 San 源码 component.js 的 watch 会比较数据对象引用，data.js 的嵌套 set 会复制祖先对象；直接 watch('task') 可能因 task.title 更新而重置草稿。目标回调使用第二参数 change.change.expr.paths.length===1 保持本规则限定的浅根替换语义，不能靠无效第三参数 deep:false。真实 San 验证根替换触发、嵌套更新不触发、初始对象先于注册、无重复初始化；未扩展到深监听、路径监听或任意 watcher 语义。

前处理、stub 模型返回后处理、共享 repair Prompt、验证器与候选保护同步；新增 source_child_factory_not_landed、source_child_watch_not_landed、source_child_initialization_analysis_unavailable。注册/工厂/根路径守卫删除或改坏必须回退。generation/服务器 Prompt 和 legacy 非 residual_v2 前处理未改，不需要启动服务。新规则首轮 20/20（58.456 秒）；9 项受影响历史用例 9/9（89.050 秒）通过；无本轮测试失败被隐藏。历史精确断言只加初始化错误与组合步骤，不删旧诊断、不豁免旧失败；完整套件独立重跑，不将散测拼为全通过。

开发只读 30 项预检完成、不写证据；随后补强动态 this/this.computed 成员、动态 data.get 与模板未知工厂调用的拒绝边界，新规则再次单独 20/20（53.235 秒）通过。最终从稳定代码重新执行完整套件与全部回放，预检不冒充最终冻结结果。

完整测试 614/614、0 失败，999.702 秒，输出 unit_tests.txt。冻结前后在真实 San 子组件上复现 function→object、内建 watch 恢复；以冻结 Vue 原纯工厂为运行 oracle，验证新建/编辑、根替换/嵌套不重置、空值默认、标签/跨实例隔离及源输入不被写坏。子组件从构造到 inited/watch 执行，不 attach 完整父组件、不启动 UI/定时器；因此不是完整浏览器/全业务通过。

30 个累计输入重做静态验证/编译，仅 TaskManager 改写，24 个原始通过件原字节且仍静态通过。TaskManager 当前两条 factory/watch 错误变为 0，保留 migration_hints_not_landed 警告；不是 splice 复发，也不是原始批次新跑分。仅它重做轻量初始 DOM，其余视觉标记沿用前层。真实 bounded 调度器读取冻结输入、禁止模型：1 个确定性步骤、0 次 LLM，自动门 final_passed=true。正向接受、反向拒绝、固定点、独立规则与组合前处理一致。

TripItineraryPlanner 上轮外部渲染辅助依赖风险仍失败、不豁免。完整父组件初始化/watch 时机、浏览器弹窗与原生拖放、持久化/计时器联动仍未完整运行；未知源工厂/watch 形态仍需人工审查。不宣布独立测试、整个迁移器普适正确或组件全交互通过。下一步审查父生命周期与整条拖拽事件链，再决定是否配置人工验收；暂不付费复跑。

运行清单 363 项，SHA256SUMS 覆盖代码、派生 San、回放/运行观察、报告和完整日志；旧原始、协议和各层冻结包不改，未 commit/push。调度器 output_sha256 为规范化 UTF-8 文本身份，与文件字节 SHA 分开复算。
