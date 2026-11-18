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
