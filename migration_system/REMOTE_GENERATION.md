# G3：Qwen 传输边界与生成契约映射（离线验证）

日期：2026-11-16。此增量实现真实 HTTPS 协议的客户端代码、响应／用量检查和纯 P1 产物映射函数；**尚未接入真实调用账本，没有开放真实模型执行入口，没有发生模型调用**。不能据此宣称整个真实生成阶段接入完成。

后续增量：[G3 原始响应登记闭环](RECORDED_GENERATION.md)已实现独立账本、LangGraph 与备份的离线验证协议，并新增 0005 显式迁移。下文保留传输边界初次实现时的状态；真实计数／批准和提供方执行仍未接入，不能把离线收据映射为真实版本。

## 已实现的内容

- `adapters/qwen_transport.py`：把 G1 的完整已封装消息原样映射到 Qwen 请求；绑定模板、端点、请求字节、输入计数证明描述和超时配置的指纹。只支持明确的 qwen-plus 非思考文本配置，未知模型不静默替换。
- 网络默认禁用。密钥只能由调用者显式传入内存，不读取环境变量或配置文件，不写入计划／报告，不输出原始异常。仅允许指定的阿里云 HTTPS 主机与固定路径，禁用代理继承、重定向和自动重试，限制响应大小。不执行返回的 San 脚本。
- 输入 token 上界必须绑定当前 messages 哈希和模型，并带计数方法、计数器版本指纹及聊天包装覆盖声明。缺少上界、仅估算、不含聊天包装，或者输入上界＋输出限额超过总额时，预检阻断。**当前尚无经过验证的真实计数器接入；测试中的计数器与上界为合成数据，不能拿来解锁真实调用。**
- 响应必须包含可核对的模型／响应身份、单条 assistant 文本、stop 和有效 usage；工具调用、思考输出、截断、无效代码形状、模型漂移及超额均不产生可接受候选。usage 必须是非负整数且总数等于输入与输出之和，布尔值不算整数。
- 即使输出无效／截断／超额，也保留已知 usage。超时、HTTP 错误或缺少有效 usage 保持未知，不报 0 token／零费用；调用可能已受理，标为 review_required 而不重试。HTTP 超时是传输等待限制，**不是跨进程硬截止或提供方取消保证**。
- `reporting/provider_generation.py`：纯一致性映射函数，逐项核对请求快照、源／SSM 字节、响应、收据和候选引用；通过后构造严格 P1 `ArtifactRevision(origin=generation, parent_revision_id=null)`，并用原 P1 加载器往返验证。只表示生成产物，不给出质量通过；migration_quality_status 仍为 not_run。

官方协议依据：[Qwen 兼容 Chat Completions API](https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions)、[模型用量说明](https://www.alibabacloud.com/help/en/model-studio/model-usage-statistics)（2026-11-16 查阅）。本配置使用适配旧 qwen-plus 的 max_tokens 和显式 enable_thinking=false；不把新模型参数直接套到旧配置，不把字符数当成准确 token 数。输出限额与实际 usage 分开检查，不能据此保证提供方计费绝对不超额。

## 与 G1／G2 的隔离

G1 的 external_calls_permitted=false 不修改；G3 传输计划不构成真实执行授权。[G2](GENERATION_LEDGER.md) 的表和图仍只接受 OfflineGenerationClient，明确拒绝 QwenHTTPSClient。G2 的候选仍是 offline_client_test，contract_revision=null。网页开发夹具、SSM 面板、CLI 和 worker 都没有新增真实模型执行开关。

客户端的 CallPermit 仅声明未来可信调用方提供的计划／尝试／授权事实，**它不是独立认证、授权或数据库持久化证明**。当前客户端内的已用尝试集合仅防止同一实例重复发送，不能保证重启、并发或跨进程不重复。将两个布尔值设成 true 不能替代真实调用开始登记、批准流程和未决结果复核。

纯映射函数要求未来调用方提供真实账本审计后的不可变证据。哈希只证明输入彼此一致，不能证明响应来自提供方，也不能证明快照早于调用。专项测试使用完整但合成的请求／响应／收据，只验证一致性拒绝与 P1 字段映射；**不是可登记到实际实验的真实生成证据，也不能把测试响应换个 provenance 名称就当成真实调用。** 当前没有实际生成记录使用该映射函数。

## 本轮不做的事

不读取用户模型密钥、不发送模型请求、不上传 LangSmith、不改变实际数据库 schema、不新增迁移、不重提取已有 SSM，不修改旧 Prompt／规则、Vue／San、冻结实验或 tests/manual 页面，不 commit／push。实际库继续是用户已升级的 0004；本轮无需再次 init-db 或重跑旧提取。

## 离线验证

专项命令（仅临时目录、合成传输响应；无需模型密钥）：

```powershell
& migration_system/.venv/Scripts/python.exe -m unittest discover -s migration_system/tests -p test_qwen_transport.py -v
```

新增 26 项：消息与配置绑定、主机限制、输入上界与预算、缺少授权声明／禁网、超时不重试、代理／重定向／响应限长、错误脱敏、usage 保留与类型／总数、输出超额、工具／思考响应、G2 拒绝真实客户端，以及源／SSM／快照／收据／候选的一致性拒绝和严格 P1 映射。正向映射使用合成证据，不作为模型或质量证据。

完整新工程 254 项 Python 测试通过（224.444 秒）；原 P1 契约 40 项和前端 Node 22 项重跑通过，check_scaffold 只读检查通过。前端代码未变，本轮未重新构建或进行浏览器验收。这些是工程测试，不是全仓测试或 30 样本迁移回归。

本轮再次只读核对实际库为 0004_generation_ledger，四张 G2 表存在；原 DeliveryPhaseCard 提取仍 completed、请求指纹及请求／收据／SSM 文件哈希与原记录一致，主夹具运行仍 finished／not_run。没有写入实际生成记录或改变原提取。相关值仍以 SSM_EXTRACTION.md 与 G2 记录为准，不据此宣称全部业务表不变或真实生成验收通过。

## 下一步：完成 G3 的受控执行接入

先增加与 G2 离线记录隔离的真实生成账本及显式迁移，将不可变计划／可信计数证明／批准范围在调用前登记；开始尝试先持久提交，原始响应和收据按不可覆盖文件登记。恢复必须核对当前绑定，复用已提交收据；结果不明时禁止自动重发。补齐并发、进程崩溃、断点、备份／恢复及超时测试，再把纯映射接到已审计的真实证据上。

可信 token 计数或经论证的上界策略尚待落地，不能用本轮测试声明替代。真实执行入口、密钥注入、一次调用批准和预算需另行明确；首次真实调用之前仍须停下确认，不在本轮隐式启动。生成联调后继续接目标评估／修复图、LangSmith、few-shot 与 LoRA，不能由传输测试代替这些研究任务。
