# v3 嵌套原生控件桥接最终证据

2026-11-17。SHA256SUMS.json 登记 8 个 payload（不包括本说明和清单自身）：

- native.json：v3 上的原有 94 项有限对照及保留的 vnode 图差异。
- native_writes.json：5 项新增写入对照、8 项边界控制。
- browser.json：两张隔离实际 Edge 页，原生控件及 7 条真实 watcher 回调逐条比较。
- runtime.cjs、compatibility.cjs、native_writes.cjs、browser_probe.cjs、test_public_instance_proxy_v3.py：最终源码及测试副本。

回归：v1/v2/v3 合并 17 项，21.334 秒；既有公开键／控件 11 项，24.760 秒。二者不是论文样本数，也不是全部系统／真实模型重跑。

结果仍为研究部分兼容，不是生产准入；无云调用、实际库写入、真实生成组件改写。新依赖、通知策略差异、真实失败及未完成边界见 [完整记录](../../PUBLIC_INSTANCE_PROXY_V3.md)。
