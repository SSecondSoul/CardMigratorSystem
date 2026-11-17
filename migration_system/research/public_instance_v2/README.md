# 公开实例代理 v2 研究修复

本原型修复对象／ref 身份、computed、实际 watcher 及 San 读取依赖／DOM 刷新，**未接入生产，完整契约仍未完成**。

v2 新增依赖当前已安装的独立 `@vue/reactivity` 3.5.45 内核；不是 Vue 组件或渲染器。不得把“目标页没有 Vue 组件运行时”描述成“没有 Vue 依赖”。内核构建／指纹需固定，缺少触发钩子会拒绝。

94 个有限原生场景、四页实际浏览器、8 项边界控制和剩余限制见 [完整记录](../../docs/PUBLIC_INSTANCE_PROXY_V2.md)。v1 与生产阻断不变；不修改生成 SFC 或调用模型。数据、源码和依赖均在 migration_system 内，使用本目录的 frontend／engine／browser Node 安装。
