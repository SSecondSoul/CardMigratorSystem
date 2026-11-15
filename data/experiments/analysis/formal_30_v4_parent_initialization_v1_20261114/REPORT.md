# 父初始化浅复制语义闭环 v1（2026-11-14）

## 结论与范围

本轮只提高 Vue→SSM→San 源码迁移正确性，不增加 Ref provider、跨框架互操作协议、用户输入接口或运行时生产依赖。使用冻结的 TripItineraryPlanner Vue 和上一轮 shared-swap 离线产物；不重新生成、不修改 canonical San、不改人工验收页，不继承人工通过。

源码 created 以原生 map + Object.assign({}, item) 生成新数组、新记录，但共享嵌套对象；生成的 inited 经递归 clone 深复制，改变引用关系。已在共享 repair AST 中加入源码驱动的有界规则。新诊断 source_parent_initialization_not_landed 接入现有 ValidateStage 的 AST 检查，repair 前处理、模型返回后处理、repair Prompt 和独立候选回归门同步。生成阶段/服务器 Prompt 不改，无须为本轮修改重启服务器。

上一轮静态剩2条；本轮新检测使当前输入成为3条，修复后仍2条、validation_passed=false。不是组件整体通过，不把新增检测解释为新引入的产品回归。

## 修复边界

仅匹配源码两条有序初始化语句及精确的字面量根 setter（this[key]=value），两个声明的数组 props、已声明且无冲突的本地数组/选中字段。目标必须是直接 require('san') 导出的父组件，已知六语句 inited 与词法绑定、完整体相符的旧 map/clone helper；未知 helper、额外副作用、改序、观察器、全局遮蔽/写入、字段冲突或不明生命周期形态拒绝自动修复。组件、字段、helper 和 setter 改名仍可匹配，不使用组件名白名单。

恢复源码浅 map，同时恢复相邻的首元素存在性判断：源码 days[0] ? days[0].id : '' 不等价于 days.length>0 ? days[0].id : ''。不补默认项、不深克隆、不改到 attached、不重复初始化。只降低两个已证明的字面量根调用，不恢复任意动态 setValue，也不按点路径解释任意键。

仅父 inited AST 改变；独立 AST 对照确认其他脚本不变，模板与 CSS 原文不变。候选门独立重新分析源契约，不信任调用者提交的 validation_passed；倒退到旧深复制、隐藏诊断或移走钩子不能放行。新增规则不豁免 nested_state_mutation。

## 验证与反例

原生 Vue 2.7.16/San 3.15.6 的真实组件构造对照：

- 普通嵌套对象：新数组/新记录、共享 meta、meta 写入可见且顶层 cost 写入隔离，与源码一致；旧 target 的 meta 不共享。
- Symbol 属性：源码浅复制属性得以保留。
- 循环嵌套对象：源码/修复件成功；旧深复制 RangeError。
- 空记录数组、空日期数组：对照一致。
- 稀疏 items、首日期为洞/null：完整 target 仍出现 TypeError，源码没有；旧 computed helper 的集合语义仍未闭合。本轮没有宣称这些完整组件用例通过。

为定位最后一组，另在真实框架内仅隔离 computed，执行原样初始化钩子：稀疏记录、稀疏/空首日期及空日期四种输入均与源钩子一致。此测试是钩子局部证明，不是生产补丁，不把清空 computed 的探针用于生产或完整等价声明。首次测试的三处失败及最终仍保留的完整组件异常均保存。

默认 props 的轻量初始 DOM 对照：前/后结构、标签序列和文本相似度均1，TED=0；San 编译/渲染无新错误。不是浏览器交互或截图视觉验收。

最终定向回归：217/217，13个完整 suite、2个工作进程、321.286秒；运行前后实现和测试指纹不变。不是全仓库测试。包括新初始化13项、shared swap、浅记录更新、只读桥接、事件包装、阶段/启动、子组件工厂、候选保护、评估器校准与调度。

失败留存：

1. 首次新增12项测试中3个子例失败：完整 target 的 computed 在稀疏/空日期输入下抛错，不能用局部初始化证明掩盖。拆分完整组件风险断言与隔离钩子对照后13项通过，生产 computed 没有改写。
2. 首次完整定向217项中2条测试失败：一条把方法前的尾部缩进纳入了比较；另一条子组件旧测试未计入已有动态 class 诊断及修复组合。保留全部旧诊断和失败日志，只更新精确测试预期/规则组合，不删错误码、不放宽验证器。子组件单项复核1/1通过，随后完整重跑。
3. 输出截断、Windows GBK 编码及 PowerShell 引号导致的工具调用失败单独记录，非模型/产品修复失败。

## 清查、统计与剩余工作

沿用既有30项冻结/累计开发输入，仅做共享 AST 规则扫描：只 TripItineraryPlanner 改写，其余29项不变，原24个批次通过件未改写。这里不是重新验证30项全交互，更不是新的独立测试。实际原生运行时组件1项，本轮新增人工确认0项。

原始批次24/30通过、6失败、0执行异常、1,821,544 tokens不变；本轮模型调用0。未启动服务器/浏览器/Jupyter UI，未 commit/push。

仍保留：moveItem 共享记录突变/通知的完整响应式证明；公开任意动态 setValue 接口未迁移；computed helper 在稀疏/空记录下的原生集合语义差异。不能把“静态剩2条”理解为“只剩2个真实问题”。

下一步优先核对 computed 外部辅助函数的原生数组语义，再审查共享写入通知和动态辅助接口的校验范围；继续冻结反例→源码契约→受限规则→回归，不靠增加 Prompt 或反复模型试跑代替闭环。

## 复核入口

- 输入：../formal_30_v4_parent_initialization_v1_input_20261114/baseline.json
- 本包 audit.json、native_observations.json、inventory.json、implementation.json、tests.json、派生 San 与 SHA256SUMS.txt
- 失败：../formal_30_v4_parent_initialization_v1_development_failed_20261114/、../formal_30_v4_parent_initialization_v1_historical_tests_failed_20261114/
- 只读重放：项目根目录执行 python -m migration_pipeline.replay_source_parent_initialization_v1，仅输出 JSON，不写产物/不调用模型。
- Notebook：notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb，追加记录，原111个单元和 metadata 保留。新只读审计从根目录及 Notebook 目录执行；历史单元保留其对应历史版本的指纹，不伪造其对当前代码的通过。
