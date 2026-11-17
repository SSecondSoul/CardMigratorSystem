# 公开实例代理 v4：渲染完成与 nextTick 调度

2026-11-17。**研究调度修复已验证，完整生命周期／任意公开键契约尚未完成，未接入生产。**

本轮继续“允许内部公开实例代理，先验证兼容性再接入”的授权。以已封存 v3 为基线，在 `research/public_instance_v4` 验证；不修改 v1/v2/v3、源 Vue、生产引擎、Prompt、阈值或配置。

## 本轮实际复现了什么

先对原 v3 运行新的实际浏览器探针，而不是把已有通过当作完整调度证明。同一组 **8 个有限场景中，v3 只有 3 项一致、5 项不同**：

| 场景 | v3 差异 | v4 结果 |
| --- | --- | --- |
| 没有 watcher，赋值后 await $nextTick | 源 DOM 已为 1，目标仍为 0 | 一致，DOM 为 1 |
| nextTick 回调返回值与 receiver | receiver／返回值正确，但回调读到旧 DOM | 一致，含 DOM、this、返回值 |
| 同轮及空闲的 nextTick Promise 身份 | 没有保留源 Promise 共享关系 | 一致 |
| 只有 pre watcher | tick 在原生 DOM 更新前返回 | pre 读旧 DOM，tick 读新 DOM |
| post watcher 又写入状态 | 新 post 提前执行，tick 仍读到旧 DOM | 新 pre→新渲染→新 post→tick 顺序一致 |
| 空闲 tick 的微任务顺序 | 已一致 | 保持，不凭空插入渲染轮 |
| 卸载前已注册 tick | 已一致 | 保持；watch 被取消，既有 tick 回调仍执行 |
| 渲染已结束后的空闲 tick | 已一致 | 保持，不因旧标记多等一轮 |

最后三项是保留的既有一致性，不冒充本轮新修复。v3 的失败不会被回填成通过。

## 修改方式

1. **真实原生通知与完成标记连接。** 在原生通知之后登记由加载方提供的 `nextRender` 完成标记；实际浏览器使用 `san.nextTick`。等待队列和关联渲染完成，而不只等 watcher Promise。
2. **post 队列按批执行。** 回调中新增加的 post 工作留到下一轮；先执行该轮 pre 工作并等待对应原生渲染，避免连续排空 post 导致顺序倒置。
3. **保留 Promise 共享。** 同一活动轮复用完成 Promise，空闲复用已完成 Promise。不能为修正 DOM 等待而改变每次空闲 tick 的微任务顺序。
4. **不把卸载等同于取消全部 Promise。** 停止 owner watcher 后，已经登记的 tick 回调仍按实测结果完成；加载方清理仍独立于公开业务字段。

以上只覆盖已列出的受控场景，不是复刻整个 Vue 调度器，也没有实现 Vue 全部生命周期 hooks、组件树或私有 vnode 图。

## 测试与证据

- **实际浏览器前后对照**：source／target 各一张隔离 Edge 页；v3 3/8 一致，v4 8/8 一致。无 warning/error，目标 `Vue=false`、`VueReactivity=true`。全部判断直接读取 `$nextTick` 返回时的 DOM，不在判断前额外等待 San 来掩盖差异；仅夹具之间做清理隔离。
- **v4 实际控件回归**：另外两页复用 v3 的输入框、复选框、下拉框、字面点号键测试，状态、DOM 和每页 7 条 watcher 回调一致。
- **非 DOM 原生对照**：原有 94 项一致，原生写入 5 项及 8 项控制仍通过；私有 vnode 差异仍保留。
- **最终工程回归**：v1/v2/v3/v4 合并 **22 项通过，50.132 秒**（旧 17 项及新增 5 项）；既有生产公开键／控件 **11 项通过，28.071 秒**。中间专项 5 项 16.708／27.132 秒不累计。

### Node 探针与真实浏览器要区分

原生对照在 Node 中没有 DOM，源 Vue 也使用 render-null host。v4 新的渲染标记使这类探针调用到本机 San 的 MessageChannel 调度分支；实测探针可打印结果但进程不退出，本地源码中该分支未关闭 channel。两次未退出运行已中断，不能算完成通过。

因此 v4 的**非 DOM 夹具**显式注入微任务渲染屏障替代，报告写 `node_render_barrier_is_test_double=true`；它只验证状态、身份、watcher 等非 DOM 行为。**真正的 San 调度和 DOM 结论只来自独立浏览器探针**，没有用 Node 替代结果证明浏览器正确，也未修改 engine 或全局 MessageChannel。这个测试宿主调整不是生产运行时变更。

最终 5 份报告（native、native_writes、before_v3、after_v4、controls_browser）及 6 份源码／测试共 **11 payload** 封存在 [v4 验证目录](verification/2026-11-17_public_instance_proxy_v4/README.md)，以 SHA256SUMS.json 绑定最终版本。旧中间结果不替代最终包。

## 还没有完成的部分

- 完整 Vue 私有实例／vnode 图、父子组件和循环作用域仍未实现。
- 完整 mounted／updated／卸载 hook、祖先异常捕获、所有重入与调度交错、递归更新保护仍未证明。本轮仅验证有限卸载清理，不宣称生命周期整体等价。
- v3 的原生 setter 同步重入、缺失父对象、根级通知与原生嵌套 change 事件的差异仍保留。
- 独立响应式内核仍依赖 development 触发钩子，仍是新增 VueReactivity 依赖，而非“完全无 Vue”。
- 仍未连接真实 SSM 自动编译、正式 SFC 导出、真实加载器和生产候选门。

保持 `arbitrary_public_key_contract_complete=false`、`production_admission_eligible=false` 和 `source_dynamic_key_contract_unsupported`，不增加固定键白名单或缩小外部契约来放行。本轮不重跑全部系统、30 组件或真实模型，不把工程用例数计为论文样本数。

下一步应处理 owner 生命周期／作用域连接及剩余私有契约边界，再考虑真实组件接入。当前不需要用户重启或付费复跑；无模型、LangSmith、训练、实际数据库／队列写入、commit 或 push。
