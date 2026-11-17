# 模块化系统开发记录 2026 年 11 月 16 日

## 2026-11-17：纠正范围偏离，撤销规则生成，只放行动态 setter 预检查

用户明确指出：此前要求的是解除 `setValue` 中 `this[key] = value` 的模型前阻断，而非新增确定性源到 San 转换。此前 v2 接入偏离该要求，本次撤销，删除 `stages/business.py` 和主链内计划生成、专用静态绑定校验、`business_rule_checks_failed` 停止分支。现有生成 Prompt、原静态校验、浏览器评估、规则修复／模型修复、候选复测及回退均保留。

预检查只对 `source_dynamic_key_contract_unsupported` 放行，继续模型配置检查；其他源码语法、依赖及配置错误仍阻断。不改 Vue、不改键域、不保证任意公开键完全等价，不豁免生成结果质量。新任务范围 `san-supported-migration-v3`，初始来源 `generation` 且有模型收据；旧 v2 任务 dc9c942c547745ed989bc3db583af744 和封存证据不改写，也不算模型迁移效果。

`runtime/san_business_v1` 与 `research/` 仅离线保留，不在生产绑定或主链中使用。指南删除必填组件动作 JSON／零调用正常生成等当前操作说明；历史规则报告在前端明确标记已撤销来源。真实密钥、用户配置、任务库及队列均不修改，不自动产生付费调用。

本次检查：主链 102 项、动态 setter 模型准入 7 项、支持范围 5 项、原实验复用 5 项、研究契约保护 7 项通过；前端 22 项及正式构建通过。仓库外副本未复制业务实例运行时，仍完成原模型响应夹具链；原复杂源码在生成后主动暂停，只验证入模，不声称迁移质量通过。旧 79 个封存 payload 不变。结果及口径见 [撤销记录](docs/verification/2026-11-17_dynamic_setter_model_admission_v1/README.md)。

## 2026-11-17：现有复杂组件动态 setter 的有限生产接入

用户在 CapacityPlanningBoard 仍被阻断后明确要求补齐现有复杂组件。旧任务 b05e37a0254b4f5583d9c30c0f1bd3bb 及原源码 f84efcfbc0b57731e358ff24264f6600a3a64fa58e725290f77799f4e7ac1d02 保留；未修改 Vue、用户 TOML、实际库／队列或模型密钥。

新增 `stages/business.py`，将此前业务实例运行时限定为可规范化验证的单组件规则路径接入原 LangGraph。源码 Options／方法体自动保留、模板转成 San、源／SSM／运行时指纹绑定，实际目标仍由 San 渲染，不按组件名或固定键放行。普通生成 Prompt、修复 Prompt、规则调度及 engine 原件不变。新范围 `san-supported-migration-v2`，产物来源 `source_ast_rule_generation`，0 模型调用正常；规则路径检查失败以 business_rule_checks_failed 停止，不反复交给模型重写内联运行时。

真实反例与修正：方法体中的响应式依赖未进入循环热区，导致选中颜色滞后；San 的旧 option.value 兼容行为增加源端没有的属性。已修正私有表达式依赖传播及实际 option 属性，未给评估器添加忽略差异。完整任意公开键／所有公共 API 仍不宣称完成。

CapacityPlanningBoard 在真实整图和仓库外独立副本中六维通过，9 步交互通过，源文件哈希保持；离线重放结构／DOM 相似度 1、UI 100%、最终截图 SSIM 1／差异像素 0。外部调用 Symbol、字面点号键、data／watch／dispose／attach、一次键转换及异常身份均在生产导出与 Vue 对照。其他 22 个动态 setter complex 只做了编译盘点：总计 17 可编译、6 阻断，不能当成迁移通过。

本轮相关测试：主链 102、旧代理 41、业务运行时 13、契约保护 7、新范围 5、生产专项 5、原实现复用 5 均通过，前端 22 项和构建通过；末次诊断提示修改后再次跑生产专项及公开键 11 项。原生产“永不变化”测试的原件封存后，改为核验旧 payload／研究实现和显式版本变化，不跳过行为断言。真实云模型／上传／训练调用均 0；普通模型链的两次 exchange 是独立验证中的明确夹具，不混作复杂组件规则生成。

