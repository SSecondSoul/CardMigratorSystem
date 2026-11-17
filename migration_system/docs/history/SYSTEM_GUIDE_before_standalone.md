# 独立化前的历史系统说明（原文保留，路径与启动命令已被新指南替代）

2026-11-16 后续：[语义与 DOM 通用修复](SEMANTIC_REPAIR.md)。共享规则补齐类名分隔、数值样式依赖和 watcher／mounted 顺序；冻结候选离线检查及 15 步交互通过，不回填原失败任务，也不当作新模型迁移成功率。部署需重启 API／真实 Worker 后新建任务。

2026-11-16 补充：[语法优先修复闭环](SYNTAX_REPAIR.md)。生成后先解析；失败时提供类别／位置／片段，语义和浏览器检查暂缓。可证明的局部规则先生成候选，否则使用聚焦语法消息；语法通过不等于迁移通过。部署需重启 API 与真实 migration-worker，旧任务不改绑。

更新：2026-11-16。新主路径协议：`modular-migration-v1`。面向本机单用户、自包含 Vue Options API 组件，不是互联网多用户服务。

本次把真实迁移模块接入同一个工作台、API、数据库和 LangGraph，而不再要求逐模块人工交接。旧开发夹具、G1—G3 边界试验和既有实验数据继续保留。**工程实现完成与真实模型效果验证是两件事**：缺少凭据的云模型／LangSmith，以及缺少模型权重和训练资源的 LoRA，不会被模拟结果替代。

## 1 开题技术路线与模块

| 开题要求 | 实际主路径／入口 |
| --- | --- |
| 四维 SSM 与 AST 提取 | `adapters/ssm.py`，真实 compiler-sfc／Babel 提取，失败不冒充 AST 成功 |
| SSM 驱动生成与 few-shot | `prompts/migration.py`；默认从两个自建开发演示选择一个，完整示例进入实际 messages 并冻结哈希；同源／同组排除 |
| San AST 与 SSM 结构校验 | `stages/structure.py`；San 真正解析模板，SSM v3 模板维度与目标进行共同投影，执行有序 Zhang–Shasha TED；四维中的脚本／绑定／事件／样式另经现有语义校验 |
| 生成—校验—反馈—修复 | `graph/migration.py` 独立节点和条件边，不包装旧 orchestrator 的整条循环 |
| 规则与模型混合修复 | `adapters/legacy_checks.py`／`legacy_worker.py` 明确调用现有验证器、确定性规则和修复 Prompt；不实例化旧模型客户端；无规则命中才请求模型 |
| 候选保护 | 所有候选完整复测；原先通过维度退化、出现新诊断代码、无严格改善时拒绝，保留接受版本 |
| Puppeteer／像素／样式 | `browser/evaluate.mjs`、`metrics.mjs`；新浏览器会话、固定视口、截图、DOM、计算样式、SSIM、实际不同像素率和差异热图 |
| 代表性交互 | 相同 props、同序列 click／input／select／key／drag；比较每步 DOM、样式与表单控件值／勾选状态，未配置则 `not_run` |
| LangSmith | `observability/traces.py` 实际 SDK 调用；显式启用后导出图阶段、模型请求哈希、耗时、用量与状态；默认不上传 |
| LoRA | `training/data.py`、`training/lora.py`：分组数据准备、PEFT 训练、参数检查、日志、适配器保存／加载、本地推理统一接入主图 |
| 视觉嵌入辅助 | `adapters/embedding.py` 本地 CLIP 模型、冻结模型／处理器；仅辅助，不抵消其他失败；模型未配置明确未执行 |
| 业务持久化与人工记录 | Alembic 0007；任务、原始请求／响应、调用收据、所有候选／检查／决策／图片、人工耗时与改动行数；哈希归属审计和备份 |
| 前后端 | 现有 Vue 3 工作台新增真实迁移页签，Flask 同源 API 与独立 `migration-worker`；开发夹具另页签，不混用通过率 |

默认演示不是从原测试集抽取的答案，也不代表 few-shot 已带来准确率提升。用于论文的训练／验证／测试样本、消融和效果，仍必须按实验协议另行运行。

## 2 统一部署

先停止旧 API／Worker。当前用户业务库已只读核对为 **0006**，本次没有自动迁移或覆盖它。部署新代码需升级到 **0007_modular_migration**，只新增四张真实迁移表；原表、文件及历史快照不改写。

