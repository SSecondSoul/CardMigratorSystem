# 模块化系统开发记录 2026 年 11 月 16 日

## 2026-11-17：ProductFilterPanel 公开键能力提前阻断与控件状态检查

原任务 `ea3808cfe9ff4ae7b301e5c8d593e3aa`、3 次模型调用、87999 Tokens 和 repair_budget_exhausted 失败保留。先冻结 45 个历史任务文件、源输入和 freeze.json，共 47 payload。源 SHA-256 `aed0d49a2bab60b3103e50beb0236320d35f7fb9d8bd2341db36a65be65e817a`；原接受 revision 2 不修改，最后一次同代码响应的拒绝记录不改写。

本轮没有实现任意公开键的完整迁移：用户此前保留该契约，不能把 `this[key]=value` 简化为几个固定状态键。原生 San 测试证明点号键会被 data.set 当作路径；Symbol、实例运行时命名空间等仍未证明。新增精确能力预检查复用原共享方法识别器，源合法但不支持时，在 SSM／模型 preflight／生成之前返回 `source_dynamic_key_contract_unsupported`，保存具体位置和源码绑定诊断；真实临时数据库图验证模型调用／Tokens 均为 0。这是已知不支持能力的提前识别及避免无效调用，不是 ProductFilterPanel 语义已修好或迁移已通过。其他未知方法形状仍受原静态检查和门控约束。

补齐初始态控件 live value／checked 比较，多选 select 采集选中值列表。即使 HTML 或截图相同，实际值不同也产生明确错误并使结构失败；相同值只作为独立证据，绝不删除原 value／空 class 属性差异。空 class 分析的另一处 baseParse 修正为 HTML parse，动态成员、DOM 观察及未知依赖继续阻断策略批准。工作台显示原始诊断与初始控件值状态。生成／修复 Prompt 模板、SSM、预算和阈值未改，没有有限键兼容层、手工产物补丁或新增互操作功能。

最终独立重放 `2026-11-17_modular_product_filter_contract_replay_v4` 封存 21 payload：从冻结 revision 2 执行 11 个限定动作，初始及动作后控件值均一致，双端共 24 条商品列表预期符合。但静态 fail、严格 DOM 结构 fail、整体交互 fail，编译运行／源基准／视觉 pass，最终 passed=false；原请求空动作的 not_run 不回填，不算新的迁移成功或独立测试样本。v1 为环境拦截浏览器的未完成现场；v2 在错误场景断言处退出；v3 保留错误预期下的完整结果。v4 按源名称排序和 clear 保留排序的契约修正夹具预期后重新验证，未为适配夹具修改源／目标代码。

稳定实现最终验证：新增专项 **11 项通过（33.120 秒）**；完整模块回归 `python -m unittest discover -s migration_system/tests -p 'test_modular*.py' -v` **102 项通过（671.729 秒）**，包含专项、冻结 ExpenseTracker 实际规则闭环和真实临时浏览器／工作台；原共享方法接口回归 **16 项通过（463.020 秒）**。前端 TypeScript／Vite 构建通过、Node **22 项通过**。这些工程测试不相加成迁移样本分母，根目录其他套件没有全量重跑。初次专项 6 项失败来自新模块相对 require 根目录错误，修正后独立及完整回归均通过；首次受限环境中的模块运行浏览器被拦截，已中止并在获准的隔离浏览器环境重新完整运行，未把中间失败记成成功。

47 个冻结 payload、21 个重放 payload、当前实现指纹，以及原 45 个任务文件和源输入共 46 个原件核验不变。Notebook 已追加，JSON／13 个唯一单元 ID 校验通过。本轮无真实模型调用、LangSmith 上传、真实数据库写入、commit／push。详见 [公开键契约及控件检查记录](PUBLIC_KEY_CONTRACT_20261117.md)。部署仅需重启 API／migration-worker 并刷新，无数据库升级；该样本仍缺少完整公开键能力，不建议继续付费复跑。

## 2026-11-17：源模板 HTML 空元素解析与可定位错误提示

