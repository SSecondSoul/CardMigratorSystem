# 五次失败任务的通用闭环修复证据

本目录不替换旧实验；工程开发回放，不是独立测试。完整说明：[CLOSED_LOOP_V2](../../CLOSED_LOOP_V2.md)。

最终关联回归 165/165、零跳过（337.730 秒）；独立副本验证通过；新增云调用 0。首轮测试中旧 Prompt 等价性断言未覆盖本次明确新增的一条提示，调整为仅允许该字节差异后重跑全套通过；初次失败摘要单独保留。旧 16 项修复上下文封存、126 项语义比较封存以及原 235 个任务登记文件均再核验哈希未变。

文件分层：

- `FREEZE.json`：变更前 479 项 payload 的哈希、任务顺序、235 个登记文件核验结果。
- `jobs/`：五次历史任务的登记产物、上传源码、只读数据库摘录。原失败与共 414835 Tokens 不重算。
- `before/`：修复前引擎／业务层实现，保留旧比较与旧接受门。
- `after/replay/`：真实静态／本机浏览器重放、独立规则候选及历史候选接受判断；模型新增调用 0，实际业务数据库未修改。
- `after/tests.json`、`after/standalone.json`：完整关联回归与移出仓库后的独立运行验证。独立测试使用明确的已记录响应替身，不是云模型质量实验。
- `after/tests-initial-old-prompt-expectation-failure.json`：保留首次旧 Prompt 断言失败，不作为最终通过结果。
- `after/implementation/`：本轮实现、用例、复验／封存脚本原件。
- `SHA256SUMS.json`：本轮最终清单。只允许首次创建，后续只读核验。

核验命令（在 `migration_system`）：

```powershell
& .venv/Scripts/python.exe scripts/seal_closed_loop_v2.py --require-live-match
```

未来授权修改实现后，不加 `--require-live-match` 仍可核验历史封存原件。旧 `semantic_comparison_v1`／`repair_context_v1` 的 payload 和 seal 均不修改，旧脚本要求“当前代码等于旧版”时出现 live mismatch 不等于历史文件丢失。

所有五次原任务仍是失败记录；新规则候选和可接受的进步不得写回旧记录或宣称全部通过。控件位置／span 差异继续失败，未知 class 观察条件保持严格比较。代表性交互仍未运行。
