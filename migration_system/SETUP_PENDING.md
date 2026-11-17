# 开发后待补配置清单

本轮不索取或读取真实密钥，不启动付费调用、远程上传或训练。以下由用户在系统开发交付后补齐；不要将密钥写进仓库、Notebook、截图或聊天。

## 必需与可选资源

| 项目 | 当前状态 | 补充位置／操作 |
| --- | --- | --- |
| 数据库版本 | 用户现有库已确认 0006；新代码为 0007 | 停旧 API／worker，显式 `init-db`；旧数据不需重传 |
| 云模型 API key | 未配置，开发期间未调用 | Worker 终端 `$env:LLM_API_KEY = "你的密钥"` |
| 模型网络许可 | 默认关闭 | 确认费用政策后将 `configs/system.toml` 的 `model.network_enabled` 改为 `true`，再创建新任务 |
| 模型名称／区域 | 默认 qwen-plus／北京 DashScope HTTPS | 同 TOML；需要与账户开通区域一致；其他供应商未宣称兼容 |
| 模型费用控制 | 最多四次请求、每次输出 8192、已知 usage 停止线 131072 | 这些不是硬账单限额；严格总预算需计数器／账户限额，未确认则保持网络关闭 |
| 本地写入令牌 | 每次启动 API 自行生成 | `$env:CARDMIG_SYSTEM_WRITE_TOKEN = [guid]::NewGuid().ToString('N')`；页面填这个，不是模型 key |
| Chromium／Edge | 本机 Edge 已用于真实校准 | 自动发现或 `CARDMIG_BROWSER_EXECUTABLE`；其他机器需安装兼容浏览器 |
| LangSmith key／上传同意 | 默认关闭；未上传 | `tracing.enabled=true`，对应进程设 `LANGSMITH_API_KEY`；只导出哈希、阶段、耗时、成本／状态摘要 |
| few-shot 研究语料 | 已提供两个自建开发演示，默认选择一个 | 严格研究用语料需审核 group／split／来源与目标正确性；更换 manifest 并建立新实验版本 |
| LoRA 基础模型／许可证 | 未下载／未确认 | 本地模型路径与确切版本；`license_confirmed=true` 只在本人核实后填写 |
| LoRA 硬件／训练环境 | 未安装可选大依赖，未训练 | 建议独立 Python 3.12 环境与可用 GPU；按 training README 安装，记录解析后的依赖锁 |
| LoRA 配对数据与适配器 | 执行入口已实现，无训练成果 | 先构建有分组隔离的数据，再显式 `train-lora --execute`；训练完成后选 `local_lora` 后端 |
| 视觉嵌入模型 | 未下载，辅助项明确未执行 | 本地 CLIP 模型目录填 `learning.embedding_model_path`；不使用网络自动下载 |
| 代表场景／人工验收 | 每个真实任务由使用者配置 | props、click／input 等场景；人工通过、改动行数和耗时独立追加 |

## 后续统一启用方式

1. 按 [系统指南](SYSTEM_GUIDE.md) 升级数据库、启动 API 和 `migration-worker`。
2. 核对 TOML 模型、预算政策和浏览器配置，补齐对应终端环境变量；不在页面传模型凭据。
3. 所有配置完成后创建一条新的真实迁移任务，统一检查生成、校验、截图、修复、报告和下载；不用再逐模块反复交接。
4. 云模型／LangSmith／LoRA 的实际连通与效果分别保留证据。工程测试通过不代表开题中的 85%／90%／70% 目标已经达到。

新配置只用于新请求；不能改写旧请求的网络权限、Prompt 或绑定指纹来伪造已批准／已验证记录。
