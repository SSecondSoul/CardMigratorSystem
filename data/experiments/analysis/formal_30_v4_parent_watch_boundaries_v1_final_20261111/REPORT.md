# 父监听异常与动态键边界诊断 v1（2026-11-11）

本轮只诊断上一轮明确未证明的分支，不修改生产规则/Prompt、canonical San 或测试页；0 模型请求。保留上轮正常流程修复及其 672/672 完整测试证据，不撤销它，也不扩大为异常/任意键均等价。原始批次仍为24/30、6失败、0执行异常、1,821,544 tokens，不是新批次或独立测试。

冻结源 Vue2.7.16 与上轮派生 San（San3.15.6）原字节不变。9 场景×2框架×10同步/观察阶段=18次运行、180份快照、90组对照。源业务方法、San代码均不改写；只在隔离 localStorage 中让一次 setItem 抛错。默认采用显式 Vue config.errorHandler 记录错误；另有 Node 无自定义 handler 对照，不把该配置说成浏览器默认策略。宿主监听 unhandledRejection 仅收集结果、保持进程继续，不给被测 Promise 加 catch，不替换原生调度器；最终移除监听。两个 setImmediate 只观察原生 Promise 队列与拒绝通知，不执行模拟的应用timer。无浏览器/DOM attach/真实存储；Vue用空根render，San直接调用attached、真实headless dispose。

| 场景 | 状态不同的阶段 | 业务效果不同的阶段 |
| --- | --- | --- |
| declared_same_value | 无 | 无 |
| declared_changed_value | 无 | 无 |
| restored_extra_key | 无 | 无 |
| new_key | primary_tick, repeat_sync, repeat_tick, recovery_sync | primary_tick, repeat_tick, recovery_tick, destroy_sync |
| new_undefined_key | primary_sync, primary_tick, repeat_sync, repeat_tick, recovery_sync, recovery_tick, destroy_sync, destroy_tick | 无 |
| inherited_key | primary_tick, repeat_sync, repeat_tick, recovery_sync | primary_tick, repeat_tick, recovery_tick, destroy_sync |
| prototype_key | primary_sync, primary_tick, repeat_sync, repeat_tick, recovery_sync, recovery_tick, destroy_sync, destroy_tick | primary_tick, repeat_tick, recovery_tick, destroy_sync |
| write_failure_captured | primary_tick, repeat_sync | primary_tick, repeat_tick, recovery_tick, destroy_sync |
| write_failure_headless_default | repeat_tick, recovery_sync, recovery_tick | repeat_tick, recovery_tick, destroy_sync |

动态键检查区分初始/恢复时已有的响应式键、事后新增普通键、同值undefined的新键、继承键及__proto__。同时记录 ownEnumerableKeys、ownUndefined、是否自有__proto__、原型身份与继承标记，避免 JSON.stringify 忽略undefined/原型而造成假等价。原型输入仅进入独立vm中的settings对象；宿主与沙箱Object.prototype都未改动。

上轮队列try/finally能复位，但不等于桥接Vue错误处理与继续剩余watcher的策略。未知键直接赋值、整个对象克隆、同值保护也不能无条件等价。本轮保存成功/失败的每次存储尝试、业务方法调用、timer启动/清理及恢复阶段，不能只比较最后画面或最终内存。异常路由单列，不过滤成“正常通过”。

具体观测：显式捕获策略下第一次保存抛错后，源tasks回调中止，但settings回调继续保存并启动30秒timer；目标整个flush中止，settings当轮未运行。下轮目标可再次工作，说明finally复位有效，却不能据此称错误策略相同。Node默认无自定义handler时，源本轮抛错且后续监听队列不再运行，目标finally复位后可恢复；因此也不能无条件“catch后继续”假装对齐两种策略。后续timer事件ID差异来自此前缺失启动，不是独立缺陷。

已有声明键和恢复对象中已存在的额外键作为三个控制场景，状态及业务效果全匹配。事后新增普通/继承键在源中无响应式通知，目标整对象替换则额外保存/启动timer；新增undefined时源会创建自有属性，而目标Object.is保护直接跳过，连属性形状都不同。__proto__在源中修改局部settings原型，在目标spread中变成自有键，既有形状差异也有效果差异。不把新增属性“修成响应式”，也不以只序列化JSON隐藏这些差别。

诊断测试 16/16，0失败/0跳过，1.355秒。现有382项清单原字节未变；本轮未重新运行完整672项，不能拼接成新的完整套件成绩。两项边界仍待工程化，不计为新的整批生产缺陷率，不继承人工通过。后续先确定可证明的错误策略/调用键范围，再实现规则、验证器、拒绝保护和对照回归；不得直接吞异常、假造Vue2新增属性通知或默认整组件已通过。

预检包parent_watch_boundaries_v1_20261111（7项payload、16/16、0.599秒）保留不覆盖。最终仅调整诊断用例：它读取冻结382项清单，不再强制未来生产代码一直等于旧实时指纹；CLI本轮只读盘点仍核对382项未变。该调整不改CJS装置/输入/观察或生产规则；最终独立重跑16项，不合并两次日志。Notebook首次验证命令曾超过Windows命令长度限制而未启动，缩小为只传单元指纹后验证成功；没有因此改生产代码或伪造测试结果。
