# 给另一台电脑 AI 的完整 MySQL 建库交接 v2

日期：2026-11-18。依据本系统已实现的 **0008_multi_user，共 34 张表**。本文件包含环境确认、全部表／字段／关系、建库 SQL、核验 SQL、权限与网络要求、验收及回报模板。**只把这一份 Markdown 交给另一台 AI 即可**，不需要旧 v1 或本系统源码。附件 SQL／JSON 是对应副本。

## 0. 给接手 AI 的指令与停止条件

你在电脑 B（数据库电脑），电脑 A 运行 CardMigrator 的 Flask API／迁移 Worker。请经用户确认实例、库名、端口、后台电脑 IP 后，创建下述全新空库并核验；不是修改迁移器、调用模型、导入旧实验或发布公网服务。

**账号／权限功能已在 SQLite 实现；MySQL 驱动、连接配置、初始化、事务与备份尚未接入。本文件提供应用后续适配所需的准确表结构，不是“执行 SQL 后现有系统立即可连接”。** 不运行当前 SQLite 专用 init-db 指向 MySQL，不手动填 Alembic 版本行冒充接入完成。

- 目标为 MySQL **8.4 LTS**，不是 MariaDB／MySQL 5.7。其他版本先报告差异，不擅自升级或卸载现有数据库。
- 默认新库名 `cardmigrator_multi_user_staging`。已存在就停止询问；若已建 v1 的 `cardmigrator_staging`，保留它，另建本版库。不做原库原地扩展，不自动导入数据。
- 不使用 IF NOT EXISTS、DROP、TRUNCATE、清库、关闭外键检查或 --force 掩盖失败；不关闭整机防火墙，不授予应用 root 或任意来源 `%`。
- 一条语句报错立即停止，报告错误及已创建内容。DDL 可能逐条提交，不能宣称整批可回滚，不盲目重跑部分成功的脚本。
- 不创建演示用户／默认管理员；真实密码、Cookie、模型 Key、带密码连接串不进入聊天／Git／截图／普通日志。
- 不添加旧草案的 csrf_token_sha256、users.updated_at、source_inputs.user_id 或 migration_jobs.user_id；不擅改幂等唯一键。本版采用独立所有权表与应用端用户范围哈希。

## 1. 执行顺序

1. 只读检查版本、主机、端口、目标库是否已存在、InnoDB、JSON、CHECK 和 utf8mb4_0900_bin 支持。要求会话严格模式 STRICT_TRANS_TABLES 或 STRICT_ALL_TABLES，不忽略截断／转换警告；不擅自修改服务器全局设置。
2. 向用户确认：新库名、操作权限、后台电脑固定内网 IP／受控 VPN 地址、MySQL 端口、专用账号名、TLS 方案。不影响其他软件数据库。
3. 经确认后用建库管理员按第 5 节顺序执行 SQL；也可用同目录 schema_multi_user.sql 批处理，要求遇错停止，不用 --force。不能把 SQLite 文件改后缀或当作 MySQL 数据文件。
4. 执行第 6 节只读核验，对照本文件或 schema_multi_user.json：34 张表及所有字段／约束一致，所有表初始为空，alembic_version 也为空。表数相同不等于完整核对通过。
5. 经允许在**另一个独立的一次性验证库**做第 7 节负例，回滚测试行；准备库保持空。不在准备库加入测试账号、测试任务或存储过程。
6. 按第 8 节配置最小权限账号与来源受限的网络。密码由用户在本机安全设置并单独交接，不放在本文件中。
7. 按第 9 节回报，区分静态核对、实机执行、电脑 A TCP／驱动连接。到此停止，等待电脑 A 完成应用适配，不擅改模型配置、Prompt 或阈值。

连接关系：**浏览器 → 电脑 A 的 Flask API／Worker → 电脑 B 的 MySQL**。浏览器不直连 3306，不持有数据库密码。数据库电脑不需要安装 Vue、Node 或迁移模型；源码和产物仍由电脑 A 保存。

Windows 可把附件放到专用目录，确认客户端、账号和路径后参考下列批处理形式；密码交互输入，不拼进命令。路径示例无空格，实际客户端路径有空格时由操作 AI 正确处理引号：

```powershell
cmd.exe /c "mysql --default-character-set=utf8mb4 --host=127.0.0.1 --port=3306 --user=数据库建库账号 --password --batch --skip-force --skip-reconnect < C:\CardMigratorDB\schema_multi_user.sql"
```

检查退出码和第一条错误，不用 source 命令代替遇错停止批处理；GUI 客户端须明确选择遇错停止。只有本 Markdown 时，把第 5 节 SQL 原样另存 UTF-8 文件。不要为执行成功而删改类型／约束。

环境只读检查：

```sql
SELECT VERSION(), @@hostname, @@port, @@SESSION.sql_mode, @@character_set_server;
SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='cardmigrator_multi_user_staging';
SELECT ENGINE, SUPPORT FROM information_schema.ENGINES WHERE ENGINE='InnoDB';
SELECT COLLATION_NAME, CHARACTER_SET_NAME, PAD_ATTRIBUTE FROM information_schema.COLLATIONS WHERE COLLATION_NAME='utf8mb4_0900_bin';
```

## 2. 数据约定与应用语义

- 保留原 ID 长度，多数为应用生成的 32 字符 UUID hex；80／100 字符 ID 是不透明标识。只有 run_events.id 自增，不用 MySQL UUID() 替代。
- String(n) → VARCHAR(n)，Float → DOUBLE，Integer → 有符号 INTEGER，Boolean → BOOLEAN，JSON → JSON。MySQL BOOLEAN 为数值别名，后台仍须校验布尔输入；不猜测 ENUM、默认值或新增布尔 CHECK。
- 时间保持含小数的 Unix 秒，不改 DATETIME／毫秒／单精度 FLOAT。未来导入前检查 SQLite INTEGER 是否超过 MySQL 32 位范围，超范围停止审查，不截断。
- 采用 utf8mb4_0900_bin，区分大小写及尾随空格；不改为默认不区分大小写或 PAD SPACE 排序规则。外键两侧类型、长度、字符集、排序规则一致，不能用前缀索引替代 PK／UNIQUE。
- JSON 字段非空／SQL NULL 按字典保留；JSON 内 null 不等于 SQL NULL。驱动往返核对中文、数组、布尔、数字、嵌套对象；不以 MySQL 打印的 JSON 文本重算覆盖 request_sha256。
- 登录名由后台转为小写 username_normalized 并唯一。密码保存 Werkzeug scrypt 编码哈希，不用 SHA2、MySQL 账号密码或明文替代；auth_sessions 保存高熵会话摘要，CSRF 从 Cookie 派生，没有草案中的 CSRF 哈希列。
- `users → input_owners → source_inputs`、`users → job_owners → migration_jobs`：所有权独立关联，不改旧请求。输入与任务属于同一用户由后台事务检查，当前无对应复合数据库 FK；历史无 owner 记录只向管理员开放，不自动归给首个用户。
- migration_jobs.idempotency_key 仍全局 UNIQUE，后台把用户 ID 与客户端键一起哈希，实现用户范围幂等。文件、调用、反馈沿 job 所有权授权，不擅改唯一约束。
- user_usage_daily 以 UTC 日期记录准入／调用预留／已知 Tokens；调用预留与开始记录须同事务，未知调用不自动重发，收据重放不重复结算。daily_tokens_soft 不是硬计费封顶，storage_bytes 仅注册源码字节，不是全部文件磁盘配额。
- FK 使用 RESTRICT，保留复合父键与所有 CHECK，不级联删除实验记录。worker_health.run_id、runs.final_revision_id、migration_feedback.revision_sha256、audit_logs.target_id 当前无对应数据库 FK，不凭名字擅加跨表外键。
- Vue／San／SSM／截图／模型调用文件仍在电脑 A 的产物目录，数据库只存登记、路径、摘要等。仅搬数据库不等于搬完文件。
- LangGraph 的 langgraph.sqlite3 由检查点库管理，**不包含在这 34 张业务表中**，不猜建 checkpoints 等表。后续业务库改为 MySQL 可先保留本机 SQLite saver 与单 Worker，不能宣称检查点也已经迁移。
- alembic_version 在准备库保持空。0008_multi_user 是结构依据，不是允许另一台 AI 插入的版本值；电脑 A 的 MySQL 初始化／结构核验通过后，才能由正式流程登记。

