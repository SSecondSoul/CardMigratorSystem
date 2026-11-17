# 任意公开键契约与控件状态诊断（2026-11-17）

## 结论：本轮没有把 ProductFilterPanel 改判为通过

原任务 `ea3808cfe9ff4ae7b301e5c8d593e3aa`，ProductFilterPanel.vue，`failed / repair_budget_exhausted`，真实模型 3 次、已知 Tokens 87999。源哈希 `aed0d49a2bab60b3103e50beb0236320d35f7fb9d8bd2341db36a65be65e817a`。原请求没有交互，历史 `not_run` 保留。

第一轮共享规则补齐 props 默认值和循环；第二轮模型恢复混合子节点顺序，编译运行通过、截图相同；第三轮模型返回相同代码，候选无改善被拒绝。最终有 `source_dynamic_assignment_unproven` 和 `rendered_dom_mismatch`，不是此前 HTML 空元素解析失败。

## 保留用户已经选择的契约

源 `setValue(key,value) { this[key]=value }` 与目标 `this.data.set(key,value)` 不能按任意键直接等价：例如 `extra.key` 在 JavaScript 实例上是字面属性，在 San Data 中是路径；Symbol、方法名和运行时实例命名空间也不能用六个状态键的 UI 测试来证明。真实 San 反例测试确认点号键差异。

用户此前明确保留“任意公开键”要求，不采用仅证明源码可达六个键的降级协议。因此本轮**没有实现完整动态实例兼容层，也没有缩小契约**；任意公开键迁移能力仍未完成。这不是已修好该组件功能的声明。

已实现通用的能力预检查：

- `method_interface_semantics.cjs` 导出原验证器使用的同一个 exact setter 识别器，规则和预检查不各写一套判定。
- 新 `browser/source-contracts.mjs` 只检查导出父 Options 的方法，支持直接方法及可解析常量函数别名；不按组件名／状态键白名单匹配，不执行上传脚本。
- 新系统在源语法预检查之后、模型 preflight／SSM／生成之前检查此能力；已知不支持时返回 `source_dynamic_key_contract_unsupported`，新任务模型调用／Tokens 均为 0。源合法与源语法错误分开描述，包含本地源码位置／片段，报告不上传片段到 LangSmith。
- 不识别某种方法形状不等于证明其支持；原静态语义验证、候选门控和最终质量检查继续保留。这是精确已知边界的提前阻断，不是完整 Vue 能力分析。

这是避免已知不支持契约反复消耗模型的流程修复，**不是该语义能力的完整实现**。不建议为同一源码反复新建任务支付费用；今后若要完成该迁移，仍须实现并证明完整契约，或由用户另行明确批准新的受限契约，保留旧失败。

## 控件实际值与原始 DOM 分开检查

源和目标实际的 query／category／range／checkbox／sort 属性值在原始快照中一致。原始 DOM 仍有四处 value 属性存在性和四处空 class 差异；属性观察者／未知依赖存在时不能擅自归一化。

本轮修正的是检查完整性和可诊断性：

- 初始态也比较控件 live `value`／`checked`，而不仅在交互之后检查；多选 select 额外采集全部选中值。
- 初始属性值不同产生 `rendered_control_state_mismatch` 并使结构检查失败，即使截图或 HTML 标签相同也不放行。
- `initial_control_state` 及各动作的具体状态差异写入报告和实际修复消息；`rendered_dom_mismatch` 同时说明 live 值是否一致，工作台显示原始诊断和初始值检查状态。
- **不删除原始 value 属性、空 class 差异，不降低阈值，不修改 DOM 归一化批准条件。** 空 class 分析中的另一个 `baseParse` 入口改为 HTML-aware `parse`；含动态成员／DOM 观察／未知调用的组件仍拒绝批准，ProductFilterPanel 未获批准。

## 冻结与限定场景重放

冻结目录：`data/experiments/evaluator_calibration/2026-11-17_modular_product_filter_failure_frozen_v1`，45 个历史任务文件、源输入和 freeze.json，共 47 个 payload，SHA-256 单独封存。

最终诊断：同级 `2026-11-17_modular_product_filter_contract_replay_v4`。使用原接受 revision 2，不手改 San、不重新生成，执行 11 步搜索／清空／分类／价格／有货过滤／价格排序／选择／空结果恢复。双端共 24 条明确商品列表预期（含初始态）全部符合，初始及各动作的控件实际值一致；但严格 DOM 未通过，各动作的整体交互判定仍 fail，静态仍 fail，不宣称迁移通过。限定场景不覆盖任意公开方法输入。

v1 保留受限环境浏览器无法启动的未完成现场；v2 为诊断脚本因预期错误提前退出的现场；v3 完整保留错误预期的失败观察。预期最初误用输入数组顺序并假设 clear 重置 sort，v4 按源声明的名称排序和保留已选排序修正后重新验证。没有为满足夹具而改源代码或目标代码。

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/replay_public_key_failure.py `
  --frozen-evidence data/experiments/evaluator_calibration/2026-11-17_modular_product_filter_failure_frozen_v1 `
  --output-dir data/experiments/evaluator_calibration/另选全新诊断目录
```

只写独立证据目录，校验冻结清单、原任务及源输入不变，记录当前实现；不写数据库、不调用模型、不上传 LangSmith。新增专项 11 项通过（33.120 秒）；完整模块回归 102 项通过（671.729 秒，已含专项），共享方法接口回归 16 项通过（463.020 秒）；前端构建及 Node 22 项通过。工程用例不能计成论文迁移成功样本；中间失败及复测边界见 [开发记录](DEVELOPMENT_20261116.md)。

## 部署

前端 dist 已构建；重启 API 和 migration-worker、刷新页面可启用新检查，无数据库升级。旧任务不改绑、不恢复后覆盖历史。**当前 ProductFilterPanel 的任意公开键支持仍阻断，部署并不意味着可以复跑到通过。** SSM、生成／修复 Prompt 模板、用户配置和手工测试页均未修改；本轮没有 commit／push。
