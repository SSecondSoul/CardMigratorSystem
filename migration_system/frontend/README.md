# 迁移工作台前端

完整安装和启动以 [系统指南](../SYSTEM_GUIDE.md) 为准。以下命令全部在 `migration_system` 目录内执行，不需要原实验仓库。

## 构建和测试

```powershell
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend test
```

构建结果 `frontend/dist` 由本系统 Flask 同源提供，默认 http://127.0.0.1:8790/，不需要另启前端端口或宽松 CORS。`npm.cmd --prefix frontend run dev` 只监听并重建，刷新工作台查看，不是另一个网站或 HMR 服务。

## 页面与代码

- `src/App.vue`：只切换真实迁移页和开发历史页；历史页按需加载，默认不查询夹具队列。
- `src/components/MigrationWorkbench.vue`：默认真实迁移任务、状态、报告、下载和人工反馈。
- `src/components/DevelopmentWorkbench.vue`：保留早期夹具与 SSM 历史查看，不计为真实迁移结果。
- `src/components/SsmPanel.vue`、`src/lib/ssm-model.ts`：原只读 SSM 面板，本轮没有改写。

真实后台执行命令是 `migration-worker`；`worker` 为它的别名。旧夹具仅使用显式 `development-worker`，不能用夹具通过替代迁移质量。

本地写入令牌在启动 API 的终端生成，填入页面；它不是模型密钥。模型配置和密钥只在 Worker 配置／环境中提供。刷新页面不会自动重交任务，网络错误也不等于组件迁移失败。

## 历史说明

为避免把过期启动步骤当作当前流程，原前端说明与人工确认记录已完整归档到 [历史前端记录](../docs/history/frontend-README_pre_standalone_20261117.md)，不删除旧证据。当前验证汇总见 [开发记录](../DEVELOPMENT_20261116.md)；工程测试通过不等于真实模型通过率已提高。
