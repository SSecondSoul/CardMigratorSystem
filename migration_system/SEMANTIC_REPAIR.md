# 语法之后的通用语义与 DOM 修复（2026-11-16）

> 本页保留 2026-11-16 的固定接受候选与历史结果。2026-11-17 已对后续真实失败的最初生成版本补齐字符串 CSS 包络、源 deep watcher 配置和诊断→修复调度，且验证完整图路径；最新范围与证据见 [闭环补齐记录](SYNTAX_CLOSURE_20261117.md)。不能把旧页中选定候选的成功外推为所有新生成都通过。

本轮延续 [语法优先闭环](SYNTAX_REPAIR.md)。不修改 Vue 源码、手工测试页、用户配置或原失败任务，不增加修复额度／降低阈值，也没有调用模型或修改 Prompt。

## 修改位置与边界

修改的是实验流水线与新系统共用的规则／验证模块，不是特定组件的生成文件。新系统 `adapters/legacy_worker.py` 的验证入口和 `enable_residual_v2=True` 规则入口自动复用这些变更。旧实验流程需使用启用了对应规则集的入口，不宣称所有历史配置都已启用同样规则。

| 问题 | 处理 | 保留的限制 |
| --- | --- | --- |
| Enter 键事件丢失 | 复用已有 `source_dom_semantics.cjs`，恢复来源匹配的键盘 guard | 不替换未知业务 handler，不推测组合修饰符 |
| `row{{record.type}}` 合并成错误类名 | 扩展 `class_binding_semantics.cjs`，核对 DOM 路径、循环／条件作用域、静态前缀与原动态引用后补分隔符 | 合法字符串拼接不误报；未知表示保留 review；只证明分隔符，不证明任意运行时数组／对象类名转换等价 |
| 样式对象与 CSS 插值不能对应，且公开方法被加了依赖参数 | 扩展 `source_render_dependency_semantics.cjs`，证明单尺寸属性／显式单位／只读数值叶方法后恢复源公开签名，另建私有模板依赖方法 | 不归一化任意 CSS；单位、属性、参数或方法体变化均拒绝；脚本另有引用、多模板引用、未知调用及副作用不自动恢复 |
| 源 mounted 调用误放 inited，但 attached 已有 watcher | 扩展 `source_phase_semantics.cjs`，保留来源匹配的 watcher 并把原调用移动到其后 | 要求没有其他早期钩子、未知启动语句、重复／未知 watcher、即时 watcher 或不同回调；不复制初始化调用 |

CSS 证明仅支持 width／height／位置／最小最大尺寸中的一个属性、一个插值，以及匹配的 `%`／px／em／rem／vh／vw 单位。源方法须是可证明只读、全部返回路径为数值操作的叶方法。私有方法显式接收响应式依赖；公开方法重新从 `this.data.get(...)` 读取源字段，不能为修模板而改变源公开调用方式。已有文本渲染 DAG 规则不改成无条件恢复公共方法。

watcher 阶段规则要求回调与源 handler 是同一组无参数方法调用，字段在已声明状态中；深度选项仅接受布尔值，即时执行不放行。它修复的是来源已确认的调用阶段与顺序，不证明跨刷新持久化或任意调度时序完全等价。

## 冻结重放结果

原任务：`5c2fc8916fcd4b8bb65f32ea28e20488`，`ExpenseTracker.vue`，3 次历史模型调用，已知 Tokens 175512，原状态 blocked / model_usage_stop_reached 不变。

本次输入固定为原接受 revision 1 经上一轮通用语法规则得到的候选，SHA-256 `6b513daf6bb3e8a12738516f01d2c8b34bd0be6f675171dee84f1fea2065438a`，不是挑选新生成样本。新规则候选 SHA-256 为 `9b8be8e3a0adcd7bd1f0b03246601b21441954a281b281ad31acea542fd1e34f`。

当前检查下静态错误从 7 项降至 0。编译运行、源基准、静态、SSM／San 模板结构、原始／有效 DOM、视觉均通过；原始 DOM 与结构均 100%，UI 100%、SSIM 1、不同像素 0。原任务的代表交互仍不回填；另加 15 步诊断场景全部通过，覆盖非 Enter 不添加、Enter 添加、收支切换、分类／类型过滤、清除过滤、主题切换和删除。候选门控 `strict_improvement` 接受，规则重复运行字节不变。

辅助源 Vue／目标模板 AST 投影仍为 **96.10%**，未改成 100%：三个 Vue `binding:key` 在 San 中合入循环 trackby，投影表示不同；循环／key 契约另由旧静态规则检查。这不改变主指标或通过阈值。

最终证据：[semantic_replay_v3](../data/experiments/evaluator_calibration/2026-11-16_modular_expense_tracker_semantic_replay_v3/)。先核验并复制上轮 30 个证据 payload，再保存原件副本、规则实现副本、新候选、双端截图、原始快照、每步差异及门控；v1／v2 保留中间版本，不覆盖。工具不连接模型或任务数据库。

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/replay_semantic_repair.py `
  --source-evidence data/experiments/evaluator_calibration/2026-11-16_modular_expense_tracker_syntax_replay_v4 `
  --diagnostic-actions migration_system/configs/diagnostics/expense-tracker-actions.json `
  --output-dir data/experiments/evaluator_calibration/选择一个全新目录
```

## 验证与应用

新增测试 `tests/test_source_semantic_followup_v1.py` 覆盖真实 San 求值／公开方法及依赖更新、watcher 注册后只加载一次、合法拼接反误报，以及单位／副作用／参数／作用域／未知 watcher 等拒绝用例。最终测试统计见 [开发记录](DEVELOPMENT_20261116.md)。

这是冻结开发产物的自动规则回放，不是新模型端到端结果或独立测试正确率。没有对源码缺失 option 的初始 revision 0 补造元素，也没有证明任意 props、全部公开调用、持久化跨刷新或新生成代码都正确。

部署需重启 API 和 `migration-worker`。新建任务才会绑定更新后的共享规则；不要给旧失败任务改绑或回填通过。数据库无需新迁移。若后续开展真实模型复跑，应另登记运行并保留费用与新产物，而不是覆盖本次离线证据。
