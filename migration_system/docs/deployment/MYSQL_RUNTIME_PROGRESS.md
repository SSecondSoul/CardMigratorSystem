# 云数据库接入进度（2026-11-18，未切换）

目标是复用当前 SQLite 多用户系统的表、账号隔离、任务队列、模型调用和报告链，切换业务库到用户指定的腾讯云 TDSQL-C，而不是另建迁移器。源提取器、生成／修复 Prompt 和质量阈值均未改。

## 当前事实

当前最新：用户已创建云库管理员 `admin`，实查启用且无需强制改密。API 已使用专用云库配置启动，页面和健康接口返回 200，匿名任务读取返回 401，会话初始化返回多用户模式。迁移 Worker 在无排队／运行任务时完成一次真实云库空闲检查并退出。没有调用模型；当前 agent／API 进程没有 `LLM_API_KEY`，因此未启动常驻付费 Worker。用户需在自己的终端设置模型密钥并启动 Worker，再登录和提交新任务验证完整链路。旧 SQLite 未迁移或改动。证据见 [管理员与空闲 Worker](../verification/2026-11-18_mysql_cloud_integration/admin_api_worker_live_check.json)、[真实 HTTP](../verification/2026-11-18_mysql_cloud_integration/api_http_live_check.json)，操作见 [云库启用指南](MYSQL_CLOUD_ACTIVATION.md)。备份恢复及完整模型迁移／下载仍未验收，不能宣称整个系统已全部通过。

### 前一阶段：专用账号恢复

当前最新状态：应用账号和加密应用密码已经创建。首次检查在外键探针误报：云端返回 `1216`，脚本只识别 `1452`。已修正为识别两种明确的缺父记录错误码，新增有效父子插入及回滚正例；使用现有账号、现有加密密码恢复成功，没有重建或扩大权限。证据见 [原生恢复报告](../verification/2026-11-18_mysql_cloud_integration/application_native_checks_passed.json) 和 [系统 SQLAlchemy／Service 实际读库](../verification/2026-11-18_mysql_cloud_integration/application_service_live_check.json)。11 项账号恢复测试、9 项初始化探针测试、24 项连接与 17 项运行测试通过。网站账号和迁移任务数仍为 0；现在只需隐藏设置网站新管理员密码，然后继续云端 API／Worker 验收。API／Worker 尚未切换。

### 上一阶段记录

最新状态：真实云端初始化报告为 `mysql_bootstrap_and_native_checks_passed`，34 表无结构差异，已登记 `0008_multi_user`；JSON／Unicode／NULL、时间戳、双连接锁、唯一键／外键／CHECK 和 DML 回滚均通过。业务表仍为空，仅版本表有记录。证据见 [原生检查报告](../verification/2026-11-18_mysql_cloud_integration/bootstrap_native_checks_passed.json)。

用户已选择**空云库重新创建管理员，不迁移旧 SQLite 数据**。新增 `scripts/provision_mysql_app.py --execute --init-admin`：隐藏输入 root 密码、创建来源受限且强制 TLS 的最小 DML 权限应用账号；仅应用随机密码用 Windows CurrentUser DPAPI 加密保存；新管理员复用现有账号入口。默认离线，发现已有账号／文件不覆盖，失败保存阶段信息。9 项新增账号边界测试及既有 24 项连接、17 项运行、7 项初始化测试通过；加密模块此前使用虚构密码完成 5 项真实当前用户 DPAPI 测试。均不代替云端账号和 API 验收。

当前仍需用户在本机隐藏输入密码完成账号初始化，然后验证云端 API／Worker 登录、隔离、队列、产物和备份恢复。专用账号、新管理员及运行切换尚未实际完成。下一步仅按 [云库启用指南](MYSQL_CLOUD_ACTIVATION.md) 执行账号初始化，不再重复建表。生成／修复 Prompt、模型配置和 SQLite 历史记录不变。

## 历史诊断与实现记录（下列“尚未”描述对应当时阶段）

当前最新结果：用户完成只读检查，真实报告确认 **34 表均已存在且全空**，字段／主键／唯一键／外键无差异。12 项 CHECK 比较失败全部来自 MySQL 兼容实例返回的转义引号表示；已冻结 [原报告](../verification/2026-11-18_mysql_cloud_integration/schema_inspection_before_quote_normalization.json)，SHA-256 与源报告一致。通用修复只在元数据词法层识别这种有匹配层数的引号表示，保留字面值、CHECK 数量和 ENFORCED 校验；不修改源 SQL 或云端表，不忽略约束。真实报告离线重放后 12 项差异全部归零，见 [重放说明](../verification/2026-11-18_mysql_cloud_integration/schema_quote_normalization_replay.json)。

