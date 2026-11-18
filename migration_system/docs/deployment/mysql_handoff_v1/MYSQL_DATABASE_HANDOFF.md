# 给另一台电脑 AI 的 MySQL 建库交接文件 v1

> **历史版本，勿按本文件创建当前系统数据库。** 本文保留 0007 的 26 表及当时的未实现草案；当前系统已是 0008_multi_user／34 表。请给另一台 AI 发送 [完整 MySQL 多用户交接 v2](../mysql_handoff_v2/MYSQL_MULTI_USER_HANDOFF.md)，它包含全部字段、关系、SQL、核验和回报模板，不再依赖本文件。下文“当前／尚未实现”均指 v1 当时状态。

日期：2026-11-18。用途：电脑 B 准备 MySQL；电脑 A 保持现有迁移系统与 SQLite 实验数据。你可以只发送本 Markdown 文件，它已包含建表 SQL、字段字典、关系、验收和停止条件；同目录 SQL／JSON 是方便执行和机器核对的副本。

## 0. 请另一台电脑的 AI 先读此段

你的任务仅是：在用户指定的 MySQL 实例中，经确认后创建一个**全新的空准备库**，按本文件建表并核验，反馈非敏感连接信息。不是修改 Vue／San，不是调用模型，不是导入历史数据，也不是立即开放公网。

**本文件不能让现有系统直接支持 MySQL。当前 Python 连接、初始化、事务、备份和 LangGraph 检查点仍有 SQLite 专用实现。建表完成 ≠ 系统接入完成 ≠ 多用户权限完成。**

- 本文件的“当前结构 SQL”逐字段来自现有 0001—0007 模型，保持原表名、列名、可空性、唯一与外键约束；仅做明确列出的 MySQL 类型／存储映射。
- 用户、登录会话与用户归属目前尚未实现。第 7 节仅是待确认的扩展草案，不得混进当前兼容基线，更不得声称建了登录表就完成权限隔离。
- 不得删除／覆盖现有库，不执行 DROP、TRUNCATE、批量 DELETE、关闭外键检查或 `mysql --force`。不得修改其他软件数据库、服务器全局字符集或现有数据库账号。
- 默认准备库名 `cardmigrator_staging`。若已存在，停止并询问，不用 IF NOT EXISTS 掩盖旧结构；DDL 可能逐条提交，失败不保证整批回滚。失败后先检查已创建内容，不盲目重跑。
- 不在聊天、日志、截图、Git 或本文件中记录真实密码、模型 Key、完整带密码连接串。账号密码由数据库电脑用户本地设置，并安全交给系统管理员。
- 不把数据库端口暴露给整个互联网。先确认两台电脑是否处于同一局域网／受控 VPN，再允许指定后台主机连接。

## 1. 环境与执行顺序

目标语法：**MySQL 8.4 LTS**，InnoDB、utf8mb4、区分大小写的 `utf8mb4_0900_bin`；不是 MariaDB 或 MySQL 5.7 脚本。若用户已有其他版本，先报告版本／兼容差异，不自动卸载升级或替换原服务。

1. 只读确认 `SELECT VERSION(), @@hostname, @@port, @@sql_mode, @@character_set_server;`，确认 InnoDB、JSON、CHECK 与目标排序规则支持。
2. 向用户确认数据库名、后台电脑的固定局域网 IP、端口、是否有同名库、是否允许建库；既有数据先按用户要求备份。
3. 使用本机管理员执行第 6 节当前结构 SQL（或同目录 `schema_current.sql`）。此阶段只建空结构，不运行应用 `init-db`、不拷贝 SQLite 文件改扩展名、不导入演示账号。
4. 执行第 8 节只读核验；实际 MySQL 建表和负例约束测试由电脑 B 完成并提供证据。本文件生成端仅做离线核对，**没有在真实 MySQL 上验证执行成功**。
5. 建立应用专用账号：限定电脑 A 的来源 IP，日常权限仅本库 SELECT／INSERT／UPDATE／DELETE；建表迁移使用单独受控账号。不要给应用 root、全局权限或任意来源 `%`。用户同意的数据库级权限与密码均在本机处理。
6. MySQL 监听数据库电脑受控内网接口，防火墙仅放行后台电脑到该端口；需要时配置并验证 TLS。不得为了方便关闭整机防火墙或所有 TLS 校验。
7. 返回第 9 节交接清单，等待电脑 A 的 MySQL 适配工作。建库 AI 不自行修改电脑 A 的系统代码／预算／模型配置。

连接结构：浏览器 → 电脑 A 的后台 API／Worker → 电脑 B 的 MySQL。浏览器不持有数据库密码，不直连 3306。

## 2. 数据和类型约定

- 业务主键通常是应用生成的 32 字符 UUID hex；80／100 字符 ID 是原程序的不透明标识，不自行改为整数或 MySQL UUID()（通常 36 字符）。只有 `run_events.id` 自增。
- Python Float／SQLite REAL 在此映射为 MySQL **DOUBLE**，避免 MySQL 单精度 FLOAT 损失 Unix 秒时间戳精度。时间继续为应用提供的 Unix 秒，不能自行改 DATETIME／毫秒整数。
- String(n) → VARCHAR(n)；Integer → INTEGER；Boolean → BOOLEAN；JSON → MySQL JSON。字段非空、空值和无数据库默认值按现有模型保留；BOOLEAN 在 MySQL 是数值别名，应用仍需验证布尔输入。
- 当前模型没有状态列 ENUM；已有 CHECK 原样保留，其余状态由应用验证，不自创 ENUM 缩小范围。
- 全表使用同一字符集／排序规则，ID、哈希、相对路径保持区分大小写。外键类型、长度及排序规则必须匹配；不得用默认不区分大小写的规则替换。
- MySQL 外键默认立即检查，因此复合外键引用了明确的 PRIMARY／UNIQUE 键；不新增历史模型中没有的循环外键。删除／更新引用采用 RESTRICT，不级联删除实验记录。
- 请求 JSON、版本绑定、文件 SHA-256 不因换数据库擅自重算。JSON 序列化／反序列化必须回归核对，不能直接哈希 MySQL 显示的 JSON 文本冒充原请求摘要。
- DB 存文件索引与摘要；Vue、San、完整 SSM、截图、调用文件仍在电脑 A 的 `var/artifacts` 或以后明确配置的共享存储中。**只迁移数据库不会搬走文件。**
- `langgraph.sqlite3` 是 LangGraph 库管理的检查点库，不在本业务 DDL 中。不手工创建名为 checkpoints 的猜测表，不假设 LangGraph 已能使用 MySQL；后续需单独确定受支持的检查点后端。
- `alembic_version` 在准备库中保持空表。不得执行 INSERT／UPDATE／stamp 假装已完成 `0007_modular_migration`；现有 init-db 有 SQLite 专用逻辑，正式版本登记要等本系统 MySQL 迁移接入、结构审查及验证通过后由迁移流程执行。

