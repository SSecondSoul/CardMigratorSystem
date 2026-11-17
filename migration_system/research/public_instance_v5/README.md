# 公开实例代理 v5：root owner 研究

基于封存 v4，增加每实例 root owner 的生命周期连接及原生销毁清理。不是生产加载器，不修改默认迁移链或放行完整任意公开键。

- runtime.cjs：代理、状态、调度及私有 owner capability。
- owner.cjs：root attach／update／dispose 接入；不实现完整 Vue 组件树。
- compatibility.cjs／native_writes.cjs：既有非 DOM 对照，渲染屏障为明确测试替代。
- owner_controls.cjs：10 项边界控制。
- browser_probe.cjs：旧 v4／新 v5 生命周期前后对照。
- scheduling_browser_probe.cjs／controls_browser_probe.cjs：owner 已连接的实际调度／控件回归。

在 migration_system 目录运行：

```powershell
node research/public_instance_v5/owner_controls.cjs
& .venv/Scripts/python.exe -m unittest discover -s tests -p 'test_public_instance_proxy*.py' -v
```

使用本目录已有依赖与本机浏览器，不需要模型密钥或服务重启。依赖、实际失败及未闭合范围见 [v5 记录](../../docs/PUBLIC_INSTANCE_PROXY_V5.md)。
