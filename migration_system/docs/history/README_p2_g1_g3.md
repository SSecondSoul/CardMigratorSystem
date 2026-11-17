# 历史阶段说明（P2／G1—G3，保留原文，不作为当前启动指南）

版本：`0.1.0.dev0`。2026-11-16 按用户要求由逐步交接转为完整模块化开发，新增真实迁移主图、生成／校验／视觉／交互／修复／候选保护、LangSmith 接口、few-shot、LoRA、真实任务前端和 API。原 P2b／P2c 与 G1—G3 实验入口保留。**当前使用入口以 [系统指南](SYSTEM_GUIDE.md) 为准，外部依赖统一见 [待补配置](SETUP_PENDING.md)**，本文件后部的阶段记录保留为历史，不自动变更旧实验结论。

工作台默认页签现在使用真实迁移模块；“开发夹具与 SSM 历史”页签继续执行原夹具，仍不计迁移成功。真实云模型／LangSmith 默认禁用，未配置就阻断。LoRA 已有实际执行代码，未下载权重或训练。系统是本机、受限组件范围的工程实现，不宣称全部 Vue 语法、外部服务、论文目标或生产环境已验收。

依据：[重构方案](../docs/architecture/迁移系统整合重构方案_v1.md)、[全栈方案](../docs/architecture/前后端与数据持久化方案_v1.md)。旧流水线、人工 runner 和冻结实验保持原位。

## 实现边界

| 部分 | 当前状态 |
| --- | --- |
| 工程与契约 | 独立 src 包、TOML 配置、目录边界、固定 P1 源指纹的只读适配 |
| 持久化 | SQLAlchemy、Alembic 0001→0007；用户实际库已确认 0006，本次只读核对，待统一部署升级；新增真实任务／调用／文件／人工记录进入备份 |
| API／worker | 真实 HTTP、持久入队、独立 worker、单活租约、独立心跳、开发 readiness、事件轮询、取消／受限恢复 |
| 图编排 | 独立真实迁移图：预检→SSM→生成→评估→诊断→修复→候选复测／接受或回退→报告；旧夹具图另行保留 |
| 产物与恢复 | 不可覆盖提交、字节哈希、版本归属、收据复用、未决尝试／实现漂移阻断 |
| 质量与研究能力 | 主路径接入真实生成适配、SSM／目标 AST TED、旧静态规则、San 解析／浏览器运行、Puppeteer／DOM／SSIM／像素／样式与代表交互；真实模型效果未测 |
| 真实 SSM 提取 | 独立历史图与新主图都调用真实提取器；历史报告不改写 |
| 契约报告 | 夹具仍为严格 P1 未执行投影；真实提取有源阶段 EvaluationResult，新 v2 请求预冻结后可生成源阶段 RunReport，旧记录不补快照 |
| 生成边界 G1 | 只读登记 SSM→完整请求字节／Prompt 指纹／拟议预算；显式离线客户端测试，无真实调用或持久 San 版本 |
| 生成账本 G2 | 独立请求／尝试／收据／离线候选登记，真实 LangGraph、结果不明阻断、收据复用及备份恢复；没有真实模型传输 |
| 传输边界 G3 | Qwen HTTPS 客户端、用量／预算拒绝检查与纯 P1 生成映射已离线验证；未接真实账本／计数器／执行入口，没有真实调用 |
| G3 登记闭环 | 独立计划／原始响应／收据、LangGraph、崩溃／幂等／备份恢复的离线实现；真实模式仍因计数器与批准流程未接入而阻断 |
| 预算与批准 | 文档上下文上界预留、只读预算审查及单计划批准／撤销／一次领取账本；不是精确 tokenizer，默认预算不变，批准未接真实调度 |
| 网页前端 | 新增真实任务提交／状态／分维度结果／源码／截图／热图／候选记录／下载／人工确认；旧页签保留 |
| few-shot／LoRA／追踪 | 默认一个自建开发示例进入真实请求；PEFT 数据／训练／本地推理与 LangSmith SDK 追踪代码已实现，外部资源待补，不冒称实际训练或上传完成 |

旧夹具及 G1—G3 worker 仍禁用远程 tracing；新 `migration-worker` 使用显式配置的摘要追踪和模型适配器，默认开关关闭。开发期间无付费调用或远程上传。旧夹具不执行上传源码，新真实路径仅执行用户声明可信的组件，详见系统指南的安全边界。

