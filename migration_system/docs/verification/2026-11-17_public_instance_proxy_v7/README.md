# v7 keyed 候选修复证据

2026-11-17。SHA256SUMS.json 登记 **21 个 payload**，不含本说明及清单自身。

- `before_v6.json`／`after_v7.json`：相同有限 owner 树场景，3/4 → 4/4；前者与旧封存 v6 失败报告逐字节一致。目标及无代理原生最小对照都切换到所记录版本，未替换源结果。
- `keyed_browser.json`：Vue／上游 San／内存候选三页；13 次原生更新、普通元素路径和 9 项拒绝控制。最终 raw San 整树销毁顺序仍不一致，单列 `native_disposal_order.equal=false`，没有归成通过。
- `root_browser.json`／`scheduling_browser.json`／`controls_browser.json`：相同候选下既有真实浏览器回归。
- `native.json`／`native_writes.json`／`owner_controls.json`：非 DOM 对照与边界，使用原 San，渲染屏障替代明确披露。
- 十一份 cjs、一份 Python：最终研究源码／测试。上游 San 未复制或改写到生产；san_candidate.cjs 校验其版本／SHA-256 后生成内存文本，报告记录上游及候选 digest。

合并工程检查 **41 项通过，110.122 秒**，生产专项 **11 项通过，27.472 秒**。旧差异／拒绝边界断言也是工程通过的一部分，不代表完整契约放行。旧证据与 185 项生产实现保持；无模型调用或论文新增迁移样本。

原生 probes 没有 Proxy／VueReactivity／owner；代理 probes 使用独立 VueReactivity，但无 Vue 组件运行时。动态代理子 props 尚未验证，完整契约和生产准入仍为 false。范围及实际中间失败见 [完整记录](../../PUBLIC_INSTANCE_PROXY_V7.md)。
