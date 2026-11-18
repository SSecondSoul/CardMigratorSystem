# 迁移工作台前端

2026-11-18 界面更新：按参考图调整为青绿色侧栏、任务列表、六阶段进度和详情页签。接入真实报告数据，不使用示例通过率或示例截图；迁移生成、评估与修复算法不变。构建后在原地址硬刷新即可，无需新开前端端口。

界面改版验证：前端类型检查／构建、33 项前端单元测试、真实提交联调 1 项、相关 API 检查 8 项及实验复用检查 5 项通过。真实浏览器使用冻结失败任务的临时副本，核对 1586／1024／390 px 三个尺寸及工作台交互；未调用模型、未改实际任务。生产 Python／引擎／运行时浏览器文件与原指纹一致，旧迁移封存 520 项 payload 哈希不变。没有把 UI 改版当作迁移通过率提升。

用户界面精简复验：移除实验对比页面；新建任务固定 SSM＋有界修复；取消下方确认勾选展示。构建、34 项前端测试、临时数据库真实提交测试和三个尺寸浏览器复核通过。提交测试确认仍发送 `strategy: "ssm"`、`trusted_source: true` 和 `confirm_model_calls: true`；只在用户点击创建时提交，不因上传源码自动创建任务。后台字段及基线／消融策略仍保留供实验使用，历史任务仍展示实际策略。可信源码执行及模型费用改为说明文字，不再是提交前的勾选门槛。本次未修改迁移引擎、后台接口或真实任务。

本地会话更新：普通工作台移除新建弹窗和设置页的令牌输入，API 增加自动会话及防跨站写入校验，CLI 无需配置写入令牌即可启动。构建和 38 项前端测试通过；临时数据库真实浏览器验证无令牌创建、刷新后可继续使用且不重交任务、取消任务、Cookie 对脚本不可见。1586／1024／390 px 页面复核无错误／无写入，新增会话专项及既有 API／控制闭环回归分别记录在 [会话说明](../docs/LOCAL_BROWSER_SESSION_V1.md)。未调用云模型、未更改真实任务。与上次纯页面调整不同，本次 API 代码发生变化，需要重启 API／Worker 并创建新版本任务，不能强行续跑旧绑定。

完整安装和启动以 [系统指南](../SYSTEM_GUIDE.md) 为准。以下命令全部在 `migration_system` 目录内执行，不需要原实验仓库。

## 构建和测试

```powershell
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend test
```

构建结果 `frontend/dist` 由本系统 Flask 同源提供，默认 http://127.0.0.1:8790/，不需要另启前端端口或宽松 CORS。`npm.cmd --prefix frontend run dev` 只监听并重建，刷新工作台查看，不是另一个网站或 HMR 服务。

## 页面与代码

- `src/App.vue`：侧边导航与顶栏；开发夹具按需加载，与真实迁移分开。
- `src/components/MigrationWorkbench.vue`：工作台、可搜索／筛选的任务记录、连接设置及详情组合。
- `src/composables/useMigrationWorkbench.ts`：真实任务读取／提交、轮询、产物下载、取消／同版本恢复及人工反馈；只读请求不携带写入令牌，不自动重试写入。
- `src/components/workbench/`：新建弹窗、质量卡片、截图并排／透明叠加／真实差异热图、San 代码、修复候选／回退、产物和人工验收。
- `src/lib/migration.ts`、`migration-api.ts`：真实迁移的类型、显示投影、表单校验与同源请求。缺失指标显示“—”，未配置交互显示“未测试”。
- `src/workbench.css`：本轮布局样式，`cm-*` 命名空间避免影响历史开发夹具。
- `src/components/DevelopmentWorkbench.vue`：保留早期夹具与 SSM 历史查看，不计为真实迁移结果。
- `src/components/SsmPanel.vue`、`src/lib/ssm-model.ts`：原只读 SSM 面板，本轮没有改写。

真实后台执行命令是 `migration-worker`；`worker` 为它的别名。旧夹具仅使用显式 `development-worker`，不能用夹具通过替代迁移质量。

普通工作台不再填写本地写入令牌：启动后自动取得短期 HttpOnly／SameSite=Strict 会话 Cookie，写请求附带仅存页面内存的防跨站凭据。会话 8 小时有效，API 重启失效；刷新后自动建立会话，但绝不重交任务。会话过期／校验失败时停止原写入，提示刷新状态后由用户决定是否重新操作。此功能仅限本机单用户，不替代公网账号认证。模型配置和密钥仍只在 Worker 配置／环境中提供；实验脚本和旧开发夹具保留原令牌入口。

列表为接口返回的最近 100 条以内任务；搜索和分页作用于已返回记录，不宣称检索整个数据库。设置页显示操作会话状态，除轮询开关外为只读，不能假装已修改服务器 TOML。API 环境提示与 Worker 真实调用收据分开解释。

本轮浏览器测试脚本置于 `tests/browser/`，不新增或修改迁移运行绑定中的 `browser/` 实现文件，避免纯 UI 测试导致旧任务实现指纹漂移。使用临时数据库复验页面（不调用模型、不修改真实任务）：

```powershell
& .venv/Scripts/python.exe scripts/verify_workbench_ui.py --output var/workbench-ui-new
& .venv/Scripts/python.exe -m unittest discover -s tests -p test_modular_workbench.py -v
```

## 历史说明

为避免把过期启动步骤当作当前流程，原前端说明与人工确认记录已完整归档到 [历史前端记录](../docs/history/frontend-README_pre_standalone_20261117.md)，不删除旧证据。当前验证汇总见 [开发记录](../DEVELOPMENT_20261116.md)；工程测试通过不等于真实模型通过率已提高。
