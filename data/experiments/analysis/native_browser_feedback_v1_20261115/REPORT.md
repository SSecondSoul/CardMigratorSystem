# S2：原生浏览器封存证据与反馈适配 v1（2026-11-15）

## 完成内容

新增 `native_browser_feedback_v1.py`，直接验证并读取受控评估器schema3，不改旧v2反馈模块或浏览器评估器，不通过临时重签／降级格式复用旧转换器。完成原生来源核验、反馈分流及现有RepairPromptBuilder的**离线审核预览**，尚未生产自动修复接入。

按vue-san-validation-report技能区分设施证据、源基准问题、目标观察与残余风险；Notebook仅追加，不把测试通过写成新人工验收。

## 输入检查与错误处理

- 外部固定的封存指纹、文件路径／内容、HTML／PNG指纹／块CRC／尺寸与绑定manifest；拒绝非有限数、重复JSON key、未支持schema和未封存输入。
- run／实际origin端口／序号与角色／context-target-session唯一性、两份原生主frame/target响应、executionContext与捕获关联。
- 从session重建事件所有者；核对事件owner副本、序列及exceptions／consoleErrors／blocked副本，拒绝删改诊断。错误文字不能改变所有者；URL仅检查冲突，不能为未知session指派来源。
- 校验CDP调用和响应身份、未完成或错误响应、处置数量／frame查询、HTTP请求计划、浏览器退出与清理；保留记录中的销毁后事件疑点。
- 不信complete／passed／eligible／clean标志；重复观察也必须一致。固定主题、语言／时区／DPR／时间等应实际生效，稳定但环境错仍复核。原生21项样式属性加rect须齐全；viewport不接受溢出裁切。
- 指标仅校验固定证据的维度／范围／分母一致性，**不独立解码PNG或重算SSIM**。样式差重新计算；1326／1625等尺寸差不缩放成虚假指标。
- 不完整／未知或设施问题先复核，源oracle其次，目标运行／视觉候选再次；低优先级事实保留。所有repair_dispatch_allowed和semantic_gate_bypass_allowed仍false。

这些是对已知可信评估器封存记录的一致性核验；别人重签一份报告不获得真实性认证，不是恶意Python调用方安全沙箱。

## 真实封存回放

从上轮96payload封存包读取6组记录，组件绑定另核验早前130payload中的prepared manifest，无新浏览器或模型。replay／verified_replay／final_replay是三次**离线转换**，不是三次新组件运行。

| 原始记录 | 场景数 | 分流 |
|---|---:|---|
| controls | 4 | 全部设施／证据复核（浏览器断连／不完整） |
| context_smoke | 1 | 设施／证据复核（GPU崩溃） |
| controls_retry | 4 | 全部设施／证据复核（旧trace／证明不完整） |
| controls_final | 4 | 全部设施／证据复核（含故意跨页反例，缺最终原生双观测） |
| controls_verified | 4 | 全部设施／证据复核（故意跨页URL冲突与网络拒绝） |
| frozen_components | 5 | 前4项visual_match_only，Analytics review_source_oracle |

frozen_components来自VolumeControl、BatchRenamer、AnalyticsDashboard的既有5个静态场景10页，不是独立测试集。Analytics保留10条source_oracle、0条target_runtime、7项矩形差、source[1280,1326]／target[1280,1625]，无像素或SSIM伪分数。真实目标修复预览0，没有新迁移通过率；历史成绩仍24/30，不回填。

## 离线预览的边界

每次重新读取可信固定证据；源／未知／设施问题不进入目标修复。当前Vue／San UTF-8源码SHA和props必须等于渲染输入，包由独立指纹绑定，不接受调用者改反馈包旗标。合成正向用例实际调用现有PromptBuilder，在禁止网络下保留source_dynamic_assignment_unproven和原目标DOM诊断，caller state不变；这不是模型效果或组件修复泛化证据。

目前只对manifest单模块提供预览。多模块可评估／分流，但主文件SHA不能证明当前依赖图没变，在自动依赖重绑定完成前拒绝预览；不要求用户发明业务调用协议或额外手填元数据。完整SSM与候选语义门仍需独立校验，任意公开键及通知／异常边界未解决、不豁免。

## 测试与文件保护

新90项（83合成保护＋7旧原生记录核验）＋旧登记53＋旧反馈50＋SFC封装39＋repair34＋动态键12＝**278项定向测试通过**，六suite最终完整输出在tests.json。非全仓库、非之前273项campaign。最初83／88项开发测试也成功，但不重复计入278；本轮无新失败尝试。旧repair测试用stub，无付费模型。

75个旧相关文件、3个人工配置、6个冻结组件输入与旧96payload封存指纹不变。新增4个实现／测试／说明文件；现有Notebook和范围进度文档只追加，保留旧137单元与metadata。未改生产Prompt、规则、调度、浏览器、组件产物或旧分数；无浏览器／模型／新人工／依赖安装／UI／commit／push。

## 剩余工作与下一步

协议尚未冻结：需明确错误等级、源oracle警告处置、状态／交互场景与视觉阈值，列出生产接入前候选门和失败行为，审核后才接批处理。不能把离线预览当自动执行权限，也不直接付费全量复跑或独立测试。

现有CDP trace未保存每条命令完整params/result或诊断与处置统一时间线，所以本层核对原始响应／登记／传输摘要一致性，不能独立重建全部时序或认证未知生产者。原记录中的时序风险保留。仍未完成完整依赖图当前绑定、全交互、预置存储／登录、跨机器字体／浏览器等价等；能力边界如实披露，不新增互操作／provider或业务调用协议。

接口、命令与限制：`docs/ir-design/native-browser-feedback-v1.md`。以下Notebook核查只读运行，不启动浏览器或Jupyter UI。