## 3. 表清单与关系

包括真实迁移主链、账号功能及兼容代码仍可能读取的历史账本。不能因为网页未展示历史入口就省略对应表。


| 表 | 分组 | 作用 |
| --- | --- | --- |
| `alembic_version` | 版本管理 | 结构迁移版本；交接脚本建空表，不伪造升级完成记录。 |
| `auth_throttle` | 多用户 | 持久化登录限流窗口，bucket 是账号/IP 组合摘要。 |
| `source_inputs` | 共享输入 | 上传源码的路径与内容哈希；源码本体在产物目录。 |
| `users` | 多用户 | 账号、密码哈希、角色、启用与强制改密状态。 |
| `worker_health` | 运行监控 | Worker 心跳；run_id 仅提示当前运行，不是所有权或锁。 |
| `audit_logs` | 多用户 | 账号、安全与关键任务操作审计，不保存明文密码或模型密钥。 |
| `auth_sessions` | 多用户 | 可撤销登录会话；只保存高熵凭据摘要。 |
| `input_owners` | 多用户 | 源码所有者及实际源码字节数；不重写旧输入表。 |
| `migration_jobs` | 当前迁移主链 | 真实 Vue→SSM→San 任务、请求快照、运行状态与版本绑定。 |
| `tasks` | 历史开发夹具 | 旧开发任务，不等同 migration_jobs。 |
| `user_limits` | 多用户 | 按账号限制任务、调用、Token 停止线与已注册源码字节。 |
| `user_usage_daily` | 多用户 | 按 UTC 日记录任务准入、调用预留和已知 Tokens。 |
| `job_owners` | 多用户 | 真实迁移任务所有者；未分配的历史记录只允许管理员访问。 |
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

关系简图（具体 FK 以逐字段约束为准）：

```text
users 1 → N auth_sessions / user_usage_daily / input_owners / job_owners / audit_logs(actor_id)
users 1 → 0..1 user_limits（应用创建账号时同时创建）
source_inputs 1 → 0..1 input_owners；migration_jobs 1 → 0..1 job_owners
source_inputs 1 → N migration_jobs → N migration_files / migration_model_calls / migration_feedback
source_inputs 1 → N tasks → N runs → N artifact_revisions / attempts / evaluations / candidate_decisions / run_events / worker_locks
source_inputs 1 → N ssm_extractions → N ssm_extraction_files / generation_jobs / provider_generation_jobs / generation_approvals
generation_jobs 1 → 0..1 generation_attempts / generation_candidates；1 → N generation_files
provider_generation_jobs 1 → 0..1 provider_generation_attempts；1 → N provider_generation_files
generation_approvals 1 → N generation_approval_files
```

auth_throttle 独立按摘要 bucket 限流；worker_health 是心跳表，不是用户所有权。旧数据允许无 owner，不能把可选关系改成必填并自动归档到新账号。

## 4. 全部字段与约束

除自增事件 ID 外没有数据库生成的业务默认值。NULL／非空、PRIMARY KEY、UNIQUE、FK、CHECK 均按当前模型导出，不补造约束。

### alembic_version

结构迁移版本；交接脚本建空表，不伪造升级完成记录。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `version_num` | VARCHAR(32) | 否 | Alembic 修订号；本交接不填充。；PK |

主键：(version_num)；额外 UNIQUE：无。


### auth_throttle

持久化登录限流窗口，bucket 是账号/IP 组合摘要。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `bucket` | VARCHAR(64) | 否 | 不含明文凭据的登录限流摘要键。；PK |
| `window_start` | DOUBLE | 否 | 限流窗口开始 Unix 秒。 |
| `failures` | INTEGER | 否 | 当前窗口的已预留登录尝试计数。 |

主键：(bucket)；额外 UNIQUE：无。


### source_inputs

上传源码的路径与内容哈希；源码本体在产物目录。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `filename` | VARCHAR(120) | 否 | 源文件名，不是服务器任意路径。 |
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。 |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |

主键：(id)；额外 UNIQUE：无。


### users

账号、密码哈希、角色、启用与强制改密状态。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `username` | VARCHAR(64) | 否 | ASCII 登录名原值。 |
| `username_normalized` | VARCHAR(64) | 否 | 后台小写规范化的唯一登录名。 |
| `display_name` | VARCHAR(120) | 否 | 界面显示名称。 |
| `password_hash` | VARCHAR(255) | 否 | Werkzeug scrypt 编码哈希，不能存明文密码。 |
| `role` | VARCHAR(16) | 否 | admin 或 user，实际权限由后台每次校验。 |
| `is_active` | BOOLEAN | 否 | 账号启用状态。 |
| `must_change_password` | BOOLEAN | 否 | 管理员创建/重置密码后必须先改密。 |
| `created_at` | DOUBLE | 否 | 应用提供的 Unix 秒时间戳，包含小数。 |
| `password_changed_at` | DOUBLE | 否 | 最近改密 Unix 秒。 |

主键：(id)；额外 UNIQUE：(username_normalized)。

CHECK：`role IN ('admin','user')`。


### worker_health

Worker 心跳；run_id 仅提示当前运行，不是所有权或锁。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `pid` | INTEGER | 否 | Worker 进程号。 |
| `state` | VARCHAR(24) | 否 | Worker 状态字符串，或 migration_jobs 的完整运行状态 JSON（以字段类型为准）。 |
| `run_id` | VARCHAR(32) | 是 | 关联旧开发运行；worker_health 中仅作提示。 |
| `last_seen` | DOUBLE | 否 | 最近心跳时间，Unix 秒。 |
| `binding_sha256` | VARCHAR(64) | 否 | Worker 实现绑定摘要。 |