原任务 `3d3d69c7760045e1bd0c741f7cf3638b`（InvoiceLineEditor）在模型调用前被阻断，模型 0 次、Tokens 0。原因是新浏览器评估入口使用不含 HTML 平台规则的 `compiler-dom.baseParse`，将合法 `<input>` 误判为缺少结束标签；不是源 Vue 已被证明有错，也不是浏览器未安装或模型失败。本轮仅修正该入口为 `compiler-dom.parse`，San 目标解析、SSM、Prompt、阈值、模型预算和用户配置不变，没有删除适配层。

补齐 input／img／br／hr／wbr 普通与自闭合写法、兄弟节点、真正缺失／错配结束标签、脚本语法错误、含 emoji 的 UTF-16 行列、诊断来源边界、临时数据库图阻断及真实工作台／双端浏览器测试。真正不完整的非空标签仍在生成前阻断，不能通过忽略解析错误放行。源模板／SFC／脚本错误分别记录固定代码、位置精度和有限片段，Python 根据当前上传源码重算位置和片段；工作台以转义文本显示具体错误及零模型调用状态。LangSmith 不上传这些源码片段，历史报告没有诊断时不补造。

先复制原 request、failure 和源输入，共三个历史文件。修复前／后证据分别为 `2026-11-17_modular_source_void_elements_preflight_v1`／`v2`；同一源码 SHA-256 `9b50005a20314dd9c1f52db9496c6092d8f2838958955be0fa0350db7c77a8df` 从 blocked 变为 completed。v2 单独封存 10 个 payload，核验实现指纹及三个历史原件不变。离线工具不启动渲染浏览器、不调用模型、不改真实数据库或任务；这个 completed 只表示源预检查通过，没有生成 San，不是该样本迁移质量通过。

最终新增专项 **12 项通过（33.895 秒）**；完整模块回归 `python -m unittest discover -s migration_system/tests -p 'test_modular*.py' -v` **91 项通过（241.352 秒）**，含冻结 ExpenseTracker 初始响应完整图、候选保护及真实浏览器回归。前端 TypeScript／Vite 构建通过，Node 前端测试 **22 项通过**。专项已包含在模块回归，不能相加当作迁移样本数。本轮未重跑根目录旧流水线全套，其上一轮结果保留原记录。

开发中空元素浏览器夹具最初混入 input 静态 value 的 Vue 属性／San 控件属性表示差异，导致一项失败；随后改用 placeholder 隔离本次解析目标，最终专项重新全部通过。未修改 DOM 比较规则来掩盖该独立差异，未把中间运行写成全通过。

说明和重放命令见 [源模板解析修复](SOURCE_TEMPLATE_PARSING.md)，Notebook 已追加本节。前端 dist 已构建；部署重启 API 与 migration-worker，刷新后新建任务即可，无数据库升级。原任务失败和零费用记录不变；本轮真实模型调用 0、LangSmith 上传 0，无 commit／push。

## 2026-11-17：初始生成语法、拒绝反馈和规则调度闭环

原任务 `b2a59e959191487fa4c3acbe945f04cb` 的失败与 80802 Tokens 原样保留。本轮没有真实模型调用、LangSmith 上传或真实业务队列／数据库更新。先冻结 29 个任务文件和源输入，共 30 个，再使用本次初始生成而非挑选已通过候选进行重放。

修改包括有来源证明的缺失 option、受限多处括号／方法逗号恢复；语法专用消息携带同父版本被拒绝尝试的哈希／原因／实际诊断；完全相同修复 messages 在模型调用前阻断。生成 Prompt 及旧语义 Prompt 模板未改；修复预算／Token 停止线／阈值未增减。完整边界见 [闭环补齐记录](SYNTAX_CLOSURE_20261117.md)。

语法解除后完整路径又发现字符串 CSS 包络、非 San watcher 配置，以及 `missing_watch_migration` 没有调度到有界规则的遗漏。本轮在共享 CJS 与 `RepairStage._deterministic_repair_plan` 同时补齐来源匹配规则和诊断→修复映射。浅 watcher、immediate、未知回调／启动副作用、复杂 CSS 或不同业务操作数仍拒绝推测。

