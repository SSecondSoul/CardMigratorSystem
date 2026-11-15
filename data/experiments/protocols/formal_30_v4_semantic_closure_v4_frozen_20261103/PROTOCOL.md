# v4 semantic closure v4：覆盖状态与图表依赖单样本回归

日期：2026-11-03（Asia/Shanghai）。仅 MonitoringDashboard；重复开发回归，不是独立未见测试。

## 输入、预算与计分

从与 v3 冻结输入逐字节相同的 Vue 重新提取 SSM、生成一次，再在本轮候选上迭代修复。
不继承上一轮 San，也不把离线修复候选作为生成输入或参考答案。
采用全新批次 formal_30_v4_semantic_closure_v4 的默认输出、repair reports 与 summary checkpoint；
不使用 --force，不覆盖旧结果。中断后代码不变可用同一命令按 checkpoint 恢复；主动重新生成必须先封存并另建批次。

预算沿用最大 3 次 LLM repair，repair_policy=bounded_prepass_v1，semantic_rule_set=residual_v2；
每次调用前最多 4 个确定性步骤，全样本最多 12 步。qwen/qwen-plus，客户端 temperature=0.2；
LLM_TIMEOUT=600，generation/repair 客户端各 660 秒。launcher 在新进程导入设置前固定环境。
没有固定模型/渲染随机种子；实际模型服务版本与旧服务器是否确已停止不能由文件哈希独立证明。

TaskManager 排除在本轮外，保留此前 textarea 候选和独立用户验收，不回填为旧批次自动通过。
旧 v3 原始分数仍为 0/1，240133 tokens；旧完整 30 项分数不修改。
模型与确定性步骤分别记录；异常、拒绝、回退候选都保留，不挑选较高 DOM 分数替换最终结果。

## 本次系统变更与证据边界

冻结失败快照 315 文件、离线闭环包 22 文件和 TaskManager 候选包 13 文件全部校验。
相对 v3 的 4 个修改文件为 repair.py、repair_scheduler.py、residual_semantics.cjs、source_phase_semantics.cjs；
新增注册标识符恢复、语义覆盖证明及只读 helper 显式依赖模块、回放与测试。
生成阶段与服务端 Prompt 未在这一步修改；不是仅改 Prompt 的单因素实验。

候选门只在源注册、方法 AST、作用域和渲染调用等证据严格匹配时，区分“新近可见的旧缺陷”与真实新缺陷。
旧缺陷仍保留为验证错误，不免检、不自动判成功；未知证明和实际计算变化仍拒绝。
图表 helper 规则只转换私有内联组件中可证明只读、自包含且调用覆盖完整的方法，原子更新所有调用及参数。
同时保留源 prop、事件参数、watcher 持久化与布尔事件的有边界修复；不承诺任意新生成代码都能自动修好。

离线包中：原始保留失败产物仍有 19 条静态诊断，DOM 0.9781；捕获的被拒候选经规则处理后静态 0 错误，DOM 0.9825。
这些是冻结产物重放，不是新鲜模型成功，也不是浏览器交互验收。
原先历史记录中的 4 条隐藏依赖拒绝理由不改写；新检测另发现的 watcher 持久化缺陷另行披露。
测试包含真实计算改动必须拒绝的反例，以及 0/1/7/30/90 点和不同画布宽度的坐标一致性验证。

运行前完成：全套本地测试、无模型只读回放、dry-run、新协议 frozen/live 哈希验证。
冻结后不得再改所列代码。模型运行结束先封存全部原始产物，再诊断、配置人工页和交互检查。
当前人工页仍指向已验收 TaskManager，本次不改；不能把它的“通过”当作 MonitoringDashboard 通过。
后续完整 30 样本开发回归仍未完成；候选集探索性评估继续等待。

## 操作者命令

在项目根目录、cardmig 环境中，先在旧服务器窗口按 Ctrl+C 停止旧服务。

窗口 A（本地填写真实密钥，不写入仓库）：

```powershell
$env:LLM_API_KEY = "你的密钥"
python -m migration_pipeline.run_formal_30_v4_semantic_closure_v4 --server
```

保持 A 运行。窗口 B：

```powershell
python -m migration_pipeline.run_formal_30_v4_semantic_closure_v4 --execute
```

两入口先验证本协议 live 哈希；不一致应停止，不修改旧校验清单。
首次运行前可 --dry-run；不要附加 --force 或旧输出路径。运行完成后不要马上重跑或改代码。
原始结果封存入口（由后续检查步骤调用）：

```powershell
python -m migration_pipeline.freeze_formal_30_v4_semantic_closure_v4_results
```

协议准备和冻结不调用模型、不启动服务器、不含密钥。
