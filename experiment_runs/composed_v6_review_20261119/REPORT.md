# 通用修复 v6：两轮根因与真实离线验证

## 结果口径

真实新生成批次仍为 **15/70**。本次只读冻结源码与模型产物，模型调用为 0；离线候选有效通过 28/70，不可改写为新的真实模型通过率。
新增离线通过：AttendanceRoster、BreadcrumbNavigator、BudgetThreshold、CourseModuleAccordion、DeliveryRouteTimeline、EnergyLoadScheduler、FleetDispatchConsole、MeetingPollScheduler、QuizNavigator、SeatBookingMap、StarRatingInput、TransferList、WorkoutPlanner。历史通过回退：无。
仍未解决 42 项；没有将未通过改为人工通过。

## 根因与落实位置

- **修复入口遗漏**：模板解析通过便提前返回，源匹配的 getter／事件修饰符修复没有执行。现覆盖可解析模板，并完成有界后续属性修复；采用 HTML namespace/void-element 解析，避免 input 与 SVG 定位混乱。
- **规则与模型衔接断层**：模型输出未经规则复核就进入候选门，恢复默认值等工作被推迟到下一轮甚至预算耗尽。现同一提案内最多 3 次语法→最新静态检查→既有规则；原始输出、逐步哈希另存，最终仍复测和回退。
- **computed 依赖组断裂**：只搬 getter 不改其消费者，或把 reduce 的新建局部累加器误当外部状态修改。现只搬完整源函数体翻译一致的 getter，连同已知源消费者的零参数误调用原子改为值读取；未知调用、参数、依赖缺失仍拒绝。
- **完整调用体修复过窄**：本地记录复制／时间戳被全局闭包白名单误拒。现允许已知 Date/Object/Array 标准引用，并保留源码／目标同名遮蔽检查；不放行未知键和 this owner。
- **原生 DOM 表示差异无法直接由模型模板修复**：受限非空普通 data 的 input :value 使用原生 defaultValue 反射；字符串条件 class 使用原生 className 反射。实际修复 value/class 属性，不删除 DOM 差异。对 v-model、nullable props、未知键、SVG 等仍保守拒绝；模板投影只合并同表达式的实现别名，CSS 属性观察仍严格。

## 尚未闭合的部分

remaining.json 逐项保留：真实缺失节点／控件、初始化时序、未知动态键流、内联组件与复杂 getter、语法与事件契约、候选门中新显现诊断。不能把这一轮修订叫作“全部问题彻底修复”。
TaskManager 的模型传输结果未知仍单独保留；未再次调用，已知 Tokens 不代表其实际费用为零。

## 证据

- 两轮逐项及全部修复轮次：../analysis_v3_vs_first70_20261119/。
- 本次全部 70 项离线规则与真实浏览器候选门：../composed_v6_final_replay_20261119/。
- 规则／浏览器／编排回归：migration_system/docs/verification/2026-11-19_general_repairs_v1/test-results-composed_v6_verified.json。
- 部分中断的预检目录保留 INTERRUPTED 标记，不混入本轮完整结果。
