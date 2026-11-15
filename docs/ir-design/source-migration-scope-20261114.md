# Vue 到 San 源码迁移研究范围决定

日期：2026-11-14。依据：用户明确要求按开题报告开展研究，不需要 Vue/San 运行时互操作，不额外添加功能，以提高迁移正确率为目标。

## 研究主线

以 `docs/paper/专业学位硕士研究生选题报告4.docx` 中主要研究内容 1.3、1.4 和关键问题 2.4 为依据：

Vue 源码及必要依赖 → 自动提取 SSM → 生成 San → 结构、编译、行为及视觉校验 → 规则或模型修复 → 回归验证与实验统计。

使用者不需要编写依赖 provider、注册跨框架订阅能力或额外保留 Vue 来驱动迁移后的 San 状态。必要的子组件、模块源码、运行环境及测试数据，与上述额外互操作接口不是同一要求。

源码中的状态初始化、computed、watch、生命周期、事件、动态样式和父子数据绑定仍属于应正确迁移的内容。不能因为停止互操作研究而跳过这些语义；若源码本身使用 Ref，也应研究其构造和使用逻辑的迁移，而非要求用户提供外部 Vue provider。

## 不再推进的路线

- 不实现 `native-ref-dependency-interop-v1-draft.md` 中的 provider 协议，也不开展其公开 API 可行性原型。
- 不将“外部仍在运行的 Vue 程序持续修改同一个原生 Ref，San 保留其原生身份和订阅关系”作为本研究新增的必选功能。
- 不为该路线增加生产依赖、应用接入要求、Prompt 要求或验收门槛。

此前设计稿和结构化清单保留为历史提案，状态改为用户决定不纳入研究范围；不是实现成功，也不是通过证据。

## 证据和判定约束

既有冻结包、失败反例、Notebook 历史单元和批次 summary 保持不变。既有范围下的失败不能回填为成功，原统计分母、修复轮数、token 和运行记录不能重写。

后续将问题按来源区分：源组件及必要依赖实际需要的迁移语义、评估器缺陷，以及额外构造的跨框架互操作探针。范围分类不是诊断豁免；不能仅删错误码或降低阈值来提高正确率。已知生命周期、队列和父子更新差异须逐项判断是否涉及源码迁移，不能整体归为互操作后忽略。

## 后续工作顺序

1. 对照冻结源组件和失败报告，整理主线缺陷清单，并核对生产校验、候选准入是否误把额外互操作能力当作必要条件；本决定本身不自动解除任何现有阻断。
2. 对确认的迁移缺陷建立“源语义 → 检测 → 有边界的通用修复 → 回归用例”闭环；能确定修复时用规则，复杂问题给模型明确反馈，保护已有正确部分。
3. 先使用冻结失败产物做离线验证，再以隔离的新实验版本复跑受影响组件及回归集，比较初次通过率、修复后通过率、修复成本和人工复核结果。

本次仅确定范围并同步记录，没有实现新的修复，没有运行模型或新增通过结论。后续需付费模型运行或人工验收时，仍交由用户执行或确认。

## 后续核对记录

范围分类与首次离线核对已完成，见 `data/experiments/analysis/formal_30_v4_source_migration_scope_audit_v1_20261114/REPORT.md`。六个指定历史候选编译均通过、三个静态通过、三个仍失败；不是新批次成绩。下一项是 TripItineraryPlanner 的源渲染依赖、状态提交和方法接口核对与通用修复，不再推进 Ref provider。现有生产阻断未解除。

TripItineraryPlanner 第一项有界修复已完成，见 `data/experiments/analysis/formal_30_v4_trip_event_interface_v1_20261114/REPORT.md`：共享 repair AST 规则恢复公开事件转发包装接口，冻结候选诊断9→7，45项定向测试通过；组件整体仍未通过。下一项核对 updateDraft 克隆／提交链及别名检测，再处理渲染依赖和动态 setter，不跳过剩余问题或直接付费复跑。

