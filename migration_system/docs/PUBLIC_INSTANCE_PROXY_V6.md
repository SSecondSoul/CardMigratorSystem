# 公开实例代理原型 v6：父子 owner 与 keyed 作用域（部分闭合）

2026-11-17。**四个有限树场景仅三个一致；keyed 重排仍失败，不接入生产。** 这是代理研究版本，不是新的 formal／pilot 批次，也没有新增论文迁移样本。

本轮继续用户允许内部公开实例代理、先兼容验证再接入的授权。研究源码位于 research/public_instance_v6，保留 v1 至 v5 文件与封存，不改生产引擎、生成／修复 Prompt、阈值、配置、源 Vue 或历史产物。

## 已实现的研究连接

- 子 owner 根据实际 San runtime.owner 查找已登记父 owner；未知父级拒绝，不用组件名猜父级。
- 私有 capability 连接逻辑 parent/root 的真实记录，公开 $parent/$root 指向相应业务 Proxy；子项的 effectScope 与父项独立。
- 同一 owner family 内的 nextTick 等待已登记成员的队列和实际渲染，子项变更不只等待父项自己的队列。
- 初始 root 在真实 DocumentFragment 中构建后一次插入，子 mounted 与 root mounted 按子先父后的顺序执行；不是修改探针读到的 DOM。
- 父级批量销毁按当前 DOM 顺序清理已登记子项，保留子 DOM 到父级移除，unmounted 在真实移除后按子先父后执行。
- 子项单独移除时，其 unmounted 排入父级 post 队列；停止对应 scope，不把所有兄弟项 scope 一起停止。不同 root family 彼此隔离。

这些只连接受控同步 owner，不是完整 Vue renderer、私有 vnode 图或通用循环编译器。

## 实际结果：不能把 3/4 写成全部通过

| 树场景 | v6 结果 |
| --- | --- |
| 实际父子挂载／卸载顺序、DOM、scope、$parent/$root 身份 | 一致 |
| keyed 重排、删除、重新加入，保留存活项身份与局部状态 | **不一致，保留失败** |
| 父销毁取消子项排队 pre/post watcher，既有 tick 完成 | 一致 |
| 两个独立 root family 不互相停止 scope | 一致 |

旧 v5 在这四个新增树场景为 0/4，因为此前仅连接单 root；这不是旧测试或论文通过率变成 0%。新 v6 为 3/4，无 warning/error。报告仍为 owner_tree_difference_observed。

### 未解决的 keyed 差异

初始 a/b/c，各子项局部 count 为 1；列表改为 c/b 后，Vue 保留 b 的实例和 count=1。当前 San 路径却销毁并重建 b，变成 count=0。

另外运行了**不含公开 Proxy、响应式内核和 owner helper 的原生 San 对照**，相同模板 `s-for="item in ids trackBy item"`、相同列表变化，同样得到：

```json
{"bSame":false,"cSame":true,"bDisposed":true,"dom":["c:1","b:0"]}
```

因此当前证据将此具体失败定位到所固定 San 3.15.6 的原生 keyed 更新路径，而不是“Prompt 又退化”或 owner 代理独有问题；**尚未定位算法内部的具体缺陷行，也未证明其他 key／模板都失败**。没有修改旧 engine、忽略 key、只比最终 DOM、缓存补回局部状态，或把重建当作等价来放行。

## 回归与证据口径

- owner 已连接的既有 root 6 项、实际调度 8 项及控件回归保持；控件每页仍有 7 条实际 watcher 回调。
- 非 DOM 原生 94 项、写入 5 项和 8 项控制保持，root 防护 10 项保持；非 DOM 渲染屏障继续明确是测试替代，不能证明 DOM。
- 最终 v1 至 v6 合并工程检查 **34 项通过，93.577 秒**，包括旧 28 项和新增 6 项；**其中有“确认 keyed 失败仍被识别”的反例断言，所以不是树场景全部通过。**
- 生产公开键／控件专项 **11 项通过，30.039 秒**。专项 6 项 20.819 秒为中间结果，不叠加。
- 目标页加载独立 VueReactivity，没有 Vue 组件／渲染运行时，不能称为完全无 Vue 依赖。

未全量运行系统、30 组件或真实模型；没有完整像素／SSIM 评估。所有场景仍由可信夹具手工准备组件和生命周期函数，不是 SSM 自动编译成功证据。

## 开发中的实际失败

首轮只有 2/4 一致：San 初始挂载会较早暴露父容器／前一个子项 DOM，批量销毁兄弟项顺序也与源不同。使用真实离线 DOM 构建、父级顺序清理及保留子 DOM 后，对照提升至 3/4。保留旧中间 JSON，不把它们说成最终源码证据。

keyed 的 b 实例重建在上述修正前后均存在，并由原生对照复现；当前未修复。

## 剩余边界与下一步

1. **优先定位并修复这个已封存的原生 keyed 重排差异**，形成有版本边界的修复和回归，再谈生产整合；不能继续靠模型复跑或补 Prompt 证明它消失。
2. 本轮没有验证动态子 props 更新、任意深度组件树、全部循环表达式／key 类型、跨独立 root 的全局调度关系。报告明确 dynamic_child_prop_updates_verified=false。
3. 完整私有实例／vnode 图、初始化 hooks、组合式注入、祖先异常捕获、过渡／异步卸载、KeepAlive、递归保护等旧缺口仍保留。
4. 实际 SSM 编译、SFC 导出、生产加载器和修复候选门仍未接入。

保持 arbitrary_public_key_contract_complete=false、production_admission_eligible=false 及生产 source_dynamic_key_contract_unsupported。有限夹具范围不代替用户要求的任意公开键契约。

最终八份报告及十份源码／测试共 **18 payload** 封存于 [v6 验证目录](verification/2026-11-17_public_instance_proxy_v6/README.md)，SHA256SUMS.json 校验。生产基线、旧证据和用户配置保持。无模型、LangSmith、训练、实际库／队列写入、commit 或 push；当前无需重启或付费复跑。
