# 公开实例代理 v3 研究代码

本版本基于已封存 v2，补充原生双向控件向源响应式状态的嵌套写入。不由生产系统导入，不解除任意公开键契约阻断。

- `runtime.cjs`：源状态写入、原生镜像、合并通知；保留 v2 代理及 watcher。
- `compatibility.cjs`：原有 94 项有限原生对照在 v3 上重放。
- `native_writes.cjs`：5 项新增对照及 8 项桥接控制。
- `browser_probe.cjs`：隔离 Vue／San 页面实际输入、勾选、下拉选择和清理。

在 migration_system 目录执行：

```powershell
node research/public_instance_v3/compatibility.cjs
node research/public_instance_v3/native_writes.cjs
& .venv/Scripts/python.exe -m unittest discover -s tests -p 'test_public_instance_proxy*.py' -v
```

浏览器需已安装本机 Edge 与本目录 Node 依赖；不需要模型密钥或服务重启。内核仍为显式独立 VueReactivity development 构建，目标不加载 Vue 组件运行时。完整限制与失败记录见 [v3 说明](../../docs/PUBLIC_INSTANCE_PROXY_V3.md)。
