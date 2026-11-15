# Conditional class binding closure v1 — 2026-11-13 发现，2026-11-14 验证

开发回归中的通用闭环改进，不是独立测试或完整组件通过证明。

- 用户报告 TaskManager 默认暗黑；冻结产物四种布尔组合均产生 `task-manager dark-theme`。
- 旧规则仅抓完整属性中的外层对象花括号，遗漏静态前缀后的裸多键 map；源比较仅支持单键且依赖其他错误触发。San 编译只接受了字面量前缀，因此编译通过不是语义通过。
- 生成和修复共用完整 class 约束；校验无条件分析父/内联模板；修复前后均用同一条源码匹配规则，且不依赖 residual_v2；两个调度策略均独立阻止条件 class 退化或隐藏诊断。
- 确定性改写只接受完整源码对象、字面量键、相同 DOM/循环/条件作用域、已知字段、静态 class 和全部条件。无法证明的情况不猜测修改。
- 207/207 项定向回归通过（7 个测试模块）；San 原生 parser/Data/evaluator 覆盖 false/false、false/true、true/false、true/true、回到 false/false。不是浏览器重绘验证。此前失败日志保留，未删除或放宽旧测试。
- 原冻结 `.san`、测试页面及人工 manifest 均未改动。离线候选为 `TaskManager_class_binding_offline.san`，当前手工页面仍加载旧冻结产物。
- 完整 ValidateStage 仍不通过：保留源 watcher 动态键与异常策略边界；未修改原 24/30 结果、未调用模型。
- Notebook 原 76 单元完整保留。历史代码单元重新执行：17/27 通过，10 个失败详见 audit；旧单元的 live-code 指纹不会为这次授权修改而放宽。新增单元按冻结副本和明确变更白名单校验。
- 服务器端生成 Prompt 需重启本地服务才生效；新启动的批处理进程直接加载新校验与修复代码。尚未重启、未复跑模型、未人工宣告通过。