## 3. 表清单

“完整”指与当前业务数据库结构一致，包括兼容代码仍可能读取的历史表；不意味着新增了完整在线多用户系统。不要仅因普通用户界面没有显示历史功能就擅自省略对应表。

| 表名 | 分组 | 作用 |
|---|---|---|
| `alembic_version` | 版本管理 | 结构迁移版本；交接脚本建空表，不伪造升级完成记录。 |
| `source_inputs` | 共享输入 | 上传源码的路径与内容哈希；源码本体在产物目录。 |
| `worker_health` | 运行监控 | Worker 心跳；run_id 仅提示当前运行，不是所有权或锁。 |
| `migration_jobs` | 当前迁移主链 | 真实 Vue→SSM→San 任务、请求快照、运行状态与版本绑定。 |
| `tasks` | 历史开发夹具 | 旧开发任务，不等同 migration_jobs。 |
| `migration_feedback` | 当前迁移主链 | 指定接受产物版本上的人工验收，独立于自动质量结论。 |
| `migration_files` | 当前迁移主链 | 任务所属文件索引及 SHA-256；不保存文件二进制。 |
| `migration_model_calls` | 当前迁移主链 | 实际模型调用状态、顺序及响应／用量收据。 |
| `runs` | 历史开发夹具 | 旧开发运行、幂等提交与固定请求／版本。 |
| `artifact_revisions` | 历史开发夹具 | 旧开发产物版本及同一运行内的父子关系。 |
| `attempts` | 历史开发夹具 | 旧开发尝试及响应；不替代真实迁移模型账本。 |
| `run_events` | 历史开发夹具 | 旧开发运行事件；唯一的自增主键表。 |
| `ssm_extractions` | 历史独立 SSM 提取 | 注册源码独立提取的请求及状态；当前主链 SSM 也可作为任务文件保存。 |
| `worker_locks` | 历史开发夹具 | 旧开发 Worker 租约，不能当作跨机器任务调度方案。 |
| `candidate_decisions` | 历史开发夹具 | 旧开发候选接受／回退关系。 |
| `evaluations` | 历史开发夹具 | 旧开发评估记录，不等同真实迁移的 assessment。 |
| `generation_approvals` | 历史生成审批 | 单一生成计划的审批、过期与使用状态。 |
| `generation_jobs` | 历史离线生成账本 | 离线测试生成请求，不是在线模型迁移任务。 |
| `provider_generation_jobs` | 历史记录式生成 | 记录式提供方生成请求，不混入离线候选来源。 |
| `ssm_extraction_files` | 历史独立 SSM 提取 | 独立提取的 request／ssm／receipt 文件索引。 |
| `generation_approval_files` | 历史生成审批 | 审批、撤销和领取证据文件索引。 |
| `generation_attempts` | 历史离线生成账本 | 每个离线生成任务最多一个尝试。 |
| `generation_files` | 历史离线生成账本 | 离线生成文件索引。 |
| `provider_generation_attempts` | 历史记录式生成 | 每个记录式生成任务最多一个尝试。 |
| `provider_generation_files` | 历史记录式生成 | 计划、请求、响应、收据与候选文件索引。 |
| `generation_candidates` | 历史离线生成账本 | 离线测试候选；parent_id 必须为空，来源固定。 |

## 4. 关系图与未声明外键的字段

```text
source_inputs 1 → N migration_jobs
migration_jobs 1 → N migration_files / migration_model_calls / migration_feedback
source_inputs 1 → N tasks → N runs
runs 1 → N artifact_revisions / attempts / evaluations / candidate_decisions / run_events / worker_locks
source_inputs 1 → N ssm_extractions → N ssm_extraction_files
ssm_extractions 1 → N generation_jobs / provider_generation_jobs / generation_approvals
generation_jobs 1 → 0..1 generation_attempts / generation_candidates；1 → N generation_files
provider_generation_jobs 1 → 0..1 provider_generation_attempts；1 → N provider_generation_files
generation_approvals 1 → N generation_approval_files
```

以上是简图，实际数据库 FK 逐项如下；generation_jobs 另关联 source_inputs，ssm_extractions 可选关联旧 runs。

- `migration_jobs(input_id)` → `source_inputs(id)`。
- `tasks(input_id)` → `source_inputs(id)`。
- `migration_feedback(job_id)` → `migration_jobs(id)`。
- `migration_files(job_id)` → `migration_jobs(id)`。
- `migration_model_calls(job_id)` → `migration_jobs(id)`。
- `runs(task_id)` → `tasks(id)`。
- `artifact_revisions(parent_id, run_id)` → `artifact_revisions(id, run_id)`。
- `artifact_revisions(run_id)` → `runs(id)`。
- `attempts(run_id)` → `runs(id)`。
- `run_events(run_id)` → `runs(id)`。
- `ssm_extractions(input_id)` → `source_inputs(id)`。
- `ssm_extractions(referenced_run_id)` → `runs(id)`。
- `worker_locks(run_id)` → `runs(id)`。
- `candidate_decisions(candidate_id, run_id)` → `artifact_revisions(id, run_id)`。
- `candidate_decisions(previous_id, run_id)` → `artifact_revisions(id, run_id)`。
- `candidate_decisions(run_id)` → `runs(id)`。
- `evaluations(revision_id, run_id)` → `artifact_revisions(id, run_id)`。
- `evaluations(run_id)` → `runs(id)`。
- `generation_approvals(extraction_id)` → `ssm_extractions(id)`。
- `generation_jobs(extraction_id)` → `ssm_extractions(id)`。
- `generation_jobs(input_id)` → `source_inputs(id)`。
- `provider_generation_jobs(extraction_id)` → `ssm_extractions(id)`。
- `ssm_extraction_files(extraction_id)` → `ssm_extractions(id)`。
- `generation_approval_files(approval_id)` → `generation_approvals(id)`。
- `generation_attempts(job_id)` → `generation_jobs(id)`。
- `generation_files(job_id)` → `generation_jobs(id)`。
- `provider_generation_attempts(job_id)` → `provider_generation_jobs(id)`。
- `provider_generation_files(job_id)` → `provider_generation_jobs(id)`。
- `generation_candidates(job_id)` → `generation_jobs(id)`。
- `generation_candidates(relative_path)` → `generation_files(relative_path)`。

特别注意：`worker_health.run_id`、`runs.final_revision_id`、`migration_feedback.revision_sha256` 当前没有数据库外键；`generation_candidates.parent_id` 仅 CHECK IS NULL。复合 FK 才能约束旧开发版本属于同一 run。不要凭字段名擅自补外键，也不要宣称数据库约束了所有文件／跨账本身份；部分仍由应用核验。