主键：(id)；额外 UNIQUE：无。


### audit_logs

账号、安全与关键任务操作审计，不保存明文密码或模型密钥。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `actor_id` | VARCHAR(32) | 是 | 可选操作者用户 ID；初始化/失败登录可为空。 |
| `action` | VARCHAR(80) | 否 | 当前表的操作类型：安全审计动作，或旧候选接受／回退决策。 |
| `target_id` | VARCHAR(100) | 是 | 被操作对象的不透明 ID，不是数据库外键。 |
| `created_at` | DOUBLE | 否 | 应用提供的 Unix 秒时间戳，包含小数。 |
| `details` | JSON | 否 | 事件详情 JSON。 |

主键：(id)；额外 UNIQUE：无。

- `audit_logs(actor_id)` → `users(id)`。

### auth_sessions

可撤销登录会话；只保存高熵凭据摘要。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `user_id` | VARCHAR(32) | 否 | 关联 users.id；不是由客户端自由指定的所有者。 |
| `token_sha256` | VARCHAR(64) | 否 | 256 位随机登录凭据的 SHA-256 摘要，不是密码哈希。 |
| `origin` | VARCHAR(240) | 否 | 登录绑定的完整同源地址。 |
| `created_at` | DOUBLE | 否 | 应用提供的 Unix 秒时间戳，包含小数。 |
| `expires_at` | DOUBLE | 否 | 到期时间，Unix 秒。 |
| `revoked_at` | DOUBLE | 是 | 撤销时间，NULL 表示尚未撤销。 |

主键：(id)；额外 UNIQUE：(token_sha256)。

- `auth_sessions(user_id)` → `users(id)`。

### input_owners

源码所有者及实际源码字节数；不重写旧输入表。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `input_id` | VARCHAR(32) | 否 | 关联上传源码。；PK |
| `user_id` | VARCHAR(32) | 否 | 关联 users.id；不是由客户端自由指定的所有者。 |
| `byte_size` | INTEGER | 否 | 对应上传源码的实际 UTF-8 字节数。 |

主键：(input_id)；额外 UNIQUE：(user_id, input_id)。

- `input_owners(input_id)` → `source_inputs(id)`。
- `input_owners(user_id)` → `users(id)`。

### migration_jobs

真实 Vue→SSM→San 任务、请求快照、运行状态与版本绑定。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
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

主键：(id)；额外 UNIQUE：(idempotency_key)。

- `migration_jobs(input_id)` → `source_inputs(id)`。

### tasks

旧开发任务，不等同 migration_jobs。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `input_id` | VARCHAR(32) | 否 | 关联上传源码。 |
| `name` | VARCHAR(120) | 否 | 显示名称。 |

主键：(id)；额外 UNIQUE：无。

- `tasks(input_id)` → `source_inputs(id)`。

### user_limits

按账号限制任务、调用、Token 停止线与已注册源码字节。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `user_id` | VARCHAR(32) | 否 | 关联 users.id；不是由客户端自由指定的所有者。；PK |
| `max_active_jobs` | INTEGER | 否 | 排队或执行中任务数上限。 |
| `daily_jobs` | INTEGER | 否 | UTC 日任务准入上限。 |
| `daily_model_calls` | INTEGER | 否 | UTC 日模型调用预留次数上限。 |
| `daily_tokens_soft` | INTEGER | 否 | 已知 Tokens 达线后停止下一调用，非硬计费上限。 |
| `storage_bytes` | INTEGER | 否 | 已注册源码字节上限，不包括生成代码和截图。 |

主键：(user_id)；额外 UNIQUE：无。

CHECK：`max_active_jobs >= 0 AND daily_jobs >= 0 AND daily_model_calls >= 0 AND daily_tokens_soft >= 0 AND storage_bytes >= 0`。

- `user_limits(user_id)` → `users(id)`。

### user_usage_daily

按 UTC 日记录任务准入、调用预留和已知 Tokens。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `user_id` | VARCHAR(32) | 否 | 关联 users.id；不是由客户端自由指定的所有者。；PK |
| `day` | VARCHAR(10) | 否 | UTC 日期 YYYY-MM-DD。；PK |
| `jobs_count` | INTEGER | 否 | 该日成功准入任务数，幂等重试不重复增加。 |
| `calls_count` | INTEGER | 否 | 该日已持久预留的模型调用次数，未知调用也占用。 |
| `known_tokens` | INTEGER | 否 | 实际收据确认的总 Tokens，按调用开始的 UTC 日结算。 |

主键：(user_id, day)；额外 UNIQUE：无。

- `user_usage_daily(user_id)` → `users(id)`。

### job_owners

真实迁移任务所有者；未分配的历史记录只允许管理员访问。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。；PK |
| `user_id` | VARCHAR(32) | 否 | 关联 users.id；不是由客户端自由指定的所有者。 |

主键：(job_id)；额外 UNIQUE：无。

- `job_owners(job_id)` → `migration_jobs(id)`。
- `job_owners(user_id)` → `users(id)`。

### migration_feedback

指定接受产物版本上的人工验收，独立于自动质量结论。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `revision_sha256` | VARCHAR(64) | 否 | 人工确认的接受产物 SHA-256；不是当前数据库外键。 |
| `passed` | BOOLEAN | 否 | 人工验收结果，不覆盖自动质量结论。 |
| `changed_lines` | INTEGER | 是 | 人工修改行数，可为空。 |
| `elapsed_seconds` | DOUBLE | 是 | 人工耗时秒数，可为空。 |
| `notes` | VARCHAR(4000) | 否 | 人工备注，当前最大 4000 字符。 |
| `created_at` | DOUBLE | 否 | 应用提供的 Unix 秒时间戳，包含小数。 |

主键：(id)；额外 UNIQUE：无。

- `migration_feedback(job_id)` → `migration_jobs(id)`。

### migration_files

任务所属文件索引及 SHA-256；不保存文件二进制。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。；PK |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `kind` | VARCHAR(40) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |

主键：(relative_path)；额外 UNIQUE：无。

- `migration_files(job_id)` → `migration_jobs(id)`。

### migration_model_calls

实际模型调用状态、顺序及响应／用量收据。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(80) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `ordinal` | INTEGER | 否 | 同一真实迁移任务内的调用序号，不允许重复。 |
| `status` | VARCHAR(24) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `receipt` | JSON | 是 | 真实调用收据／用量 JSON；未返回时可为空，不得填伪造的零用量。 |
| `started_at` | DOUBLE | 否 | 调用或尝试开始时间，Unix 秒。 |
| `finished_at` | DOUBLE | 是 | 调用结束时间，未完成时可为空。 |

主键：(id)；额外 UNIQUE：(job_id, ordinal)。

- `migration_model_calls(job_id)` → `migration_jobs(id)`。

### runs

旧开发运行、幂等提交与固定请求／版本。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
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

主键：(id)；额外 UNIQUE：(task_id, idempotency_key)。

- `runs(task_id)` → `tasks(id)`。

### artifact_revisions

