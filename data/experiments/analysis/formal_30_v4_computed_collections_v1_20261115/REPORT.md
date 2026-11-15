# 源 computed 集合语义闭环 v1（2026-11-15）

## 结论

针对冻结 TripItineraryPlanner 修复一类真实迁移偏差：两个 computed 将原生集合操作改写成逐下标密集循环，丢失稀疏数组和回调长度快照语义。源码 dayItems 使用 filter().slice().sort()，totalCost 使用 reduce(...,0)；目标闭合 helper 链中的 filter/reduce 遍历洞位，可能额外访问 undefined、处理回调中新追加的元素。恢复两个完整源码 computed 本体，不修改全局 helper、公开业务方法、初始化、模板或 CSS。

新增 source_computed_collection_not_landed 的两个源契约；现有共享校验、repair 前处理、模型返回后处理、repair Prompt 与独立候选保护同步。生成阶段及服务器 Prompt 未修改；没有新增用户输入协议、Ref provider、跨框架运行时互操作或生产依赖。

上轮静态剩2条；新检测加2条后，本轮输入4条，修复后2条、validation_passed=false。不豁免 moveItem 的 nested_state_mutation，不恢复任意动态 setValue，不宣称组件整体通过。

## 同等求值核对及历史解释更正

上轮记录了 days 为洞/null 时 Vue 构造成功而 San 构造 TypeError。这一构造观察本身真实，但不能推出“源码同一个 getter 不抛错”：Vue 懒计算，San 提前计算。新增探针对两边按相同顺序读取 computed，并单独保留只启用指定 getter 的运行结果。

结果：源码 activeDayLabel 的原生 find 会访问洞位/null；当真的读取 getter 时也抛 TypeError。现有 target 的同类 getter 抛相同异常，只是发生于构造阶段。本轮不向源码不存在的逻辑里添加 null guard、过滤、空串兜底或 lazy 运行时适配，不把“没有读过的 getter”视作成功。本轮不证明其余 find/fromSet 等 helper 对任意输入等价。求值/异常阶段差异仍保留为待审边界，未宣称生命周期或错误捕获等价。历史冻结包和旧 Notebook 单元不改，以本轮追加解释补正。

与此不同，稀疏 items 经源码的浅初始化后仍保留洞；同等读取全部 computed 时源码正常，旧 San 发生 TypeError。该反例在 filter 和 reduce 两条独立 getter 中都复现，是本轮实际修复对象。传入显式 undefined/null 记录时，源码初始化 Object.assign({},value) 会得到空记录，其 NaN 结果保持为 NaN（探针使用显式非有限数标签，不混同 JSON null）；直接在 getter 层输入原始 null 的源码 TypeError 也保留。

## 有界规则

- 从完整源码 AST 识别两种只读计算形态：按声明状态过滤、浅切片和 localeCompare 排序；从0开始逐记录属性求和。数据字段、属性键、参数、computed/helper 名及组件名均可改变，不使用组件名白名单。
- 只在声明状态/选项无冲突、标准 San 导出、原生全局无遮蔽/显式写入等边界内分析。源 watcher/mixin、未知形态保留审查。
- 错误目标必须匹配完整 const 根读取/尾调用、不可变顶层 helper 的词法绑定、完整 getter 和 filter/reduce/sort helper 体；未知函数、逃逸引用、额外副作用或更改源 guard/accumulator 不猜测修复。
- 将源码 this.<field> 降为字面量 data.get，保留原生操作、求值顺序、洞位、回调长度快照、元素身份及异常。实际 San 中验证了依赖重算，包含初始空数组后的切换和根替换。
- 已正确的单个 const 根别名 + 原生返回形式须完整证明后认定 landed，不改写正确产物。
- 独立候选门重新计算源契约；倒退为旧 helper、变更计算体、移除 getter 或清空诊断不能伪造通过。未知形态的缺乏证明不是新发现值不一致的证据，应与已复现迁移缺陷分开统计。

## 验证及开发期发现

最终完整定向测试 233/233，14个 suite、2个工作进程、594.289秒，实现/测试指纹运行前后不变。不是全仓库测试。覆盖新集合闭环16项，以及父初始化、共享投影、记录更新、只读桥接、事件、阶段/启动/子组件工厂、候选门、校准和调度。Planner 前处理与 stub 模型响应后处理输出一致，模型调用0。

原生 Vue2.7.16/San3.15.6：

1. 全组件构造且同等读取 getter：普通、稀疏、空、显式 undefined/null 初始记录五类与源码一致。
2. 求值阶段边界：两类异常 days 保留源码 getter TypeError、San 构造 TypeError，未消除或冒充等价。
3. 两组初始状态（空/非空），各六次切换或根替换观察：computed 值和依赖更新一致。
4. 八组函数层对照（两 getter × 洞位/回调追加/记录身份/显式 null），源码与修复件一致；旧 helper 在洞位、追加情形不同。该层不替代组件生命周期验收。
5. 默认 props 的轻量初始 DOM 前/后结构、标签和文本相似度均1，TED=0，无 San 编译/渲染错误。不是浏览器交互、截图视觉验收或新增人工通过。
6. 独立 AST 比较仅两个 computed 本体变化；其他脚本（包括 legacy helper）不变，模板/CSS 原文不变。

30项规则预检发现开发期识别器误报：PlaybackQueue.totalDuration 已原生 reduce，只是多一个 const 根别名。原预检及说明保留在 recognizer_failed 包；补完整单根别名的无额外效果证明，不用组件白名单、不改该产物，并增加固定回归。此为开发期识别器问题，不算原批次组件缺陷或模型失败。历史组合测试按新增两个诊断/规则步骤同步，保留旧阻断；父初始化旧构造探针中的 sparse 风险现在被新规则修复，days 的懒/急求值边界仍显式保留。

最终沿用30项冻结/累计开发输入作共享 AST 清查：只 Trip 改写，其他29项不变，原24个通过件无此规则新诊断。不是新的全30静态/交互通过结论，更不是独立测试。

## 统计、范围和下一步

原批次24/30通过、6失败、0执行异常、1,821,544 tokens不变；本轮原生探针针对1个组件、人工确认0项、模型请求0。没有启动服务器/浏览器/Jupyter UI，不改 canonical San 或人工验收页，未 commit/push。探针的本地 Vue 文件仅作源码运行时 oracle，不是迁移后的生产依赖或 provider。

仍需核对：moveItem 共享记录写入的通知/响应式证明；任意动态 setValue 的真实调用范围与校验边界；异常 getter 的求值阶段差异。下一步先审查前两项源契约，不仅删诊断或靠增加 Prompt/反复生成证明正确。

## 证据入口

- 本包：audit.json、native_observations.json、inventory.json、implementation.json、tests.json、派生 San、SHA256SUMS.txt。
- 输入：../formal_30_v4_computed_collections_v1_input_20261115/（baseline和同等求值修复前观察）
- 识别器误报：../formal_30_v4_computed_collections_v1_recognizer_failed_20261115/。
- 只读重放：项目根执行 python -m migration_pipeline.replay_source_computed_collections_v1；不写文件/不调用模型。
- Notebook：notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb，原113个单元及 metadata 不变，追加更正与只读审计。新审计从根和 Notebook 目录执行，检查 JSON/代码，不做 UI 渲染。历史指纹依旧对应历史实现，不改旧单元来伪装其对当前版本通过。
