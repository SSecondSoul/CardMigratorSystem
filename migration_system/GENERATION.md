# San 生成接入 G1：请求边界与只读预览

日期：2026-11-16。当前是生成阶段的第一个开发增量，**不是已完成真实生成接入**。不调用模型、不上传 LangSmith、不新增数据库迁移或网页入口，不改变开发夹具和已有 SSM 记录。

当前代码已推进到[预算／批准增量](GENERATION_APPROVAL.md)及 0006，实际用户库仍为先前已确认的 0005，本轮未自动升级。下文保留 G1 初次实现时的边界／测试／迁移状态；当前启动和升级要求以最新文档为准，真实模型执行仍未开放。

后续更新：[G2 登记／断点／备份](GENERATION_LEDGER.md) 已实现离线账本与真实图，并新增 0004 显式迁移。下文保留 G1 阶段边界和当时测试结果；其中尚无持久化的描述仅针对 G1，不能据此跳过当前 0004 升级。真实模型传输仍未接入。

## 已实现

- `prompts/generation.py`：核对旧生成 Prompt 的两个完整源文本指纹后，仅加载指定纯构造函数和 class 规则常量。不 import 原 Flask 路由、原编排或模型工厂，不执行上传的 Vue／SSM 脚本。旧 Prompt 中的数据访问、类名、生命周期／watch、事件、内联子组件规则原样保留。本轮没有改写或优化 Prompt 内容。
- `stages/generation.py`：从已审计且 completed 的登记 SSM 构造不可变请求字节，绑定源输入 ID／路径／哈希、SSM 提取 ID／路径／哈希／原请求指纹、实现／依赖／P1 指纹、完整 system／user messages 及哈希、模型和预算配置。每次读取返回独立副本；同一实现及输入下可重现相同请求哈希。此处“封装／冻结”仅在内存中，**尚未作为预注册请求持久化**。
- 模型参数使用明确字段，不接收 API key、端点或任意 headers。默认拟议参数为输出上限 8192、总 token 32768、超时 240 秒、temperature=0、单次生成、零修复／规则。它们是预览参数，不是已获授权的付费预算或正式实验协议。
- `adapters/generation.py`：显式注入 `OfflineGenerationClient`，没有默认网络客户端／密钥读取／重试。类型标识只约束可信测试代码，不是阻止恶意客户端联网的安全沙箱。
- 离线输出检查：提供者／模型身份、完成原因、可选 usage 类型与已报告预算、UTF-8／2 MiB 上限、纯文本 template／script／style 形状。失败保留错误码，不暴露原始异常。结果为 `offline_client_test` 候选，不执行组件，不生成 P1 ArtifactRevision，也不冒充真实 generation 或迁移 pass。
- `application/generation_preview.py` 与 CLI：只读已有登记记录，核对源／SSM 字节，输出指纹和配置；不写文件、不创建运行、调用或版本，不重跑提取。

没有继承以前的正确 San 产物：这里是新的生成请求预览，而非修复。后续修复节点必须显式引用生成／上次接受版本及候选父版本，不能把重新生成解释成原产物上的修复。

## Prompt 绑定来源

源文本指纹统一将 CRLF／CR 规范为 LF，再按 UTF-8 SHA-256：

| 旧文件（仅只读） | SHA-256 |
| --- | --- |
| local_server/api/evaluation_routes.py | `71818205059132bb15330aa4d474ec4269ebed19b8337a9ea00ef3d459972548` |
| migration_pipeline/utils/class_binding_contract.py | `bf83e708c7e6c11713f246a3ec9f16f02aba8276020faac770a1a5243de23e66` |

两个文件全部核对后，AST 选择 `_build_generation_prompt` 和字面量 `CLASS_BINDING_RULE`，只编译该受信任构造函数。不是一般不可信 Python 沙箱。任何旧文件变化都会阻断预览，需要显式复核与新绑定，不能自动接受新 Prompt。此受限适配先验证现有规则无损接入；未来若统一归档到新 prompts 包，需版本化并验证输出一致或显式记录变更。

