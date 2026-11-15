# 浏览器反馈分流与离线修复预览 v1

范围：将已封存浏览器证据转换为机器可读反馈，验证不会把Vue源警告、目标运行问题、视觉观察或捕获阻断混成同一种错误。本入口**尚未接入生产批处理或自动repair调用**，不修改旧visual_eval、RepairStage、候选门或Prompt文件。

## 分类与优先级

| channel | 含义 | recommended_action／处理 |
| --- | --- | --- |
| evaluation_integrity | 未完成／不稳定捕获、来源不明、传输／清理问题等评估阻断 | review_evaluator_or_evidence；不能根据异常文字猜目标修法 |
| source_oracle | 有归属依据的源页面运行／console诊断 | review_source_oracle；保留目标差异，但不生成目标修复预览 |
| target_runtime | 有归属依据的目标运行／console诊断 | 源及评估证据正常后才可进入目标复核 |
| visual_observation | 原尺寸、像素／SSIM及关键样式／矩形差异 | 源正常且证据完整后才可进入目标复核 |
| 无差异 | 只有声明静态场景视觉一致 | visual_match_only；不触发修复，也不代表组件综合通过 |

优先处理评估阻断，其次源基准问题；这只是处理优先级，所有通道事实都保留，不丢弃较低优先级问题。`review_target_candidate`不是自动repair许可。高度不等保留原始尺寸，不生成伪造SSIM或热图；有差异但没有绑定源Vue／目标San代码的HTML控制样例，也不能冒充组件修复输入。

## 运行

在项目根目录运行，只读取冻结文件，无浏览器／服务器／模型请求：

```powershell
python -m migration_pipeline.replay_browser_feedback_v1

# 可选择保存到新目录，拒绝覆盖
python -m migration_pipeline.replay_browser_feedback_v1 `
  --output-dir data/experiments/analysis/my_new_browser_feedback
```

本回放脚本固定读取本轮baseline引用的130payload封存包及其外部指纹；旧65项相关实现／测试和人工页若已改变，先新建协议／基线，不回退用户文件来绕过校验。

API：`convert_recording(bundle_directory, expected_seal_sha256, recording_relative, bindings_relative)`。`expected_seal_sha256`必须由可信冻结协议提供，不能信任未验证报告自带的“校验通过”。校验封存清单及路径、HTML绑定、原始／重复PNG指纹和CRC、重复观察、关键映射、指标数值／分母及计划；重新计算关键样式差异，不依赖调用者传入的passed／eligible／空styleChanges标志。PNG这里只验证块／CRC及头部，不解码IDAT／透明度／滤波，也不独立重算像素和SSIM；这些是绑定到已知评估器的封存观察，未知生产者重新签一份清单不能变成可信测量。

## 与现有修复代码的边界

`build_repair_preview(state, *, bundle_directory, expected_seal_sha256, recording_relative, bindings_relative, scene_index)`重新读取并分流固定证据，不消费调用方改过的反馈JSON或“允许修复”标志。只有完整、源基准正常、明确绑定Vue／San代码且确实有目标问题时才生成**离线审核Prompt**：

- `vue_source`、`generated_code`的UTF-8指纹必须匹配渲染输入；props也必须匹配，布尔／数字不能混淆。换行／编码规范尚须正式协议固定，当前严格拒绝不一致，不自动规范化成相同。
- 只追加目标运行或视觉问题；源、未知来源或评估问题阻断预览。旧visual诊断仅有限白名单允许合并，源端或未知code不静默删除／转发，而是要求复核。
- 调用已有RepairPromptBuilder生成预览，保留旧validation错误／警告、已认可旧visual问题；不改调用方state，不把visual_eval_passed或validation_passed写成true。
- 原有动态公开键及其他语义候选门仍须独立执行。预览不是候选修复产物，不能靠像素改善豁免接口／通知／异常语义。
- 顶层与场景的`repair_dispatch_allowed`恒为false；没有API请求、自动修复或生产放行。不能把`target_feedback_eligible`当作自动执行权限。

## 本轮真实回放

corrected_run／repeat各5场景：4项visual_match_only；Analytics为review_source_oracle，10条源诊断未变成San失败；7项关键矩形与1326／1625高度差照常保留。真实场景目标修复预览0、模型0。滚动条反事实进入评估复核；合成高度控制有尺寸差，但无组件绑定，不能生成组件修复预览。旧分数不回填。

50项新测试包含正向离线Prompt预览、来源文字伪装、伪造pass／clean／stable／路由标志、旧证据被改动、错误分母、非有限数、props／代码过期、旧源警告误入目标修复等反例。合成PNG／JSON仅单元夹具，不是新浏览器实测、真实候选修好或目标修复泛化证明。

## 尚需完成

旧v2没有原生page/session归属表；当前诊断只有在调用栈含唯一合法loopback `/page/N` 且session无冲突时才作**旧记录的保守归属**，不根据“Vue”“San”字样猜来源。它没有验证实际服务器端口身份，也不是新生产session登记证明；无归属或冲突仍阻断。下一步应先补原生session／page登记、逐页持久化隔离、正式错误级别与场景／阈值协议，再考虑生产适配。现有源码基准警告不能擅自吞掉或自动改源，处置必须有明确实验记录。

此层不证明SSM内容与源码对应、全部业务状态、永久稳定、交互、未知SFC构建或跨机器字体／浏览器等价，也不是恶意Python调用方安全沙箱。正式接入时仍需完整协议与独立候选校验；本研究不新增Vue/San运行时互操作、provider或调用方业务协议。