说明见 [DYNAMIC_SETTER_PRODUCTION_V1](docs/DYNAMIC_SETTER_PRODUCTION_V1.md)，证据位于 docs/verification/2026-11-17_dynamic_setter_production_v1，另建 2026-11-17_dynamic_setter_production_v1.ipynb。用户应重启 API／Worker、新建原 CapacityPlanningBoard 任务并独立人工确认，不恢复旧任务，不据本例宣称全批或独立测试通过。

## 2026-11-17：收敛到明确支持范围的生产迁移闭环

用户确认优先生产闭环，不再以完整任意公开实例兼容为本轮前提。保留唯一 LangGraph 主链及内置实验算法，不接入或删除代理研究，不放行仍不支持的动态键源码。新增服务端 `san-supported-migration-v1` 范围快照，随新任务参与请求哈希并进入报告；readiness／前端展示范围，旧任务不追溯改判。详见 [交付范围](docs/PRODUCTION_CLOSURE_V1.md)。本轮不修改用户 TOML、密钥、实际数据库／队列，也不启动付费模型、LangSmith 上传或训练。

验证完成：主链 102 项，新范围 5 项，原实现复用对照 5 项，旧契约保护 7 项，前端 22 项及构建均通过；仓库外独立副本以真实 AST／SSM／LangGraph／Puppeteer 完成修复候选、六维评估、下载和零调用阻断验证。模型为明确的响应夹具（两次 exchange），真实云模型调用 0。保存 [结果与指纹](docs/verification/2026-11-17_supported_production_closure_v1/README.md)，另建 2026-11-17_supported_production_closure_v1.ipynb，不覆盖已打开的旧 Notebook。尚待用户新建一条真实模型任务和独立人工验收，不能据工程检查声称论文通过率或完整兼容已达成。

## 2026-11-17：继续补自动内联树／父事件／错误路由及读取时序（仍未完整发布）

新增 runtime/san_business_v1/template.cjs、tree.cjs、events.cjs。静态 const 内联 Options／模板／注册从源 AST 直接编译为 San 树，拒绝无法解析的组件及私有子依赖；不是手工可信父子 metadata。支持已测的多参数／数组／once 事件、渲染时成员引用快照、严格函数接收者、动态替换回调数组、父 props／inheritAttrs=false 动态 attrs、连字符 attrs 原名、ref／parent／root／options 身份及祖先捕获。无 Vue 组件／渲染器；Node 只解析。

实际中间反例包括 this 严格身份比较被误报逃逸、data-note 变成 dataNote、原生局部更新漏读 getter、未用字段误触发整组件更新、隐藏分支旧读取、方法覆盖立即替换已安装事件、可选成员调用导致严格函数 this 指向桥接对象。分别修 AST 检查、源属性名映射、惰性通知／实际渲染读依赖、事件渲染快照与统一错误分派。source 自动编译探针新增 getter／隐藏分支／未用字段，值探针 12 类值＋带副作用 toString；单根 pre watcher 递归按原版本 101 次回调、count 102、nextTick 拒绝且不提交待渲染 DOM。有限证明不推广为任意全局时序等价。

本轮最终新专项 **20 项通过（32.673 秒）**，旧 v1–v7 **41 项通过（63.472 秒）**，默认生产边界 **11 项通过（15.044 秒）**；同一实现指纹下六份探针及冻结 ProductFilterPanel **11 步交互通过**，UI 100%、SSIM 1、不同像素 0。结果封存到 docs/verification/2026-11-17_san_business_instance_v1_tree_partial；首轮 47 payload、旧 v1–v7、原185文件生产基线不变，Notebook 只追加新记录。

完整契约仍未完成：slots、动态／函数／循环 ref、自动 attrs 透传、跨 root／复杂异步递归、广义模板及副作用顺序、生成／校验／修复／候选门集成未闭合；research v7 的 keyed 内存候选也尚未进入新导出，不能把其4/4套用给新组件树。保持 full_contract_complete=false、production_admission_eligible=false 和默认源阻断。无模型、LangSmith、训练、实际库／队列写入、commit/push；目前不要求用户重启或付费复跑。

## 2026-11-17：San 业务契约、可执行源编译与冻结样本交互重放（部分实现）

用户确认保持 San 迁移目标，不再复刻 Vue 私有实例／vnode 图；另立 san-business-instance-v1，不回写 v1–v7 失败、分母或费用。任意字符串／Symbol 业务键、ToPropertyKey、对象／ref／别名和公开功能仍需实现或明确阻断，不能缩成固定六键或简单值。契约与实际进度分别见 docs/SAN_BUSINESS_INSTANCE_CONTRACT_V1.md、docs/SAN_BUSINESS_RUNTIME_V1.md。

