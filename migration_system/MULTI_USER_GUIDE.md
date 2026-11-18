# SQLite 多用户版：启动与使用

2026-11-18。本版已实现账号与权限、页面和 SQLite 表结构，复用原 SSM → 模型生成 → 评估 → 有界修复主链。不是重新生成一套迁移器，也不需要用户填写模型 Key 或本地写入令牌。

**当前交付范围是受邀可信账号、单台服务器、单 Worker 排队。** 登录隔离不等于不可信源码执行沙箱；不要直接向互联网开放匿名注册或任意源码执行。未来公网部署仍需 HTTPS、正式 WSGI、执行沙箱和资源隔离。MySQL 尚未接入，不要只改连接串。

## 1. 先启动本电脑的账号版

所有命令在 `migration_system` 目录内执行。先等待正在执行的旧任务结束，再在旧 API／Worker 终端按 Ctrl+C 停止，避免占用 8790 端口。已有依赖无需重装。

终端一（首次初始化与管理员创建）：

```powershell
cd C:\Users\soul\Desktop\swu\毕业设计\migration_system
npm.cmd --prefix frontend run build
& .venv/Scripts/python.exe scripts/run_system.py init-db --config configs/multi_user.toml
& .venv/Scripts/python.exe scripts/run_system.py init-admin --config configs/multi_user.toml --username admin
```

最后一条命令会两次询问管理员密码：输入 **12–128 个字符**，输入过程不回显，不能把密码写入命令参数。没有默认账号／默认密码。`init-admin` 只允许在尚无账号的数据库执行一次；已经成功创建过就跳过，不能借此覆盖原管理员。

仍在终端一启动 API：

```powershell
& .venv/Scripts/python.exe scripts/run_system.py serve --config configs/multi_user.toml
```

终端二，同样进入 `migration_system`：

```powershell
cd C:\Users\soul\Desktop\swu\毕业设计\migration_system
$env:LLM_API_KEY = '你的模型密钥'
& .venv/Scripts/python.exe scripts/run_system.py migration-worker --config configs/multi_user.toml
```

沿用 `configs/system.toml` 的模型配置；如 `api_key_env` 指定了其他变量名，使用那个变量名。不需要改已配置好的模型、Prompt 或调用预算。模型 Key 只交给 Worker，不输入网页、不提供给普通用户。

打开 **http://127.0.0.1:8790/**，硬刷新，用刚创建的管理员登录。如果仍是旧的免登录工作台，核对 API 和 Worker 都带了 `--config configs/multi_user.toml`。仅启动 API 时任务会排队，启动对应 Worker 后才执行。

## 2. 网页操作

管理员进入侧栏“用户管理”：

1. 创建受邀账号：账号以英文字母开头，3–64 位，只含字母、数字、点、下划线或横线；填写显示名称、临时密码和角色。
2. 通过安全渠道单独告知用户临时密码；用户首次登录必须改密，再重新登录，之后才能提交迁移任务。
3. 查看账号实际用量、调整额度；禁用／启用／重置密码需要再次输入当前管理员密码。不能禁用自己。禁用和重置会撤销该用户的全部旧会话。
4. 管理员可以查看全体近期任务和历史无所有者记录，以及关键操作审计。普通用户没有这些入口，后台也会拒绝相应请求。

普通用户登录后：

- 新建迁移继续固定为 **SSM＋有界修复**，不用选择实验策略、填写令牌或额外确认勾选项。
- 只能查询、下载、取消、恢复和反馈自己的任务；即使知道其他任务 ID，也不能读取源码、报告或文件。
- “我的账号”显示实际用量与额度，可以修改密码、退出。改密会撤销全部旧会话；退出当前会话也会同步清除同浏览器其他标签页的工作台。
- 登录会话最长 8 小时，保存在 HttpOnly／SameSite=Strict Cookie，数据库只保存随机会话凭据的摘要。有效会话可跨 API 重启保留；不保存明文密码。
- 写入请求不自动重发。若创建响应超时，先核对任务列表，不要连续重复提交。

当前没有匿名自行注册、邮箱找回、组织／项目团队、支付计费和在线训练。忘记密码联系管理员；这些不是本轮账号闭环的前置功能。

## 3. 数据和配额

`configs/multi_user.toml` 指向独立目录：

| 内容 | 位置 |
| --- | --- |
| 业务数据库 | `var/multi_user/runtime/business.sqlite3` |
| LangGraph 检查点 | `var/multi_user/runtime/langgraph.sqlite3` |
| 源码、SSM、San、报告、截图、调用收据 | `var/artifacts/multi_user/` |

原 `configs/development.toml`、`var/runtime/`、原实验文件均未删除或自动搬迁。账号版初始列表为空是正常现象，不代表旧记录丢失。不要把原目录直接覆盖到新目录，也不要手改历史任务请求、指纹或所有者来绕过校验。

Schema 为 **0008_multi_user**：保留原 26 张表，新增 8 张表，共 34 张。新增 `users`、`auth_sessions`、`user_limits`、`user_usage_daily`、`input_owners`、`job_owners`、`audit_logs`、`auth_throttle`。所有权独立关联旧输入／任务表，不重写已冻结的实验 JSON 或哈希。历史无所有者记录只对管理员开放，不自动分配给第一个用户。

默认每个账号：

