# 父监听时序真实 Vue 对照（2026-11-11）

本轮只建立运行 oracle，不改生产规则/Prompt、canonical San 或测试页。0 模型请求；原批次仍 24/30、6失败、0执行异常、1,821,544 tokens。不是新批次、独立测试或人工验收。

隔离获取官方 Vue2.7.16 npm 发布包，核对官方 dist sha512/sha1；只提取 runtime、LICENSE、package.json，不安装依赖、不运行脚本、不改项目 package/lock/node_modules。完整包、精确运行时字节与来源记录同时冻结。Vue2页只锁 vue@2，未证明浏览器实际补丁版本；本 oracle 不替代该页面。官方说明参见 [异步更新队列](https://v2.vuejs.org/v2/guide/reactivity.html#Async-Update-Queue)、[固定版 initWatch](https://raw.githubusercontent.com/vuejs/vue/v2.7.16/src/core/instance/state.ts)、[固定版 scheduler](https://raw.githubusercontent.com/vuejs/vue/v2.7.16/src/core/observer/scheduler.ts)。

## 实测方法

5存储场景×3版本（源Vue、当前San、只在内存提前注册的San）=15次执行，每次18个同步/nextTick阶段，共270份状态/事件快照。实际 Vue 根构造、响应式深监听、默认 async 队列、$mount→mounted 与 $destroy→beforeDestroy；render替为无子组件的空根VNode，Node无DOM patch，不声称测试源模板。San实际构造/inited/内建watch/nextTick/native dispose；attached应用钩子直接调用，无完整DOM attach。独立vm沙箱，固定Date，模拟localStorage/应用interval/timeout；真实框架Promise队列，不用自写Vue调度器。通知3000ms回调与周期同步未触发，不说所有timer都清理。

## 初始化保存次数

| 存储场景 | 源Vue | 当前San | 仅提前注册San |
| --- | ---: | ---: | ---: |
| empty | 1 | 0 | 1 |
| saved_manual | 2 | 0 | 2 |
| saved_autosave_off | 0 | 0 | 1 |
| saved_interval_30 | 2 | 0 | 2 |
| malformed | 1 | 0 | 1 |

源在构造期注册tasks/settings，mounted同步加载完成后异步监听；当前San加载后才注册，初始化效果漏掉。同轮两次任务标题修改，源只运行一次tasks监听，San运行两次；先改settings两次再改tasks，源仍按声明次序tasks→settings各一次，San为settings→settings→tasks，保存中间态且重复重启interval。已保存30秒设置时，源先由mounted启动一次、再由settings watcher清理重启一次，这是源实际行为，不擅自“优化掉”。

仅提前注册不是合格修复：恢复数据原为autoSave=false/30秒，San tasks同步回调先按默认autoSave=true/60秒写回存储，settings恢复后不再保存，磁盘模拟状态停在错误默认设置。该对照只改内存AST，未应用生产，不计为已实施修复回归。

销毁前改设置：源$destroy前尚未执行待排watcher，beforeDestroy只保存一次；San立即监听先保存并建interval，再disposed保存并清理，共2次保存。真实框架销毁后再改数据均无监听/保存，活动interval归零；仍有源本来未取消的通知timeout，本轮不触发它，也不谎称全timer无泄漏。

将此前父监听remaining_risk升级为1类已复现迁移缺陷（调度/时机语义缺口，多个症状不重复计数）。不是原生drag规则或工厂规则失效，也不是本轮引入。没有浏览器/子组件事件或原始30批次复跑；不更新分数。

## 验证与下一步

诊断测试 14/14，0失败/0跳过，1.874秒；不是完整644项重跑（引用上轮1140.378秒日志，不拼接成绩）。现有370项生产清单原字节不变。先前网络沙箱拒绝与官方直接获取步骤保留在audit.json；没有用“没拿到运行时”阻塞后伪造Vue队列。

后续规则必须同时证明：首次注册早于源初始化、每实例每字段去重、按源注册顺序批处理、回调读取执行时最新值、清空本轮pending后处理回调中新变更、销毁使待排任务无效、同源持久化/计时器副作用。源码若使用sync/immediate、未知路径/额外effects或不能证明闭合依赖，需拒绝自动改写。不能只移动watch，也不能只加Promise或任意防抖。再同步验证器/候选保护/回归，使用本冻结oracle验收，完成前不付费复跑。