旧开发产物版本及同一运行内的父子关系。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(80) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `run_id` | VARCHAR(32) | 否 | 关联旧开发运行；worker_health 中仅作提示。 |
| `parent_id` | VARCHAR(80) | 是 | 父产物标识；artifact_revisions 有复合外键，generation_candidates 则 CHECK 必须为空。 |
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。 |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `source_kind` | VARCHAR(40) | 否 | 产物来源，不能把离线测试产物改记成真实模型生成。 |
| `fixture_assertions` | JSON | 否 | 历史夹具验证数据 JSON，不代表真实迁移通过。 |

主键：(id)；额外 UNIQUE：(id, run_id)。

- `artifact_revisions(parent_id, run_id)` → `artifact_revisions(id, run_id)`。
- `artifact_revisions(run_id)` → `runs(id)`。

### attempts

旧开发尝试及响应；不替代真实迁移模型账本。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(100) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `run_id` | VARCHAR(32) | 否 | 关联旧开发运行；worker_health 中仅作提示。 |
| `kind` | VARCHAR(40) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |
| `status` | VARCHAR(24) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `result` | JSON | 是 | 尝试结果 JSON，可为空表示尚未返回等状态。 |
| `started_at` | DOUBLE | 否 | 调用或尝试开始时间，Unix 秒。 |
| `model_tokens` | INTEGER | 是 | 旧尝试的 Token 记录，可为空。 |

主键：(id)；额外 UNIQUE：无。

- `attempts(run_id)` → `runs(id)`。

### run_events

旧开发运行事件；唯一的自增主键表。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | INTEGER | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `run_id` | VARCHAR(32) | 否 | 关联旧开发运行；worker_health 中仅作提示。 |
| `event_key` | VARCHAR(120) | 否 | 同一旧运行内的幂等事件键。 |
| `kind` | VARCHAR(40) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |
| `details` | JSON | 否 | 事件详情 JSON。 |

主键：(id)；额外 UNIQUE：(run_id, event_key)。

- `run_events(run_id)` → `runs(id)`。

### ssm_extractions

注册源码独立提取的请求及状态；当前主链 SSM 也可作为任务文件保存。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `input_id` | VARCHAR(32) | 否 | 关联上传源码。 |
| `referenced_run_id` | VARCHAR(32) | 是 | 可选的旧开发运行引用，不是当前 migration_jobs 外键。 |
| `status` | VARCHAR(24) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `request` | JSON | 否 | 固定请求 JSON；保留原内容、嵌套数据和 Unicode。 |
| `stop_reason` | VARCHAR(100) | 否 | 停止原因代码。 |
| `created_at` | DOUBLE | 否 | 应用提供的 Unix 秒时间戳，包含小数。 |

主键：(id)；额外 UNIQUE：无。

CHECK：`status IN ('prepared','started','received','completed','blocked','review_required')`。

- `ssm_extractions(input_id)` → `source_inputs(id)`。
- `ssm_extractions(referenced_run_id)` → `runs(id)`。

### worker_locks

旧开发 Worker 租约，不能当作跨机器任务调度方案。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(20) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `owner` | VARCHAR(32) | 否 | Worker 租约持有者标识，不是用户 ID。 |
| `run_id` | VARCHAR(32) | 否 | 关联旧开发运行；worker_health 中仅作提示。 |
| `expires_at` | DOUBLE | 否 | 到期时间，Unix 秒。 |

主键：(id)；额外 UNIQUE：无。

- `worker_locks(run_id)` → `runs(id)`。

### candidate_decisions

旧开发候选接受／回退关系。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(100) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `run_id` | VARCHAR(32) | 否 | 关联旧开发运行；worker_health 中仅作提示。 |
| `previous_id` | VARCHAR(80) | 否 | 候选之前的接受产物标识。 |
| `candidate_id` | VARCHAR(80) | 否 | 本次候选产物标识。 |
| `action` | VARCHAR(24) | 否 | 当前表的操作类型：安全审计动作，或旧候选接受／回退决策。 |
| `reason` | VARCHAR(120) | 否 | 决策原因代码。 |

主键：(id)；额外 UNIQUE：无。

- `candidate_decisions(candidate_id, run_id)` → `artifact_revisions(id, run_id)`。
- `candidate_decisions(previous_id, run_id)` → `artifact_revisions(id, run_id)`。
- `candidate_decisions(run_id)` → `runs(id)`。

### evaluations

旧开发评估记录，不等同真实迁移的 assessment。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(100) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `run_id` | VARCHAR(32) | 否 | 关联旧开发运行；worker_health 中仅作提示。 |
| `revision_id` | VARCHAR(80) | 否 | 被评估产物版本。 |
| `status` | VARCHAR(32) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `scope` | VARCHAR(80) | 否 | 旧评估的范围标识。 |
| `fixture_assertions` | JSON | 否 | 历史夹具验证数据 JSON，不代表真实迁移通过。 |

主键：(id)；额外 UNIQUE：无。

- `evaluations(revision_id, run_id)` → `artifact_revisions(id, run_id)`。
- `evaluations(run_id)` → `runs(id)`。

### generation_approvals

单一生成计划的审批、过期与使用状态。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `extraction_id` | VARCHAR(32) | 否 | 关联独立 SSM 提取记录。 |
| `idempotency_key` | VARCHAR(80) | 否 | 幂等提交标识；唯一作用域见各表约束。 |
| `request` | JSON | 否 | 固定请求 JSON；保留原内容、嵌套数据和 Unicode。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `status` | VARCHAR(16) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `created_at` | DOUBLE | 否 | 应用提供的 Unix 秒时间戳，包含小数。 |
| `expires_at` | DOUBLE | 否 | 到期时间，Unix 秒。 |

主键：(id)；额外 UNIQUE：(extraction_id, idempotency_key)。

CHECK：`status IN ('pending','approved','revoked','consumed')`。

- `generation_approvals(extraction_id)` → `ssm_extractions(id)`。

### generation_jobs

离线测试生成请求，不是在线模型迁移任务。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `extraction_id` | VARCHAR(32) | 否 | 关联独立 SSM 提取记录。 |
| `input_id` | VARCHAR(32) | 否 | 关联上传源码。 |
| `idempotency_key` | VARCHAR(80) | 否 | 幂等提交标识；唯一作用域见各表约束。 |
| `status` | VARCHAR(24) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `request` | JSON | 否 | 固定请求 JSON；保留原内容、嵌套数据和 Unicode。 |
| `stop_reason` | VARCHAR(100) | 否 | 停止原因代码。 |
| `created_at` | DOUBLE | 否 | 应用提供的 Unix 秒时间戳，包含小数。 |

主键：(id)；额外 UNIQUE：(extraction_id, idempotency_key)。

CHECK：`status IN ('prepared','started','received','completed','blocked','review_required')`。

- `generation_jobs(extraction_id)` → `ssm_extractions(id)`。
- `generation_jobs(input_id)` → `source_inputs(id)`。

### provider_generation_jobs

