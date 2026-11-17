# 公开实例代理 v2：响应式、watcher 与实际读取修复

日期：2026-11-17。**研究修复已验证，生产尚未接入，完整任意公开键契约仍未完成。**

本轮沿用用户“允许内部公开实例代理，先验证兼容性再接入”的授权。v1 源码、4 个差异及原封存包不改写；不把新结果回填成 v1 已通过。

## 相比 v1 修复了什么

| 问题 | v2 实现 | 本轮检查 |
| --- | --- | --- |
| 声明状态对象返回原对象，响应式身份不一致 | 使用同版本独立 `@vue/reactivity` 内核，保留原 data 对象和内核身份缓存 | 普通对象、数组、Map、循环、共享引用、root 自引用、ref 解包及原 ref 保留 |
| `$` 只能抛错 | 建立独立逻辑实例记录，公开 proxy／data／ctx 等真实别名；San 实例仍隔离 | 不只检查 typeof；比较身份、root／parent 基本关系及 raw data 身份 |
| `$watch` 只有未实现错误 | 基于内核 watch、组件局部 effect scope 及 pre/post 队列 | 默认合并、sync、immediate、once、暂停／恢复、cleanup／stop、数字 deep、路径／函数 getter、this 绑定及 dispose 取消 |
| computed 每读一次都重新求值 | 使用内核 computed 缓存与失效 | 重复读取不重复调用 getter，状态变化后重新求值 |
| 仅 Proxy 中的状态变了，San DOM 不刷新 | 私有原生 Data 接收者读取跟踪，实际读取一次并订阅所访问依赖 | 嵌套别名及逃逸 ref 的实际 DOM 刷新，不靠另跑模板或深遍历值 |
| watcher 错误处理改变 getter 结果 | 显式记录错误的策略适配，错误处理函数返回值不当作 getter 成功值 | getter／callback／cleanup 分类、多个 cleanup 继续执行及异步 rejection |

## 新依赖与原生实例边界

v1 没有 Vue 依赖；**v2 新增使用独立响应式内核**，不能继续笼统称为“目标没有任何 Vue 依赖”。当前使用本目录已经安装的 `frontend/node_modules/@vue/reactivity` **3.5.45**，没有下载新依赖、升级锁文件或加载父仓库代码。

San 目标页加载 San 和独立 VueReactivity，**不加载 Vue 组件／渲染运行时**，没有 createApp／Vue 组件嵌套在目标里。它仍是需要审计、封装并记录许可证的候选运行时依赖，不是已经内联到正式生成 SFC 的成品。

实现位于 `research/public_instance_v2`：

- `runtime.cjs`：复用 v1 的字段／错误类型，业务 receiver 与原生 San receiver 分开。
- `compatibility.cjs`：当前 Vue 3.5.45／San 3.15.6 原生对照。
- `browser_probe.cjs`：普通根与 ref 根的四张隔离页面、实际 DOM 和时序。
- `controls.cjs`：原生借用接收者、通知次数、描述符恢复和不支持配置拒绝等控制。

San 直接保留 initData 对象，因此 v2 在初始化时将原生镜像根分开，避免同步时污染源 raw data。`Data.get` 的跟踪只覆盖本实例实际访问，不修改 San 全局原型，不通过额外深遍历调用对象 getter；根变化只发一次原生通知，结束后恢复原先自有方法描述符。

独立内核当前使用 development 构建的调试触发钩子；缺失该钩子时在修改实例前拒绝，不默默用 production 构建替换。未来若要发行生产构建，需重新证明或替换这项实现，不能删掉检查放行。

## 最终证据