新增 runtime/san_business_v1：源 Options／AST 自动编译脚本、refs 和 DOM 策略，真正 San constructor 中隔离业务与原生 receiver；data() 原对象、简单父 props／watch／hook DOM 顺序、事件配置回调／once／model、forceUpdate、卸载后 watcher、跨导出共享内核均有实际对照。内嵌独立 @vue/reactivity／@vue/shared 3.5.45，不加载 Vue 组件／渲染器；不是零 Vue 依赖。修正默认工厂输入、冻结空 data、显示与 Symbol input、连字符 props／声明 emits 与 attrs 分类及 Windows 导出字节指纹；未实现根 ref／vnode 回调和原生父事件路由明确拒绝。

保留实际中间失败：初始 DOM 属性／key 表达不同，早期 Windows 换行导致 manifest 与导出字节不一致，卸载 watcher 错误地继续回调，新增 attrs 对照未归一化 display-name／误删 onClick／错误保留 key。现分别修实际 DOM、经独立核实后的模板身份映射、字节写入、inactive scope 和输入分类。不降低旧阈值或修改原始浏览器证据，早期观察不冒充最终源码绑定。

最终本轮新专项 **18 项通过（37.111 秒）**，旧代理 v1–v7 **41 项通过（76.907 秒）**，默认生产公开键专项 **11 项通过（19.396 秒）**；以封存 unittest 日志时间为准，summary 中 subprocess wall time 包含启动开销，不混为同一计时。新报告分别包含 92 个有限业务案例、自动源编译浏览器对照、5 个公共 API／父子夹具、12 类值和 4 项共享／拒绝控制，不累加为迁移成功样本。

冻结 ProductFilterPanel 的原 source／第 3 版 San 模板离线派生新产物，实际执行 11 步搜索／分类／库存／排序／价格／选中／清空／空结果；初始及每步 DOM／样式／控件状态一致，初始结构及原始 DOM 相似度 1、UI 100%、SSIM 1、不同像素 0。静态范围仅为 canonical source Options／receiver 绑定，不冒称旧完整语义分析器已适配。scripts/verify_san_business.py 可重现本轮；最终源码／输入／测试／浏览器／截图／SHA256SUMS 封存至 docs/verification/2026-11-17_san_business_instance_v1_partial，旧封存及 185 文件生产基线保持。

**完整修复及生产接入尚未完成**：默认生成／验证／修复／候选门／API／前端未导入新模块，自动组件树、祖先错误捕获、slots／动态 attrs／refs、复杂父事件和递归／副作用顺序仍需闭合。full_contract_complete=false、production_admission_eligible=false，旧 source_dynamic_key_contract_unsupported 保持。无模型／LangSmith／训练／实际业务库或队列写入、commit/push；无需重启或付费复跑。Notebook 仅追加两格，原 21 格内容不变。

## 2026-11-17：代理研究 v7 修复单元素根 keyed 组件重建（未接入生产）

继续用户授权，定位固定 San 3.15.6 的 ForNode._updateArray：仅 nodeType=ELEM 允许移动，组件不在 LIS 静止项时进入销毁／重建。新增独立 research/public_instance_v7，按精确上游版本及源码 SHA-256 生成内存候选，只对已检查的同步、单元素根组件启用原移动路径。不改固定 engine、v1 至 v6、封存、生产 Prompt／规则／配置或源 Vue，不按组件名特判。

相同有限树场景旧 v6 3/4、候选 v7 **4/4**；无代理原生对照也由 bSame=false、count 丢失变为保留实例／count。另有原 Vue／原 San／候选 San 三页对照，13 次连续更新验证实例、状态、原生 props／index／事件和普通元素路径，2 项限定案例一致。9 项实际拒绝边界覆盖多根／条件根／组件根／过渡及不支持 key；拒绝时未移动／销毁旧实例，但不承诺回滚已经设置的源 Data。

首轮扩展原生探针整体失败，逐步字段均一致，差异仅最后 raw San 整树 dispose 顺序；最终分开列表更新案例与最终销毁观察并保留 native_disposal_order.equal=false。该 native 差异不由 keyed 补丁修复，owner 桥接后的实际卸载顺序继续由树探针验证。不将修改探针记录等同为修复了原生销毁。

