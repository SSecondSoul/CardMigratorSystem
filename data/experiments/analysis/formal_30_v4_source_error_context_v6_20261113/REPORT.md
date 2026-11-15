# 源错误上下文桥：隔离候选 v6（2026-11-13）

**实现了显式映射、同步只报告、不读写响应式状态的浏览器错误上下文协议；不等于生产异常闭环。**
formal_30_v4 开发探针，非独立正式测试。原批仍为24/30、6失败、0执行异常、1,821,544 tokens；0模型请求，无新增人工验收。

## 根因与修改位置

v5合并Promise队列的异常缺少Vue祖先捕获/全局回退上下文；San原生最近error钩子语义也不能直接替代Vue errorCaptured。新增独立helper及AST探针，仅在v5之上插入helper工厂、实例配置方法及dispatch分支。源赋值右侧、队列、观察桥、业务方法、事件和生命周期其余脚本通过AST反向还原确认未改。不是生成/修复阶段生产Prompt改动，也未接入生产repair.py。

应用必须明确提供原生父链、钩子列表、全局处理器getter和终端日志sink；从近祖先到远祖先、同祖先声明顺序调用，仅严格false短路。捕获钩子抛错后将次生错误归属该祖先，按errorCaptured hook进入全局，再继续原错误。全局抛不同错误先记录次生再原错误；重抛原错误不重复记录。无handler时交给显式终端sink，继续队列，不重试失败回调内部语句。不猜测San.error映射、不安装全局补丁。

## 受控原生证据

固定Vue2.7.16/San3.15.6和冻结miniDOM；11场景×3变体×10阶段=33运行、330快照、220源/目标比较。显式映射v6的110/110阶段在状态、完整事件、原始console、Promise拒绝记录上匹配。旧source/v5的22运行和110比较完整不变，九组负向仍在；没有把历史失败覆盖成成功。另22个独立原生San watch控制证实最近error返回true仍不冒泡，未改全局San语义。

**传播协议与诊断文字分开负责。** 核心helper不实现Vue通用组件trace；本次应用装置显式映射subject/near/far源名称，并提供有界、非递归的诊断格式适配器，因而这些fixture的raw console能相等。该适配器是冻结runtime harness源码，不是生产日志实现，更未证明任意组件栈/重复栈/递归格式。真实native parentComponent关系已检查，但源应用映射由装置显式给出，不是自动迁移成果。

主体渲染替换为最小节点，业务/生命周期方法体不改。故障存储与应用timer为注入装置；原生框架、Promise和祖先挂载真实执行，但未打开真实浏览器，不是TaskManager UI/CSS或真实存储验收。纯helper无效映射单测另存，不冒充native框架证据。

## 保护与残余风险

未配置v6时，旧浏览器全量观察及旧headless显式报告器审计均原样保留（含失败）；旧native子组件观察保持。候选San本轮编译通过，生产验证仍失败；独立动态键/异常策略诊断和伪造通过保护仍阻止放行。

受控profile声明不读写响应式状态，**未实现也未证明依赖收集暂停，运行时不强制hook纯度**。任意应用祖先/config映射、异步/可重入hook、SSR/Node回退、抛错日志sink及通用trace仍未闭合；不能以调用者声明代替这些证明。缺少context时仍走原v5行为，不默认吞错。九种场景是同一剩余风险的展开，不计为九条生产缺陷，也不增加人工通过数。

## 测试与封存

定向测试：{"passed": 78, "failed": 0, "skipped": 0, "elapsed_seconds": 59.812, "suites": [{"suite": "test_source_error_context_v6.py", "passed": 24, "elapsed_seconds": 13.852}, {"suite": "test_browser_error_chain_audit_v1.py", "passed": 20, "elapsed_seconds": 1.418}, {"suite": "test_parent_watch_error_router_v5.py", "passed": 20, "elapsed_seconds": 12.696}, {"suite": "test_parent_watch_scope_guard.py", "passed": 14, "elapsed_seconds": 31.846}], "not_a_full_suite": true}。不是完整703项重跑。旧416项清单（含387生产/既有运行文件）、30保留输入/Vue、测试页/验收脚本、Notebook旧66单元和元数据未变；新增5文件后421项，10个payload封存。candidate .san仅为分析目录中的离线证据，不替换canonical产物。

下一步应先证明真实应用上下文映射与响应式依赖边界，再决定能否接入；不能直接启动付费模型复跑或宣布完整闭环。不修改生产Prompt/规则、页面、原成绩，不commit/push。
