# 真实 SSM 提取：离线适配与登记图 v1

日期：2026-11-16。范围：新系统适配层、独立 CLI、登记数据库／备份、独立真实提取图及测试。不是完整迁移、全语法覆盖或论文正确率结果；网页主运行图仍是 development_stub。

当前代码新增 **0006_generation_approvals**；实际库仍为此前用户已确认的 0005，本轮没有自动升级，原提取及三个证据文件指纹已只读核对保留。重启新代码前需先停 API／worker，显式 init-db 后确认原 SSM 查看／下载，不重新提取。当前步骤见[预算／批准说明](GENERATION_APPROVAL.md#数据库与当前人工确认点)。[0005 已确认记录](RECORDED_GENERATION.md#当前入口与实际库)和下文 0003 为历史阶段事实，不意味着 0006 已执行或真实迁移已完成。

## 最新增量：登记数据库与真实提取图

已增加 `0003_ssm_extractions`：`ssm_extractions` 保存请求／状态／来源，`ssm_extraction_files` 登记请求、SSM 和完成／阻断收据的路径及 SHA-256。不修改冻结的 0001／0002，不将 SSM 填入原 San 版本表，不改变原夹具报告。旧 var 离线探测目录也不会自动导入或改写。

新增独立 LangGraph `prepare_source → extract_ssm → register_report`。沿用单独的图 SQLite 库，以 `ssm:<extraction_id>` 为 thread ID，与原运行隔离；全过程持有现有本地执行锁，与其他图执行、迁移和备份互斥。它由明确 CLI 同步执行，**尚不是网页可提交的生产迁移队列**，不声称接入完整生成／校验／修复图。

### 升级与执行登记图

实现阶段先在临时库验证，未自动升级用户正在使用的数据库；随后用户已显式升级到 0003 并完成一次登记图提取，实测记录见下文。以下保留新环境／复现命令，重复执行提取会新建记录；已有结果无需再次提取。升级前先用 Ctrl+C 停止新系统 API 和 worker，再于仓库根目录执行：

```powershell
# 增量创建两张新表；不是删库重建。
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py init-db
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py extract-ssm-graph --run-id b0f6b858240b431fa486d791bf6e03c4
```

也可将 run-id 换为 `--input-id "已有32位输入ID"`。API／worker 不需为 CLI 提取而启动；也不需令牌或模型密钥。继续用网页时应显式重启两个进程。旧历史结果只读保留，不绕过绑定续跑旧任务。不用删除数据库／checkpoint／原证据，旧备份保持原样；本系统尚不支持将旧 schema 的备份自动转换为新 schema。

新登记文件位于配置 artifact_dir 下 `ssm-extractions/<extraction_id>/`，默认 `data/experiments/migration_system/ssm-extractions/`。源码沿用原已登记输入，不重复冒充为生成产物。打印的 status=completed 只代表真实 SSM 提取完成，迁移质量仍 not_run、模型调用 0。

只读审计：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py ssm-extraction-report --extraction-id "替换为新提取ID"
```

API 启动后也可 GET `/api/v1/ssm-extractions/<id>/report`，以及 `/artifact` 下载 SSM JSON；保留原 Host／Origin 边界，不增加无需令牌的写接口。网页已有独立只读列表／详情／下载面板，原夹具六项 not_run 不回填成通过。

### 恢复与备份

- 提取前持久登记 started，完成收据和 SSM 先不可覆盖落盘，再登记文件引用与 received；最后图节点核对引用并标记 completed／blocked。
- 只有已登记收据能被自动复用。收据提交而图 checkpoint 尚未推进时，恢复不会重复调用提取器。prepared 尚未启动可继续；只有 started、没有已登记收据的情况进入 review_required，不从孤立文件猜测完成、不自动再提取。
- `resume-ssm-extraction --extraction-id "已有ID"` 只针对同一冻结请求／当前绑定。实现、提取器或锁变更会阻断执行；历史报告仍可只读核对，不补造新事实。已结束记录复用结果，不重新提取。
- backup／verify-backup／restore 纳入两张新表、全部已登记 SSM 请求／输出／阻断收据和同一图库 checkpoint，校验文件集合、来源与收据归属。prepared／received 的受控中断可在静止状态备份并恢复；未决 started 必须先复核。执行中由 OS 锁阻止备份，仍需停止其他 worker。
- **旧命令 `extract-ssm` 的 var 离线目录仍不属于注册集合，不自动纳入备份。** 两种路径必须区分。孤立文件不自动补登记、不删除。
- 尚未映射为完整 P1 RunReport，未添加真实 San 版本、模型调用、浏览器评估或正则降级模式；本步不是正式实验。

### 源阶段统一契约映射（后续增量）

现已增加 reporting/extraction_projection.py，既有 report API／ssm-extraction-report CLI 同时返回 contract_evaluation、contract_projection 和 contract_report。SSM 证据已核对只意味着源阶段产物提取检查 pass／static，没有 San revision；整体迁移仍为 not_run，其他五项检查未执行，不表示语义等价／覆盖率已达标。

- 新 registered-ssm-graph-v2 请求在创建时冻结 P1 MigrationRequest 和零模型／禁用 Prompt／源阶段评估策略快照，保存于原 request JSON。可输出严格 v1 RunReport 的源阶段投影，但不是完整迁移通过报告。无需新的数据库迁移。
- 已存在的 registered-ssm-graph-v1 请求没有预冻结快照：保留原字节，仅提供有证据引用的源 EvaluationResult，contract_report=null，projection=partial_evaluation_only。不补写快照，不要求为填满报告而复跑。
- 源语法、未支持结构、设施和证据错误分别归类；未识别错误保持 unknown／blocking。均不授权修改 Vue 或调用目标修复。执行复核仍阻断整体结论，即使已存在可信源输出。
- pass 的 evaluator_version 为 ssm-source-evidence-v1，环境指纹来自实际运行时／依赖／解释器；引用索引绑定源文件及登记请求／SSM／收据。未测覆盖率和人工／耗时不补值，SSM 也不进入 San 的版本链。
- 新快照缺失／类型或策略漂移、证据不完整时阻断；报告只读且保留冻结绑定，备份校验也复用同一审计。原夹具报告维持原状。完整字段口径见[统一数据契约第 8 节](../docs/architecture/统一数据契约_v1.md)。

本次对实际提取 `5fe54b4c976241ddbe29fde9a331535d` 只读验证：新增 contract_evaluation 为 ssm_extraction／pass／static，带 4 个已核对的文件引用和 evaluator_version=ssm-source-evidence-v1；由于原协议 v1 没有预冻结快照，contract_report=null，projection=partial_evaluation_only。读取前后数据库提取快照一致，请求指纹仍为 `8b55e3d84f9698f93ad98484df3b17ca9830036a221f2b0cabcc764a59c3d88f`；原夹具报告仍 not_run。没有重新提取或写入用户记录。

新增投影测试 19 项；新系统完整回归 178 项（182.309 秒）、原 P1 40 项、前端 Node 17 项均通过。覆盖预冻结发生在解析前、P1 往返校验、不同错误来源、类型／路径／策略漂移、证据缺失、源 pass 不等于迁移 pass、历史无回填及只读单快照。原 P1 三个固定源指纹不变，无依赖更新／数据库迁移／模型调用／追踪上传。本步无需重跑现有提取或再执行 init-db；后续运行新 API／worker 时重启以加载新代码。

登记图新增 26 项测试；最终新工程 159 项 Python 测试在 149.413 秒内通过，原 P1 40 项及前端 Node 17 项亦通过。覆盖真实节点／命名空间、收据提交与 checkpoint 间隙恢复、未决结果禁止重跑、实现漂移后复核和备份、来源／文件／类型／终态损坏、升级保留原报告、只读 API／CLI 以及备份恢复。实际 Node 解析使用只读的现有仓库提取器与依赖，数据库／登记文件和升级均在临时环境；未在用户实际库上运行新登记图。只读核对实际库仍为 0002_worker_health。

### 用户实际库的登记图验收（2026-11-16）

用户随后执行 init-db 和 extract-ssm-graph，助手只读核对如下，不重复提取、不改写结果：

- 实际库为 `0003_ssm_extractions`；来源为已上传 `DeliveryPhaseCard.vue`，引用原 run `b0f6b858240b431fa486d791bf6e03c4`。
- 新提取 ID：`5fe54b4c976241ddbe29fde9a331535d`，状态 completed，停止原因 `ssm_extracted_not_migration_pass`；用户输出 graph_pending=false，图库内该独立 thread 有 5 个 checkpoint。
- 请求指纹：`8b55e3d84f9698f93ad98484df3b17ca9830036a221f2b0cabcc764a59c3d88f`。
- 登记目录：`data/experiments/migration_system/ssm-extractions/5fe54b4c976241ddbe29fde9a331535d/`；请求／收据／SSM 三个登记文件均通过读取和哈希／归属审计。
- `request.json` SHA-256：`5127ee61bc9603a5503de7e26b16e1708e829112505afe377c2a281427a03b2e`；`receipt.json`：`dac7781173c88e63f5a72b834f7b47e3931263bc3c6605768550bfc7069fd9b6`。
- `ssm.json` SHA-256：`872d768b0328bdf5bc9b883d261626fe30f2c9e22113e993a8252134200079b3`，SSM 3.0；与之前独立离线探测的 SSM 字节完全相同，两条记录不混合或覆盖。
- 原夹具 run 只读报告仍为 finished／outcome=not_run，原 P1 报告及六项检查仍为 not_run；真实提取未被伪装成完整迁移通过。
- 模型调用 0、LangSmith 未上传。新登记结果具备进入备份的条件，但本轮未对用户实际库执行备份或恢复；备份恢复的通过证据仍来自临时环境测试。

登记图这一增量已在实际库验证；其后的源阶段契约映射已实现，随后逐步接主迁移图，不启用付费模型或正则降级。

## 为什么先独立接入

旧 `SSMFactory` 继续只读复用，不导入旧迁移编排器，也不复制第二套 SSM schema。新适配器在独立 Python／Node 子进程中调用原 `parse_sfc.cjs` 与 SSM v3 组装器。旧解析器会在 Node 失败时回退正则解析；本适配层明确禁止这一解析器降级，不将依赖缺失／语法错误标记为 AST 提取成功。

最初的离线增量先验证提取接口及证据；本次已增加上面的独立登记图，完整迁移图与 P1 报告仍待后续。现有网页无“真实迁移”开关，旧报告的六项 not_run 不改变。

## 工作台只读展示（2026-11-16 后续增量）

新增 GET `/api/v1/ssm-extractions`，1—50 条键集分页，默认 10 条，按 created_at／id 倒序；列表只读登记元数据，明确 evidence_audit=not_performed_in_list，不调用解析器、不读全部 SSM、不证明内容通过。报告／下载仍调用原证据审计。分页参数、Host／Origin 检查保留，不新增写接口或 schema。

工作台新增独立真实源面板，分别显示登记执行状态、源评估和整体迁移未执行；展示源／请求／环境指纹、诊断来源及证据清单，支持报告与 SSM 下载。历史 v1 记录仍 contract_report=null、partial_evaluation_only，页面解释历史缺失而不补写或要求复跑。点击下载会重新核对证据；查询或审计失败时禁用下载，不把错误 JSON 当 SSM。

本步只读核对实际记录 5fe54b4c976241ddbe29fde9a331535d：三个 GET 返回 200、下载 SSM 35053 字节，模型调用 0、迁移 not_run；读取前后所有业务表逻辑行摘要及原夹具报告相同，没有重跑提取或修改记录。用户已升级 0003，不需要重复 init-db 或提取。随后用户回复“已确认通过”：对应提取完成／整体迁移未执行、历史快照缺失提示和报告／SSM 两份 JSON 下载打开。记录为新面板基础人工验收通过，未独立读取用户下载文件或追加浏览器证据；跨页／断连／窄屏等专项不从整体回复推定通过。详见[网页记录](frontend/README.md#真实-ssm-只读面板2026-11-16)，不新增质量实验或正式成绩。

新增 7 项工作台后端测试和 5 项前端测试；本轮完整新工程 Python 185 项（197.038 秒）、原 P1 40 项、前端 Node 22 项及类型检查／构建通过。测试证明有界分页、只读不执行、旧权限保留及损坏证据禁止下载等工程行为，不是浏览器验收或 SSM 覆盖率证明。

下一步进入真实生成适配的开发：先定义并冻结源／SSM／Prompt／模型配置／预算和客户端边界，离线验证生成输出登记、收据复用与异常阻断，再另行确认真实模型联调。SSM 提取成功不解锁整体迁移 pass；目标评估和修复仍需实际接入。

后续 G1 已提供 `generation-preview`，只读消费本节已登记且完成的 SSM，不重提取、不补写旧 P1 快照，完整请求暂只封装在内存中。已复用固定的旧 Prompt 构造函数／规则、定义模型及预算边界，并测试显式离线客户端响应。**还没有持久生成收据、San 版本或实际模型调用**，因此下一增量为 G2 登记／图恢复／备份，而不是直接宣称已迁移。命令与限制见 [GENERATION.md](GENERATION.md)。本次实际记录预览重复一致，业务表逻辑行未改变；无需再次初始化或运行提取。

## 旧离线探测命令（保留）

仓库根目录、第三个 PowerShell 窗口执行（不要输入正在运行 serve／worker 的前台进程）。当前代码要求先完成上面的 0003 增量升级；无需为每次提取重复初始化。已结束历史运行可只读引用，不能强行续跑旧绑定；不删除数据库。

使用已上传源码关联的运行 ID，例如本次人工联调记录：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py extract-ssm --run-id b0f6b858240b431fa486d791bf6e03c4
```

或直接指定已有 input ID（与 run-id 二选一，替换下面的占位字符串）：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py extract-ssm --input-id "替换为32位输入ID"
```

不需要写令牌、模型密钥或 LangSmith 密钥；只读引用业务库和已登记源码，写入独立的本地提取探测目录，不创建迁移运行、不调用模型、不上传追踪。测试先使用合成源码；本轮也已对下述实际上传源码完成提取。

默认输出：`migration_system/var/ssm-extractions/<extraction_id>/`。CLI 只打印状态、目录、文件指纹和错误码，不打印源码或环境。提取完成退出 0，阻断退出 2，不自动重复提取。

| 文件 | 内容 |
| --- | --- |
| `request.json` | 提取 ID、来源 input ID／可选关联 run ID、文件名、输入字节 SHA-256、受限范围 |
| `source.vue` | 经原登记哈希核对的源码快照，不执行内容 |
| `ssm.json` | 仅成功提取时保存 SSM 3.0；没有伪造的 San 产物 |
| `receipt.json` | 最后写入的完成／阻断收据；请求／SSM 字节指纹、实际绑定、限制和零模型调用 |

文件使用已有不可覆盖存储提交；每次显式执行创建新的 extraction ID。请求／源码已保存而没有最终收据表示未完成，不能当成功；不自动清理或续跑。不把这些探测结果登记成已有夹具运行的版本／质量检查。

**备份边界：这些文件当前属于独立辅助探测，不在业务 DB 的注册产物集合，因此现有 backup／restore 命令不包含它们。** 如需保留本步证据，应另行保存整个提取目录；后续接数据库／图时须设计登记、备份和恢复，不得静默假定已覆盖。源码／SSM 可能含业务敏感内容，目录不自动上传。

## 提取范围与失败行为

- 仅已有系统允许的 UTF-8、≤256 KiB、字母／数字／下划线 `.vue` 文件；先核对输入字节哈希。
- 当前为 Options API、一个元素模板根节点。`script setup`（包括双 script）、多根／纯文本根、外置 `src` 块、自定义块、不支持的模板／脚本语言明确阻断，不静默丢弃。**这不是项目最终支持范围**，不改变开题完整提取要求；未支持能力需后续补齐。
- Vue SFC 错误、模板结构错误及 Babel 脚本语法错误阻断；不承诺完整 Vue 编译／运行时有效性、CSS 语法验证或语义等价。
- 引用的子组件／模块不加载、不执行，不声称完成依赖解析；用户源码的顶层调用、生命周期、数据工厂均不运行。
- 模板／脚本使用真实 AST；样式及跨块关联沿用旧启发式逻辑，**不是四维全部 AST 精确证明或 ≥90% 覆盖率证据**。
- Node、根目录现有提取依赖及 package-lock 必须可用。只读使用已有依赖，不修改／安装旧根依赖。四个直接解析依赖的实际版本需与锁文件相同；缺失／版本不符即阻断。
- 绑定记录旧 SSM 全部 Python 源码／bridge、根 package.json／package-lock、新适配器、解释器、实际 Node 版本／包版本和已加载 Node 模块的文件 SHA-256；执行前后复核漂移。记录的是本次本地绑定，不是新的预注册正式实验协议，也不是完整恶意依赖供应链认证。
- 子进程环境不继承模型／追踪密钥、NODE_OPTIONS、PYTHONPATH 等注入项；不执行 shell。Node 20 秒、外层 Python 30 秒超时，超过 8 MiB 的返回内容拒绝接纳。输出大小检查发生在捕获后，不冒称硬内存配额或敌对代码安全沙箱。
- 完成只表示提取获得了符合本适配器形状检查的 SSM；`migration_quality_status=not_run`、`production_ready=false`，不产生迁移 pass。

## 实现与验证

代码：`adapters/ssm.py`、`ssm_worker.py`、`ssm_bridge.cjs`，`stages/extract.py` 和 CLI `extract-ssm`。只在新工程编辑，旧 SSM／P1 契约／数据库迁移／Vue／San／Prompt 和历史冻结产物不变。

测试命令：

```powershell
& migration_system/.venv/Scripts/python.exe -m unittest discover -s migration_system/tests -p test_ssm_extraction.py -v
```

测试覆盖真实 AST 及重复输出一致、用户代码不执行、显式失败／不回退、UTF-8／大小／路径／哈希、超时、环境隔离、输出形状／绑定漂移、已登记输入与收据、失败无假产物、CLI 退出码，以及提取前后原运行报告保持不变。数据库／输出使用临时目录；真实提取器和现有 Node 依赖仅被读取。

2026-11-16 验证结果：新增 21 项，新工程合计 133 项 Python 测试通过（96.159 秒）；原 P1 契约 40 项、前端 Node 17 项亦重跑通过。check 可报告离线提取可用、尚未接图。没有更新 Python／Node 依赖或修改 P1 固定源文件。

### 本次已上传源码实测

- 来源：`DeliveryPhaseCard.vue`，关联 run `b0f6b858240b431fa486d791bf6e03c4`。
- 提取 ID：`3138f3b1206749a2bc11f21774a96124`；结果 `completed`，SSM 3.0，模板根 `article`。
- 目录：`migration_system/var/ssm-extractions/3138f3b1206749a2bc11f21774a96124/`。
- `ssm.json` SHA-256：`872d768b0328bdf5bc9b883d261626fe30f2c9e22113e993a8252134200079b3`。
- `receipt.json` SHA-256：`37f7e9b2557dab55060eea2d5b0b4b459c533159df74d1f65aef85107539bc2f`。
- 请求、源码快照、SSM 与收据字节指纹已独立重读核对。Node 24.19.0、Python 3.14.7；只读使用旧根提取依赖 Vue compiler-sfc／compiler-dom 3.5.42、Babel parser／traverse 7.29.8，与新前端的 Vue 依赖不混为一套。
- 模型调用 0、无追踪上传。仅实际提取，不是组件迁移通过或四维覆盖率实验；原开发运行仍保持其夹具口径。本辅助目录尚不属于业务备份范围。

后续：登记账本与独立图节点已按顶部新增节实现；继续补完整迁移图及 P1 报告映射、支持语法与标注覆盖测试，再分阶段接真实生成和质量评估。未执行付费模型、浏览器评估、训练、LangSmith 上传或正式实验。
