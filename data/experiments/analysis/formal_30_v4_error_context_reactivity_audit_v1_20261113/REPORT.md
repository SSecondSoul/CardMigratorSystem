# 应用映射与响应式错误钩子审计 v1（2026-11-13）

这是验证边界的审计，不是新生产规则或已部署修复。v6 helper/adapter及原生装置原封不动，上一轮110阶段证据完整重放。0模型调用，无人工确认，无页面改动；原批24/30、6失败、0执行异常、1,821,544 tokens不变。

## 真实应用核对的证据等级

只读取本地可执行脚本AST，不据旧注释推断当前组件。当前两页实际加载RuleBuilder，不是TaskManager；Vue root没有本地errorCaptured/mixins/extends，页面无全局errorHandler赋值；San wrapper没有v6配置调用。冻结TaskManager源没有errorCaptured/mixins/extends声明。验收驱动的window监听不是桥接配置。CDN/loader/运行中插件或全局配置未访问，不能用“本地未声明”证明真实浏览器没有祖先钩子。页面版本与固定Vue2.7.16/San3.15.6也不等同。因此**应用映射仍未部署/认证**，不能把v6 fixture应用绑定当成真实应用结果。

## 原生依赖与重入审计

保留固定miniDOM和原TaskManager业务/生命周期体；仅注入auditSentinel、一项computed及最小渲染以观察依赖。9场景×2变体×12阶段=18运行、216快照、108比较。含正常、两次同步设置、显式依赖阳性对照，以及6个捕获/全局钩子读状态、写无关状态、重入settings/tasks场景。钩子通过实际v6异步dispatch到达，没有手工调用helper.handle或私有框架错误函数。

**不是108项完整状态全通过**。108比较的完整事件、raw console、拒绝相等；所有原始状态差异保留在audit.json。无关sentinel后续变更未使computed新增求值（8场景×2变体），显式依赖阳性对照则两框架均增加1次，证明装置可以观测依赖。这只支持当前异步队列中的有限观察，不证明活跃render/computed上下文中的暂停/恢复，也不改变v6原profile。6种响应式hook刻意越出“不读写响应式状态”的声明；匹配不等于合法扩展。

## 保留并解释的差异

San computed较早求值，Vue computed较晚/合并求值，故同步帧有计数差异；settings hook将30改15时，目标多算一次。**无异常的两次同步设置控制也出现同样计数差异**，因此不能归为v6新回归或错误依赖。后续无关数据变更不增加两者计数。Vue销毁保留节点/San dispose移除节点也在正常控制中复现；所有destroy帧DOM差异保留，不过滤成成功。原业务状态没有观察到差异，渲染稳定时内容一致，但不能据此承诺computed副作用可等价迁移。

## 结果与下一步

定向测试：{"passed": 56, "failed": 0, "skipped": 0, "suites": [{"suite": "test_error_context_reactivity_audit_v1.py", "passed": 18, "elapsed_seconds": 11.975}, {"suite": "test_source_error_context_v6.py", "passed": 24, "elapsed_seconds": 14.134}, {"suite": "test_parent_watch_scope_guard.py", "passed": 14, "elapsed_seconds": 30.99}], "elapsed_seconds": 57.099, "not_a_full_suite": true}；不声称完整703项重跑。旧421文件清单（含387生产/既有运行文件）、来源/页面/原v6证据未改；新增3审计/测试文件后424项，7个payload封存。旧Notebook68单元及元数据保留，追加审计节。

结论是缩小了未知范围，并非宣布完整闭环：应用映射仍需明确实际部署入口；当前async通道未观察到额外依赖，但通用依赖暂停、活跃收集器中的钩子、异步/无限重入、SSR与任意祖先映射仍未证明。下一步应先确定是否把生产方案限定为已证明的异步watcher通道，并设计可拒绝越界上下文的能力契约；不直接接入生产、不放宽诊断、不付费模型复跑。
