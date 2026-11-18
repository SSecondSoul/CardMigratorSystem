# 远端 MySQL 连接准备（2026-11-18）

当前云库已完成 VERIFY_CA、34 表和原生检查、版本登记；用户选择空库重新创建管理员。现在按 [云库启用指南](MYSQL_CLOUD_ACTIVATION.md) 准备专用账号，尚未切换运行服务。下文“尚未适配／尚未建表”为此前连接准备阶段记录，最新证据以 [MySQL 接入进度](MYSQL_RUNTIME_PROGRESS.md) 为准。

## 以下为此前连接准备阶段

这一阶段只核验连接和准备库，不切换 API／Worker，不导入 SQLite 数据，不登记 Alembic 版本，不调用模型。现有多用户系统继续使用 SQLite。连接工具不读取账号、源码或报告内容，不执行 DDL／数据写入。

## 当前交接状态

### 当前改用腾讯云实例

用户后续选择腾讯云 TDSQL-C（控制台显示兼容 MySQL 8.0）。当前外网端点为 `cq-cynosdbmysql-grp-ehvygvrf.sql.tencentcdb.com:25926`；2026-11-18 本机一次 TCP 探测成功，未进行数据库认证、TLS 身份验证或 SQL 执行。本地忽略配置中的地址和端口已更新到云端，账号仍为空；库名 `cardmigrator_multi_user_staging` 是计划值，尚未确认云端存在。API／Worker 仍使用 SQLite，云端 34 表未由本机创建或核验。

数据库控制台显示内网端口为 3306；外网客户端使用分配的 25926 端口，两者不混用。账号、建表权限及 TLS／CA 仍待确认。下方另一台电脑的 8.0.41／34 表回报为此前准备路线，不能当作当前云端的已有结构或版本证据。

### 此前另一台电脑的交接记录（不代表当前云库）

数据库电脑回报：MySQL Community Server **8.0.41 / Win64**；地址 `10.114.143.105:3306`；准备库 `cardmigrator_multi_user_staging`。已按 [v2 交接](mysql_handoff_v2/MYSQL_MULTI_USER_HANDOFF.md) 创建并核验 `0008_multi_user` 的 34 表、202 字段、34 主键、19 额外唯一键、38 外键、14 个已启用 CHECK；全部表为空，包括 `alembic_version`。

上述结构核验来自另一台电脑的回报，不是本机远端复核。交接目标是 MySQL 8.4，实际为 8.0.41；连接检查工具允许对 8.0.16+／8.4 做只读结构核验，但会单独报告 8.0 版本差异，**不据此宣称应用兼容性已验证，也不要求现在重装数据库**。

本机本次网络观察：以太网 `10.66.103.20`；WLAN `169.254.9.77`。对 `10.114.143.105:3306` 的一次 TCP 探测在 4 秒后超时；未做 MySQL 登录。地址可能变化，或存在路由、防火墙、无线客户端隔离、服务监听配置问题；仅凭超时不能确定原因。本机当前地址也不一定等于数据库看到的客户端来源地址。

当前缺项：可达且稳定的网络地址、应用专用账号及其来源限制、密码的安全交付、TLS 证书与身份验证。没有这些条件时，先不尝试账号登录或切换服务。

## 1. 交给数据库电脑 AI 的后续任务

可以直接复制下面这段给另一台 AI：

> 保留已经创建的 `cardmigrator_multi_user_staging`，不要重跑建表 SQL、导入数据或写入 `alembic_version`。后台电脑目前报告以太网地址 `10.66.103.20`，WLAN 为 `169.254.9.77`；到数据库电脑 `10.114.143.105:3306` 的一次 TCP 探测超时。请先重新核实两台电脑的稳定地址、可达路由、MySQL 监听接口、Windows 网络配置与入站防火墙规则。只允许已确认的后台电脑来源访问 3306，不关闭防火墙、不向公网开放，也不要把账号来源设为 `%`。不要仅凭上述暂存 IP 创建长期授权。
>
> 网络来源确认后，创建应用专用账号（建议 `cardmig_app`），只授予该准备库的 SELECT／INSERT／UPDATE／DELETE；不要使用 root，不给全局、DDL、GRANT OPTION、FILE 等权限。后续应用适配若需要版本登记或升级，由单独明确授权的部署流程处理，本次不要提前登记。
>
> 优先配置 TLS，并交付可验证的服务器身份：若用 IP 连接，证书需覆盖该 IP；若用稳定域名，证书需覆盖该域名。给后台电脑提供 CA 公共证书文件和指纹，私钥留在数据库电脑。不要通过关闭证书验证来掩盖不匹配。
>
> 回报可用地址、端口、库名、专用账号名、精确来源限制、TLS 状态及 CA 交付方式。密码通过单独的安全渠道交给操作者，不写入报告、SQL 文件、聊天或 Git。只读结构核验与应用读写兼容性测试分开报告。

## 2. 本机文件与依赖

命令在 `migration_system` 目录运行。可提交的空白模板是 `configs/mysql_connection.example.toml`。已为本次地址建立 Git 忽略的 `configs/mysql_connection.local.toml`：账号暂空、密码仅从环境变量读取、默认验证 TLS。该文件独立于 `configs/multi_user.toml`，**不会改变当前 API／Worker 的数据库**。