在仓库根目录执行（依赖本工作区已安装；换机器时先按 README 安装 Python 与根目录 AST 依赖）：

```powershell
npm.cmd --prefix migration_system/browser ci --ignore-scripts --no-audit --no-fund --cache migration_system/var/npm-cache
npm.cmd --prefix migration_system/frontend run build
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py init-db
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py system-status
```

升级前如需另存旧业务库，用 SQLite 的 backup API（包含已提交 WAL），不要运行中只复制 `.sqlite3` 主文件。系统自身的已校验备份在升级至当前 schema 后使用 `backup`／`verify-backup`，旧备份保持原 schema，不能伪造为新版本。

窗口一：

```powershell
$env:CARDMIG_SYSTEM_WRITE_TOKEN = [guid]::NewGuid().ToString('N')
$env:CARDMIG_SYSTEM_WRITE_TOKEN
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py serve
```

窗口二（真实任务必须启动这个 Worker，旧 `worker` 命令仅处理开发夹具）：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py migration-worker
```

浏览器访问 `http://127.0.0.1:8790/`。默认打开真实迁移页，上传可信 `.vue`、填本地写入令牌并确认范围后创建任务。模型 API key 不在页面输入。配置网络开关和密钥的方法见 [待补配置](SETUP_PENDING.md)。

本次已构建前端。后续 Python／运行配置变化需重启 API 与 Worker；前端变化需重新 build。旧运行绑定实现和协议，不因升级自动续跑。

## 3 执行、授权和恢复

新任务在入队时冻结源码哈希、props、场景、阈值、完整运行配置、few-shot 内容及选择结果、实现指纹和调用授权。该授权只适用于这个任务，不是 G3 历史单计划批准的继续执行。

- 最多一次生成、三轮修复，最多四次模型请求；规则修复也计入三轮预算。
- 每次模型调用前先持久化请求及 `started`，收到原始响应后先记录响应与 usage，再决定候选是否有效。错误输出也保留已知成本。
- 已登记响应可重放，状态不明的 `started`／`unknown` 不自动重发；需要复核，不能通过恢复按钮偷偷再消费一次。
- 原始请求和响应、接受版本、失败候选、评估和决策均为不覆盖文件；报告与备份读取时重新核对字节哈希。
- 网络默认关闭。未配置时任务明确阻断，不返回占位 San。开启网络后应创建新授权任务；不能修改旧任务的冻结网络权限。
- 环境密钥不属于冻结明文配置，可补齐同一环境变量后受限恢复；代码、Prompt、模型配置变化则拒绝旧检查点。
- 取消是协作式的：保留已发出的请求及返回成本，在下一安全阶段停止，不声称取消能撤销已产生的费用。

**预算政策变化必须披露**：G3 的条件性一百万输入 token 上界批准边界保持原状，仍不由本次入口自动放行。新协议采用显式请求次数、每次输出上限和已知返回用量停止线，**不是精确输入计数，也不是硬计费上限**；没有从 32768 自动扩大为一百万的隐藏批准。用户应在实际启用前确认此政策；若需要严格总 token／金额上限，应保持网络关闭并接入可靠计数或供应商账户限额，不能将字符数当计费 token。

## 4 评价口径

默认固定：结构相似度 `>0.95`、UI 还原度 `>95%`、不同像素率 `<0.05`，以及静态／编译运行／源基准通过。配置了交互才将其列入必需维度，未配置不会冒称行为等价。

UI 分数 = `100 × (0.5 × SSIM + 0.3 × (1 − 不同像素率) + 0.2 × 样式一致率)`。独立保存三项原始指标。SSIM 为均匀 8×8 亮度窗口、总体方差实现；不同像素率为 RGBA 任一通道差值大于 10 的像素比例，不是 `1−SSIM`。该配方是新协议，不能混称既有实验的同口径结果。

结构主指标比较实际提取的 SSM 模板与 San 模板 AST 的共同投影，另报源模板 AST TED 和双端 DOM TED。投影覆盖元素、属性／绑定名称、事件名称、指令和直接文本；不证明表达式或任意公开方法等价。SSM 对混合文本／子节点顺序的局限另由静态检查和渲染 DOM 检查约束；`key` 身份语义不由 TED 证明。

