# G2：离线生成登记、断点恢复与备份

日期：2026-11-16。范围为新系统的独立离线账本和真实 LangGraph 持久编排；**没有真实模型传输、付费调用或迁移质量通过结论**。旧流水线、生产 Prompt／规则、Vue／San、历史实验不修改。

最新增量为[条件性预算上界与本地批准](GENERATION_APPROVAL.md)，代码新增 0006，实际库仍是已确认的 0005、未自动升级。当前停机升级要求以该文档为准。下文的 0004／0005 确认均为历史阶段事实，不覆盖后续迁移；G2 离线候选与新批准记录始终分开，不因此放开模型调用。

后续 [G3 传输／映射边界](REMOTE_GENERATION.md) 已增加独立客户端代码及离线测试，但尚未接入本账本；下文 G2 仍仅接受离线客户端，不能据此改为真实模型执行。

后续新增 [G3 原始响应登记协议](RECORDED_GENERATION.md)及 0005 显式迁移，与本 G2 表／候选隔离。用户现已显式完成 0005 升级并确认原 SSM 查看／下载，助手只读核对新表及原证据保留，无需重复初始化或提取。新环境／旧 schema 的升级要求以该文档为准；下文 0004 为 G2 当时的历史状态，不能据此推断当前库版本或放开真实模型调用。

## 与 G1 的区别

[G1](GENERATION.md) 把完整请求封装为不可变内存字节，只有只读预览。G2 在调用前将完整 G1 模板放入新登记协议 `registered-offline-generation-g2-v1`，保存请求／指纹／幂等键和来源，不追认以前未冻结的调用。

外层 G2 的 persistent_registration=true 表示本次确实登记到数据库／文件。内层 prepared 的 persistent_registration=false 保留 G1 模板原语义，不篡改为真实模型授权。两层 external_calls_permitted 都是 false。当前候选只能是 offline_client_test，不能写成 P1 generation、model、rule 或人工修复版本；contract_revision=null，整体质量 not_run。

## 独立表与图

新增 Alembic `0004_generation_ledger`，不改写 0001—0003：

| 表 | 用途与保护 |
| --- | --- |
| generation_jobs | 冻结完整请求、来源提取／输入、状态及停止原因；extraction_id＋idempotency_key 唯一 |
| generation_attempts | 每项最多一次登记尝试；调用前提交 started，结果不明保留复核，不重新分配名额 |
| generation_files | 请求、收据、候选文件路径／SHA-256；每种文件只登记一次，不覆盖原文件 |
| generation_candidates | 离线候选版本；无父版本，归属同一请求，source_kind 固定 offline_client_test |

独立真实 LangGraph 为 `prepare_generation → invoke_offline_client → register_candidate`，thread ID 为 `generation:<id>`，沿用独立图 SQLite 和同步 checkpoint。全程持有同一本地 OS 执行锁，排除另一生成／提取图、迁移和备份。当前由 Python API 显式注入可信 OfflineGenerationClient 执行，只有测试使用，不提供网页“执行模型”或 CLI 假模型选择器，不接旧 development_stub 队列。

## 调用与恢复

- prepared：完整请求已经登记，尚无调用尝试。中断后同一绑定可继续。
- started：在进入客户端前提交。进程退出或客户端异常而没有已登记收据时，转 review_required；不能从候选／收据孤立文件猜测完成，也不自动再调用。
- received：收据和候选先不可覆盖落盘，再以单个业务事务登记引用与候选／尝试状态。checkpoint 间隙恢复复用已提交收据，不调用客户端第二次。
- completed／blocked：最后节点重新核对所有引用、字节和响应形状／已报告预算。完成仅指离线候选登记；截断／无效输出记阻断收据，没有可下载候选。
- review_required：保留不明结果、已预留的一次名额及错误码。只有已登记并核对的收据可继续归档；没有收据时仍阻断。实现或来源／Prompt 漂移不放行调用。

幂等键相同、请求相同返回原记录；相同键换模型／预算／实现等返回冲突。新键表示显式创建新请求，不自动继承以前正确候选。当前没有修复图，候选 parent_id 必须为空；未来修复必须引用真正的接受版本，不能把重新生成当成原版本修复。

真实模型调用确定为 0。offline_client_invocations 仅在收到可靠收据后为 1；只有 started 而没有收据时为 null，不伪称客户端一定调用或一定没调用。generation_slots_reserved 仍为 1，结果不明不能借此重试。缺少 usage 保持 null／usage_unknown，当前不能证明真实付费 token 总额事前可控；真实传输／输入计数／提供方超时和实际计费联调仍待后续。

## 报告、下载与备份

`GenerationService.report` 在单个业务快照中读取请求／尝试／文件／候选，再核对已登记源 SSM 报告及其精确引用。核对所有字节指纹、归属、幂等键、请求指纹、候选身份、单次尝试、收据状态和预算／输出形状；只读审计不调用客户端、不重新生成或提取。历史报告可读冻结绑定；执行／恢复另核对当前实现、Prompt 和源引用。