最终语法证据 `2026-11-17_modular_expense_tracker_syntax_closure_v3`：四个冻结 revision 均通过语法检查，36 个 payload 单独封存。最终语义证据 [semantic_closure_v3 报告](../data/experiments/evaluator_calibration/2026-11-17_modular_expense_tracker_semantic_closure_v3/REPORT.md)：从初始 revision 0 的语法规则输出出发，总诊断 9→0；编译运行／源基准／静态／结构／视觉全部通过，SSM／San、原始与有效 DOM、UI 均 100%，SSIM 1、不同像素 0；额外 15 步交互全部通过。辅助源／目标 AST 仍 96.10%，不改指标或阈值。规则幂等、候选门控接受，新目录封存 62 个 payload；原任务仍失败，原空动作仍 not_run。

中间证据全部保留：syntax v1 为旧规则基线，v2 为未修完第四候选的中间版本；semantic v1／v2 静态仍剩 3／2 条，不计成通过。浏览器在受限环境启动失败也不计成组件质量结论，最终真实浏览器测试在临时隔离 context 完成。

专项语法／反馈测试 24 项通过（53.290 秒）；共享语义／实际调度／原生 San 测试最终 20 项通过（75.513 秒）；原流水线回归 78 项通过（383.318 秒）。最终完整模块回归 `python -m unittest discover -s migration_system/tests -p 'test_modular*.py' -v`：79 项通过（490.876 秒），包含上述语法专项与新增初始响应完整图测试。这些是有重叠的工程用例，不相加当作迁移样本数量或独立成功率。

新增 `test_modular_frozen_closure.py` 在临时数据库中注入冻结初始生成响应与 SSM，实际执行 LangGraph、解析器、共享验证／规则、候选门控和真实浏览器。原 3 轮修复额度不增加，最终通过全部维度及 15 个动作；生成响应为一次明确的测试替代，之后没有模型修复调用，所有修复 revision 都来自实际规则。未使用测试替代的质量分数。未知调用、重复请求、幂等、历史失败不回填等保护同时通过模块回归。

部署要重启 API 与 migration-worker，新建任务绑定新实现；不恢复旧任务，不改原源码或手工页。离线已记录响应的图回归不能替代新的真实模型迁移质量验证。

## 后续：语法之后的事件、生命周期与 DOM 闭环

在上一节语法修复的基础上继续处理同一冻结任务，不调用模型。输入固定为原接受 revision 1 的语法修正候选 `6b513daf6bb3e8a12738516f01d2c8b34bd0be6f675171dee84f1fea2065438a`；原任务、Vue、原 San、费用账本及手工页面不修改。

诊断发现：Enter 键事件旧规则已经能修，但在编译失败时无法有效运行；旧类名规则覆盖对象映射，漏掉字符串引用与静态类拼接无空格；样式对象的单位拼接与 CSS 插值不能对应；mounted 阶段规则把已有 watcher 误当成 mounted 动作，漏掉一次加载移位。共享 `class_binding_semantics.cjs`、`source_render_dependency_semantics.cjs`、`source_phase_semantics.cjs` 分别补齐有边界的证明与修复，事件仍复用原 `source_dom_semantics.cjs`。

规则按源码、元素路径、循环／条件作用域及 AST 验证，不看组件名。数值样式叶方法允许恢复错误扩展的源公开签名，再隔离为显式依赖的私有模板方法；有其他脚本／事件引用、多模板根、单位／参数／体变化、未知调用或副作用则不猜测。类名只证明字面分隔符，合法拼接不误报；未知表示保留 review，不冒充完整类型等价。watcher 回调、字段、选项和原挂载调用必须可匹配，且无其他早期／未知启动效应。详细条件见 [语义闭环说明](SEMANTIC_REPAIR.md)。本轮生成、语义修复及语法专用 Prompt 都未再修改，SSM、阈值和调用预算不变。

原任务 `5c2fc8916fcd4b8bb65f32ea28e20488` 仍为失败及 175512 Tokens。离线规则候选 `9b8be8e3a0adcd7bd1f0b03246601b21441954a281b281ad31acea542fd1e34f` 静态错误从当前检查的 7 项降至 0；编译运行、源基准、静态、模板结构、原始／有效 DOM、视觉通过，原始 DOM／SSM 结构 100%、UI 100%、SSIM 1、不同像素 0。候选门控 strict_improvement 接受，重复运行规则字节不变。另加 15 步诊断交互全部通过（非 Enter、Enter、收支、过滤、主题、删除），不回填历史 not_run。

