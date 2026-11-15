# 真实浏览器隔离接入验证 v1（2026-11-13）

**已从Node miniDOM前进到真实无头Edge，不是完整TaskManager界面/人工验收，也未接入生产。** 固定本地Vue2.7.16/San3.15.6，无CDN、无模型调用；不改v7候选、旧页面、Prompt/规则和原批成绩。验证报告技能用于分开记录浏览器事实、故障注入和remaining_risk。

## 浏览器与隔离方式

Edg/157.0.4341.46，可执行文件SHA256：3e2c8557b5ca4d78868d3089346146ceab94f198ce3d58526ce8f6c8d4b4167c。记录运行版本及运行前后不变的可执行文件指纹，但不声称浏览器二进制已vendoring或将来自动更新后可直接复现。Node内置WebSocket连接本机临时CDP端口，Windows隐藏新建headless进程及临时profile；不复用日常资料。HTTP只监听127.0.0.1随机端口，白名单4路由，不提供目录浏览或任意仓库文件。测试页请求由CDP限制本地origin，无外部页面请求。无需安装Playwright或新依赖。

每场景/变体创建真正同源iframe，固定脚本在iframe的Function/global中执行，原生DOM及native组件父链真实运行；不是Node vm或模拟document。固定时钟、存储故障、业务timer仍为注入装置，调度用真实浏览器Promise和外层原生timer等待。测试结束移除iframe、关闭自己启动的浏览器和临时HTTP服务并清理新建profile。没有调用私有框架错误方法。

## 结果

两次独立浏览器运行的完整native observations相同。每次11场景×3变体×10阶段=33运行、330快照、220比较；v7的110/110阶段在状态、完整业务/捕获事件、原始console和拒绝记录上匹配。原v5九组负向在浏览器仍复现，共51个不匹配阶段，未替换为成功。CDP层异常也完整保留（对应旧v5反例的未处理拒绝），不只查看手工包装console。v7真实实例的配置锁/销毁拒绝与私有入口检查通过，原生San最近error钩子行为保持。

## 失败尝试与边界

首次受限环境尝试在返回观察前CDP连接断开，临时profile清理也失败；原runner、fixture和日志已封存3payload。后续独立启动成功，失败原因仍未定，不武断归为组件或框架错误。失败目录已按明确路径清理，不影响日常资料。

主体render仍替换为最小main节点，**本轮不包含完整模板、子组件UI、CSS、拖拽、设置/任务弹窗或真实存储/timer业务行为验收**。祖先hook/全局handler/logger来自显式隔离应用绑定，并非读取现有RuleBuilder页面配置；不认证真实用户应用映射，也不解决任意回调副作用、一般依赖暂停、SSR或异步钩子问题。原生产验证仍失败的已有证据只引用，不声称本轮重编译或放行。

## 测试与证据

定向测试：{"passed": 57, "failed": 0, "skipped": 0, "suites": [{"suite": "test_async_watcher_browser_v1.py", "passed": 20, "elapsed_seconds": 0.441}, {"suite": "test_async_watcher_scope_v7.py", "passed": 23, "elapsed_seconds": 15.699}, {"suite": "test_parent_watch_scope_guard.py", "passed": 14, "elapsed_seconds": 27.838}], "elapsed_seconds": 43.978, "not_a_full_suite": true, "browser_tests_validate_recorded_live_run_not_launch_per_unit_test": true}。不是完整703项重跑，也不是30样本新批次。旧429项清单（含387生产/既有运行文件）及Notebook旧72单元/元数据保留，新增4文件后433项；本轮8payload，另失败3payload。原批24/30、6失败、0执行异常、1,821,544 tokens不变；无commit/push。

下一步应准备固定版本、完整TaskManager模板和内联子组件的独立人工验收入口，再由用户确认真实界面交互；不应据最小渲染接入测试直接声称整个组件或生产闭环通过。
