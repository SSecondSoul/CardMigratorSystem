# 安装与运行

当前更新：已按用户要求删除源 AST 确定性生成路径。`setValue(key, value) { this[key] = value; }` 不再单独触发预检查阻断；新任务统一回到原有模型生成、校验和有界修复链，范围为 `san-supported-migration-v3`。模型配置仍必需，放行不等于迁移已经正确。历史任务和证据不改判。

当前使用[有明确支持范围的生产闭环](docs/PRODUCTION_CLOSURE_V1.md)，不启用公开实例代理研究。先完成一条范围内真实任务即可，不必先配置 LoRA／LangSmith／CLIP，也不必等待完整兼容契约。旧任务仍按原指纹保留，新实现请创建新任务。

所有命令均在 **`migration_system` 目录内**执行，不需要原“毕业设计”根目录的代码或 Node 依赖。需要 Python、Node.js 和本机 Chromium／Edge／Chrome；当前验证环境是 Windows，其他平台须单独复测。

## 1. 安装（已有对应依赖时可跳过）

```powershell
cd 你的路径\migration_system
uv venv .venv
uv pip sync --python .venv/Scripts/python.exe --require-hashes requirements.lock
npm.cmd --prefix engine ci
npm.cmd --prefix browser ci
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
```

保留三份 Node 锁是为了不升级原来不同模块已验证的版本。`engine` 包含 AST／San 依赖，`browser` 包含 Puppeteer／像素依赖，`frontend` 包含 Vue 及构建工具；都是本目录内部，不依赖父目录 node_modules。不需要启动旧 `local_server`。

只读检查：

```powershell
& .venv/Scripts/python.exe scripts/run_system.py check
```

它核验内部实现指纹和目录配置，不调用模型，也不初始化数据库。`scaffold_verified` 不等于组件迁移通过。

## 2. 配置与新数据库

模型／浏览器／追踪／LoRA 统一在 `configs/system.toml`；现有用户配置未被本轮重构改写。模型密钥放在其 `api_key_env` 指定的环境变量中，不写入源码。LangSmith 上传默认仍需显式开关与凭据，不在重构验证中自动启用。

默认运行路径在 `configs/development.toml`：

- 数据库与图检查点：`var/runtime/`。
- 上传源文件、SSM、San、报告、截图和调用收据：`var/artifacts/`。

原 `var/business.sqlite3`／`var/langgraph.sqlite3` 及原仓库 `data/experiments/migration_system/` 保留不动。它们不是新路径中的空记录，也没有被删除；不自动导入、不改旧任务实现绑定、不自动重发旧模型请求。本轮只在临时副本初始化测试库，未替你初始化实际新库。

停止本系统旧 API／Worker 后，在本目录显式初始化新的默认路径：

```powershell
& .venv/Scripts/python.exe scripts/run_system.py init-db
```

## 3. 启动（两个终端）

终端一：

```powershell
$env:CARDMIG_SYSTEM_WRITE_TOKEN = [guid]::NewGuid().ToString('N')
$env:CARDMIG_SYSTEM_WRITE_TOKEN # 仅在自己的终端查看并复制到页面，不提交或发送给他人
& .venv/Scripts/python.exe scripts/run_system.py serve
```

终端二，同样进入本目录：

```powershell
$env:LLM_API_KEY = '你的模型密钥'
& .venv/Scripts/python.exe scripts/run_system.py migration-worker
```

如果配置中的密钥变量名不是 LLM_API_KEY，使用配置指定的变量名。打开 http://127.0.0.1:8790/；页面“本地写入令牌”使用终端一变量的值，不是模型密钥。`worker` 现在也是真实迁移 Worker 的别名；仅演练旧开发夹具时才使用 `development-worker`。

上传 Vue、确认可信本地执行及模型调用授权后创建任务。源语法／支持范围问题在模型前阻断；模型调用后保存每次实际响应／用量，候选复测后才能接受。下载和人工反馈不能覆盖自动结论。Ctrl+C 停止服务，不删除数据库。