候选下既有 root 6 项、调度 8 项、控件及每页 7 条 watcher 保持；非 DOM 94 项／写入 5 项和 8 控制／owner 10 控制保持，非 DOM 仍使用原 San 及明确屏障测试替代。最终合并 **41 项通过，110.122 秒**；生产专项 **11 项通过，27.472 秒**。首轮专项 7 项中 1 项失败、43.116 秒为中间结果不累计。九报告＋十一 cjs＋一测试共 **21 payload** 封存至 docs/verification/2026-11-17_public_instance_proxy_v7。详见 docs/PUBLIC_INSTANCE_PROXY_V7.md。

代理动态 child props、完整私有图／初始化／异常／过渡及真实 SSM 编译／导出／加载仍未闭合；下一步先补动态 child props 的真实父子同步反例。arbitrary_public_key_contract_complete=false、production_admission_eligible=false 和生产契约阻断不变。不把研究循环 key 边界当成缩减 setValue 任意公开键的授权。无模型／LangSmith／训练／实际库或队列写入／commit/push，无需重启或付费复跑。

## 2026-11-17：代理原型 v6 父子 owner／循环作用域（3/4，keyed 未解决）

新增 research/public_instance_v6，沿授权先验证，不改旧版本／封存和生产。实际 San runtime.owner 对应已登记父 owner，逻辑 parent/root 指向真实记录，子 scope 独立；family nextTick 等待成员队列。真实 DocumentFragment 初始构建与顺序批量清理使挂载／卸载 DOM 可见性、顺序一致。条件移除后的 unmounted 排到父 post 队列，不同根互不清理。

四个有限树场景旧 v5 0/4、新 v6 **3/4**，**keyed 重排仍失败**：a/b/c 的 count 均为 1，改为 c/b 时 San 把本应保留的 b 销毁并重建为 count=0。新增不含 Proxy／响应式内核／owner 的原生 San 3.15.6 对照也重现 bSame=false、bDisposed=true、c:1/b:0；当前定位到原生更新路径，尚未定位具体算法行。不靠改 Prompt、忽略 key、仅比 DOM 或回填状态判通过，也未改固定引擎。旧 0/4 是新增树证据，不是旧迁移率被改为 0%。

首轮树对照 2/4，修正真实挂载可见性和兄弟卸载顺序后 3/4；keyed 失败保留。已有 root 6 项、调度 8 项、控件每页 7 条 watcher 回归保持，非 DOM 94 项、写入 5 项／8 控制及 root 10 控制保持，屏障替代继续明确声明。目标仍有 VueReactivity 依赖但无 Vue 组件运行时。

最终合并工程检查 **34 项通过（93.577 秒，旧 28 项＋新增 6 项）**，其中包含确认 keyed 失败仍被识别的反例，**不等于树行为全部通过**；生产专项 **11 项通过（30.039 秒）**。专项 6 项 20.819 秒为中间验证不累计。八份报告与十份源码／测试共 **18 payload** 封存至 docs/verification/2026-11-17_public_instance_proxy_v6。没有全系统／30 组件／模型重跑或论文新增样本。

优先下一步定位修复已冻结的原生 keyed 差异；动态子 props、任意深度／循环／key、跨 root 调度、私有实例图和真实编译／加载仍未完成。arbitrary_public_key_contract_complete=false、production_admission_eligible=false，生产阻断不变。详见 docs/PUBLIC_INSTANCE_PROXY_V6.md。无模型、LangSmith、训练、实际库／队列写入、commit/push，无需重启或付费复跑。

## 2026-11-17：公开实例代理 v5 root owner 生命周期与清理（未接入）

继续先兼容验证再接入的授权。v4 没有 owner hooks，直接原生 dispose 会绕过代理句柄清理；新增 research/public_instance_v5，以每实例 owner helper 连接 beforeMount/mounted、beforeUpdate/updated、beforeUnmount/unmounted。hook 的业务 this 与原生 receiver 分开，hook 内 $watch 归属 owner，直接原生销毁、句柄销毁都停止 scope 并 cleanup；beforeUnmount 在旧 DOM／活 scope，unmounted 在 DOM 已移除／scope 已停时执行，之后才标 isUnmounted。保留卸载后的 $el 引用，不伪造 vnode。旧代码／封存、生产链、Prompt、阈值、配置和源组件不改。

