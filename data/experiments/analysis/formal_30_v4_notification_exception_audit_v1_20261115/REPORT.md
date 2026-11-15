# 共享通知及异常求值阶段审查

日期：2026-11-15。分类：冻结候选原生行为审查／remaining_risk；不是新的生产缺陷率、修复成功、完整组件验收或模型实验。

## 本轮结论

本步审查完成，但两类语义边界仍未解决。普通moveItem的5组根提交／通知／事件／值及引用投影一致；额外深层同步观察者仍3次对1次。改成嵌套data.set或浅复制发布虽达到3次回调，却改变回调中的根对象身份；不能只追数量。force:true产生3条底层变更仍只有1次原生watch回调，深克隆则改变共享旧记录和嵌套身份。这四种提案均不提升为通用修复。

异常阶段已定位得更具体：Vue对洞/null/undefined日期可完成构造，但首次需求读取activeDayLabel时抛TypeError；San在构造期提前计算而抛TypeError，inited未进入。源码自己也有getter异常，不是“源对这些输入完全正常”。源在首次读取失败后替换days并selectDay可恢复，目标当前构造失败而无实例可恢复。捕获后返回空字符串会吞掉源异常；删除computed则连正常输入标题也丢失。没有把上述改法加入生产。

当前Trip仍不通过，动态公开键契约及现有诊断不豁免。额外观察者不升级为新必需功能，也不据普通投影通过就删除nested_state_mutation。未证明所有观察者或完整异常策略等价；不声称所有可能修复都不可能。

## 输入与方法

源与目标仍是最新filter闭环后的冻结Trip Vue和离线San，路径与SHA见baseline.json／audit.json；不改canonical、离线产物、模板、CSS或人工页。前一步动态键分支已记有条件不支持，本步不重新发明setter或缩范围。

探针使用完整冻结组件选项创建未挂载的Vue2.7.16和San3.15.6原生实例。目标提案只在内存override方法／computed，不输出新的.san，也不调用模型。共享组为5类移动输入×5个提案；异常组为5种days输入×3个提案。每个对照重建源和目标实例；不是浏览器操作或像素评估。

新增文件：
- migration_pipeline/probe_notification_exception_v1.cjs
- migration_pipeline/replay_notification_exception_v1.py
- tests/test_notification_exception_audit_v1.py

这些是冻结fixture专用的审查／测试提案，不是按字段名白名单实施的生产规则。不能把测试中写死的items／start等名称当作通用修复算法。原生产规则、验证器、repair Prompt及候选准入不变；本步没有新增生产错误码或执行提案的生产候选门。candidate_disposition.json仅为离线不推广处置。

## 共享写入与通知

### 当前候选保留的行为

前移、后移、原位、下界和上界5组，在明确投影下source与target一致。投影包含error、立即与nextTick后的状态、根替换、旧记录值、记录／嵌套身份、程序提交调用、notify与事件payload身份及其可见值；原生框架底层流量另存，不强行归一成相同trace。只有受控数据集上的观察，不能外推任意getter／代理输入等价。

正向移动时源额外深层同步观察者依次看到：
1. 共享记录第一处写入后starts=[10:00,10:00,14:00]，根仍旧对象，value===oldValue。
2. 第二处写入后starts=[10:00,09:00,14:00]，根仍旧对象，value===oldValue。
3. 最终items根提交，根为新对象、旧值仍原根；后续saved=false及notify／事件按源顺序执行。

当前San仅在最终根提交看到1次。这个外部探针不在原SFC内部，不能作为新增互操作／provider要求；但也不是全部观察者等价证明，既有审查诊断保留。

### 四种常见补法为何不推广

| 内存提案 | 观察到的反例 |
| --- | --- |
| deep_detach | 旧记录start不跟随源共享写入；选中记录的meta嵌套身份改变；仍仅1次回调 |
| nested_data_set | 3次回调，但每次根均已替换，前两次与源不等；旧记录未被共享写入 |
| force_same_root | 原始Data变更3次含2次force，但原生watch仍1次，不能等同深层回调 |
| shallow_republish | 3次回调但前两次根身份错误；原位操作还多出回调（源1、目标3） |

installed San Data.set内部使用immutableSet构造嵌套更新，原生watch还按newValue!==oldValue判断回调。因此“每处赋值调用一次data.set”及“强制发变更”不自动保留源身份和深观察语义。源码运行时文件及实际dist哈希见environment.json；不是对任何版本San或所有方案的普遍不可能证明。

## 异常阶段及恢复路径

探针分别记录构造、created／inited、label计算、首次需求读取、恢复数据再读取：

| 阶段（days有洞/null/undefined） | 源Vue | 当前San |
| --- | --- | --- |
| 构造 | created完成并返回实例，未需求读取label | label提前计算抛TypeError，inited未进入 |
| 首次直接读label | 抛TypeError | 无成功构造实例可读取 |
| 替换days并selectDay(d1)再读取 | 恢复one | 构造已失败，无实例恢复 |

正常days和空days，两端构造及首次可见值一致，但内部计算顺序不一致。正常输入的顺序不同本身不是本轮新业务失败；异常输入的构造／读取／恢复可观察结果不同才是未解决边界。

catch_return_empty使目标可构造，却把源TypeError变成空字符串；drop_computed使正常one变undefined。它们不是异常语义修复，不能为通过构造而吞错／删computed。这里直接捕获原生需求读取，不模拟完整浏览器渲染、全局错误处理、父级errorCaptured或SSR；未证明activeDayLabel旧helper对任意输入的全部find语义。

## 测试与未变内容

新增15项原生审计、17项共享交换闭环、16项computed集合闭环及11项动态键能力边界测试均通过，共59项。四个相关套件分别执行，完整输出见tests.json；不是全仓库，也没有重跑前273项或30个模型样本。测试通过证明上述观察和反例可复现，不表示组件通过。

41个既有相关实现／测试及人工页指纹不变；3个新脚本／测试源码与哈希封存于implementation.json。原生runtime和源码取证文件指纹在baseline及environment，非完整环境备份。之前的filter修复未回滚，普通投影和原生computed测试保持。

旧开发回归24/30、6失败、0执行异常、1,821,544 tokens不回填。静态旧诊断保留；本步未执行新的静态ValidateStage，不能把旧两条诊断当作仅剩两个实际问题。两类风险及动态键不支持继续独立披露，不生成新的人工通过结论。

## 处置和后续

S1本分支以明确未解决边界和拒绝天真修复的证据收束，不是宣称修复完成，也不是取消未来研究。没有充分源契约证明前，不增加Prompt或反复模型复跑来掩盖这些差异。

下一步进入S2受控浏览器／像素评估器开发：先固定环境并用同图、已知颜色／间距差异和动态数据控制样例校准，再接入实际组件评估；所有已知阻断保留，不直接启动新全30或独立测试。后续冻结版本若仍含未解决行为，应如实报告失败／不支持，而非要求调到100%才收尾。

本轮按实验报告技能封存证据并仅追加Notebook两单元，保留前127单元及metadata；编译全部53个代码单元，从根与Notebook目录执行新增只读证据单元，不验证UI，不承诺历史指纹单元在最新代码下Run All。范围进度文档仅追加，旧包不覆盖。

本包baseline／audit／native_observations／candidate_disposition／tests／implementation／environment／REPORT及SHA256SUMS.txt。只读复现：python -m migration_pipeline.replay_notification_exception_v1。

无模型／服务器／浏览器、新人工确认、生成产物改写、分数回填、commit或push。
