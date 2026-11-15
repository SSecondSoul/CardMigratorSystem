# 受控浏览器／像素评估器 v1

本入口是论文收尾 S2 的隔离原型，**不替换旧 visual_eval，不放行语义阻断，不修改历史成绩**。输入是已准备好的可信、自包含 HTML 页面及显式关键元素映射；不是自动 Vue/San 工程编译器，也不要求使用者提供运行时互操作协议。

## 运行

项目根目录、原 Python 环境中执行；需要 Node 原生 WebSocket 和本机 Edge，本轮实测 Node24.19.0／Edge157。不启动 local_server、不需要密钥、不安装依赖。

```powershell
python -m migration_pipeline.calibrate_controlled_browser_pixel_v1 `
  --output-dir data/experiments/analysis/my_new_pixel_calibration
```

必须使用不存在的新目录。校准器验证已知正、负样例，校准成功不等于样例都被判通过：错误、变化页面的评估状态应是 blocked。额外失败路径校准：

```powershell
python -m migration_pipeline.calibrate_controlled_browser_pixel_v1 `
  --output-dir data/experiments/analysis/my_new_pixel_failures `
  --failure-modes-only
```

底层 `migration_pipeline/run_controlled_browser_pixel_v1.cjs` 从 stdin 读取 JSON，导出 `run(input)`；页面参数为 `pages:[{name,html,selectors:{业务标识:CSS选择器}}]`，比较参数为 `pairs:[{source:页面名,target:页面名}]`，还需 `outputDir` 与 `thresholds:{pixelTolerance,maxChangedPixelRatio,minSSIM}`。缺阈值不默认通过。当前底层 CLI 的0退出码仅表示完成评估，**调用方必须检查 JSON 的 status、eligible 和 passed**；blocked或启动失败为2。Python校准器只在所有预期控制成立时返回0。

## 控制与输出

- 隐藏的 headless Edge，新建专用临时 profile、本机随机端口和白名单路由，不连接用户资料；完成后关闭自己的浏览器并清理自己的目录。
- 640×480、DPR1、浅色主题、zh-CN、Asia/Shanghai、固定 Date／随机种子、Arial默认字体、禁用动画／过渡／光标闪烁。对业务而言这是显式受控输入，并非证明任意时刻／随机输入都等价。
- 页面必须设置 `window.__visualReady === true`，等待字体及两帧后截图；120ms后再次截图。仅两次采样相同，不证明以后永久稳定。
- 关键选择器必须唯一、可见尺寸非零且完整位于视口；文档溢出直接阻断，**暂不支持 full-page／滚动长页面**，不默默裁切成通过。
- 保存输入、两张真实 PNG、关键计算样式／矩形、RGB差异比例／MAE、SSIM、差异热图及错误。网络请求受CSP和CDP双重限制；CSP拒绝也由Log域计入错误，不要求请求真的发到外网。
- PNG仅支持8位RGB/RGBA、不透明、非交错；CRC及扫描行格式错误阻断。不缩放、不配准、不遮罩、不自动改对比度。
- 差异像素：RGBA最大通道差超过 pixelTolerance；分母为全视口像素数。MAE为RGB原始0..255绝对误差均值，不受像素容差抹除。
- SSIM：BT.601灰度、11×11高斯窗口sigma1.5、valid区域、总体矩、L255／K1=.01／K2=.03。不是色彩指标，不可代替RGB差异或关键样式判断。浮点误差允许同图略小于1。
- 关键矩形和21项计算样式精确比较，作为额外必要条件。当前是严格校准口径，**不是已选定生产阈值**，不据本次样例事后放宽。

## 尚未完成的生产接入

下一步应建立真实冻结 Vue／San 产物到自包含页面的可靠适配，保留完整模板、子组件、默认 props 和CSS；声明必要依赖、就绪条件、输入种子、状态场景和关键元素映射。选择简单／中等／复杂开发样例校准，给长页面及资源建立明确策略后，再冻结评估协议及接入批处理。不能通过改动生成组件让评估器“看起来一致”。

当前小样例只验证原生Vue2.7.16和San3.15.6能在同环境形成相同画面，不代表Trip、TaskManager或30组件通过。没有交互操作、方法接口或通知／异常语义等价证明；现有任意公开键阻断及未决风险保留。浏览器二进制和字体未随仓库vendoring：记录版本／文件指纹供漂移核对，但不能声称跨机器像素可直接重现。HTML需可信；这不是恶意脚本安全沙箱。网络限制针对页面，不保证操作系统／浏览器后台服务绝对无通信。

实现参考：[Edge DevTools Protocol](https://learn.microsoft.com/en-us/microsoft-edge/devtools/protocol/)、[Page.captureScreenshot](https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-captureScreenshot)、[Emulation](https://chromedevtools.github.io/devtools-protocol/tot/Emulation/)。本原型复用仓库已有CDP路径；未来依赖与维护策略另行冻结。