新增有限浏览器场景旧 v4 **0/6**、v5 **6/6** 一致；0/6 只是新增 owner 场景此前未连接，不改写旧 v4 测试或论文迁移率。另有 owner 已连接的 **8 项** 实际调度、控件及每页 **7 条** watcher 回调回归，**10 项** owner 边界控制通过。非 DOM 原生 94 项、写入 5 项及 8 项控制保持，屏障测试替代继续明确声明，实际 DOM 证据来自隔离 Edge；目标仍有独立 VueReactivity 依赖但没有 Vue 组件运行时。

最终 v1 至 v5 合并 **28 项通过（70.162 秒，含旧 22 项及新增 6 项）**；生产公开键／控件专项 **11 项通过（25.828 秒）**。专项 6 项 19.309 秒、补指令防护前合并 28 项 65.115 秒为中间结果不累计。七份报告及九份源码／测试共 **16 payload** 封存至 docs/verification/2026-11-17_public_instance_proxy_v5，绑定最终代码，不作为论文新增迁移样本或全系统重跑。

实际修正：San dispose 内部调用 detach 被外部 detach 防护误挡，仅允许 unmounting 内部路径，外部 detach 仍拒绝；封存前补查真实 s-transition 指令防护并重跑。详见 docs/PUBLIC_INSTANCE_PROXY_V5.md。每实例保留 dispose／attach 幂等防护，不声称卸载后所有 wrapper 均恢复。

完整父子／循环作用域、初始化 hooks／组合式注入、过渡／异步卸载／祖先异常、私有实例图、所有调度交错／递归保护和真实 SSM 编译／加载仍未闭合。arbitrary_public_key_contract_complete=false、production_admission_eligible=false，生产阻断保持，不以 root 夹具范围缩小用户契约。无模型、LangSmith、训练、实际库／队列写入、commit 或 push，无需重启或付费复跑。

## 2026-11-17：公开实例代理 v4 渲染／nextTick 调度（未接入）

先以同一实际浏览器探针对旧 v3 复现：8 个有限场景只有 3 项一致，5 项不同，包括无 watcher／只有 pre watcher 时 tick 早于 DOM、回调读旧 DOM、post 侧写顺序及 Promise 身份。新增 research/public_instance_v4，以原生通知后的真实渲染完成标记、共享完成 Promise 及 post 分批处理修正；不改 v1/v2/v3 源码或封存，不改生产 Prompt、引擎、配置、源 Vue 和历史产物。

最终浏览器前后对照 **v3 3/8 一致、v4 8/8 一致**，无 warning/error；v4 实际控件两页也通过，仍各有 7 条实际 watcher 回调。非 DOM 原生 94 项、写入 5 项及 8 项控制保持。目标无 Vue 组件运行时但仍有显式 VueReactivity 依赖。卸载只验证取消 owner watch 及保留既有 tick 回调，不声称完整生命周期闭合。

Node 非 DOM 夹具新增调用原生 San 调度后打印结果不退出，本机源码选择未关闭的 MessageChannel；两次运行被中断，不算完成通过。v4 非 DOM 夹具显式改注入微任务屏障替代，报告记录 node_render_barrier_is_test_double=true；实际 DOM／San 调度结论全部由独立浏览器取得，生产与 engine 不改，也没有修改全局 MessageChannel。详见 docs/PUBLIC_INSTANCE_PROXY_V4.md。

最终 v1 至 v4 合并 **22 项通过（50.132 秒，含旧 17 项及新增 5 项）**；既有生产专项 **11 项通过（28.071 秒）**。中间 5 项 16.708／27.132 秒不累计。最终前后浏览器、控件和非 DOM 5 份报告及源码／测试 6 份共 **11 payload** 封存至 docs/verification/2026-11-17_public_instance_proxy_v4。没有全系统、30 样本或模型重跑，不计论文新增迁移样本。

完整私有图、父子／循环作用域、生命周期 hooks／异常／递归保护和真实编译／加载仍未闭合；v3 原生重入及事件口径差异保留。arbitrary_public_key_contract_complete=false、production_admission_eligible=false，生产阻断保持。无模型、LangSmith、训练、实际库／队列写入、commit 或 push，无需重启或付费复跑。

## 2026-11-17：公开实例代理 v3 嵌套控件写入（未接入）