TripItineraryPlanner 的 updateDraft 源记录浅复制／字面量根提交闭环已完成，见 `data/experiments/analysis/formal_30_v4_record_update_v1_20261114/REPORT.md`。新增有界通用 repair AST 规则、源契约检测、repair Prompt 约束与独立候选保护；生成 Prompt 未修改，未知克隆及副作用模式继续阻断。旧版7条诊断加1条重叠新检测后为8条，自动修复后为6条；95项定向测试通过，真实冻结组件4次原生方法对照一致，仅 updateDraft 改变。仍非整组件通过，未新增人工验收、模型调用或全30项重跑，原24/30统计不变。下一项处理 isConflict/dayCount 的源码私有渲染依赖；moveItem 和公开动态 setValue 保留阻断，等待各自源契约证明。

TripItineraryPlanner 的私有渲染依赖桥接闭环已完成，见 `data/experiments/analysis/formal_30_v4_render_bridge_v1_20261114/REPORT.md`。规则按完整体／词法绑定识别只读外部桥接，生成两个源码派生私有方法，使文本、条件 class 和 s-if 显式传入 items／conflictIds；公开脚本和 CSS 不改，computed 保留为已声明依赖边界，不宣称全面等价。DOM 作用域检查只复用重新证明的完整条件，候选门独立拒绝丢失证明或清空诊断。上一版6条加2条重叠新检测后为8条，修复后2条；最终179项定向测试通过（非全仓库），真实组件5组原生方法／编译表达式对照一致。失败和测试修正已另包保留，Notebook 已追加。30项仅作规则清查，原24个通过件不改写且无该规则新诊断；不回填原分数、不新增人工通过、不运行模型。下一项分别审查 moveItem 的共享记录突变／提交和公开动态 setValue，不盲目深克隆或按点路径解释动态键。

共享交换的源浅投影修复已完成，见 `data/experiments/analysis/formal_30_v4_shared_swap_v1_20261114/REPORT.md`。通用 repair AST 规则保留源共享写入，恢复浅复制／未选中记录身份及根提交、标记、通知顺序；源契约检测、repair Prompt、独立候选保护与事件包装器原子组合已验证。上一步2条静态诊断加新投影检测为3条，修复后仍2条：不豁免 nested_state_mutation，不伪造任意动态 setter。169项定向测试通过，九类原生方法输入与源码一致；其他脚本／模板／CSS 保留，原24/30统计不变，无模型／新人工通过。另确证 initialItems 初始化仍有深／浅克隆嵌套引用差异，未被本步方法测试或当前两条诊断覆盖；已保存反例，不能把“静态剩2条”当“实际只剩2个问题”。下一步优先闭合初始化浅复制偏差，再审查共享写入通知证明与动态辅助接口校验范围，不新增互操作能力或用户输入要求。

父初始化浅复制闭环已完成，见 `data/experiments/analysis/formal_30_v4_parent_initialization_v1_20261114/REPORT.md`。通用 repair AST 规则恢复源码 created→inited 的原生 map／Object.assign 浅记录复制及首元素存在性判断；检测、修复前后处理、repair Prompt 与独立候选保护同步，生成／服务器 Prompt 不改。217项定向测试通过（非全仓库），仅父 inited 改写，其他脚本／模板／CSS 不变。新诊断使输入2→3条，修复后仍2条、整体未通过；原24/30统计与人工页不变，模型调用0。普通嵌套、Symbol、循环和空值初始化原生对照一致；稀疏 items／空首日期的完整组件仍因旧 computed helper 抛 TypeError，隔离钩子通过不冒充组件等价。开发失败及历史测试更新已保存并追加 Notebook。下一步核对 computed 外部辅助函数的原生集合语义，再审查共享写入通知和动态辅助接口范围，不直接付费复跑或准备独立测试。

