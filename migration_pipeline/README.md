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

## 文件职责

- `migration_pipeline/__init__.py`
  - 对外统一导出 pipeline 相关公共接口。
  - 方便外部直接导入 `GenerateStage`、`GenerateStageInput`、`MigrationPipelineOrchestrator` 等对象。

- `migration_pipeline/config.py`
  - 管理 pipeline 访问统一生成服务所需的配置。
  - 目前主要包含 `MIGRATION_GENERATION_API_URL` 和 `MIGRATION_GENERATION_TIMEOUT`。

- `migration_pipeline/generation_client.py`
  - 封装 pipeline 调用统一大模型生成接口的 HTTP client。
  - `GenerationRequest` 定义请求结构，`GenerationResult` 定义响应结构。
  - `HTTPGenerationClient` 负责向 `/api/evaluation/generate` 发送请求。

- `migration_pipeline/orchestrator.py`
  - 放置当前的编排入口和状态结构。
  - `MigrationPipelineState` 是未来 LangGraph state 的过渡定义。
  - `MigrationPipelineOrchestrator` 目前提供 `run_generate_only()` 和 `run_generate_node()` 两个入口。

- `migration_pipeline/run_generate_stage.py`
  - 最小可用的终端脚本入口。
  - 支持从 Vue 文件先提取 SSM 再生成，也支持直接读取现成的 SSM JSON 进行生成。

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
  - 当前已实现的渲染评估阶段。
  - 负责调用 `vue_render.py` 和 `san_render.py`，分别生成 Vue/San 的 `html_snapshot` 与 `dom_snapshot.tree`。
  - 后续 DOM 树编辑距离、截图、像素差异、页面比对都应在这个阶段继续扩展。

- `migration_pipeline/stages/repair.py`
  - 预留给修复阶段。
  - 未来可根据校验或评估结果触发二次修复生成。

- `migration_pipeline/utils/san_compile.py`
  - 提供 San script 可执行性校验工具。
  - 通过 Python 调用 Node，在沙箱中执行 `.san` 的 `<script>` 块，检查基础语法、`require('san')`、`san.defineComponent(...)` 和组件导出结构。

- `migration_pipeline/utils/vue_render.py`
  - 提供 Vue 组件渲染快照工具。
  - 执行 Vue Options API 样本，合并 props、data、computed 后渲染 template 插值，输出统一格式的 `html_snapshot` 与 `dom_snapshot.tree`。

- `migration_pipeline/utils/san_render.py`
  - 提供 San 组件渲染快照工具。
  - 通过 Python 调用 Node，执行 `.san` 的 `<script>`，合并 `initData`、props 和 `inited` 后渲染 template 插值，输出 `html_snapshot` 与 `dom_snapshot.tree`，为后续 DOM 对比和视觉评估打基础。

- `migration_pipeline/utils/ast_compare.py`
  - 预留给 AST 级别比对能力。
  - 未来可用于模板结构或脚本结构相似度分析。

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
