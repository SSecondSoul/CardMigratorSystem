# 公开实例代理兼容性原型

已获用户授权先验证、后接入；当前是**未完成契约、不能生产放行**的研究模块。

- `runtime.cjs`：独立业务公开 receiver，闭包隔离 San 原生 receiver，无 Vue 依赖。
- `compatibility.cjs`：当前 Vue／San 的 73 个一致性场景及 4 个已观察到的差异。
- `browser_probe.cjs`：两张隔离页面的实际按钮／状态更新实验，San 页不加载 Vue。

它不被默认系统加载；没有修改生成产物、Prompt、SSM 或旧阻断。详细结果、限制与复现见 [验证记录](../../docs/PUBLIC_INSTANCE_PROXY_V1.md)。没有从旧实验根目录加载代码或数据。
