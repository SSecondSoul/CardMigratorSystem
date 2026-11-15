# 父异步监听有界闭环 v1（2026-11-11）

原批次仍24/30、6失败、0执行异常、1,821,544 tokens。0模型请求；复用开发冻结件，不是新生成/独立测试。不改canonical San、测试页、旧证据，不commit/push。

新增source_parent_watch_semantics.py/.cjs：只支持纯初始数据、默认async且deep=true的根字段监听（无handler参数），完整源回调、mounted/beforeDestroy、传递效果方法逐一AST对应；拒绝未知阶段/外部依赖/mixins/同步或immediate选项/递归/handler写回被监听根字段。字段和组件名不特判。限定源调用/条件回调；保守规范化Data API、只读别名、相邻临时赋值，不跨越可改变状态的效果猜测等价。

每实例闭包队列，按源注册次序去重，Promise微任务执行时读最新状态，清理pending后调用，销毁取消未运行任务；try/finally复位队列，不吞异常。不声称跨框架错误捕获/抛错策略等价，只覆盖正常完成回调；非原生Promise/异常存储/任意raw对象突变/未知动态键仍未证明，不能据此宣布全组件通过。

对照暴露额外的同值克隆入口：源已有键同值赋值无通知，而目标克隆整个settings触发监听。只在完整源动态属性赋值与目标四段clone写回/后续效果精确匹配时，加Object.is同值保护，保留后续通知。只证明已声明的现有设置键；未知动态键、原型键、新增键的Vue2非响应式语义未证明。绝不改回调业务效果来凑队列通过。

residual_v2前处理/返回后处理、共享repair Prompt、验证器、候选保护同步；新增source_parent_watch_not_landed/analysis_unavailable与lost_source_parent_watch_contracts。generation/服务器Prompt和legacy前处理不改。旧错误/断言保留并补新诊断/组合规则，旧冻结分数不回写。

最终独立完整测试672/672、0失败/跳过，1238.068秒。累计30项静态/编译回放仅TaskManager改写，原24通过件原字节仍静态通过；Trip外部依赖仍保留。TaskManager当前1→0错误、migration_hints_not_landed警告保留；仅它重做轻量初始DOM。真实调度器冻结输入1确定性步/0 LLM、现行自动门通过，不等于业务/浏览器通过。

源Vue2.7.16对照装置保持业务操作，只去掉已不适用的naive反事实版本（两处显式版本列表），另去除框架hook/注册/低级通知的记录差异，保留全部业务方法、存储、timer事件。修前不匹配；修后5场景×18阶段=90对，完整业务效果序列与状态均匹配，包括autoSave=false不误写、同轮多改合并、声明顺序、同值设置、dispose前取消、原生销毁后不触发。不是只比较最终画面。San attached应用钩子直接调用，无DOM attach；源空根render不测子组件/原模板，应用存储/timer模拟，真实框架Promise队列，San3.15.6并非人工页3.15.3。

实现过程的失配保留：最初装置构造了未使用的非法AST片段、后对数组直接调用节点生成比较报错，均已改正；首次别名规范化不对称/误把延迟箭头当即时效果，先拒绝了updateStatistics/updateSyncInterval，后加双端与即时范围证明；初次仅队列版在autoSave已false场景多重启timer，促成同值入口修复。未应用这些失败候选到canonical，不计为已实施生产回归。完整稳定验证独立重跑，不拼接散测。

冻结清单382项。下一步在不扩大证明范围的前提下处理异常策略与未知动态键边界，再决定是否人工整页验收；本轮不付费重生成、不放宽规则使未证明分支通过。
