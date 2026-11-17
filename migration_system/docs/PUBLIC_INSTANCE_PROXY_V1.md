# 内部公开实例代理：首轮兼容性验证

后续研究修复见 [v2 记录](PUBLIC_INSTANCE_PROXY_V2.md)。本页及 v1 封存继续保留当时结果，不用 v2 改写历史失败；生产完整契约仍未放行。

日期：2026-11-17。状态：**原型部分兼容，尚未接入生产，任意公开键契约未完成**。

用户已明确授权：“允许内部公开实例代理，先验证兼容性再接入”。这允许调整后续生成组件的导出／加载结构，不等于批准降低语义要求或立即解除阻断。

## 本轮实际实现

实现位于 `research/public_instance_v1/runtime.cjs`，不放进原引擎快照，不由默认 Worker、Prompt 或评估器加载。

- 对外业务 receiver 是独立 Proxy，San 原生实例和 Data 指针由加载方句柄／闭包持有，不作为公开实例的魔法字符串或 Symbol 属性保存。
- 源方法绑定到业务 Proxy。`this[key] = value` 由 JavaScript 原生赋值执行键转换，不先转字符串，不把点号字面属性当路径，也不拒绝未知业务键。
- 声明状态通过 San 的单根 accessor AST 更新，而非动态路径字符串；额外实例属性留在业务上下文。
- `stateKeys` 表示实际声明的状态布局，**不是允许调用的键白名单**。外部键仍可以是任意字符串、Symbol 或需 ToPropertyKey 转换的值。
- 业务的 `data`／`watch`／`dispose` 等属性不覆盖 San 原生字段。加载方继续对原生实例执行 attach、watch、dispose，业务方法使用公开 receiver。
- 对照当前 Vue Options 的 props 只读写入、computed 写入及已绑定方法捕获／覆盖行为；不是完整 computed、watch、组件树或反射实现。
- 原型本身没有 Vue 依赖、不改 San 原型。Vue 仅作为原生对照端；目标浏览器页确认没有加载 Vue。

这是实例边界研究，不是把源 Vue 组件嵌入 San 中执行，也不是新增用户输入或独立互操作产品。当前方法和元数据来自人工构造的合成夹具，**尚未实现从 SSM 自动生成／验证该布局、自动改写真实组件或导出正式 San SFC**。

## 验证事实

固定原生 Vue **3.5.45**、San **3.15.6**，不是把旧 Vue 2 探针结果沿用到新系统。

73 个原生对照场景一致，覆盖普通状态、点号／括号字面键、空／数字／undefined／null／BigInt 键、Symbol、键转换顺序及抛错、业务上下文中的对象／函数／循环值、原生字段同名键、只读行为、computed 基本写入、已捕获方法和 setter 自覆盖等。计数指有限实验，不是任意输入的数学证明。

两张实际隔离 Edge 页面分别运行 Vue 和 San。给业务 `data` 赋 null、`watch` 赋 42 后，原生点击及赋值仍得到相同文本 **0 → 1 → 11**，内部状态指针保持、dispose 成功。San 页无 Vue 运行时、双方无控制台 warning/error。只验证这组功能，不是像素／SSIM 或真实组件质量验收。

最终原型测试 **5 项通过（14.445 秒）**，已含原生与浏览器实验、精确 73 例／单次键转换断言及生产阻断保持断言；既有公开键／控件检查 **11 项通过（24.430 秒）**。两组不相加成迁移成功样本；未全量重跑整个系统、旧 30 样本或模型批次。

## 已观察到的未解决差异

1. **声明状态中的对象响应式身份**：赋同一普通对象后，Vue 的公开读取不是原对象，原型仍返回原对象；只看字段值会漏掉此差异。
2. **公开 `$`／内部实例图读取**：Vue 返回实际内部记录，原型明确抛 `PrototypeCapabilityError`，不伪造内部记录冒充等价。
3. **`setValue('$', value)` 后的公开读取**：赋值动作本身都不报错，但读取结果仍因上一项而不一致。这是实际任意键反例，不从契约中排除。
4. **公开 `$watch` API**：原型未实现 Vue 的 watcher／异常队列语义；不能用加载方原生 San watch 可调用替代此证明。

以上只列已测反例，不是穷尽清单。对象别名／深层响应式、ref、描述符／冻结反射、完整 computed 缓存与副作用、setup／mixins／插件／globalProperties、父子组件、调度／异常和实际 SFC 加载均未完整验证。不以固定键、限制值类型或缩小外部调用范围来消除原契约。

因此结果显式保存 `arbitrary_public_key_contract_complete=false`、`production_admission_eligible=false`。测试通过表示“有限一致性和已知失败都被正确记录”，**不表示这些差异已修好**。

## 生产边界与后续顺序

现有 `source_dynamic_key_contract_unsupported`、原静态错误、候选门和报告不改。生成／修复 Prompt、内置 engine 清单、用户配置、旧库／产物及既有费用记录未改；无真实模型调用、LangSmith 上传或训练。

后续应先关闭对象身份／别名等真实反例，明确并验证公开 receiver 与 San 原生 receiver 的生命周期／事件连接，再实现可审计的 SSM 到代理组件生成与独立静态识别、原生／浏览器反例测试。只有这些门通过，才另立集成版本接入生成、规则修复和评估；不能仅看到 73 例相同就去掉旧阻断或付费复跑。

## 证据与复现

最终证据及本轮源码副本见 `docs/verification/2026-11-17_public_instance_proxy_v1`，SHA-256 封存。第一次原生探针在 warning 控制台前缀处理处失败，修正 core 的 `[Vue warn]:` 与 reactivity 的 `[Vue warn]` 前缀比较后重测；第二次真实发现 `__proto__` 行为不同，按当前 Vue 默认 globalProperties 的继承键 defineProperty 语义修复原型，并新增重复赋值／描述符对照。未改 Vue/San 或阈值适配夹具。

初版 69 例及 5 项测试（12.163 秒）、扩展后 5 项（10.224 秒）为中间记录；最终强化精确场景数及单次键转换断言后重新运行 5 项（14.445 秒），最终记录不与中间重复计数。

在 `migration_system` 内：

```powershell
node research/public_instance_v1/compatibility.cjs --output var/public-instance-v1/选择全新结果.json
& .venv/Scripts/python.exe -m unittest discover -s tests -p test_public_instance_proxy_prototype.py -v
```

输出文件拒绝覆盖。无需重启服务器或设置模型密钥；当前生产任务仍会被同一契约阻断，不应为了试代理而重新提交模型任务。
