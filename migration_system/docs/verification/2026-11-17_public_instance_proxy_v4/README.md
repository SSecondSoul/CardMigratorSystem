# v4 调度研究最终证据

2026-11-17。SHA256SUMS.json 登记 11 个 payload，不含本说明和清单自身。

- before_v3.json／after_v4.json：相同实际浏览器探针，8 项调度场景由 3 项一致变为 8 项一致；旧失败保留。
- controls_browser.json：v4 上的实际控件回归，两页均有 7 条真实 watcher 回调。
- native.json／native_writes.json：94 项有限非 DOM 对照、5 项写入对照及 8 项控制；明确记录渲染屏障是非 DOM 测试替代。
- runtime.cjs、compatibility.cjs、native_writes.cjs、browser_probe.cjs、controls_browser_probe.cjs、test_public_instance_proxy_v4.py：最终源码／测试。

最终合并 22 项 50.132 秒、生产专项 11 项 28.071 秒通过，不是论文新增样本或全系统重跑。旧 v3 runtime 指纹仍绑定其原封存；新包不改写旧证据。

研究部分兼容，生产准入与完整任意公开键契约仍为 false；无模型或实际库写入。详情、测试替代声明及限制见 [v4 记录](../../PUBLIC_INSTANCE_PROXY_V4.md)。
