# 源 HTML 空元素预检查修复重放

原任务：`3d3d69c7760045e1bd0c741f7cf3638b`，InvoiceLineEditor.vue。

原源码 SHA-256：`9b50005a20314dd9c1f52db9496c6092d8f2838958955be0fa0350db7c77a8df`。

旧入口 `compiler-dom.baseParse` 缺少 HTML 平台规则，合法 input 误报缺少结束标签。源模板改用 `compiler-dom.parse`；目标 San 解析及质量阈值不变，真正缺失非空结束标签仍阻断。诊断通过 Python 来源边界及本地报告，工作台显示具体位置和转义片段。

相邻 v1 为修复前 blocked，本目录 v2 为源 preflight completed；两次都使用同一源输入。先冻结原 request、failure、源输入三个文件，再执行 Node 源预检查。模型调用 0、未启动渲染浏览器、未写数据库或历史任务、未上传 LangSmith。没有生成目标 San，不能记为迁移成功。

`SHA256SUMS.json` 单独封存 10 个 payload；`FROZEN_SHA256SUMS.json` 记录三个历史原件，`replay.json` 保存实现指纹与范围。本说明在清单生成后补写，不属于这 10 个 payload。

稳定实现验证：新增专项 12 项通过（33.895 秒），完整模块回归 91 项通过（241.352 秒，已含专项）；前端构建与 Node 22 项测试通过。包含真实临时浏览器及工作台测试，不使用真实模型或质量分数替代。工程用例数量不是迁移样本数；更完整边界见 `migration_system/SOURCE_TEMPLATE_PARSING.md`。
