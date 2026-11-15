# v4 语义复发保护与 residual_v2 离线验证

验证完成：269/269 测试通过（66.053 秒），含新增 19 项；新协议 270 份 payload、278 项 live 哈希验证通过，dry-run 通过。没有启动模型回归，旧快照 290 项复核通过。

日期：2026-11-03。原始输入 `formal_30_v4_semantic_closure_v1_results_20261103_145253`，290 文件回放前后校验。旧结果仍 2 完成、0 自动通过，本分析没有调用模型。

## 已实现

1. `repair_scheduler.py` 增加已审查诊断的具体发现差集：隐藏响应式依赖、computed 调实例方法、生命周期行为契约、dataTypes、prop defaults。比较 code/location/message 和次数，不以总错误减少抵消新增问题。新候选拒收后恢复上一份候选并保留失败，不把较早失败候选转成成功。
2. 新增 `residual_semantics.cjs/.py`，通过 metadata `semantic_rule_set=residual_v2` 显式启用。computed 调用的自包含方法被复制为脚本 helper，原实例方法保留；原调用实参保持。拒绝外部闭包、this、未知副作用或参数对象写入，允许限定数学及原有局部 Date 操作。Date 仍依赖时钟，不宣称为无时钟依赖的数学纯函数；固定时钟测试覆盖过期／未过期、已完成／无日期分支。
3. dataTypes 根据源 inline Vue props 和实际注册映射补到相应子组件，采用真实字段与可确定类型，数组式源 props 用 any。无源父 props 不虚构 schema；已有 schema、未知类型／联合类型／不明确注册保持原样。未更改验证器，不添加空 dataTypes 来消除错误。
4. 新修复接入 repair 确定性预处理和 LLM 返回后处理，规则集由批配置传入并记录于报告。原 bounded_v1 不默认执行新增 AST 转换；候选语义保护扩展对 bounded 调度生效。冻结基线已变，旧协议继续用于历史证据，不修改旧包解除 live mismatch。
5. repair Prompt 修复 missing_data_types 阻断聚焦路由的问题，单一隐藏依赖／生命周期残留也可聚焦；补真实源 props、生命周期及递归方法调用链，明确不要重引已消除诊断。

## 原始证据回放

| 检查 | 结果 |
| --- | --- |
| TaskManager 冻结第 2→3 次 LLM | 第三次新增隐藏 tasks 依赖被拒；保留第二次代码及其失败评估，坏候选单独留证 |
| TaskManager 冻结最终产物应用 residual_v2 | dataTypes 与 computed 实例方法问题消除，仍剩 hidden_template_reactive_dependency，DOM 0.9889，仍失败 |
| MonitoringDashboard 冻结最终产物应用 residual_v2 | getX/getY 实例上下文问题消除，仍剩 lifecycle_behavior_not_landed，DOM 0.9605，仍失败 |
| 聚焦提示 | TaskManager 56,256 字符、MonitoringDashboard 66,701 字符；输入及提示哈希见 replay.json |

TaskManager 实际模型上一轮 Prompt 为约 44 万字符，这里仅比较已准备文本长度，不声称已经节约实际模型 token 或提升通过率。本次没有模型请求，没有本批 summary，也无新的人工交互通过结论。

## 边界和剩余工作

保护门不是通用语义等价证明。它依赖同版本验证器的具体消息／位置稳定性，不同表述可能保守拒收；未知诊断和警告不自动纳入。候选门只在修复后重新评估时起作用，不能保证发现所有动态缺陷。

TaskManager 的隐藏 tasks 依赖仍需修复模板参数和方法读取；MonitoringDashboard 的设置加载从 attached 调用链移至 inited 涉及 watcher／localStorage／通知权限时机，未用简单确定性搬运猜测修复。新 Prompt 提供完整源证据，实际效果须模型运行后验证。旧三个失败样本及完整 30 项回归未结案，v5 等待。

新增两组测试：语义复发保护 7 项、residual-v2 与边界 12 项。完整日志和预运行哈希置于 `data/experiments/protocols/formal_30_v4_semantic_closure_v2_frozen_20261103/`。预算仍为每样本最多 3 次 LLM repair，每次前最多 4 步确定性处理。只有用户执行新 launcher 的 --execute 才启动模型回归；旧批次不强制重抽。

复现离线检查：`python -m migration_pipeline.replay_formal_30_v4_residual_v2`。测试：`python -m unittest discover -s tests -p test_*.py`。新 Notebook：`notebooks/02-migration-experiments/2026-11-03_formal_30_v4_semantic_closure_v2.ipynb`。未改人工测试页、未手改原始生成 San、未 commit／push。
