# 多用户数据库交接 v2：与 SQLite 0008 实现对齐

日期：2026-11-18。此文件替代 v1 草案用于后续 MySQL 适配：users、会话、所有权、额度、审计与限流已在本电脑的 SQLite 实现；**MySQL 驱动、初始化、事务、备份与检查点仍未适配，不代表切换连接串即可使用。**

仅允许另一台 AI 经确认后，在 MySQL 8.4 的全新 `cardmigrator_multi_user_staging` 准备库执行下方 SQL；不得覆盖 v1 准备库、原 SQLite 或任何现有库。遇到同名库/语句失败立即停止，不用 IF NOT EXISTS、关闭外键检查或删表掩盖错误。DDL 不保证整批回滚。密码、模型 Key、演示用户和 Alembic 版本行不包含在 SQL 中。

本文件可单独交给另一台 AI；同目录 SQL/JSON 是对应副本。网络监听、最小权限账号、TLS、验收和非敏感回报模板继续参考 v1 第 1、8、9 节，但**本版表数与字段以本文件为准**。另一个 AI 不应执行 v1 第 7 节旧草案，尤其不能另加已被实现替代的字段。

## 结构与边界

- 保留原 26 张基线表，再新增 8 张账号相关表，共 34 张。不修改旧 request、binding、哈希或实验来源。
- `users → input_owners → source_inputs`，`users → job_owners → migration_jobs`。创建任务时后台在事务中验证源码所属账号与任务账号相同；当前没有为此新增复合数据库 FK，不要误称数据库单独证明了所有权。
- `users → auth_sessions / user_limits / user_usage_daily / audit_logs(actor_id)`。audit_logs.target_id 是不透明审计对象，不是所有表的通用外键。
- 任务文件、模型调用和人工反馈沿 job 所有权鉴权；历史无 owner 的记录仅管理员访问，不自动分配。
- 任务表仍是全局 UNIQUE(idempotency_key)，后台把用户 ID 与客户端幂等键一起哈希后保存，实现用户范围内幂等；不擅自用草案的复合唯一键替换。
- Auth Cookie 明文不入库；CSRF 从当前随机 Cookie 凭据派生并校验，不存在草案中的 csrf_token_sha256 列。账号密码使用 scrypt；登录 token 的 SHA-256 不是密码存储方案。
- user_usage_daily 的调用次数在模型发出前与调用开始记录同事务预留；响应未知/用量未知阻断该用户后续调用，重放收据不重复结算。Token 限制是软停止线，源码配额不包含全部产物。
- Float 映射为 DOUBLE 保持 Unix 秒精度；INTEGER 为有符号 32 位，后续搬迁若有超范围值必须先审查，不截断。字符串保持原长度与区分大小写的 utf8mb4_0900_bin。保留 JSON、NULL、CHECK、UNIQUE 和 FK，引用删除使用 RESTRICT。
- Vue/San/SSM/截图等文件仍在应用产物目录，数据库不是文件备份。LangGraph 检查点仍由 SQLite saver 管理，不手工猜建检查点表。
- alembic_version 在准备库保持空表，不能手动 stamp 为 0008 冒充完成 MySQL 接入；实际升级由后续已验证的迁移流程执行。
- 用户初始数据应由应用 init-admin 隐藏密码提示和管理界面创建，不在 SQL 中填默认管理员/明文密码。

## 字段与约束

### alembic_version

结构迁移版本；交接脚本建空表，不伪造升级完成记录。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `version_num` | VARCHAR(32) | 否 | Alembic 修订号；本交接不填充。；PK |

UNIQUE：[]；CHECK：[]。


### auth_throttle

持久化登录限流窗口，bucket 是账号/IP 组合摘要。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `bucket` | VARCHAR(64) | 否 | 不含明文凭据的登录限流摘要键。；PK |
| `window_start` | DOUBLE | 否 | 限流窗口开始 Unix 秒。 |
| `failures` | INTEGER | 否 | 当前窗口的已预留登录尝试计数。 |

