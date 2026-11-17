# 修复证据整理与完整评估追加撤销

2026-11-18，按用户明确要求修改模型修复的输入组织，不修改生成算法、迁移目标或质量门。策略为 `repair-evidence-projection-v1`，生产支持范围仍为 `san-supported-migration-v3`。

## 变更边界

- `stages/repair.py` 删除整份 `json.dumps(evaluation)` 追加。语法修复分支、规则修复的完整输入、重复请求门、模型调用账本、候选复测及回退保持原机制。
- `prompts/repair_context.py` 只用于发送前整理：精确重复的诊断合并，位置不同的诊断不合并；DOM／控件／属性差异放入旧 builder 可传递的 details，保留路径、预期值、实际值和比较策略。
- 样式按属性计数、记录缺失／改变类别，每属性最多两个路径和值示例；保留上游已经截断的标记，不把 500 个记录样本解释为全部问题。完整评估与原始观察仍本地保存，不按摘要重新计分。
- 完整 SSM 仍提供给原规则和旧 Prompt builder，以提取原语义契约。只在发送前把通用 Prompt 的全量 SSM 区块替换为按错误选择的分区与紧凑 JSON；原预期语义契约、所选方法体及默认值保留。未知错误保守回退完整紧凑 SSM，已有聚焦分支不重新塞入完整 SSM。
- Notice 明确这是局部证据，不是完整源码规范或通过证明；不允许据省略字段删功能、改门槛或声称错误消失。每次语义模型修复在原调用目录保存 `repair-context.json`，记录源证据哈希与选择策略。
- 内置 engine 98 项、生成消息、评估和收据不改；没有规则生成新路径、实例 Proxy、额外模型调用或依赖。

## 冻结失败请求的实际离线重建

原任务 `ee5d500651ea484bafeac17873bd0e04`，原源码 SHA-256 `f84efcfbc0b57731e358ff24264f6600a3a64fa58e725290f77799f4e7ac1d02`。

| 项目 | 原记录 | 本次离线重建 |
| --- | ---: | ---: |
| 修复用户消息字符数 | 346,990 | 107,019 |
| 字符减少比例 | — | 69.16% |
| 提供方输入 Tokens | 91,540 | 未调用，未知 |
| 本次真实模型调用 | — | 0 |

此处不是 Token、费用或迁移通过率提升实验。未调用模型、未修复该组件产物、未修改用户配置／实际任务库／队列，旧费用／停止原因不改。`source_dynamic_assignment_unproven` 等六类原诊断仍在，不豁免语义契约。

同一旧预期契约与新提示中的预期契约做对象比对，相同。选择 template／script／styles 等相关分区，省略重复索引；原 500 条样式差异汇成 13 个属性组及最多 26 个定位示例，记录原计数和上游截断。完整原始数据在 frozen 中保留。

## 文件与复现

- `before/`：修改前修复阶段和旧 AST 来源对照测试，保留原证明口径。
- `frozen/`：旧模型请求／提供方收据、接受的修复后 San、SSM 和对应评估，仅复制并核验，不改旧任务文件。
- `after/messages.json`：离线生成的新请求消息，**未发送给模型**。
- `after/context.json`、`after/report.json`：输入投影选择与字符对比。
- `after/standalone.json`：仓库外副本实际运行结果与实现指纹。CounterCard 使用明确模型响应夹具验证原修复及六维检查；复杂组件只检查入模后主动暂停，不声称复杂组件质量通过。
- `after/implementation/`：本次边界、脚本与专项测试实现副本。
- `SHA256SUMS.json`：本目录 payload 指纹，不包含自身。

在 migration_system 中可选择全新输出目录重新离线构造，不启动网络模型或数据库任务：

```powershell
& .venv/Scripts/python.exe scripts/replay_repair_context.py `
  --evidence-dir docs/verification/2026-11-18_repair_context_v1/frozen `
  --source tests/fixtures/CapacityPlanningBoard.vue `
  --output-dir var/repair-context-v1/另选全新目录
```

## 已执行检查

| 检查 | 结果 |
| --- | --- |
| `test_modular_*.py` | 102 项通过，303.999 秒 |
| `test_repair_context.py` | 10 项通过，4.552 秒 |
| `test_refactor_reuse.py` | 5 项通过，41.711 秒 |
| `test_dynamic_setter_production.py` | 7 项通过，32.831 秒 |
| `test_san_business_contract_policy.py` | 7 项通过，0.544 秒 |
| 冻结请求离线投影／原契约一致性 | 通过 |
| 仓库外独立副本主链 | 通过 |

以上共 131 项 Python 测试，不是全部仓库测试或 131 个迁移样本。原 AST 全函数相等测试保留修改前原件，改为逐项证明原规则前缀、规则候选、语法路径、重复请求与模型调用门及产物保存未变；生成与旧 Prompt builder 来源对照仍通过。前端没有变更，未重复构建。

下一步：重启 API／Worker、创建新任务取得真实模型结果；不跨版本恢复旧预算阻断任务，不自动提高 Token 额度，不以本次输入减少代替迁移正确率证据。