继续用户授权的先兼容验证路径。本轮针对 v2 明确拒绝的原生 Data.set 嵌套写入，新增 research/public_instance_v3，不改 v1/v2 文件／封存，不改生产引擎、Prompt、配置、旧源码或费用。控件经同一源响应式状态写入，保留别名、数组项、ref 身份；按根合并镜像通知，支持已测 silent／silence／quiet／force 语义及调用方 option 身份。监听器回写不再在内部保护期间绕过源状态；缺失父对象和同步 watcher 内原生重入仍拒绝。

v3 重放原有 **94 个有限对照一致**，新增 **5 项** 嵌套写入对照和 **8 项** 控制成立。实际隔离 Edge 两页经输入、复选框开关、下拉选择和字面点号键输入后状态／DOM 一致，每页 **7 条** 实际同步 watcher 回调逐条一致；公开 data/watch/dispose 同名赋值不破坏内部句柄。目标无 Vue 组件运行时但仍显式使用独立 VueReactivity 内核。

最终 v1/v2/v3 合并 **17 项通过（21.334 秒，包含旧 13 项与本轮 4 项）**；既有生产公开键／控件 **11 项通过（24.760 秒）**。修正后专项 4 项 5.604 秒是中间结果，不累计。未全量重跑系统／30 组件或模型，不作为论文新增迁移样本。最终三份结果及五份源码／测试共 **8 payload** 封存至 docs/verification/2026-11-17_public_instance_proxy_v3，SHA-256 核验。

真实失败：初次普通权限启动浏览器等待超时；许可隔离浏览器中又发现源页三击未全选导致 staredited，补充实际状态诊断，明确 Ctrl+A 后重测通过。没有靠改源组件掩盖错误。详见 docs/PUBLIC_INSTANCE_PROXY_V3.md。

仍不承诺原生 San 嵌套 change 事件逐字节等价，使用根级失效通知；不是原子回滚事务。完整私有 vnode 图、生命周期／异常／作用域、development 内核限制、真实 SSM 编译／加载均未闭合。arbitrary_public_key_contract_complete=false、production_admission_eligible=false，生产阻断保持。没有模型、LangSmith、训练、实际库／队列写入、commit 或 push，无需重启或付费复跑。

## 2026-11-17：公开实例代理 v2 响应式与读取修复（未接入）

沿用户授权继续修复，不改 v1 原型／封存或生产链。新增 research/public_instance_v2，采用本目录已安装的独立 @vue/reactivity 3.5.45 内核，不含 Vue 组件／渲染器，但属于新增运行时依赖，不能称为完全无 Vue 依赖；无新下载安装或锁升级。修复对象／循环与共享引用／ref 身份、computed 缓存、实际 $watch 与根级显式记录错误策略，并建立真实逻辑 proxy/data/ctx 关系，不用 typeof 或伪造 vnode 宣称完整等价。

另修复“公开值已变、San DOM 未变”：分开 San 保留的 initData 镜像，实际 Data.get 单次读取订阅依赖，订阅嵌套别名及逃逸 ref；根变更不重复发通知，不改全局原型，借用接收者保持、结束恢复自有描述符。内核缺少所需触发钩子会在修改前拒绝，不能直接换 production 构建；原生嵌套不可变写与 silent/force／子树策略仍未闭合。

最终 **94 个有限原生场景一致**；四张隔离 Edge 页（source/target × 普通/ref）实际计数 0→1→11、逃逸 ref 21、嵌套别名 DOM 9 一致。普通各 6、ref 各 8 条真实 pre/post 回调值和 DOM 文本一致，明确拒绝空日志比较。目标加载独立响应式内核但无 Vue 组件运行时，双方无 warning/error。8 项边界控制通过，包含单次通知、原生根写、描述符恢复及不支持路径拒绝。

最终 v1/v2 合并 **13 项通过（32.993 秒，包含 v1 原 5 项及新增 8 项）**；同组 19.760 秒为中间测试。旧公开键／控件 **11 项通过（28.267 秒）**。测试及研究结果不叠加为迁移样本，也未全量重跑系统／30 样本。native/browser/controls 及 5 个代码副本共 8 payload 封存至 docs/verification/2026-11-17_public_instance_proxy_v2；原生产运行时与 v1 封存指纹保持不变。

中间真实失败保留说明：cleanup 数组无接收者分派错误；记录错误函数返回值被误当 getter 结果；代理嵌套／ref 已变化而原生镜像／DOM 未刷新；过早取得 watcher 空日志。修正后增强反例再测。中间 JSON 不绑定最终源码，也未逐轮备份源码，不冒充最终证明。详细记录见 docs/PUBLIC_INSTANCE_PROXY_V2.md。

