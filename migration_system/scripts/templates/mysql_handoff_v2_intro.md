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