GET `/api/v1/generations/<id>/report` 读取应用报告；`/artifact` 仅在 completed 后下载，文件名为 `offline_generation_<id>.san`，明确不是已验收的真实迁移产物。沿用 Host／Origin 保护，没有新增网页写接口。不执行候选里的脚本，不以 SFC 文本形状替代 San 编译、语义、视觉或交互检查。

备份包含四张新表、全部已登记请求／收据／候选及对应图库。校验和恢复不仅核对文件清单／哈希，还调用源提取和生成报告审计。未决 started 阻止备份；停止执行并登记复核后可保存不明事实。恢复仅到全新目录，received 收据可继续，不重复调用。孤立文件不自动导入，原文件和旧备份不覆盖。仍只支持同 schema／实现的备份恢复，不提供跨版本自动转换。

## 用户实际库升级点

助手仅在临时数据库验证 0003→0004 保留原运行／SSM 报告；没有升级实际库。只读核对实际库仍为 0003_ssm_extractions、没有 generation_* 表；原 DeliveryPhaseCard 提取仍 completed，请求、SSM、收据指纹与既有记录相同。

后续用户验收（2026-11-16）：用户执行升级步骤后确认“SSM能下载查看”。助手再次只读核对实际库已为 0004_generation_ledger，四张生成表存在；原提取 `5fe54b4c976241ddbe29fde9a331535d` 仍 completed，请求指纹 `8b55e3d84f9698f93ad98484df3b17ca9830036a221f2b0cabcc764a59c3d88f` 未变，请求／收据／SSM 字节指纹仍为 SSM_EXTRACTION.md 中的原值。实际升级由用户显式完成，无需再次初始化或提取。本项只确认 schema 和该原提取证据保留，不据此宣称全部业务行未变、实际备份恢复或新生成图人工验收通过。

新代码的 schema HEAD 为 0004，用户现已完成升级。以下命令仅供新环境／仍为旧 schema 的环境复现；已有 0004 无需重复执行。旧 schema 在重启新 API／worker、运行预览或备份前需要先显式升级，否则会报 database_schema_mismatch，不能删库或跳过校验。升级时先在各窗口 Ctrl+C 停止新系统 API 和 worker，再于仓库根目录执行：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py init-db
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py serve
```

原 API 窗口的本地写令牌仍在时直接使用；新 PowerShell 窗口先自行生成 `$env:CARDMIG_SYSTEM_WRITE_TOKEN = [guid]::NewGuid().ToString('N')`，不用发送给助手。只读查看 SSM 不需 worker 或页面令牌。已有提取无需复跑，不需要模型密钥。升级后确认原 SSM 可查看／下载，再继续下一增量。

## 可用 CLI（不要求本次执行）

只读 `generation-preview` 继续保留。新增 `prepare-generation` 是明确的本地登记写操作，不调用模型；相同键不得用于不同请求：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py prepare-generation `
  --extraction-id 5fe54b4c976241ddbe29fde9a331535d `
  --idempotency-key delivery-g2-local-001 `
  --provider qwen --model qwen-plus

& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py generation-report `
  --generation-id "替换为返回的32位ID"
```

provider／model 目前只是拟议参数，**不是调用真实 Qwen 的开关**。prepare 不提交主运行队列，也不会自动生成代码；没有 `--execute` 命令。测试客户端执行与恢复只在临时环境的专项／全量测试中验证，未对用户库创建演示候选。

## 验证结果

新增 25 项专项测试；全量新工程 228 项 Python 测试通过（396.885 秒），原 P1 契约 40 项、前端 Node 22 项通过。包括真实子进程在调用开始后退出、未知结果不重试、并发相同幂等键、已提交收据／checkpoint 间隙复用、实现漂移、截断和预算阻断、缺少 usage、损坏／跨归属证据、API 只读下载、LangSmith 环境不启用上传、备份恢复后复用收据，以及 0003→0004 保留原报告。测试使用临时库／产物；原提取器和 Prompt 来源只读，不改用户实际库。

这些是离线工程与恢复证据，不是模型生成或迁移正确率实验。用户实际升级后的原 SSM 读取／下载现已确认，详见上面的人工反馈及只读核对；新生成图、备份恢复仍仅由临时环境测试支持。本次确认回合仅更新文档，未安装依赖、运行真实模型、上传追踪、执行训练、修改旧实验或 commit／push。

## 后续

用户显式升级及原 SSM 证据保留确认已完成。下一步 G3 开发真实客户端与实际预算／用量策略、真实产物 P1 映射，先用离线传输替身测试，再单独确认真实调用的提供方／模型／预算。之后接真实目标评估／修复、LangSmith、few-shot 与 LoRA。不得把本次离线 candidate／receipt 的成功当作迁移正确率或正式实验成绩。