辅助源 Vue／目标模板 AST 投影保留 96.10%，三个差异为 Vue `binding:key` 与 San 循环内 trackby 的表示位置；未把该辅助指标改为 100%，未改投影公式或阈值。最终 56 个新 payload 哈希与实现指纹、原任务 24 个文件及源输入共 25 文件不变均核验，Notebook JSON／10 个唯一单元 ID 校验通过。证据说明 REPORT.md 在生成清单后补写，不包含在 56 个 payload 内。

最终证据为 `data/experiments/evaluator_calibration/2026-11-16_modular_expense_tracker_semantic_replay_v3`，v1／v2 保留中间实现及测试副本。先验证／冻结上一轮 30 个 payload，再写新候选、实现、原始快照、截图和清单，不更新数据库。本轮模型调用 0、LangSmith 上传 0，无 commit／push；不算独立测试或新增模型成功样本。

最终验证分别执行：新增规则专项 **16 项通过，41.386 秒**；模块回归 `test_modular*.py` **70 项通过，320.199 秒**；旧 TaskManager 冻结失败闭环专项独立复测 **1 项通过，186.200 秒**。原生 San 验证公开数值方法／模板随字段更新，以及先注册 watcher、再只加载一次；反例覆盖错误单位、业务体改动、未知调用、脚本引用、别名／作用域、即时或重复 watcher、合法类名拼接不误报等。各套件有重复覆盖，不能相加当迁移样本数。

开发中一次合并运行 114 项有 3 项失败，没有作为完整通过证据：两项来自尚未修正的测试夹具（原生 San 根结构假设、替换误伤方法签名），另一项为与修改过程重叠的旧样本诊断计数不一致，稳定实现上的独立复测通过；后续新增 watcher 原生测试已加超时／显式结束，不遗留等待进程。以上最终三组重新运行结果独立记录，不声称根目录全部测试已在最终指纹下一次完整通过。部署只需重启 API／真实 Worker 并新建任务，无数据库升级；真实模型端到端效果仍待新运行验证。

## 补充：ExpenseTracker 语法优先闭环

原任务 `5c2fc8916fcd4b8bb65f32ea28e20488` 停止于 `model_usage_stop_reached`：3 次模型调用，已知 Tokens 175512。源文件哈希 `47995c773b5698e5f4fda5b5e854b27648c3b1e030a845ab19790930ad564736`。根因不是已证明 Vue 错误，而是目标代码将 s-for 写成伪标签，前两轮脚本还缺对象方法分隔逗号；编译适配层泛化报错且语义分析级联，未形成语法优先闭环。

新增 `target_syntax_first_v1`：SFC／Babel／San 解析诊断保留位置与片段；未知精度明确标注。先解析再调用旧语义验证器，语法失败不把 not_run 视觉检查当成 visual_mismatch。新增源码匹配的单子元素循环属性规则和 Babel AST 确认的相邻对象方法逗号规则；不按组件名特判，不补造丢失元素。规则无效或被拒绝时使用新增的聚焦语法修复消息，避免重复注入完整 SSM。旧生成 Prompt 和语义修复 Prompt 入口未修改，实际新增了语法专用消息与路由。预算和阈值均未增加。

候选仍复测：语法失败时记录局部进展；语法首次通过后允许进入此前未执行的语义检查，不把新可观察错误当成回退。原通过维度／源基准保护不取消，语义阶段的新错误保护不变。详细范围与命令见 [语法闭环说明](SYNTAX_REPAIR.md)。

离线工具先冻结历史原件再回放；最终证据 `data/experiments/evaluator_calibration/2026-11-16_modular_expense_tracker_syntax_replay_v4`。初始版语法诊断由 10 降至 3，因缺少 option 子元素而继续阻断；原第 1、2 轮产物经规则后分别从 10／9 降至 0，可运行浏览器，但静态语义和 DOM 仍失败，生命周期／事件／渲染依赖及第 2 轮的隐藏依赖错误继续保留。未执行额外代表动作，不把原 not_run 改为通过。