UNIQUE：[]；CHECK：[]。


### source_inputs

上传源码的路径与内容哈希；源码本体在产物目录。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `filename` | VARCHAR(120) | 否 | 源文件名，不是服务器任意路径。 |
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。 |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |

UNIQUE：[]；CHECK：[]。


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

UNIQUE：[['username_normalized']]；CHECK：["role IN ('admin','user')"]。


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

UNIQUE：[]；CHECK：[]。


### audit_logs

账号、安全与关键任务操作审计，不保存明文密码或模型密钥。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `actor_id` | VARCHAR(32) | 是 | 可选操作者用户 ID；初始化/失败登录可为空。 |
| `action` | VARCHAR(80) | 否 | 接受／回退等决策。 |
| `target_id` | VARCHAR(100) | 是 | 被操作对象的不透明 ID，不是数据库外键。 |
| `created_at` | DOUBLE | 否 | 应用提供的 Unix 秒时间戳，包含小数。 |
| `details` | JSON | 否 | 事件详情 JSON。 |

UNIQUE：[]；CHECK：[]。

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

UNIQUE：[['token_sha256']]；CHECK：[]。

- `auth_sessions(user_id)` → `users(id)`。

### input_owners

源码所有者及实际源码字节数；不重写旧输入表。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `input_id` | VARCHAR(32) | 否 | 关联上传源码。；PK |
| `user_id` | VARCHAR(32) | 否 | 关联 users.id；不是由客户端自由指定的所有者。 |
| `byte_size` | INTEGER | 否 | 对应上传源码的实际 UTF-8 字节数。 |

UNIQUE：[['user_id', 'input_id']]；CHECK：[]。

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

UNIQUE：[['idempotency_key']]；CHECK：[]。

- `migration_jobs(input_id)` → `source_inputs(id)`。

### tasks

旧开发任务，不等同 migration_jobs。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(32) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `input_id` | VARCHAR(32) | 否 | 关联上传源码。 |
| `name` | VARCHAR(120) | 否 | 显示名称。 |

UNIQUE：[]；CHECK：[]。

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

UNIQUE：[]；CHECK：['max_active_jobs >= 0 AND daily_jobs >= 0 AND daily_model_calls >= 0 AND daily_tokens_soft >= 0 AND storage_bytes >= 0']。

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

UNIQUE：[]；CHECK：[]。

- `user_usage_daily(user_id)` → `users(id)`。

### job_owners

真实迁移任务所有者；未分配的历史记录只允许管理员访问。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。；PK |
| `user_id` | VARCHAR(32) | 否 | 关联 users.id；不是由客户端自由指定的所有者。 |

UNIQUE：[]；CHECK：[]。

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

UNIQUE：[]；CHECK：[]。

- `migration_feedback(job_id)` → `migration_jobs(id)`。

### migration_files

任务所属文件索引及 SHA-256；不保存文件二进制。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。；PK |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `kind` | VARCHAR(40) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |

UNIQUE：[]；CHECK：[]。

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

UNIQUE：[['job_id', 'ordinal']]；CHECK：[]。

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

UNIQUE：[['task_id', 'idempotency_key']]；CHECK：[]。

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

UNIQUE：[['id', 'run_id']]；CHECK：[]。

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

UNIQUE：[]；CHECK：[]。

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

UNIQUE：[['run_id', 'event_key']]；CHECK：[]。

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

UNIQUE：[]；CHECK：["status IN ('prepared','started','received','completed','blocked','review_required')"]。

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

UNIQUE：[]；CHECK：[]。

- `worker_locks(run_id)` → `runs(id)`。

### candidate_decisions

