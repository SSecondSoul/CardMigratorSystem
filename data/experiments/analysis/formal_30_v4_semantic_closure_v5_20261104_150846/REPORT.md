# MonitoringDashboard：semantic closure v5 原始结果复核

日期：2026-11-04（Asia/Shanghai）。这是 formal v4 内部第五轮语义闭环的单样本开发回归，不是独立测试或完整 30 样本复跑。

## 结论

原始自动评估通过，保留原分数；但只读源码审查发现设置 watcher 丢失持久化写入，现有规则未报告。
因此人工状态仍为 `not_started_watch_persistence_review_required`，不能宣布业务等价、全部闭环完成或完整 30 项通过。

## 冻结与运行数据

- 原始快照：`data/experiments/snapshots/formal_30_v4_semantic_closure_v5_results_20261104_150846`，364 文件 SHA-256 校验通过。
- 协议：`formal_30_v4_semantic_closure_v5_frozen_20261104`，352 项 frozen/live 校验仍通过。没有改运行期规则、Prompt、canonical San 或原始 summary。
- 运行：14:58:19—15:08:24，605.000 秒。
- 1 个配置、1 个完成、1 个自动通过、0 个执行异常。
- 初始：16 条静态错误，DOM 0、San 渲染失败。
- 最终：0 条静态错误，保留 1 条 `migration_hints_not_landed` 警告；DOM 结构相似度 0.9912，tag/text 相似度均 1.0。
- 生成 107,336 tokens，模型修复 134,895 tokens，总计 242,231 tokens。
- 最终文件：`MonitoringDashboard_repaired_normalized_2.san`。
- 精确 SHA-256：`c449590f735d97cab2dc91ea24f8353fd1bba1be3464b1b814af24eefd3be168`。
- summary、repair history、全部候选进度签名、最终文件和 token 账目已交叉核对；自动交互评估为 null。

## 候选链不能只写“1 轮修复成功”

1. 初始生成后第 1 次确定性候选尝试注册标识符恢复、prop schema 恢复、指令解包、methods 展开。候选门拒绝，记录 4 条新近可见的 `hidden_template_reactive_dependency`。该候选保留，未作为模型输入继承。
2. 实际模型修复 1 次，候选门接受，但仍有 `missing_self_click_guard`，不算当时已经通过。模型返回后处理包括只读图表 helper 显式依赖、模板／class／methods、布尔事件和 prop schema 处理。
3. 第 2 次确定性候选恢复 self-click/native-drag 语义，被接受，最终通过；记录 `before_llm_call=2` 仅是第二次模型调用前的处理位置，实际没有发生第二次模型请求。

所以是 **1 次 LLM repair、2 次确定性候选处理（1 拒绝、1 接受）**，不是 2 次确定性成功，也不是 2 次模型调用。
第 1 次拒绝不能擅自宣称“误拒”；现有覆盖证明没有将这 4 条诊断解释为可豁免的旧缺陷。原始拒绝理由不改写，后续可另行审查边界。

## 前轮问题与本轮证据

### 初始化时机与次数

源 mounted 调用 `initData()`，其 7 条无参调用在本轮 San 的 attached 首部按顺序各出现一次：
`updateDateTime → initChartData → initRequestStats → initAlerts → initLogs → initServices → loadSettings`。
inited 只注册 watcher，没有这些初始化调用。没有前轮的 inited/attached 重复初始化形态。

这是直接展开形态，不是 `initDataImpl()` 包装器形态；通用 AST 的 `startup_contracts=[]`，不能拿旧工具固定统计的“initDataImpl 调用为 0”误报缺少初始化，也不能宣称新包装器修复规则在本轮触发。独立审计核对了展开前缀、顺序和直接次数；不是任意间接调用图等价证明。

### 通知权限方法

`requestNotificationPermission` 保留为导出父组件可调用方法；原能力检测和 `settings.desktopNotifications` 条件保留。源／目标识别出的父脚本、模板内部引用均为 0，无未决引用站点。
没有新增保存、挂载、勾选时的申请权限调用。本轮 postprocessing 没记录“补回该接口”的规则，不能把保留事实改写成自动恢复触发。
没有实际执行权限申请或浏览器通知。

### 新发现的持久化遗漏

源 Vue 第 608 行：

```js
localStorage.setItem('dashboard_settings', JSON.stringify(newVal));
```

San 第 638 行的 watcher 是 `(newValue, oldValue) => { ... }`，保留自动刷新开关处理，但缺少上述写入；导出父组件也没有其他直接 `localStorage.setItem` 写入补偿，`loadSettings` 只有读取。代码证据见 `summary.json → independent_ast_review.watcher`。

现有 `source_phase_semantics.cjs → repairWatchPersistence` 的检测和修复共用严格匹配：源单参数，目标只有同名单参数或特定无参局部取值形式，且原有语句 AST 相同。遇到改名加第二参数时直接 continue，因而不只是不自动修复，连持久化诊断也没有输出。最终 `source_semantics.findings=[]` 和旧自动零错误均如实保留，另列独立缺陷。

这不是原始结果被覆盖，也不是这次检查修改了产物；是既有规则覆盖范围不足。刷新后设置能否保存仍需真实浏览器测试，不能将尚未执行的具体症状写成已观察结果。

## 本次操作与下一步

- 分析工具：`migration_pipeline/analyze_formal_30_v4_semantic_closure_v5.py`。
- 新增只读审计 6/6 测试通过，2.502 秒，覆盖真实快照、参数改名与额外参数、保留写入、子组件隔离、初始化直接次数、导出父组件歧义。没有重新跑完整 380 项；运行前完整 374 项结果仍是独立旧记录。
- 首次测试中“歧义父组件”夹具拼接了两个 SFC，实际只检查了第一个 script，不构成同一脚本的导出歧义；改为同一 script 两个导出后重新 6 项通过，未改审计器或生产规则来放宽结论。
- 未调用模型、未打开浏览器、未更换人工页、未改 canonical 产物、未 commit/push。

建议先基于本冻结产物补齐 **watcher 参数作用域内的 alpha-mapping、无用旧值参数边界、持久化缺失诊断、候选门和有界恢复测试**。
必须证明新旧参数用途、原条件／副作用顺序和目标其余语句一致；保留目标参数及无关代码。遮蔽、额外效果、动态访问或实际依赖旧值时不猜修。
检测范围与自动修复范围应分开：能识别缺失但不能安全修时报告，而不是静默视为通过。
离线验证后再决定是否需要新模型协议；当前不再盲目复跑，也不直接跳到下一批独立测试。