## 5. 完整字段字典

全部字段按应用约束提供，除自增事件 ID 外没有数据库生成的业务默认值。NULL 表示可以缺失，不等于空字符串／空 JSON；原请求 JSON 的 null 与 SQL NULL 也不能随意混用。

### alembic_version

结构迁移版本；交接脚本建空表，不伪造升级完成记录。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `version_num` | VARCHAR(32) | 否 | Alembic 修订号；本交接不填充。；主键 |

唯一约束：无额外 UNIQUE（主键除外）。

### source_inputs

上传源码的路径与内容哈希；源码本体在产物目录。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `filename` | VARCHAR(120) | 否 | 源文件名，不是服务器任意路径。 |
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。 |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |

唯一约束：无额外 UNIQUE（主键除外）。

### worker_health

Worker 心跳；run_id 仅提示当前运行，不是所有权或锁。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `pid` | INTEGER | 否 | Worker 进程号。 |
| `state` | VARCHAR(24) | 否 | Worker 状态字符串，或 migration_jobs 的完整运行状态 JSON（以字段类型为准）。 |
| `run_id` | VARCHAR(32) | 是 | 关联旧开发运行；worker_health 中仅作提示。 |
| `last_seen` | DOUBLE | 否 | 最近心跳时间，Unix 秒。 |
| `binding_sha256` | VARCHAR(64) | 否 | Worker 实现绑定摘要。 |

唯一约束：无额外 UNIQUE（主键除外）。

### migration_jobs

真实 Vue→SSM→San 任务、请求快照、运行状态与版本绑定。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `input_id` | VARCHAR(32) | 否 | 关联上传源码。 |
| `idempotency_key` | VARCHAR(80) | 否 | 幂等提交标识；唯一作用域见各表约束。 |
| `request` | JSON | 否 | 固定请求 JSON；保留原内容、嵌套数据和 Unicode。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `binding` | JSON | 否 | 实现、依赖与协议的版本绑定 JSON。 |
| `status` | VARCHAR(32) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `stage` | VARCHAR(40) | 否 | 当前真实迁移阶段，供队列与报告展示。 |
| `stop_reason` | VARCHAR(120) | 否 | 停止原因代码。 |
| `state` | JSON | 否 | Worker 状态字符串，或 migration_jobs 的完整运行状态 JSON（以字段类型为准）。 |
| `cancel_requested` | BOOLEAN | 否 | 安全取消请求标志。 |
| `created_at` | DOUBLE | 否 | 应用提供的 Unix 秒时间戳，包含小数。 |
| `updated_at` | DOUBLE | 否 | 最后更新时间，Unix 秒。 |

唯一约束：(idempotency_key)。

### tasks

旧开发任务，不等同 migration_jobs。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `input_id` | VARCHAR(32) | 否 | 关联上传源码。 |
| `name` | VARCHAR(120) | 否 | 显示名称。 |

唯一约束：无额外 UNIQUE（主键除外）。

### migration_feedback

指定接受产物版本上的人工验收，独立于自动质量结论。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `revision_sha256` | VARCHAR(64) | 否 | 人工确认的接受产物 SHA-256；不是当前数据库外键。 |
| `passed` | BOOLEAN | 否 | 人工验收结果，不覆盖自动质量结论。 |
| `changed_lines` | INTEGER | 是 | 人工修改行数，可为空。 |
| `elapsed_seconds` | DOUBLE | 是 | 人工耗时秒数，可为空。 |
| `notes` | VARCHAR(4000) | 否 | 人工备注，当前最大 4000 字符。 |
| `created_at` | DOUBLE | 否 | 应用提供的 Unix 秒时间戳，包含小数。 |

唯一约束：无额外 UNIQUE（主键除外）。

### migration_files

任务所属文件索引及 SHA-256；不保存文件二进制。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。；主键 |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `kind` | VARCHAR(40) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |

唯一约束：无额外 UNIQUE（主键除外）。

### migration_model_calls

实际模型调用状态、顺序及响应／用量收据。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(80) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `ordinal` | INTEGER | 否 | 同一真实迁移任务内的调用序号，不允许重复。 |
| `status` | VARCHAR(24) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `receipt` | JSON | 是 | 真实调用收据／用量 JSON；未返回时可为空，不得填伪造的零用量。 |
| `started_at` | DOUBLE | 否 | 调用或尝试开始时间，Unix 秒。 |
| `finished_at` | DOUBLE | 是 | 调用结束时间，未完成时可为空。 |

唯一约束：(job_id, ordinal)。

### runs

旧开发运行、幂等提交与固定请求／版本。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `task_id` | VARCHAR(32) | 否 | 关联旧开发任务。 |
| `idempotency_key` | VARCHAR(80) | 否 | 幂等提交标识；唯一作用域见各表约束。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `request` | JSON | 否 | 固定请求 JSON；保留原内容、嵌套数据和 Unicode。 |
| `binding` | JSON | 否 | 实现、依赖与协议的版本绑定 JSON。 |
| `status` | VARCHAR(32) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `outcome` | VARCHAR(32) | 否 | 旧开发运行结果，不冒充真实迁移质量。 |
| `final_revision_id` | VARCHAR(80) | 是 | 旧运行接受的产物标识；当前无数据库外键，由应用审查。 |
| `cancel_requested` | BOOLEAN | 否 | 安全取消请求标志。 |
| `stop_reason` | VARCHAR(120) | 否 | 停止原因代码。 |
| `created_at` | DOUBLE | 否 | 应用提供的 Unix 秒时间戳，包含小数。 |

唯一约束：(task_id, idempotency_key)。

### artifact_revisions

旧开发产物版本及同一运行内的父子关系。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(80) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `run_id` | VARCHAR(32) | 否 | 关联旧开发运行；worker_health 中仅作提示。 |
| `parent_id` | VARCHAR(80) | 是 | 父产物标识；artifact_revisions 有复合外键，generation_candidates 则 CHECK 必须为空。 |
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。 |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `source_kind` | VARCHAR(40) | 否 | 产物来源，不能把离线测试产物改记成真实模型生成。 |
| `fixture_assertions` | JSON | 否 | 历史夹具验证数据 JSON，不代表真实迁移通过。 |

唯一约束：(id, run_id)。

### attempts