2026-11-15：computed 集合闭环完成，见 `data/experiments/analysis/formal_30_v4_computed_collections_v1_20261115/REPORT.md`。源码驱动规则恢复两个完整原生集合计算体，不全局替换 helper，检测／repair 前后处理／repair Prompt／独立候选门同步；233项定向测试通过，4条诊断修复后仍2条，整体未通过。五类原生初始化及切换／根替换、洞位／回调追加／记录身份对照一致。清查中的 PlaybackQueue 正确 const 根别名识别器误报已保留并修复；原24个通过件不改写且无此规则新诊断。补正上轮解释：days 洞/null 的 source find 在同等读取时也抛错，不能以 Vue 构造成功证明 getter 成功；San 的提前求值/异常阶段差异仍待审，本步不添加兜底、不证明其余 helper 对任意输入等价。只两个 computed AST 改变，其他脚本／模板／CSS 不变；Notebook 追加，原24/30统计不变，模型与新增人工确认均0。下一步审查共享记录写入的通知证明及任意动态 setValue 的真实调用/校验范围，不直接付费复跑或进入独立测试。

2026-11-15：剩余源调用／通知链审查完成，见 `data/experiments/analysis/formal_30_v4_remaining_contract_audit_v1_20261115/REPORT.md`。5组 moveItem 输入在根提交／通知／事件／引用身份的声明投影下一致，原始内部trace不同；额外外部深层同步观察者为Vue3次、San1次，不据此豁免现有诊断或实现provider。源setValue的14处字面量根调用与目标写入位置及次数对应，不证明右值／时序和公开接口等价；点号键和新增实例字段反例保留。生产规则、Prompt、校验口径和人工页不改，静态仍2条且失败。本轮新确证稀疏items下源码删除按钮方法removeItem仍因目标旧filter访问洞位而失败，源成功且事件1次、目标不变且事件0；公开dayCount同根因失败另记，不能混同已有私有模板helper。12项审查证据测试通过（含预期失败，不是组件通过），前轮233项未重跑但25个既有实现／测试指纹不变。Notebook只追加，原24/30与tokens不变，模型／新人工确认0。下一步优先将真实removeItem路径纳入源契约诊断、有边界通用修复及候选保护，并核对公开计数方法；不先改验收范围、不全局替换helper、不直接付费复跑。

2026-11-15：原生filter方法闭环完成，见 `data/experiments/analysis/formal_30_v4_filter_methods_v1_20261115/REPORT.md`。源码驱动通用repair规则恢复removeItem完整filter／根提交／标记／通知链和公开dayCount计数，检测、repair前后处理、repair Prompt与独立候选门同步；生成／服务器Prompt不改。只两个公开方法体改变，不全局改helper，不豁免旧阻断；新检测使输入2→4条，修复后仍2条且整体失败。22组函数层对照及原生稀疏删除／公开计数验证通过，默认轻量DOM相似度1、TED0，非人工或浏览器验收。补齐事件转发新增的同事务组合，保留悬空目标调用拒绝边界；探针、旧集成和首个261项260通过的测试构造失败全部留档，修正后重新启动16套件4进程综合回归261/261通过（444.319秒），32个相关文件指纹稳定，不是拼接单项复测或全仓库测试。30项规则清查仅Trip命中，原24通过件无新规则诊断且产物不改写；原24/30、6失败、1,821,544 tokens不回填，模型／新增人工确认0。Notebook只追加并保留旧117单元；下一步分别处理剩余共享写入通知和公开动态setter源契约，异常求值阶段风险仍保留，不直接付费复跑或进入独立测试。

