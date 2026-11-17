# 公开实例代理 v5：root owner 生命周期与清理

2026-11-17。**已完成有限 root owner 连接验证，完整 Vue 生命周期／实例契约尚未完成，生产尚未接入。**

沿用用户“允许内部公开实例代理，先验证兼容性再接入”的授权。本轮在 `research/public_instance_v5` 以已封存 v4 为基线实施，旧版本、生产 Prompt／引擎／阈值／配置、源 Vue 和历史产物不改。

## 补齐的缺口

v4 验证了调用代理句柄 dispose 的部分清理，但没有连接 owner hooks。直接调用原生 San 实例的 `dispose()` 会绕过句柄，源响应式 scope／watcher 仍可能存活。两条路径不同，不能用句柄清理通过来推断原生销毁也通过。

v5 新增独立研究 helper `owner.cjs`，连接同一个代理句柄与原生实例，不导入主系统：

- 接入 `beforeMount`／`mounted`、`beforeUpdate`／`updated`、`beforeUnmount`／`unmounted` 六种 root hooks。
- hook 的 `this` 为公开业务 Proxy，San 原生 receiver 仍独立；业务 `data/attach/dispose` 同名字段不覆盖内部生命周期入口。
- hook 中的 `$watch` 归属 owner scope，原生 `dispose()`、加载方句柄 dispose 都经过同一清理路径。
- `beforeUnmount` 在旧 DOM、活动 scope 下执行；随后停止 owner watcher、执行 cleanup、取消排队的 watch／updated 工作，再销毁原生 DOM。
- root `unmounted` 时 DOM 已移除、scope 已停止，但逻辑 `isUnmounted` 仍为 false；hook 后才标 true，与本轮 Vue root 对照相符。
- 卸载后保留原 `$el` 引用用于已验证的读取，不因 San 清空 el 就丢失它；不是伪造 Vue vnode。
- 使用每实例方法包装，不改 San 全局原型；保留 dispose／attach 幂等及重挂载防护，恢复 Data.get/set 与 update 描述符。**不是宣称销毁后所有实例包装都消失**。

不会为不存在的 updated hook 凭空增加 post 工作。updated 回调进入既有渲染感知队列，避免破坏上一轮 nextTick／pre/post 顺序。

## 本轮实际证据

| 检查 | 结果与口径 |
| --- | --- |
| 新增 root owner 浏览器对照 | 同一探针：v4 0/6 一致，v5 6/6 一致，无 warning/error |
| hook 观察 | 顺序、this、count、实际 DOM、$el 文本、isMounted/isUnmounted、scope.active |
| 直接原生销毁 | watcher 不再运行、cleanup 一次，scope 停止 |
| mounted 创建 watcher | 存活时收到 1、2，销毁后不再收到 3 |
| 卸载前侧写 | beforeUnmount 的同步 watch 仍执行，排队 pre/post/updated 被取消，既有 nextTick 回调保留 |
| 显式记录错误策略 | hook 数组前项抛错后，后项和卸载清理继续；比较阶段名及 receiver |
| owner 边界控制 | 10 项：未知 hook、父级上下文、transition 字段及真实 s-transition 指令、描述符、重复绑定、外部 detach、借用 receiver、幂等清理、不可扩展实例 |
| owner 已连接的调度重放 | v4 原有 8 项实际调度场景一致 |
| owner 已连接的实际控件 | 输入、复选框、下拉、点号键输入一致，每页 7 条实际 watcher 回调 |
| 非 DOM 既有对照 | 94 项、写入 5 项及 8 项控制保持，私有 vnode 差异仍保留 |

**v4 的 0/6 仅表示新增 owner 场景此前未连接，不是既有测试通过率变成 0%，更不是论文组件迁移率。** 修复前的直接原生销毁路径保留作证据，旧 v4 通过的句柄清理结果不改写。

最终 v1 至 v5 合并 **28 项通过，70.162 秒**（旧 22 项及新增 6 项）。既有生产公开键／控件专项 **11 项通过，25.828 秒**。专项 6 项 19.309 秒、补 transition 指令前的合并 28 项 65.115 秒为中间结果，不累计。

Node render-null 夹具继续明确使用微任务渲染屏障测试替代，报告 `node_render_barrier_is_test_double=true`；实际 hooks／DOM／调度只由隔离 Edge 页证明。目标仍加载独立 VueReactivity，不加载 Vue 组件／渲染运行时，不能称为完全无 Vue 依赖。没有全系统、30 组件或真实模型重跑，也不是完整 SSIM／像素评估。

## 本轮真实失败

第一次连接后，原生 dispose 被外部 detach 防护挡住：San 的同步 dispose 内部也会调用 detach。修正为仅在 owner 已进入 unmounting 状态时允许这条内部调用；外部直接 detach 仍拒绝，不能把它当作 Vue unmount 或 KeepAlive。

封存前发现只检查实例 transition 字段不充分，增加真实解析的 s-transition 指令反例；补充后重跑合并回归及全部最终浏览器证据。中间文件不替代最终源码证据，未修改原生引擎来消掉失败。

## 还没有实现的边界

1. 当前是**受控单 root owner**，未实现父子树的 hook 排序、循环作用域、KeepAlive、Suspense、Teleport、过渡动画或异步卸载。存在父级／已知过渡入口会预先拒绝；不宣称已识别任意模板的所有隐藏复杂性。
2. 不支持 beforeCreate／created 等初始化 hooks、组合式 API 的 currentInstance 注入、SSR、所有异步 hooks／重入／递归更新及初始化失败恢复。beforeMount 中销毁仍明确拒绝。
3. 错误对照限显式根级记录策略，不证明默认抛错或祖先 errorCaptured 策略；未充分验证外部直接停止 effectScope、任意私有对象改写。
4. 完整 Vue 私有 vnode／实例图、部分原生 setter 重入、原生根级通知与嵌套 change 事件差异仍未闭合；development 内核触发钩子限制保留。
5. 仍是手工准备生命周期函数／模板的合成夹具，未从真实 SSM 自动编译、正式导出 SFC、接入真实生产加载器或规则／修复候选门。

保留 `arbitrary_public_key_contract_complete=false`、`production_admission_eligible=false` 与生产 `source_dynamic_key_contract_unsupported`。本轮的 root 夹具范围是证据边界，**不是把用户要求的任意公开键契约缩小后宣告实现**。

## 封存与下一步

七份最终报告和九份源码／测试，共 **16 payload**，封存于 [v5 验证目录](verification/2026-11-17_public_instance_proxy_v5/README.md)，SHA256SUMS.json 绑定最终文件。v1 至 v4 原封存、生产运行时基线及用户配置保持。

后续应验证父子／循环 owner 作用域及剩余私有契约，再连接真实编译／加载；不能仅凭本轮 root hooks 一致解除生产阻断。当前不需要重启或付费复跑；无模型、LangSmith、训练、实际数据库／队列写入、commit 或 push。
