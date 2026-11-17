# 源模板 HTML 空元素解析修复（2026-11-17）

## 缺陷与范围

原任务 `3d3d69c7760045e1bd0c741f7cf3638b`，源码 `InvoiceLineEditor.vue`，停止于 preflight，模型 0 次、Tokens 0。原任务只有 request 与 failure 两个文件；本轮先复制两文件及源输入，核对三个文件哈希，不恢复旧任务或回填报告。

源码中的 `<input>` 是合法 HTML 空元素，不缺结束标签。旧 `browser/evaluate.mjs` 的源 AST 投影调用 `@vue/compiler-dom.baseParse`，没有带入 HTML 空元素等平台规则，因而误报 `Element is missing end tag.`；错误经过 Python 边界后被归为 `browser_evaluation_blocked`。

对原源码的独立对照中：Vue SFC 解析、带 HTML 规则的模板解析及 Vue 模板编译通过，旧 baseParse 失败。这是新评估实现的兼容性缺陷，不是源组件问题，也不是模型、API Key 或浏览器启动失败。

## 修改

- 源模板投影使用 `@vue/compiler-dom.parse` 的 HTML 平台解析；保留原始 Vue 字节，不把所有 input 改写成自闭合，也不增加正则补标签。
- 对 `<input>`、`<img>`、`<br>`、`<hr>`、`<wbr>` 验证合法普通／自闭合写法的投影相同；不会把后续兄弟节点错误包进空元素。
- 不安装忽略错误的 onError 回调。缺失／错配的 div、span、textarea、strong 等非空元素继续阻断；San 目标侧仍走原有 San 模板及 Babel 语法检查，没有放宽目标检查或通过阈值。
- 区分 `source_template_syntax_error`、`source_sfc_syntax_error`、`source_script_syntax_error`。诊断包含消息、绝对 UTF-16 偏移、1-based 行列、定位精度及有限源码片段；位置不可用时不伪称精确。
- Python `SourceParseError` 只接受已知源解析类型，最多 16 条；重算行列和片段并绑定当前上传的源码，不采信外来 excerpt／额外字段。未知浏览器错误继续使用通用代码，不回显原始 stderr。
- LangGraph 将诊断写入本地 failure 证据与报告的 `state.failure_diagnostics`，并保存源哈希；LangSmith 仍只收到原有摘要，不上传源码／片段。
- 工作台在原“运行与质量报告”区域显示中文类别、原始代码、行列和转义的片段。模型尚未调用时明确提示；旧报告没有这些诊断则保留历史缺失，不补造。

没有删除适配层或重构调用链。本轮没有修改 SSM、生成／修复 Prompt、模型预算、目标正规化规则、用户的 `system.toml`、`SsmPanel.vue` 或 `ssm-model.ts`。

## 离线证据

- 修复前：`data/experiments/evaluator_calibration/2026-11-17_modular_source_void_elements_preflight_v1`
- 修复后：`data/experiments/evaluator_calibration/2026-11-17_modular_source_void_elements_preflight_v2`

两次都从同一原源码出发，哈希 `9b50005a20314dd9c1f52db9496c6092d8f2838958955be0fa0350db7c77a8df`，原文件不变；前者 blocked，后者 completed。独立工具只执行 Node 源解析，不启动渲染浏览器、不初始化数据库、不调用模型、不上传 LangSmith。清单与实现哈希分别保存，不覆盖。

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/replay_source_preflight.py `
  --run-id 3d3d69c7760045e1bd0c741f7cf3638b `
  --output-dir data/experiments/evaluator_calibration/另选一个全新目录
```

这个 completed **仅证明源预检查解除，不证明该组件已完成迁移或质量通过**。本轮没有为 InvoiceLineEditor 生成或修复 San。

## 回归与部署

`test_modular_source_template.py` 新增源解析、精确阻断、UTF-16 定位、错误边界、零模型调用图，以及真实浏览器／工作台到临时数据库的测试。错误片段以文本显示，不执行上传的模板；普通前端查询不触发模型。

浏览器空元素对照用例曾混入 input 静态 value 属性的框架表示差异（Vue 保留属性、San 写控件属性），该差异不是本轮修复目标；对照夹具改用 placeholder 隔离空元素解析，未改 DOM 比较规则来忽略该差异。

专项 12 项通过（33.895 秒），TypeScript／Vite 构建与前端 Node 22 项通过。完整模块回归和最终证据校验见 [开发记录](DEVELOPMENT_20261116.md)。这些工程测试不进入模型迁移通过率分母。

前端 dist 已重新构建。部署需重启 API 和 migration-worker、刷新网页，然后另建任务绑定新实现。数据库结构不变，无需 init-db；原失败任务保持历史结果，不能按新代码恢复旧绑定。仍需单独验证后续真实生成与质量评估。
