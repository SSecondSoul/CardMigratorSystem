# G3 登记闭环：原始响应、断点与备份（离线验收）

日期：2026-11-16。本增量把[传输边界](REMOTE_GENERATION.md)的计划与响应检查接入独立持久账本和 LangGraph。**执行仍仅限显式离线传输替身；真实 token 计数器和批准入口尚未接入，provider_https 模式明确阻断。** 不是已经完成真实模型生成或迁移质量验证。

后续[预算／批准增量](GENERATION_APPROVAL.md)已增加条件性文档上界策略与独立本地批准账本，但未接实际传输调度，原图仍拒绝真实模式。该增量新增 0006，实际库仍是下文用户已确认的 0005；当前升级要求以链接文档为准，下文“无需重复 init-db”只针对当时完成的 0005 确认，不覆盖后续迁移。

## 新增内容

- 显式 Alembic `0005_provider_generation`，只增加 provider_generation_jobs／provider_generation_attempts／provider_generation_files 三表，不改写 0001—0004。与 G2 离线候选表、夹具及 SSM 提取记录隔离。
- 完整冻结来源、G1 请求和 messages、Prompt／实现指纹、模型／预算、端点、绑定当前模型与消息的 token 上界描述及计划指纹。保留 G1 禁止外部调用语义。相同提取＋幂等键复用原请求，参数改变则冲突。
- 先提交 started，再进入传输替身。单项只有一次名额；异常／超时不退还名额，不自动换键或重试。没有实际模型调用，不把测试传输次数当作模型调用次数。
- 保存实际收到的响应字节、HTTP 状态、规范化检查结果、实际报告的 usage 及可接受候选。响应捕获上限为 4 MiB＋1 字节，超过 4 MiB 拒绝，不声称超限时保存了完整响应。文件不可覆盖，文件引用与收据在同一业务事务登记。截断／超额／无效输出仍保存可解析的已知 usage，不回填为零。
- 返回后即使发现实现漂移，也先登记已经收到的响应／用量，再在后续节点阻断。历史报告可核对冻结证据；继续执行另核对当前来源／Prompt／实现绑定。
- 独立真实 LangGraph：prepare_transport → record_exchange → register_result；thread 为 provider-generation:<id>，同步 SQLite checkpoint。沿用本地 OS 执行锁，互斥其他图、迁移和备份；显式关闭 LangSmith tracing。
- 备份清单包含新登记文件和三表。复制后的业务库／文件再次审计；未决 started 阻止备份，显式复核后保留未知事实。恢复到全新目录后复用已登记响应，不再次进入传输替身。

### 各状态的含义

| 状态 | 可否重新进入传输 |
| --- | --- |
| prepared、无 attempt | 同一绑定可首次进入；仍只允许离线替身 |
| started、无已登记收据 | 进程退出或结果不明，需复核，禁止重发 |
| received、已登记收据 | 仅复核与归档既有响应，不再调用 |
| review_required、已知收据 | 保留 usage／响应；绑定允许时可继续归档，不重发 |
| review_required、无收据 | 保留预留名额，传输次数未知，不重发 |
| completed／blocked | 已知结论复用，不重复执行；completed 仅指离线结果登记 |

文件落盘与数据库提交不是跨系统原子事务。若收据文件已写、数据库尚未提交就退出，该文件是孤立证据，保留但不自动导入；账本仍视为未决，不据此重新发送。数据库收据已提交而 checkpoint 尚未前进时，则复用登记收据。这是避免自动重复的恢复策略，**不是提供方恰好一次或成本绝对可控保证**。

## 计数与证据边界

目前执行仅接受 RecordedOfflineTransport；QwenHTTPSClient 或普通对象在开始尝试前被拒绝。创建 provider_https 请求直接返回 provider_live_counter_and_approval_not_integrated；不能通过设布尔值、提供模型密钥或合成计数器开启真实调用。

离线请求也校验 token 上界与输出额度，但测试计数器是合成数据，只验证协议与拒绝逻辑，不证明真实请求 token 数。可信计数器／上界策略和批准范围仍是下一步未完成工作。

request.json 中的严格 P1 请求形状是待传输契约模板，其外层 plan.json 与收据明确标记 offline_transport_test／external_calls_permitted=false。离线结果的 actual_model_calls=0、contract_revision=null、migration_quality_status=not_run、production_ready=false。不调用真实产物映射函数将其变成 P1 generation。原 G2 候选也不升级或追认为真实模型产物。