本轮连接／比较测试 24 项、运行边界测试 17 项、初始化 CLI 测试 7 项通过；新增用例证明改变枚举值或禁用 CHECK 仍会阻断。尚需再次执行显式初始化，复用已有 34 表进行版本登记与原生回滚测试，不删除或重建现有表。本机离线重放没有执行任何新云端 SQL，不等于原生验收通过。初始化失败现在也会自动保存脱敏报告和结构差异，避免只在终端留下无定位信息的错误名。

只读诊断已补充字段／键／CHECK 的 expected、actual，支持本机隐藏提示读取密码及自动保存结果；不会将密码写入环境变量或报告，也不会创建、修改、删除云端表或登记版本。从仓库根目录运行：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/check_mysql_connection.py --connect --password-prompt --save-report
```

该只读诊断已由用户完成，报告在 `var/mysql-inspection-reports/`，不需要为了本次修复重复运行；上方命令保留供以后只读复核使用。当前应执行下方的初始化入口继续，而不是手工改表或降低约束要求。

最新进展：用户已明确批准 `VERIFY_CA`。已配置该模式并完成真实 TLS 1.3 握手及所提供 CA 的证书链验证；不再要求用户重新开启 SSL。域名身份检查未执行，报告明确标记 `tls_identity_verified=false`，没有自动降级或关闭 TLS。证据见 [VERIFY_CA 探测](../verification/2026-11-18_mysql_cloud_integration/endpoint_probe_verify_ca.json)。当前还缺进程内的 root 登录凭据，尚未执行云端 SQL 或切换运行服务。下方域名不匹配及未开启 SSL 为历史诊断，不代表当前仍处于该状态。

最新状态：用户已开启 SSL 并提供 `TencentDB-SSL-CA` 目录，已配置其中的 `ca.pem`。真实探测确认服务端现在支持 TLS，但 `VERIFY_IDENTITY` 报错误 62／`hostname_mismatch`，不是此前的未启用 SSL。证据见 [开启 SSL 后的探测](../verification/2026-11-18_mysql_cloud_integration/endpoint_probe_after_ssl.json)。当前没有关闭域名校验、使用不可信 CA、发送密码或执行云端 SQL；是否采用官方文档中的 `VERIFY_CA` 仍待用户明确选择。下方未启用 SSL 的条目保留为此前阶段记录。

- 当前 API／Worker 默认配置仍为 SQLite，没有重启、切库、复制业务数据或登录云端 MySQL。
- 云端外网域名和端口已录入本地忽略配置。真实 TCP 可达；进一步无账号／无密码／无 SQL 的握手探测返回 `8.0.30-cynos-3.1.19.002`，但未宣告支持 SSL。证据见 [endpoint_probe.json](../verification/2026-11-18_mysql_cloud_integration/endpoint_probe.json)。
- DMC 已由用户以 root 登录目标实例。工具可读到库列表和 SQL 编辑器文本，但图像捕获／点击失败，键盘焦点也不能可靠控制。只读查询填入后没有执行。随后尝试填入完整建表脚本，目前只读到编辑器末尾的建表约束文本，不能据此声称完整 SQL 已验证，更不能宣称云端建表成功。
- 另一台电脑此前的 MySQL 8.0.41／34 表核验不适用于当前新云实例。

## 本轮实现（代码存在，不等于云端验收）

1. `config.py` 新增显式 `[database]` 选择，默认仍是 SQLite。MySQL 必须使用多用户认证、独立连接配置，不从 URL／TOML 接收明文密码。配置读取不连接数据库。
2. `persistence/mysql_connection.py` 复用原只读连接工具，CLI 仍为 `scripts/check_mysql_connection.py`。增加 `--probe`：仅读取服务端握手及验证 TLS，不发送认证数据或执行 SQL。
3. `persistence/database.py` 增加 SQLAlchemy／PyMySQL MySQL 引擎，强制验证 TLS 与严格 SQL 模式，不将 root 作为常驻应用账号。保留原 SQLite 引擎。
4. MySQL 的短事务用服务端 `GET_LOCK`／`RELEASE_LOCK` 串行化，保持原 SQLite 短事务的配额／准入保护语义；不自动重试结果未知的写入。**该腾讯云实例是否支持这一锁机制仍需真实验证**。本机图执行锁和单 Worker 限制未取消。
5. 显式 `init-db` 的 MySQL 路径不重放 SQLite 历史 DDL，只在已存在的空数据库创建经过哈希核验的 34 表；已有准备表先逐项比较。只对结构吻合且全空的准备库显式登记 `0008_multi_user`，不会自动修补部分表、覆盖数据或冒认未知版本。云端数据库本身仍须先创建。
6. `Service` 按配置选择引擎，不再对 MySQL 使用 SQLite 文件存在性检查。`mysql_multi_user.example.toml` 仅是未生效的接入示例，本机 LangGraph 检查点／产物仍独立存放。
7. 备份／恢复已增加 MySQL 路径：在应用事务互斥锁内将业务行导出为可离线核验的 SQLite 归档，同时保留注册产物与本机 LangGraph 检查点。恢复只写入已经初始化且为空的目标业务库及全新本机目录，撤销旧登录会话并停止旧 Worker 心跳；不删除目标行、不禁用外键、不覆盖旧目录。任何安装失败或云端提交结果不明时保留 `.restore-in-progress` 标记，阻止假恢复后启动。**原生 MySQL 备份／恢复仍待真实云端验收**，不能用本轮本机替身测试代替。
8. `portable_database.py` 对每张表核验列、版本、行数和内容指纹，按父子关系插入；区分 SQL NULL 与 JSON null，拒绝超长字符串、非标准 JSON、非空目标及超出迁移上限的数据。MySQL 两端还需核对实际 InnoDB／完整结构，防止非事务表导致假回滚。注册文件仍按原 SHA-256 校验，历史请求和绑定不重写。

## 已执行的工程检查

MySQL 连接／TLS 探测离线测试 16 项，新增配置／引擎／事务／空库初始化测试 16 项，原配置与脚手架回归 29 项，多用户回归 18 项，MySQL 建表交接回归 9 项，均通过（共 88 项）。初始化和锁测试使用明确的测试替身，SQLite 多用户回归使用临时 SQLite；不能代替真实 MySQL 事务、DDL、权限或并发验证。建表交接导出 `--check` 仍匹配。

后续补充：可移植数据复制 9 项、MySQL 归档分支 4 项、原 API／独立 Worker／LangGraph 垂直切片 22 项通过；并重跑新增 MySQL 运行边界 16 项。数据复制使用真实临时 SQLite，云端归档分支使用明确的 SQLite 引擎替身；包含内容被触发器篡改时回滚、SQL NULL／JSON null 区分、自引用外键、会话撤销、非空目标拒绝和失败标记保留。累计覆盖 123 个不同测试用例，但仍不是原生云端验收。

## 尚未完成的必要工作

- SSL 开启、CA 获取和用户选定的 `VERIFY_CA` 握手已完成；当前不声称域名匹配。模式差异参见 [腾讯云 SSL 说明](https://intl.cloud.tencent.com/zh/document/product/1098/63090)。
- 安全取得初始化凭据，创建／核验新业务库和 34 表，配置低权限应用账号；密码不通过聊天、Git 或日志传递。
- 真实验证版本、CHECK、JSON、时间戳、事务锁及配额并发，完成账号隔离、队列、产物下载、模型调用记账的端到端回归。
- 完成 MySQL 备份／恢复的真实云端验收，并明确是否迁移 SQLite 旧数据或使用全新账号库。旧源码、报告和图检查点不在 MySQL 中，切换不能只复制表而丢弃文件；本轮没有自动上传旧记录。
- 全部验证通过后，才以独立配置启动 API／Worker。源码绑定已变化，旧任务不跨实现强行续跑；切换前保留原 SQLite 和产物备份。

因此，当前不能宣称“云端已建表”“系统已切换”或“MySQL 生产接入通过”。后续工作应继续向真实云端验收推进，不能以本轮离线测试替代最终目标。

## 下一步：本机隐藏输入 root 密码

新增 `scripts/bootstrap_cloud_mysql.py`：默认仅输出离线计划；明确传 `--execute` 才在交互终端隐藏读取 root 密码。密码仅在该进程内使用，不写入配置／报告、不通过命令行参数传递；退出时不保留 root 密码。脚本可创建配置指定的新业务数据库，复用系统的 34 表初始化和版本登记，再在真实 MySQL 上测试 JSON／时间戳、双连接锁互斥、唯一键／外键／CHECK 和 DML 回滚。

在仓库根目录运行：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/bootstrap_cloud_mysql.py --execute
```

只在本机提示中输入 root 密码，不发送聊天。脚本没有 DROP／TRUNCATE／清空数据／GRANT／创建 MySQL 账号，不复制旧 SQLite 数据，不启动 Worker 或调用模型，不切换服务；发现部分未知结构会停止，失败后不要盲目重跑 DDL。成功报告保存在 `var/mysql-bootstrap-reports/`，不含密码。该入口已完成隐藏提示、错误脱敏和回滚探针的离线测试，尚未使用真实 root 凭据执行。

建库及原生探针成功之后，仍需应用专用账号、API／Worker 真实端到端检查和切换，不可把初始化成功当作整个系统接入完成。
