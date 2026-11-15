# TripItineraryPlanner 公开事件包装接口通用修复 v1

日期：2026-11-14。按开题报告推进 Vue → San 源码迁移，不新增 Vue/San 原生 Ref 互操作能力。本次是**部分修复**，不是组件已通过。

## 修复了什么

源 Vue 保留公开 emitEvent(name,payload) 和 notify(items) 方法。目标把其内部调用内联成 this.fire 后，遗漏了两个方法本身，违反公开接口保留要求。

修改共享 AST 规则 `migration_pipeline/utils/method_interface_semantics.cjs`：识别封闭的同步事件转发链，恢复缺失包装方法，将叶子 this.$emit(name,payload) 映射为 this.fire(name,payload)。函数名来自源代码，没有 TripItineraryPlanner 或具体方法名特判。

只接受单条、无 return 的调用语句；参数为已声明参数或字面量；叶子恰好两个参数；依赖方法必须同样可证明。递归链、额外副作用、未知依赖、默认／解构参数、可选／展开调用、目标已有不同实现、框架方法覆盖和目标动态调用均不自动修复。已有方法、调用时机、事件绑定、生命周期不改。

## 修改处于哪个阶段

这是**repair 阶段的通用确定性规则**，通过既有 bounded source semantics 接入修复前处理和模型返回后处理。两条路径均有测试。本轮没有修改生成 Prompt、repair Prompt、服务器路由或校验阈值，也没有直接手改标准 San 产物。

原校验器仍报告缺失接口，直到修复后的代码实际出现对应方法。候选保护允许本次有证据的恢复，回退删除接口则拒绝。这里没有把“未证明”等价为“通过”。

## 冻结候选离线结果

- 实际 RepairStage 前处理只产生一步 restored_source_event_forwarding_interfaces；重复处理达到不动点。
- 完整静态诊断从 **9 条降到 7 条**：消除 emitEvent 和 notify 的两条接口缺失；这两个表象属于同一类公开包装接口丢失，不能据此计算泛化正确率。
- San 编译通过。修复前后均重新执行轻量初始 DOM 对比，结构／标签／文本相似度均为 1.0，树编辑距离为 0；不等于真实浏览器像素或交互通过。
- 独立候选门接受该增量；整个组件仍 validation_passed=false、production_eligible=false。
- AST 反向比较确认只新增 emitEvent、notify；移除这两个新定义后，原脚本 AST 完全一致。模板和样式原字节不变，原始冻结候选和 canonical San 不覆盖。

自动派生候选：`TripItineraryPlanner_event_interfaces_offline.san`。完整前后诊断见 audit.json。

## 验证与反例

17 项新增测试、16 项既有方法接口测试、12 项既有源阶段语义测试，三套定向测试共 **45/45** 通过，不是一次全量测试运行。新增测试包括源码改名、依赖顺序、不动点、只读检查、闭包／副作用拒绝、框架覆盖拒绝、候选门、真实前处理和模拟模型返回后处理。

测试使用固定的原生 Vue 2.7.16 / San 3.15.6，分别验证合成对象和冻结 TripItineraryPlanner 的公开事件辅助方法：事件内容一致，payload 引用身份保留，返回值维持 undefined。不挂载完整 UI，不创建跨框架 Ref，不调用外部模型。

另对 30 个累计冻结候选进行源方法／阶段 AST 扫描，仅 TripItineraryPlanner 会被此规则改写，原先通过的 24 项无改写。这不是重新跑完 30 项完整校验、视觉或迁移批处理。

开发中保留一次失败：扩展后处理测试的首次 17 项运行有 1 条失败（29.663 秒），原因是保存阶段补末尾换行，测试把文件结果与无换行 AST 文本按字节比较。原测试源码 base64、SHA-256 和失败摘要保存于单独失败包；改为明确断言“精确转换结果＋一个换行”，没有使用 strip 掩盖其他差异，也没有调整生产规则。初始 15 项通过只是较早测试版本，不与最终 17 项重复计数。测试摘要来自终端输出，不声称保存完整原始 stdout。

## 仍未修复的七条诊断

- isConflict 的 class／s-if 以及 dayCount 的文本绑定仍有三条隐藏响应式依赖诊断。
- moveItem、updateDraft 仍有两条状态引用写入诊断，需分别核对实际语义与分析器覆盖，不能一律删除。
- 动态公开 setValue(key,value) 尚未恢复；Vue this[key] 是实例属性赋值，不能直接假定等价于 San 路径 setter。
- dayCount 的源渲染依赖图仍有一条未落地诊断。

特别注意：源 moveItem 本身对浅拷贝数组中的共享记录改 start，再构造提交结果。擅自改为全深拷贝、提前提交或完全禁止原地修改，都可能改变其业务可观察行为。后续需源对照证明，而不是为了清空 nested_state_mutation 猜修。

## 记录与下一步

输入冻结包：`data/experiments/analysis/formal_30_v4_trip_event_interface_v1_input_20261114`。本包 implementation.json 保存修复后代码／测试的精确 base64 与指纹，输入包保存修复前规则，用于追溯。

原批次仍为 24/30、6 失败、0 执行错误、1,821,544 tokens；没有新模型调用、服务器／浏览器启动或人工确认。人工验收配置和页面不改，Notebook 只追加且保留旧103单元。

下一步先对 updateDraft 的克隆／提交链建立源匹配证明，区分真实缺陷与别名误报，再处理渲染依赖和动态 setter。所有修复继续走通用规则、校验与回归闭环；不需要现在付费复跑或人工验收。

