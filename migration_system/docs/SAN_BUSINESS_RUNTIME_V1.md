# San 业务实例 v1：当前可执行进度（未发布）

当前状态：用户明确拒绝以规则替代模型生成，已撤销动态 setter 的生产接入及 `stages/business.py`。本目录所述运行时仅离线研究保留，不参与当前生产生成、校验或加载。生产范围为 `san-supported-migration-v3`，动态 setter 只放行预检查，仍走原模型链；研究通过不等于模型迁移通过。

2026-11-17 后续优先级调整：用户确认先交付[明确支持范围的生产迁移闭环](PRODUCTION_CLOSURE_V1.md)。本模块暂停扩展，不接入默认 Worker，不作为该闭环交付前置条件；以下研究进度和缺口保留，不改判为完整契约已完成。

2026-11-17。契约为 [san-business-instance-v1](SAN_BUSINESS_INSTANCE_CONTRACT_V1.md)，不是继续扩建 Vue 私有 vnode 模拟器。此处承接旧 v7，**不修改其封存、失败、费用或实验分母**。

## 本轮继续：自动内联树、事件／错误路由和真实渲染读取

在首轮 18 项证据之后继续开发，不覆盖其 47 个封存 payload。新增 template.cjs／tree.cjs，自动读取源码 const 内联 Options、注册表及 template，生成真正 San 组件树；绑定来自源 AST 的事件表达式，不需人工 metadata，也不在 Node 执行源代码。外部 imports、递归／动态组件注册及更宽模板语言尚未实现，仍明确拒绝。

真实源树验证：两参数与数组监听器、once、动态 props 和 inheritAttrs=false 下的动态 attrs、连字符 attrs 原名、组件 ref／$parent／$root、子 $options 与父注册表对象身份、祖先 errorCaptured 返回 false。另验证任意键覆盖方法后，已安装事件仍保留旧函数直到下次渲染；新监听器在渲染时切换，严格函数 this 不被错误绑定到桥接对象；动态替换声明状态中的回调数组也会触发更新。DOM 成员事件的非循环表达式加入响应式渲染前读取；数组与异步错误通过统一分派器，避免额外 catch 重复路由。

本轮实际遇到并修复：裸 this 严格比较误报逃逸；San 将 data-note 归一化为 dataNote，破坏 $attrs 原名；过早镜像读取 getter；San 局部更新比 Vue 少执行 getter；未使用字段误触发更新；旧分支读取未清理；事件覆盖后立即切换而非渲染时切换；可选成员调用误将严格函数 this 设为桥接对象。当前带副作用 getter／toString、未使用字段、隐藏分支和函数值均有真实对照，不将这些有限案例推广为任意执行顺序的完整证明。

public_api_probe 新增单根 pre watcher 递归对照：同一固定版本的 101 次回调／count=102、nextTick 拒绝及不提交旧待渲染 DOM；跨根／复杂异步递归尚不能据此宣称完成。本轮同一指纹下最终专项 **20 项／32.673 秒**、旧代理回归 **41 项／63.472 秒**、默认生产边界 **11 项／15.044 秒**，全部通过。自动源树、13 项值显示、6 项公共 API 夹具和冻结商品筛选 11 步重放分别保留；商品筛选 UI 100%、SSIM 1、不同像素 0。测试时长来自 unittest 日志，不累加为迁移样本。本轮以 `verification/2026-11-17_san_business_instance_v1_tree_partial/summary.json` 及日志为最终证据，首轮 18 项结果不回写。

**这轮仍不是完整契约发布。** slots、动态／函数／循环 refs、自动 attrs fallthrough、更宽组件树／模板语言、跨 root 调度和复杂副作用顺序仍需闭合；默认生成／验证／修复及发布指纹未接入。原来的剩余项表是首轮历史状态，上述内联树、有限父事件／祖先错误和动态 attrs 已有代码，不应再说它们完全没做；也不能说已实现所有这些能力的变体。

还不能把 research v7 的 keyed 4/4 自动记为此导出的结果：该研究是在加载前对固定 San 源码生成内存候选，本导出当前使用原生 San，尚未将那份 guarded keyed 移动补丁接入可部署加载链。因此新自动组件树的有状态 keyed 重排仍未闭合，必须单独验证，不能只比较最终 DOM。循环／条件分支中的事件 getter 与 DOM 更新先后也不能由当前非循环快照案例推断为完全等价。

## 已实际实现

