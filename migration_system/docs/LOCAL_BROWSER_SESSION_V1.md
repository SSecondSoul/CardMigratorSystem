# 本地浏览器会话 v1

2026-11-18：将普通工作台的手动写入令牌改为自动会话；仅改变访问控制与页面，不改生成／修复 Prompt、SSM、评估器、质量门或模型预算。

## 使用范围

只用于 `127.0.0.1`／`[::1]` 的本机单用户工作台。它不是账号登录，不防御已控制本机的程序／其他操作系统用户或同源脚本被篡改；禁止据此宣称支持公网或多用户部署。模型 API Key 始终留在 Worker。

## 流程与边界

1. 工作台以自定义 `X-Cardmig-Session: bootstrap` 请求 `GET /api/v1/browser-session`；普通页面导航不能取得会话，外站 CORS 预检不获放行。所有路由继续校验 Host／Origin；浏览器会话和写操作还拒绝非 same-origin 的 Fetch Metadata。
2. API 签发短期 Cookie：HttpOnly、SameSite=Strict、host-only、路径 `/api/v1`，按端口命名。当前为本机 HTTP，Cookie 在 HTTPS 下自动增加 Secure；不允许借此扩展公网 HTTP 部署。
3. 响应只含防跨站随机值与有效期，不返回服务器实验写入令牌。前端仅在内存缓存随机值，写操作使用 `X-Cardmig-CSRF`，后台同时核验签名 Cookie、绑定的 Host、过期时间及随机值。不把 Cookie 单独作为写权限，也不使用 localStorage 保存凭据。
4. 签名密钥为每次 API 启动随机生成；会话 8 小时过期，重启即失效。刷新页面会重新连接。凭据过期或校验失败不会重放 POST；用户核对任务列表后决定是否重新操作。上传源码、只读轮询和建立会话均不自动入队或调用模型。
5. 原 `X-Cardmig-Token` 实验脚本方式保留：启动 API 前可设置 `CARDMIG_SYSTEM_WRITE_TOKEN`；未设置时自动生成内部令牌。显式提供错误令牌时拒绝请求，不偷偷回退会话授权。旧开发夹具仍走原令牌方式，与普通用户工作台分开。

## 版本与验证

API 认证文件属于现有整体实现指纹，变更后应等待当前任务结束，再重启 API 和迁移 Worker；不要篡改旧任务绑定以续跑。历史任务／报告不改判，不自动重跑，不删除现有数据库。

回归入口（均在 `migration_system` 目录）：

```powershell
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend test
& .venv/Scripts/python.exe -m unittest discover -s tests -p test_browser_session.py -v
& .venv/Scripts/python.exe -m unittest discover -s tests -p test_modular_workbench.py -v
& .venv/Scripts/python.exe scripts/verify_workbench_ui.py --output var/workbench-session-new
```

会话单测覆盖 Cookie 属性、双凭据、外站请求、导航／预检、客户端隔离、篡改、过期、重启／端口隔离和旧令牌兼容。浏览器提交联调用临时数据库，验证无令牌创建、刷新后会话可用、不重复提交及取消任务；不启动 Worker，不产生模型费用。布局测试仍只读临时冻结任务副本，不把工程测试通过计为组件迁移通过。

已执行：前端类型检查／构建及 38 项前端测试；会话专项 9 项（含无环境令牌启动）；既有工作台 API 8 项；既有持久化控制闭环 22 项；无令牌真实提交／刷新／取消联调 1 项；三种尺寸只读布局验证。均使用临时库或临时冻结任务副本，实际模型调用为 0。布局报告在 `var/workbench-ui-browser-session-01/report.json`，不作为迁移质量通过证据。
