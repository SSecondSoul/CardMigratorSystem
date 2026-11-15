# watcher 持久化：通用有界闭环补齐

日期：2026-11-04。用户确认后实施；承接本目录 REPORT.md，旧报告、原始自动分数和快照保持原样。

## 改动位置与适用范围

新增 `migration_pipeline/utils/watch_persistence_semantics.cjs`，由 `source_phase_semantics.cjs` 调用。
`bounded_semantics.cjs` 输出 `watcher_contracts`；复用已有 `source_watch_persistence_not_landed` 诊断和 `restored_source_watch_persistence` 规则名。
ValidateStage、确定性预处理、模型返回后处理继续通过同一 AST 桥接处理；已有候选门已登记该诊断，本轮以真实调度器、正向接受和反向拒绝用例验证其衔接，没有放宽门禁。

这是通用源驱动规则，没有 MonitoringDashboard、settings 或 dashboard_settings 的组件／字段／存储键特判。
支持范围是可解析 Options API 导出父组件中的源单参数 watcher、已证明的尾部 `localStorage.setItem(字面量键, JSON.stringify(当前值))`，以及目标 inited 中唯一直接注册的块状函数回调。
不承诺继承、多个注册、间接 storage 别名、任意 watcher 形态或所有业务语义等价。

检测范围与自动修复范围分开：识别到上述源契约后，目标复杂参数、旧值被实际使用、主体变化、作用域或状态转换不明确时仍保留诊断，不因不能安全自动修而静默视为通过。
诊断表示原尾部写入未得到证明；不把一切不匹配都说成已经实测的存储丢失症状。

## 自动恢复边界

- 使用 Babel 的词法绑定做 alpha-mapping，不用字符串替换参数名；保留属性键、字符串和嵌套绑定，避免捕获同名自由变量。
- 允许单个改名当前值参数、当前值加未使用的旧值参数、或无参回调首部从同一路径 `data.get` 取得的唯一 const 当前值。
- 第二参数必须无引用、无重赋值；当前值绑定不可重赋值，JSON/localStorage 不能被局部或模块绑定遮蔽。
- 源前缀转换为 San 状态读取后，必须与目标既有主体逐项同序匹配。额外效果、条件改变、已有其他写入、复杂签名、async、返回／异常／循环／嵌套函数／eval／arguments 等不猜修。
- 只在原回调末尾追加源写入，使用目标当前值绑定；不改变参数列表、原条件、刷新逻辑、生命周期、模板、CSS 或子组件。不新增保存或挂载触发点。
- 已正确保留尾部写入的受支持形态不重复写；再次处理必须固定点。

## Prompt 与上下文闭环

`repair_prompt.py` 明确参数改名或无用旧值参数不能成为删除持久化的理由。
复核发现本轮 SSM 的 `watch.handler_body` 仅是截断预览，没有尾部写入，不能靠它向模型提供完整依据。
`repair.py` 将原 Vue 文本交给 Prompt 构造器；针对 watcher 诊断，以 AST 提取的完整源 handler 和契约补充证据。不编造未提供的源码。
修改的是 repair 阶段 Prompt／输入桥接及共享语义规则，没有修改 generation 或服务器 Prompt。

## 测试与冻结回放

新增 17 项测试：泛化字段／存储键、作用域与自由变量、参数变化、拒修但保留诊断、固定点、安装的 San watcher 存储桩、ValidateStage、两个 repair 入口、候选门和实际调度器。
受控 Node storage 桩在构造后写入 0 次，设置变化两次后依序写入 2 次；不是真实浏览器存储或用户人工验收。
真实调度器以冻结候选为输入，0 个模型请求、1 个确定性步骤完成修复。

首次完整 397 项测试有 2 项旧诊断集合预期失败，246.666 秒；源码复核确认旧产物也遗漏尾部写入。
仅向两项历史测试补充当前诊断及 `script.watch.settings` 位置断言，不改旧快照、旧评分，也不放宽检测。
两项单独通过后重新完整 **397/397 通过，239.652 秒**。计数为先前 374 项加之前 6 项审计和本轮 17 项。
当前 v5 审计工具同时区分冻结零错误与新规则实时诊断，不再要求当前规则复现旧漏检；旧分析 summary 不覆盖。

离线输入为原 v5 最终件：新规则报告 1 条持久化错误，DOM 0.9912。
一步仅插入 `localStorage.setItem("dashboard_settings", JSON.stringify(newValue));` 后静态零错误，DOM 0.9825、仍通过。
完整原文扣除这条插入与输入一致；固定点、正向门通过、逆向删除写入被拒绝。
两个 DOM 观测全部保留，不挑较高分，也不把差异归因于本次写入或模型质量改善；本次没有固定渲染随机输入。
初始化展开序列和通知权限接口／零新增引用继续通过独立 AST 复核。

证据包：`data/experiments/analysis/formal_30_v4_watch_persistence_closure_v1_20261104`。
2026-11-04T15:48:36+08:00 冻结，16 文件校验通过，含 11 份代码／测试、派生 San、完整测试日志、replay.json、317 项 live inventory 和校验脚本。
派生候选 `MonitoringDashboard_watch_persistence_offline.san`，SHA-256：
`3cbe7d15e64ce8df02cd79f2dbd510af998a3f8bb05187df60d2c221926aa5b4`。

## 后续边界

原始模型快照 364 文件仍完整；旧协议 frozen 352 项仍可验证，但当前代码已改变，其旧 live 不再适用，不能改旧 SHA 清单绕过。
没有新模型调用、真实浏览器存储／权限操作、人工页切换、canonical San 修改、commit 或 push。
原 v5 自动 1/1、242231 tokens 不回填为本次离线修复结果；没有新生成／人工通过或完整 30 项通过结论。
后续可先将独立离线候选用于人工确认，再为当前最终规则另建整批开发回归协议；任何模型运行都不能复用旧 live 协议。