旧开发尝试及响应；不替代真实迁移模型账本。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(100) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `run_id` | VARCHAR(32) | 否 | 关联旧开发运行；worker_health 中仅作提示。 |
| `kind` | VARCHAR(40) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |
| `status` | VARCHAR(24) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `result` | JSON | 是 | 尝试结果 JSON，可为空表示尚未返回等状态。 |
| `started_at` | DOUBLE | 否 | 调用或尝试开始时间，Unix 秒。 |
| `model_tokens` | INTEGER | 是 | 旧尝试的 Token 记录，可为空。 |

唯一约束：无额外 UNIQUE（主键除外）。

### run_events

旧开发运行事件；唯一的自增主键表。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | INTEGER | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键；AUTO_INCREMENT |
| `run_id` | VARCHAR(32) | 否 | 关联旧开发运行；worker_health 中仅作提示。 |
| `event_key` | VARCHAR(120) | 否 | 同一旧运行内的幂等事件键。 |
| `kind` | VARCHAR(40) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |
| `details` | JSON | 否 | 事件详情 JSON。 |

唯一约束：(run_id, event_key)。

### ssm_extractions

注册源码独立提取的请求及状态；当前主链 SSM 也可作为任务文件保存。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `input_id` | VARCHAR(32) | 否 | 关联上传源码。 |
| `referenced_run_id` | VARCHAR(32) | 是 | 可选的旧开发运行引用，不是当前 migration_jobs 外键。 |
| `status` | VARCHAR(24) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `request` | JSON | 否 | 固定请求 JSON；保留原内容、嵌套数据和 Unicode。 |
| `stop_reason` | VARCHAR(100) | 否 | 停止原因代码。 |
| `created_at` | DOUBLE | 否 | 应用提供的 Unix 秒时间戳，包含小数。 |

唯一约束：无额外 UNIQUE（主键除外）。

CHECK：`status IN ('prepared','started','received','completed','blocked','review_required')`。

### worker_locks

旧开发 Worker 租约，不能当作跨机器任务调度方案。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(20) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `owner` | VARCHAR(32) | 否 | Worker 租约持有者标识，不是用户 ID。 |
| `run_id` | VARCHAR(32) | 否 | 关联旧开发运行；worker_health 中仅作提示。 |
| `expires_at` | DOUBLE | 否 | 到期时间，Unix 秒。 |

唯一约束：无额外 UNIQUE（主键除外）。

### candidate_decisions

旧开发候选接受／回退关系。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(100) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `run_id` | VARCHAR(32) | 否 | 关联旧开发运行；worker_health 中仅作提示。 |
| `previous_id` | VARCHAR(80) | 否 | 候选之前的接受产物标识。 |
| `candidate_id` | VARCHAR(80) | 否 | 本次候选产物标识。 |
| `action` | VARCHAR(24) | 否 | 接受／回退等决策。 |
| `reason` | VARCHAR(120) | 否 | 决策原因代码。 |

唯一约束：无额外 UNIQUE（主键除外）。

### evaluations

旧开发评估记录，不等同真实迁移的 assessment。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(100) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `run_id` | VARCHAR(32) | 否 | 关联旧开发运行；worker_health 中仅作提示。 |
| `revision_id` | VARCHAR(80) | 否 | 被评估产物版本。 |
| `status` | VARCHAR(32) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `scope` | VARCHAR(80) | 否 | 旧评估的范围标识。 |
| `fixture_assertions` | JSON | 否 | 历史夹具验证数据 JSON，不代表真实迁移通过。 |

唯一约束：无额外 UNIQUE（主键除外）。

### generation_approvals

单一生成计划的审批、过期与使用状态。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `extraction_id` | VARCHAR(32) | 否 | 关联独立 SSM 提取记录。 |
| `idempotency_key` | VARCHAR(80) | 否 | 幂等提交标识；唯一作用域见各表约束。 |
| `request` | JSON | 否 | 固定请求 JSON；保留原内容、嵌套数据和 Unicode。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `status` | VARCHAR(16) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `created_at` | DOUBLE | 否 | 应用提供的 Unix 秒时间戳，包含小数。 |
| `expires_at` | DOUBLE | 否 | 到期时间，Unix 秒。 |

唯一约束：(extraction_id, idempotency_key)。

CHECK：`status IN ('pending','approved','revoked','consumed')`。

### generation_jobs

离线测试生成请求，不是在线模型迁移任务。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `extraction_id` | VARCHAR(32) | 否 | 关联独立 SSM 提取记录。 |
| `input_id` | VARCHAR(32) | 否 | 关联上传源码。 |
| `idempotency_key` | VARCHAR(80) | 否 | 幂等提交标识；唯一作用域见各表约束。 |
| `status` | VARCHAR(24) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `request` | JSON | 否 | 固定请求 JSON；保留原内容、嵌套数据和 Unicode。 |
| `stop_reason` | VARCHAR(100) | 否 | 停止原因代码。 |
| `created_at` | DOUBLE | 否 | 应用提供的 Unix 秒时间戳，包含小数。 |

唯一约束：(extraction_id, idempotency_key)。

CHECK：`status IN ('prepared','started','received','completed','blocked','review_required')`。

### provider_generation_jobs

记录式提供方生成请求，不混入离线候选来源。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `extraction_id` | VARCHAR(32) | 否 | 关联独立 SSM 提取记录。 |
| `idempotency_key` | VARCHAR(80) | 否 | 幂等提交标识；唯一作用域见各表约束。 |
| `request` | JSON | 否 | 固定请求 JSON；保留原内容、嵌套数据和 Unicode。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `status` | VARCHAR(24) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `stop_reason` | VARCHAR(100) | 否 | 停止原因代码。 |
| `created_at` | DOUBLE | 否 | 应用提供的 Unix 秒时间戳，包含小数。 |

唯一约束：(extraction_id, idempotency_key)。

CHECK：`status IN ('prepared','started','received','completed','blocked','review_required')`。

### ssm_extraction_files

独立提取的 request／ssm／receipt 文件索引。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。；主键 |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `extraction_id` | VARCHAR(32) | 否 | 关联独立 SSM 提取记录。 |
| `kind` | VARCHAR(16) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |

唯一约束：(extraction_id, kind)。

CHECK：`kind IN ('request','ssm','receipt')`。

### generation_approval_files

审批、撤销和领取证据文件索引。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。；主键 |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `approval_id` | VARCHAR(32) | 否 | 关联生成审批。 |
| `kind` | VARCHAR(16) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |

唯一约束：(approval_id, kind)。

CHECK：`kind IN ('request','approval','revocation','claim')`。

### generation_attempts

每个离线生成任务最多一个尝试。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(80) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `status` | VARCHAR(24) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `started_at` | DOUBLE | 否 | 调用或尝试开始时间，Unix 秒。 |

唯一约束：(job_id)。

CHECK：`status IN ('started','received','review_required')`。

### generation_files

离线生成文件索引。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。；主键 |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `kind` | VARCHAR(16) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |

