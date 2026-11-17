# 公开实例代理原型 v6：有限 owner family

基于 v5，连接真实 San 父子 owner、独立 scope 和 family nextTick。**四个树场景仅三个一致，原生 keyed 重排仍有实例重建／状态丢失，未放行生产。**

- runtime.cjs／owner.cjs：私有逻辑 parent/root、实际挂载／清理及 family 调度。
- browser_probe.cjs：Vue／San 树对照及不含代理的原生 keyed 对照。
- root_browser_probe.cjs／scheduling_browser_probe.cjs／controls_browser_probe.cjs：既有实际浏览器回归。
- compatibility.cjs／native_writes.cjs／owner_controls.cjs：非 DOM 对照，屏障测试替代有明确声明。

在 migration_system 内运行：

```powershell
& .venv/Scripts/python.exe -m unittest discover -s tests -p 'test_public_instance_proxy*.py' -v
```

工程检查包括识别已知差异的反例，检查全绿不等于 keyed 行为已一致。需要本目录依赖与本机浏览器，不需要模型／服务。详见 [v6 记录](../../docs/PUBLIC_INSTANCE_PROXY_V6.md)。
