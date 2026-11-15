## 2026-11-14：源原生属性赋值 v8 实验修复（未生产放行）

在已冻结 V7 反例之后，新增通用、显式 opt-in 的源码匹配修复；仅接受完整匹配的 V7 composition，不按组件名硬编码，不修改生产 emitter／Prompt／验证器。

- 从 Vue 源码提取整个赋值表达式，将 `this.settings[key]` 接收对象映射为 `this.data.get("settings")[key]`，保留键转换、RHS顺序和通知尾部；显式保留ES module严格模式。不是简单删除诊断或缩小key接口。
- TaskManager 和重命名通用 fixture 共 116 个比较点：不一致从 39 降到 18；已一致控制点回退 0。
- 剩余场景：date_value, delete_then_mutate_detached_alias, frozen_value, nonenumerable_then_mutate_alias, redefine_then_mutate_detached_alias, sparse_array_value。这是部分通用修复，**动态键／属性形状闭环仍未完成**，不宣称任意输入或反射等价。
- 75 项定向测试，包含新修复、冻结V7反例及V7结构匹配；反例测试通过仅表示稳定重现，不表示所有缺口已修复。
- 受限值观察器和flush后旧订阅仍需修改；当前生产三项阻断、独立候选门保留。0模型请求，原始24/30、6失败及token统计不变。
- 未改旧V7观察器、冻结候选、验收配置、组件或原有批次结果。新产物仅供离线实验，不切换人工页，不要求用户复跑。
- 首次75项测试中1条顺序断言失败：测试错误假定键转换先于RHS转换。已保留原代码／日志，修正为执行原生源赋值作对照；双方都得到 rhs→key，适配器实现未因此修改。没有削弱严格模式、源表达式匹配或未关闭阻断。

证据：`data/experiments/analysis/formal_30_v4_source_property_assignment_v8_retry_20261114`；原反例：`data/experiments/analysis/formal_30_v4_v7_dynamic_shape_audit_20261114`。
下一步针对已冻结的值接受与订阅时机反例改进观察器，再做受限错误桥和生产集成。
