# 公开实例代理 v7：keyed 单元素根组件移动研究

保留 v6 已实现的 owner family，单独验证 San 3.15.6 原生 keyed 组件重排修复。**不由生产主链加载，也不解除任意公开键契约阻断。**

- `san_candidate.cjs`：校验上游版本及 SHA-256，确定性生成内存候选；不写入 engine/node_modules，不允许未知版本静默套补丁。
- `browser_probe.cjs`：相同四个 Vue／San owner 树场景，目标及无代理原生对照均加载候选。
- `keyed_browser_probe.cjs`：原 Vue、未修改 San、候选 San 三页对照；13 次连续更新、普通元素回归及真实拒绝边界。此探针目标页没有 Proxy、VueReactivity 或 owner 桥。
- `root_browser_probe.cjs`、`scheduling_browser_probe.cjs`、`controls_browser_probe.cjs`：既有实际浏览器回归，也加载同一候选。
- `runtime.cjs`、`owner.cjs` 等：保留 v6 研究实现；非 DOM 屏障仍显式为测试替代，不证明浏览器时序。

本轮仅验证同步、已挂载、单元素根组件与有限唯一字符串 key。多根、条件根、组件根、过渡、重复／保留名／数字／Symbol key 明确拒绝。**这是尚未完成研究的防护边界，不是将用户的任意公开键契约缩小后宣告成功。** 初挂载、splice 等其他循环路径不在本补丁全面保护承诺内。

运行（仓库根目录）：

```powershell
& migration_system/.venv/Scripts/python.exe -m unittest discover -s migration_system/tests -p test_public_instance_proxy_v7.py -v
```

需要本机浏览器及目录内已安装的固定依赖，不需要服务器、API key 或真实数据库。详见 [v7 记录](../../docs/PUBLIC_INSTANCE_PROXY_V7.md)。旧版本及其失败证据不修改。