原 24 个任务文件及源输入共 25 文件在回放前后核对，历史状态／费用／产物未改写。首次 v1 因沙箱内浏览器启动超时中断，保留未完成说明；v2／v3 为中间完整证据，v4 对应最终位置精度实现。本轮新增模型调用 0，无 LangSmith 上传、无 paid rerun、无 commit／push。

最终验证：`python -m unittest discover -s migration_system/tests -p 'test_modular*.py' -v` **70 项通过，166.829 秒**，包含新增语法专项 16 项、原评估器／策略／真实浏览器／候选保护／账本及前端提交回归。仅指模块工程测试，不是 70 个真实迁移样本，也不是重新跑过最初全部系统套件。先前沙箱内浏览器超时，以及一次并行运行的前端等待超时，均未计入通过；独立重试后可运行。新增 San 非法表达式用例最初被外层 Vue 解析器提前拦截，后改为确实进入 San 事件表达式解析器的反例，未放宽生产解析规则。

最终 30 个证据 payload 哈希及当前实现指纹均核验；Notebook 9 个单元 JSON／唯一 ID 校验通过。对初始版规则候选构造聚焦消息（未发送）：旧第一次修复消息总字符 234771，新语法消息 30618；这是字符数对比，不是 Token 数或账单节省证明。尚未执行新 Prompt 的真实模型效果验证。剩余语义／DOM 问题继续保留为后续工作，不以调高预算或离线语法成功宣称已全部修复。

## 请求与范围

用户确认 0006 升级和网页后，要求按开题报告连续完成系统模块，不再每完成一个小模块就暂停人工交接；密钥和外部资源集中登记，开发完成后补充。本次没有修改开题报告或用互操作扩展任务。

核对了开题报告原文的研究内容 1.1—1.4、关键问题及目标，并参照既有实验审计与 r3 整合方案。项目仍采用独立 `migration_system`，旧实验流水线、SSM、人工测试页面、原 Vue、Notebook 和快照不修改。

## 交付代码

- 真实任务持久化、API、独立 worker 与 LangGraph 节点／条件边；数据库 0007 只增表。
- 真实 SSM、统一生成和 few-shot、Qwen 单次 HTTPS 调用及原始响应／usage 账本。
- 旧校验／规则／修复 Prompt 的只读版本适配，新 SSM／目标 San 模板 AST 和 DOM 有序 TED。
- Puppeteer 双端新 context、受控渲染、截图、关键样式、代表动作、均匀窗口 SSIM、不同像素率与热图。
- 同口径候选复测、原通过维度保护、新错误保护、无改善拒绝、终态报告和人工反馈。
- 显式 LangSmith 摘要追踪；训练数据构建、PEFT LoRA 训练、本地 adapter 推理；可选本地视觉嵌入。
- 真实工作台默认页签，开发夹具／SSM 历史仍保留；代码、图片、完整记录下载和人工台账。
- 独立 Node 依赖锁，Python 51 项运行时锁重新解析，训练大依赖另行配置。

完整路径、语义和部署见 [系统指南](SYSTEM_GUIDE.md)，待补密钥／资源见 [配置清单](SETUP_PENDING.md)。包仍为开发版本，不以改版本号宣称生产验收。

## 协议与证据边界

新 `modular-migration-v1` 与既有 G1—G3、正式／探索性实验分开。次数／输出额度／已知用量停止线不是严格输入计数或账单上限。旧 G3 的上界批准仍不自动放行，旧冻结请求不改写。

通过代表给定 props、给定场景和新指标阈值，不代表任意公开键、事件共享、异常阶段等问题已全面证明，也不能直接报告论文总体正确率。默认 few-shot 两例为自建开发演示，不是从测试集取答案；研究 corpus 和 LoRA 效果另需验证。

现有实际库通过只读 SQLite 查询确认为 0006，源输入三条。没有对该库执行 init-db、入队或写反馈。测试全部使用临时数据库、临时产物或固定本地组件；浏览器校准不使用现有用户会话。

## 内部验证

