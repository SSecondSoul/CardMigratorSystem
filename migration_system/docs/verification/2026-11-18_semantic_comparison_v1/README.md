# 通用比较与受限 setter 契约验证

2026-11-18，用户明确授权以源码内部可静态确认调用＋普通 data 状态键验收；不证明任意外部键等价。原完整公开键失败记录不追溯改判。

最终合并回归：152 项通过，0 跳过，369.747 秒（102＋16＋10＋7＋7＋5＋5）。前端构建／类型检查通过，98 项引擎清单核验通过，系统目录外隔离运行通过（响应替身，真实模型调用 0）。这些是工程检查，不是 152 个迁移样本或两个失败组件整体通过。

## 内容

- `frozen/`：两次失败原件，包含原请求、SSM、revision、评估、模型消息／收据和原报告；另存与原请求 SHA-256 对应的 source.vue。没有把模型答案用于生成。
- `before/`：原内置引擎方法判定、静态结果／修复 Prompt 与原清单。对应源指纹保留在新 MANIFEST。
- `after/`：原 revision 1 在当前实现下的离线静态／浏览器／多维重评，原 source／target 不改；工程回归和隔离目录验证另存为 tests.json、standalone.json。
- `after/implementation/`：本轮关键实现／测试／复核脚本的字节副本；SHA256SUMS.json 同时绑定 payload 和当前实现。`seal_semantic_comparison.py` 默认只读核验，`--create` 仅允许首次封存，拒绝覆盖。

HabitWeekTracker 模板 93.75% → 100%、受限 setter 证明通过，但 DOM 23 处 class 表示差异未获保守归一化批准，整体仍失败。PollResults 受限 setter 证明通过，但确实新增 span 包装，静态／结构仍失败；控件路径不再误称值差异。原报告和旧 Token 保留，未运行新模型、不改数据库／队列、不降低阈值。交互仍 not_run。

## 复核

在 migration_system 目录执行：

```powershell
& .venv/Scripts/python.exe scripts/seal_semantic_comparison.py
& .venv/Scripts/python.exe scripts/verify_semantic_comparison.py --output var/semantic-comparison-v1/new-tests.json
& .venv/Scripts/python.exe scripts/replay_semantic_comparison.py --evidence-dir docs/verification/2026-11-18_semantic_comparison_v1/frozen --output-dir var/semantic-comparison-v1/new-replay
```

新输出必须不存在。Notebook `2026-11-18_semantic_comparison_v1.ipynb` 只读核验这些证据。回归属于软件测试，不是迁移样本；standalone 使用明确记录响应替身验证图、评估、修复、API／下载，实际付费模型调用为 0，不据此宣称复杂样本已通过。