| 限额 | 默认值 | 计算方式 |
| --- | ---: | --- |
| 排队／执行中任务 | 3 | 取消或结束后不占活动名额；恢复仍检查活动上限 |
| 每日任务 | 20 | 创建成功即占用，幂等重试不重复计数；取消不退还 |
| 每日模型调用 | 50 | 发出请求前持久预留；网络结果未知也占用 |
| 每日已知 Tokens 停止线 | 500,000 | 达线后阻止下一调用，**不是硬计费封顶** |
| 已注册源码总字节 | 20 MiB | 按实际 UTF-8 字节，不是所有文件总磁盘配额 |

日统计采用 **UTC 日期**。调用跨午夜时按调用开始日结算；已知响应重放不重复计费。单次调用仍可能跨过 Token 停止线，生成代码／截图也不计入源码字节额度，运营方仍需监控磁盘与模型账单。

模型响应或用量未知时，阻断该账号后续模型调用，包括另建任务；不能通过换任务 ID 绕过，也不会自动重发。后台需要人工核对供应商收据；本轮没有增加一个“忽略未知用量”的放行按钮。

多用户可以同时提交，后台仍只有一个迁移 Worker 顺序执行。SQLite 事务保护创建额度、用户范围幂等与调用预留，不宣称支持多机分布式 Worker 或高并发数据库负载。禁用账号会阻止排队任务和后续阶段／模型调用，**不能撤销已经发给供应商的在途请求**。

## 4. 管理员恢复与备份

管理员忘记密码时，由能访问服务器的操作员执行：

```powershell
& .venv/Scripts/python.exe scripts/run_system.py reset-admin-password --config configs/multi_user.toml --username admin
```

通过隐藏提示设置新密码并撤销旧会话。此命令属于服务器运维权限，不是对外找回接口。

备份同时覆盖数据库与已注册产物；备份中包含密码哈希、源码和调用证据，必须限制访问。停止 Worker 并按既有备份流程操作，所有命令使用相同多用户配置：

```powershell
& .venv/Scripts/python.exe scripts/run_system.py backup --config configs/multi_user.toml
```

保留输出的 backup_id；验证／恢复继续使用既有 CLI，但恢复必须使用全新的目标目录，不能覆盖原库。恢复会撤销备份中的登录会话，避免历史有效 Cookie 再次生效；原备份文件不被改写。

## 5. 后续远程使用与 MySQL

当前 `serve` 是 **本机开发验收服务**，刻意不开放局域网 HTTP 监听。不要删除 Host／Origin／CSRF 校验来让另一台电脑连接。

线上受邀用户部署需要运维方另外完成：

- HTTPS 域名、证书、正式 WSGI 服务和反向代理；后端只由可信代理连接，不直接暴露 Flask 开发服务。
- 用 `CARDMIG_SYSTEM_CONFIG=configs/multi_user.toml` 和精确的 `CARDMIG_PUBLIC_ORIGIN=https://你的域名` 配置 WSGI 工厂 `card_migration_system.interfaces.wsgi:create_application()`。代理必须保留约定的 Host；不信任任意客户端转发头、不开放通配 CORS。
- API 与单 Worker 使用同一套配置和本机持久目录；Worker 与 API 的模型环境按既有指南配置。
- OS／容器级源码执行沙箱、浏览器与服务网络隔离、CPU／内存／磁盘／运行时限制、日志和备份保护。**Cookie 登录与浏览器独立上下文本身不能证明这些已经具备。**

本轮未部署公网服务器或安装正式 WSGI／容器组件，不把临时 HTTP 测试当作公网安全验收。

给另一台电脑 AI 的新交接文件为 [MySQL 多用户交接 v2](docs/deployment/mysql_handoff_v2/MYSQL_MULTI_USER_HANDOFF.md)，已按实际 SQLite 34 张表生成。v1 的 26 表与旧多用户草案保留为历史；新准备库以 v2 为准。MySQL 驱动、迁移、事务锁、备份和图检查点适配仍需另做，不是修改一个数据库 URL 就完成。

## 6. 本轮验证与实现位置

真实浏览器验收使用临时 SQLite 与随机测试密码：登录、管理员创建账号、强制改密、普通用户建任务、用量、跨标签页退出、切换账号后旧数据清除、他人报告 404、重载会话、390 px 布局。没有启动迁移 Worker、没有调用云模型。接口／额度和原迁移闭环回归另用显式假模型，不计入论文迁移效果。

主要实现：

- `persistence/accounts.py`、`migrations/versions/0008_multi_user.py`：新增表与升级。
- `application/accounts.py`：密码、会话、所有权、额度、审计与限流。
- `interfaces/api/accounts.py`：登录／后台接口与逐请求权限校验。
- `application/service.py`、`application/migrations.py`：在原创建／调用事务中接入所有者和限额；不改 Prompt、迁移规则或评估阈值。
- `frontend/src/components/AuthGate.vue`、`AccountPanel.vue`、`AdminUsersPanel.vue`：登录、个人账号和管理员界面。
- `tests/test_multi_user.py`、`test_multi_user_workbench.py`：接口隔离与真实浏览器验收。

本轮未替用户创建真实管理员、初始化实际账号库或执行付费迁移。需要你按第 1 节设置自己的管理员密码，再进行一次真实人工体验。