完整 Vue 私有 vnode／渲染图仍明确未实现，完整生命周期／调度交错、部分原生写策略及自动 SSM 编译真实 SFC／加载／候选门均未闭合。arbitrary_public_key_contract_complete=false、production_admission_eligible=false；source_dynamic_key_contract_unsupported 保持，Prompt／SSM／原引擎／阈值／配置／旧产物和费用不动。没有云模型、LangSmith、训练、实际库写入或 commit/push；目前无需重启或付费复跑。

## 2026-11-17：获授权的公开实例代理原型（未接入）

用户在确认原生 Vue／San 的 `data` 命名空间冲突后明确授权“允许内部公开实例代理，先验证兼容性再接入”。新增 research/public_instance_v1 独立原型和专项测试，不导入默认系统、不改变组件导出／加载、不修改 engine／SSM／生成或修复 Prompt／规则／阈值／配置。业务 receiver 与原生 San receiver 分开，内部 Data 由闭包／加载方句柄保存；源风格方法绑定业务 Proxy，键转换仍由原生 JS 赋值执行，任意额外字符串／Symbol 不被固定键白名单拒绝。

当前 Vue 3.5.45／San 3.15.6 的 **73 个有限原生场景一致**；覆盖字面点号键、转换顺序／异常、Symbol、业务 data/watch 等与 San 字段同名属性、绑定方法覆盖及基本只读行为。两张隔离 Edge 页在公开 data=null、watch=42 后继续实际点击与赋值，双方按钮文本 0→1→11、内部指针保持、dispose 成功，San 页无 Vue 运行时、无 warning/error；不是完整像素评估或实际组件 SFC 验收。

原型明确保留 **4 个实际差异**：声明状态对象的响应式身份、Vue 内部记录读取、`$` 任意键赋值后的公开读取、公开 `$watch` API。另有深层别名／ref、完整 computed 缓存／反射／调度、父子树与自动 SSM 编译等未验证。`arbitrary_public_key_contract_complete=false`、`production_admission_eligible=false`，不新增白名单或值域限制来改判通过；当前生产仍返回 source_dynamic_key_contract_unsupported。

最终专项 **5 项通过（14.445 秒）**，既有公开键／控件专项 **11 项通过（24.430 秒）**；首轮 5 项 12.163 秒及扩展阶段 5 项 10.224 秒保留为中间验证，不叠加计数。首次原生实验暴露 warn 前缀比较问题；随后实际发现 __proto__ 的 Vue 默认 globalProperties 继承键 defineProperty 分支差异，修复原型并增加重复赋值／描述符反例后重测。源码、双端版本／实现指纹与观察封存到 docs/verification/2026-11-17_public_instance_proxy_v1，6 payload 以 SHA256SUMS.json 核验；原独立重构验证的生产实现指纹全部保持不变。

本轮无真实模型／LangSmith／训练／实际库写入、无 commit／push，不回填历史样本结果。尚不能让用户付费复跑验证完整契约；后续先关闭这些反例并验证实例生命周期连接，再做可审计生成、校验和修复接入。详见 docs/PUBLIC_INSTANCE_PROXY_V1.md。

## 2026-11-17：r5 独立目录重构与实验实现内聚

用户要求按开题和既有实验复用完整模块化重构，不再引入不必要的新迁移模块，也不继续依赖“毕业设计”根目录。先核对选题报告中四维 SSM、few-shot／LoRA、LangGraph／LangSmith、TED、Puppeteer／SSIM／像素／计算样式和有限修复路线。本轮调整依赖及职责，不改变 Prompt 正文、规则顺序、预算或质量阈值；已有任意公开键与严格 DOM 未证明问题不趁重构豁免，也不把旧高通过率当作任意行为等价证明。

新增内部 `engine/MANIFEST.json` 登记 98 项来源（source commit `2b57afbc7d21f35cd7072f4f3d11e8cb43f6bf13` 及实际工作区文件指纹）：96 项逐字节保留，另两项是无副作用 package facade 及纯生成函数／类名规则常量提取。未复制旧完整 orchestrator 或 Flask 服务；静态、规则与修复 Prompt 仍来自原实现，主编排只有新系统的真实 LangGraph。独立 Node 依赖在 engine 内按原 package-lock 离线安装 30 包，未升级前端／浏览器锁或模型配置。`.gitattributes` 保留内置源码／证据字节，不让 checkout 改写清单指纹。