唯一约束：(job_id, kind)。

CHECK：`kind IN ('request','receipt','candidate')`。

### provider_generation_attempts

每个记录式生成任务最多一个尝试。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(80) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `status` | VARCHAR(24) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `started_at` | DOUBLE | 否 | 调用或尝试开始时间，Unix 秒。 |

唯一约束：(job_id)。

CHECK：`status IN ('started','received','review_required')`。

### provider_generation_files

计划、请求、响应、收据与候选文件索引。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。；主键 |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `kind` | VARCHAR(16) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |

唯一约束：(job_id, kind)。

CHECK：`kind IN ('plan','request','response','receipt','candidate')`。

### generation_candidates

离线测试候选；parent_id 必须为空，来源固定。

| 字段 | MySQL 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(80) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；主键 |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。 |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `parent_id` | VARCHAR(80) | 是 | 父产物标识；artifact_revisions 有复合外键，generation_candidates 则 CHECK 必须为空。 |
| `source_kind` | VARCHAR(32) | 否 | 产物来源，不能把离线测试产物改记成真实模型生成。 |

唯一约束：(job_id)；(relative_path)。

CHECK：`parent_id IS NULL`；`source_kind = 'offline_client_test'`。

## 6. 当前结构完整 SQL：只对新的空准备库执行

此 SQL 不包含用户扩展，不登记 Alembic 修订、不包含任何密码。请确认目标实例与库名后执行；不要自动作用于现有数据库。

