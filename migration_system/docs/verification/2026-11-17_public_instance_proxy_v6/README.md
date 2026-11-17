# v6 部分闭合及原生 keyed 失败证据

2026-11-17。SHA256SUMS.json 登记 18 个 payload，不含本说明及清单自身。

- before_v5.json／after_v6.json：新增树场景旧 0/4、新 3/4；keyed 项仍 equal=false。包含无代理的原生 San 对照。
- root_browser.json／scheduling_browser.json／controls_browser.json：既有实际浏览器回归。
- native.json／native_writes.json／owner_controls.json：非 DOM 对照及防护，屏障替代显式标注。
- 九份 cjs 与一份 Python 测试：最终源码副本。

合并 34 项 93.577 秒、生产专项 11 项 30.039 秒通过；其中包含保留失败的反例，不是树场景 4/4 或论文新增样本。源 key 行为仍未闭合，完整契约及生产准入为 false。

失败、分层定位及下一步见 [完整记录](../../PUBLIC_INSTANCE_PROXY_V6.md)。
