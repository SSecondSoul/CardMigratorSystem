# v4 semantic closure v3：仅 MonitoringDashboard 的新生成回归

日期：2026-11-03，Asia/Shanghai。重复开发样本，不是独立未见测试。

## 输入、预算与输出口径

仅运行 MonitoringDashboard 一项，源 Vue 必须与 v2 原始结果包逐字节一致。由 Vue 重新提取 SSM、生成一次，再在本次生成候选上迭代修复；不是继续修改上一轮 San，也不把离线修复候选当作本轮初始输出或参考答案。

最多 3 次 LLM repair，bounded_prepass_v1，每次调用前最多 4 个确定性步骤（全样本最多 12 步），semantic_rule_set=residual_v2。qwen/qwen-plus，temperature=0.2（随客户端源码冻结），无固定模型或渲染随机种子。上游 LLM_TIMEOUT=600，generation／repair 客户端各 660 秒；launcher 在新进程导入配置前固定环境。

批次 formal_30_v4_semantic_closure_v3 使用全新的默认输出目录、repair reports 和 summary checkpoint；不用 --force、不覆盖旧结果。首次启动只应有一个未运行样本；中断后保持代码不变，用同一命令依据 checkpoint 恢复。执行异常另列，不能只保留成功尝试。若需要主动重新生成，应先冻结当前尝试，再建立新批次。

TaskManager 排除在本批次外，保留已通过的 textarea 修复候选与独立人工验收；不把人工反馈修复回填为 v2 自动成功。原 v2 批次仍 1/2 自动通过。旧完整 30 项分数不修改，后续仍需完整开发回归，探索性候选集评估继续等待。

## 冻结变更与证据边界

v2 冻结失败产物的源参数链、挂载阶段和 watcher 存储写入闭环已离线验证。通用 repair AST 规则仅在源证据和生成结构满足边界时应用，不按组件名硬编码；不承诺所有新生成结果都能自动修好。新增 source_mounted_order_not_landed、source_watch_persistence_not_landed 检测与语义回退保护，repair 聚焦 Prompt 同步更新；含此前已通过的 textarea 检测／修复。generation 和服务器 Prompt 未在这两步修改。

冻结输入、SSM、generation／repair、验证器、渲染器、候选门、规则／依赖清单和测试；代码在冻结之后不得再改。本次验证器也变化，不能把新结果差异只归因于 Prompt、规则或模型随机性。与旧版本不是同一评估器下的单因素消融。

原始失败快照 297 文件、离线闭环包 12 文件及 TaskManager 人工通过候选包 13 文件各自校验；新包保留旧分数、人工验收和离线证据。旧冻结包不改。离线 DOM 相似度存在变化，不挑选较高值替换记录。离线修复通过不是新鲜模型回归通过，初始 DOM／静态通过也不是全部交互通过。

本协议的首次模型调用前验证：完整单元测试、源输入哈希、离线重放、dry-run、新协议自身与 live 哈希。服务器是否确已重启、运行时环境与实际模型版本不能由文件哈希独立证明，必须由操作者按命令启动，并保留服务与批处理输出。冻结包不含 API 密钥。

## 操作者执行

在项目根目录、cardmig 环境，先于旧服务器窗口按 Ctrl+C 停止旧服务。

窗口 A：

```powershell
$env:LLM_API_KEY = "你的密钥"
python -m migration_pipeline.run_formal_30_v4_semantic_closure_v3 --server
```

保持窗口 A 运行。窗口 B：

```powershell
python -m migration_pipeline.run_formal_30_v4_semantic_closure_v3 --execute
```

两个入口均先检查本包 live 哈希；任何不一致应停止并建立新版本，不修改旧校验清单。运行结束后不要马上修改代码或重跑；先冻结原始产物，再诊断／评估。可使用：

```powershell
python -m migration_pipeline.freeze_formal_30_v4_semantic_closure_v3_results
```

模型调用由用户启动，准备和冻结本协议不调用模型。人工测试页本次不切换，不能把仍指向 TaskManager 的页面通过结论当作新 MonitoringDashboard 的人工通过。待本批原始结果封存后再单独配置页面、进行交互检查。