记录式提供方生成请求，不混入离线候选来源。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `extraction_id` | VARCHAR(32) | 否 | 关联独立 SSM 提取记录。 |
| `idempotency_key` | VARCHAR(80) | 否 | 幂等提交标识；唯一作用域见各表约束。 |
| `request` | JSON | 否 | 固定请求 JSON；保留原内容、嵌套数据和 Unicode。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `status` | VARCHAR(24) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `stop_reason` | VARCHAR(100) | 否 | 停止原因代码。 |
| `created_at` | DOUBLE | 否 | 应用提供的 Unix 秒时间戳，包含小数。 |

主键：(id)；额外 UNIQUE：(extraction_id, idempotency_key)。

CHECK：`status IN ('prepared','started','received','completed','blocked','review_required')`。

- `provider_generation_jobs(extraction_id)` → `ssm_extractions(id)`。

### ssm_extraction_files

独立提取的 request／ssm／receipt 文件索引。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。；PK |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `extraction_id` | VARCHAR(32) | 否 | 关联独立 SSM 提取记录。 |
| `kind` | VARCHAR(16) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |

主键：(relative_path)；额外 UNIQUE：(extraction_id, kind)。

CHECK：`kind IN ('request','ssm','receipt')`。

- `ssm_extraction_files(extraction_id)` → `ssm_extractions(id)`。

### generation_approval_files

审批、撤销和领取证据文件索引。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。；PK |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `approval_id` | VARCHAR(32) | 否 | 关联生成审批。 |
| `kind` | VARCHAR(16) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |

主键：(relative_path)；额外 UNIQUE：(approval_id, kind)。

CHECK：`kind IN ('request','approval','revocation','claim')`。

- `generation_approval_files(approval_id)` → `generation_approvals(id)`。

### generation_attempts

每个离线生成任务最多一个尝试。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(80) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `status` | VARCHAR(24) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `started_at` | DOUBLE | 否 | 调用或尝试开始时间，Unix 秒。 |

主键：(id)；额外 UNIQUE：(job_id)。

CHECK：`status IN ('started','received','review_required')`。

- `generation_attempts(job_id)` → `generation_jobs(id)`。

### generation_files

离线生成文件索引。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。；PK |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `kind` | VARCHAR(16) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |

主键：(relative_path)；额外 UNIQUE：(job_id, kind)。

CHECK：`kind IN ('request','receipt','candidate')`。

- `generation_files(job_id)` → `generation_jobs(id)`。

### provider_generation_attempts

每个记录式生成任务最多一个尝试。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(80) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `request_sha256` | VARCHAR(64) | 否 | 固定请求摘要，不能因更换数据库重新计算覆盖历史。 |
| `status` | VARCHAR(24) | 否 | 当前账本状态字符串；已有 CHECK 或应用约束见下。 |
| `started_at` | DOUBLE | 否 | 调用或尝试开始时间，Unix 秒。 |

主键：(id)；额外 UNIQUE：(job_id)。

CHECK：`status IN ('started','received','review_required')`。

- `provider_generation_attempts(job_id)` → `provider_generation_jobs(id)`。

### provider_generation_files

计划、请求、响应、收据与候选文件索引。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。；PK |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `kind` | VARCHAR(16) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |

主键：(relative_path)；额外 UNIQUE：(job_id, kind)。

CHECK：`kind IN ('plan','request','response','receipt','candidate')`。

- `provider_generation_files(job_id)` → `provider_generation_jobs(id)`。

### generation_candidates

离线测试候选；parent_id 必须为空，来源固定。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(80) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。 |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `parent_id` | VARCHAR(80) | 是 | 父产物标识；artifact_revisions 有复合外键，generation_candidates 则 CHECK 必须为空。 |
| `source_kind` | VARCHAR(32) | 否 | 产物来源，不能把离线测试产物改记成真实模型生成。 |

主键：(id)；额外 UNIQUE：(job_id)；(relative_path)。

CHECK：`parent_id IS NULL`；`source_kind = 'offline_client_test'`。

- `generation_candidates(job_id)` → `generation_jobs(id)`。
- `generation_candidates(relative_path)` → `generation_files(relative_path)`。

## 5. 完整建库 SQL（仅新的空准备库）

包含全部 34 表；不插入用户、版本或业务数据。确认目标实例后执行，遇错停止。

```sql
-- FUTURE MYSQL PREPARATION ONLY. Runtime is currently tested on SQLite.
CREATE DATABASE `cardmigrator_multi_user_staging` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;
USE `cardmigrator_multi_user_staging`;

CREATE TABLE `alembic_version` (
  `version_num` VARCHAR(32) NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `auth_throttle` (
  `bucket` VARCHAR(64) NOT NULL,
  `window_start` DOUBLE NOT NULL,
  `failures` INTEGER NOT NULL,
  PRIMARY KEY (`bucket`)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `source_inputs` (
  `id` VARCHAR(32) NOT NULL,
  `filename` VARCHAR(120) NOT NULL,
  `relative_path` VARCHAR(240) NOT NULL,
  `sha256` VARCHAR(64) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `users` (
  `id` VARCHAR(32) NOT NULL,
  `username` VARCHAR(64) NOT NULL,
  `username_normalized` VARCHAR(64) NOT NULL,
  `display_name` VARCHAR(120) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `role` VARCHAR(16) NOT NULL,
  `is_active` BOOLEAN NOT NULL,
  `must_change_password` BOOLEAN NOT NULL,
  `created_at` DOUBLE NOT NULL,
  `password_changed_at` DOUBLE NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_users_1` UNIQUE (`username_normalized`),
  CONSTRAINT `ck_users_1` CHECK (role IN ('admin','user'))
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

