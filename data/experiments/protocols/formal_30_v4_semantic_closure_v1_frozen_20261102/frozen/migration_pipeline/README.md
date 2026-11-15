# migration_pipeline

## 最小运行示例

先启动 `local_server`，再在项目根目录执行：

```bash
python3 migration_pipeline/run_generate_stage.py \
  --vue-file data/datasets/components/01_simple/step/vue/step.vue \
  --output-file data/experiments/step.san \
  --instruction ""
```

如果想保留原有默认文件并另存一份，可以传不同文件名，例如：

```bash
python3 migration_pipeline/run_generate_stage.py \
  --vue-file data/datasets/components/01_simple/step/vue/step.vue \
  --output-file data/experiments/step_from_pipeline.san \
  --instruction ""
```

如果已经有 SSM JSON，也可以直接执行：

```bash
python3 migration_pipeline/run_generate_stage.py \
  --ssm-file path/to/ssm.json \
  --output-file data/experiments/from_ssm.san
```

## 多轮 repair 闭环运行示例

先启动 `local_server`，再在项目根目录执行：

```bash
python3 migration_pipeline/run_pipeline.py \
  --vue-file data/datasets/components/01_simple/step/vue/step.vue \
  --output-file data/experiments/step.san \
  --max-repair-rounds 3
```

运行后会输出最终 San 文件路径，并默认导出 repair 指标报告到：

```text
data/experiments/repair_reports/<source>_repair_history.json
```

如果已经有 SSM JSON，也可以直接执行：

```bash
python3 migration_pipeline/run_pipeline.py \
  --ssm-file path/to/ssm.json \
  --output-file data/experiments/from_ssm.san \
  --report-file data/experiments/repair_reports/from_ssm_repair_history.json
```

报告中包含初次 validate/visual_eval 摘要、最终结果、`stop_reason`、`repair_rounds`，以及每轮 repair 后的结构相似度、树编辑距离和错误数量。

## 分层批量实验

评估器校准后的 9 个代表样本配置位于：

```text
migration_pipeline/batch_configs/pilot_9_v4.json
```

旧批次 `pilot_9.json` 已冻结为测量工具校准实验；`pilot_9_v2` 已在完成 simple 与 medium 共 6 个样本后冻结，用于记录评估器校准后、Repair Prompt 增强前的基线。两者都不应继续追加或覆盖。对应快照分别位于 `data/experiments/snapshots/pilot_9_pre_evaluator_fix_20260924_150916/` 和 `data/experiments/snapshots/pilot_9_v2_pre_prompt_fix_20260924_155149/`。

`pilot_9_v3` 沿用 v2 的评估器和相同样本，新增以下实验变量：

- Repair Prompt 明确要求 computed 通过 `this.data.get(...)` 读取；
- 精确保留 Vue `data()` 初始值；
- 双向绑定只允许可赋值路径，派生表达式使用单向插值；
- 连续两轮代码哈希、错误码和结构指标完全相同时，以 `no_repair_progress` 提前终止。

v3 正式运行两个针对性 medium 样本后已冻结到 `data/experiments/snapshots/pilot_9_v3_targeted_pre_ssm_fix_20260924_162405/`。其中 DataPaginationTable 真实通过；FormRulePlayground 因 SSM data 初始表达式被截断、关键属性差异低于结构阈值而假通过。当前默认批次 `pilot_9_v4` 在 v3 基础上新增：

- SSM 同时保存完整 data 初始表达式和可静态求值的结构化值；
- Validator 精确比较 Vue data 与 San initData 的静态初始值；
- `value`、`checked`、`selected`、`disabled` 等关键 DOM 属性不一致直接判错。

v4 的两个针对性 medium 样本均在一轮 repair 后通过；FormRulePlayground 的初始状态已达到 DOM 零差异。v4 结果已冻结到 `data/experiments/snapshots/pilot_9_v4_targeted_pre_interaction_fix_20260924_164548/`。源码复核发现其错误提示文本和数值转换与 Vue 有轻微漂移，因此“通过”应解释为静态、编译和初始状态轻量 DOM 通过，而非完整浏览器交互等价。

