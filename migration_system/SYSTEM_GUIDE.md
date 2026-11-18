# 安装与运行

**2026-11-18 SQLite 多用户版已实现。现在要用账号登录／用户管理，请直接按 [多用户启动指南](MULTI_USER_GUIDE.md) 操作**：使用 `--config configs/multi_user.toml` 初始化独立库、隐藏密码提示创建首个管理员，再以同一配置启动 API 和迁移 Worker。下面未带该参数的命令仍是原本机单用户实验模式，不要混用两个模式的 API／Worker。

远程 MySQL 准备更新为 [多用户 34 表交接 v2](docs/deployment/mysql_handoff_v2/MYSQL_MULTI_USER_HANDOFF.md)，与当前 SQLite 0008 实现对齐。原 [v1 交接](docs/deployment/mysql_handoff_v1/MYSQL_DATABASE_HANDOFF.md) 保留为 0007 的 26 表与早期草案，不再代表最新账号实现。当前没有自动连接 MySQL 或迁移原实验库。

最新增量（2026-11-18 闭环 v2）：修正普通对象键／简写比较误报，补齐 `this.computed.*` 的 AST 检测与有界修复，并用控件身份／父拓扑证据区分候选诊断细化与新缺陷。沿用 v4 范围，生成仍走模型，历史失败不改判；五次冻结重放仍有真实或未获准归一化的结构差异，不能宣称全部通过。见 [结果与边界](docs/CLOSED_LOOP_V2.md)。

当前更新（2026-11-18）：新任务范围为 `san-supported-migration-v4`，继续使用模型生成、校验和有界修复，不启用源 AST 确定性生成。按用户确认，动态 setter 仅证明“源码内部可静态确认的普通 data 状态键调用”，不证明任意外部公开键等价；不按方法名放行，也不修改 Vue 源码。历史任务和证据不改判。详见 [通用修复与边界](docs/SEMANTIC_COMPARISON_V1.md)。

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
& .venv/Scripts/python.exe scripts/run_system.py serve
```

终端二，同样进入本目录：

```powershell
$env:LLM_API_KEY = '你的模型密钥'
& .venv/Scripts/python.exe scripts/run_system.py migration-worker
```

如果配置中的密钥变量名不是 LLM_API_KEY，使用配置指定的变量名。打开 http://127.0.0.1:8790/；用户页面自动建立本地会话，不再需要填写写入令牌。会话有效期 8 小时，API 重启后失效；刷新页面可自动连接，失败的写入请求不会自动重发。此模式仅适用于本机单用户，不是公网账号认证。`worker` 现在也是真实迁移 Worker 的别名；仅演练旧开发夹具时才使用 `development-worker`。

实验脚本／旧开发夹具仍可使用 `X-Cardmig-Token`。如需此接口，在启动 API 前设置 `$env:CARDMIG_SYSTEM_WRITE_TOKEN = [guid]::NewGuid().ToString('N')` 并仅在自己的终端使用；未设置时 API 自动生成内部随机令牌，不暴露给页面。模型 API Key 仍只提供给 Worker。会话与安全边界见 [本地浏览器会话](docs/LOCAL_BROWSER_SESSION_V1.md)。

上传可信 Vue 源码后点击创建任务；页面保留源码执行及模型费用说明，不再要求额外确认勾选。提交仍保存后台确认字段，便于实验分析；上传或建立会话不会自动创建任务。源语法／支持范围问题在模型前阻断；模型调用后保存每次实际响应／用量，候选复测后才能接受。下载和人工反馈不能覆盖自动结论。Ctrl+C 停止服务，不删除数据库。

## 4. 提交现有组件：原有模型迁移流程

停止旧 API／Worker 后按第 3 节重启，浏览器 Ctrl+F5 刷新。页面范围应为 `san-supported-migration-v4`；否则仍是旧服务或旧页面。

上传你原来的 Vue 源码，**不要修改 setValue，也不要用已知正确的 San 作为输入**。用户页面固定“SSM ＋ 有界修复”，填写后创建新任务，无需选择基线／消融策略或输入本地令牌。不需要指定特殊组件名称、规则路径或专用 JSON。原有 SSM 生成 Prompt、静态校验、模型修复 Prompt、候选复测和回退继续使用。

评估配置中的交互 JSON 是**可选测试用例**，不是生成参数或路由条件。不填时仍进行静态、编译运行、初始结构和视觉检查，交互项标记 `not_run`，不宣称完整功能通过。[capacity-planning-actions.json](configs/diagnostics/capacity-planning-actions.json) 仅是 CapacityPlanningBoard 的可选验收示例，其他组件无需使用它。

新任务成功进入生成阶段后，应有模型调用收据；初始来源为 `generation`，后续修复来源仍按实际模型修复或原有规则修复记录。源码中的动态赋值不再被单独提前拒绝，但错误生成仍会被校验并尝试有界修复，预算用尽仍如实失败。语法错误、外部依赖等原有限制仍保留；不保证任意公开 API 全部等价。

本轮同时修正动态 class 固定 token 在源／目标模板上的不对称比较，并区分真实 DOM 结构、class 表示差异和控件路径变化。原始 DOM／TED 始终保留；仅在现有保守观察审查获准时归一化 class 空属性、HTML 空白、顺序及重复 token。未知依赖不忽略差异，新增包装节点不按“表示差异”删除。逐方法证明在报告 `assessment.source_method_contracts`，被拒原因也会进入修复输入；保留 helper 与源码匹配的内联写入均可证明，单纯同名或键名相同不能通过。

2026-11-18 修复输入整理：生成阶段仍发送原有完整语义信息，不改变生成 Prompt。模型修复不再追加整份 `evaluation`；重复诊断合并，样式差异按属性计数并保留路径／源值／目标值示例，已截断的观察明确标记。已识别错误只发送相关 SSM 分区；未知错误保守回退完整 SSM 的紧凑 JSON，不截断方法体或默认值。原有语义契约和未修改代码仍需保留，不能把未发送的字段理解为源中不存在。

完整 SSM、评估、原始浏览器数据仍本地保存；规则修复读取完整证据，质量门和候选回退不变。每次语义模型修复新增 `calls/<轮次>/repair-context.json`，记录证据哈希、选择范围、原始／发送字符数；实际发送内容和提供方 Tokens 仍以 `request.json`／`receipt.json` 为准。字符减少不等于相同幅度的 Token 或费用减少。重启 API／Worker、创建新任务使用此策略，不恢复旧实现检查点；不会自动重发旧调用或提高额度。

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

阅读源码执行及模型费用说明后点击创建，无需填写本地写入令牌。验收查看：新任务范围以页面当前支持范围为准；模型调用／Tokens 有真实收据；六个质量维度（含交互）通过；SSM、San、报告能下载；人工确认另外记录。初始产物已通过时不应为演示强制修复；如失败，按该任务实际诊断处理，不放宽门槛或反复付费复跑。

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