## 4. 提交现有组件：原有模型迁移流程

停止旧 API／Worker 后按第 3 节重启，浏览器 Ctrl+F5 刷新。页面范围应为 `san-supported-migration-v3`；否则仍是旧服务或旧页面。

上传你原来的 Vue 源码，**不要修改 setValue，也不要用已知正确的 San 作为输入**。策略选默认“SSM ＋ 有界修复”，确认可信执行、模型调用费用及本地令牌后创建新任务。不需要指定特殊组件名称、规则路径或专用 JSON。原有 SSM 生成 Prompt、静态校验、模型修复 Prompt、候选复测和回退继续使用。

评估配置中的交互 JSON 是**可选测试用例**，不是生成参数或路由条件。不填时仍进行静态、编译运行、初始结构和视觉检查，交互项标记 `not_run`，不宣称完整功能通过。[capacity-planning-actions.json](configs/diagnostics/capacity-planning-actions.json) 仅是 CapacityPlanningBoard 的可选验收示例，其他组件无需使用它。

新任务成功进入生成阶段后，应有模型调用收据；初始来源为 `generation`，后续修复来源仍按实际模型修复或原有规则修复记录。源码中的动态赋值不再被单独提前拒绝，但错误生成仍会被校验并尝试有界修复，预算用尽仍如实失败。语法错误、外部依赖等原有限制仍保留；不保证任意公开 API 全部等价。

旧任务 `dc9c942c547745ed989bc3db583af744` 来自现已撤销的规则路径，不恢复、不改写为模型结果。需要比较当前效果时创建新任务；不要跨实现版本继续旧检查点。

## 5. 可选：普通模型路径冒烟 CounterCard

这是工程冒烟任务，不是独立论文测试样本；请创建新任务，不恢复旧版本检查点。页面上传或粘贴以下源码，文件名填 `CounterCard.vue`，使用默认 SSM 策略和修复预算：

```vue
<template><button class="card" @click="increment">{{ count }}</button></template>
<script>
export default {
  name: 'CounterCard',
  data() { return { count: 0 } },
  methods: { increment() { this.count++ } }
}
</script>
<style>.card { color: rgb(20, 40, 60); }</style>
```

在“评估配置”的交互 JSON 填：

```json
[{"name":"increment","type":"click","selector":"button"}]
```

确认可信执行、模型调用费用和本地写入令牌后提交。验收查看：新任务范围为 `san-supported-migration-v3`；模型调用／Tokens 有真实收据；六个质量维度（含交互）通过；SSM、San、报告能下载；人工确认另外记录。初始产物已通过时不应为演示强制修复；如失败，按该任务实际诊断处理，不放宽门槛或反复付费复跑。

历史报告中的 `source_dynamic_key_contract_unsupported` 保留原结论；当前生产预检查不再仅因该模式停止，其他解析／配置阻断仍正常报告。

## 6. 验证与研究入口

```powershell
& .venv/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py' -v
npm.cmd --prefix frontend test
& .venv/Scripts/python.exe scripts/verify_standalone.py --output var/refactor-verification/另选全新结果.json
```

最后一条把系统及已安装依赖实际复制到仓库外临时目录，禁止读取原工程源码，使用临时数据库、真实解析器／LangGraph／Puppeteer和明确的模型响应测试替代检查主链。不会调用真实模型或修改原库；需要浏览器启动权限。Python 已安装的第三方环境与本机浏览器仍是正常运行依赖，不属于旧项目源码。

`test_refactor_reuse.py` 是在原实验仓库运行的来源对照，独立复制后不存在旧源码时明确跳过；这不影响独立主链，也不把跳过当作获得新来源证据。历史冻结样本用例同样属于实验区对照，不宣称所有含旧数据的测试都能在新机器上凭空复现。

训练研究命令仍通过 `run_system.py build-training-data`、`train-lora` 进入；不在普通迁移时自动训练或下载模型。真实模型效果、LangSmith 上传及 LoRA 训练结果须用各自原始证据验证，不能用工程夹具通过替代论文统计。
