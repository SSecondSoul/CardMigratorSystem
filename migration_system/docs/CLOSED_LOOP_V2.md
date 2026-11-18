# 最新五次任务：通用比较、computed 与候选门修复

2026-11-18。沿用 `san-supported-migration-v4` 的验收范围，本轮是范围内错误修复，不扩大公开 API 承诺。

## 改了什么

1. **静态语义比较**：完整调用者 AST 比较前，仅统一普通对象表达式中非计算属性的标识符／字符串键，以及等效简写。例如 `{message}` 与 `{"message": message}` 不再误报。仍比较全部调用者语句、参数、求值及属性顺序；计算键、展开顺序、访问器、重复键顺序和不同值不忽略。`{__proto__}` 与原型设置器 `{"__proto__": value}` 不视为等价。不按组件名、方法名建立白名单。
2. **校验＋有界规则修复**：AST 检查 San 组件中错误的 `this.computed.<name>` 读取，增加 `invalid_san_computed_namespace_access`。只有能对应源组件声明、目标确有 computed 定义、属于根组件直接／词法 this 上下文的值读取，才提议改为 `this.data.get(name)`。调用、写入、未知键、运行时覆盖、无源声明、子组件无法建立来源关系的情况不猜测修复。候选仍走真实静态、浏览器及质量复检；修复 Prompt 和相关 SSM 投影接收同一错误码。
3. **候选接受门**：新增受限、版本化控件身份／父拓扑证据。仅当缺失控件恢复、实时状态按序一致、DOM 指标改善，且剩余路径错位可绑定到旧候选中已存在的同一控件及相同父拓扑时，允许把“控件状态不符→已有位置缺陷”识别为诊断细化。缺证据、证据截断、控件身份／父拓扑改变、其他新错误、已通过维度退步仍拒绝。**接受进步不等于通过**，多余 span 等结构缺陷继续失败。这不是全程序没有新缺陷的证明。

生成仍为原 SSM＋模型路径；不启用源码到 San 的确定性生成、业务代理或新运行时。规则只在修复阶段提出候选，不直接覆盖既有产物。没有新增整份评估追加，也没有增加模型预算、降低阈值或修改 Vue。

## 五次冻结任务的离线结果

| 原任务／组件 | 验证到的改进 | 保留的未通过项 |
| --- | --- | --- |
| `48d232…`、`bd8061…` CapacityPlanningBoard | `log` 的对象键／简写误报消除，普通内部键调用证据成立 | trackby 写法、解除分配事件、实际渲染／控件差异 |
| `d090a4…` DependencyReleasePlanner | `release` 对象键表示误报消除，静态语义通过 | 原始 DOM 属性差异；不能直接宣称整体通过 |
| `5d3338…` HabitWeekTracker | 原来静态漏检的两个 computed 命名空间读取现在被检出；实际规则候选的静态、运行、视觉通过，22 个控件实时状态一致 | DOM 仍有 23 个 class 表示差异，当前策略未获准归一化，结构维度仍失败 |
| `42acb6…` PollResults | 历史第 2／3 候选恢复到 5 个控件的进步可接受，不再仅因诊断细化回退 | footer 多余 span 与其他 DOM 差异继续失败；原第 1 接受产物不改写 |

以上是冻结产物离线重放，不是新模型实验，不能计入独立测试通过率。原 5 次失败记录及共 414835 Tokens 成本保留。代表性交互原先未配置，仍为 `not_run`；本轮不把它变成通过。

Poll 第 2／3 候选是各自相对原第 1 接受产物的独立判断，不是顺序重复接纳相同代码；已经接纳第 2 候选后，同一候选再提交没有严格改善，仍被拒绝。

## 证据与复验

最终关联回归 **165/165 通过，零跳过，337.730 秒**（含 13 项新专项用例）；独立副本的实际 LangGraph、临时数据库、API／前端下载、SSM 和浏览器检查通过。其模型部分使用明确的已记录响应替身，新增云模型调用为 0。首轮 164/165 的失败是旧复用测试要求 Prompt 完全相同，已改为只允许新增的那一条 computed 命名空间读取提示，其他文本仍逐字匹配；首轮失败摘要保留，不掩盖测试调整。

证据目录：[verification/2026-11-18_closed_loop_v2](verification/2026-11-18_closed_loop_v2/README.md)。`FREEZE.json` 冻结最新五次终态任务的 235 个登记文件、源码与变更前实现，共 479 个 payload。原始登记哈希已核对；不修改实际数据库、队列、原 `.san` 或旧封存。

从 `migration_system` 内复验，输出必须使用不存在的新路径：

```powershell
& .venv/Scripts/python.exe scripts/replay_closed_loop_v2.py --output-dir var/closed-loop-v2-replay-new
& .venv/Scripts/python.exe scripts/verify_semantic_comparison.py --output var/closed-loop-v2-tests-new.json
& .venv/Scripts/python.exe scripts/verify_standalone.py --output var/closed-loop-v2-standalone-new.json
& .venv/Scripts/python.exe scripts/seal_closed_loop_v2.py
```

前两项为真实解析器／规则／浏览器的本地检查，不调用付费模型。独立副本测试显式使用已记录响应测试客户端，不声称真实模型生成成功；真实图、持久化和浏览器照常执行。

部署需停止旧 API 和 migration-worker 后重新启动，再创建新任务，不能改绑或续跑旧指纹任务。下一步先检查剩余结构／事件错误与尚未获准的表示归一化条件，不宜用反复付费试跑替代诊断。

`model_api_key_missing` 表示执行 readiness 检查的 API 进程没有读取到相应环境变量；它本身不能推翻独立 Worker 已持有效凭据发出请求的收据。五次任务实际 15 次模型请求均有成功 HTTP／用量收据，因此本轮失败不能归因为缺少模型密钥。此处仅澄清进程范围，不读取或复制用户密钥。
