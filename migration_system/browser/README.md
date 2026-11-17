# 浏览器执行器

早期此目录仅为预留；当前已实现以下模块，旧 CDP 记录保持不变。
# 当前模块化评估器

2026-11-16 新增 `evaluate.mjs`、`metrics.mjs` 和独立锁文件。真实主图通过 Python `adapters/browser.py` 调用，不连接旧人工测试页或用户浏览器会话。使用 Puppeteer-core 与本机 Chromium／Edge；双端各新建 context，拦截外部请求，固定视口／样式环境。

执行 San 模板解析、Vue 运行编译、真实截图、DOM／计算样式／表单状态和代表动作采集；PNG 使用亮度 8×8 SSIM、RGBA 阈值不同像素率和热图。不自动删除源警告或掩盖随机差异。

```powershell
npm.cmd --prefix migration_system/browser ci --ignore-scripts --no-audit --no-fund --cache migration_system/var/npm-cache
npm.cmd --prefix migration_system/browser test
```

安装使用独立 `node_modules`，没有修改根目录依赖。具体范围、容量、指标公式和安全边界见 [系统指南](../SYSTEM_GUIDE.md)。浏览器是可信组件执行环境，不是恶意脚本的 OS 沙箱。下文如有早期预留说明，属于本模块建立前历史。