2026-11-15：动态setter审查及校验／候选门加固完成，见 `data/experiments/analysis/formal_30_v4_dynamic_setter_guard_v1_20261115/REPORT.md`。不是setter迁移修复：当前Trip候选代码不改，旧两条阻断保留。15类输入、6种内存提案证明常见补法不足以保证任意公开键契约；五个可调用提案旧版能清掉接口诊断但整组件仍失败，新版新增source_dynamic_assignment_unproven并独立拒绝遗漏／伪造报告。仅共享方法检测、repair调度候选门与repair Prompt三个既有生产文件改变，无自动setter改写、生成／服务器Prompt或兼容层新增。新启动17套件4进程综合273/273通过（516.458秒），35个相关文件指纹稳定。30项静态清查22项有动态契约、21项可调用但未证明（19项历史通过），不是21个已证业务缺陷或新批次分数；旧24/30与tokens不回填。Notebook追加保留旧119单元，模型／新人工确认0。实际可达调用新协议或保留任意公开键契约的选择尚待用户答复；在此之前不缩范围，不直接复跑，不豁免共享通知及异常阶段风险。

2026-11-15（范围答复）：用户明确选择“仍保留任意公开键契约并继续阻断”。不采用六个源码可达根键的缩范围协议，不将局部投影提升为任意接口证明；保留缺失／未证明诊断、共享通知及异常阶段风险，当前Trip候选仍失败。本次只是范围决定记录，不是人工功能通过；生产代码、Prompt、产物与分数不改，无新测试campaign或模型调用。上段及封存包中的待答复状态作为历史保留，本追加决定供后续使用；继续在既有源码迁移范围内寻找可证明修复，不新增provider、互操作或调用方协议。

2026-11-15（论文收尾审查）：已按选题报告形成14项要求／实现／证据差距及S1—S5有限收尾计划，见 `docs/paper/论文实验收尾计划_20261115.md` 与 `data/experiments/analysis/thesis_closeout_audit_v1_20261115/REPORT.md`。新只读AST审计核实21项均为同一动态路径写入方法（简单7／中等10／复杂4），另1项缺接口；引用旧封存方法级反例，不冒充21个新的整组件原生／浏览器实测，任意公开键契约及诊断不豁免。截图与image_diff工具均0字节、当前visual_eval为DOM路径，像素／计算样式证据须补齐。11项新增审计测试通过，前273项未重跑但35个既有相关实现／测试和人工页指纹不变；未修改生产规则、Prompt、产物、分数或既有封存包。Notebook仅追加保留旧123单元；模型／新人工／浏览器均0。本计划不是新冻结协议：先做动态接口／通知／异常阶段有边界修复或明确未解决结论，再校准视觉交互、冻结完整回归、做公平对比并并行写作；开题未验证目标如实披露，工具／训练路线差异与导师确认，不额外扩功能或无限复跑。

2026-11-15（动态接口可行性）：已用冻结Trip原生Vue／San未挂载实例验证data=null／数字／对象／强制转换键及声明根正对照，见 `data/experiments/analysis/formal_30_v4_dynamic_setter_feasibility_v1_20261115/REPORT.md`。源公开data赋值后真实updateBudget与$watch正常；目标保留San data则公开赋值不等价，覆盖则业务更新与watch均TypeError，拒绝键则改变源成功行为。结论仅在“同一直接公开实例／任意键／标准San data存储／无门面、拦截兼容层或新协议”组合下不支持并继续阻断，不声称其他架构全部不可能。没有自动setter恢复，也没有新生产错误码或调度跳过逻辑；生产规则、Prompt及产物不改。新增原生11项、既有保护12项及收尾审计11项共34项定向测试通过，非全仓库或273项综合campaign；38个既有相关文件和人工页指纹不变，Notebook只追加保留旧125单元。动态接口分支先按有条件能力边界收束，任意键契约不缩小，下一项转向共享通知和异常阶段；旧24/30、两条Trip阻断和其余风险保留，无模型／新人工／浏览器／服务器／commit或push。

