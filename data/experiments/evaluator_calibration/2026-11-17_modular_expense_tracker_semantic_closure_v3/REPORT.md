# ExpenseTracker：初始生成产物离线闭环（2026-11-17）

本说明在 payload 清单生成后追加，`SHA256SUMS.json` 仍封存原 62 个证据 payload，不覆盖原任务。

## 输入与边界

- 原任务：`b2a59e959191487fa4c3acbe945f04cb`；原结果 failed／repair_budget_exhausted、真实模型调用 3、已知 Tokens 80802 保持不变。
- 使用该任务最初生成的 revision 0，而不是挑选已人工修好的版本。
- 先经 `2026-11-17_modular_expense_tracker_syntax_closure_v3` 的来源匹配语法规则；本目录核对并复制其 36 个封存 payload，再执行实际共享语义规则与浏览器检查。
- 本轮新增真实模型调用 0，不上传 LangSmith、不读写真实业务数据库、不修改源 Vue 或原 San。

## 结果

| 检查 | 语法规则后、语义规则前 | 语义规则后 |
| --- | --- | --- |
| 静态语义 | fail | pass |
| 编译／运行 | pass | pass |
| 源基准 | pass | pass |
| SSM／目标结构＋DOM | fail | pass |
| 视觉 | pass | pass |
| 原任务代表动作 | not_run | not_run |

诊断总数由 9 项降为 0（前者包含结构诊断，不能全部称作静态错误）。最终 SSM／San 结构和原始／有效 DOM 均 100%，UI 100%，SSIM 1，不同像素比例 0。辅助源／目标模板 AST 保留 96.10%，没有改成 100%；key／trackby 的投影表示不同仍须由独立规则约束。

另加固定 15 步诊断动作，全部通过，静态／运行／源基准／结构／视觉／交互各维度均 pass；不回填原任务的空动作配置。覆盖收支新增、Enter 与非 Enter、分类／类型过滤、清除、主题切换和删除。没有证明跨刷新持久化、任意 props、任意公开调用或所有调度行为等价。

候选门控 strict_improvement 接受；再次运行规则字节不变。最终候选 SHA-256：`0c0d2cde569db4f1fce50b680da732a2b7888e06ce90b19109bfa660e9e00ff3`。

规则包括既有类名分隔／Enter 恢复、数值样式只读依赖图，以及新补的源 deep watcher 配置注册。修复入口同时补齐 missing_watch 诊断到有界规则的映射，不只验证 helper 本身。

## 中间结果保留

`semantic_closure_v1` 静态剩余 3 条，`v2` 剩余 2 条；二者均保留，不与本次成功重放混同。早期浏览器在受限环境启动失败是工程环境失败，不能记成迁移通过；最终评估使用临时隔离浏览器。完整 LangGraph 与测试统计见 `migration_system/DEVELOPMENT_20261116.md`。

这是同一个开发失败样本的离线规则验证，不是一次新模型生成成功，也不进入独立测试成功率分母。