`pilot_9_v5` 保留完整 computed/method 源码，并支持配置提交后交互场景。FormRulePlayground 在比较器校准后通过；DataPaginationTable 在 3 轮 repair 后仍生成 `disabled="{= expression =}"`，最终以 `dom_critical_attribute_mismatch` 失败，共消耗 97,731 token。该失败不能覆盖或改写。

当前默认批次为 `pilot_9_v6`。v6 在 v5 基础上新增 `invalid_dynamic_attribute_binding` 静态错误：`disabled`、`checked`、`selected` 等派生属性必须使用 `{{ ... }}` 单向插值，禁止使用 `{= ... =}` 双向绑定；generation 与 Repair Prompt 同步加入相同硬约束。合法的可赋值路径（例如 `value="{= pageSize =}"`）仍允许使用双向绑定。

运行前先做 dry-run，只校验样本路径、复杂度配额和输出计划，不会调用模型：

```powershell
python migration_pipeline/run_batch_pipeline.py --dry-run
```

确认 `local_server` 已启动后执行批量实验：

```powershell
python migration_pipeline/run_batch_pipeline.py
```

也可以先运行单个样本：

```powershell
python migration_pipeline/run_batch_pipeline.py --sample-id simple_step
```

批量 runner 默认具备：

- 每个样本结束后原子更新 checkpoint/汇总 JSON；
- 已标记为 `completed` 的样本下次自动跳过；
- 执行异常记录为 `error`，下次运行自动重试；
- 单样本异常默认不影响后续样本；
- `--force` 可强制重跑已完成样本；
- `--fail-fast` 可在首个执行异常后停止；
- `--include-state` 可在单样本报告中保留完整 pipeline state。
- 连续两轮 repair 结果无进展时提前终止，并在 repair history 中记录 progress signature。

默认输出位置：

```text
data/experiments/pipeline/batches/pilot_9_v6/
data/experiments/repair_reports/batches/pilot_9_v6/
data/experiments/batch_reports/pilot_9_v6_summary.json
```

批量汇总包含初次通过数、repair 后通过数、执行异常数、平均 repair 轮数、停止原因分布、token 消耗，以及 simple/medium/complex 分层统计。

## 文件职责

- `migration_pipeline/__init__.py`
  - 对外统一导出 pipeline 相关公共接口。
  - 方便外部直接导入 `GenerateStage`、`GenerateStageInput`、`MigrationPipelineOrchestrator` 等对象。

- `migration_pipeline/config.py`
  - 管理 pipeline 访问统一生成服务所需的配置。
  - 目前主要包含 `MIGRATION_GENERATION_API_URL` 和 `MIGRATION_GENERATION_TIMEOUT`。

- `migration_pipeline/generation_client.py`
  - 封装 migration pipeline 访问生成服务的 HTTP client。
  - 目前提供 `GenerationRequest`、`GenerationResult`、`HTTPGenerationClient`，对上游 stage 隐藏 HTTP 细节。

- `migration_pipeline/repair_client.py`
  - 封装 migration pipeline 访问修复服务的 HTTP client。
  - 目前提供 `RepairRequest`、`RepairResult`、`HTTPRepairClient`，默认请求 `/api/evaluation/repair`，避免 repair 阶段复用 generate 接口。

- `migration_pipeline/orchestrator.py`

  - 放置当前的编排入口和状态结构。
  - `MigrationPipelineState` 是未来 LangGraph state 的过渡定义。
  - `MigrationPipelineOrchestrator` 目前提供 generate、validate、visual_eval、repair 的节点入口，以及一次修复复检闭环 `run_generate_validate_visual_eval_repair_and_recheck()`。

- `migration_pipeline/run_generate_stage.py`
  - 最小可用的终端脚本入口。
  - 支持从 Vue 文件先提取 SSM 再生成，也支持直接读取现成的 SSM JSON 进行生成。

- `migration_pipeline/run_pipeline.py`
  - 可重复运行的完整 pipeline 终端入口。
  - 调用 generate、validate、visual_eval 和最多 3 轮 repair 闭环，并导出每轮 repair 指标报告。

