# 覆盖状态、结构恢复与私有图表 helper 闭环

日期：2026-11-03。来源是已冻结的 v3 失败快照（315 文件），本次没有模型调用，也没有改写旧结果。独立离线包：`data/experiments/analysis/formal_30_v4_coverage_helper_closure_v1_20261103`，22 文件验证通过。

## 本次修改位置

本轮没有修改 generation、服务器 Prompt 或 repair Prompt 文本。修改的是 repair 确定性预处理／模型返回后处理、候选门及底层源语义分析模块。`validate.py` 文件本轮未改，但其调用的分析模块改变，检测行为也随之扩展；不能把新验证结果当作旧版本原有评分。

1. `inline_identifier_recovery.{py,cjs}`：仅恢复源 SSM 明确注册的 hyphen-tag 对应非法变量声明与父 components 引用。使用 Babel recovery 获取 token／范围，再要求结果通过严格 JS 解析与 binding 验证；不把 recovery AST 当合法代码。标签字符串、模板文字、注释不替换；额外 token 用途可能是减法，拒绝猜改。注册歧义、其它语法错误或来源缺失不改。恢复后每个构造器只允许对应注册引用，命名冲突另选标识符。
2. `semantic_coverage.{py,cjs}` 与 `repair_scheduler.py`：只对明确的“源注册语法恢复后才可分析”转换作范围证明。按相同注册 tag 对齐子组件，要求方法 AST、同位置／属性的全部渲染调用相同，再隔离重检旧范围。已证明的诊断记为 newly_visible_preexisting_semantic_findings，仍保留在 validation_errors 中，不自动判通过。父 inited 完全相同且源 watcher 缺失写入可在虚拟恢复代码中独立证明时，也可归为既有缺陷。无法证明则仍拒收；不是对编译失败或隐藏依赖的全局豁免。
3. `stateful_helper_semantics.{py,cjs}`：仅处理父 components 唯一注册、未额外暴露的内联子组件私有计算方法。把常量路径的 this.data.get 读取转换为显式参数，同步修改所有模板调用和词法 this 调用；参数数目必须完整匹配，拒绝动态索引、裸方法引用、未知 this、外部自由变量、写入和参数 mutation。转换后的计算仍须通过既有自包含计算检查，随后复用 residual 提取 computed 使用的独立 helper。不是任意有状态业务方法重写，亦不证明所有 computed getter 深层行为无副作用。
4. `source_phase_semantics.cjs`：补充“方法主体已经等价于源、只是循环项绑定缺参”的明确形状；补充零参数 watcher 内部以同名 const 读取当前被 watch 根字段的等价前缀，仅补源明确缺失的末尾存储写入。对唯一匹配、源与目标默认值均为 boolean 的非 .self 赋值事件生成 setter；不混算已转换的 backdrop guard，不复用条件关闭方法作为无条件 setter。
5. 模板修复与独立脚本分析分开：模板解析失败不能遮住可独立证明的 watcher／生命周期诊断；模板编辑先在局部事务中完成，失败不泄漏半份编辑。

以上均为结构／源码证据驱动规则，无 MonitoringDashboard 名称硬编码。分析和测试可引用本样本，生产规则不按样本名分支。任一规则不满足边界时保持原状；原始文件不被手工修补。

## 候选门验证

旧 v3 拒收的四项图表隐藏依赖，在当前门下可证明为既有问题首次可见；新分析器另外识别到原先零参数 watcher 的缺失持久化，两侧 inited 相同，因此本次当前检查器共解释五项既有诊断。旧模型 history 的四项原判据不修改，不把第五项冒充旧版当时就有的诊断。

反例只把 RequestChart.getX 公式常量 2 改为 3，其余诊断文本可以相同；新门仍报告新增语义问题并拒收。未知来源、改变渲染调用、额外诊断、改变父 inited 也不能借已有诊断豁免。捕获旧候选做 mock 调度时可继续而不回退，但未修复诊断仍计失败；mock 不是新模型请求。

## 离线重放结果

| 输入 | 确定性步骤 | 静态结果 | 初始 DOM | 结论 |
| --- | ---: | --- | --- | --- |
| v3 实际保留的失败原件 | 1 | 19 条诊断仍在（9 类） | 通过，0.9781 | 未闭合，不计通过 |
| v3 被拒收的 LLM 候选 | 1 | 错误清零 | 通过，0.9825 | 仅离线修复通过，未人工验证 |

两个步骤均通过候选门且达到固定点，没有调用模型。第一项还剩模板 Math／成员调用、事件／循环语法、重复 class、self guard、嵌套状态 mutation、事件参数及生命周期映射问题，不能宣称语法恢复已经处理了整个原件。第二项执行显式依赖、computed helper、源 props schema、KPI 参数绑定、watcher 存储及源 boolean setter 规则，保留了原有 backdrop guard。

离线输出摘要：

- retained_failure_offline.san：`f38ffbceb4223a7b9a281212a3e211436f13c9eb122dfc0b11c20949a8b666f3`
- rejected_candidate_offline.san：`db2df5182053d6a543eb1147791d8bde71fe80a868da05f3f41b857b2272468b`

源组件含随机数据；以 replay.json 保存的本次观察为准，不选择更高相似度替换。静态／初始 DOM 通过不是全部交互或生命周期等价证明；窗口尺寸、计时器、设置弹窗等仍需后续针对性检查。

## 测试与证据

完整 **319/319 测试通过，142.262 秒**。其中本轮新增 19 项覆盖真实失败／候选、真假回归、未知证据拒收、声明／注册恢复边界、私有引用边界、getter／参数 mutation 拒绝、幂等、真实 Stage 后处理及 mock 调度。实际 San computed 测试覆盖 0、1、7、30、90 个点与 600／1200 两种宽度，逐项比较折线坐标和圆点计算。未执行浏览器交互测试。

开发期间一次全量验证开始后又收紧了私有注册条件，文件稳定性检查阻止该次封存；随后用最终代码重新完整验证，才生成本 22 文件证据包。未覆盖既有证据，不将未封存调试当作新的模型实验。

原始 v3 快照 315 文件、TaskManager 人工通过候选 13 文件复核通过。代码变化使旧 v3 live 基线不再匹配，这是预期；不要重写旧 SHA 清单或沿用旧命令运行新代码。本次没有更改两个测试页面，没有 commit／push。

复现只读重放：

```powershell
python -m migration_pipeline.replay_formal_30_v4_coverage_helper_closure
python data/experiments/analysis/formal_30_v4_coverage_helper_closure_v1_20261103/verify_snapshot.py
```

## 后续状态

这一步补上了已观察到的候选门可见性误判和有边界规则闭环，不是保证所有初次生成产物都合法，也不是新鲜模型迁移通过。原 v3 仍为 1 完成、0 通过、1 失败，原用量 240,133 tokens 不变。TaskManager 已人工通过候选保留，完整 30 项回归仍待完成。

后续需另建、冻结新运行协议／checkpoint，再只验证 MonitoringDashboard；新运行从源 Vue 生成，不能用本离线修复文件充当初始代码或择优替换失败结果。操作者启动模型前不得继续改冻结实现。新结果先冻结，再检查并安排人工交互；不直接 --force 重抽原批。
