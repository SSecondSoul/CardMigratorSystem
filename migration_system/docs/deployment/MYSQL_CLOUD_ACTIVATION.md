# 云库账号初始化与切换

## 当前状态

2026-11-18：腾讯云业务库 `cardmigrator_multi_user_staging` 已完成 34 表结构核验、版本 `0008_multi_user` 登记及原生约束／回滚／双连接锁检查。用户选择**使用空云库、重新创建管理员**；不迁移旧 SQLite 的账号、密码哈希、任务或调用记录，原库和本机文件保留。

TLS 采用用户明确批准的 `VERIFY_CA`：加密并验证下载的 CA 证书链，不宣称已验证连接域名。此模式不会回退到明文连接。

应用账号 `cardmig_app`、当前 Windows 用户的加密应用密码和两份云库配置已创建；使用该账号的真实原生检查及系统 SQLAlchemy／Service 读库检查已通过。用户已创建新网站管理员 `admin`，实查为启用且无需强制改密。API 已使用云库配置启动于 `http://127.0.0.1:8790/`，真实 HTTP 页面／健康／匿名鉴权接口检查通过；迁移 Worker 完成一次空队列检查后已退出，没有模型调用。完整登录及付费迁移／下载链路仍待验证。

## 现在：登录并启动迁移 Worker

API 已在后台运行，不要重复启动或占用 8790 端口。打开 `http://127.0.0.1:8790/`，用 `admin` 和刚设置的密码登录。

当前执行环境没有模型密钥。由用户在自己的 PowerShell 终端设置密钥并启动常驻 Worker；密钥不要发到聊天：

```powershell
$env:LLM_API_KEY = '你的模型密钥'
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py migration-worker --config configs/mysql_multi_user.local.toml
```

命令从仓库根目录执行。确认 Worker 在线后再提交简单新任务，验证真实迁移、质量报告和下载；本轮未自动消耗模型额度。API 的本机进程信息和日志在 `var/mysql_multi_user/runtime/api-process.json`、`api.stdout.log`、`api.stderr.log`。当前 API 进程未持有模型密钥，其进程的密钥 readiness 提示不能据此推断另一个 Worker 是否有密钥，应结合 Worker 与实际任务结果判断。

证据见 [管理员／API／空队列 Worker 检查](../verification/2026-11-18_mysql_cloud_integration/admin_api_worker_live_check.json) 和 [实际 HTTP 检查](../verification/2026-11-18_mysql_cloud_integration/api_http_live_check.json)。匿名鉴权检查不等于已经使用用户密码完成登录；空闲 Worker 不等于完整迁移验证通过。

## 已完成：网站管理员初始化

在仓库根目录 `C:\Users\soul\Desktop\swu\毕业设计` 的 PowerShell 执行：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py init-admin --config configs/mysql_multi_user.local.toml --username admin
```

该命令已由用户执行完成，下面保留用法供新库参考；当前不要重复初始化。提示输入网站管理员 `admin` 的新密码，12–128 个字符，输入两次，不会回显。不需要再输入 root 密码或重跑创建数据库账号的命令。

`init-admin` 只能在没有账号的库中初始化，不能覆盖已有管理员。API／Worker 必须由创建加密密码的同一 Windows 用户在同一电脑上启动；复制加密文件到其他电脑或服务账号不能直接使用，应重新配置凭据。

## 已完成的账号初始化及故障恢复记录

最初使用 `provision_mysql_app.py --execute --init-admin` 隐藏读取 root 密码创建专用账号。该次在最小权限核验后停止：云端对缺失父记录返回 `1216 / ER_NO_REFERENCED_ROW`，脚本此前只接受 `1452 / ER_NO_REFERENCED_ROW_2`，因此误报外键检查失败；不是外键未生效，也不需要给应用账号增加 REFERENCES 或管理权限。

通用修复同时接受这两种明确的“缺失父记录”错误码，仍拒绝权限错误、字段错误或插入意外成功，并增加有效父子记录的插入、读回和全部回滚验证。失败会保留数字驱动错误码，不打印异常原文。新增恢复入口只读取本系统失败报告及绑定端点／库名／账号的 DPAPI 应用密码，重新核验当前身份、权限、34 表和业务空库，绝不执行 CREATE USER／ALTER USER／GRANT 或重写密码。

本次恢复已成功，报告见 [应用账号原生检查](../verification/2026-11-18_mysql_cloud_integration/application_native_checks_passed.json)。恢复没有再次使用 root 凭据；所有探针均回滚，该恢复时点管理员尚未创建，随后已由用户创建。系统实际 SQLAlchemy／Service 读库也通过，见 [服务读库验证](../verification/2026-11-18_mysql_cloud_integration/application_service_live_check.json)。

以下内容说明首次初始化的行为，不要在当前已经建好账号的实例上重复执行：

首次初始化提示：

1. 云数据库 **root 密码**：仅用于此次创建专用数据库账号，不保存。
2. 网站新管理员 **admin 的密码**：12–128 个字符，输入两次。它与数据库 root 密码是两回事，建议分别设置。

这些输入均不回显；不要把密码发到聊天、写入命令参数或截图。命令默认不带 `--execute` 时只展示离线计划。

脚本已创建 MySQL 专用账号 `cardmig_app`，限制为实际连接来源 IP、要求 TLS，并仅授予目标库的 SELECT／INSERT／UPDATE／DELETE。含下划线的库名按服务端 `partial_revokes` 设置处理，防止数据库级 GRANT 意外匹配其他库。账号密码随机生成，用当前 Windows 用户的 DPAPI 加密保存在 `var/secrets/mysql-app.dpapi`；只保存应用密码，不保存 root 密码。现有环境变量密码路径仍可用于其他部署环境。

生成以下独立文件（均已被 Git 忽略）：

- `configs/mysql_app.local.toml`：应用连接信息，引用加密密码文件，无明文密码。
- `configs/mysql_multi_user.local.toml`：云库运行配置，独立图检查点和产物目录。
- `var/mysql-provision-reports/*.json`：脱敏结果，记录创建到哪一步。

新网站管理员复用原 `AccountService` 的密码哈希、权限与审计实现，没有另一套登录逻辑。该步骤不启动 API／Worker、不调用模型、不更改旧 SQLite 配置。

若命令失败，先检查保存的报告，**不要盲目重复创建账号或删除文件**。创建账号属于不可回滚操作，部分成功时账号或加密密码可能已存在，脚本会拒绝覆盖。若数据库账号已经准备好，仅管理员初始化未完成，按报告确认后可单独重试原入口：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py init-admin --config configs/mysql_multi_user.local.toml --username admin
```

## 初始化后验收，再启动

管理员入口返回 `completed` 后，继续验证原生云库上的登录、账号隔离、任务排队、Worker、报告和产物下载。工程离线测试不能替代这些真实检查；本轮初始化不执行付费模型调用。

在旧任务结束并停止旧 API／Worker 后，两个 PowerShell 终端分别使用**同一份云库配置**（以下仍从仓库根目录执行）：

```powershell
# API 终端
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py serve --config configs/mysql_multi_user.local.toml
```

```powershell
# Worker 终端：模型密钥仍沿用你的模型配置，不是数据库密码
$env:LLM_API_KEY = '你的模型密钥'
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py migration-worker --config configs/mysql_multi_user.local.toml
```

打开 `http://127.0.0.1:8790/`，使用新管理员登录。旧 SQLite 的登录会话和任务不会在云库中出现。不要让两个后端同时占用该端口，不强行续跑旧实现的任务。完整 MySQL 备份／恢复和公网部署仍须分别验收；数据库在云端不代表网站已对外安全上线。