旧开发候选接受／回退关系。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `id` | VARCHAR(100) | 否 | 应用生成的记录标识；仅 run_events.id 为自增整数。；PK |
| `run_id` | VARCHAR(32) | 否 | 关联旧开发运行；worker_health 中仅作提示。 |
| `previous_id` | VARCHAR(80) | 否 | 候选之前的接受产物标识。 |
| `candidate_id` | VARCHAR(80) | 否 | 本次候选产物标识。 |
| `action` | VARCHAR(24) | 否 | 接受／回退等决策。 |
| `reason` | VARCHAR(120) | 否 | 决策原因代码。 |

UNIQUE：[]；CHECK：[]。

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

UNIQUE：[]；CHECK：[]。

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

UNIQUE：[['extraction_id', 'idempotency_key']]；CHECK：["status IN ('pending','approved','revoked','consumed')"]。

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

UNIQUE：[['extraction_id', 'idempotency_key']]；CHECK：["status IN ('prepared','started','received','completed','blocked','review_required')"]。

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

UNIQUE：[['extraction_id', 'idempotency_key']]；CHECK：["status IN ('prepared','started','received','completed','blocked','review_required')"]。

- `provider_generation_jobs(extraction_id)` → `ssm_extractions(id)`。

### ssm_extraction_files

独立提取的 request／ssm／receipt 文件索引。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。；PK |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `extraction_id` | VARCHAR(32) | 否 | 关联独立 SSM 提取记录。 |
| `kind` | VARCHAR(16) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |

UNIQUE：[['extraction_id', 'kind']]；CHECK：["kind IN ('request','ssm','receipt')"]。

- `ssm_extraction_files(extraction_id)` → `ssm_extractions(id)`。

### generation_approval_files

审批、撤销和领取证据文件索引。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。；PK |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `approval_id` | VARCHAR(32) | 否 | 关联生成审批。 |
| `kind` | VARCHAR(16) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |

UNIQUE：[['approval_id', 'kind']]；CHECK：["kind IN ('request','approval','revocation','claim')"]。

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

UNIQUE：[['job_id']]；CHECK：["status IN ('started','received','review_required')"]。

- `generation_attempts(job_id)` → `generation_jobs(id)`。

### generation_files

离线生成文件索引。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。；PK |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `kind` | VARCHAR(16) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |

UNIQUE：[['job_id', 'kind']]；CHECK：["kind IN ('request','receipt','candidate')"]。

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

UNIQUE：[['job_id']]；CHECK：["status IN ('started','received','review_required')"]。

- `provider_generation_attempts(job_id)` → `provider_generation_jobs(id)`。

### provider_generation_files

计划、请求、响应、收据与候选文件索引。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `relative_path` | VARCHAR(240) | 否 | 相对产物目录的路径；不表示数据库电脑上的绝对路径。；PK |
| `sha256` | VARCHAR(64) | 否 | 文件字节的 SHA-256 十六进制摘要。 |
| `job_id` | VARCHAR(32) | 否 | 关联本表所属账本的任务；不同账本的 job_id 不可混用。 |
| `kind` | VARCHAR(16) | 否 | 尝试／文件／事件类型，具体取值由账本决定。 |

UNIQUE：[['job_id', 'kind']]；CHECK：["kind IN ('plan','request','response','receipt','candidate')"]。

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

UNIQUE：[['job_id'], ['relative_path']]；CHECK：['parent_id IS NULL', "source_kind = 'offline_client_test'"]。

- `generation_candidates(job_id)` → `generation_jobs(id)`。
- `generation_candidates(relative_path)` → `generation_files(relative_path)`。

## 完整 SQL（仅新空库，未在真实 MySQL 实机执行）

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

## 回报要求

报告 MySQL 版本、内网地址/端口、准备库名、专用账号名（不含密码）、来源 IP 限制/TLS、34 张表的核验、失败语句、CHECK/FK/UNIQUE 负例结果、空 Alembic 版本表。不得宣称账号表建好即完成公网不可信代码执行隔离；系统当前支持受邀可信账号、单 Worker 排队，公网任意源码沙箱尚未交付。
