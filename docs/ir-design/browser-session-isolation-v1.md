# 受控浏览器原生来源登记与逐页存储隔离 v1

本层是源码迁移评估器的开发校准，不要求用户提供新的业务材料，不增加 Vue/San 互操作能力，不调用模型，不代表生产反馈已放行。

## 实现

- `migration_pipeline/run_controlled_browser_pixel_v3.cjs`：独立于旧 v1/v2 的无头 Edge 入口，继续使用完整页面、固定环境、显式 ready、重复观测和既有像素算法。
- `migration_pipeline/utils/browser_session_registry_v1.cjs`：保存随机 runId、实际本地 HTTP origin、输入页面序号与 HTML SHA、CDP browserContextId／targetId／sessionId、主 frame 及 executionContext。source／target 角色来自已声明的比较对，不来自错误文字。
- 每页使用 `Target.createBrowserContext` 新建临时独立上下文，目标显式放入该上下文；关闭目标后 `Target.disposeBrowserContext`，最终清理本次专用临时 profile。不会读取或清空用户已有浏览器资料。
- 准备好和重复截图后分别用 `Target.getTargetInfo`、`Page.getFrameTree`核验真实 context／target／主页面 URL，保留原始响应。不能仅拿调用栈 URL 猜所有者。
- Runtime exception、console error／warning、浏览器 Log error／warning、被拦截请求都保存 session 所有者。未知 session、未知 executionContext、不同文档 URL 或销毁后的事件保留为未核验，不重分配给下一页。
- 网络拦截按 session 只允许自身页面的精确 GET URL；同一 loopback 服务里的其他页面也不允许，query、其他端口、非 GET 或未知 session 一律拒绝。CSP 继续禁止 connect／frame／worker；不开放真实网络。
- 所有页面完成后重新按所有者计算 clean，替代按全局日志长度区间切片。未知归属、原生身份未完成、清理失败仍阻断，不能转成组件代码修复。

## 存储策略

页面之间采用不同 BrowserContext，因此默认不共享 localStorage、sessionStorage、Cookie、IndexedDB 或 Cache Storage。**同一个页面场景里的刷新不清空存储**，用于验证保存设置后刷新；不同页面或新场景重新创建上下文。

不注入主题或业务设置，不重写组件代码。当前仅支持空存储初态；旧用户存储迁移、导入预置状态、多窗口共享、登录、权限、service worker 生命周期、跨域资源、文件系统及其他未测存储 API 不在本轮实证范围。不能把五类控制结果外推成全部浏览器状态或安全沙箱证明。

## 可复现入口

在项目根目录、新输出目录下执行；需要本机可正常启动 GPU／renderer 的 Edge 权限，**不使用 `--no-sandbox`**：

```powershell
python -m migration_pipeline.calibrate_browser_session_isolation_v1 `
  --output-dir data/experiments/analysis/my_new_session_controls

python -m migration_pipeline.replay_frozen_browser_session_v1 `
  --output-dir data/experiments/analysis/my_new_native_frozen_replay

python -m unittest discover -s tests -p test_browser_session_registry_v1.py -v
```

前一入口有故意的 warning／跨页网络反例，底层浏览器结果应为 blocked；外层校准脚本只在预先规定的正反控制全部成立时返回 0。这是测试设施保护通过，不是负例组件通过。

## 接入限制

输出采用 `schemaVersion:3`，含 `nativeRegistry` 与 CDP 传输记录。此前 `browser_feedback_v1.py` 仍只消费旧 schema v2，不应改字段冒充兼容或强制放行。下一步须为原生 schema 建立独立的封存校验／反馈适配并冻结错误级别、状态场景与阈值协议，再接生产 repair；目前自动 dispatch、生产 Prompt、候选语义门和历史成绩均不变。

来源登记证明已知评估器实测时的映射，不认证任意生产者提交的伪造记录；仍需可信代码、外部固定封存指纹和独立验证。任意公开键、通知与异常阶段的既有阻断不豁免。静态视觉一致不等于完整交互或迁移语义等价，也不是独立测试集结论。