开发过程中曾发现并修正新表混入旧 metadata 的建库问题、评估页默认 favicon 的伪基准告警、目标运行异常被错分为设施失败等问题。没有删除源组件警告或降低通过阈值。全套回归与收口专项分别执行并保存独立日志；先前边开发边运行产生的绑定漂移不作为最终通过证据。

完整回归命令 `python -m unittest discover -s migration_system/tests -v`：**330 项通过，595.297 秒**，日志在本机忽略的 `migration_system/var/modular-verified-tests.log`。原 P1 契约 **40 项通过**；前端 Node **22 项通过**，像素校准 Node **1 项通过**；TypeScript 检查与 Vite 构建通过。

在完整运行期间及随后进一步补充了嵌套 San 模板块解析、被拒绝规则转模型修复、规则轮数不占模型调用额度、越限收据不能重放放行等专项。当前模块专项 `test_modular*.py` **32 项通过，59.724 秒**，日志 `var/modular-current-tests.log`；训练数据专项 **3 项通过，0.666 秒**。完整套件当次为 330 项，当前测试收集为 333 项，新增用例已包含在收口专项中；没有声称以同一命令一次跑过全部 333 项。专项与完整套件有重叠，不把次数相加当独立样本数，更不是迁移正确率分母。

规则候选被拒绝后，同一接受父版本不再重复提交相同规则结果，而转模型修复；模型调用额度按实际登记调用数计算，规则轮次不会占掉调用名额。超过每次输出上限的响应保留实际用量并阻断，重放收据仍阻断，不能借恢复绕过检查。这两项均有正例／保护测试。

已单独验证：真实 Puppeteer 静态同图、已知颜色差异、目标运行异常、真实 SSM／静态校验／按钮交互；真实 Vue 前端→Flask→一次性 SQLite 提交。浏览器最终解析器专项 **4 项通过，57.294 秒**。包已通过隔离构建后以 editable 安装，未手改 egg-info。只读 `system-status` 当前仅报告模型网络未开启、模型 key 缺失；这符合本轮不调用外部模型的要求。

## 未执行

没有云模型调用、LangSmith 远程上传、模型权重下载、LoRA 训练或真实模型效果验收；没有复跑历史 30 项／独立测试，也没有 commit 或 push。缺少资源的项目保持明确待验证，不用模拟数值补齐论文指标。

## 首次真实提交后的适配修复：CommonJS 源导出

用户启用模型网络并提交 `DeliveryPhaseCard.vue` 后，任务 `3a5205caedf0413493256822a1928be9` 在 preflight 以 `unsupported_source_sfc` 阻断，模型开始／未知调用／已知 Tokens 均为 0。只读核对上传文件与仓库原样本 SHA-256 相同：`2a057ec6591b35d3044b9b77106e849ccea48e0ac407ab39d34d7e37fceda16b`；不是上传不完整，也不是生成或修复失败。

根因：新浏览器适配器只接收 `export default`，但旧数据集合法 Options API 源码使用 `module.exports = { ... }`。在 `browser/evaluate.mjs` 的源导出识别处补充单一顶层 CommonJS Options 对象；仅在隔离浏览器内提供模块作用域，源码不在 Node 执行、不修改上传文件／原数据集，也不修改旧阻断记录。混合导出、重复导出、CommonJS 工厂调用、外部 import 继续阻断。新增预检正反例和真实浏览器点击更新测试；离线测试夹具强制关闭网络，避免用户本地开启配置影响测试或授予真实调用权限。

旧任务保持失败时的绑定；部署此修复需重启 API 与 `migration-worker`，刷新网页并新建任务，不能将旧冻结请求改写为新实现。该修复属于评估源加载适配层，不是 Prompt 调整；不降低质量阈值，不代表组件迁移已通过。