2026-11-15（共享通知与异常阶段）：新原生探针及15项审计测试确认普通moveItem五组状态／事件／身份投影仍一致，额外外部深同步观察者仍Vue3次／San1次；不升级为源SFC新增必需功能，也不豁免旧诊断。深克隆破坏共享／嵌套身份；嵌套set或浅发布虽3次回调但前两次根身份不等，浅发布原位还多回调；force原始变更3次而watch仍1次。days洞／null／undefined下源构造完成但首次getter读抛TypeError、随后可恢复；San构造提前抛错且inited未进入；吞错返回空值和删除computed都不作为修复。详见 `data/experiments/analysis/formal_30_v4_notification_exception_audit_v1_20261115/REPORT.md`。本步是未解决边界的原生审查，不是通用不可能证明或修复完成；生产规则／Prompt／产物和范围不改，无新错误码或提案生产准入运行。15+17+16+11共59项相关测试分别执行通过，非273项综合或全仓库；41个既有相关实现／测试及人工页指纹不变，Notebook只追加保留前127单元，旧24/30与tokens不回填。动态键继续阻断，静态旧诊断保留（本步未新跑ValidateStage），其数量不代表全部实际风险。S1本分支先以明确风险结论收束，下一项S2开发受控浏览器／像素评估器并做已知差异校准，不直接付费复跑；无模型／服务器／浏览器／新人工／commit或push。

2026-11-15（S2受控视觉校准）：新增隔离浏览器／PNG像素与SSIM／21项计算样式及关键矩形／差异图入口，见 `docs/ir-design/controlled-browser-pixel-v1.md` 和 `data/experiments/analysis/controlled_browser_pixel_v1_20261115/REPORT.md`。固定视口／主题／语言时区／时间随机输入、显式ready与二次截图；两次真实Edge运行各9页7比较、9项控制成立，8个非持续变化页跨启动截图SHA一致。原生Vue／San小样例与同图无差，颜色／padding反例检出，报错／网络拒绝／不稳定自比较阻断；另5种失败路径正确拒绝。新27+旧校准17+通知异常15共59项相关测试通过，非273项或全仓库；53个既有相关文件及3个人工配置不变，旧空工具与生产DOM评估路径不改。首轮连接／清理失败和测试证据路径setup失败均留档，只清理自己专用临时profile。无新依赖安装、无模型／新人工／生产规则或Prompt更改，旧分数不回填，Notebook仅追加保留旧129单元。此步仅S2基础设施校准，非完整产物或交互验收；尚需真实冻结组件页面适配、分层开发样例、长页面资源策略与预先冻结的生产阈值／反馈协议，不能直接付费跑新批次或进入独立测试。字体／浏览器记录指纹但未vendoring，任意公开键及通知／异常边界继续阻断或保留风险，不新增互操作／provider。

2026-11-15（S2真实冻结组件页面）：新增CommonJS Options API／静态本地依赖SFC封装及独立v2完整页面截图，按原顺序每层首项VolumeControl／BatchRenamer／AnalyticsDashboard，默认与显式props共5场景10页；完整模板、内联子组件、默认值及scoped边界保留，见 `data/experiments/analysis/frozen_component_browser_v1_20261115/REPORT.md` 与 `docs/ir-design/frozen-component-browser-v1.md`。4个简单／中等静态场景像素及样式完全一致；复杂页双方7子组件、30图点及15活动加载且观察数据一致，源有10条重复key警告，完整页面1326／1625高和7项关键矩形差，继续阻断，不吞警告、不缩放编指标、不算目标新执行失败或新的4/5迁移率。首轮PNG相同但观测不等的捕获问题已保留；固定scrollbar-gutter并补重复详情，内存改auto反事实再现宽1265→1280，最终两次10页截图SHA／业务观察／样式一致，非组件业务补丁。9项合成原生依赖／scoped隔离／完整截图／失败边界成立；39+27+12共78项定向测试通过，另扩展测试过早读取未完成repeat的setup失败保留，不是旧273项或全仓库。58个既有相关文件、3个人工配置、6个冻结输入和旧75payload保持，Notebook追加保留旧131单元；旧分数、Prompt、规则及产物不改，无依赖安装／模型／新人工／commit或push。仍是S2开发校准：仅普通SFC子集与受限资源／像素预算，未证明有存储组件逐页隔离或完整交互；字体／浏览器未vendoring。下一项需区分源oracle／目标差异／设施阻断的机器反馈，补存储／状态策略，再冻结生产阈值协议及接入repair，不直接付费全量复跑或进入独立测试；任意公开键和通知／异常边界继续保留。

