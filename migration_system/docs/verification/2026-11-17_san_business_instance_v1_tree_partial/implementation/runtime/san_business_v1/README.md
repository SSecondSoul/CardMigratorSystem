# San 业务实例：可执行核心与离线编译器（尚未发布到主 Worker）

契约：san-business-instance-v1；[范围声明](../../docs/SAN_BUSINESS_INSTANCE_CONTRACT_V1.md)。这里不是另一个 Web 系统，也不启动服务器。默认生产路径和旧 source_dynamic_key_contract_unsupported 仍未修改；**不能将本目录当作已完整修复或已生产接入。**

## 代码职责

- runtime.cjs：在业务 Proxy 中执行源函数，分开原生 Data／生命周期；复用 v7 的独立响应式、watch 和调度桥，新增受控 props 更新、事件及 forceUpdate。`$`／`_` 私有实例图读取明确拒绝，不制造 vnode。
- owner.cjs：有限同步 owner family；在受支持的简单父输入更新路径中批量传 props，先执行子 pre watcher，再运行 beforeUpdate／真实 DOM 更新／updated。复杂绑定、slots／attrs 父输入路径仍明确拒绝。
- component.cjs：真正的 San constructor，自动调用源 Options 的 props 默认值／data／methods／computed／watch／初始化和挂载销毁 hooks；loader 通过 Constructor.business(native) 取业务句柄，业务同名属性不覆盖句柄。实际 data() 返回对象保留身份、描述符和原型，不 Object.assign 克隆。
- compiler.cjs／cli.cjs：只在 Node 解析源码，原 source Options 函数留到已授权的浏览器中执行。采用已有生成 San 的模板／样式，确定性生成业务脚本；绑定 source、模板、运行时和依赖指纹，可独立检验篡改。输出内嵌独立 @vue/reactivity 和 @vue/shared 3.5.45（保留 MIT 头），用于响应式及 toDisplayString 纯显示工具；外部只需要 San，不导入 Vue 组件或渲染器，也不依赖 research／父工程源码。不是零 Vue 依赖。
- registry.cjs：独立导出共享有指纹的响应式内核和 owner 品牌，登记在 San 模块的不可替换 Symbol 属性，不占业务键；不兼容内核明确拒绝。
- dom.cjs：源 AST 自动指定 class／value／checked／selected 策略，在实际 DOM 更新中落实；不修改截图或比较结果。
- identity_projection.py：编译器核实源 :key 与目标 trackBy 完全匹配后，才对模板树应用版本化身份映射；不改原始 DOM 属性或浏览器证据。
- browser_probe.cjs：真正从源 SFC 编译出的独立导出和控件／实例键／生命周期／强制刷新对照。
- public_api_probe.cjs：事件及实际 San 父子 API 反例。它是可信运行时夹具，不冒充 source／SSM 已自动编译组件树。
- value_probe.cjs：从源 SFC 编译，验证 12 类有限值及一个带副作用 toString 的文本和 input 表示；不将有限通过当作任意副作用顺序的完整证明。
- template.cjs／tree.cjs／tree_probe.cjs：新增 Node AST 模板转换和自动内联 Options 组件树，真实浏览器验证多参数／数组／once 事件、父子 props／attrs、ref／$options 身份、祖先错误路由及任意键覆盖方法后的旧事件绑定。没有载入 Vue 渲染器。
- events.cjs：私有 owner 登记上的事件绑定与错误捕获；成员事件引用按渲染快照捕获，非循环引用由独立响应式读取触发失效，避免动态替换回调后仍使用旧监听器。
- controls.cjs：共享内核、禁止混用及未实现回调的明确拒绝控制。
- legacy_business_cases.cjs：基于旧有限对照的新口径副本；92 项业务一致，两个先前通过的私有实例观察分开排除，另保留一个私有 vnode 观察。旧 v1–v7 源码和报告未改。

源码只接受当前已实现的普通 JavaScript、直接 Options 对象导出，不执行 Node 源码；静态内联组件注册已支持，imports、递归或无法静态解析的组件、mixins／未知公共 Options、私有图依赖、this 逃逸、未知动态读、模板辅助函数隐藏依赖等仍明确拒绝。**这些公开特性仍是未完成项，而不是新契约排除项。** 当前还不能宣称所有 slots／attrs／错误捕获／组合式及任意组件树都兼容。

本轮还补了惰性原生失效通知、按实际渲染清理读取依赖、整组件失效与未使用字段过滤；带副作用 getter、隐藏分支及函数值需要持续对照，不靠单次 DOM 相同判等。单根 pre watcher 的递归上限／拒绝／取消待提交 DOM 已有真实对照；不宣称所有跨 root／跨组件递归调度已完成。默认 Worker 仍未接入，完整契约仍为 false。

## 验证与离线重放

仓库根目录：

```powershell
& migration_system/.venv/Scripts/python.exe -m unittest discover -s migration_system/tests -p 'test_san_business*.py' -v
```

开发者可对明确的源文件和既有生成 San 做一次离线重放（不会调用模型，不会改数据库／旧产物）：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/replay_san_business.py `
  --source "你的源组件.vue" `
  --target "此前生成的组件.san" `
  --output-dir migration_system/var/san-business-v1/一个全新目录 `
  --evaluate --trusted-source
```

这里的 target 是内部已生成产物，不是要求最终用户额外提供迁移输入。主链集成后本应自动取生成候选，但**该集成尚未完成**。省略 --evaluate 只编译；执行本地组件需 --trusted-source。输出在 var 下拒绝覆盖，含产物、指纹、实际截图及真实失败报告。旧评估器、DOM 属性规则和 0.95 等阈值未降低；canonical-source 检验仅证明源脚本及接收器绑定，不能冒充旧完整静态验证或整个契约通过。

可附加 `--actions-file 交互步骤.json`；输出精确 UTF-8 字节、props／actions／阈值和 SHA256SUMS，防止 Windows 换行破坏产物指纹。`scripts/verify_san_business.py` 将新专项、旧代理回归、生产公开键专项、探针和一次显式冻结样本重放收集为源码绑定证据；不调用模型、不写实际业务库／队列，任一差异或实现漂移即失败。详见 [当前开发与证据](../../docs/SAN_BUSINESS_RUNTIME_V1.md)。
