# 有边界的语义闭环修复 v1

日期：2026-11-02。复用 TaskManager、MonitoringDashboard 的开发失败证据；不是独立测试集，不调用模型，不改旧原始产物和评分。

## 修复位置

- repair Prompt：补源事件方法完整参数／函数体、禁止 `this.event`／data-* 绕行、说明参数化 computed 的正确落地；self-click 残留也可进入聚焦提示。
- repair 确定性计划及 LLM 输出后处理：新增 Babel AST 有边界转换。纯算术箭头 formatter 可由 computed 移到普通方法；参数丢失仅在 SSM 中完整源方法是简单同步处理器、对应绑定明确时一起还原参数和方法体。它不按组件名分支。
- 候选事件追溯：原 Vue 有 `.self` 契约、父组件包装体精确为 target/currentTarget 条件和原无参方法调用时可追溯。带额外副作用、错目标、错参数不放行；既有事件丢失、视觉退化、关键编译错误仍拒收。
- 无法解析、复杂控制流、未知全局、隐藏依赖、嵌套状态写入等情况保持原样，交给 LLM；不保证所有旧缺陷都能自动修好。

## 对前次诊断的更正

真实安装版 San 的 `parseTemplate` 和 `getEventListener` 测试表明：裸绑定 `on-click="guard"` 会由解析器补默认 `$event`；`guard()` 才不传参，`guard($event)` 显式传参。前次将“不显式写 $event”视作可能缺事件的诊断不准确，本次已更正。不能以此将历史失败改计为成功：TaskManager 当时的事件追溯确有覆盖缺口，但静态 computed／其它事件问题仍存在。

## 冻结失败回放

输入：`formal_30_v4_repair_scheduling_v1_results_20261102_224614`，283 文件哈希验证；输出只写本分析目录，原快照回放前后不变。详细输入／输出哈希、每步候选门和错误见 `replay.json`。

| 冻结输入 | 新规则离线静态结果 | 初始 DOM 相似度 |
| --- | --- | ---: |
| TaskManager 第一轮／原最终候选 | 仍四类：事件语法、一个 self guard、computed 实例方法、隐藏 tasks 依赖 | 0.9889 |
| TaskManager 第二轮／原拒收候选 | 仍两类：事件语法、computed 实例方法 | 0.9889 |
| MonitoringDashboard 原最终候选 | 静态通过：源事件绑定与方法体恢复、纯算术 computed 转方法 | 0.9605 |

两份 TaskManager 输入仍失败，不能把较少错误的候选手工改为成功产物。MonitoringDashboard 这里只是冻结产物规则回放通过，不是新生成模型批次通过，也不是人工交互通过。初始 DOM 检查没有覆盖所有动态功能。

## 验证与新运行

实际冻结前验证：250/250 测试通过（48.650 秒），新协议 262 份 payload／270 项 live 哈希校验通过，dry-run 通过，无模型调用。旧快照 283 项复核通过。

新增 12 项正反例测试：合法 self 包装、额外副作用／错目标／错事件／错误组件作用域、源契约缺失、事件参数丢失、纯算术 formatter、隐藏依赖与歧义拒修、源事件方法还原及复杂源拒修、解析失败、Prompt 源方法证据、真实 San 事件行为。formatter 测试实际调用 San 实例方法比较 7／30／90 三个输入的结果。

完整测试和 dry-run 日志封存在 `data/experiments/protocols/formal_30_v4_semantic_closure_v1_frozen_20261102/`。运行预算仍为每样本最多 3 次 LLM repair，每次之前最多 4 个确定性步骤。新批次、独立输出目录；generation／服务器 Prompt 未改，repair Prompt／规则／事件追溯改变。不作单因素或独立泛化结论。

下一步由操作者运行新批次，结束先冻结结果再检查。TaskManager 仍需实际验证 LLM 能否修好残留，不能仅靠本地回放宣布闭环完成。原 30 项失败事项和完整回归继续保留，v5 等待。本次未提交或推送 Git。
