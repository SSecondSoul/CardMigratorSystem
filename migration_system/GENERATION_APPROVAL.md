# Token 预算策略与单次计划批准（G3 增量）

日期：2026-11-16。范围：可核查的保守输入上界、只读预算审查、独立持久批准／撤销／领取记录与备份。**没有真实模型调用，也没有开启真实生成执行入口。** 不读取模型密钥，不上传 LangSmith，不调整已有默认额度，不修改旧 Prompt／规则、Vue／San 或历史实验。

## 本轮计数策略是什么

这不是精确 tokenizer。官方 [qwen-plus 规格](https://www.alibabacloud.com/help/en/model-studio/qwen-plus)及[中文规格](https://help.aliyun.com/zh/model-studio/qwen-plus)列出上下文窗口 1,000,000、最大输出 32,768，并说明当前别名与 2025-07-28 快照的关系。官方[用量说明](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/model-usage-statistics)指出实际 token 数依赖 tokenizer，应以 API usage 为准。

本策略从这些规格作**条件性推导**：假设提供方执行文档上下文限制，且请求只含文本、不使用工具／搜索／媒体／思考，则成功受理请求的输入（包括聊天包装）不会超过整个上下文窗口。因此将整个 1,000,000 作为输入预留上界，再加本次输出额度。这里故意比文档最大输入更宽松保守；不是精确 token 数，也不是提供方签发的计数证明或绝对计费保证。

代码 `adapters/token_budget.py` 固定策略 ID、模型／端点范围、文档链接、复核日和指纹。只支持本轮已复核的 qwen-plus／qwen-plus-2025-07-28、北京端点及非思考纯文本配置；未知模型／输出超限／策略过期阻断。复核窗口为 2026-11-16 至 2026-11-23 UTC，不自动联网更新规格。滚动别名不构成不可变底层模型身份承诺，窗口内仍依赖提供方遵守规格；更新目录须显式版本化并保留历史审计能力，不覆盖旧请求。

| 字段 | 默认值与含义 |
| --- | --- |
| input_tokens_exact | null，未做精确 tokenization |
| reserved_input_tokens | 1,000,000，整个文档上下文窗口上界 |
| max_output_tokens | 8,192，沿用原默认输出额度 |
| required_total_reservation | 1,008,192，条件性保守预留，并非预计实际消耗 |
| configured_max_total_tokens | 32,768，原默认额度未变 |
| 默认预算审查结果 | blocked，不自动提高额度、不调用模型 |

如果以后选择这条保守路线，用户必须另行明确决定是否提高单次预算；本轮没有替用户作此决定。也可以继续保持阻断，另行实现与实际商业模型／聊天包装匹配的更紧计数方案。不能直接拿开源近似 tokenizer、字符比率或其他产品的 tokenizer 接口当作本提供方的精确证明。HTTP 错误或响应丢失的费用仍未知，不把模型规格当作所有失败请求的计费上限保证。

## 批准记录与实际调用分开

`GenerationApprovalService` 冻结完整 G1 源／SSM／messages、模型／预算／端点、实现／Prompt 指纹、预算策略和计划指纹。默认 15 分钟有效，最长一小时，且不越过目录复核期限。预算不满足时不会创建待批准记录。

- pending：计划已登记，不可领取。
- approved：本地操作者显式确认“一次调用计划”，且提供精确 request_sha256；不等于已经执行、网络已开启或质量已通过。
- revoked：未领取记录可以撤销，即使已过期或实现漂移；不能借撤销退还已领取名额。
- consumed：领取前核对当前源／实现／策略／到期时间和计划指纹，在事务中登记 claim；同一库只允许一次领取。重复／并发领取、错计划、过期、未批准或已撤销均阻断。

批准／撤销／claim 分别保存不可覆盖的动作文件，报告重新核对身份、类型、请求／计划指纹、时间顺序及归属。过期不会自动续期；同一幂等键仍指向原记录。生成新请求或换预算／模型必须用新的显式意图，不自动继承批准。

claim 只返回 **ClaimedApproval，不是 Qwen CallPermit**。批准名额被领取，不代表提供方调用开始已持久化，不能把 durable_start_recorded 假设为 true；现有 HTTPS 客户端拒绝直接使用该对象。未来调度器还必须把批准领取、真实生成开始登记和原始响应收据接成一个审计闭环，再构造可发送许可。本轮没有该调度入口；原 G2／G3 离线图继续拒绝真实客户端／provider_https。

这是一套受信任本地开发环境的批准／一致性控制，不是公网身份系统、数字签名或恶意数据库篡改防护。程序调用者属于可信代码，CLI 操作属于本机操作者；不可把任意写库权限当成经过认证的人类同意。领取后的实际模型调用数保持未知，不以领取次数代替调用次数或零费用。备份恢复保留已领取名额，但不能同时运行多份数据库克隆，不宣称多主机／多克隆的恰好一次调用。

完整请求可能含源码／SSM 中的敏感文本；动作与请求仅在本地保存，不自动上传。CLI 摘要不打印完整 messages，不能因此认为底层请求或备份不含源码，仍须妥善保管。

## 入口（本轮不要求创建或批准实际记录）

| CLI | 作用 |
| --- | --- |
| generation-budget-review --extraction-id ... --provider qwen --model qwen-plus | 只读，默认预算预期返回 blocked／退出码 2；不是模型错误 |
| prepare-generation-approval --extraction-id ... --idempotency-key ... 加模型／预算参数 | 显式登记 pending；原默认预算不足时阻断，不隐式扩大 |
| generation-approval-report --approval-id ... | 只读审计；不打印完整源码／messages |
| approve-generation-plan --approval-id ... --expected-request-sha256 ... --confirm-single-call | 显式批准匹配的一次计划，不发送请求 |
| revoke-generation-plan --approval-id ... --expected-request-sha256 ... | 撤销未领取记录 |

没有 CLI claim／execute、网页批准按钮、模型密钥输入或自动提交批准。测试中的大预留额度和批准动作仅针对临时合成数据，不是用户已授权的实际模型预算。

## 数据库与当前人工确认点

新增 `0006_generation_approvals`：generation_approvals／generation_approval_files 两表，不修改 0001—0005。备份纳入新表与登记文件，复制库／文件后重新审计，恢复不重置已领取名额。临时库验证 0005→0006 保留原 SSM／传输登记记录。

当前代码 HEAD 为 0006，实际用户库仍为先前已确认的 0005；本轮没有自动升级。重启新代码前应在原窗口 Ctrl+C 停止新系统 API／worker，保留原数据和已有备份，在仓库根目录执行：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py init-db
# 新窗口需要本地启动令牌；不是模型密钥。
$env:CARDMIG_SYSTEM_WRITE_TOKEN = [guid]::NewGuid().ToString('N')
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py serve
```

刷新工作台，确认原 DeliveryPhaseCard 报告和 SSM 仍可查看／下载。无需重提取、重新构建前端或启动 worker；不要在本轮准备／批准真实调用或提高 token 预算。新 schema／实现的工具不自动转换旧备份，不删库、改版本号或删锁绕过检查。

## 验证与后续

专项：`python -m unittest discover -s migration_system/tests -p test_generation_approvals.py -v`（使用新系统虚拟环境）。新增 22 项通过（71.450 秒），覆盖默认预算拒绝、精确用量未知、目录范围／过期、请求／模型绑定、pending／批准／过期／撤销／并发领取、指纹及布尔类型篡改、领取不是传输许可、CLI 无网络、备份恢复与升级保留。

完整新工程 298 项 Python 测试通过（444.975 秒）；原 P1 契约 40 项、前端 Node 22 项重跑通过，check_scaffold 只读检查和 git diff --check 通过。测试使用临时数据库／产物与合成响应，不是全仓测试、浏览器验收或正式迁移结果。前端代码未变，本轮未重新构建。

只读核对实际库仍为 0005_provider_generation，尚无 generation_approvals／generation_approval_files 表；原提取 5fe54b4c976241ddbe29fde9a331535d 仍 completed，请求指纹与请求／收据／SSM 三文件哈希均与既有记录一致。没有创建或批准任何实际调用记录，也没有自动升级用户库；实际 0006 升级和旧证据保留需用户完成后另行确认。

下一步在用户明确预算策略后，把批准消费与真实生成开始／原始响应账本作原子登记集成，先离线验证崩溃／不明结果／重复发送保护，再另行确认一次真实联调。不能把本轮批准机制视为用户同意扩大预算或授权发模型请求。真实评估／修复、LangSmith、few-shot、LoRA 仍按开题路线继续。