2026-11-15（S2机器反馈分流）：新增独立browser_feedback_v1及冻结回放／离线Prompt预览接口，见 `data/experiments/analysis/browser_feedback_routing_v1_20261115/REPORT.md` 与 `docs/ir-design/browser-feedback-routing-v1.md`。source_oracle／target_runtime／visual_observation／evaluation_integrity分开，旧130payload核验后corrected／repeat前4项仅视觉一致、Analytics源基准复核；10条源诊断不算San错误，7项矩形与1326／1625高度差保留，真实目标修复预览0。未知来源、不完整／不稳定捕获、传输／清理问题不触发代码修复，不信调用方成功／clean／stable／路由标志；每次预览重读固定证据并绑定当前源／目标代码和props，合成正向调用既有PromptBuilder保留动态公开键诊断及旧目标问题，不改state或候选门。所有自动dispatch恒false，尚未生产接入；未改旧visual_eval、Prompt文件、调度器／规则及产物。50+39+34+12共135项定向测试通过，非全仓库或273项campaign；旧repair测试用stub，合成PNG／JSON不作新浏览器事实。65个旧相关文件、3个人工配置、6个冻结输入保持，Notebook仅追加保留旧133单元，旧分数不回填，无新模型／浏览器／服务器／人工／依赖／commit或push。旧v2事件只按唯一合法页栈帧保守归属，仍缺原生session/page登记及实际端口身份核验；不独立重算像素／SSIM，哈希不是未知生产者认证。下一步补原生归属与逐页持久化隔离，再定错误级别／状态／阈值并冻结生产协议后接入批处理；源oracle警告不擅自吞掉或改源，任意公开键和通知／异常风险不解除，不直接付费全30或独立测试，不新增互操作／provider。

2026-11-15（S2原生来源与逐页存储）：新增独立v3评估器及session登记，真实run/origin/context/target/session/frame绑定、两次原生target/frame响应、事件所有者和每页精确GET请求保护；每页独立BrowserContext，关闭后销毁。见 `data/experiments/analysis/browser_session_isolation_v1_20261115/REPORT.md` 与 `docs/ir-design/browser-session-isolation-v1.md`。两次各6页15项控制确认localStorage／sessionStorage／Cookie／IndexedDB／Cache Storage跨页隔离而同页刷新保留；未知／冲突／延迟来源仍复核。旧冻结3组件5静态场景10页重放13项检查成立，HTML／截图／业务观察不变，4项仅视觉一致，Analytics10条源诊断原生归Vue，7项矩形及1326／1625高度差仍保留。首次受限环境GPU失败、报告缺字段和CSP提前拦截导致反例不成立均保留；正常本机权限重跑，不禁用浏览器沙箱，只清理任务临时profile。新53+旧50+39+34+12共188项定向测试通过，非全仓库或273项campaign；69个旧相关文件、3个人工配置、6个冻结输入和旧21payload不变，Notebook只追加保留旧135单元，旧24/30及tokens不回填。schema3尚无封存反馈适配，旧v1桥仍只支持schema2，不强行接生产；下一项先做原生封存校验／分流适配，再定错误级别、状态／阈值和冻结生产协议。本步无模型／新人工／依赖安装／commit／push，不改生产Prompt／规则／调度或组件。仅证明空初态五类存储控制，不外推预置状态／登录／权限／service worker／全部浏览器状态；任意公开键及通知／异常边界继续保留，不新增互操作或业务协议，不直接付费全量或独立测试。

