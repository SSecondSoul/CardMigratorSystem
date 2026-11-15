# S2浏览器反馈分流／离线修复预览 v1（2026-11-15）

已将冻结浏览器结果转换为按来源分开的机器反馈，并验证与现有RepairPromptBuilder的**离线预览**接口。**不是生产自动repair已接入，不是实际修好Analytics或新30项通过。** 本轮回放不启动浏览器／服务器／模型、不执行生成组件；相关旧保护测试包含既有原生方法探针，不是新浏览器验收。报告技能用于保留观察、复核与生产放行的不同证据等级。

## 为什么需要独立分流

现有repair主要接收validation和visual_eval_errors；浏览器raw日志若直接混入，就可能让模型去修改源Vue警告、截图设施问题，或因像素相同而忽略错误／捕获不完整。新增独立反馈层，不改现有visual_eval、RepairStage、调度器／候选门或Prompt文件。

反馈保留四个通道：source_oracle、target_runtime、visual_observation、evaluation_integrity。评估证据／捕获阻断优先，其次源基准复核；所有较低优先级事实仍保留。无差异只给visual_match_only，不认证组件综合通过；review_target_candidate也不等于自动执行许可。

## 冻结真实证据的回放

完整核验上一轮130payload清单及外部固定指纹，再回放corrected_run、repeat、首轮run、gutter_counterfactual和controls。没有重新截图或改原报告。

| 记录 | 新机器动作 | 保留事实及边界 |
| --- | --- | --- |
| corrected_run及repeat各5场景 | 前4项visual_match_only，Analytics review_source_oracle | 10条源诊断不是San错误；7项矩形及1326／1625高度差保留，无伪造SSIM |
| 初始run | 5项review_evaluator_or_evidence | 旧录制缺完整repeatObservation，不冒充新准入证据；不否认旧PNG曾观察到相同 |
| gutter_counterfactual | review_evaluator_or_evidence | styles／extent不稳定是评估复核，不自动改目标代码 |
| controls中的高度差 | review_target_candidate，但target_feedback_eligible=false | 这是未绑定源Vue／目标San代码的HTML控制，不冒充组件修复输入 |
| controls中超预算／横向溢出 | review_evaluator_or_evidence | 不根据错误描述文本猜测业务修法 |

真实5场景本轮生成目标修复预览0、目标运行诊断0、模型调用0。没有把4个静态视觉一致场景计为新迁移率，也没有因为源端警告阻断就删除目标布局观察。source_oracle的console原始channel及内容保留；本轮不按“Vue／San”字样猜来源。

## 证据与准入保护

从可信冻结协议取得SHA256SUMS外部指纹，核验成员／路径／哈希、页面HTML绑定、原始／重复PNG和CRC、重复观察及关键选择器映射。重新计算关键矩形／样式差异，检查指标数值、像素分母与PNG尺寸，不将调用方passed／eligible／stable／clean或空styleChanges标记当作权威。记录变动、非有限值、错误分母、未知schema等拒绝；图像不等高不缩放、不编造像素／SSIM。

这里**没有独立解码IDAT／透明度／滤波或重算像素／SSIM**，指标是固定到已知评估器及旧封存包的观察。校验清单只证明与外部指纹一致，未知生产者重新生成清单不能成为可信测量。v2没有原生page/session登记表，旧事件只在栈帧含唯一合法loopback /page/N且session不冲突时保守归属；实际服务端口身份并未独立登记，不能宣称生产级provenance已完成。无法归属或冲突仍阻断。

## 与修复阶段的连接完成到哪

新增build_repair_preview每次独立重读固定证据，不消费调用方编辑的路由JSON。两侧完整、源正常、确有目标问题且绑定Vue／San组件时才允许生成离线Prompt；当前source/code的UTF-8哈希和props也必须匹配渲染输入。只把目标运行／视觉问题映射到既有RepairPromptInput，保留validation错误／警告和白名单旧目标visual问题；未知或源端旧visual诊断不静默删除／转发，而是要求复核。

合成夹具的正向路径实际调用现有PromptBuilder，验证追加browser_critical_style_mismatch等反馈，同时保留source_dynamic_assignment_unproven和旧目标DOM诊断，state保持不变；禁止网络调用的测试内可成功构造预览。**这证明接口与过滤合同，不是实际修复组件，也不是模型能按该Prompt修好的证据。** 原有任意公开键、通知、异常及独立候选门仍需执行。新层所有repair_dispatch_allowed恒false，尚未接入批处理或RepairStage自动请求。

## 测试与保护范围

新50项、旧页面适配39项、现有repair Prompt／循环34项、公开动态键保护12项，共**135/135分别运行通过**；不是全仓库或旧273项综合campaign。50项包括来源文字伪装、源／目标并存、其他页面诊断隔离、未知来源、伪造成功／clean／stable／路由、过期代码／props、旧visual源诊断、证据篡改与正向预览。单元PNG／JSON是合成夹具，不是新增浏览器实测；旧repair测试使用stub，不新增真实模型请求。

新增4文件：utils/browser_feedback_v1.py、replay_browser_feedback_v1.py、tests/test_browser_feedback_v1.py及说明文档。65个既有相关实现／测试／依赖文件、3个人工配置、6个冻结源／目标不变。Notebook只追加保留旧133单元与元数据；旧24/30、6失败、1,821,544 tokens不变。无新依赖、人工确认、commit或push；未打开Notebook UI，仅解析JSON、编译并执行新增只读证据格。

## 下一步与剩余边界

本步解决“反馈不能混类、不能凭成功标志绕过证据、旧语义错误不能被视觉覆盖”的离线数据路径；尚未形成生产修复全闭环。下一项先补原生page/session登记和逐页持久化隔离，再明确正式错误级别、状态／资源策略、阈值及输入规范；源oracle警告须明确实验处置，不擅自吞掉／自动改源。随后才能冻结生产协议并接入批处理反馈，不直接付费复跑全30或进入独立测试。

仍未证明SSM与源码的完整绑定、所有业务状态／交互、永久稳定、未知SFC、跨机器字体／浏览器，亦不提供恶意Python调用方安全边界。本研究不新增Vue/San互操作、provider或调用方业务协议。使用说明：[browser-feedback-routing-v1.md](../../../../docs/ir-design/browser-feedback-routing-v1.md)；机器结果见verified_replay及action_matrix.json。
