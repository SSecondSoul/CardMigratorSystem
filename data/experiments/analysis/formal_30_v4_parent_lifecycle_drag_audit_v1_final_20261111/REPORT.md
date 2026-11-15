# TaskManager 父生命周期与完整拖放声明链诊断（2026-11-11）

本轮只读检查上层子组件初始化冻结候选；不是修复完成、不是新批次或独立测试。原成绩仍为 24/30、6 失败、0 执行异常、1,821,544 tokens。0 模型请求；不改生产规则/Prompt、canonical San、人工页或旧冻结包，不 commit/push。

## 已复现与尚未证明

1. 父 attached 先 loadInitialData/startAutoSync/通知，后注册 tasks/settings 监听。空存储、已存数据、关闭自动保存、损坏 JSON 四个场景直接运行真实 San 应用钩子，初始化的监听回调与保存次数均为 0；统计显式 updateStatistics 正常，后续嵌套编辑/设置替换可以触发监听，disposed 清除模拟 interval 并保存。源 Vue 使用声明式 deep watch（在 mounted 之前建立），但本机未执行 Vue runtime 的异步监听队列，不能把预期保存次数/计时器顺序冒充已证实；不能简单把 San 注册移到初始化前，San 同步监听可能在恢复 settings 之前就保存、重启 timer，需单独证明源顺序与副作用。

2. Vue TaskItem.onDragStart(e) 有 dataTransfer.setData('text/plain',index) 和 effectAllowed='move'，目标缺失这两项。提取冻结源函数用相同模拟事件执行，源写入且发出索引；目标实际 San 声明监听器只发索引。这不是本轮引入的回归，且当前静态验证仍 0 错误，说明现有源 DOM/数组事务规则没有覆盖该事件体副作用。浏览器是否因此阻止原生拖拽尚未执行，不能宣称在所有浏览器必现。

3. San 3.15.6 watch 两个形参，第三参数 deep/immediate 无效。真实 San 观察证明嵌套 data.set 与 data.splice 触发根监听；直接修改 data.get 返回对象、再同引用 set 不触发。不能认为已有 {deep:true} 等价 Vue 深监听，也不把源直接突变一律安全。

## 已通过的局部检查

解析冻结目标父/子模板，使用已安装 San 的 getEventListener 和 Component.fire 实际解释声明，模拟 dragstart→子自定义事件→父索引→drop-on/列表 drop→moveTask→dragend。6 场景（向下/向上、列表末尾、自身、取消、禁用）列表顺序均与提取的源 moveTask 函数一致，元素身份保留，原数组不被改坏；drop.stop 与 dragover.prevent 确认执行。过滤后的索引正确到达父方法，结束后拖拽索引清空。这里手工绑定真实声明并注入合成事件，不运行 DOM attach/浏览器原生手势，不能替代交互验收。

## 验证与边界

新增诊断测试 14/14，0.329 秒，无跳过；完整 614 项不是本轮重跑，引用上轮冻结日志（999.702 秒），两者不合并为新全套通过。生产运行清单 363 项逐项保持一致；本轮使用的 Node 模块与 San bundle 另保存哈希。本次 Python 3.14.7、Node v24.19.0、San 3.15.6；不是假定历史 cardmig/Python 3.10/Node 20 环境一致。浏览器页 San 仍为 3.15.3，不声称前者验证过。

诊断脚本开发的两次失败不隐去：首次错误假定源 export default，实际为 CommonJS module.exports；随后直接加载 San 未打包 parser 内部模块触发循环依赖。均为测试装置错误，未作生产规则更改；最终读取实际安装 san.dev bundle，只在内存导出原有 getEventListener 函数，函数体/依赖包原字节不改，给导出父构造器配置 SFC 外层模板后再实例化。不把这两次失败计为组件新缺陷或修复回归。

预冻结 audit_v1_20261111 的 7 项 payload 保留并校验，不覆盖。最终只调整测试职责：正式回归用例核对冻结清单而不永久禁止未来生产规则更新，CLI 仍逐项校验实时 363 项身份。最终重新执行同样 14 项测试；运行观察与预冻结完全一致。两份日志不拼接为 28 项或全套通过。

未重跑 30 样本/轻量 DOM，不增加“已通过数”，不继承人工确认。TripItineraryPlanner 外部渲染辅助依赖风险保持上层记录，不豁免。Notebook 只追加证据，不覆盖历史。

## 下一步

先为原生事件方法体建立基于完整源 AST 的有边界规则（保留 guard、dataTransfer 操作、参数、emit 次序），同步验证器/候选保护/正反例；用本冻结输入验证，不靠 Prompt 文字宣称闭环。父监听注册另需覆盖异步批次、恢复存储、自动保存关闭、计时器创建/取消、销毁清理的源运行 oracle；未证明前 fail closed，不自动搬动。两项完成后再讨论完整调度器/30 项离线回放与人工验收，暂不付费复跑。