## 环境与安装

以下均在仓库根目录执行。已有本轮创建的 `migration_system/.venv` 时不必重新安装。新环境使用 uv，隔离于原 cardmig 环境：

```powershell
uv venv migration_system/.venv
uv --cache-dir migration_system/var/uv-cache pip sync --python migration_system/.venv/Scripts/python.exe --require-hashes migration_system/requirements.lock
```

项目声明 Python ≥3.12，本轮只在 Windows／Python 3.14.7 实测。`requirements.lock` 固定 51 个运行时依赖及分发文件哈希，实际包括 Flask 3.1.3、SQLAlchemy 2.1.8、Alembic 1.20.1、LangGraph 1.2.22、langgraph-checkpoint-sqlite 3.1.3。其他 Python／平台安装后仍需复测，不宣称整个版本矩阵通过。

当前支持仓库 checkout 运行：迁移脚本、配置、依赖锁和旧 P1 源码位于包外，wheel 尚不是脱离仓库的完整部署包。

## 检查与测试

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/check_scaffold.py
& migration_system/.venv/Scripts/python.exe -m unittest discover -s migration_system/tests -v
& migration_system/.venv/Scripts/python.exe -m unittest discover -s tests -p test_migration_contracts_v1.py -v
```

第一条只读检查不创建数据库、不启动服务；`scaffold_verified` 不等于运行就绪。测试仅使用临时数据库和临时产物，不清空用户数据库。

P2a 28＋链路 22＋运维 25＋报告 29＋工作台后端 8＋SSM 离线提取 21＋登记图 26＋源阶段契约投影 19＋SSM 工作台接口 7＋生成边界 G1 18＋G2 登记图 25＋G3 传输／映射 26＋G3 登记闭环 22＋预算／批准 22＝新工程 Python 298 项；另有原 P1 契约 40 项及前端 Node 单元 22 项。本轮均重跑通过，新工程完整回归耗时 444.975 秒。前端代码未变，既有 TypeScript 检查和 Vite 构建已通过（本轮仅重跑前端单元测试，未重新构建）。覆盖后端实际 HTTP／子进程／持久化、引用与恢复、前端输入／请求／幂等控制、真实 AST、独立提取图、预冻结契约、离线生成／传输登记账本、并发幂等、进程退出／收据恢复、增量升级及备份，以及合成 Qwen 协议响应／用量／P1 产物映射、预算审查和本地批准／撤销／并发领取。这些单元／API 结果不是自动浏览器验收、全仓或 30 样本迁移回归。

## 启动开发链路

已增加网页，先从仓库根目录构建静态资源（当前工作区依赖已隔离安装；新环境的安装命令见[前端说明](frontend/README.md)）：

```powershell
npm.cmd --prefix migration_system/frontend run build
```

用户此前已显式完成 0005 并确认原 SSM 保留；本轮新增 0006 批准账本尚未升级实际库，重启新代码前需一次显式升级。先停止本工程 API／worker并保留原数据和已有备份，再运行下面的 init-db，不涉及旧批次。不自动变更运行绑定，旧实现的运行仍需复核，不能直接续跑。当前步骤见 [预算与批准说明](GENERATION_APPROVAL.md#数据库与当前人工确认点)，不重新提取源码或提高模型预算：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py init-db
```

窗口一启动 API；令牌是本地写请求保护，不是模型密钥，不要提交到仓库：

```powershell
$env:CARDMIG_SYSTEM_WRITE_TOKEN = [guid]::NewGuid().ToString('N')
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py serve
```

