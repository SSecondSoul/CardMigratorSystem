# 原生双端交互校准：VolumeControl v1

日期：2026-11-15。用途是改善迁移验收，不是新增互操作功能。

## 已批准口径与未完成事项

用户“确认采用”已独立登记于 `data/experiments/protocols/native_browser_criteria_adopted_20261115/approval.json`：零像素差异、SSIM 下限 0.999999999、关键样式及矩形零差异、源码警告/错误阻断。原待审核草案保持原样；这份新确认不授权模型调用或全批次冻结。

本步只完成一个组件、两个场景的本地原生输入校准。生产分派接入、全 30 项场景映射、其他交互类型、依赖图重新绑定和模型/代码全批次冻结仍未完成。

## 实际可执行场景

- 范围键盘边界：默认 45 → Home 到 0 → End 到 100 → Home 到 0；`change` 载荷依次为 0、100、0。
- 静音恢复：默认 45 → 点击静音到 0 → 点击恢复到 45；载荷依次为 0、45。

每个场景在独立 Vue 2.7.16 / San 3.15.6 上下文运行，默认 props 不注入，冻结 SFC 的脚本不改写。旧草案的“输入 60→0→100”未执行；本版用显式原生 Home/End 场景代替，不追溯宣称旧计划完成，也不代表拖拽测试。

## 实现和观察边界

- `utils/native_interaction_actions_v1.cjs`：只允许按钮 click、range 的 Home/End。使用 CDP DOM.focus 和 Input 命令；不调用业务方法，不使用 dispatchEvent，不接受脚本载荷。目标缺失、禁用、遮挡或超出视口即阻断，不自动滚动。
- `utils/interaction_page_adapter_v1.cjs`：沿用已有受限编译/打包器，额外被动监听显式声明的根事件和 DOM 输入。不改变组件脚本、CSS、状态或事件处理器。只支持 JSON 可序列化的单载荷根事件；挂载前事件不在覆盖内，监听器存在性敏感组件也不能据此推断等价。
- `run_controlled_browser_interaction_v1.cjs`：每一步两次全页截图及观察，保存会话/上下文归属、状态、事件、DOM 文本/值、关键样式及稳定性。后续步骤阻断时保留初始证据，并将未执行步骤保留为 not_run。
- 结果 `schemaVersion=4`，不冒充原 schema 3。现有反馈适配器和生产入口未接入本版。执行器的 passed 只表示画面对照；独立核验器再检查预期状态、事件、原生输入和身份绑定，仍不签发综合迁移通过。
- `check_native_interaction_volume_v1.py`：只读核验实际记录、PNG 哈希和历史文件。它不运行浏览器或模型，也不修改旧分数。

## 对照与证据

五对合成对照：正常点击、两端增量故意不同、源码 console.warn、目标缺失、目标禁用。后四类必须不通过；源码警告即使画面完全相同也阻断。它们是测试执行器的对照，不是五个迁移样本。

证据目录：`data/experiments/analysis/native_interaction_volume_v1_20261115/`。包含执行输入、原生会话记录、逐步状态/事件、截图、差异图、独立重算、单元/定向回归测试和报告。

只读复核（项目根目录）：

```powershell
python migration_pipeline/check_native_interaction_volume_v1.py
python -m unittest discover -s tests -p test_native_interaction_volume_v1.py -v
```

再次运行本机浏览器必须使用新的输出目录，不能覆盖本次证据：

```powershell
node migration_pipeline/probe_native_interaction_volume_v1.cjs volume data/experiments/analysis/native_interaction_volume_v1_retry/volume --execute
node migration_pipeline/probe_native_interaction_volume_v1.cjs controls data/experiments/analysis/native_interaction_volume_v1_retry/controls --execute
```

## 不可推导的结论

不证明其他 props、任意公开键、异常/通知、拖拽、异步业务、嵌套依赖、其他运行时或所有组件等价。`source_dynamic_assignment_unproven` 等既有语义阻断保持；本步不放宽契约、不修补生成产物、不调用 LLM、不修改旧 30 项结果（24/30，token 1,821,544）。本机字体二进制尚未锁定，不能把本次零差异外推为跨机器承诺。