```sql
-- PREPARATION ONLY: new empty MySQL 8.4 database; no existing data is modified.
-- No IF NOT EXISTS, DROP, data import or fake Alembic stamp. Stop on the first error.
CREATE DATABASE `cardmigrator_staging` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;
USE `cardmigrator_staging`;

CREATE TABLE `alembic_version` (
  `version_num` VARCHAR(32) NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `source_inputs` (
  `id` VARCHAR(32) NOT NULL,
  `filename` VARCHAR(120) NOT NULL,
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `worker_health` (
  `id` VARCHAR(32) NOT NULL,
  `pid` INTEGER NOT NULL,
  `state` VARCHAR(24) NOT NULL,
  `run_id` VARCHAR(32) NULL,
  `last_seen` DOUBLE NOT NULL,
  `binding_sha256` VARCHAR(64) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `migration_jobs` (
  `id` VARCHAR(32) NOT NULL,
  `input_id` VARCHAR(32) NOT NULL,
  `idempotency_key` VARCHAR(80) NOT NULL,
  `request` JSON NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `binding` JSON NOT NULL,
  `status` VARCHAR(32) NOT NULL,
  `stage` VARCHAR(40) NOT NULL,
  `stop_reason` VARCHAR(120) NOT NULL,
  `state` JSON NOT NULL,
  `cancel_requested` BOOLEAN NOT NULL,
  `created_at` DOUBLE NOT NULL,
  `updated_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_migration_jobs_1` UNIQUE (`idempotency_key`),
  CONSTRAINT `fk_migration_jobs_1` FOREIGN KEY (`input_id`) REFERENCES `source_inputs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `tasks` (
  `id` VARCHAR(32) NOT NULL,
  `input_id` VARCHAR(32) NOT NULL,
  `name` VARCHAR(120) NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_tasks_1` FOREIGN KEY (`input_id`) REFERENCES `source_inputs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `migration_feedback` (
  `id` VARCHAR(32) NOT NULL,
  `job_id` VARCHAR(32) NOT NULL,
  `revision_sha256` VARCHAR(64) NOT NULL,
  `passed` BOOLEAN NOT NULL,
  `changed_lines` INTEGER NULL,
  `elapsed_seconds` DOUBLE NULL,
  `notes` VARCHAR(4000) NOT NULL,
  `created_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_migration_feedback_1` FOREIGN KEY (`job_id`) REFERENCES `migration_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `migration_files` (
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  `job_id` VARCHAR(32) NOT NULL,
  `kind` VARCHAR(40) NOT NULL,
  PRIMARY KEY (`relative_path`),
  CONSTRAINT `fk_migration_files_1` FOREIGN KEY (`job_id`) REFERENCES `migration_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `migration_model_calls` (
  `id` VARCHAR(80) NOT NULL,
  `job_id` VARCHAR(32) NOT NULL,
  `ordinal` INTEGER NOT NULL,
  `status` VARCHAR(24) NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `receipt` JSON NULL,
  `started_at` DOUBLE NOT NULL,
  `finished_at` DOUBLE NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_migration_model_calls_1` UNIQUE (`job_id`, `ordinal`),
  CONSTRAINT `fk_migration_model_calls_1` FOREIGN KEY (`job_id`) REFERENCES `migration_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `runs` (
  `id` VARCHAR(32) NOT NULL,
  `task_id` VARCHAR(32) NOT NULL,
  `idempotency_key` VARCHAR(80) NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `request` JSON NOT NULL,
  `binding` JSON NOT NULL,
  `status` VARCHAR(32) NOT NULL,
  `outcome` VARCHAR(32) NOT NULL,
  `final_revision_id` VARCHAR(80) NULL,
  `cancel_requested` BOOLEAN NOT NULL,
  `stop_reason` VARCHAR(120) NOT NULL,
  `created_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_runs_1` UNIQUE (`task_id`, `idempotency_key`),
  CONSTRAINT `fk_runs_1` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `artifact_revisions` (
  `id` VARCHAR(80) NOT NULL,
  `run_id` VARCHAR(32) NOT NULL,
  `parent_id` VARCHAR(80) NULL,
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  `source_kind` VARCHAR(40) NOT NULL,
  `fixture_assertions` JSON NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_artifact_revisions_1` UNIQUE (`id`, `run_id`),
  CONSTRAINT `fk_artifact_revisions_1` FOREIGN KEY (`parent_id`, `run_id`) REFERENCES `artifact_revisions` (`id`, `run_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_artifact_revisions_2` FOREIGN KEY (`run_id`) REFERENCES `runs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `attempts` (
  `id` VARCHAR(100) NOT NULL,
  `run_id` VARCHAR(32) NOT NULL,
  `kind` VARCHAR(40) NOT NULL,
  `status` VARCHAR(24) NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `result` JSON NULL,
  `started_at` DOUBLE NOT NULL,
  `model_tokens` INTEGER NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_attempts_1` FOREIGN KEY (`run_id`) REFERENCES `runs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `run_events` (
  `id` INTEGER NOT NULL AUTO_INCREMENT,
  `run_id` VARCHAR(32) NOT NULL,
  `event_key` VARCHAR(120) NOT NULL,
  `kind` VARCHAR(40) NOT NULL,
  `details` JSON NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_run_events_1` UNIQUE (`run_id`, `event_key`),
  CONSTRAINT `fk_run_events_1` FOREIGN KEY (`run_id`) REFERENCES `runs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `ssm_extractions` (
  `id` VARCHAR(32) NOT NULL,
  `input_id` VARCHAR(32) NOT NULL,
  `referenced_run_id` VARCHAR(32) NULL,
  `status` VARCHAR(24) NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `request` JSON NOT NULL,
  `stop_reason` VARCHAR(100) NOT NULL,
  `created_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_ssm_extractions_1` FOREIGN KEY (`input_id`) REFERENCES `source_inputs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_ssm_extractions_2` FOREIGN KEY (`referenced_run_id`) REFERENCES `runs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_ssm_extractions_1` CHECK (status IN ('prepared','started','received','completed','blocked','review_required'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `worker_locks` (
  `id` VARCHAR(20) NOT NULL,
  `owner` VARCHAR(32) NOT NULL,
  `run_id` VARCHAR(32) NOT NULL,
  `expires_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_worker_locks_1` FOREIGN KEY (`run_id`) REFERENCES `runs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `candidate_decisions` (
  `id` VARCHAR(100) NOT NULL,
  `run_id` VARCHAR(32) NOT NULL,
  `previous_id` VARCHAR(80) NOT NULL,
  `candidate_id` VARCHAR(80) NOT NULL,
  `action` VARCHAR(24) NOT NULL,
  `reason` VARCHAR(120) NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_candidate_decisions_1` FOREIGN KEY (`candidate_id`, `run_id`) REFERENCES `artifact_revisions` (`id`, `run_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_candidate_decisions_2` FOREIGN KEY (`previous_id`, `run_id`) REFERENCES `artifact_revisions` (`id`, `run_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_candidate_decisions_3` FOREIGN KEY (`run_id`) REFERENCES `runs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `evaluations` (
  `id` VARCHAR(100) NOT NULL,
  `run_id` VARCHAR(32) NOT NULL,
  `revision_id` VARCHAR(80) NOT NULL,
  `status` VARCHAR(32) NOT NULL,
  `scope` VARCHAR(80) NOT NULL,
  `fixture_assertions` JSON NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_evaluations_1` FOREIGN KEY (`revision_id`, `run_id`) REFERENCES `artifact_revisions` (`id`, `run_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_evaluations_2` FOREIGN KEY (`run_id`) REFERENCES `runs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `generation_approvals` (
  `id` VARCHAR(32) NOT NULL,
  `extraction_id` VARCHAR(32) NOT NULL,
  `idempotency_key` VARCHAR(80) NOT NULL,
  `request` JSON NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `status` VARCHAR(16) NOT NULL,
  `created_at` DOUBLE NOT NULL,
  `expires_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_generation_approvals_1` UNIQUE (`extraction_id`, `idempotency_key`),
  CONSTRAINT `fk_generation_approvals_1` FOREIGN KEY (`extraction_id`) REFERENCES `ssm_extractions` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_generation_approvals_1` CHECK (status IN ('pending','approved','revoked','consumed'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `generation_jobs` (
  `id` VARCHAR(32) NOT NULL,
  `extraction_id` VARCHAR(32) NOT NULL,
  `input_id` VARCHAR(32) NOT NULL,
  `idempotency_key` VARCHAR(80) NOT NULL,
  `status` VARCHAR(24) NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `request` JSON NOT NULL,
  `stop_reason` VARCHAR(100) NOT NULL,
  `created_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_generation_jobs_1` UNIQUE (`extraction_id`, `idempotency_key`),
  CONSTRAINT `fk_generation_jobs_1` FOREIGN KEY (`extraction_id`) REFERENCES `ssm_extractions` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_generation_jobs_2` FOREIGN KEY (`input_id`) REFERENCES `source_inputs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_generation_jobs_1` CHECK (status IN ('prepared','started','received','completed','blocked','review_required'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `provider_generation_jobs` (
  `id` VARCHAR(32) NOT NULL,
  `extraction_id` VARCHAR(32) NOT NULL,
  `idempotency_key` VARCHAR(80) NOT NULL,
  `request` JSON NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `status` VARCHAR(24) NOT NULL,
  `stop_reason` VARCHAR(100) NOT NULL,
  `created_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_provider_generation_jobs_1` UNIQUE (`extraction_id`, `idempotency_key`),
  CONSTRAINT `fk_provider_generation_jobs_1` FOREIGN KEY (`extraction_id`) REFERENCES `ssm_extractions` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_provider_generation_jobs_1` CHECK (status IN ('prepared','started','received','completed','blocked','review_required'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `ssm_extraction_files` (
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  `extraction_id` VARCHAR(32) NOT NULL,
  `kind` VARCHAR(16) NOT NULL,
  PRIMARY KEY (`relative_path`),
  CONSTRAINT `uq_ssm_extraction_files_1` UNIQUE (`extraction_id`, `kind`),
  CONSTRAINT `fk_ssm_extraction_files_1` FOREIGN KEY (`extraction_id`) REFERENCES `ssm_extractions` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_ssm_extraction_files_1` CHECK (kind IN ('request','ssm','receipt'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `generation_approval_files` (
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  `approval_id` VARCHAR(32) NOT NULL,
  `kind` VARCHAR(16) NOT NULL,
  PRIMARY KEY (`relative_path`),
  CONSTRAINT `uq_generation_approval_files_1` UNIQUE (`approval_id`, `kind`),
  CONSTRAINT `fk_generation_approval_files_1` FOREIGN KEY (`approval_id`) REFERENCES `generation_approvals` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_generation_approval_files_1` CHECK (kind IN ('request','approval','revocation','claim'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `generation_attempts` (
  `id` VARCHAR(80) NOT NULL,
  `job_id` VARCHAR(32) NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `status` VARCHAR(24) NOT NULL,
  `started_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_generation_attempts_1` UNIQUE (`job_id`),
  CONSTRAINT `fk_generation_attempts_1` FOREIGN KEY (`job_id`) REFERENCES `generation_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_generation_attempts_1` CHECK (status IN ('started','received','review_required'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `generation_files` (
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  `job_id` VARCHAR(32) NOT NULL,
  `kind` VARCHAR(16) NOT NULL,
  PRIMARY KEY (`relative_path`),
  CONSTRAINT `uq_generation_files_1` UNIQUE (`job_id`, `kind`),
  CONSTRAINT `fk_generation_files_1` FOREIGN KEY (`job_id`) REFERENCES `generation_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_generation_files_1` CHECK (kind IN ('request','receipt','candidate'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `provider_generation_attempts` (
  `id` VARCHAR(80) NOT NULL,
  `job_id` VARCHAR(32) NOT NULL,
  `request_sha256` VARCHAR(64) NOT NULL,
  `status` VARCHAR(24) NOT NULL,
  `started_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_provider_generation_attempts_1` UNIQUE (`job_id`),
  CONSTRAINT `fk_provider_generation_attempts_1` FOREIGN KEY (`job_id`) REFERENCES `provider_generation_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_provider_generation_attempts_1` CHECK (status IN ('started','received','review_required'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `provider_generation_files` (
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  `job_id` VARCHAR(32) NOT NULL,
  `kind` VARCHAR(16) NOT NULL,
  PRIMARY KEY (`relative_path`),
  CONSTRAINT `uq_provider_generation_files_1` UNIQUE (`job_id`, `kind`),
  CONSTRAINT `fk_provider_generation_files_1` FOREIGN KEY (`job_id`) REFERENCES `provider_generation_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_provider_generation_files_1` CHECK (kind IN ('plan','request','response','receipt','candidate'))
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `generation_candidates` (
  `id` VARCHAR(80) NOT NULL,
  `job_id` VARCHAR(32) NOT NULL,
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  `parent_id` VARCHAR(80) NULL,
  `source_kind` VARCHAR(32) NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_generation_candidates_1` UNIQUE (`job_id`),
  CONSTRAINT `uq_generation_candidates_2` UNIQUE (`relative_path`),
  CONSTRAINT `fk_generation_candidates_1` FOREIGN KEY (`job_id`) REFERENCES `generation_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_generation_candidates_2` FOREIGN KEY (`relative_path`) REFERENCES `generation_files` (`relative_path`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_generation_candidates_1` CHECK (parent_id IS NULL),
  CONSTRAINT `ck_generation_candidates_2` CHECK (source_kind = 'offline_client_test')
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;
```

## 7. 在线多用户扩展草案：尚未实现，本次默认不执行

以下只定义最小账号／会话候选结构供两端 AI 对齐，**不是 0007 当前 schema，不是已确定的生产协议**。不要自行添加到账本或改写旧请求 JSON；待本系统增加对应 Alembic 修订、账号 API、权限中间件和测试后再执行正式迁移。

### users（拟新增）

| 字段 | 候选类型／约束 | 含义 |
|---|---|---|
| id | VARCHAR(32) PK | 应用生成用户标识 |
| username | VARCHAR(64) NOT NULL | 登录名原值，首版建议限定明确字符集 |
| username_normalized | VARCHAR(64) NOT NULL UNIQUE | 后台按统一规则规范化的登录名，不能仅依赖数据库不区分大小写 |
| display_name | VARCHAR(120) NOT NULL | 显示名称 |
| password_hash | VARCHAR(255) NOT NULL | 经可靠密码库产生的哈希编码，绝不保存明文／普通 SHA-256 密码 |
| role | VARCHAR(16) NOT NULL | 首版 user／admin，具体授权由后台执行 |
| is_active | BOOLEAN NOT NULL | 账号可用状态 |
| created_at | DOUBLE NOT NULL | 创建 Unix 秒 |
| updated_at | DOUBLE NOT NULL | 更新 Unix 秒 |
| password_changed_at | DOUBLE NULL | 密码变更 Unix 秒 |

### auth_sessions（拟新增）

| 字段 | 候选类型／约束 | 含义 |
|---|---|---|
| id | VARCHAR(32) PK | 会话记录 ID |
| user_id | VARCHAR(32) NOT NULL FK→users.id | 会话所属用户 |
| token_sha256 | VARCHAR(64) NOT NULL UNIQUE | 高熵随机会话凭据摘要；不能保存 Cookie 明文 |
| csrf_token_sha256 | VARCHAR(64) NOT NULL | 防跨站凭据摘要，最终算法随认证实现确定 |
| created_at | DOUBLE NOT NULL | 创建 Unix 秒 |
| expires_at | DOUBLE NOT NULL | 过期 Unix 秒 |
| last_seen_at | DOUBLE NULL | 最近使用时间 |
| revoked_at | DOUBLE NULL | 退出／撤销时间 |

拟建立 `INDEX(user_id, expires_at)`；退出、密码变更和禁用用户时撤销相关会话。现在的本机会话不关联用户，不应直接改名冒充此表。

### 所有权与其他待设计项

- `users 1 → N source_inputs`、`users 1 → N migration_jobs`：拟增加非空 `user_id` 外键；旧数据先明确归档账号，再经过迁移补齐，不能自动授予任意首个登录用户。
- `migration_jobs(user_id,input_id)` 必须与上传源码用户一致，可通过来源表 `(user_id,id)` 唯一键及复合外键在新修订中增强；后台还必须逐个鉴权，包括报告、下载、取消、恢复和人工反馈。
- 当前真实任务的 `UNIQUE(idempotency_key)` 是全局范围；多用户修订应评审为 `UNIQUE(user_id,idempotency_key)`。当前 SQL 仍保留全局唯一，不偷偷改定义。
- 文件、模型调用和人工反馈沿所属 job 查询用户权限；不能仅依靠路径或随机 ID。旧开发夹具和独立提取账本也要隔离为管理员功能或纳入用户归属，不留匿名读取接口。
- 用户额度、用量预留／结算、审计日志的表及并发协议尚未设计，当前调用收据不是额度预扣表。另一台 AI 不要凭猜测新增计费、余额、支付或团队表。
- 建表并不提供认证、权限、源码执行沙箱、HTTPS 或公平队列。此草案未实现前不得对外宣称在线多用户已可用。

## 8. 电脑 B 的验收步骤

执行同目录 `verify_schema.sql`（下列为等价检查要点）；结果只读，不应含任何业务源码／密钥。

1. 核对表数与名称，当前结构共 **26 张**，含空 `alembic_version`；业务表初始行数为 0。少任何一张都先报告，不能通过伪造行补齐。
2. `SHOW CREATE TABLE migration_jobs;`、`SHOW CREATE TABLE artifact_revisions;` 并检查每表字段类型、可空性、PK、UNIQUE、复合 FK、CHECK、InnoDB 和排序规则，与本文件字典／SQL 或 `schema_current.json` 对照。
3. 在管理员明确同意的**另一个一次性验证库**内做负例并回滚测试数据：不存在父项不能插入；调用 `(job_id,ordinal)` 重复被拒；跨 run 的评估／父版本／候选引用被拒；独立 SSM 非法状态与离线候选错误来源被拒；路径唯一性区分大小写。不要将测试样例插入准备库，更不要关闭外键检查。
4. 用两条只相差大小写／尾随空格的测试标识，验证所选排序规则未无意合并原 SQLite 可区分的值；用真实精度的 Unix 秒验证 DOUBLE；JSON 用中文、null、数组和数字做驱动往返检查。
5. 从电脑 A 检查端口可达（PowerShell：`Test-NetConnection -ComputerName <电脑B内网IP> -Port <MySQL端口>`）。该命令只证明 TCP 可达，不证明账号权限／TLS／系统接入成功。
6. 用应用专用账号在独立验证库或经允许的本库做授权检查：仅可访问所授权库，不能建账号、改全局设置或读取其他应用库。凭据不要打印。
7. 如果 MySQL 无法执行某条语句，报告版本、报错、具体表／约束及已创建表；不删表、不改字段长度、不删除 CHECK/FK 以“让它通过”。

只读核验 SQL：

```sql
-- Read-only; expected 26 tables, and no Alembic version row.
SELECT VERSION() AS mysql_version, DATABASE() AS current_database, @@sql_mode AS sql_mode;
SELECT COUNT(*) AS table_count FROM information_schema.TABLES WHERE TABLE_SCHEMA = 'cardmigrator_staging' AND TABLE_TYPE = 'BASE TABLE';
SELECT TABLE_NAME, ENGINE, TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA = 'cardmigrator_staging' ORDER BY TABLE_NAME;
SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = 'cardmigrator_staging' ORDER BY TABLE_NAME, ORDINAL_POSITION;
SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = 'cardmigrator_staging' ORDER BY TABLE_NAME, CONSTRAINT_NAME;
SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE CONSTRAINT_SCHEMA = 'cardmigrator_staging' ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION;
SELECT tc.TABLE_NAME, cc.CONSTRAINT_NAME, cc.CHECK_CLAUSE FROM information_schema.CHECK_CONSTRAINTS cc JOIN information_schema.TABLE_CONSTRAINTS tc ON tc.CONSTRAINT_SCHEMA=cc.CONSTRAINT_SCHEMA AND tc.CONSTRAINT_NAME=cc.CONSTRAINT_NAME WHERE tc.CONSTRAINT_SCHEMA='cardmigrator_staging' ORDER BY tc.TABLE_NAME, cc.CONSTRAINT_NAME;
SELECT COUNT(*) AS alembic_rows_must_be_zero FROM `cardmigrator_staging`.alembic_version;

```

## 9. 另一台电脑 AI 完成后的回报模板

```text
MySQL 版本：
数据库电脑内网 IP／受控域名：
端口：
准备库名：
应用专用账号名（不含密码）：
允许连接的后台电脑 IP：
TLS 配置／证书验证方式：
当前基线建表结果：实际数量／预期数量、失败表和报错
CHECK／外键／唯一／排序规则实测结果：
alembic_version 是否保持空表：
是否修改旧库／导入真实数据：应为否
多用户扩展是否执行：应为否（待正式迁移）
从后台电脑验证：未验证／仅TCP／账号连接／驱动往返
密码如何通过安全渠道单独交接：不要填写密码本身
仍需电脑 A 完成：MySQL驱动与配置、初始化／事务／锁、备份恢复、检查点后端、账号权限接入和回归
```

即使电脑 B 全部完成，电脑 A 当前 SQLite 连接也不会自动切换。不手改旧任务的 request／binding／SHA-256，不将旧结果重记成新版本模型成功。

## 10. 依据与来源

结构来源是本系统 `src/card_migration_system/persistence/` 中七份 metadata 与 migrations/versions/0001—0007；字段字典和 SQL 由 `scripts/export_mysql_handoff.py` 只读导出，未连接或更改现有数据库。类型映射、排序规则和 DDL 不是已完成的 MySQL 运行适配证明。

- [MySQL 外键要求](https://dev.mysql.com/doc/refman/8.4/en/create-table-foreign-keys.html)：引擎、类型／字符集匹配与父键要求。
- [MySQL JSON／其他类型的默认值](https://dev.mysql.com/doc/refman/8.4/en/data-type-defaults.html)：本脚本不凭空添加 JSON 默认值。
- [MySQL 远程连接排查](https://dev.mysql.com/doc/refman/8.4/en/problems-connecting.html)：监听地址、端口和来源账号。
- [MySQL 加密连接](https://dev.mysql.com/doc/refman/8.4/en/using-encrypted-connections.html)：TLS 与证书身份验证。

源文件指纹（用于发现后续结构漂移，不是数据库密码或连接信息）：

| 文件 | SHA-256 |
|---|---|
| `src/card_migration_system/persistence/schema_v1.py` | `9920f313a80ae4f2f8f34711818bdd8088428d2f68d959ed7f85cdc8338405d3` |
| `src/card_migration_system/persistence/worker_health.py` | `18aded42ed6ba5858a0e9d4302daa496b5eb2b16edbef652bb600a3d653b9f91` |
| `src/card_migration_system/persistence/ssm_extractions.py` | `43b234d4708b9108338fa7809ab30e12992884303b00f52f0c655ad31d2f4792` |
| `src/card_migration_system/persistence/generations.py` | `82b4ab65adee1e74e6089dfae84be8e3f19aeac6f013a6d87ea746e8668e0c65` |
| `src/card_migration_system/persistence/provider_generations.py` | `de862e806d97cb8f26eaaa0f6c0e6b858149a8ba8ab32086c60deca88da5438c` |
| `src/card_migration_system/persistence/generation_approvals.py` | `6f79d429c6447603c963ee2934da1facda9261afaadbb14eab7106123f212863` |
| `src/card_migration_system/persistence/migrations.py` | `cc85a5f38660a8c899d8d9455e3d7e0dfbf9b723ae078fcad29443682394a1a7` |
| `migrations/versions/0001_development_slice.py` | `9e177a7b69523a4b4fd9bf3c43baf353a3da2cfaf7eb7b50e0ec21e239461b10` |
| `migrations/versions/0002_worker_health.py` | `0f9ebaf046bbaea3dd5265fcb07551a883473ccc62ae1dc6421c7eb7945b02e5` |
| `migrations/versions/0003_ssm_extractions.py` | `2a09e8486a2539315cad8b136bb8bdc1500d996ba4ab30bed92efb1d6f7fcc2e` |
| `migrations/versions/0004_generation_ledger.py` | `21583f3caf0862ef2357412bfd0ce643ca8913264f67f840a1fbe1050b2a7f8c` |
| `migrations/versions/0005_provider_generation.py` | `84aa1711129c6aa83da5d619a0ae51b1833eee74c0ce74bb7131e50d2cdbddfd` |
| `migrations/versions/0006_generation_approvals.py` | `b3dad8dc783f2258f388109346b3009cd854e3d70a41ad008e90229184d61547` |
| `migrations/versions/0007_modular_migration.py` | `4a8665745540e4284f38207835ecc72f8d0654f9417143bef0012b90d9569b6f` |