2026-11-16 评估兼容性修正后使用 `ssm_v3_element_attributes_events_directives_direct_text_v2`：按 San 表达式种类区分整段插值和文本分段，不把三元表达式的分支文字当作静态文本；合并动态 class 时保留可识别的固定 class token；相邻文本先合并再归一化空白。样式路径按元素兄弟编号，不受缩进文本／注释影响。阈值、TED 单位代价、像素和 UI 公式不变；class 条件与 token 边界仍由复用的静态验证器检查。结构差异另附限量的具体路径和标签，供诊断和修复使用。

这属于评估实现版本修正，不表示旧报告自动变成新口径。历史任务／模型账本不改写；离线重评写独立证据。可用下列命令对已有完整任务做只读对照（不调用模型，`--output-dir` 必须是不存在的新目录；`--with-browser` 会执行可信组件）：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/replay_evaluator_compatibility.py `
  --run-id 已有任务ID --with-browser --output-dir data/experiments/evaluator_calibration/新的证据目录
```

对照包含当前旧验证器直接调用与新适配层调用、旧 DOM 快照评估阶段、新结构评估及可选浏览器评估；不把旧 DOM 阶段称为像素评估，也不宣称已验证所有旧样本。新任务的旧模块指纹覆盖 `.py`、`.cjs`、`.js`，避免遗漏实际 Node 语义检查器变更。部署需重启 API／真实 Worker；旧任务不改绑重跑。

### 空 class 的受限比较策略与 DOM 诊断

`empty_class_presence_v1` 不是全局忽略空属性。浏览器先对双端源码做保守 AST／模板／CSS 检查：仅在自包含数据组件未发现 DOM 属性观察、反射、未知调用、外部／运行时扩展或 CSS 属性选择器／`attr()` 等依赖时，才允许在**比较副本**上消除精确的 `class=""`；非空／空白类名以及其他属性不归一化。未知依赖、分析失败、旧的无结构化属性快照保持严格比较。该策略只适用于已声明的组件内观察范围，不证明任意外部脚本观察属性存在性时等价。

报告保留 `raw_dom_ted`、`raw_dom_differences`、策略批准／拒绝原因、归一化路径；`dom_ted` 是明确策略下的有效比较指标。原始树不改写，不能将归一化后的 100% 称为原始 DOM 完全相同。所有动作也分别保留原始／有效 DOM 指标。策略的代码指纹随任务绑定，新旧报告不能静默混算。

实际 DOM 或代表交互失败会产生 `rendered_dom_mismatch`／`representative_interaction_mismatch`，包含具体路径、属性标签、策略原因或动作名，不再只有分数；这些诊断会由现有修复链路传入模型消息。候选在其他保护均满足时，可识别实际 DOM 的严格改善，避免模板分数相同而丢失进展。未放宽新错误／原通过维度保护，也未增加修复轮数。

独立重评可通过 `--diagnostic-actions migration_system/configs/diagnostics/choice-chips-actions.json` 添加本地动作文件，最多 20 步；这只是新证据中的补充场景，不改写原任务请求中的空场景。默认 `ChoiceChips` 示例覆盖即时、每日、关闭和恢复每日四次选择；不证明所有外部 props 或其他环境。

源异常、警告和资源阻断会保留基准阻断，不让模型修 Vue。目标编译／运行异常作为目标缺陷；浏览器缺失、依赖缺失或容量超限属于设施／范围阻断，不作为模型修复理由。

页面读取运行记录而非模拟百分比。`finished` 仅表示**配置检查**通过，不是所有输入下功能等价，更不是论文已达 85%／90%／70% 目标。人工确认单独追加，绑定最终产物哈希，不改写自动分数。

## 5 当前支持范围