CREATE TABLE `audit_logs` (
  `id` VARCHAR(32) NOT NULL,
  `actor_id` VARCHAR(32) NULL,
  `action` VARCHAR(80) NOT NULL,
  `target_id` VARCHAR(100) NULL,
  `created_at` DOUBLE NOT NULL,
  `details` JSON NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_audit_logs_1` FOREIGN KEY (`actor_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `auth_sessions` (
  `id` VARCHAR(32) NOT NULL,
  `user_id` VARCHAR(32) NOT NULL,
  `token_sha256` VARCHAR(64) NOT NULL,
  `origin` VARCHAR(240) NOT NULL,
  `created_at` DOUBLE NOT NULL,
  `expires_at` DOUBLE NOT NULL,
  `revoked_at` DOUBLE NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_auth_sessions_1` UNIQUE (`token_sha256`),
  CONSTRAINT `fk_auth_sessions_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `input_owners` (
  `input_id` VARCHAR(32) NOT NULL,
  `user_id` VARCHAR(32) NOT NULL,
  `byte_size` INTEGER NOT NULL,
  PRIMARY KEY (`input_id`),
  CONSTRAINT `uq_input_owners_1` UNIQUE (`user_id`, `input_id`),
  CONSTRAINT `fk_input_owners_1` FOREIGN KEY (`input_id`) REFERENCES `source_inputs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_input_owners_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
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

CREATE TABLE `user_limits` (
  `user_id` VARCHAR(32) NOT NULL,
  `max_active_jobs` INTEGER NOT NULL,
  `daily_jobs` INTEGER NOT NULL,
  `daily_model_calls` INTEGER NOT NULL,
  `daily_tokens_soft` INTEGER NOT NULL,
  `storage_bytes` INTEGER NOT NULL,
  PRIMARY KEY (`user_id`),
  CONSTRAINT `fk_user_limits_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_user_limits_1` CHECK (max_active_jobs >= 0 AND daily_jobs >= 0 AND daily_model_calls >= 0 AND daily_tokens_soft >= 0 AND storage_bytes >= 0)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `user_usage_daily` (
  `user_id` VARCHAR(32) NOT NULL,
  `day` VARCHAR(10) NOT NULL,
  `jobs_count` INTEGER NOT NULL,
  `calls_count` INTEGER NOT NULL,
  `known_tokens` INTEGER NOT NULL,
  PRIMARY KEY (`user_id`, `day`),
  CONSTRAINT `fk_user_usage_daily_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE `job_owners` (
  `job_id` VARCHAR(32) NOT NULL,
  `user_id` VARCHAR(32) NOT NULL,
  PRIMARY KEY (`job_id`),
  CONSTRAINT `fk_job_owners_1` FOREIGN KEY (`job_id`) REFERENCES `migration_jobs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_job_owners_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
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

## 6. 完整只读核验 SQL

建表成功后执行，所有业务表和版本表必须为空。不能代替第 7 节约束实测。

```sql
-- Read-only; expect 34 tables, zero missing/extra tables and zero rows in every table.
SELECT VERSION() AS mysql_version, @@hostname AS db_host, @@port AS db_port, @@SESSION.sql_mode AS sql_mode;
SELECT SCHEMA_NAME, DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='cardmigrator_multi_user_staging';
SELECT COLLATION_NAME, PAD_ATTRIBUTE FROM information_schema.COLLATIONS WHERE COLLATION_NAME='utf8mb4_0900_bin';
SELECT COUNT(*) AS table_count_must_be_34 FROM information_schema.TABLES WHERE TABLE_SCHEMA='cardmigrator_multi_user_staging' AND TABLE_TYPE='BASE TABLE';
WITH expected AS (
SELECT 'alembic_version' AS table_name
UNION ALL
SELECT 'auth_throttle' AS table_name
UNION ALL
SELECT 'source_inputs' AS table_name
UNION ALL
SELECT 'users' AS table_name
UNION ALL
SELECT 'worker_health' AS table_name
UNION ALL
SELECT 'audit_logs' AS table_name
UNION ALL
SELECT 'auth_sessions' AS table_name
UNION ALL
SELECT 'input_owners' AS table_name
UNION ALL
SELECT 'migration_jobs' AS table_name
UNION ALL
SELECT 'tasks' AS table_name
UNION ALL
SELECT 'user_limits' AS table_name
UNION ALL
SELECT 'user_usage_daily' AS table_name
UNION ALL
SELECT 'job_owners' AS table_name
UNION ALL
SELECT 'migration_feedback' AS table_name
UNION ALL
SELECT 'migration_files' AS table_name
UNION ALL
SELECT 'migration_model_calls' AS table_name
UNION ALL
SELECT 'runs' AS table_name
UNION ALL
SELECT 'artifact_revisions' AS table_name
UNION ALL
SELECT 'attempts' AS table_name
UNION ALL
SELECT 'run_events' AS table_name
UNION ALL
SELECT 'ssm_extractions' AS table_name
UNION ALL
SELECT 'worker_locks' AS table_name
UNION ALL
SELECT 'candidate_decisions' AS table_name
UNION ALL
SELECT 'evaluations' AS table_name
UNION ALL
SELECT 'generation_approvals' AS table_name
UNION ALL
SELECT 'generation_jobs' AS table_name
UNION ALL
SELECT 'provider_generation_jobs' AS table_name
UNION ALL
SELECT 'ssm_extraction_files' AS table_name
UNION ALL
SELECT 'generation_approval_files' AS table_name
UNION ALL
SELECT 'generation_attempts' AS table_name
UNION ALL
SELECT 'generation_files' AS table_name
UNION ALL
SELECT 'provider_generation_attempts' AS table_name
UNION ALL
SELECT 'provider_generation_files' AS table_name
UNION ALL
SELECT 'generation_candidates' AS table_name
)
SELECT e.table_name AS missing_table FROM expected e LEFT JOIN information_schema.TABLES t ON t.TABLE_SCHEMA='cardmigrator_multi_user_staging' AND t.TABLE_NAME=e.table_name AND t.TABLE_TYPE='BASE TABLE' WHERE t.TABLE_NAME IS NULL;
WITH expected AS (
SELECT 'alembic_version' AS table_name
UNION ALL
SELECT 'auth_throttle' AS table_name
UNION ALL
SELECT 'source_inputs' AS table_name
UNION ALL
SELECT 'users' AS table_name
UNION ALL
SELECT 'worker_health' AS table_name
UNION ALL
SELECT 'audit_logs' AS table_name
UNION ALL
SELECT 'auth_sessions' AS table_name
UNION ALL
SELECT 'input_owners' AS table_name
UNION ALL
SELECT 'migration_jobs' AS table_name
UNION ALL
SELECT 'tasks' AS table_name
UNION ALL
SELECT 'user_limits' AS table_name
UNION ALL
SELECT 'user_usage_daily' AS table_name
UNION ALL
SELECT 'job_owners' AS table_name
UNION ALL
SELECT 'migration_feedback' AS table_name
UNION ALL
SELECT 'migration_files' AS table_name
UNION ALL
SELECT 'migration_model_calls' AS table_name
UNION ALL
SELECT 'runs' AS table_name
UNION ALL
SELECT 'artifact_revisions' AS table_name
UNION ALL
SELECT 'attempts' AS table_name
UNION ALL
SELECT 'run_events' AS table_name
UNION ALL
SELECT 'ssm_extractions' AS table_name
UNION ALL
SELECT 'worker_locks' AS table_name
UNION ALL
SELECT 'candidate_decisions' AS table_name
UNION ALL
SELECT 'evaluations' AS table_name
UNION ALL
SELECT 'generation_approvals' AS table_name
UNION ALL
SELECT 'generation_jobs' AS table_name
UNION ALL
SELECT 'provider_generation_jobs' AS table_name
UNION ALL
SELECT 'ssm_extraction_files' AS table_name
UNION ALL
SELECT 'generation_approval_files' AS table_name
UNION ALL
SELECT 'generation_attempts' AS table_name
UNION ALL
SELECT 'generation_files' AS table_name
UNION ALL
SELECT 'provider_generation_attempts' AS table_name
UNION ALL
SELECT 'provider_generation_files' AS table_name
UNION ALL
SELECT 'generation_candidates' AS table_name
)
SELECT t.TABLE_NAME AS unexpected_table FROM information_schema.TABLES t LEFT JOIN expected e ON e.table_name=t.TABLE_NAME WHERE t.TABLE_SCHEMA='cardmigrator_multi_user_staging' AND t.TABLE_TYPE='BASE TABLE' AND e.table_name IS NULL;
SELECT TABLE_NAME, ENGINE, TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA='cardmigrator_multi_user_staging' ORDER BY TABLE_NAME;
SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA, CHARACTER_SET_NAME, COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='cardmigrator_multi_user_staging' ORDER BY TABLE_NAME, ORDINAL_POSITION;
SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE, ENFORCED FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA='cardmigrator_multi_user_staging' ORDER BY TABLE_NAME, CONSTRAINT_NAME;
SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, ORDINAL_POSITION, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE CONSTRAINT_SCHEMA='cardmigrator_multi_user_staging' ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION;
SELECT TABLE_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, UPDATE_RULE, DELETE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA='cardmigrator_multi_user_staging' ORDER BY TABLE_NAME, CONSTRAINT_NAME;
SELECT tc.TABLE_NAME, cc.CONSTRAINT_NAME, cc.CHECK_CLAUSE FROM information_schema.CHECK_CONSTRAINTS cc JOIN information_schema.TABLE_CONSTRAINTS tc ON tc.CONSTRAINT_SCHEMA=cc.CONSTRAINT_SCHEMA AND tc.CONSTRAINT_NAME=cc.CONSTRAINT_NAME WHERE tc.CONSTRAINT_SCHEMA='cardmigrator_multi_user_staging' ORDER BY tc.TABLE_NAME, cc.CONSTRAINT_NAME;
SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME, SUB_PART FROM information_schema.STATISTICS WHERE TABLE_SCHEMA='cardmigrator_multi_user_staging' ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;
SELECT 'alembic_version' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`alembic_version`
UNION ALL
SELECT 'auth_throttle' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`auth_throttle`
UNION ALL
SELECT 'source_inputs' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`source_inputs`
UNION ALL
SELECT 'users' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`users`
UNION ALL
SELECT 'worker_health' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`worker_health`
UNION ALL
SELECT 'audit_logs' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`audit_logs`
UNION ALL
SELECT 'auth_sessions' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`auth_sessions`
UNION ALL
SELECT 'input_owners' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`input_owners`
UNION ALL
SELECT 'migration_jobs' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`migration_jobs`
UNION ALL
SELECT 'tasks' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`tasks`
UNION ALL
SELECT 'user_limits' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`user_limits`
UNION ALL
SELECT 'user_usage_daily' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`user_usage_daily`
UNION ALL
SELECT 'job_owners' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`job_owners`
UNION ALL
SELECT 'migration_feedback' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`migration_feedback`
UNION ALL
SELECT 'migration_files' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`migration_files`
UNION ALL
SELECT 'migration_model_calls' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`migration_model_calls`
UNION ALL
SELECT 'runs' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`runs`
UNION ALL
SELECT 'artifact_revisions' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`artifact_revisions`
UNION ALL
SELECT 'attempts' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`attempts`
UNION ALL
SELECT 'run_events' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`run_events`
UNION ALL
SELECT 'ssm_extractions' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`ssm_extractions`
UNION ALL
SELECT 'worker_locks' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`worker_locks`
UNION ALL
SELECT 'candidate_decisions' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`candidate_decisions`
UNION ALL
SELECT 'evaluations' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`evaluations`
UNION ALL
SELECT 'generation_approvals' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`generation_approvals`
UNION ALL
SELECT 'generation_jobs' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`generation_jobs`
UNION ALL
SELECT 'provider_generation_jobs' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`provider_generation_jobs`
UNION ALL
SELECT 'ssm_extraction_files' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`ssm_extraction_files`
UNION ALL
SELECT 'generation_approval_files' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`generation_approval_files`
UNION ALL
SELECT 'generation_attempts' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`generation_attempts`
UNION ALL
SELECT 'generation_files' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`generation_files`
UNION ALL
SELECT 'provider_generation_attempts' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`provider_generation_attempts`
UNION ALL
SELECT 'provider_generation_files' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`provider_generation_files`
UNION ALL
SELECT 'generation_candidates' AS table_name, COUNT(*) AS rows_must_be_zero FROM `cardmigrator_multi_user_staging`.`generation_candidates`;
SELECT COUNT(*) AS alembic_rows_must_be_zero FROM `cardmigrator_multi_user_staging`.alembic_version;
```

## 7. MySQL 实机验收与负例

先完成第 6 节：缺失／额外表查询均零行；所有 34 张表及版本表初始行数为 0；逐表核对字段顺序、长度、NULL、PK、UNIQUE、FK、CHECK（ENFORCED=YES）、InnoDB、排序规则、自增项。MySQL 自动生成 FK 索引正常，但不能用前缀索引代替完整唯一键。

以下仅经允许在另一个一次性验证库执行，事务回滚测试行，不向准备库写测试数据；不关闭外键检查。记录期望／实际结果和约束名，不输出真实密码或源码：

| 验证 | 预期 |
| --- | --- |
| users.username_normalized 重复 | UNIQUE 拒绝；规范化由应用完成，不能期待 bin 排序自动 lower |
| users.role 非 user/admin | CHECK 拒绝 |
| auth_sessions.user_id 无父用户／token_sha256 重复 | FK／UNIQUE 拒绝 |
| user_limits 任意额度负数 | CHECK 拒绝 |
| user_usage_daily 同 (user_id,day) 重复 | 复合 PK 拒绝 |
| input_owners／job_owners 的输入／任务／用户不存在 | FK 拒绝 |
| migration_model_calls 同 (job_id,ordinal) 重复 | UNIQUE 拒绝 |
| artifact_revisions 父版本、evaluations／candidate_decisions 版本属于另一 run | 复合 FK 拒绝 |
| ssm_extractions 非法状态、generation_candidates 错误来源或非空 parent_id | 既有 CHECK 拒绝 |
| 文件路径／测试标识仅大小写或尾随空格不同 | 不因排序规则被错误合并；utf8mb4_0900_bin 应为 NO PAD |
| Unix 小数秒、中文／emoji／数组／嵌套 JSON、SQL NULL 与 JSON null | 不静默截断，后续驱动往返与应用语义一致 |

数据库不能单独保证密码长度、输入／任务同一用户、用户隔离和额度并发协议，它们仍有后台逻辑。users.role 的 CHECK 不是 MySQL 账号权限。

## 8. 网络与最小权限

- 建库／迁移管理员只由运维使用；应用专用账号仅对本库具备 SELECT、INSERT、UPDATE、DELETE，不授予 root、全局权限、FILE、GRANT OPTION 或日常 DDL。
- 只允许电脑 A 的固定内网 IP／受控 VPN 来源，不使用 '%'；监听受控接口，防火墙只放行后台电脑到指定端口，不向整个互联网开放 3306。
- 跨机部署配置 TLS，客户端验证 CA 与服务器身份；不关闭验证掩盖证书错误。若暂在受控内网验证且 TLS 未完成，明确回报未完成，不冒充加密连接。
- 数据库专用账号独立于本系统网页登录账号、临时密码和模型 Key。密码由用户在本机安全设置并单独交接，不进入仓库或回报模板。
- 电脑 A 可执行 `Test-NetConnection -ComputerName <电脑B内网地址> -Port <MySQL端口>` 验证 TCP；不代表账号、SQL 权限、TLS 或应用已接入。
- 登录认证不等于源码沙箱。系统当前是受邀可信账号、单服务器单 Worker；公网执行隔离另行部署。

## 9. 另一台 AI 的非敏感回报模板

```text
交接版本：mysql_handoff_v2 / 0008_multi_user / 34 表
MySQL 完整版本／平台：
数据库电脑内网 IP 或受控域名：
端口：
准备库名：cardmigrator_multi_user_staging
应用专用 MySQL 账号名（不含密码）：
允许的后台电脑来源 IP：
TLS／CA／服务器身份验证：已验证／未验证及原因
表名／字段／PK／UNIQUE／FK／CHECK／排序规则核对：通过项和差异
实际表数／预期：___ / 34
所有表和 alembic_version 是否保持空：
失败 SQL／错误码／约束名和已创建结构：
独立验证库负例及 JSON／时间戳往返：实际结果，未执行就写未执行
应用专用账号权限：仅本库 DML／仍待验证
电脑 A 连接验证：未验证／仅 TCP／驱动鉴权／TLS
是否修改旧库／导入真实数据／填充 Alembic 版本：应为否
密码交接方式：安全渠道名称即可，不填写密码
仍待电脑 A：驱动／配置／初始化、MySQL 事务锁与额度并发、备份恢复、检查点策略、端到端回归
```

不回传密码、密码哈希、Cookie、模型 Key 或完整业务数据。真实数据迁移须另立导入方案，不把空库准备扩大为数据迁移授权。

## 10. 电脑 A 的后续应用接入清单（本次建库不自动执行）

1. 固定版本 MySQL 驱动及 URL／凭据环境变量配置，API 与 Worker 使用同一业务库；不向网页暴露数据库密码。
2. 分离 SQLite／MySQL 初始化、schema 核对和 Alembic 登记。当前 database.py 固定 sqlite URL、PRAGMA、BEGIN IMMEDIATE，不能直接沿用。
3. 改造短事务、隔离级别、行锁及幂等冲突处理；回归所有者检查、并发任务准入、调用预留／结算、未知用量阻断及账号切换。不能把 BEGIN IMMEDIATE 换名当作 MySQL 同等锁。
4. 备份恢复覆盖 MySQL 业务库＋已注册文件＋受控检查点的一致性，恢复继续撤销旧会话。现有 sqlite3 backup／PRAGMA 校验不适用于远端 MySQL。
5. 保持单 Worker／本机执行锁；未经验证不启用多台 Worker 或声称有分布式调度。
6. 未来导入 SQLite 数据前备份、检查字段范围并验证驱动 JSON 往返；不改原请求、哈希、binding 或实际费用，不将旧失败改判。
7. Flask 登录／权限、文件下载、LangGraph 主链、模型账本、取消／恢复与错误分支全部回归后才切换。先用显式假模型避免重复付费，另行授权真实验收。

## 11. 来源与已验证范围

由 persistence metadata 及 0001—0008 增量迁移只读导出。源端用临时 Alembic SQLite 对照字段／约束；MySQL 方言静态编译不等于真实服务器执行。本轮未连接电脑 B、未导入真实数据；MySQL 实机结果由电脑 B 回报。

官方参考（MySQL 8.4）：

- [外键要求](https://dev.mysql.com/doc/refman/8.4/en/create-table-foreign-keys.html)
- [CHECK 约束](https://dev.mysql.com/doc/refman/8.4/en/create-table-check-constraints.html)、[ENFORCED 核对](https://dev.mysql.com/doc/refman/8.4/en/information-schema-table-constraints-table.html)
- [二进制排序规则与尾随空格](https://dev.mysql.com/doc/refman/8.4/en/charset-binary-collations.html)
- [mysql 客户端选项](https://dev.mysql.com/doc/refman/8.4/en/mysql-command-options.html)
- [TLS 加密连接](https://dev.mysql.com/doc/refman/8.4/en/using-encrypted-connections.html)

源文件指纹用于发现结构漂移，不含用户记录或配置密钥：

| 文件 | SHA-256 |
| --- | --- |

| `src/card_migration_system/persistence/schema_v1.py` | `9920f313a80ae4f2f8f34711818bdd8088428d2f68d959ed7f85cdc8338405d3` |
| `src/card_migration_system/persistence/worker_health.py` | `18aded42ed6ba5858a0e9d4302daa496b5eb2b16edbef652bb600a3d653b9f91` |
| `src/card_migration_system/persistence/ssm_extractions.py` | `43b234d4708b9108338fa7809ab30e12992884303b00f52f0c655ad31d2f4792` |
| `src/card_migration_system/persistence/generations.py` | `82b4ab65adee1e74e6089dfae84be8e3f19aeac6f013a6d87ea746e8668e0c65` |
| `src/card_migration_system/persistence/provider_generations.py` | `de862e806d97cb8f26eaaa0f6c0e6b858149a8ba8ab32086c60deca88da5438c` |
| `src/card_migration_system/persistence/generation_approvals.py` | `6f79d429c6447603c963ee2934da1facda9261afaadbb14eab7106123f212863` |
| `src/card_migration_system/persistence/migrations.py` | `cc85a5f38660a8c899d8d9455e3d7e0dfbf9b723ae078fcad29443682394a1a7` |
| `src/card_migration_system/persistence/accounts.py` | `afbba90b9cdb911b3ed470dd7d2c88d8fc78ae9826d920d3af59255d120e6af1` |
| `migrations/versions/0001_development_slice.py` | `9e177a7b69523a4b4fd9bf3c43baf353a3da2cfaf7eb7b50e0ec21e239461b10` |
| `migrations/versions/0002_worker_health.py` | `0f9ebaf046bbaea3dd5265fcb07551a883473ccc62ae1dc6421c7eb7945b02e5` |
| `migrations/versions/0003_ssm_extractions.py` | `2a09e8486a2539315cad8b136bb8bdc1500d996ba4ab30bed92efb1d6f7fcc2e` |
| `migrations/versions/0004_generation_ledger.py` | `21583f3caf0862ef2357412bfd0ce643ca8913264f67f840a1fbe1050b2a7f8c` |
| `migrations/versions/0005_provider_generation.py` | `84aa1711129c6aa83da5d619a0ae51b1833eee74c0ce74bb7131e50d2cdbddfd` |
| `migrations/versions/0006_generation_approvals.py` | `b3dad8dc783f2258f388109346b3009cd854e3d70a41ad008e90229184d61547` |
| `migrations/versions/0007_modular_migration.py` | `4a8665745540e4284f38207835ecc72f8d0654f9417143bef0012b90d9569b6f` |
| `migrations/versions/0008_multi_user.py` | `2a51be21fbbea07e59b2335d05a7139e2eef1ec80dd0daa8c496878aecb7d7ef` |
