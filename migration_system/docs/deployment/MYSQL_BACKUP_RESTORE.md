# MySQL 备份／恢复使用边界（待云端验收）

此功能已开发并完成本机测试。当前云库已通过 VERIFY_CA、34 表结构与原生回滚／约束／双连接锁检查，但未执行云端业务备份恢复，API／Worker 尚未切换。用户选择空库重新创建管理员、不迁移旧 SQLite 数据。接入状态见 [进度说明](MYSQL_RUNTIME_PROGRESS.md)。

## 归档内容

复用现有 `backup`、`verify-backup`、`restore` 命令，根据明确指定的系统配置选择 SQLite 或 MySQL。MySQL 业务行转换为本机归档内的 `db/business.sqlite3`，便于不依赖云端也能校验并回退；原始账号、任务、请求哈希、用量记录均保留，不改成新实验结果。另复制注册源码、San、报告、收据和图检查点，并校验文件 SHA-256。

归档包含密码哈希、源码和业务数据，应限制本机文件访问，不上传 Git 或公开分享。它不包含模型密钥、数据库密码、环境变量、孤立文件或云厂商全实例参数，也不替代云端自动备份。

## 运行条件

- MySQL 必须先通过 TLS、实际表结构和版本检查，并使用应用专用账号。当前的 SQLAlchemy 连接和短事务锁须在真实实例验证。
- 停止单 Worker，解决运行中任务及未知调用；不能用备份掩盖未决模型费用。备份期间持有应用事务互斥锁与本机执行锁，API 写入可能等待或超时，应安排维护窗口。
- 仅保证经过本应用互斥锁的写入被隔离；数据库管理员或其他程序绕过应用直接改表不在保护范围内，期间不得运行外部 DDL／DML。
- 目前沿用已有 256 MiB 归档上限，关系数据复制另设 256 MiB／100 万行的拒绝上限。超限会失败保留未完成标记，不自动截断或删除数据。

## 验收后可使用的命令

以下假设你已另行建立并验收 `configs/mysql_multi_user.local.toml`，不是让你现在用示例配置启动服务。

```powershell
& .venv/Scripts/python.exe scripts/run_system.py backup --config configs/mysql_multi_user.local.toml
& .venv/Scripts/python.exe scripts/run_system.py verify-backup --config configs/mysql_multi_user.local.toml --backup-id 实际备份ID
```

恢复必须使用指向**新的空目标业务库、全新 runtime 和 artifact 子目录**的独立配置。目标库先显式 `init-db`；除 `alembic_version` 以外任何表非空都会拒绝。不要对当前正在使用的数据库执行恢复，也不要修改原配置伪装目标为空。

```powershell
& .venv/Scripts/python.exe scripts/run_system.py restore --config configs/mysql_restore.local.toml --backup-id 实际备份ID
```

恢复会撤销归档中的登录会话、停止归档中的 Worker 心跳，保留账号和历史记录。数据库行按外键父子关系复制，每表读回后比较行数和内容指纹；SQL NULL 与 JSON null 分开保留。MySQL 端不得通过关闭外键来强行导入。

原有 SQLite 归档也可显式恢复到空 MySQL，MySQL 的可移植归档也可按原流程恢复到新的 SQLite 目录；均不自动迁移当前用户数据，历史请求指纹不修改。归档实现绑定必须匹配当前代码，旧版本归档应在对应版本中先核验，不能直接改 manifest 绕过检查。

## 失败与回退

本机文件系统和云端事务不是同一个原子资源。恢复先安装到新的本机目录并保留 `.restore-in-progress`，在云端事务确认提交后才清除标记。发生网络断开等结果未知情况时，**不得直接重复恢复、删除标记或继续启动服务**；先核实云端是否提交及本机文件是否完整。失败目录、原归档和旧 SQLite 均保留，绝不覆盖或自动清空。

正常回退可继续使用原 SQLite 配置与原产物目录；不得同时运行指向同一任务链的两套 Worker。恢复并不会使旧实现绑定的未完成任务自动兼容新代码。
