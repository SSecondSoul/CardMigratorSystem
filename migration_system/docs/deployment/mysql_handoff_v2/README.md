# 当前 MySQL 建库交接入口

给另一台电脑 AI 发送 **[MYSQL_MULTI_USER_HANDOFF.md](MYSQL_MULTI_USER_HANDOFF.md)** 即可。它是单文件完整说明，包含全部 SQL 与核验步骤，不需要 v1 文档或本系统源码。

若方便发送整个目录，附带三份便利副本：

- `schema_multi_user.sql`：0008_multi_user 对应全部 34 张表，新建空准备库。
- `schema_multi_user.json`：机器可核对的字段、主键、唯一／外键／CHECK、源指纹及 DDL 摘要。
- `verify_schema.sql`：只读核验缺失／额外表、列、约束、索引、排序规则及所有表为空。

原 v1 的 26 表与早期多用户草案是历史版本，不再用于当前系统建库；不得在两个版本间混合执行 SQL。v2 也不授权覆盖原准备库／SQLite 或导入用户数据。

本轮源端核对：实际只读账号库确认为 0008_multi_user／34 表，字段／类型／NULL／主键与导出一致；临时 Alembic SQLite 及离线 MySQL 方言编译共 9 项测试通过。没有连接真实 MySQL，电脑 B 仍须执行 SQL 和约束验收。**建表后仍需电脑 A 完成 MySQL 应用接入，并非改一个连接字符串即可运行。**

维护时在 migration_system 目录执行以下只读检查：

```powershell
& .venv/Scripts/python.exe scripts/export_multi_user_schema.py --check
```

导出由 persistence metadata 与 migrations/versions 产生，生成器为 scripts/export_multi_user_schema.py，说明模板在 scripts/templates/mysql_handoff_v2_*.md。不要只手改生成 SQL／Markdown 而留下与模型不一致的文件。