2026-11-15（S2原生反馈适配）：新增native_browser_feedback_v1独立核验schema3，不降级旧格式、不改旧反馈器／浏览器。外部固定seal与独立组件manifest、run/origin/context/target/session/frame／executionContext、诊断副本／序列、CDP响应／处置、截图及固定环境、21项样式加rect完整性均核验；未知／冲突／设施问题优先复核，不按报错文字归属、不信成功旗标。见 `data/experiments/analysis/native_browser_feedback_v1_20261115/REPORT.md` 和 `docs/ir-design/native-browser-feedback-v1.md`。6组旧封存记录三次离线转换，真实5静态场景仍4项仅视觉一致＋Analytics源基准复核，10条源诊断、7项矩形及1326／1625高度差保留，真实目标修复预览0；源错误不送San修复。离线预览重读证据并严格绑定当前源码与props，合成正向用既有PromptBuilder保留动态键及旧目标问题、不改state；目前单模块可预览，多模块自动依赖重绑定前拒绝，不要求新业务材料。新90（83合成／7旧记录）＋旧53／50／39／34／12共278项定向测试通过，非全仓库或旧273项campaign；75个旧相关文件、3个人工配置、6个冻结输入及旧96payload不变，Notebook追加保留旧137单元与metadata，旧24/30及tokens不回填。未改生产Prompt／规则／调度／组件，自动dispatch与语义门绕过均false，无新浏览器／模型／人工／依赖／UI／commit／push。PNG未独立解码／重算SSIM；CDP trace缺完整params/result与统一诊断处置时序，不能认证任意生产者，原疑点不清除。下一项先明确错误级别、源oracle警告处置、状态／交互与阈值，审核冻结受限生产协议后才接批处理；完整SSM／当前依赖图与任意公开键、通知／异常风险仍保留，不扩互操作或业务协议，不直接付费全量／独立测试。

2026-11-15（S2接入口径草案）：已形成 `data/experiments/protocols/native_browser_admission_v1_draft_20261115/PROTOCOL.md`、机器配置、30项主Vue／历史SHA清单与场景计划及只读审查入口；见 `data/experiments/analysis/native_browser_admission_draft_v1_20261115/REPORT.md`。状态review_required、未批准／未正式冻结／生产未就绪，封存草案证据不等于协议批准。建议待用户审核：严格像素0／SSIM≥0.999999999／关键样式矩形差0，源error/warning继续阻断不吞警告，旧DOM0.95/0.8单列；not_run／缺证据不通过，任意键及通知／异常风险不豁免。30个主Vue与历史冻结一致，每层10；已有仍仅3组件5静态校准，拟8原生交互本步执行0，其余27项需映射，不以元数据标签或San单端人工候选冒充双端验收。六项待办包括用户审核、生产集成、全量场景、原生交互执行控制、当前依赖重绑定及新全批模型代码预算冻结；未来建议3次LLM repair但不在这里授权费用。新46+旧90+53+12共201项定向测试通过，非全仓库／上轮278或旧273campaign；79个旧相关文件、3个人工配置、4份参考、旧28payload不变，30对主源码核验，Notebook只追加保留旧139单元及metadata，旧24/30与tokens不回填，新比例null。未改生产Prompt／规则／调度／评估器／组件，无新模型／浏览器／服务器／人工／依赖／UI／commit／push。下一步先请用户确认口径，随后补工程缺口并另立正式冻结协议，不直接付费全量／独立测试，不新增互操作或业务调用协议。