## 只读命令

G1 初次验收时默认库为 0003，无新增迁移。当前 G2 代码要求先显式升级到 0004（见顶部链接）；升级后预览仍不需 worker 或模型密钥。在仓库根目录执行：

```powershell
& migration_system/.venv/Scripts/python.exe migration_system/scripts/run_system.py generation-preview `
  --extraction-id 5fe54b4c976241ddbe29fde9a331535d `
  --provider qwen `
  --model qwen-plus
```

可选参数：`--max-output-tokens`、`--max-total-tokens`、`--timeout-seconds`。没有 `--execute`、模型调用或产物保存选项。输出 `generation_request_preview`、external_calls_permitted=false、persistent_registration=false、actual_model_calls=0、migration_quality_status=not_run。它不登记入备份，因为没有新记录或文件；不能将终端摘要冒充预注册执行证据。

已由助手对实际 DeliveryPhaseCard 记录运行预览，并在同一实现下重复核对结果一致、所有业务表逻辑行摘要前后不变，未重提取／修改用户数据。当前 Prompt messages 指纹为 `d9a5dc1ef37deeb8fd15afa7b7ade35bc149f164fc039c854d635c3b0805d007`；源与 SSM 沿用已登记哈希。请求还包含当前实现绑定，所以后续代码修改会改变请求哈希，不应据此回写旧请求。

## 当前不具备的保证

1. **没有真实网络传输、调用开始账本、持久收据、San 版本登记、恢复或备份接入。** 离线函数显式每调用一次就调用一次假客户端；没有宣称跨进程恰好一次、收据复用或自动重试。客户端异常结果不明时只报错，不重试。
2. 总 token 只是拟议上限。输入 token 尚未真实计数，缺少 usage 保持 null／usage_unknown；不能声称费用预算已事前保证。实际调用前须接提供方能力／输入计数、余额预留、输出上限和不明用量处理。
3. timeout_seconds 是待运输层执行的配置，不能中断进程内假客户端。真实超时、取消、提供方受理但响应丢失等，必须先补持久调用状态再实现。
4. 完成原因 stop 和 SFC 文本形状不证明 San 编译成功、规则落地、语义等价或视觉／交互通过。后续真实检查不由此替代。
5. 旧 v1 提取的源证据可作为预览输入，不补造其缺失的 P1 请求。未来新生成请求必须在调用前独立冻结，不能追认旧请求或改写原夹具结论。

## 验证结果

新增 18 项测试（16 项纯边界、2 项临时真实登记 SSM／CLI 集成），覆盖 Prompt 来源漂移／缺失、规则保留、不可变请求与参数指纹、源／SSM 内容及引用核对、配置／权限／预算类型、客户端无默认传输、不重试／错误脱敏、模型身份／截断／缺少 usage、文本输出形状和原报告不变。真实提取使用临时库与产物，不写用户实验库。

新工程全量 203 项 Python 测试通过（204.229 秒），原 P1 契约 40 项和前端 Node 22 项重跑通过；前端代码和依赖未修改，没有新增浏览器验收。这些是工程边界／回归测试，不是 30 样本迁移实验或真实模型质量结果。

## 下一步 G2

先增加与夹具隔离的生成请求／调用尝试／不可覆盖文件与候选版本账本，设计显式增量迁移和备份校验；绑定本步完整请求，不仅保存摘要。调用开始必须先持久化，返回收据与候选先提交，checkpoint 断点复用已提交结果；在途结果不明或实现漂移则复核、禁止自动再调用。接入独立 LangGraph 节点后用假客户端验证崩溃、幂等、归属／哈希、预算和备份恢复。

完成这些保护后，再明确真实提供方／模型／预算和一次受限联调授权。真实生成的产物只能标为“生成完成、质量未执行”，仍需目标校验、编译、结构、视觉／交互评估及修复图。LangSmith、few-shot、LoRA 按开题路线继续实施，不因本步预览存在而视为完成。
