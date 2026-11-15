# 动态公开键接口的有条件可行性结论

日期：2026-11-15。结果：**在本轮明确的直接San实例／任意公开键契约组合下继续不支持并阻断，不添加伪修复。** 这是S1动态接口的有条件边界结论，不是将整组件判为通过，也不是证明任何其他架构都无法迁移。

## 冻结输入与范围

源为TripItineraryPlanner冻结Vue，SHA-256 77cd70af2dbbfd0788ccf61203e95ee02ebbad35d36291f9542d057f8ecd3139；目标为filter闭环后的离线候选，SHA-256 fd845c3a98f6ea2388b8c2eabebee9f2e3455a313797e6c255d36355be934626。文件路径、38个既有相关实现／测试指纹、人工页、运行时源码及前125个Notebook单元指纹在baseline.json。

用户已明确保留任意公开键契约，不限定为六个源码可达根键。以下结论需要同时成立的前提：

1. 调用方读到的是同一个直接San组件实例的公开属性，不是另一层门面。
2. 任意公开键包含源码可接受的普通键data，赋值后应可读回该值。
3. 未修改的San运行时仍使用实例data保存原生Data存储。
4. 不新增context-sensitive属性拦截、兼容门面、provider、运行时引擎分支或调用方协议。

此处第4项是“不增加运行时兼容层”的具体解释，未实现或测试上述架构方案。若以后研究范围改变，需重新评估，不能将本轮结论外推为所有JavaScript实现数学上不可能。

## 新的原生实例反例

不是重放旧JSON。新探针创建完整冻结Vue选项与内存San候选的**未挂载原生实例**，执行公开setter，再执行冻结组件真实业务方法updateBudget和映射的原生watch注册。测试5类输入：声明根saved正对照、data=null、data=42、data={marker:7}及强制转换为data的键。每种有5个目标提案，源实例每次重新创建。

data=null的观察如下：

| 目标提案 | setter结果 | 公开data读回null | San存储指针保留 | 随后updateBudget／原生watch |
| --- | --- | --- | --- | --- |
| 原候选缺方法 | TypeError | 否 | 是 | 可调用，但接口已失败 |
| 原样实例赋值 | 不报错 | 是 | 否 | 两者TypeError，预算仍500 |
| data.set路径写入 | 不报错 | 否 | 是 | 可调用，预算变321，但公开属性不等价 |
| 键转换后六根分派＋实例回退 | 不报错 | 是 | 否 | 两者TypeError，预算仍500 |
| 拒绝data后有限分派 | RangeError | 否 | 是 | 可调用，但源调用并不抛错 |

源Vue在上述namespace输入下setter不报错，公开属性可读回输入，原生$datastore保持，真实updateBudget将预算变321，$watch注册正常。根saved正对照在路径、分派和拒绝data方案下映射投影一致；这个正对照不证明任意公开键契约。coerced-data-null的源和实例／分派／拒绝方案键转换各一次、hint为string，反例不是重复键强制转换造成的假象。

数据指针被覆盖的提案先完整记录业务方法和watch错误，之后只为dispose恢复测试实例；这种cleanup不是生产修复。没有挂载DOM、浏览器截图或新增人工验收，不能宣称完整渲染／交互通过。测试的是当前冻结Trip，不将25组目标调用复制成21个组件的新增整组件实测结果。

## 有条件冲突的推导

源码setValue(data,null)后的公开属性义务是instance.data===null。当前未改San运行时的义务是同一个instance.data仍为非null的原生Data对象。installed San的component.js初始化代码写入this.data=new Data(initData)，watch调用this.data.listen；实际加载dist版本及文件指纹见environment.json。

在上述稳定同一公开属性、直接实例和未改运行时前提下，两项义务不能同时成立。仅多加Prompt、恢复空方法、把任意键当路径或拒绝保留键都不能消除这个冲突。这个结论比“所有候选都还没证明”更具体，但严格限定于列出的输出架构与契约，不声称所有架构都不可实现。

当前处置：本组合记为unsupported_under_current_combined_constraints，保留原缺失／语义未证明诊断；不缩范围、不加六键白名单、不将其降为warning。**这是离线审查处置，不是新生产错误码或自动调度跳过实现**；生产规则和修复调度没有修改。其他动态方法或不同组件／API表面仍需各自分析，不能无条件套用全部组件。

## 改动与验证

仅新增两个原生／只读探针和一个测试文件：
- migration_pipeline/probe_dynamic_setter_namespace_v1.cjs
- migration_pipeline/replay_dynamic_setter_feasibility_v1.py
- tests/test_dynamic_setter_feasibility_v1.py

新增11项原生边界测试、既有12项接口保护测试和11项收尾审计测试均通过，共34项，原始输出见tests.json。三套件分别执行，不是单一综合campaign，不是全仓库；前273项未重跑。第一遍新套件及verbose保护测试也通过，后者只保存末段；随后完整静默保护套件重跑并保存输出，不能把不完整日志说成完整日志。

38个既有相关实现／测试及人工页前后指纹保持一致；3个新文件全文保存于implementation.json，不是完整环境备份。原生产检测、候选门和repair Prompt不变，不新增自动setter恢复；原生成产物及离线候选也不写入。源／目标分别为Vue2.7.16、San3.15.6本地实例oracle，不新增生产依赖或互操作。

## 实验与后续处置

原开发回归24/30、6失败、0执行异常、1,821,544 tokens保留；当前Trip整体未通过，旧nested_state_mutation与接口阻断不解除。共享记录深层同步观察者3对1、异常求值阶段风险未被本轮解决。

本动态接口分支先以明确的有条件不支持结论收束，不重复尝试已证错误的方案或继续付费试跑。下一项转向共享记录修改的通知证明和异常阶段；可修复则形成规则／验证／回归闭环，仍不可证明则保留明确失败，不为论文收尾无限追求100%。之后按收尾计划补视觉评估，不直接启动独立测试或新全30模型批次。

证据：baseline、audit、native_observations、tests、implementation、environment、REPORT及SHA256SUMS.txt。复现：python -m migration_pipeline.replay_dynamic_setter_feasibility_v1。Notebook仅追加两单元保留前125单元及metadata，编译全部52个代码单元，从根与Notebook目录执行新增只读核查，不启动UI；不承诺旧历史指纹单元在最新实现下Run All。

无模型／浏览器／服务器、新人工通过、分数回填、commit或push。实验报告技能用于保存证据与边界，不作为迁移通过依据。
