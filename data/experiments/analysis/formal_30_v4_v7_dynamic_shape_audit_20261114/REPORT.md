## 2026-11-14：V7 动态键／属性形状的原生反例审计

本步先验证观察器是否真的等价，未改生产规则、Prompt、组件或验收配置，也未放行。

- 两个开发对象：冻结 TaskManager（24场景）和通用 assign fixture（23场景；没有 TaskManager 特有的 syncInterval 分支），合计 116 个同步／tick 比较点。不是新增独立样本或人工验收。
- 当前 V7 实验适配器出现 39 个不一致比较点，涉及 12 种场景：coerced_existing_key, coerced_new_key, date_value, delete_then_mutate_detached_alias, frozen_value, new_symbol_value, nonenumerable_then_mutate_alias, numeric_key, redefine_then_mutate_detached_alias, sparse_array_value, symbol_key, throwing_key_coercion。
- 比较键转换／赋值结果、可枚举属性形状、原型、旧对象别名、watcher 及业务副作用、异常类别和下一 tick；保留双方原始消息。框架内部元数据及所有反射等价不在通过声明内。
- Vue 使用冻结 2.7.16 原生观察器；San 使用 3.15.6 和冻结 V7。限于有限 DOM、最小根渲染、桩存储／定时器，不是完整浏览器视觉复核。源码 ES module 以严格模式执行，San CommonJS 保持产物原模式。
- Vue 完整构建启动时有两个换行属性序列化探测，测试 DOM 仅支持这两个确切字符串；不模拟通用HTML解析。初次启动失败代码和日志保留。首次编码器把Vue增强数组原型与标准数组原型算作业务状态差异，导致普通控制场景误报；原观察值保留，当前显式排除数组原型／内部元数据的反射等价声明，双方原始own names与数组反射事实另存，根对象原型仍比较。
- 三条待修复义务在 `repair_obligations.json`：属性键转换、赋值输入类型、flush后过期订阅。删除／描述符变化场景的首次tick双方一致，而下一次旧别名变化在San产生多余副作用；不能简单在遍历时丢弃旧子对象，否则会丢失首次合法通知。
- 本轮 89 项定向测试用于验证控制场景和反例可复现；“测试通过”不代表这39个不一致点被修复。
- 通过的普通场景不能外推为任意 key／value 的公开 API 等价。不能通过限制成 UI 已知键、删除属性、强制所有新键响应式或捕获后忽略错误来“修复”。
- 三项生产阻断保留，伪造通过仍拒绝；0 模型调用，原批24/30、6失败、1,821,544 tokens 不变。

反例及双方逐阶段数据：`data/experiments/analysis/formal_30_v4_v7_dynamic_shape_audit_20261114/observations.json`。
输入／运行时／旧观察器：`data/experiments/analysis/formal_30_v4_v7_dynamic_shape_input_20261114`。
测试与代码副本：同证据目录的 `tests` 日志、`audit.json`、`code/`。

后续修复应由反例驱动：先处理公开方法原生属性键转换与赋值语义，再处理删除／描述符变化后的订阅更新；未知或不支持行为继续阻断，不能宣称动态键闭环已经完成。