本次验证：`AlgorithmTests + ModularTests + SafetyTests` 共 **29 项通过，26.691 秒**；`BrowserCalibrationTests` 共 **5 项通过，66.388 秒**（包含 CommonJS 源作用域／点击、既有 ESM 同图、颜色差异、真实 SSM＋静态＋交互和目标异常分流）。工具沙箱内浏览器启动曾阻断；获准在沙箱外使用独立临时浏览器运行后五项均通过，没有关闭 Chromium 沙箱或借用用户会话。Notebook JSON 与六个单元 ID 校验通过。以上不涉及云模型调用。修复后 `browser/evaluate.mjs` SHA-256：`823b24ed09cb3fb6ad8ecef17b44735c9b50068871bf0cdf932849762b84309b`；旧失败文件哈希仍为 `22b4ec17f68a0b029baa2f4df0c97585de9854c80d97fd03acb1fd0d28c0a0d6`。原 `verification_20261116.json` 保留原开发验收时的指纹，不冒充本次修复后的指纹。

## FocusCard：新旧评估对照及离线校准

用户任务 `f3cf07b0c7e5462aaf1b1cd5a781b37a` 已真实调用模型 3 次、已知 Tokens 41391，原状态 `failed / repair_budget_exhausted`。最终接受产物是第 1 轮（SHA-256 `0ced63ec865d38bedf3cdc4d5a102780d35d48684639af75900675f69decaced`），静态 class 检查失败、新 SSM／San 结构 57.14%，但实际 DOM 和视觉均 100%。不是所有失败都应继续通过模型修复。

经只读原产物复核，修正了三处通用检查问题：旧共享 `class_binding_semantics.cjs` 在先验证原始 token 边界后归一化条件字符串类名空白；新浏览器 AST 投影按 San 表达式类型处理整段三元插值、恢复合并 class 的固定 token，并在合并相邻文本后归一化空白；样式路径改为元素兄弟序号，不受缩进文本／注释影响。没有删除文本、条件或真实节点差异。结构投影升为 v2，阈值、TED 代价和 UI 配方不变；结构路径／标签差异随评估传给诊断，避免只给分数。旧依赖指纹新增 `.cjs`／`.js`，防止 Node 语义检查器变化不被绑定识别。

新增只读脚本 `scripts/replay_evaluator_compatibility.py`。它不构造模型客户端或恢复任务；核对历史文件哈希，对照旧验证器直接调用／新适配层调用、旧 DOM 阶段、新 AST 和真实浏览器。新建证据目录拒绝覆盖，不重绑原任务。原产物不变时，当前静态语义通过，SSM／San 与源／San AST TED 均为 0，实际 DOM 100%、UI 100%；旧验证器直接调用与适配层结果一致；旧 `VisualEvalStage` DOM／文本相似度也均为 100%。另行补充开始／停止两次点击，代表交互通过，不回填原报告中的 `not_run`。

完整证据在 [校准报告](../data/experiments/evaluator_calibration/2026-11-16_modular_focus_card_evaluator_replay_v1/REPORT.md)。本轮修复／重评新增模型调用 0，未改变生成或修复 Prompt、原源码或产物。原任务状态和 41391 Tokens 保留；离线重评通过不是新的模型迁移成功样本，更不是全量旧实验等价或独立测试证据。原 `verification_20261116.json` 是此前开发验收记录，不更新成当前指纹。

收口时补充了多 token 源 class 键内部空白归一化，并增加原生 San 状态正例；最终实现重新离线重评，结果相同、原报告哈希仍未变。最终证据在 [v2 收口报告](../data/experiments/evaluator_calibration/2026-11-16_modular_focus_card_evaluator_replay_v2/REPORT.md)；v1 保留为首次对照，不覆盖其实现指纹。共核对 46 条原历史文件／输入记录（含重复引用），每个新目录脚本生成的 7 个文件哈希另行校验。

本轮原流水线回归 `python -m unittest discover -s tests -p test_migration_pipeline_regressions.py -v`：**78 项通过，153.477 秒**。随后多 token 边界收口后重跑共享 class 专项 `test_class_binding_closure_v1.py`：**28 项通过，116.818 秒**。正反例覆盖合法条件字符串空白、多 token 类名、错误条件、错误 token、丢失条件、类名粘连、源作用域／注册不匹配、未知表达式、分析器失败不能放行、候选回退和原冻结产物。新 AST 反例保留丢失静态 class、字面文本、节点、标签和事件差异；浏览器用缩进版目标验证 DOM／样式和两次点击一致。次数不与历史专项相加当迁移样本或全量系统重跑证据。

