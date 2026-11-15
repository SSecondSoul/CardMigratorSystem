# TripItineraryPlanner：剩余源调用和通知链审查（2026-11-15）

## 结论

这是冻结候选的离线审查，不是修复、全量回归或新的通过证据。组件仍未通过，不豁免既有诊断，不改变公开方法或观察者的验收范围，不增加运行时互操作能力或用户输入协议。

本轮发现一个实际源码交互路径上的残余缺陷：稀疏 initialItems 下调用删除按钮对应的 removeItem(1)，Vue 成功删除并发出一次 itinerary-change，San 的旧 filter 辅助函数访问洞位的 id 时抛 TypeError，状态未变且无事件。这里是原生实例方法调用复现，没有启动浏览器或点击页面。不能用现有“两条诊断”代表全部缺陷已被覆盖。

## 输入与方法

- 源码和候选路径及 SHA-256：见 audit.json；输入基线见 ../formal_30_v4_remaining_contract_audit_v1_input_20261115/baseline.json。
- 输入是上一轮 computed 集合修复后的离线候选，未修改 canonical San、模板、CSS 或人工页。
- AST 审查脚本：migration_pipeline/audit_remaining_source_contracts_v1.cjs；只读重放：python -m migration_pipeline.replay_remaining_source_contract_audit_v1。
- 本地原生运行时：Vue 2.7.16 与 San 3.15.6。源码方法、计算值、事件和引用身份探针不是 DOM、视觉或人工验收。
- 25 个既有实现／测试文件及 3 个人工页／配置文件指纹保持不变；本轮不改生产代码、生成 Prompt、repair Prompt、校验器或候选门。
- 本轮新增两个审查脚本及一个证据测试文件。implementation.json 封存其源码和指纹；observations.json 保存原始观察；tests.json 保存完整测试输出。

## 已确认的观察及边界

### 1. 共享记录写入及通知

对前移、后移、原位、下界、上界共 5 组 moveItem 输入，对照了根提交、saved 标记、notify、事件、计算值、nextTick 后值和记录／嵌套引用身份。在排除 San 自身 computed 缓存写入的明确投影下，5/5 一致；原始运行时 trace 不相同且已保留。

正常移动顺序为 items 根提交 → saved 根提交 → notify → itinerary-change；通知和事件读取到更新后的可见项、冲突项和预算。浅共享写入仍保留，不能擅自深克隆来消除警告。

额外添加原 SFC 不含的外部深层同步观察者时，Vue 观察到 3 次通知（含两次共享记录逐步写入），San 只观察到最终根提交的 1 次。最终值一致不等于观察序列一致。此探针用于记录边界，不实现 provider，也不据此清除或豁免 nested_state_mutation。

### 2. 动态 setValue 的实际调用

原 SFC 共 14 处直接调用，均为已声明根状态的字面量键。按调用方法和键统计，对应 14 处目标 data.set；created→inited 仅用于定位计数。没有在该 SFC 中发现 helper 引用逃逸、动态实例访问、模板引用、mixins 或 extends。

这只证明可见调用位置和次数吻合，不证明各右值与执行时序等价，也不证明外部消费者不存在。目标仍没有公开可调用的 setValue，不能单凭内部调用被内联就取消 source_method_interface_not_landed。

反例：源码 setValue('draft.start', 'literal') 设置字面量实例键，draft.start 保持原值；朴素 data.set 同名字符串却修改嵌套路径。源码新增 lateField 是实例字段，San store 字段也不是同一接口。未安装这种朴素适配器，未变更公开方法验收规则。

### 3. 额外确认的原生 filter 残余缺陷

输入 [a, , b] 经上一轮源初始化和 computed 修复后可以构造并读取显示计算值，但 removeItem 仍走旧的稠密遍历 filter：

- Vue 删除 id=1 后保留 id=2，总预算项成本由 5 变 3，发出一次事件，payload 与新 items 同引用。
- San 抛出 Cannot read properties of undefined (reading 'id')；仍为 ids=[1,2]、成本5，事件0。
- 这属于源码删除按钮绑定方法的功能缺陷，而非额外跨框架互操作要求。尚未修复或加入生产诊断；新增自动化证据用例已能重复捕获。
- 公开 dayCount('d1') 在同一稀疏输入上也出现目标 TypeError（读取 dayId），源方法不抛错。两处共享旧 filter 的洞位处理根因，不重复当作两个独立总体缺陷计数。
- 目标模板已使用先前生成的私有源码派生方法，因此公开 dayCount 失败不能写成模板计数也已失败。该探针未记录 count 返回值，不据此断言其具体值。

不将本轮观察直接回填为原批次首次人工 production_defect 或 repair_regression 数量；本轮未证明该洞位缺陷是由前一修复新引入。

## 校验与测试

重新运行当前静态校验仍失败，恰有两条既有诊断：

- nested_state_mutation：moveItem 的共享记录写入。
- source_method_interface_not_landed：公开 setValue 尚无已证明的可调用实现。

当前源语义 repair 在该候选上不再产生改动；这不表示实际源码交互没有遗漏缺陷。

12/12 本轮审查证据测试通过（完整单次运行，12.608秒；unittest 报告12.354秒），包括重命名、未知模式拒绝、逃逸检测、静态不执行脚本、5组通知对照，以及预期失败反例。测试通过表示观察可复现，**不表示组件通过**。原233项测试本轮未重跑，相关实现指纹已核对不变；不拼接为245项全量回归。

Notebook 仅追加本轮说明和标准库只读核对单元。历史115个单元与metadata保留；历史指纹单元关联各自旧版本，不声称整本 Run All 可在最新实现上通过。只验证JSON、代码编译和新增单元执行，不声称Notebook UI渲染或人工确认。

## 统计与下一步

原全30项是重复开发回归而非独立测试：24/30通过、6失败、0执行错误、1,821,544 tokens，全部保持不变。模型调用0，新增人工确认0，未启动服务器、浏览器或全30项重跑，未commit或push。

下一步先闭合已复现的 removeItem 原生 filter 源语义：冻结输入 → 源契约诊断 → 有边界通用修复 → 稀疏数组／副作用／身份／事件顺序回归 → 独立候选保护；另核对公开计数方法同根因路径。不全局替换 helper，不先放宽剩余两条诊断，不用增加 Prompt 或付费反复试跑代替闭环。

共享观察者差异与任意动态 setter 仍保留未解决状态；若以后需要改变公开接口验收范围，应另行明确决定并保留原口径失败，不能以本次源码调用审查自动改变协议。