2026-11-15（S2口径确认与原生音量交互）：用户确认严格视觉阈值及源warning阻断，另存 `data/experiments/protocols/native_browser_criteria_adopted_20261115/approval.json`，旧待审草案不改；确认标准不等于生产就绪或模型授权。见 `data/experiments/analysis/native_interaction_volume_v1_20261115/REPORT.md`。新增有界原生输入/被动事件观察与schema4分步截图，不改旧schema3及生产生成/repair Prompt、规则、分派。冻结VolumeControl默认45下Home→End→Home和静音→恢复两个场景，4原生页、10次输入，7对画面零像素/样式/矩形差，14单端状态/事件/DOM检查一致，最终28个DOM事件isTrusted为true；不冒充旧草案输入60场景或拖拽。另5对合成控制验证正常通过、故意差异/源码警告/缺失/禁用目标不通过，初始证据与not_run保留；两次启动共14页，18个可算比较PNG重算一致。最终224项定向回归通过（23+46+90+53+12，非全仓库），原84相关文件、3人工配置、4参考、6冻结SFC、30对主Vue及旧8payload不变，Notebook追加保留141单元与metadata；旧24/30与token1,821,544不变。source_dynamic_assignment_unproven及任意公开键、通知/异常边界不豁免，仍非组件综合通过；其他场景、全30映射、依赖重绑定、schema4生产反馈和全批冻结待办。无LLM/新人工组件通过/commit/push，不直接付费全量或独立测试，不新增互操作能力。

2026-11-15（S2重命名原生交互）：BatchRenamer 三场景校准完成，见 `data/experiments/analysis/native_interaction_renamer_v1_20261115/REPORT.md`。另建 v2 原生 Ctrl+A/Input.insertText 动作、被动 payload 根身份观察及可选 DOM 集合，旧实现不改；schema5 不伪装接入旧反馈/生产。冻结默认三文件，编辑 img/3、隐藏恢复预览、编辑后应用，共6页14次原生输入，10对画面零像素/关键样式/矩形差，20单端语义检查一致；52个DOM事件isTrusted，apply载荷和currentFiles在发出时引用不同。另4对8页控制确认正常编辑通过、故意输出错误/源码警告/只读输入不通过，保留初始证据和not_run；20个可比PNG指标独立重算一致。最终249项定向测试通过（25+23+46+90+53+12，非全仓库），93旧相关文件、3人工配置、4参考、6冻结SFC、30对主Vue、上步105payload与closeout不变；Notebook只追加保留143单元与metadata，旧24/30及token1,821,544不变。仅默认可达交互校准，不豁免任意公开键、通知/异常等语义；Analytics源警告仍阻断，下一步核查其源端基准/警告后再推进其余场景，不吞警告或暗改源码。生产接入、全量场景/依赖绑定/全批冻结仍待办，无LLM/新增人工通过/commit/push，不新增互操作或业务材料要求。

2026-11-15（Analytics源基准审查）：见 `data/experiments/analysis/analytics_source_oracle_audit_v1_20261115/REPORT.md`。确证源TrendChart第148/173行两组svg直接兄弟g分别用1–5及0–29数字key，规范化VNode重叠1–5；完整源重放仍10条重复键警告，不能归为San生成/repair问题或吞掉。1/2/7/30/90点原模板与仅key命名空间的机制控制显示原警告0/2/10/10/10、控制均0且画面不变；控制不写回、不当源勘误或真实交互验收。最终12原生页身份/处置完整，42诊断归属明确，5对PNG指标独立重算一致；全源/目标业务与截图SHA同旧记录，1326/1625高度与7项矩形差仍保留，未归因给key或宣称消除。首次新观察语法与单点零面积polyline关键选择失败已单独seal保留，只修诊断夹具后新目录重跑；不改冻结源码、旧渲染器/Prompt/规则/阈值/分派。205项定向测试通过（16+46+90+53，非全仓库或上步249campaign）；100旧文件、3人工配置、4参考、6冻结SFC、30对主Vue、上步114payload及旧原生96payload不变。Notebook只追加保留145单元和metadata，旧24/30与token1,821,544不回填。Analytics交互仍0、源oracle继续阻断、公开键/通知/异常不豁免；下一步需用户决定是否另建只改两处key的独立源码勘误版本，批准后重建基准/绑定，再独立查布局/交互，不暗改源或排除样本。无LLM/新人工通过/commit/push，不扩互操作或业务输入要求。
