# S2：浏览器原生来源登记与逐页存储隔离（2026-11-15）

## 本步结论

新增独立 v3 评估入口及原生 session 登记，不改旧 v1/v2 或生产 visual_eval。五类存储在两页间隔离、同一页刷新后保留的控制成立；来源不再按报错里“Vue/San”文字或全局日志区间推断。**这是测试设施改进，不是新增组件修复、自动 repair 接入或新迁移通过率。**

使用仓库 vue-san-validation-report 技能区分自动控制、冻结组件复核与残余风险；未启动 Notebook UI，也无新人工验收。人工页面、组件源码与旧成绩均不改。

## 来源与隔离实现

每页创建新的 CDP BrowserContext／target／session，保存 runId、真实本地 origin、页面序号／HTML SHA、executionContext、主 frame 及比较对 source/target 角色。ready 后和重复截图后各保留一份真实 Target.getTargetInfo／Page.getFrameTree 响应；identity 不匹配即阻断。异常、console error/warning、Log error/warning 和被拒请求绑定实际 session；未知／冲突／销毁后事件保留复核，不转移所有者。

每个 session 只允许自身精确本地 GET 页面；不放行同服务器别页、query、别端口、非 GET 或未知 session。上下文处置、传输、清理异常均不作为业务代码修复理由。全局 complete=false 会保守阻断本次比较，不选择性隐藏设施问题。

页面间使用不同上下文；场景内刷新保留自己的 localStorage、sessionStorage、Cookie、IndexedDB、Cache Storage。没有注入默认主题、删用户存储或改业务行为。清理只针对本次新建的临时 profile；最小失败探针残留的 `cardmig-pixel-v3-OLR42L` 已按精确绝对路径校验后移除，不可恢复但没有用户数据。

## 实际证据

| 证据 | 结果 | 边界 |
|---|---|---|
| controls_final、controls_verified：各6个合成页、15项控制 | 两次全部成立，跨启动截图指纹一致 | 独立脚本返回0；底层故意错误／跨页反例仍blocked，不是组件通过 |
| 37项纯登记用例 | 未知session、错context/target/URL、误导文本、延迟事件、跨页／异端口请求等均正确限制 | 合成单元证据 |
| 16项已记录证据测试 | 来源、隔离、原生响应、销毁和重现检查通过 | 不重新启动浏览器 |
| 冻结3组件、5静态场景、10页原生重放 | 13项预定检查全部成立；10个context/session不同，均验证并销毁 | VolumeControl、BatchRenamer、AnalyticsDashboard开发样本，非独立holdout |
| 与旧完整页比较 | 10页HTML／截图SHA及业务观察不变；前4场景视觉匹配 | 不代表完整交互或4/5迁移通过率 |
| Analytics | 10条诊断均归Vue；San干净；1326/1625高度差、7项矩形差保留，无伪造SSIM | 仍需源基准与目标视觉差复核，不算新修复成功 |

真实浏览器为 Edge 157.0.4341.60，二进制 SHA256：
`2497874639116d8edc3de34b3fd83f72fa099112a5d2a426e1f08fcf39a99612`。
未安装依赖，不使用 `--no-sandbox`。原始环境、截图、输入HTML和CDP记录在各子目录 result.json／input.json 中，完整实现保存在 implementation.json。

## 不成功尝试与修正

- controls：受限执行环境的浏览器连接中断，6页均blocked。最初控制报告尝试读取缺失componentEvidence而KeyError，不能视为通过；原始记录保留。
- context_smoke：最小页面重现浏览器GPU子进程访问失败，stderr最终报告“GPU process isn't usable”，exit2147483651；不能把它归因为组件或BrowserContext功能错误。正常本机权限重跑后可完成。未放宽浏览器安全沙箱。
- controls_retry：五类存储控制成立，但fetch请求先被现有CSP connect-src拒绝，没有触及新增Fetch层，因此3项反例不成立，报告allPassed=false。改用CSP允许到达拦截器的图片请求，再在controls_final和controls_verified验证15/15。
- 一次只读进程清单检查被拒绝；一次读取已清理的临时调试端点得到ENOENT。均未改系统权限或用户浏览器状态。
- 原始失败目录未覆盖或删除；first_attempt_implementation.json保留首轮实现。只有本任务临时profile执行清理，结果已记audit。

## 测试与不变量

本轮分别执行：新53＋旧反馈50＋SFC封装39＋repair Prompt/loop34＋任意动态键保护12＝**188项通过**。非全仓库测试，也非旧273项campaign。tests.json保存各suite计数／退出状态；前三suite保留完整输出，后两suite仅保存已观察的成功摘要或结尾，不冒充完整日志。旧repair测试用stub，未调用付费模型。

69个旧相关实现／测试、3个人工配置、6个冻结组件输入和上轮21payload封存保持指纹不变。Notebook仅追加，保留旧135单元及metadata。旧批次仍configured30／passed24／failed6／execution_errors0／tokens1821544，不回填新分数。任意公开键、通知／异常阶段未解决结论不豁免。

## 接下来与限制

新输出是schemaVersion3。旧browser_feedback_v1仍只接受schema2，**不能直接把新记录接进旧预览或生产repair**。下一步建立原生登记的外部固定封存校验与反馈适配，测试未知／篡改身份与过期代码拒绝，再固定错误级别、状态场景和阈值协议；之后才讨论批处理生产接入。

本步只证明空存储初态下五类API的控制和同页刷新，没有证明预置存储／登录／权限／service worker／多窗口共享或所有浏览器状态；不认证恶意评估记录，不是安全沙箱。没有全交互、跨机器字体或永久稳定证明。不新增互操作、provider或业务调用方协议，不直接付费跑30项／独立测试。未commit／push。

接口及命令：`docs/ir-design/browser-session-isolation-v1.md`。
