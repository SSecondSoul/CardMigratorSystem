# 私有异步 watcher 入口范围：隔离候选 v7（2026-11-13）

**新增可执行的入口范围保护，不是任意回调副作用检测，也不是生产放行。** 不改v6及旧证据、生产Prompt/repair.py、canonical San或页面。原批24/30、6失败、0执行异常、1,821,544 tokens不变；0模型调用、无新增人工验收。

## 范围与实际修改

v5基础上内联冻结v6源错误路由工厂及新增scope工厂。scope只存在于inited闭包，不挂在组件上；组件仅有配置委托，不暴露v7 route/run/handle。scope自身安排Promise进入，dispatch catch只在该入口有效期内调用route；watcher归属由冻结fields+合法索引生成，不接受任意info或subject。首次schedule即锁配置，早于实际tick；重复/重入schedule、跨scope/队列外route、非法索引、销毁后使用和不支持的声明profile均拒绝。能力函数引用和fields复制，避免调用者替换配置槽位；已排队后销毁仍走原队列取消/reset逻辑，异常finally撤销active状态。

AST反向还原只涉及2个factory、1个catch分支、1个schedule入口、4条私有配置/销毁语句，其余v5脚本及完整业务/生命周期方法体相同。未配置新context时仍走原v5显式报告器或抛错路径；兼容行为刻意保留，不是缺少映射也安全放行。

## 验证

11场景×3变体×10阶段=33运行、330快照、220源/目标比较；v7合法显式映射110/110阶段的状态、完整事件、raw console、拒绝匹配。原source/v5全量22运行和110比较完整保留，九组负向仍在。11个v7实例均只暴露配置入口；首次tick后重新配置为CONFIGURATION_LOCKED，销毁后为DISPOSED。原生San最近error控制语义不变。

helper guard单测另存：它证明实际Promise进入后才可route，以及异常恢复、pending取消、原错误身份和索引边界；不是TaskManager UI或真实浏览器证据。未配置v7时旧浏览器、旧headless报告器和native子组件装置观察原样保留。候选San本轮编译通过，生产验证仍失败；独立动态键/异常策略诊断和伪造通过保护保留。

## 不能夸大的边界

入口保护**不检测任意函数的响应式读写或Promise副作用**。parentOf/hooksOf/globalHandler/logError仍是受信任应用能力，profile检查只拒绝不支持的声明；调用者谎报纯度时不提供沙箱安全保证。一般依赖暂停、活跃收集器上下文、SSR、异步/无限重入、任意源祖先映射和通用diagnostic renderer都未证明。当前两页仍为RuleBuilder，未配置v7。故不接入生产、不放宽诊断或启动模型复跑。

## 中间失败与证据

首次适配器预检查在生成候选前失败：AST比较器收到Array，旧版本与日志已独立封存（2payload）；修正为仅比较CallExpression，新增AST范围回归覆盖。它不是canonical组件新缺陷，不能从论文过程记录中删除。

定向测试：{"passed": 79, "failed": 0, "skipped": 0, "suites": [{"suite": "test_async_watcher_scope_v7.py", "passed": 23, "elapsed_seconds": 14.574}, {"suite": "test_source_error_context_v6.py", "passed": 24, "elapsed_seconds": 13.589}, {"suite": "test_error_context_reactivity_audit_v1.py", "passed": 18, "elapsed_seconds": 10.649}, {"suite": "test_parent_watch_scope_guard.py", "passed": 14, "elapsed_seconds": 30.591}], "elapsed_seconds": 69.403, "not_a_full_suite": true}。未重跑完整703项。旧424项清单（含387生产/既有运行文件）、30保留输入/Vue、应用文件及Notebook旧70单元/元数据保留；新增5文件后429项，10个payload封存（另有失败2payload）。验证报告技能用于区分入口保证与纯度/应用集成的remaining_risk。

下一步应做固定版本真实浏览器中的隔离应用接入验证，并明确应用能力的信任边界；在此之前不把scope保护当作完整异常闭环或正式30样本新成绩。
