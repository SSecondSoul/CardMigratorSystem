# 公开实例代理原型 v7：修复已封存的 keyed 实例重建

后续进度见 [San 业务实例实现记录](SAN_BUSINESS_RUNTIME_V1.md)：已继续实现自动内联树、有限父事件／祖先错误和读取时序；本页保留 v7 原研究事实。新导出尚未接入此页的 keyed 内存候选，也未完整发布，不能混用两份结果。

2026-11-17。继续用户授权的“先验证兼容性再接入”。**本轮修复的是 v6 已复现的特定原生 keyed 差异，不是宣布任意公开键契约全部实现，也未接入生产。** 不修改旧 v1 至 v6／封存、固定 engine、生成／修复 Prompt、评估阈值、用户配置、源 Vue 或历史付费产物。

## 根因及修复位置

固定 San 3.15.6 的 `ForNode.prototype._updateArray` 以首子项 `nodeType === ELEM` 判断是否可直接移动。在 trackBy 的 LIS 路径中，普通元素可直接 `insertBefore`；组件仅保留 LIS 中无需移动的项，其他组件进入 dispose／重建分支。因此 a/b/c 改为 c/b 时，b 虽然 key 未变，却被销毁，局部 count 从 1 丢成 0。

这不是生成 Prompt 把 count 写错，也不是仅代理层造成：v6 无 Proxy／响应式内核／owner 的原生对照已复现。源码定位位于内置 San 的 `src/view/for-node.js`，本轮**没有修改该文件或 dist 原件**。

研究层新增 `research/public_instance_v7/san_candidate.cjs`，只对确切版本与确切 dist SHA-256 的源文本生成内存候选：

1. 精确验证 San 版本 3.15.6、上游 SHA-256 与唯一补丁锚点；不匹配立即失败，不静默套用。
2. 在 keyed 更新的移动／销毁前检查全部旧组件：已同步挂载、同一实际 DOM 父级、只有一个真实元素根、无 `_rootNode`／范围节点及过渡。
3. 对已检查的单元素根组件启用原有元素移动路径，保留实例、scope、监听器与局部状态；不缓存或回填 count，不丢弃 key，不仅比较最终文本。
4. 不支持的形状或有歧义的 key 显式拒绝；普通元素原路径保持。

这是一个**版本锁定、研究层的通用形状修复**，不按组件名特判。它不是生产生成阶段或 LLM 修复 Prompt 修改，也不将候选偷偷覆盖到 node_modules。

## 有限证据

- 同一四个实际 owner 树场景：未修改 v6 **3/4**，v7 候选 **4/4**，无 warning/error。父子 hooks／DOM／身份／scope、keyed 删除重排重插、排队 watcher 清理、独立根隔离同时比较。
- 无代理原生最小对照：旧为 bSame=false、bDisposed=true、c:1/b:0；候选为 **bSame=true、bDisposed=false、c:1/b:1**。
- 另有 Vue／原 San／候选 San 三页原生探针：**13 次连续列表更新**，每轮重新创建同 key 的数据对象，验证保留身份、局部 count、原生 props／索引传播及 DOM 点击事件；以及普通元素 keyed 路径。两个限定案例均与 Vue 一致，原 San 的组件案例不一致，普通元素案例原已一致。
- 9 项真实拒绝控制：fragment 根、条件根、组件根、s-transition 指令、transition 属性、重复 key、保留属性名、数字 key、Symbol key。抛出明确研究错误时，DOM 与旧子实例仍保持；**源 Data 已被设置，不承诺事务回滚**。这是实际 ForNode 更新，不是仅测试自写 predicate。
- 既有 owner root **6 项**、实际调度 **8 项**、真实输入／勾选／下拉控件及每页 **7 条** watcher 回调，均以同一候选 San 运行。
- 非 DOM 94 项、原生写入 5 项／8 控制、owner 防护 10 控制保留。非 DOM 测试仍使用原 San 与明确的渲染屏障替代；不能用它们冒充候选浏览器时序证明。

目标代理页加载独立 VueReactivity，不加载 Vue 组件／渲染运行时；三页原生探针的两个 San 页则连 VueReactivity 也不加载。没有虚构“完全无 Vue 依赖”的生产结论。

### 如实保留的额外差异

扩展原生探针首轮整体比较失败。逐步检查发现 13 轮更新的所有字段均一致，差异仅在最后直接原生 dispose 整棵树：源顺序 a/b，原 San 与候选均为 b/a。**keyed 移动补丁没有修复 raw San 的最终销毁顺序。**

最终报告将列表更新案例与最终销毁观察分别列出，保留源／原 San／候选的完整结果及 `native_disposal_order.equal=false`，没有删掉反例再宣称全面一致。owner 桥接后的树销毁由既有 v6 helper 处理，四项树探针继续比较真实卸载顺序／DOM／scope。本次不扩改原生整树 dispose。

初轮中间 JSON 留在 var，不能当作最终源码证据。修正探针分项记录并增加真实拒绝控制后，重新运行最终证据与工程检查。

## 工程回归及封存

最终 v1 至 v7 合并 **41 项通过（110.122 秒，旧 34 项＋新增 7 项）**；既有生产公开键／控件专项 **11 项通过（27.472 秒）**。工程检查还包含保留旧差异和拒绝边界的断言，不是任意契约全部通过。首轮 v7 专项 7 项中 1 项失败（43.116 秒），原生探针整合了最终销毁顺序，已如上保留并拆项披露；该中间运行不累计为最终通过数。

九份最终报告、十一份研究 cjs 和一份 Python 测试，共 **21 payload**，以 SHA256SUMS.json 封存于 [v7 验证目录](verification/2026-11-17_public_instance_proxy_v7/README.md)。每份报告绑定实际脚本、依赖及内存候选的 SHA-256；旧 v1 至 v6 封存与 185 项生产实现基线未变，Notebook 追加而不覆盖旧记录。

## 未完成边界

本补丁不承诺任意循环 key、任意模板／多根范围移动、异步组件、过渡、所有 splice／初始挂载路径。已测的是原生 props 传播；**代理 child props 的动态更新仍未验证**，报告继续 false。不得将循环 key 的研究边界混同为公开 setValue 任意键的缩减协议。

完整私有实例／vnode 图、初始化 hooks、组合式注入、祖先异常、所有调度交错／递归保护及真实 SSM 编译／导出／加载仍未闭合。保持 `arbitrary_public_key_contract_complete=false`、`production_admission_eligible=false` 和生产 `source_dynamic_key_contract_unsupported`。

下一步优先补齐**代理 child props 动态传播**的真实父子反例与同步闭环，然后继续编译接入前的剩余能力验证；不能仅凭这四项夹具或通过修改 Prompt 就放行生产。

无模型、LangSmith、训练、实际数据库／队列写入、commit 或 push；无需重启服务器或付费复跑。本轮不增加论文迁移样本，不是 30 组件回归或完整像素／SSIM 评估。
