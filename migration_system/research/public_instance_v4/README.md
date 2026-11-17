# 公开实例代理 v4：渲染感知的调度研究

以 v3 为基线，修复 nextTick 早于原生 DOM、post 回调侧写的顺序及 Promise 身份。未接入生产，不解除完整契约阻断，旧研究版本保持不变。

- runtime.cjs：渲染完成标记、完成 Promise、post 分批处理。
- compatibility.cjs／native_writes.cjs：非 DOM 对照；明确注入微任务屏障测试替代，不能作为 DOM 调度证据。
- browser_probe.cjs：同一探针对 v3／v4 做实际 Vue／San 调度前后对照。
- controls_browser_probe.cjs：v3 控件探针在 v4 实现上重放。

在 migration_system 目录运行：

```powershell
node research/public_instance_v4/compatibility.cjs
node research/public_instance_v4/native_writes.cjs
& .venv/Scripts/python.exe -m unittest discover -s tests -p 'test_public_instance_proxy*.py' -v
```

需要本目录已有依赖及本机浏览器，不需要服务或模型密钥。详见 [v4 实验记录](../../docs/PUBLIC_INSTANCE_PROXY_V4.md)。