- **94 个有限原生对照场景一致**；包括原 73 个键场景，以及对象身份、实际 watcher、错误策略和额外 getter 求值控制。这不是任意输入的数学证明。
- **4 张实际 Edge 页面**：source／target × 普通／ref 根。计数 0→1→11 一致；逃逸 ref 变更后均显示 21；嵌套别名修改后均显示 9。
- 普通场景各有 **6 条**、ref 场景各有 **8 条**实际 pre/post 回调，值和回调时 DOM 文本一致；显式防止比较两个空列表得到假阳性。
- **8 项边界控制成立**：借用接收者、无全局原型修改、raw 身份、单次根通知、原生根写入、嵌套原生写入明确拒绝、自有描述符恢复、不兼容内核构建在修改前拒绝。
- 最终 v1/v2 合并回归 **13 项通过（32.993 秒）**，包括 v1 原有 5 项和 v2 新增 8 项；此前同组 19.760 秒为中间结果，不重复计数。
- 既有公开键／控件回归 **11 项通过（28.267 秒）**。未全量重跑系统、30 组件或模型批次，工程测试不计论文迁移成功样本。

最终源码和 native／browser／controls 结果共 **8 payload** 封存于 `docs/verification/2026-11-17_public_instance_proxy_v2`，SHA-256 核验。v1 封存与原生产运行时指纹保持。

## 还没有完成什么

1. **逻辑实例记录不是完整 Vue 私有渲染记录。** `vm.$.proxy/data/ctx` 等基本关系已建立；`vm.$.vnode` 仍明确未实现，不用空对象或伪造 vnode 消掉反例。`typeof vm.$ === 'object'` 不能证明整个实例图等价。
2. **原生 San 嵌套不可变写入、silent／force 等策略、子组件作用域尚未闭合。** 直接经私有 `Data.set('objectValue.x', ...)` 的未证明路径会拒绝；源业务方法通过公开 receiver 修改嵌套状态的读取／渲染场景已分别验证，二者不能混为一谈。
3. **完整组件生命周期／祖先异常捕获、所有调度交错／全局插件／反射仍未证明。** 逻辑记录只提供已列出的关系，不冒充 Vue 的全部渲染状态。错误试验只证明显式记录策略下的根级场景。
4. **尚未自动从 SSM 编译真实组件、导出 San SFC、改写真实加载器或接入规则／候选门。** 本轮仍为合成夹具，不能据此宣布 ProductFilterPanel 等真实组件已通过。

这些限制没有通过固定键白名单、限制值类型或缩小外部调用契约被豁免。报告继续写 `arbitrary_public_key_contract_complete=false`、`production_admission_eligible=false`，原 `source_dynamic_key_contract_unsupported` 保持，不增加付费模型调用。

## 开发过程中的真实失败

v2 初始修复了旧四项表层探针，但新增强检查继续发现问题：cleanup 数组回调无接收者时错误使用 this.call；错误处理函数返回值被当作 getter 值；代理嵌套数据已变而 San DOM 仍是 0；捕获 watcher 日志过早得到两个空列表。分别修正回调分派、返回策略、实际读取订阅及取证时点后重测。

曾观察到“公开 ref 已为 6、原生镜像仍为 1”；最终逃逸 ref 与嵌套 DOM 对照均通过。中间过程结果在 var 中留存，但并未逐轮封存所有源码；只有本页列出的最终包绑定最终源码，不能把旧中间 JSON 说成当前版本证明。

## 当前使用方式

在 `migration_system` 内执行离线验证：

```powershell
node research/public_instance_v2/compatibility.cjs --output var/public-instance-v2/全新文件.json
node research/public_instance_v2/controls.cjs
& .venv/Scripts/python.exe -m unittest discover -s tests -p 'test_public_instance_proxy*.py' -v
```

浏览器测试需要本机浏览器与已安装的本目录 Node 依赖，不需要模型密钥。现在无需重启 API／Worker，也不应为尝试本原型而重新提交付费迁移。下一步应先处理上述未闭合边界和可审计的真实组件编译／加载连接，再考虑新集成版本；旧源码、生成产物、失败／费用、配置及 Prompt 不动。