窗口二启动独立 worker：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py worker
```

只认领一次可加 `--once`，持续 worker 空闲时每秒查询一次。浏览器手动打开 **http://127.0.0.1:8790/**；它与 API 同源，页面令牌来自 API 启动窗口，不是模型密钥。Ctrl+C 停止对应进程。未构建页面时根路径明确返回 frontend_not_built／503，不自动访问外部 CDN 或旧前端。

`GET /health/live` 只说明 API 存活。`GET /health/ready` 核对 schema／实现绑定、已有图数据库及兼容 worker 心跳：开发链路可用返回 200＋`development_ready`，无 worker／过期／不兼容／设施异常返回 503。**两种情况 production_ready 都为 false**，不是迁移或生产放行；心跳健康有最多 30 秒的失联检测窗口。

## 当前 API 子集

写请求需 JSON 和 `X-Cardmig-Token`（与 API 进程环境中的令牌相同）。仅允许配置端口的 loopback Host、同源 Origin，无宽松 CORS。

| 请求 | 当前内容 |
| --- | --- |
| `POST /api/v1/inputs` | `{"filename":"Example.vue","source":"<template><div>source</div></template>"}`；仅单文件，最多 256 KiB |
| `POST /api/v1/tasks` | `{"input_id":"上一步返回的 input_id","name":"开发验证"}` |
| `POST /api/v1/tasks/{task_id}/runs` | `{"profile":"repairable","max_repair_rounds":3}`；额外必需 `Idempotency-Key` 请求头 |
| `GET /api/v1/tasks` | 最多 50 项摘要，尚无正式分页／筛选 |
| `GET /api/v1/runs?limit=10&status=queued&before=...` | 运行分页／状态筛选；按 created_at、run_id 倒序，next_cursor 用于下一页，查询不写入 |
| `GET /api/v1/configurations` | 开发夹具／预算范围，不是开放模型清单 |
| `GET /api/v1/runs/{run_id}` | 分开返回执行状态与评估结论 |
| `GET /api/v1/runs/{run_id}/events?after=0` | 按递增 sequence 轮询，每次最多 200 条，不生成新尝试 |
| `GET /api/v1/runs/{run_id}/report` | 应用记录＋fixture_audit＋contract_projection＋contract_report（严格 P1 未执行投影或 null），见下节 |
| `GET /api/v1/runs/{run_id}/artifact` | 终态接受版本，经归属／哈希核对，下载名 development_fixture.san |
| `GET /api/v1/ssm-extractions/{id}/report`、`artifact` | 独立真实提取账本审计及 SSM JSON 下载，不将原夹具运行标为迁移通过 |
| `POST /api/v1/runs/{run_id}/cancel`、`resume` | JSON `{}`；恢复需相同绑定且无未决尝试 |

`success`、`repairable`、`regression`、`always_fail` 是开发控制夹具，分别演练无需修复、修复后满足、退化回退和预算耗尽。名称不代表真实迁移结果。

## 数据与恢复限制

- 默认配置：[development.toml](configs/development.toml)。只支持 development_stub；配置环境覆盖仅 CARDMIG_SYSTEM_MODE／HOST／PORT。runtime 限定新工程 var 内，artifact 限定仓库 data/experiments/migration_system 内，拒绝旧批次／快照路径。
- 业务 DB：`migration_system/var/business.sqlite3`；图 DB：`migration_system/var/langgraph.sqlite3`。显式初始化／worker 执行才创建，两者分开。
- 初始 9 张业务表之外，0002 增加 worker_health，0003 增加 ssm_extractions／ssm_extraction_files，0004 增加 generation_jobs／generation_attempts／generation_files／generation_candidates，0005 增加 provider_generation_jobs／provider_generation_attempts／provider_generation_files，0006 增加 generation_approvals／generation_approval_files；不改写旧迁移，不是全栈方案全部实体已落地。代码 HEAD 为 0006_generation_approvals，实际库仍为用户已确认的 0005，本轮未自动升级。先停进程再显式 init-db，确认原 SSM 保留，不删库或改版本号绕过检查。
- 文件不可覆盖提交后登记元数据；孤立文件不自动删除，下载再次验证归属／路径／哈希。边界面向可信本地开发，不是恶意代码沙箱或公网认证。
- 单活租约为 60 秒，独立线程每 10 秒记录空闲／运行心跳并续租，节点阻塞时仍执行。失联／失去租约不允许后续节点提交，过期不自动复活；本地 OS 锁覆盖整个图执行，备份和其他 worker 不能并行进入。该锁不面向网络共享盘／多主机。
- 取消不强杀正在返回的操作：仍有所有权时保存已完成收据，再在下一节点停止。真实模型尚未接入，提供方超时／usage／结果不明和外部调用取消仍需其适配器专项验收；续租不是调用超时机制。
- 尝试先登记 started，再提交结果收据。收据已提交而图尚未前进时核对身份／哈希并复用；只有 started、完成情况不明时阻断恢复。这不是跨数据库／模型的恰好一次承诺。
- 运行绑定包实现字节哈希、依赖锁、P1 指纹、输入哈希；代码／锁变化不能静默续跑旧运行。应复核并显式新建运行，不删除绑定绕过保护。
- 依赖包上传、人工意见 API、批次及真实迁移阶段的完整契约报告仍未完成；真实提取账本和 P1 夹具报告保持分开。

## 网页联调状态

前端源码、独立 package-lock、自动化单元测试及真实服务接入已提供；Flask 只提供构建目录 index／assets，没有源目录兜底或任意路径读取。Host／Origin／写令牌检查保持，根 HTML 的 CSP 限制同源脚本与连接，不渲染／执行上传组件。写令牌只存页面内存；刷新清空，URL hash 只含 run ID，读取不重交。

自动浏览器验收受工具限制：内置浏览器主机不可用，本机 Computer Use 又因无法可靠识别 URL 被安全停止；没有绕过或使用额外驱动。临时真实根页 HTTP 200 已核对，临时服务已关闭。随后基础交互／刷新／下载／布局已由用户人工确认，跨页与部分异常恢复仍待人工验证，不称全部 T3 通过；清单及逐项反馈见[前端 README](frontend/README.md)。

2026-11-16 后续人工联调：修正前端 fetch 接收者绑定，新增两项回归测试（前端共 17 项及构建通过）。用户已确认创建后排队、worker 执行结束且符合预期，报告 JSON 和开发夹具均可下载并打开，刷新后原运行及结束状态保留／无重复运行／令牌清空；仅作为用户报告的开发链路确认，不是自动浏览器验收或迁移质量证据，也未独立读取下载内容。退化回退、取消／恢复、分页及窄屏布局仍待确认，T3 尚未全部收口，详见前端 README 的人工反馈记录。

依赖仅安装在新 frontend/node_modules、缓存仅在新工程 var；旧前端、根 Node 依赖和 tests/manual 均不改，未部署远程站点。当前 Vue／Vite／TypeScript 版本、Node 环境及“输入／任务创建暂无全链路幂等保证”的限制均在前端说明中披露。

## 冻结请求与统一报告边界

人工验收补记（2026-11-16）：用户已进一步确认候选退化分支触发回退；上述该项待确认状态已更新。仅确认开发夹具的回退流程，尚不证明真实迁移退化检测；下一项为排队取消，详见前端 README。

新运行入队时自动将 `contract_snapshot` 保存在现有 runs.request JSON 字段中，不新增数据库表、不修改 P1 字段或 0001／0002。快照含严格 MigrationRequest 和开发模式的实际禁用配置描述：没有 Prompt 模板、没有模型 provider、没有质量评估执行器。四类描述按规范 JSON 哈希，外层 request_sha256 再绑定整份请求；不是从历史结果反推的 Prompt／模型配置。

sample_id 使用 `task:<task_id>`，不是论文样本编号；ssm_schema_version 明确为 development_stub_not_extracted。P1 Budget 的模型／规则迁移额度均为 0；应用 max_repair_rounds 仍是独立的 0—3 轮夹具控制预算。调用者仍只提交源码和允许的配置，快照由后端生成。同一幂等请求返回原快照，不重新构造运行。

报告在一个业务事务中读取运行、源码元数据、全部尝试、版本、检查和决定，再核对文件字节哈希、请求／收据身份、父先子后的版本关系、检查归属、比较前后引用、回退版本、终态接受版本和预算停止理由。最终下载也复用该审计，不能把被拒候选当成最终版本。报告轮询不新增尝试、不修改旧记录。

| 字段 | 含义 |
| --- | --- |
| 顶层 status／outcome／final_revision_id | 应用执行状态及夹具终态版本；不等于 P1 的迁移结果 |
| fixture_audit | 完整夹具链校验、实际版本顺序、接受版本、比较检查 ID 和回退版本；明确不是迁移证据 |
| contract_report | 经原 P1 load_contract 往返校验的 RunReport；正常／取消为 not_run，复核为 blocked，设施执行异常为 execution_error；不产生 pass／fail |
| contract_projection | 映射范围和未映射项；缺少旧请求快照时 unavailable、contract_report=null，不补造历史信息 |

P1 没有 development_stub 的产物来源／证据类型，所以夹具版本、检查、修复和候选决定完整留在应用报告，不冒充 generation／rule／model／manual 的真实迁移记录。contract_report 的 revisions／repair_decisions／candidate_decisions 为空，final_revision_id=null；源指纹仍真实核对。

六个质量维度明确 not_run：ssm_extraction、static_validation、san_compile、structure_ted、browser_visual、browser_interaction。此处 evidence_level 仅指拟执行的检查类别，不表示获得证据；无指标、评估器版本、场景覆盖或证据引用。实际模型调用／token 已知为 0，未记录的人工耗时／总耗时保持 null。实际迁移阶段接入后还需单独完成真实记录映射，不得沿用这些夹具记录充当质量结果。

请求／引用不一致返回阻断错误，不返回看似正常的契约报告；当前只支持该受限开发模式。只读查看历史可使用其冻结绑定，不因当前实现变化补造新事实；恢复／执行仍严格检查当前绑定。以前没有快照的运行不会被自动补齐，也不能据此解锁执行。

## 备份、校验与恢复

先停止本工程 API／worker，确保没有运行中任务或未处理租约。若 worker 非正常退出，先按租约复核流程处理，不删除锁表绕过保护。备份只包含两份数据库与数据库登记的输入／所有版本文件，包含被拒候选；不包含孤立文件、环境凭据、依赖缓存。源码本身可能含敏感信息，备份仅保存在本地，不自动上传。

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py backup --backup-id p2b_checkpoint
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py verify-backup --backup-id p2b_checkpoint
```

