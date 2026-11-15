# 显式应用错误报告器：隔离候选 v5（2026-11-13）

**只闭合“显式提供、同步返回、只记录而不读写组件状态的报告器”这一测试约定；默认异常策略没有闭合。** formal_30_v4开发探针，非正式独立测试或新30样本成绩。原批24/30、6失败、0执行异常、1,821,544 tokens不变；0模型请求，无新增人工验收。

## 根因和实际改动

Vue原生逐个调用用户watcher时处理异常；原合并Promise队列中的一个回调抛错会退出flush，使后续回调不执行。v5只在源顺序队列的单个dispatch外加try/catch，以及一个实例级报告器配置方法。报告器收到原Error对象、当前组件及精确watcher归属，以null作为this；返回后继续下一个watcher，但绝不恢复已失败回调内部的剩余语句。不重试存储、不加默认日志、不改Promise拒绝或全局框架配置。没有报告器就重新抛出原异常，报告器自身抛错也继续向外传播；这些失败不是已实现的Vue全局回退。

AST差分仅一个dispatch catch和一个配置方法；队列排序/去重/取消、v4引用/观察桥、完整源赋值右侧及业务方法/事件/生命周期其余脚本不变。需要显式experimental及error_policy参数；配置方法是实验应用适配入口，未在生产应用接入，不是给原源API添加限制。

## 原生运行时对照

固定Vue2.7.16/San3.15.6。9场景×3变体×10阶段=27运行、270快照、180源/目标阶段比较。6个明确报告约定场景中，源/v5的60/60阶段在状态、完整业务事件（含应用错误报告）、警告上匹配。覆盖无异常、tasks失败后settings继续、settings失败不执行自身后续同步、同轮两个watcher各报一次、后轮失败保留旧计时器、报告器返回false不误终止队列。错误身份、组件归属、watcher信息、先后顺序均检查。

rawErrors保留Vue.config.errorHandler与San实例报告器的不同通道，不能说原生框架报错标签相同；共同应用报告事件的比较不是删除原始错误。旧v4无报告器对照也保留。localStorage/应用timer是明确的故障注入装置，不是真实浏览器存储或业务timer执行；原生框架/Promise实际运行。

## 仍失败的边界（完整保留）

[
  {
    "scenario": "headless_default_not_closed",
    "mismatch_phases": [
      "primary_tick",
      "repeat_sync",
      "repeat_tick",
      "recovery_sync",
      "recovery_tick",
      "destroy_sync",
      "destroy_tick"
    ]
  },
  {
    "scenario": "missing_target_reporter_not_closed",
    "mismatch_phases": [
      "primary_tick",
      "repeat_sync",
      "repeat_tick",
      "recovery_tick",
      "destroy_sync"
    ]
  },
  {
    "scenario": "throwing_reporter_not_closed",
    "mismatch_phases": [
      "primary_tick",
      "repeat_sync",
      "repeat_tick",
      "recovery_sync",
      "recovery_tick",
      "destroy_sync",
      "destroy_tick"
    ]
  }
]

这三组共30阶段里仍有差异。源Node默认抛错会影响原生调度队列后续状态；v4/v5未实现这一策略。缺少目标报告器不能静默退回console；报告器抛错的全局回退、errorCaptured、异步/可重入报告器、组件状态依赖收集、浏览器默认路由也未证明。旧冻结9场景原装置在不配置报告器时的全部观察与v4逐字节相同，旧两种异常失败没被替换为成功；旧native子组件装置观察也原样保留。

## 应用现状（仅本地脚本静态核对）

本地Vue runner没有显式Vue.config.errorHandler声明；San runner没有接入上述实验入口。验收页的window error/unhandledrejection监听只记录事件，不构成watcher恢复策略。Vue CDN为@2浮动主版本，San页引用3.15.3，而探针使用固定2.7.16/3.15.6；未联网取CDN、未启动页面，不推断浏览器实际全局配置，更不改测试页。故不能把本次显式测试约定自动当作现有应用默认策略。

## 验证及证据

定向测试：{"passed": 57, "failed": 0, "skipped": 0, "elapsed_seconds": 53.453, "suites": [{"suite": "test_parent_watch_error_router_v5.py", "passed": 20, "elapsed_seconds": 11.587}, {"suite": "test_parent_alias_observer_v4.py", "passed": 23, "elapsed_seconds": 14.16}, {"suite": "test_parent_watch_scope_guard.py", "passed": 14, "elapsed_seconds": 27.706}], "not_a_full_suite": true}。未重跑完整703项；历史完整成绩仅引用旧日志。候选San编译通过，生产验证仍失败；动态键/异常策略诊断及伪造通过保护均保留。原409文件（含387生产/既有运行文件）、30个保留输入/Vue、两个测试页及旧Notebook62单元/元数据保留；新增4文件后413项，9个payload封存。

下一步应验证源浏览器默认错误链/祖先捕获和报告器异常回退，或先明确应用真正采用的报告契约；在此之前不接入生产、不启动模型复跑、不改原批成绩。当前显式报告约定是候选可选能力，不是完整异常闭环。
