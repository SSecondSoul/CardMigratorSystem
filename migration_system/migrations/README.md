# 数据库变更

当前 HEAD 为 **0007_modular_migration**；用户实际库已确认 0006，本次未自动升级。请统一部署时显式 init-db，详见本文末的 0007 说明及 [系统指南](../SYSTEM_GUIDE.md)。以下 0001—0006 状态保留为历史，不覆盖当前迁移要求。

P2b 已提供 `versions/0001_development_slice.py`，由显式 `run_system.py init-db` 使用 Alembic 创建受限开发业务表。env.py 只接受应用传入的连接，不猜测旧数据库位置。重复初始化保持同一版本；非空且无法识别的数据库拒绝初始化。

`src/card_migration_system/persistence/schema_v1.py` 是初始版本固定 schema，不应为未来字段原地修改。`0002_worker_health.py` 单独增加运维心跳表；`0003_ssm_extractions.py` 单独增加真实 SSM 提取及文件登记表；`0004_generation_ledger.py` 增加独立离线生成请求／尝试／文件／候选四表；`0005_provider_generation.py` 增加独立传输登记的作业／尝试／文件三表。HEAD 为 0005_provider_generation，不改写旧迁移，downgrade 明确阻断。用户现已显式升级实际库至 0005 并确认原 SSM 查看／下载；助手只读核对 schema、新表及原状态／指纹。无需重复初始化。临时库的 SSM／G2 保留与恢复测试不扩大为实际库所有业务行或备份恢复验收。

升级前停止新系统 API／worker。已有实现绑定不自动升级或放行续跑；先保留／复核旧运行，再显式新建运行。新系统 backup／verify-backup／restore 命令支持同一 schema 和实现绑定的本地备份与全新目录恢复，见[工程说明](../README.md)。不自动覆盖旧数据库，不以 schema 升级改变迁移结论。

业务 DB 与 LangGraph checkpoint 使用不同文件；自动测试只用临时数据库，不能清空用户数据库。

新 SSM 图使用原图库中独立的 `ssm:<id>` thread 命名空间；登记文件纳入同 schema 的备份／校验／恢复。旧 var/ssm-extractions 离线探测不自动导入。用户已显式升级实际库到 0003 并完成登记提取；新环境仍需先停新系统 API／worker，再运行 init-db。不要用新代码的 backup 命令强行读取旧 schema；旧备份保留，自动跨 schema 转换尚未实现。

G2 图使用 `generation:<id>`，与 SSM／夹具运行分开；没有默认模型客户端。用户此前显式升级至 0004 并确认原 SSM 保留，见 [G2 历史升级记录](../GENERATION_LEDGER.md#用户实际库升级点)。G3 登记图使用 `provider-generation:<id>`，仍只允许显式离线替身；原始响应／收据登记和备份接入不等于真实模型执行已放开。0005 实际升级及原 SSM 保留确认已完成，详见 [G3 升级记录](../RECORDED_GENERATION.md#当前入口与实际库)。实际备份恢复及新生成图不能由此推定人工验收通过；新环境／旧 schema 仍须先停进程再显式升级，不自动转换旧 schema／实现备份，不删库绕过检查。
# 当前版本 0007_modular_migration

2026-11-16 新增真实迁移 `migration_jobs`、`migration_files`、`migration_model_calls`、`migration_feedback`。独立 metadata，不让冻结的 0001 在新进程中提前创建未来表。0001—0006 不改写；0007 仅增表，不删改用户源输入或旧实验记录。

本次只读确认用户实际业务库为 0006，未自动升级。统一部署时停止 API／worker 后运行 `init-db`；备份使用 SQLite backup API 或系统当前版本的校验备份，不在运行中只复制主库文件。旧备份按其原 schema 保留，不补造新版本标记。

