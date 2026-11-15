# 开题范围对齐后的迁移主线核对 v1

日期：2026-11-14。范围依据：`docs/ir-design/source-migration-scope-20261114.md`。

## 结论

本步完成范围分类、冻结输入核验及离线重评，没有实施新的生产修复。运行时互操作和 provider 不再推进；生成、校验、规则／模型修复仍以源组件的功能和外观保持为目标。

当前选定的六个历史失败组件候选，均在本次通过 San 编译，三个静态通过、三个静态失败。这些候选来自不同日期的累计离线修复链，**不能把 3/6 当作新批次通过率，不能改写原批 24/30**。本步没有新 DOM、像素或人工交互验收。

## 本次实际核对

- 重新核验四套冻结证据包，共 521 个 payload 哈希：原 30 项结果 457、V7 输入 6、V13 33、监听边界 25。另核验父 props 与源模板修复包，引用其历史链路而非冒充本次修复。
- 对六个指定候选重新执行当前 ValidateStage 和 San 编译。TaskManager 采用已人工确认的 v7＋class 候选；其他五个采用边界收紧包中明示的冻结输入，具体路径／SHA-256 见 audit.json。
- 独立重跑队列结构套件 32/32（27.856 秒）和监听范围保护套件 14/14（44.167 秒）。这是两个定向套件，不是全量回归或业务正确性通过证明；测试摘要来自本次终端输出，未声称保存完整 stdout 日志。
- 重跑 TaskManager 源监听分析、只读队列结构检查和伪造通过候选门；三项生产诊断仍在，伪造通过仍拒绝。
- 原 summary、生产实现、Prompt、验收配置和页面均未修改；0 模型调用，未启动浏览器／服务器，无新增人工确认。

## 六个候选的当前静态结果

| 组件 | 编译 | 静态校验 | 本步解释 |
| --- | --- | --- | --- |
| StockReservationBadge | 通过 | 通过 | 已有源模板修复派生候选；不是本次生成或修复成功 |
| HabitWeekTracker | 通过 | 通过 | 已有父 props 修复派生候选 |
| RuleBuilder | 通过 | 通过 | 已有父 props 与源 class 修复派生候选 |
| TripItineraryPlanner | 通过 | 未通过，9 条诊断 | 隐藏渲染依赖、直接状态写入、公开方法及依赖图契约仍需核对 |
| MonitoringDashboard | 通过 | 未通过，1 条诊断 | 保存逻辑存在，异常包装与源行为等价性未证明 |
| TaskManager | 通过 | 未通过，3 条诊断 | 异步监听生产识别、动态键与存储异常契约未闭合 |

上述 9／1／3 是当前检查输出条数，不是 13 个独立根因或新发现生产缺陷。静态通过不表示本次完整浏览器功能已通过。旧自动批次仍为 24/30、6 失败、0 执行错误、1,821,544 tokens。

## 停止互操作后，哪些问题仍要修

### 源码迁移问题

1. TripItineraryPlanner：isConflict 隐藏读取 conflictIds；dayCount 隐藏读取 items；moveItem／updateDraft 存在待核对的状态引用写入；setValue／emitEvent／notify 的公开接口和 dayCount 的源渲染依赖未被当前规则证明落地。下一步应针对源表达式、完整方法上下文和写回顺序修复，不能直接按错误条数删代码。
2. MonitoringDashboard：源 settings watcher 直接写 localStorage，目标增加 try/catch。当前诊断是 source_watch_persistence_unproven，不是“保存调用消失”。需要以正常写入和存储失败对照确定迁移策略，避免重复插入保存调用。
3. TaskManager：源 watch(tasks, settings)、mounted、beforeDestroy、updateSettings(key,value) 和 saveToLocalStorage 均真实存在。settings[key] 的语义、异步监听时机及错误通道不能随着停止外部 Ref 探针一起忽略。

### 评估器与生产接入问题

当前生产 matcher 给 TaskManager 的 v7 候选 source_parent_watch_not_landed，而独立只读检查器能证明受限队列／生命周期结构匹配。前者尚未接受实验实现，后者不证明动态值、异常和整个应用等价；这是需要建立闭环的覆盖缺口，不是现在可以直接豁免的假阳性结论。

沿 validate、source_parent_watch_semantics、repair、scheduler 与候选门的执行链核对，未发现直接要求 Ref provider 的条件。动态键诊断由源赋值形状触发，异常诊断由源 watcher 调用链访问 localStorage 触发；它们并不只针对外部 Ref。普通 provider 字段还用于 LLM 供应商账目，不能因名称相同误判为运行时互操作依赖。

### 已停止的额外互操作探针

选定 TaskManager 源码未见 ref／shallowRef 构造文本；V12 测试设备显式在两侧构造 Vue 原生 Ref，V13 延续该设备测试内部属性通知。原 Ref 的 4 个差异和新结构的 2 个差异属于这条额外输入互操作探索。保留原始失败，不再实现 provider，也不把这些点算作六个新的正式失败组件。

不能把所有边界一概移出范围：旧扩展矩阵 cyclic_plain_value 的销毁错误通道差异不依赖原生 Ref，仍作为未解决能力边界保留。也不因一条边界无限扩展成通用 JavaScript 运行时复刻；先验证实际源业务和预先固定的迁移场景，未知输入如实披露，不追溯修改旧评分。

## 接下来实际修复什么

第一项处理 TripItineraryPlanner：对照冻结源码，区分真实缺失与分析器未证明；将可确定的渲染依赖、状态提交及方法接口问题补成通用规则、检测与正负回归用例。先离线证明，再决定是否修改 Prompt。第二项核对 MonitoringDashboard 的保存异常行为，第三项推进 TaskManager 有界源契约与生产识别；不再被原生 Ref 互操作方案占用。

每项修复保持“冻结失败 → 源语义 → 检测／修复 → 防回归 → 新版本复跑”的顺序。已修复和未修复部分分别报告，禁止通过删诊断、减少原统计分母或放宽阈值制造提升。需要付费批处理或人工检查时再由用户执行或确认。

本报告及 Notebook 追加由验证问题报告技能组织；只确认文档 JSON、只读代码和上述离线执行结果，未打开 Notebook UI。