1. 在真实 San constructor 内连接业务 Proxy；this[key] = value 保留原生 ToPropertyKey，字面点号键和 Symbol 不作为 San 路径。业务 data／watch 等字段不覆盖原生句柄。
2. 保留源 data() 返回对象、别名、ref 和描述符；按源 Options 初始化 methods／computed／watch／hooks，而非逐字段手工列白名单。San 控件通过源响应式对象写入。
3. 简单动态父 props 批量更新、child pre watcher 与更新 hooks 的实际 DOM 顺序；跨独立导出共享响应式内核／owner 品牌，避免两份内核互不订阅。
4. 公共 $emit 的已配置回调、once、model 修饰及显式错误路由；$forceUpdate 实际渲染去重；$nextTick 与 owner 屏障；卸载后的 $watch 按固定 Vue 行为生成不活跃 watcher。
5. 源 AST 自动生成 refs／原生 DOM 属性策略；真正更新空 class、value、checked／selected。插值使用独立 @vue/shared.toDisplayString，Symbol input 值显式字符串化。
6. 默认 prop 工厂取得此前已解析 props，无 data() 时共享冻结空 $data；连字符 prop 归一化；仅声明 emits 的回调从 $attrs 排除，未声明的 onClick 等保留。未实现的根 ref／vnode 回调及原生父事件路由明确拒绝，不静默丢弃。
7. 离线编译／独立校验绑定源、模板、脚本、运行时和依赖指纹；Windows 输出使用精确 UTF-8 字节，不让换行转换破坏 SHA-256。

运行时实现位于 [runtime/san_business_v1](../runtime/san_business_v1/README.md)。Node 只解析，不执行用户源码；实际组件运行在授权的隔离浏览器。目标仅由 San 渲染；独立 @vue/reactivity／@vue/shared 是披露的辅助依赖，不加载 Vue 组件／渲染器。没有引入跨框架互操作输入要求。

## 实测证据如何理解

- 新专项覆盖编译篡改拒绝、精确文件字节、源控件／hooks、92 个有限业务案例、5 个公共 API／父子夹具、12 类有限值和 4 项拒绝／共享控制。不同层级案例不能累加成迁移成功样本。
- 冻结 ProductFilterPanel 的同一源码／既有第 3 版 San 模板，离线派生新产物，实际执行搜索、分类、库存、价格、排序、选中、空结果及重置共 11 步；初始及每步 DOM／样式／控件状态检查通过，初始结构相似度及 UI 为 1／100%，阈值未下调。
- 静态范围明确是**规范源 Options 及 receiver／脚本绑定校验**，不是声称旧静态语义分析器已理解此新导出。只有编译器独立核实 :key／trackBy 完全匹配，才对模板树采用版本化身份投影；原始 DOM 比较保持严格。
- 主系统默认 gate、原 185 文件生产基线及旧 v1–v7 封存保持；回归还需持续验证，不以文档状态代替。

使用 scripts/verify_san_business.py 生成源码副本、输入副本、测试日志、实际浏览器 JSON／截图／热图和 SHA256SUMS。最终本轮封存路径：[证据目录](verification/2026-11-17_san_business_instance_v1_partial/summary.json)。本轮新专项 18 项／37.111 秒，旧代理工程检查 41 项／76.907 秒，默认生产公开键专项 11 项／19.396 秒，全部通过；时间来自 unittest 日志，summary 的 subprocess wall time 另含进程启动开销。

## 本轮发现并修正的反例

早期重放缺少 value／空 class 属性且模板 key 表达不同；并非像素相同即可忽略。已在真实 DOM 层修属性，模板身份映射只在编译验证后应用。早期 Windows 文本写入还导致导出字节与 manifest SHA 不一致，现已改为字节写入并加回归；早期报告仅是中间观察，不冒充最终实现绑定。

新增 attrs 对照的修复前结果为 public_api_difference_observed：display-name 未进入 displayName，未声明的 onClick 被误删，key 被错误计入 attrs。修复与失败观察均保留。卸载后 watcher 曾错误地产生回调；固定版本原生对照表明注册允许但 watcher 不活跃，修复按该实际行为执行，不创建一个新的活跃 scope。

## 尚未完成，不能放行

| 层次 | 当前边界／下一项 |
| --- | --- |
| 主链 | 新编译器未接入默认生成、校验、修复、候选保护、API／前端及任务指纹；不应让用户现在付费复跑 |
| 组件树 | 尚未从真实 source／SSM 自动编译 Options.components／imports 树；已有父子证据是可信夹具，不是集成证明 |
| 公共行为 | 父原生事件多参数路由、祖先 errorCaptured、完整 slots／动态 attrs／ref／复杂父绑定等仍未闭合 |
| 调度／值 | 递归 watcher 安全与源行为、带副作用 accessor／coercion 的读取和执行次序仍未充分证明；不能缩小键／值域宣称完整 |
| 发布 | 仍需版本化主链接入、失败候选保护、独立复制运行及真实端到端回归；不把单个样本通过等同系统完整 |

full_contract_complete=false，production_admission_eligible=false，默认 source_dynamic_key_contract_unsupported 未删除。未调用云模型／LangSmith／训练，没有改用户配置、实际数据库／队列，也没有 commit／push。当前无需重启用户服务器；重启也不会使未接入模块自动生效。
