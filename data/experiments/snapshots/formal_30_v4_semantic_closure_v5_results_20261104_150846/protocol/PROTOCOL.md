# formal v4：semantic closure v5 单样本开发回归

冻结日期：2026-11-04（Asia/Shanghai）。仅 MonitoringDashboard。
名称中的 v5 是 formal v4 内部语义闭环的第五轮，不是新的独立正式测试版本。
这是重复开发回归，不是独立未见测试；完整 30 样本最终规则回归仍未完成。

## 输入、预算与计分

从与原 v4 协议逐字节相同的 Vue 重新提取 SSM、生成代码，然后在本轮候选上迭代修复。
不继承上一轮 San，不把离线修复产物作为输入或参考答案。
使用全新批次 formal_30_v4_semantic_closure_v5 的默认 pipeline、repair reports 和 summary checkpoint。
不加 --force，不覆盖旧结果；同代码中断恢复可使用同一命令，主动重新生成必须先封存并另建批次。

预算：最多 3 次 LLM repair；bounded_prepass_v1、residual_v2；每次调用前最多 4 个确定性步骤、共最多 12 步。
qwen/qwen-plus，客户端 temperature=0.2，LLM_TIMEOUT=600，生成/修复客户端各 660 秒。
launcher 在新子进程导入配置前固定环境；没有固定模型或渲染随机种子。
服务商实际模型版本及旧服务进程是否停止不能仅凭代码哈希独立证明。

保留原始 v4 自动 1/1 通过、272803 tokens 记录，不把新检查结果追溯写入旧计分。
TaskManager 不纳入本轮，保留已有用户验收候选；人工页面不切换、不据此声明 MonitoringDashboard 人工通过。
所有初始、确定性和模型候选、拒绝及回退均保留，运行完成先封存全部原始结果，再诊断/安排人工检查。
不选择较高 DOM 分数覆盖最后候选。

## 系统变更和证据边界

本次准备不改生产规则；冻结前已实现的通用启动阶段与源父组件方法接口保留闭环。
原始结果 342 文件、启动闭环 24 文件、方法接口闭环 31 文件、TaskManager 验收候选包 13 文件逐一校验。
307 项已验证代码清单与当前运行时一致；新增本轮配置、launcher、preparer、结果封存器和启动边界测试。
相对旧 v4 运行协议的 8 个已有文件变更逐项记录于 manifest；新增运行时文件也纳入 frozen。
不修改生成阶段或服务器 Prompt；这是验证器、候选门、确定性恢复及 repair Prompt 的联合变更，不是单因素实验。

启动规则仅处理源代码可证明的 mounted 初始化包装器，确保对应 attached 中恰好一次；不猜测未知副作用。
方法接口检查针对可解析的 Options API 导出父组件可调用接口，不证明所有已有方法体或子组件完整等价。
自动恢复仅覆盖内部未引用、无动态/别名逃逸不确定性、同步且参数/表达式受支持的缺失方法。
保留原方法条件与顺序，状态读取转为 San data.get；未知闭包/依赖、写入、复杂签名、保留名或已有不透明项不猜测覆盖。
恢复 requestNotificationPermission 的原接口，不增加保存设置、挂载、勾选时调用权限请求的触发点。
新接口丢失或新触发点由候选门拒绝；仅源码/解析恢复证据严格成立的“新近可见旧缺陷”不算新增，但仍保留验证错误。

离线三产物静态零错误、DOM 通过、固定点和逆向拒绝均已验证；这不等于新生成成功或浏览器交互验收。
同一离线代码哈希曾有不同 DOM 分数，保留观测、不挑选分数，也不单凭分数推断差异原因。
受控 Node Notification stub 测试不是真实浏览器权限请求。
冻结前重新跑完整本地测试、三产物无模型回放、批处理 dry-run，再验证 frozen 和 live 哈希。
冻结后不得改列入清单的文件；若需改动，停止本轮并另建协议，不改旧 SHA 清单。

## 操作者命令

项目根目录、cardmig 环境。先在旧服务器窗口 Ctrl+C 停止旧服务。

窗口 A（本地填密钥，不写入仓库）：

```powershell
$env:LLM_API_KEY = "你的密钥"
python -m migration_pipeline.run_formal_30_v4_semantic_closure_v5 --server
```

保持 A 运行，在窗口 B 执行：

```powershell
python -m migration_pipeline.run_formal_30_v4_semantic_closure_v5 --execute
```

两个入口均先校验本协议 live 哈希。不加 --force 或旧输出路径；校验失败停止，不改校验清单。
仅查看计划可 --dry-run。模型结束后先反馈“运行完成”，不马上复跑或改代码。
随后使用封存入口保存原始结果：

```powershell
python -m migration_pipeline.freeze_formal_30_v4_semantic_closure_v5_results
```

协议准备不启动服务器、不调用模型、不存储密钥。
