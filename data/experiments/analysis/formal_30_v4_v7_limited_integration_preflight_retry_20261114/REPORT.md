# v7 受限接入预检与人工确认 — 2026-11-14

## 本次结论

- 用户明确反馈“通过，开始下一步”：记录本次 1/1 对正常交互人工通过。未逐项提供检查结果、截图或浏览器日志；可选保存故障未确认，不推断为执行过或通过。
- 确认对象是 manifest 固定的 TaskManager v7 + class 修复候选，不是旧默认暗黑版本。旧准备目录的 awaiting_user 保持原样，结果另存 manual_acceptance.json。
- 用户选择“先按此受限范围推进”：固定浏览器、无源祖先错误捕获、全局同步只报告错误及不访问响应式状态、固定 Vue 2.7.16 / San 3.15.6。其他配置拒绝，不宣称验证任意函数纯度。
- 新增通用、无组件名特例的应用范围声明检查器。scope accepted 只是前置条件，source equivalence / runtime callback purity / production eligible 均为 false；尚未接入生产放行路径。
- 当前完整 ValidateStage 仍有三项：source_parent_watch_dynamic_key_unproven, source_parent_watch_exception_policy_unproven, source_parent_watch_not_landed。即使伪造 validation_passed 并清空诊断，独立候选门仍拒绝。
- 69 项定向测试，全部通过：True；不是完整测试集或新模型运行。0 模型调用，未启动浏览器或服务器。原批 24/30、6 失败、1,821,544 tokens 不变。

## 不能混淆的差距

1. v7 完整模板正常交互得到人工确认；现有源码 matcher 对 v7 私有队列/生命周期包装仍不给出 normal-flow proof。不能只看到 __watcherScope_v7 字符串就消除 not_landed。
2. source updateSettings(key,value) 仍有任意动态键／属性形状、继承和别名语义的证明缺口。UI 已知选项不等于公开方法只允许这些键，不能为修复而缩小业务接口。
3. 验收页在 inited 后、首次排队前配置的 reporting-only bridge 仍是实验应用代码；受限范围已得到授权，但生产 emitter、运行时调用时机和依赖边界尚未证明与默认 Vue 匹配。

## 下一阶段顺序

先做异步队列与源码契约的精确识别，再做动态键／形状和受限错误桥接。每项以冻结失败 oracle 和正负测试验收，再接入规则、验证器、调度器与模型前后处理。保留三项阻断直到证据足够，不继续堆 Prompt 或用付费复跑代替证明。

首次预检 69 项中 2 条旧测试失败：旧 fixture 未报告新增 class 诊断，并假定 class 错误也不能被独立修复。原日志与 fixture 保留在 failed_preflight 引用中；更新测试仍要求零模型、watcher 待审查、唯一 class 修复及 script/style 原字节相同，不放宽生产规则。

旧页面、组件、准备 manifest、生产 validator/repair/scheduler/Prompt 均未修改；Notebook 只追加，不覆盖历史 78 单元。