- `migration_pipeline/stages/generate.py`
  - 当前已实现的生成阶段。
  - 负责：优先使用传入的 `ssm`；若未提供，则调用 `SSMFactory` 从 `vue_source` 或 `vue_file_path` 构建 `ssm`；随后调用统一 generation service 生成 San。
  - `run_from_state()` 是未来接 LangGraph 节点时最直接的入口。

- `migration_pipeline/stages/validate.py`
  - 当前已实现的代码级校验阶段。
  - 负责检查生成的 San 单文件组件结构、San 必要脚本格式、San script 可执行性、Vue 语法残留、San 状态读写规则，以及与 SSM 中组件名、props、data、事件处理函数的基础一致性。
  - 不负责渲染快照、DOM tree 对比或视觉差异；这些职责交给 `visual_eval.py`。
  - `run_from_state()` 可直接接收 generate 阶段输出，作为未来 LangGraph 的 validate 节点入口。

- `migration_pipeline/stages/visual_eval.py`
  - 当前已实现的渲染与结构评估阶段。
  - 负责调用 `vue_render.py` 和 `san_render.py`，分别生成 Vue/San 的 `html_snapshot` 与 `dom_snapshot.tree`。
  - 负责调用 `dom_compare.py`，输出 `tree_edit_distance`、`structure_similarity`、`tag_sequence_similarity`、`text_similarity` 以及节点差异报告。
  - 后续截图、像素差异、页面比对都应在这个阶段继续扩展。

- `migration_pipeline/stages/repair.py`
  - 当前已实现的修复阶段。
  - 负责消费 `validate` 和 `visual_eval` 的错误/差异报告，构造修复 prompt，调用 generation client 生成修复后的 San，并保存到修复输出路径。
  - `run_from_state()` 可直接接收 generate/validate/visual_eval 后的 state，作为未来 LangGraph 的 repair 节点入口。

- `migration_pipeline/utils/san_compile.py`
  - 提供 San script 可执行性校验工具。
  - 通过 Python 调用 Node，在沙箱中执行 `.san` 的 `<script>` 块，检查基础语法、`require('san')`、`san.defineComponent(...)` 和组件导出结构。

- `migration_pipeline/utils/vue_render.py`
  - 提供 Vue 组件渲染快照工具。
  - 执行 Vue Options API 样本，合并 props、data、computed 后渲染 template 插值，输出统一格式的 `html_snapshot` 与 `dom_snapshot.tree`。

- `migration_pipeline/utils/san_render.py`
  - 提供 San 组件渲染快照工具。
  - 通过 Python 调用 Node，执行 `.san` 的 `<script>`，合并 `initData`、props 和 `inited` 后渲染 template 插值，输出 `html_snapshot` 与 `dom_snapshot.tree`，为后续 DOM 对比和视觉评估打基础。

- `migration_pipeline/utils/dom_compare.py`
  - 提供 Vue/San DOM tree 对比能力。
  - 基于 `dom_snapshot.tree` 计算轻量树编辑距离、结构相似度、标签序列相似度、文本相似度，并输出缺失、新增、变化节点。

- `migration_pipeline/utils/repair_prompt.py`
  - 提供修复 prompt 构造能力。
  - 负责压缩 validate/visual_eval 报告、整理 DOM 差异，并生成供大模型修复 San 的提示词，避免 `repair.py` 承担过多 prompt 拼装逻辑。

- `migration_pipeline/utils/ast_compare.py`
  - 预留给 AST 级别比对能力。
  - 未来可用于源码级模板结构或脚本结构相似度分析。

- `migration_pipeline/utils/image_diff.py`
  - 预留给图像差异比对能力。
  - 未来可用于视觉结果的量化比较。

- `migration_pipeline/utils/screenshot.py`
  - 预留给截图能力。
  - 未来可用于组件渲染结果采集，配合视觉评估阶段使用。

## 当前职责边界

- `migration_pipeline`
  - 负责流程侧组织：提取 SSM、调用统一 generation service、承接未来 LangGraph 编排。

- `local_server`
  - 负责服务侧能力：接收请求、调用外部大模型、返回统一生成结果。
