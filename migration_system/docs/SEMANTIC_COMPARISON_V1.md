# 通用模板／DOM 比较与动态赋值契约修复

日期：2026-11-18。当前范围：`san-supported-migration-v4`。

## 授权与验收边界

用户本轮明确允许“源码中可静态确认的内部调用＋普通 data 状态键”范围内判定通过；报告必须披露“不证明任意外部键调用等价”。这是新的有界验收口径，不是证明旧任意公开键契约已经实现。旧任务、原失败与历史统计不回填或改判。

依旧是 Vue → 完整 SSM → 模型生成 San → 多维评估 → 有界规则／模型修复。没有恢复源 AST 生成分支，没有引入公开实例代理、运行时补丁或按组件名的专用路径。

## 1. 对称模板 class 投影

此前目标 San 提取了 `'habit-row ' + (...)` 中的固定 token，源 SSM 投影只有 `binding:class`，产生不对称误报。现在两端使用同一抽象规则：字面 class、条件分支交集、数组／布尔字面对象 class；拼接必须确认 HTML class token 边界。`'row'+suffix` 不当作固定 `row`，不会只因源码出现字符串就认定该类存在。

源解析返回表达式的已证明 token，SSM 树结合该证据投影；不修改保存的 SSM。目标使用相同 class token 规则。节点、文本、事件、条件、真实缺失类名仍参与比较；TED 算法、编辑代价及阈值未调低。

## 2. 原始 DOM、表示差异与真实结构

- 原始树、原始 TED、实际属性和差异均保留，比较不改渲染结果。
- `class_serialization_v2` 仅在既有保守 JS／模板／CSS 审查获准时归一化精确空 class、HTML 空白、token 顺序和重复。CSS 属性观察、DOM 反射或未知依赖仍严格比较。
- 即使策略不获准，报告也独立列出 `dom_representation_differences`，说明差异类型及是否归一化。分类不是豁免。
- 控件值相同、路径不同，诊断为 `rendered_control_position_mismatch`，不再声称“值不同”；结构门仍不通过。值、类型或数量真不同保留 `rendered_control_state_mismatch`。
- `<footer>文本<button>…` 改成 `<footer><span>文本</span><button>…` 是真实包装节点增加，仍失败，不能当作空白或表示差异删除。

## 3. 动态赋值的有界证明

规则按 AST 行为识别，不按 `setValue` 方法名识别。`assignField(k,v){this[k]=v}` 等同类写法采用相同规则。

成功证明要求：

1. 源方法是准确的两参数 `this[key] = value` 单一语句，目标是准确的两参数、单一 `this.data.set(key,value)` 语句，保持隐式 `undefined` 返回；无附加 guard、返回值或通知。
2. 源 data／目标 initData 的普通状态工厂可解析；键是已声明、无 props／computed／方法／San 内部命名冲突的简单字符串状态根。字面常量或词法作用域内未修改的 `const` 字符串可证明。
3. 每个内部调用可定位。拒绝 setter／实例逃逸、动态实例访问、未知键、额外目标调用、setter／store 重定义和 store 逃逸。
4. 源／目标调用者和键的次数对应；进一步比较**完整调用者函数**的参数、分支、值表达式、返回与效果顺序。支持保留 helper 或源码匹配的直接 `data.set` 内联形式；不能只匹配同一字段名就放行。
5. `created → inited`、`mounted → attached` 等仅按已有生命周期对应核对，不凭名字给业务方法改阶段。未证明的其他方法、观察者调度、事件、结构与交互仍由原校验器／浏览器独立检查。

输出 `source_internal_declared_state_assignment_v1` 及源码／目标位置、键、调用者映射、拒绝原因。`arbitrary_key_semantics_proven` 始终为 false；这不是运行时键白名单，生成代码没有被添加固定键 guard。

Symbol、点号键、未知参数键、props／computed、命名冲突、未知别名／逃逸及无法证明的函数形状仍不通过。没有可证明内部调用的公开 helper 不因“存在一个空壳方法”放行。分析失败保留 `unproven`，不按成功处理。

## 冻结失败产物的离线重评

输入为两次原失败的 revision 1；源码和目标均未改写，无模型调用、数据库或队列修改。

| 产物 | 模板 AST | 动态 setter | 仍未通过的原因 |
| --- | --- | --- | --- |
| HabitWeekTracker | 93.75% → 100% | 源内部调用证明通过 | 原始 DOM 的 23 处 class 表示差异，保守审查未准许归一化，结构门仍失败 |
| PollResults | 85.71%，不改 | 源内部调用证明通过 | 真正新增 span 包装，另有 3 处空 class 表示差异；控件路径变化不再误称值不同 |

两份离线重评都**不等于新模型迁移通过**。交互仍为 `not_run`，不宣称完整功能等价。源／目标原件、历史收据和旧失败均保留在 [本轮证据](verification/2026-11-18_semantic_comparison_v1/README.md)。

## 部署与复核

验证：最终 152 项相关回归通过、0 跳过；前端类型检查／构建与系统目录外独立运行验证通过。验证不调用付费模型；不表示两个冻结复杂产物整体已通过，也不替代新任务的交互／人工验收。

部署无需新增配置／密钥：停止旧 API 和迁移 Worker，按 [启动指南](../SYSTEM_GUIDE.md) 重启、Ctrl+F5 并创建新任务。页面应显示 v4，不能跨实现恢复旧失败任务。

离线复核（在 migration_system 内运行，不调用模型）：

```powershell
& .venv/Scripts/python.exe scripts/replay_semantic_comparison.py --evidence-dir docs/verification/2026-11-18_semantic_comparison_v1/frozen --output-dir var/semantic-comparison-v1/new-replay
```

输出目录必须不存在。修复证据投影仍保留去重、样式聚合和相关 SSM，不重新追加整份评估；模型输出质量仍需要新任务和代表性交互确认。