驱动 `PyMySQL[rsa]` 已在本机系统虚拟环境安装。另一环境需要安装时使用：

```powershell
uv pip install --python .venv/Scripts/python.exe --require-hashes -r requirements-mysql.lock
```

不要对这一份附加依赖锁使用 `uv pip sync`，否则可能移除系统原有依赖。主 `requirements.lock` 没有改变。

收到确认的地址、账号与 CA 后，修改本地 TOML 的 `host`、`port`、`name`、`username`、`tls.ca_file`。CA 相对路径按 `migration_system` 解析，例如 `configs/mysql-ca/server-ca.pem`，该目录也已被 Git 忽略。`tls.mode = "verify_identity"` 默认校验证书链和服务器身份；空 CA 路径使用 Python／系统信任库，不代表跳过校验。

密码在当前 PowerShell 终端中用隐藏提示输入，不要写进 TOML 或命令历史：

```powershell
$mysqlSecret = Read-Host 'MySQL 应用账号密码' -AsSecureString
$mysqlSecretPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($mysqlSecret)
try {
    $env:CARDMIG_MYSQL_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($mysqlSecretPtr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($mysqlSecretPtr)
    Remove-Variable mysqlSecret, mysqlSecretPtr
}
```

环境变量仍是当前进程中的明文秘密，不要输出它、截图环境或提交到仓库。关闭终端或检查完成后清除：`$env:CARDMIG_MYSQL_PASSWORD = $null`。

## 3. 检查命令与结果

先做离线检查，无网络连接：

```powershell
& .venv/Scripts/python.exe scripts/check_mysql_connection.py --config configs/mysql_connection.local.toml
```

账号未填、密码未设置时会报告 `configuration_pending`，这是准备状态，不是应用迁移失败。补齐配置且网络确认可达后，再显式连接一次：

```powershell
& .venv/Scripts/python.exe scripts/check_mysql_connection.py --config configs/mysql_connection.local.toml --connect
```

检查采用会话只读事务，不自动重试；核验版本、严格 SQL 模式、TLS、InnoDB、排序规则、字段、主键／唯一键／外键、CHECK 启用状态与语义，以及所有表是否仍为空。判断非空只取常量 `1`，不输出真实数据；结束时回滚并关闭连接。

- `mysql_prepared_schema_verified`：本次连接及空准备库结构核验满足要求；**不代表系统已切换 MySQL、应用读写并发已通过或备份恢复已验证**。
- `mysql_schema_review_required`：存在结构差异或非空表，列出具体项；工具不会删除数据或“修好”远端库。
- `mysql_8_0_differs_from_handoff_target_8_4`：实际服务器属于 8.0 系列；保留此差异，应用兼容性状态仍为 `not_validated`。
- `blocked`：连接／证书／版本／SQL 模式等检查未通过；只输出稳定错误名与驱动数字错误码，不输出驱动异常原文或密码。常见 1045 为登录／来源授权问题，1049 为库名问题，2003 常见于网络或服务连接失败，具体原因仍需结合数据库端核实。

不得自动回退明文连接。如果操作者明确接受**受控内网临时检查**不加密的风险，可手动将本地 `tls.mode` 改为 `disabled`、清空 CA，并额外传 `--allow-insecure-lan`；仅允许明确的私网／回环 IP，不能用于公网或当作 TLS 验收结果。正式接入优先完成 TLS；没有该明确选择时保持默认校验。

## 4. 接通以后再完成的系统工作

本工具不是另建一套业务持久层。后续在现有 SQLAlchemy 持久层内适配 MySQL 连接配置、事务与配额并发、准备库版本确认与显式登记、备份／恢复，再验证账号隔离、任务队列及真实读写。LangGraph 检查点当前仍是独立的本机 SQLite；业务库连接 MySQL 不会自动迁移检查点，也不代表支持分布式多 Worker。

切换前保留 SQLite 回退和备份；不要把本工具配置当成已生效的业务配置，不要先把当前服务停掉或删除 SQLite 文件。没有完成事务、恢复与端到端测试前，不宣称 MySQL 生产接入完成。

本轮工程验证：连接检查测试 13 项、已有 MySQL 建表交接测试 9 项、配置与脚手架回归 29 项，共 51 项通过。连接检查使用离线配置／假数据库、错误脱敏及真实驱动的离线参数构造；建表交接另核对实际临时 SQLite 升级结果和 MySQL 方言 DDL。它们不替代真实远端登录、TLS 和应用兼容性测试。没有模型调用或真实业务数据导入。

在 `migration_system` 目录可以复验：

```powershell
& .venv/Scripts/python.exe -m unittest discover -s tests -p test_mysql_connection.py -v
& .venv/Scripts/python.exe -m unittest discover -s tests -p test_mysql_handoff.py -v
& .venv/Scripts/python.exe -m unittest discover -s tests -p test_scaffold.py -v
```

参考：[PyMySQL 连接参数](https://pymysql.readthedocs.io/en/latest/modules/connections.html)、[MySQL 只读事务](https://dev.mysql.com/doc/refman/8.4/en/set-transaction.html)、[MySQL CHECK 约束](https://dev.mysql.com/doc/refman/8.0/en/create-table-check-constraints.html)。
