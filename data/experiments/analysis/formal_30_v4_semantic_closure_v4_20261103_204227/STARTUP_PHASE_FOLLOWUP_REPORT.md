# 源初始化阶段／次数通用闭环：离线完成

日期：2026-11-03。承接本目录原始结果分析；不改写原始 v4 自动通过分数。

## 修改位置

新增 `migration_pipeline/utils/startup_phase_semantics.cjs`，通过现有 source-phase／bounded AST 桥接接入验证和 repair。
相对本轮模型运行的冻结代码，5 个已有文件发生变化：

- `utils/source_phase_semantics.cjs`：接入源驱动启动包装方法规则，与旧展开序列搬移避免重叠编辑。
- `utils/bounded_semantics.cjs`：返回 `startup_contracts` 审计信息。
- `stages/repair.py`：新诊断可触发有边界确定性预处理；现有模型返回后处理也复用同一规则。
- `utils/repair_scheduler.py`：新诊断纳入候选门语义回归保护。
- `utils/repair_prompt.py`：新诊断进入聚焦 repair Prompt，明确移动已证实的提前调用，而不是只在 attached 追加第二次调用。

`ValidateStage` 原有桥接会读取共享模块的新 findings，新增错误码 `source_startup_phase_not_landed`；验证器文件本身未改，但检测行为已改变。
本轮没有改 generation、服务器 Prompt、预算或旧结果文件；不是“只改 Prompt”或针对组件名硬编码。

## 证明与拒修边界

只识别源导出父组件 mounted 的首个无参业务包装方法：其主体必须完全由已有的无参方法调用构成。
目标父组件中须存在唯一、无参、方法体 AST 相同的非生命周期别名；依据源代码与方法体映射，不依赖 MonitoringDashboard／initDataImpl 名称。

源不得有其它早期生命周期或该方法的其它引用；模板事件、动态成员访问、spread／mixins／重复 option、歧义别名、async 等不自动修。
只计父 inited／attached 的直接无参调用；不是任意间接调用图、条件或异步回调的全面等价证明。
可证明的直接阶段／次数不匹配保留诊断；未知场景不猜删。

自动处理进一步要求：inited 中仅有一次末尾调用；其前面只能是唯一、源命名、无 immediate／未知选项的 watcher 注册。
若 attached 已在首条调用同一方法，只移除 inited 的多余语句；若 attached 缺少它，把这条已证实的末尾语句移动到 attached 首部。
保留 watcher 文本、其它方法、子组件、模板与 CSS；额外效果、条件调用、多个调用、晚期顺序不匹配或未知用途不删除。

候选门拒绝“提前调用仍在，却只在 attached 新增调用”的真实次数回归；正确后移／去重可以接受。
该码没有加入任何诊断可见性豁免，不能以“旧缺陷”为由自动判通过。

## 测试与冻结证据

新增 15 项测试，覆盖真实最终产物、真实第一轮修复、通用方法／不同别名、拒修边界、验证器到确定性 Stage、真实 Stage 后处理、候选门及真实调度器零模型闭合。
实际安装的 San 构造／直接 attached hook 测试确认：构造后初始化次数 0，执行 attached 后次数 1，原 watcher 仍可响应。
这不是浏览器人工交互验收。

最终完整 **343/343** 测试通过，207.094 秒。代码在完整测试／重放前后哈希一致。
证据包：`data/experiments/analysis/formal_30_v4_startup_phase_closure_v1_20261103`，24 文件 SHA-256 校验通过。
包含 18 个代码／测试文件、完整测试日志、两份独立离线候选、replay.json、302 项当前输入／代码哈希清单和验证脚本。
原始快照 342 文件、旧协议 frozen 329 项再次校验；旧协议 live 与当前代码不同是预期，不修改旧 SHA 清单。

两份冻结输入各 1 个确定性步骤、0 模型请求：

| 冻结输入 | 本次旧件诊断 | 应用规则 | 离线结果 |
| --- | --- | --- | --- |
| 第一次模型修复 | 提前初始化、基础挂载行为缺失 | relocated_source_proven_startup_wrapper | 静态 0 错误；DOM 0.9912 |
| 原最终自动通过产物 | 提前且重复初始化 | removed_source_proven_duplicate_startup | 静态 0 错误；DOM 0.9912 |

修复后两份均为 inited 0 次、attached 1 次，固定点与反向回归拒收均验证。
两份都保留原有迁移提示警告，初始 DOM 通过不是全部交互通过；没有新生成模型分数。

最终产物派生候选 `final_automatic_pass_offline.san` SHA-256：

```text
6e585ea512971c5f9840e440ffb16c51acac17e813547bac86856b0aebc9aef5
```

首轮派生候选 `first_repair_offline.san` SHA-256：

```text
2c7697c35bbf51069403473e13847fbe9f3aad7784888d02dd27aa3a7492c44b
```

## 解释与后续

原 v4 summary 仍为 1/1 自动通过、272803 tokens，不改成新验证器下的分数。
新检查器能发现旧件漏检，再经规则闭合，是验证系统变化后的离线开发证据，不是独立测试或新鲜模型成功。
源通知权限方法的删除仍是单独审查项，本规则不猜补业务方法；不能声称该组件所有语义问题都已解决。

离线候选未覆盖 canonical San、测试页面或 summary；未启动模型／服务器、未执行浏览器人工测试、未 commit／push。
TaskManager 已验收候选和测试页配置保持。后续模型运行必须新建冻结协议，不能直接沿用旧 v4 launcher 或 --force 重抽。
完整 30 项开发回归及探索性评估仍未完成。
