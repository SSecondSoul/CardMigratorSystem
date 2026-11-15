# 动态赋值接口审查与校验门加固（2026-11-15）

本轮是校验器／候选门漏洞修复，不是动态 `setValue` 迁移修复。TripItineraryPlanner 当前冻结候选代码未改，仍有 `nested_state_mutation`、`source_method_interface_not_landed` 两条阻断，整体未通过、不可投产。旧开发回归为24/30、6失败、0执行异常、1,821,544 tokens；不是独立测试，分数不回填。

## 问题、触发与边界

源码的完整方法为 `setValue(key,value){this[key]=value;}`。Vue 声明状态由实例代理；San 响应式状态放在 `this.data`。在当前冻结输入中，加入空方法、原样实例赋值、动态路径写入或两个有限根分派方案，都能让旧接口诊断消失，且旧候选门允许部分“进展”。**当时整组件仍因共享突变失败，并非曾被本探针判为整组件通过。**

本轮把此校验缺口记为流程修复／remaining_risk，不新增或改写历史人工生产缺陷率。任意键语义未证明记为 unresolved；没有新增人工确认。这是静态与受控原生实例证据，不是浏览器交互验收。

15类输入、6种候选（缺失加5种提案）验证了声明状态及字面量额外属性的映射投影，**不是完整实例/API等价证明**：

| 提案 | 观察到的反例 |
| --- | --- |
| 缺失／空方法 | 全15类不等价 |
| San原样实例赋值 | 六个声明根、强制转换为根的键、San data命名空间 |
| 动态 `data.set(key,value)` | 点号字面键、新实例属性、键强制转换、抛错键、Symbol、San data、数字及undefined键 |
| 六根严格分派＋实例回退 | 强制转换为根的键、San data |
| 先ToPropertyKey再六根分派＋实例回退 | San data命名空间 |

后两个测试提案在六个**字面量**根键的声明状态投影通过，不能升级为任意公开键接口通过。覆盖San的data字段会破坏框架数据指针；探针先记录破坏，再仅为dispose恢复指针，不是生产修复。没有证明一切可能实现均不可能，也没有安装兼容层。

前轮源码调用清查发现14处、六个字面量根键，但未完成所有右值、时序、依赖与外部消费者闭包证明。不能未经授权把任意公开键契约缩成这六个键。

## 实际修改的位置

仅三个既有生产文件相对本轮baseline改变；三个新文件为测试／只读探针。

- `migration_pipeline/utils/method_interface_semantics.cjs`：AST识别完整、非箭头、同步、双参数、唯一 `this[key]=value` 赋值体；不执行源码。缺失方法保留旧接口错误；可调用但未证明的目标新增 `source_dynamic_assignment_unproven`。常量函数别名可解析，带其他效果／含糊选项不冒充精确契约。
- `migration_pipeline/utils/repair_scheduler.py`：独立重新读取前后契约，拒绝丢失契约、漏报缺失／未证明诊断和伪造通过；不能靠清空validation_errors绕过。
- `migration_pipeline/utils/repair_prompt.py`：修复Prompt新增键转换、字面键、声明状态、Symbol与框架命名空间提示；不能仅补可调用方法算修复，不发明provider、shim或调用方协议。
- `migration_pipeline/probe_source_dynamic_setter_v1.cjs`：仅测试用受控原生对照，提案只在内存生成。
- `migration_pipeline/replay_source_dynamic_setter_guard_v1.py`：冻结输入只读重放与30项静态清查。
- `tests/test_source_dynamic_assignment_guard.py`：12项通用名称、AST边界、原生反例、真实校验和stub修复链测试。

生成／服务器Prompt、校验阶段入口与repair阶段确定性改写规则未修改；没有实现自动setter恢复。已有repair前后处理会调用共享语义检测，新增诊断不自动获得一个错误的改写器。人工页、canonical San及已有离线候选均未改。

## 验证结果与影响范围

新增12项定向测试先通过；去掉冗余测试字符串替换后，**重新启动全部17套件、4个并行测试进程**，273/273通过，516.458秒。35个相关实现／测试文件测试前后SHA-256一致；不是全仓库测试，也不是把旧261项与单项复测拼接成273项。

冻结失败候选的真实ValidateStage与独立候选门重放：五个可调用提案都产生新诊断且被拒绝；包括缺失方法在内六种伪造清空诊断的候选均被拒绝。所有提案经确定性prepass仍不改写；当前原候选仍2条错误。

30项仅作新规则清查：22/30有精确动态赋值源码契约；21/30目标可调用但语义未证明，其中19项历史通过、2项历史失败；另1项是Trip原本缺失方法，保持原错误。**这21项是新增未证明风险，不等于已经证实21个业务缺陷，也不是新的全批次失败率。** 规则保守性及任意公开API是否属于验收范围需要独立明确，不能用“原24件无新增诊断”描述本轮。没有逐项修改或重跑模型，原成绩保留。

共享记录写入的额外深层同步观察者Vue3次／San1次、days空值／洞位的求值阶段差异仍保留；本轮未解决，不删除其诊断或声称完整行为等价。

## 证据索引与复现

本目录 `audit.json`、`native_observations.json`、`inventory.json`、`tests.json`、`implementation.json`、`environment.json`、`SHA256SUMS.txt`；输入封存于同级 `formal_30_v4_dynamic_setter_guard_v1_input_20261115`，含规则前验证／门结果和原生对照。引用上一轮filter包的校验清单和源／候选指纹，不覆盖它。

三个新脚本／测试保存完整源码；其余相关文件保存前后指纹，不是完整源码／环境备份。Vue2.7.16仅作本地原生oracle，San3.15.6；无新生产依赖、无运行时互操作。

只读重放：`python -m migration_pipeline.replay_source_dynamic_setter_guard_v1`。17个精确测试命令与原始stderr见tests.json。Notebook仅追加2单元，保留前119单元及metadata；编译全部代码单元并仅执行新增只读单元（根目录、Notebook目录），不启动Notebook UI。历史指纹单元仍属于历史代码，不承诺最新代码下Run All。

## 下一步与授权边界

已向用户询问但尚未收到选择：按源码和必要依赖实际可达调用另立新协议，还是保留任意公开键契约继续阻断。在答复前，旧范围不变；即使选择前者，也必须另做可达调用／右值／时序证明，保存旧失败，不能直接宣布六根分派通过。

模型调用0、新人工确认0、服务器／浏览器未启动；无commit或push。不直接付费复跑、不准备独立测试。