生成／修复从任务账本服务拆到 `stages/generate.py`、`stages/repair.py`，修复 body 的 AST 与拆分前相同，依赖显式传入以保留原测试边界。默认前端只加载真实迁移页，旧夹具页延迟加载；`worker` 为真实迁移别名，旧夹具显式叫 `development-worker`。历史 README／指南归档到 docs/history，六个依赖原数据的重放／冻结脚本移到 `tools/migration_system_history`，原冻结文件不变。当前架构、部署和保留决定分别见新 README、SYSTEM_GUIDE、docs/ARCHITECTURE、docs/REUSE_MATRIX；不是再追加一套并行的运行系统。

`Settings.repository_root` 保留兼容字段名，但值固定为本目录 engine，无父目录代码兜底。新默认库／检查点是 `var/runtime`，产物是 `var/artifacts`；旧 var 业务库和父目录实验产物未移动／删除／导入，本轮没有初始化或升级实际数据库，没有启动用户真实队列。SsmPanel.vue、ssm-model.ts、用户 system.toml 未改；原 Vue／San、失败／通过和费用不重写。

独立性验证在仓库外临时目录中实际复制源、配置、已安装依赖和前端构建；Python 读取审计拒绝原 checkout 的源码／数据（正常使用已有 Python 第三方运行环境），不设置父级 NODE_PATH、不用链接共享源文件。临时 API／SQLite、实际 AST 提取／LangGraph、规则／校验、Puppeteer、候选接受及下载全部通过，所有载入的系统模块来自副本；额外确认合法空元素、真正语法错误和已知未支持契约在模型前阻断。模型为明确响应测试替代，2 次 fixture exchange、实际云调用 0，不冒充真实模型成功样本。结果存于 docs/verification/2026-11-17_standalone_refactor，两个 payload 已用 SHA256SUMS 封存，并核对当前实现指纹。

复用对照专项 **5 项通过（96.340 秒）**：SSM 完全相同、生成 messages 完全相同、静态诊断／规则／修复 Prompt 相同、修复函数 AST body 一致和源码归属不变。配置／契约专项 **28 项通过（18.915 秒）**；生成边界 **18 项通过（17.972 秒）**；前端 TypeScript／Vite 构建及 Node **22 项通过**。

完整系统回归执行了 **408 项（2107.899 秒）**：406 项通过，2 项失败来自旧开发夹具的 subprocess 仍调用 `worker`，而该名称已明确切换到真实迁移 Worker；并非模型或评估分数回归。将两处夹具命令修正为 `development-worker` 后，受影响任务链路完整 **22 项通过（67.098 秒）**，配置／入口 **29 项通过（15.749 秒）**，并新增真实 Worker 别名路由断言。没有把第一次失败隐去，也没有声称以同一命令一次跑过新增后的全部 409 项。

收尾将普通测试中的提取／浏览器／契约路径也改成内部 engine；来源对照和冻结样本用例在缺少旧语料时明确跳过，不把它们伪装为新部署的运行依赖。受影响的 SSM、登记图和配置合计 **76 项通过（247.747 秒）**；最终完整模块化专项 **102 项通过（524.307 秒，无跳过）**，覆盖真实浏览器、冻结语法／规则闭环、原多维评估及工作台。当前原实验语料存在，历史用例没有因独立化而被跳过。运行时实现仍与仓库外独立副本验证指纹完全一致；只读 check 验证 98 项内部引擎，未初始化实际库。以上各组与完整回归有重叠，不相加为迁移样本数。

前端 README 中历次互相覆盖的“当前入口”和旧命令也已归档到 docs/history，现行前端文档只保留本目录构建、真实主入口及历史页边界，避免继续误用旧 `worker` 夹具说明。

中间验证不计成功：纯 builder 指纹最初误用 Windows 原始 CRLF 哈希，修正为原约定 LF 归一化；初次完整测试因此失败并中止后重跑。独立探针的两个夹具假设也修正：原规则可能无需第二次模型边界调用即可修好；小文字色差可能在既有阈值内，不应强求修复。最终用显著布局／背景缺陷覆盖真实模型修复候选路径，未降低阈值或伪造评分。新建证据清单中的手抄哈希也在校验发现后更正，payload 本身未改。未执行真实模型、LangSmith 上传、LoRA 训练、commit 或 push；整个历史 30 样本的模型通过率未重新测量，不宣称重构提高了该统计。

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