最终收口实现的模块专项 `python -m unittest discover -s migration_system/tests -p 'test_modular*.py' -v`：**41 项通过，136.497 秒**，包含实际隔离浏览器和工作台到临时数据库提交；云模型为明确测试客户端或不调用，未触及真实业务队列。首次同专项 41 项、126.284 秒的结果保留为中间验证，不与收口重复计数。Notebook 仍为工程记录，原报告／两次重评文件清单均完成哈希核验。

## ChoiceChips：原始 DOM 属性存在性与受限比较策略

任务 `6d2eb1d3cc034c88b1b4167728334c8c` 的接受产物为第 2 轮（SHA-256 `6b4bd4b84d866d93e37a0fdbb742ea3d6ea2ce52d39a22088a1c4a43121bce29`）。原静态语义／编译运行／视觉通过，SSM／San AST 100%，原始 DOM 83.33%，原任务 `failed / repair_budget_exhausted`，模型开始 3 次、已知 Tokens 36725。两处差异仅是未选中按钮的 Vue `class=""` 与 San 无 class；它们在 CSS `[class]` 或 DOM 属性读取下可能可观察，不能无条件称为完全等价。

新增 `browser/empty-class-policy.mjs` 做双端保守 AST／模板／CSS 审查，阻断 DOM 访问／反射、未知调用、外部／运行时扩展、CSS 属性选择器／转义／`attr()` 等不明依赖；未知语法保持严格比较。对获准的自包含数据组件，仅在比较副本中归一化精确空 class，原始 DOM 树、原始 TED 和差异完整保留，其他属性与非空 class 不忽略。新报告明确 `empty_class_presence_v1` 策略、原因、改变路径和 `raw_dom_ted`；这是一项版本化、受限观察范围内的比较策略，不是证明任意外部 DOM 观察者等价，也不是原始 DOM 自动变为 100%。

补齐 `rendered_dom_mismatch` 及动作失败诊断，提供实际节点路径／属性差异／策略原因，随现有修复消息传递；未修改生成／修复 Prompt 模板，但实际消息会含新增诊断。候选评分补入 DOM 严格改善，其余原通过维度／新错误保护不变。原始源码和产物、阈值、UI 公式和修复预算未变。

旧验证器直接调用与新适配层均通过；旧 `VisualEvalStage` 通过、DOM／文本均 100%。本次新浏览器重评保留原始 DOM 83.33%，有效比较 DOM 100%，静态语义／编译运行／源基准／结构／视觉全部通过。另用动作文件 `configs/diagnostics/choice-chips-actions.json` 验证即时、每日、关闭、恢复每日四次选择，均通过；每步原始／有效 DOM 差异保留，不回填历史 `not_run`。辅助源模板 AST 87.5% 的差异是 Vue `:key`／San trackby 表达位置，不是本轮失败来源；未把辅助指标改为 100%。

证据见 [ChoiceChips 重评报告](../data/experiments/evaluator_calibration/2026-11-16_modular_choice_chips_dom_replay_v1/REPORT.md)：原报告 SHA-256 `bb45e4d3745e03fdfaf8acc5d4e31a7b79c53fc6bcc07bc6055abe717322994a` 保持不变，核对 46 条历史引用（含重复引用），新证据单独保存并校验清单。本轮实际新增模型调用 0，未上传 LangSmith、未恢复或改绑旧任务；原 36725 Tokens 成本不抹除。

验证：策略／比较纯测试 **10 项通过，25.051 秒**；随后 `python -m unittest discover -s migration_system/tests -p 'test_modular*.py' -v` **53 项通过，167.236 秒**，覆盖真实浏览器正例、CSS `[class]` 保持失败的反例、反射／未知调用拒绝、旧快照不自动改写、非空 class／其他属性不放行、原图路由与回退保护。之后只新增测试（未改生产实现），单独运行 `EmptyClassRepairFeedbackTests` **1 项通过，1.537 秒**：用明确测试客户端验证实际 DOM 诊断和节点属性到达现有修复模型消息，云调用仍为 0。没有声称以同一命令一次跑过全部 54 项，专项不与历史统计叠加当迁移成功样本。原报告与新 7 文件清单、当前实现指纹、Notebook JSON／单元 ID 均核验。
