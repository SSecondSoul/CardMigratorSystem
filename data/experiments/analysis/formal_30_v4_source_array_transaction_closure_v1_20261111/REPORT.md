# 源数组移动事务闭环 v1（2026-11-11，离线开发回归）

原始批次仍为 24/30、6 失败、0 执行异常、1,821,544 tokens。本轮接续父模板依赖闭环的冻结 TaskManager 中间件；不从 Vue 新生成，不改 canonical San 或人工页，不回填分数，不继承人工通过，不是独立测试。真实模型请求 0。

既有 _normalize_mutated_state_array_aliases 根据正则找到 alias/mutator/writeback，可在复制后仍保留错误提交时机，也无法证明整个方法与源一致。本轮 residual_v2 前后处理均禁用这一路较弱回退，保留非 residual_v2 legacy 行为；改用 source_array_transaction_semantics.py/.cjs，按完整 Vue 与导出 San 父方法、声明数组及整个规范化方法体证明“两次 splice 的局部移动事务”。不是按 TaskManager 名称特判。

仅支持一个 const 根数组别名、同一末尾成功 if 中的解构删除/单元素插入、纯局部索引调整和简单 findIndex 比较。比较源全部参数/默认布尔值、早退、过滤/原始索引、分支、拖拽状态和通知原文。拒绝未知效果/控制流、循环/提前返回、额外 splice、别名逃逸/重赋值、嵌套对象写、实时数组再读、未知回调、重复/条件提交、fallback、全局 Array 遮蔽/显式重写。浅复制仅隔离数组结构，不声称通用记录深复制或绝对证明外部运行时原型未被篡改。

自动改写只复制别名初始化，并把唯一数据提交放在最终插入后、清理拖拽状态/通知前。旧代码 tasks.splice 修改存储数组在先；旧 this.data.set('dragStartIndex',null) 后才 [...tasks] 提交。复制后若仍按旧位置提交，观察拖拽状态的逻辑可能见到旧列表，故必须恢复源“列表先改变，后续效果再发生”的顺序。元素对象保持身份，未移动分支不提交，不为源码已有缺陷猜新逻辑。

前处理、stub 模型返回后处理、共享 repair Prompt、验证器与候选保护同步。新增 source_array_transaction_not_landed / source_array_transaction_analysis_unavailable；即使 spread 去掉了旧 mutation 诊断，丢失提交或改变 guard/index/通知也不能通过新契约。旧 generation/服务器 Prompt 未改，不启动服务器。

开发初检暴露 Babel cloneNode 不保留 start/end，旧位置匹配导致分析器报错并原样返回，没有改坏产物；改为按原语句索引定位 clone。首轮 19 项、2 失败（57.001 秒）：测试错误预期紧凑 fixture 必被 legacy 行正则识别，以及 oracle 只识别 export default 而真实 Vue 使用 CommonJS。改测试使用真实 legacy 输入、共享 sourceParent 提取原方法，生产规则未放宽。后续精确结果以完整日志为准，开发摘要不冒称完整失败日志已保存。

修正后历史/针对组合 40/40（156.071 秒）通过；一次后续组合执行 68 项、1 error（219.945 秒），唯一 error 是命令误写不存在的 formatter 测试选择器，67 个实际测试通过，不称该轮全通过。按真实名称单独执行 formatter 测试 1/1（42.967 秒）通过；再从稳定清单重跑完整套件，不拼接散测作为完整通过。

加入完整调度器和源未知事务拒绝用例、加固原型字段与绑定丢失保护后，新规则单独 21/21（63.498 秒）通过。开发只读 30 项回放亦完成且不写文件；最终证据使用随后稳定代码重新执行的完整套件与回放，不把预检当成冻结结果。

完整套件 594/594、0 失败，879.305 秒，完整输出 unit_tests.txt。真实安装 San 组件数据存储上比较源方法 oracle：向上/向下、过滤可见列表、末尾插入、null/undefined/越界、同一任务、目标已消失；核对原数组未变、元素身份保留、一次提交、清理/通知见到新顺序。真实 TaskManager 用原冻结源方法与精确目标方法的最小运行夹具，不触发整个组件的初始化/定时器；因此不是浏览器原生拖放证据。

实际 bounded_prepass_v1 调度器注入冻结产物提供器，不调用生成服务；用真实 ValidateStage/VisualEvalStage、禁止任何模型请求的 repair client，1 个确定性步骤、0 次 LLM，得到 final_passed=true，代码等于独立规则。这里 final_passed 只表示离线静态/轻量初始 DOM 自动门通过，不是新批次或人工/全交互通过。

累计 30 项重新静态验证/编译，只 TaskManager 改写；24 个原始通过件原字节且仍通过。仅 TaskManager 重做轻量初始 DOM，其余视觉标记沿用前层。TaskManager 按现行校验 2→0 条错误（旧 mutation 与同一新源事务的重叠诊断），validation_passed=true，migration_hints_not_landed 警告保留。正向接受、反向拒绝、固定点与组合前处理一致；原始批次不曾因此变成 25/30 或更高。

TripItineraryPlanner 上轮新暴露的外部 dayCountGetter/filter 渲染依赖仍失败，本轮不处理、不豁免。完整 TaskManager 初始化工厂/watch 时机、浏览器弹窗/实际拖放、持久化/计时器交互仍是 remaining_risk；不能从静态零错误推断全部业务已等价。下一步审查完整初始化和拖拽链，再决定是否进入人工验收，不立即付费复跑。

运行清单 359 项，SHA256SUMS 覆盖新包代码、派生 San、回放、报告和完整日志；旧冻结包、协议和分数不改，未 commit/push。
