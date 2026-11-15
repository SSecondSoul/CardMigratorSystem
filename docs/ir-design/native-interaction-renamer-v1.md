# BatchRenamer 原生双端交互校准 v1

日期：2026-11-15。这是源码迁移验收能力的补充，不增加互操作功能或用户业务材料要求，不调用模型。

## 范围与场景

使用此前冻结的 Vue/San 文件和默认三个 png 文件，不注入替代默认值、不修改组件。三个独立场景：

1. 编辑前缀为 img、起始序号为 3，预览得到 img-3.png / img-4.png / img-5.png。
2. 隐藏预览再显示，表格消失/恢复而业务数组不变。
3. 从默认状态编辑同样的规则，再应用；核对内部文件名、一次 apply 数组载荷，以及载荷与内部 currentFiles 的引用不同。

保持批准口径：零像素容差、差异像素比例上限 0、SSIM ≥ 0.999999999、关键样式/矩形零差异；源 warning/error 阻断。只证明上述默认输入与操作，不证明任意公开键、所有 props 或完整迁移语义。

## 新增实现，不改上一版

- `utils/native_interaction_actions_v2.cjs` 委托 v1 的 click 和 Home/End；新增 replace_text。只接受不超过 80 字符的非空可打印 ASCII 文本，以及界内正整数 number 编辑；目标必须可见、未禁用、非只读且未遮挡。不覆盖清空、IME、任意小数/步长、粘贴、拖拽和自动滚动。
- 先原生 DOM.focus，再发送 Ctrl+A 和 Input.insertText；不注入赋值、不调用业务方法、不 dispatchEvent。读回不等于期望值即阻断，不强行修正。
- `utils/interaction_page_adapter_v2.cjs` 只增加被动事件身份记录，在事件发生时比较 payload 与显式字段 currentFiles。组件脚本、事件处理器、默认值和 CSS 不改。只覆盖挂载后声明的 JSON 单载荷事件；不会更改/试写载荷，不证明任意监听器、初始化前事件或完整别名图。
- `run_controlled_browser_interaction_v2.cjs` 增加显式可选 DOM 集合观察，用于表格消失后记录 count=0，而不是把缺失表格伪造为截图成功。关键元素仍必须唯一可见。每一步两次完整截图及只读观察，延续每页独立上下文和原生归属。
- 新记录 schemaVersion=5，与旧 schema 3/4 分开。生产分派与旧反馈适配器不变，不自动接入生产。

结果、输入、图片、差异图与核验保存在 `data/experiments/analysis/native_interaction_renamer_v1_20261115/`。四对合成对照仅校准执行器：正常编辑、故意不同的输出、源码警告、只读输入。它们不是额外迁移样本。

## 复核方式

项目根目录只读复核，不启动模型、浏览器或服务：

```powershell
python migration_pipeline/check_native_interaction_renamer_v1.py
python -m unittest discover -s tests -p test_native_interaction_renamer_v1.py -v
```

需要重新做浏览器校准时，必须使用新的输出目录；已有证据禁止覆盖：

```powershell
node migration_pipeline/probe_native_interaction_renamer_v1.cjs renamer data/experiments/analysis/native_interaction_renamer_v1_retry/renamer --execute
node migration_pipeline/probe_native_interaction_renamer_v1.cjs controls data/experiments/analysis/native_interaction_renamer_v1_retry/controls --execute
```

## 仍未完成

Analytics 源警告继续阻断，不能从本组件成功推断它通过。其他交互/全30项映射、依赖重绑定、生产反馈接入、全批模型/代码预算冻结仍待处理。任意公开键、通知和异常语义不豁免。旧 24/30 与 token 1,821,544 不变，无新组件人工确认。字体二进制和完整传递依赖未冻结；本机浏览器零差异不外推跨机器保证。CDP trace 不认证任意第三方生产者。
