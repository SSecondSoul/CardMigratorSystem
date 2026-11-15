## 2026-11-14：显式原生依赖互操作协议 v1 草案（待审核，未实现）

本步按验证报告技能核对V13冻结证据、固定Vue源码与现有V7应用声明，形成可审核的设计与验收清单；没有新增运行时实验、没有实现provider，更没有放行生产。

- 设计：`docs/ir-design/native-ref-dependency-interop-v1-draft.md`；结构化清单：`docs/ir-design/native-ref-dependency-interop-v1-review.json`。状态均为draft／approval pending／not implemented。
- 明确输入提供方、San迁移端、宿主与独立门禁三方职责；概念接口为describe／open／capture／dispose，不是现成或已实现的Vue接口。
- 关键要求：保留Ref／value身份，旧别名依赖保留到源匹配重收集位置，provider只递交失效、不执行业务回调；生命周期代际与captureEpoch分开；异常部分收集状态、共享订阅与子组件同身份缓存传播必须有源对照。
- 受审公开Vue订阅API只作为输入端候选路线。静态源码显示sync会调用run/get重收集，pre/post使用另一队列，不能直接假定时序匹配。冻结构建导出的Vue.effect旁注明确仅内部测试，本稿不以此绕过公开API约束。
- 不改全局tracking／框架原型，不加重复观察器，不复制／代理／轮询，不暗用Vue watch/effect替San实现观察；现有V7错误profile不等于依赖provider批准，不缩小原公开值域。未知域依然是未履行契约，不是通过。
- 六个阶段门P0—P5、14个验收向量，全部待审核／待测；覆盖原Ref4点、新结构属性2点、旧别名时序、capture异常、真实父子缓存、多owner／晚到通知、未知provider、生命周期与伪造通过。清单校验通过仅为静态文档一致性，不代表这些向量已运行。
- 旧Ref192点仍有4差异，新结构116点仍有2差异，旧生命周期差异仍为1；上轮205项测试仅引用、未重跑。原批24/30通过、6失败、0执行错误、1,821,544 tokens不变。
- 生产、实验实现、人工验收配置指纹保持，0模型调用，未启动服务器／浏览器，无新增人工通过声明。仅新增设计／整理脚本及Notebook追加，旧98单元与metadata保留。

证据：`data/experiments/analysis/formal_30_v4_dependency_protocol_draft_v1_20261114`；设计前副本：`data/experiments/analysis/formal_30_v4_dependency_protocol_draft_v1_input_20261114`。当前证据等级为**static_only**，JSON与代码单元核对不代表Notebook UI渲染。请求的下一步授权仅为按草案开展输入端显式公开API隔离可行性原型，仍不接生产／不改部署依赖；在确认和可行性证据前不实施provider。若公开API不满足时序等条件则保留阻断、提交设计决策，不暗换内部接口。
