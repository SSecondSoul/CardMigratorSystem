# 原生浏览器证据反馈适配 v1

本层将受控评估器 `schemaVersion:3` 的封存记录转成离线反馈。新增文件 `migration_pipeline/utils/native_browser_feedback_v1.py`；不修改旧 `browser_feedback_v1.py`，不把新版降级或改字段冒充旧格式。它不是浏览器启动器、生成器或自动修复调度器。

## 输入与核验

`convert_recording(bundle_directory, expected_seal_sha256, recording_relative, binding_reference=None)`：

- 外部可信实验协议固定 SHA256SUMS.txt 指纹，校验封存成员、相对路径、输入／结果／图片内容。拒绝重复 JSON key、非有限数、错 schema 与未封存文件。
- 重新核对 runId、实际 loopback origin／端口、页面序号与HTML、context／target／session唯一性、声明比较对角色、两份真实 target/frame 响应、主 frame／executionContext、捕获与登记的 session/context 对应。不根据错误文本或栈帧猜所有者。
- 从登记 session 重建事件所有者，核对 owner 副本及重复诊断集合，防止源诊断被丢掉或插入另一页；未知session、冲突／外部URL、不同executionContext及原记录中的处置后事件风险进入 evaluation_integrity。嵌套异常及异步父栈URL也检查；URL只用于发现冲突，不用于给未知session指定来源。
- 核对 CDP 调用／响应 ID、错误及生命周期数量、两次frame查询、关闭／销毁、HTTP请求计划与退出／清理。不能靠 complete／passed／eligible／clean 等标志取得许可；独立证据不足则阻断。
- 固定环境仅接受当前已校准的 v3 值和仅含width/height的viewport，检查页面实际观测的主题、DPR、语言／时区／时间等。重复稳定但主题用错仍不作为可信证据。
- 绑定原始／重复PNG指纹、块／CRC与尺寸，重新算关键样式差，不接受调用方给出的空diff。沿用已封存评估器指标的范围／分母一致性核查；**不重新解码像素或独立计算SSIM**。不同尺寸不缩放、不编造分数。

`binding_reference` 是独立封存的组件包装 manifest 引用，三字段为 `bundle_directory`、`expected_seal_sha256`、`manifest_relative`。它可以引用此前封存包，不复制或重签旧证据；核对其页面HTML与本次捕获相同。只有源Vue／目标San身份及源码指纹均存在时，才能标成已绑定组件对。

这些指纹由仓库实验协议提供，不要求使用者为Vue源码另写业务协议，也不认证未知生产者重签的报告。本层不是恶意Python调用方的安全沙箱。

## 输出与优先级

按 `evaluation_integrity > source_oracle > target_runtime/visual_observation > visual_match_only` 推荐人工／离线审核动作，同时保留较低优先级事实。视觉一致不认证迁移通过；所有 `repair_dispatch_allowed=False`、`production_protocol_frozen=False`、`semantic_gate_bypass_allowed=False`。

跨页网络拒绝属于设施／证据复核，不是目标方法修复指令。完整记录中任何未知来源或未完成处置使本次场景保守阻断；不能选择性删除负例来使其他比较合格。浏览器进程stderr仍作为原始环境证据，不按其中的“ERROR”文本猜框架错误。

## 离线修复预览

`build_repair_preview(state, *, bundle_directory, expected_seal_sha256, recording_relative, binding_reference, scene_index)` 每次重新读取固定证据，不接收调用方修改后的反馈包作为权限：

1. 必须只有可信、完整、已绑定的目标运行／视觉问题；源、未知、设施问题拒绝。
2. 当前Vue／San源码UTF-8指纹和props必须匹配捕获输入。不能把旧正确产物默认当成当前代码。
3. 目前预览仅支持manifest中单模块的组件。多模块源码虽可评估与分流，但只有主文件SHA不证明当前依赖图未变；在实现自动依赖重绑定前拒绝预览，不另造调用方业务材料要求。
4. 调用既有RepairPromptBuilder产生审核文本，保留原validation及认可的旧目标visual诊断；未知／源端旧visual不静默删除或转发。
5. 不改调用者state，不清除任意公开键或其他语义阻断，不调用模型，不给候选产物放行。目标反馈可审核与自动执行是两件事。

## 复现与结果

```powershell
python -m migration_pipeline.replay_native_browser_feedback_v1
# 可选新目录，拒绝覆盖：
python -m migration_pipeline.replay_native_browser_feedback_v1 `
  --output-dir data/experiments/analysis/my_new_native_feedback
python -m unittest discover -s tests -p test_native_browser_feedback_v1.py -v
```

六组旧封存的原生记录离线回放；5个真实静态场景为4项visual_match_only＋Analytics源基准复核。10条源诊断、7项矩形差与1326/1625高度差不变，真实目标修复预览0。故意跨页负例／崩溃／证据不完整均复核，不冒充组件失败率。

90项新测试包括合成正向Prompt预览、源目标文字伪装、身份／副本／序列篡改、退出与环境错误、伪造成功标志、seal／JSON／图片／props与代码漂移等。原生21项样式属性加rect必须齐全，viewport不允许隐藏纵向溢出。单元夹具不是新浏览器实测或真实组件修好。未启动新浏览器或模型，不安装依赖，不改生产Prompt、规则、组件或旧成绩。

## 尚未完成

需明确错误等级、源oracle警告处置、状态／交互场景和生产阈值，冻结受限生产接入协议并验证候选语义门后，才能接入批处理。CDP trace未保存每条命令完整params/result或诊断与销毁的统一时序，因此本层核对已知记录一致性，不能独立证明所有时间关联或任意生产者真实性；记录的处置后风险绝不被清除。

仍未证明完整SSM绑定、全部依赖图当前一致、全交互、登录／预置存储或跨机器环境等价。任意公开键与通知／异常风险不豁免；不新增Vue/San互操作、provider或业务调用协议，不直接全量付费复跑或宣称独立测试结论。