输出在 `migration_system/var/backups/p2b_checkpoint/`，同名备份存在即拒绝；省略 backup-id 可生成新 ID。使用 SQLite backup API 包含已提交 WAL 页，而不是只复制主数据库文件；备份时 OS 锁阻止图写入，业务短事务排除其他数据库写入。manifest 记录绑定、文件大小及 SHA-256，校验 integrity／外键／schema 和登记文件集合。限 10000 个文件、总计 256 MiB，面向当前开发链路。

恢复示例配置：[restore-example.toml](configs/restore-example.toml)。它指向全新 `var/restored-example` 和独立产物子目录，端口 8791；**恢复前不要运行 init-db**：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py restore --backup-id p2b_checkpoint --config configs/restore-example.toml
```

现有目标目录即使为空也拒绝覆盖。恢复前验证完整备份及当前实现／依赖／P1 绑定；保留业务事实、checkpoint、全部版本／候选，旧 worker 在线状态重置为 stopped，必须显式重新启动。之后 serve／worker 均使用相同 `--config configs/restore-example.toml`。原目录仍保留，恢复实例只用于验证／后续显式接管，不要同时消费两份克隆队列，尤其未来存在付费模型时。

备份失败保留 `.incomplete`，恢复中断保留新目标的 `.restore-in-progress` 并拒绝启动／初始化／覆盖重试。需要人工复核部分目录，再另选全新目标；程序不自动删除证据。当前不支持跨 schema／跨实现转换恢复。哈希校验用于本地完整性，不是对恶意备份的身份认证或加密。

## P1 契约接入

`contracts.load_p1_contracts(repository_root)` 先核对包内 `adapters/p1_contracts_pin.json` 固定的三个源文本指纹，再在私有 namespace 加载精确核对的文本。不执行旧 migration_pipeline/__init__.py 或完整 orchestrator，不复制第二套定义。

UTF-8 指纹只规范 CRLF／CR 为 LF，缓存不能跳过漂移核对。不同 namespace 的 Python 类身份不相同，边界通过 v1 JSON 交换。应用执行状态／夹具报告不能伪装为符合完整 P1 契约的迁移成功报告。

## 接下来

真实 SSM 登记图已提供：见 [提取说明](SSM_EXTRACTION.md)。升级 0003 后用 `extract-ssm-graph --run-id ...`（或 input-id）运行 prepare_source／extract_ssm／register_report 独立节点，登记请求／SSM／收据，纳入备份，并可用 `ssm-extraction-report` 审计、`resume-ssm-extraction` 受限恢复。原 `extract-ssm` 仍是辅助离线探测，其 var 目录不自动导入或备份。新 v2 请求预冻结 P1 快照并提供源阶段报告，旧 v1 请求仅作源评估、不补写历史请求；整体迁移未执行，网页夹具的六项 not_run 不改变。

最新人工验收进展：用户已确认创建／排队／执行、下载、刷新保持且令牌清空、退化回退、排队取消及 worker 重启保护、状态筛选和窄屏布局正常。本轮基础人工联调已完成；跨页、异常断连、在途取消／受限恢复未人工验证，不能称全部 T3 或生产验收通过。详细逐项状态以 frontend/README.md 为准。

用户已完成 0003 升级和 DeliveryPhaseCard 真实登记图提取；助手核对文件哈希／归属、5 个独立 checkpoint，并已只读映射为 P1 源评估，未重复提取或补写原请求。工作台现可只读查看真实提取记录、源评估／契约范围、文件指纹，并下载报告与 SSM。用户已确认新面板的提取状态／迁移未执行、历史快照提示及两份 JSON 下载打开通过；这是用户人工确认，不是自动浏览器证据或整体迁移通过。具体边界见 [前端说明](frontend/README.md#真实-ssm-只读面板2026-11-16)。下一步接真实生成适配，先冻结输入／SSM／Prompt／模型配置和预算、实现客户端边界及产物登记的离线测试，再单独确认真实模型调用；后续继续接完整评估／修复图、LangSmith、few-shot 和 LoRA。追踪上传及研究实验另行确认范围与预算。本轮仅更新验收文档，无新数据库迁移或提取，未修改旧实验、Vue／San、生产 Prompt／规则，未 commit／push。

### G1 实施回顾（后续 G2 已实施，见下节）

已实现 [G1 请求边界与只读预览](GENERATION.md)：保留旧 Prompt 规则，通过两个固定源指纹只加载纯构造函数，核对实际源／SSM 后封装完整请求、消息、模型／预算和实现指纹；注入离线客户端检验响应／失败，不执行网络或生成代码。`generation-preview --extraction-id ... --provider qwen --model qwen-plus` 只输出指纹与参数，不生成持久记录或产物。当时已对实际 DeliveryPhaseCard 只读运行，重复结果一致，数据库逻辑行未变化；G1 当时不需升级，后续 G2 的 0004 升级要求见下节。

G1 当时未完成持久收据／版本和图节点，这些离线能力已由 G2 补充；真实模型传输、token 预检和提供方超时仍未接入。G1 未修改旧流水线、Prompt 内容、依赖、已有实验或数据库 schema；G2 的新增迁移不得与其历史描述混淆。

新增 18 项 G1 测试；完整新工程 203 项、原 P1 40 项和前端 Node 22 项通过。当前只读 check 可显示 san_generation=read_only_request_preview_and_offline_client_boundary_only，不把预览描述为可执行生产生成。

### G2：离线账本／图恢复已实现，实际升级已确认

见 [G2 说明](GENERATION_LEDGER.md)。新增四张独立表及 0004 迁移，冻结完整请求和幂等键；客户端调用前登记开始，已提交收据跨 checkpoint 复用，不明结果转复核而不再调用。离线候选不能冒充 P1 真实生成版本。备份纳入完整账本／登记文件／图，恢复后复用收据。没有模型密钥或网络客户端、没有网页执行开关，没有修改旧 Prompt、依赖或冻结实验。

2026-11-16 用户确认“SSM能下载查看”；助手随后只读核对实际库为 0004_generation_ledger、四张生成表存在，原 DeliveryPhaseCard 提取仍 completed，请求指纹及请求／收据／SSM 三文件指纹与升级前记录相同。实际升级由用户执行，不是助手自动变更；无需重复 init-db 或重新提取。本次仅确认 schema 与该原提取证据保留，不扩大为所有业务行不变、实际备份恢复或真实生成验收。下一步 G3 接真实客户端、实际用量／预算策略及产物 P1 映射，先离线验证传输边界，再单独确认真实模型调用。

G2 新增 25 项测试；新工程完整 228 项、原 P1 40 项及前端 Node 22 项通过。检查命令的生成能力标记现为 registered_offline_graph_available_no_real_model_transport，不表示真实模型生成已接入。

### G3 第一增量：传输与映射边界离线验证

详见 [G3 说明](REMOTE_GENERATION.md)。新增 Qwen HTTPS 客户端代码，默认禁网，不读取密钥环境变量、不重试、不继承代理或跟随重定向；精确绑定 G1 消息和模型配置。缺少可信输入 token 上界时阻断发送，响应异常仍保留已知用量，不把未知成本记为零。纯映射函数核对完整证据后可构造 P1 generation 版本，但没有接入真实登记服务；合成响应测试不是实际生成证据。

G2 仍拒绝该真实客户端，现有离线候选 contract_revision=null。客户端许可声明不是持久授权证明，本地防重复集合不是跨进程保证；可信计数器、真实调用账本、批准入口及恢复／备份集成仍须完成。没有新增 CLI 执行开关、网页入口、数据库迁移、模型调用或追踪上传，本轮无需 init-db、重新提取或进行网页验收。

本轮只读复核实际库仍为 0004；原提取 completed、请求指纹及三个证据文件哈希未变，原夹具运行仍 finished／not_run。下一步补完 G3 的真实账本与可信计数策略、先持久登记再调用及未决结果恢复保护，离线验证后才单独确认一次真实模型联调。LangSmith、目标评估／修复、few-shot 和 LoRA 仍为后续必做。

验证结果：新增 26 项专项测试通过；完整新工程 254 项（224.444 秒）、原 P1 40 项、前端 Node 22 项均通过。check_scaffold 只读检查通过，qwen_transport 明确标记为仅离线验证、未接账本／真实入口。未安装新依赖、未运行真实模型、未改旧 Prompt／规则或历史实验，未 commit／push。

### 当前 G3 登记增量：原始交换的持久化、图恢复与备份

详见 [登记闭环说明](RECORDED_GENERATION.md)。新增独立 0005 三表，冻结完整传输计划；先提交开始尝试，再进入离线替身，原始响应／用量和收据先登记，后续节点再核对实现绑定并归档。独立 LangGraph 与备份恢复均接入；已登记收据在 checkpoint 间隙复用，未登记的孤立文件不自动导入，不明结果不重发。

该增量仅允许 offline_transport_test，拒绝真实客户端和 provider_https；合成计数不能开启网络。模型调用保持 0，contract_revision=null，整体质量 not_run。可信真实计数／上界策略、批准流程、HTTPS 实际登记及真实证据映射仍未完成，不能把本步离线闭环说成真实生成已可用。LangSmith、few-shot、LoRA 和目标评估／修复仍按开题路线继续。

实现回合结束时只读核对实际库仍 0004、没有 provider_generation_* 表，原提取 completed 且请求／收据／SSM 指纹保留；当时未自动升级，停在用户显式升级确认点。后续用户确认与最新实际库状态见下段，不将历史检查回写为已提前升级。

验证结果：新增专项 22 项通过；完整新工程 276 项（399.565 秒）、原 P1 40 项、前端 Node 22 项重跑通过，check_scaffold 只读检查和 git diff --check 通过。本轮未读模型密钥、安装依赖、运行模型／训练、上传追踪、改旧实验或 commit／push；临时库升级和恢复测试不是实际库升级／备份恢复的人工验收。

后续确认（2026-11-16）：用户确认显式升级及原 SSM 查看／下载；助手只读核对实际 schema 为 0005_provider_generation、三张新表存在，原 DeliveryPhaseCard 提取仍 completed、原请求指纹及三个文件哈希未变，原夹具运行仍 finished／not_run。该升级确认点已完成，无需重复初始化或提取；不扩大为真实生成、实际备份恢复或生产验收通过。本确认回合只更新文档，未重新运行完整测试、调用模型或写运行数据。下一步实现可信 token 计数／上界策略与批准流程，真实调用仍须另行确认。

### 当前预算／批准增量（0006，未自动升级实际库）

见 [预算与单次批准](GENERATION_APPROVAL.md)。基于已复核模型文档推导成功纯文本请求的条件性上界，预留整个上下文窗口作输入额度，不冒充精确计数。默认总预算仍是 32,768；保守策略需要的输入＋默认输出预留为 1,008,192，因此默认继续阻断，没有自动扩大预算、创建或批准实际调用。

新增独立批准／动作文件表和只读预算审查 CLI。批准绑定完整请求指纹、模型／端点／预算／策略、有效期和一次名额；错请求、过期、撤销、并发重复领取及实现漂移阻断，备份恢复保留已领取名额。领取返回 ClaimedApproval，不是传输开始证明或可发送许可；真实 HTTPS／原始响应账本集成仍待后续，原图继续拒绝真实模式。

当前停在用户显式升级 0006 并确认原 SSM 保留的确认点，命令见上面的启动说明。本轮没有读取密钥、发送模型请求、上传追踪、安装依赖或自动改实际数据库；旧 Prompt／规则、Vue／San、历史实验及 tests/manual 不变，未 commit／push。

验证：新增 22 项专项测试通过（71.450 秒）；完整新工程 298 项（444.975 秒）、原 P1 40 项、前端 Node 22 项及 check_scaffold／git diff --check 均通过。只读核对实际库仍 0005、尚无审批表，原提取 completed、请求指纹及三个文件哈希未变；未创建或批准实际调用记录。
