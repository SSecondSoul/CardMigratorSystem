# 语法优先修复闭环（target_syntax_first_v1）

> 下文保留 2026-11-16 的初始规则与历史验证口径。2026-11-17 已扩展来源可证明的缺失 option／多处标点恢复和拒绝反馈；最新范围、反例限制与完整初始路径验证见 [闭环补齐记录](SYNTAX_CLOSURE_20261117.md)。解析策略版本不变，各新增正规化规则以独立规则名登记。

## 目的与顺序

针对生成的 San SFC 不能解析、语义分析级联报错且修复反馈只有 `invalid_target_sfc` 的缺口，增加独立语法层。不是修正 Vue 源码，也不是降低迁移通过阈值。

真实主路径：生成 → SFC／Babel／San 语法检查 → 静态语义 → 双端浏览器／结构／视觉／代表动作 → 候选保护。语法失败时，后续检查明确记为 deferred／not_run，不生成大量解析失败的语义诊断；静态和编译维度保持 fail，绝不签发通过。

诊断提供类别、消息、源码片段和绝对位置（JavaScript UTF-16 偏移，行列从 1 开始）。SFC／Babel 可定位到错误；San 模板解析器未提供精确偏移时，显式标记 `location_precision=template_block_start`，不伪称是精确错误列。最多存储 64 条诊断，并保留总数与 overflow 标志。

## 有边界的通用规则

1. **循环属性修复**：只接受形如 `<s-for="item in items trackby item.id">…</s-for>` 的无其他属性包装，且内层只有一个元素。必须在 Vue 模板中找到唯一匹配的循环变量、集合、key 和元素标签，才把 s-for 移到该元素。真实 AST 位置排除属性字符串、注释和插值中的伪标签。不会添加 div，不猜测缺失元素，不处理多子节点、嵌套包装、来源不匹配或未知表达式。
2. **对象方法分隔符修复**：Babel 指向缺少逗号的位置；只插入一个逗号。完整脚本重新解析成功后，还需在新 AST 中确认插入点恰是两个相邻 ObjectMethod 之间。数组、普通语句、多个尚未解决的脚本错误不自动猜测。

规则不读取组件名，也不以 ExpenseTracker 白名单放行。正常产物保持原字节；每次修改记录规则名、位置与替换内容，并重新进行全部适用检查。规则仍不能证明任意业务行为等价。

## Prompt 与候选门控

- **生成 Prompt 未修改**，继续使用绑定的既有生成入口。
- **语义修复 Prompt 未替换**，继续复用旧 `build_repair_prompt` 和确定性规则。
- **新增语法修复专用消息**：规则不能改善或规则候选被拒绝时，传入当前 San、原 Vue、具体语法诊断和最小修改约束，不重复注入完整 SSM／级联语义报错。这是新增的修复分支，不宣称与旧完整 messages 逐字相同。
- 语法规则只生成候选，不直接通过。两个语法失败候选只在诊断数量严格减少、未新增错误类别且未发生截断时认可进展。
- 语法首次通过时，以前 deferred 的语义错误属于“新可观察结果”，不应误当成修复引入的回退；门控记录 `syntax_unblocked_semantic_checks`。候选仍必须满足全部 required 维度才能通过。已通过维度丢失、源基准阻断仍拒绝；语法通过后的常规新错误保护不变。
- 修复轮数／模型次数／Token 停止线未增加。停止线仍不是严格计费上限；本轮没有修改输入 Token 预估或预算预留算法。

## 实现与部署

核心文件：`browser/target-syntax.mjs`、`browser/syntax-cli.mjs`、`adapters/syntax.py`、`stages/syntax.py`；接入 `application/migrations.py` 和 `stages/evaluation.py`。解析不会在 Node 中执行上传／生成脚本，也不需要云模型密钥。

API 和 `migration-worker` 必须重启，然后新建任务。实现绑定随代码改变，不能直接恢复旧冻结任务以替换历史结论。工作台“候选决策与差异”和下载报告包含语法诊断、deferred 检查与修复焦点；未改测试页面或用户配置。

## 冻结样本回放

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/replay_syntax_repair.py `
  --run-id 5c2fc8916fcd4b8bb65f32ea28e20488 `
  --with-browser `
  --output-dir data/experiments/evaluator_calibration/选择一个全新目录
```

工具先验证源和 revision 哈希并冻结原始文件，再运行规则。只向独立证据目录写副本及候选，不调用模型、不上传 LangSmith、不更新数据库；已有证据目录拒绝覆盖。

最终证据目录为 `data/experiments/evaluator_calibration/2026-11-16_modular_expense_tracker_syntax_replay_v4`。首次 v1 浏览器超时留下未完成现场；v2／v3 是完整中间实现证据；v4 对应最终位置精度标注的实现。不是新增模型成功样本或独立测试集实验。

该样本原第 1、2 轮候选修正后语法／真实编译运行可通过，但静态语义／DOM 仍失败；初始版还丢了循环中的 option 元素，规则不会凭空补造。原失败状态和 175512 Tokens 账本保留，不得把“语法修好”写成“ExpenseTracker 已通过”。