- 对源父组件中精确的 `this[key] = value` 公共 setter，当前无法证明任意公开键的完整契约；新任务在模型调用前以 `source_dynamic_key_contract_unsupported` 阻断。源代码合法，不应通过缩小到几个固定状态键或反复调用模型放行。初始及动作后的控件实际值另行检查，实际值一致不豁免 DOM 属性存在性差异；见 [公开键契约记录](PUBLIC_KEY_CONTRACT_20261117.md)。
- 自包含、单元素根节点的 Options API JavaScript Vue SFC；支持 `export default`，也支持单一顶层 `module.exports = { ... }` Options 对象（仅在隔离浏览器内建立 CommonJS 作用域，不改写上传文件）。混合／重复导出或 CommonJS 工厂调用不放行；内联子组件可在源码内声明，不能依赖未提供的模块。
- San SFC 使用 CommonJS `require("san")`，按既有生成契约声明 DataTypes、dataTypes、initData；其他 require 不被执行。
- 当前浏览器主路径显式阻断外部 import、script setup、TypeScript／JSX 运行、SCSS 等预处理、外部资源／服务及跨模块依赖包，不静默删除依赖。**完整模块化系统不等于支持任意 Vue 工程。**
- 源码 ≤256 KiB；场景 ≤20 步；DOM TED ≤1500 节点、样式采集 ≤300 元素；超过容量阻断，不截断后签发通过。
- 固定视口截图只覆盖该视口；动画／过渡关闭，不自动遮罩、改写随机数／时钟、抑制源警告或修正 Vue 源码。不同随机数据可导致差异，必须另立评估配置，不能硬判等价。
- 执行的是可信本地组件。浏览器有新临时用户目录和每端新 context、HTTP 请求拦截，没有使用用户浏览器会话；这不是恶意代码的系统级沙箱，不应上传不可信文件。

## 6 CLI、批量和实验导出

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py submit-migration `
  --source path/to/Component.vue --max-repair-rounds 3 `
  --idempotency-key my-run-v1 --trust-local-source --confirm-model-calls

& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py migration-report --run-id 这里填migration_id
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py migration-statistics
```

`--evaluation-config` 接 JSON，例如 `{"props":{},"actions":[{"name":"下一页","type":"click","selector":".next"}]}`。场景检查的是 DOM、样式和表单状态，不是任意 JavaScript eval。拖拽使用原生浏览器自动化，失败留证。

批量 manifest：

```json
{"batch_id":"development-batch-v1","samples":[{"id":"case-a","group":"family-a","vue":"relative/CaseA.vue","props":{},"actions":[]}]}
```

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py submit-migration-batch `
  --manifest path/to/batch.json --trust-local-source --confirm-model-calls
```

同批全部 group 从 few-shot 候选中排除。相同源码复用输入登记；相同 batch_id／sample_id 使用幂等键跳过已有请求，不自动重新生成。输入、配置或实现变动应更换批次 ID，并保留前次结果。策略可选 `direct`（源码零样本、无修复）、`ssm_no_repair`、`ssm`；要归因 SSM／few-shot／修复的独立增益，必须预先固定其余变量，不能把三个默认组合的差异全部归因某一个模块。

统计保留所有配置任务在分母内，分别报告静态、运行、结构、视觉、交互、综合、已知成本和人工台账。不补造历史耗时，不将开发／披露接触样本改称独立测试。

## 7 内部验证与未验证项

源 HTML 空元素解析与结构化错误提示的 2026-11-17 修复见 [源模板解析说明](SOURCE_TEMPLATE_PARSING.md)：合法 `<input>`／`<img>`／`<br>` 不再被误报缺结束标签；真正不完整的标签仍在模型调用前阻断。历史错误不回填，预检查完成不等于迁移通过。

2026-11-17：初始生成语法失败、拒绝反馈、来源匹配样式／watcher 及验证→修复调度闭环的最新边界与离线证据，见 [闭环补齐记录](SYNTAX_CLOSURE_20261117.md)。冻结产物回放与真实新模型迁移须分别记录；不恢复旧任务或覆盖原结果。

代码内含图路由／恢复／未知调用／幂等／回退／备份／API 权限测试、真实浏览器同图／颜色差异／交互／目标异常校准和真实前端→临时数据库提交测试。最终执行结果见 [开发记录](DEVELOPMENT_20261116.md)。

本轮没有调用云模型、向 LangSmith 上传、下载模型权重、执行 LoRA 训练、重跑历史 30 样本、修改原 Vue 或覆盖实验记录。真实外部连通性和迁移效果需要在补齐 [配置清单](SETUP_PENDING.md) 后统一验证，不需要再为每个小模块单独交接。

实现 API 依据：[Puppeteer 独立 context](https://pptr.dev/api/puppeteer.browser.createbrowsercontext)、[请求拦截](https://pptr.dev/guides/network-interception)、[截图](https://pptr.dev/guides/screenshots)、[LangSmith create_run](https://reference.langchain.com/python/langsmith/client/Client/create_run)、[PEFT](https://huggingface.co/docs/peft/en/quicktour)。实际安装版本及本地测试结果优先于把文档示例当作已经完成远程验收。
