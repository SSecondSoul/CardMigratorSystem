# v5 root owner 最终证据

2026-11-17。SHA256SUMS.json 登记 16 个 payload，不含本说明和清单自身。

- before_v4.json／after_v5.json：相同 root owner 探针，旧未连接 0/6、新连接 6/6；不是论文组件通过率。
- scheduling_browser.json／controls_browser.json：owner 已连接的实际浏览器调度／控件回归。
- native.json／native_writes.json／owner_controls.json：非 DOM 对照及 owner 边界控制，屏障测试替代有显式声明。
- runtime、owner、compatibility、native_writes、owner_controls、browser_probe、scheduling_browser_probe、controls_browser_probe 八份 cjs 及一份 Python 测试：最终源码副本。

最终合并 28 项 70.162 秒、生产专项 11 项 25.828 秒通过。完整任意公开键、私有实例图和生产准入仍未完成。无模型或实际数据库写入，旧版本与生产基线不改写。

实现范围、真实失败和限制见 [完整记录](../../PUBLIC_INSTANCE_PROXY_V5.md)。