超时或 HTTP／usage 不明时，usage 保留 null，状态需复核；不推断零计费。原始响应可能含生成代码或提供方错误正文，仅作为本地登记证据，不自动上传、展示到网页或写进普通日志。报告仍不代表 San 编译、语义、DOM、像素或交互已验证。

## 当前入口与实际库

应用 API：ProviderGenerationService.create／report／invoke／finish／review；图入口 execute_recorded_generation。只在临时测试中显式注入离线传输。没有新增网页、CLI 模型执行开关，也没有默认网络客户端，不读取环境中的模型密钥。

**当前代码 HEAD 与用户实际库均为 0005_provider_generation，用户显式升级及原 SSM 查看／下载已确认。** 无需重复 init-db 或重新提取。新环境／仍为旧 schema 的环境在启动 API／worker 或基于 Service 的命令前，仍须先显式升级，否则返回 database_schema_mismatch。旧实现绑定的运行不自动解锁续跑，不删除数据库、改版本号或删锁绕过保护。

以下保留此次已完成的人工升级步骤，供新环境复现；当前用户库不需重复执行：

1. 在原窗口 Ctrl+C 停止新系统 API 和 worker，保留原数据及已有备份。旧 schema／旧实现的备份不由新工具自动转换，不改 manifest 绕过检查。
2. 显式升级并重新启动 API（不会调用模型）：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py init-db
# 新窗口没有本地写令牌时执行；不是模型密钥，不需要发给助手。
$env:CARDMIG_SYSTEM_WRITE_TOKEN = [guid]::NewGuid().ToString('N')
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py serve
```

3. 刷新 http://127.0.0.1:8790/，确认原 DeliveryPhaseCard 提取仍能查看，报告和 SSM JSON 仍能下载打开。API 启动需本地写令牌；只读查看无需在网页填写令牌或启动 worker。不要重跑 extract-ssm-graph。

后续人工确认（2026-11-16）：用户回复“已确认”，对应上述显式升级和原 DeliveryPhaseCard 报告／SSM 查看、下载确认。助手随后只读核对实际 schema 已是 0005_provider_generation，三张 provider_generation_* 表存在；原提取仍 completed，请求指纹及请求／收据／SSM 文件哈希与原记录一致，原夹具运行仍 finished／not_run。实际升级由用户执行，不是助手自动升级或临时库测试替代。本项不扩大为实际生成、全部业务行不变、备份恢复或生产验收通过；助手未另行采集浏览器下载证据。

## 验证

专项测试：

```powershell
& migration_system/.venv/Scripts/python.exe -m unittest discover -s migration_system/tests -p test_provider_generation_ledger.py -v
```

新增 22 项，覆盖预冻结／幂等冲突、输入计数门禁、拒绝真实客户端／真实模式、started 提交顺序、真实图中断／进程退出、超时／未知 usage 不重发、截断／超额保留用量、实现漂移、重新计算哈希后的类型／归属／候选错误、文件与数据库提交间隙、备份恢复、锁互斥、禁止环境启用 tracing，以及临时库 0004→0005 保留原 SSM 和 G2 报告。

新增专项 22 项通过（115.753 秒）；完整新工程 Python 276 项通过（399.565 秒），原 P1 契约 40 项、前端 Node 22 项重跑通过。check_scaffold 只读检查及 git diff --check 通过。前端代码未改，本轮未重新构建／浏览器验收。全部为临时数据库、测试文件与合成响应；不等于正式迁移实验或真实模型联调。

升级前只读复核记录：当时 schema 是 0004_generation_ledger，尚无 provider_generation_* 表；原提取 5fe54b4c976241ddbe29fde9a331535d 为 completed，请求指纹为 8b55e3d84f9698f93ad98484df3b17ca9830036a221f2b0cabcc764a59c3d88f，请求／收据／SSM 文件哈希与 SSM_EXTRACTION.md 原记录一致。升级后的最新确认见上节，旧记录保留，不回写成已提前完成升级。

本次确认回合仅只读核对并更新文档，没有新迁移执行、提取、模型调用、密钥读取、追踪上传或 commit／push；未修改运行数据和旧实验。未重新跑完整测试，前述 276／40／22 是实现回合的测试结果，不新增测试通过数量。

## 后续未完成

先实现可核查的 token 计数／上界策略与受控批准流程，再将真实 HTTPS 返回的原始交换接到该登记协议，完成真实证据版本映射与对应故障测试。真正开启模型前仍要单独明确提供方／模型／预算并获得一次受限调用确认；不借本轮离线账本隐式放行。之后继续真实评估／修复、LangSmith、few-shot 与 LoRA，保持开题路线和现有输入范围。
