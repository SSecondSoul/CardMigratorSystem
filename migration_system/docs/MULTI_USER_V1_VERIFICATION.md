# SQLite 多用户 v1 工程验证

日期：2026-11-18。此记录是账号工程验收，不是新一轮 Vue → San 迁移准确率实验。所有新接口测试使用临时数据库；图测试明确注入假模型／假评估器；网页验收使用真实浏览器、真实 HTTP API 和临时 SQLite，不启动云模型或迁移 Worker。

## 本轮结果

账号创建可用性复验：补充逐字段规则、示例、角色权限与创建后的交付说明，中文即时／提交校验和首错聚焦；前端测试增至 **40/40**。真实浏览器再次通过，确认空表单、中文登录名、过短密码不发送创建请求，修正后只创建一次账号，390 px 管理表单无横向溢出。后端鉴权、密码规则和迁移实现未修改，不需要重启 Worker。

| 检查 | 结果 | 主要覆盖 |
| --- | --- | --- |
| `test_multi_user.py` | 18/18 | 登录／会话／CSRF／所有权、管理员、强制改密、禁用、并发额度、用户范围幂等、未知用量阻断、备份恢复撤销会话、HTTPS Cookie、沿用原图 |
| `test_multi_user_workbench.py` | 1/1 | 管理员创建账号、首次改密、建任务、用量、跨标签页退出、切换账号不残留、他人报告 404、重载会话、390 px 无横向溢出 |
| `test_mysql_handoff.py` | 6/6 | v1 26 表仍可重建；v2 34 表字段、PK、UNIQUE、FK、CHECK 与实际 Alembic SQLite 一致，导出不连接数据库、不污染 v1 |
| `test_browser_session.py` | 9/9 | 原本地会话、Origin／Host、防跨站写入和旧脚本令牌行为不回归 |
| `test_workbench_api.py` | 8/8 | 原前端资源边界、同源 CSP、列表与只读行为 |
| 前端类型检查／Vite 构建 | 通过 | 构建包含登录、个人账号、管理员与原工作台 |
| `frontend test` | 38/38 | 原表单、真实报告映射、API、会话、未知响应不自动重发等 |

同次开发过程还完成既有 `test_modular_system.py` 21 项、`test_operations.py` 25 项、`test_scaffold.py` 29 项和 `test_modular_workbench.py` 1 项回归；这不是对整个仓库所有测试的全量通过声明。MySQL DDL 未在真实 MySQL 执行。

运行命令（仓库根目录）：

```powershell
& migration_system/.venv/Scripts/python.exe -m unittest discover -s migration_system/tests -p test_multi_user.py -v
& migration_system/.venv/Scripts/python.exe -m unittest discover -s migration_system/tests -p test_multi_user_workbench.py -v
& migration_system/.venv/Scripts/python.exe -m unittest discover -s migration_system/tests -p test_mysql_handoff.py -v
& migration_system/.venv/Scripts/python.exe -m unittest discover -s migration_system/tests -p test_browser_session.py -v
& migration_system/.venv/Scripts/python.exe -m unittest discover -s migration_system/tests -p test_workbench_api.py -v
npm.cmd --prefix migration_system/frontend run build
npm.cmd --prefix migration_system/frontend test
```

真实浏览器测试输出位于被忽略的 `var/multi-user-ui-20261118/`，包括登录、管理员、任务排队、账号桌面／窄屏截图和 report.json。随机测试账号及任务只存在于临时 DB，测试结束即关闭清理；截图不作为实际线上用户记录。

## 不变项与边界

- 本次未修改 `engine/`、运行时 `browser/`、`prompts/` 或模型配置 `configs/system.toml`。登录／额度属于原迁移链外围的账号控制，不以此宣称提升迁移通过率。
- 原实验数据库、任务请求／证据、模型费用和失败结论不被自动改写或导入。
- 尚未初始化用户的真实多用户库或设置真实管理员密码；用户须按 [启动指南](../MULTI_USER_GUIDE.md) 完成。
- 已支持受邀可信账号、单服务器单 Worker；尚未部署正式 WSGI／HTTPS、MySQL 或公网不可信源码执行沙箱。登录测试通过不是这些能力的证明。
