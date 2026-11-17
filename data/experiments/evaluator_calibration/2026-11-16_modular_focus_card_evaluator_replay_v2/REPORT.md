# FocusCard 评估器兼容性：最终收口重评

本目录是最终实现的独立离线重评，保留先前 [v1 对照说明](../2026-11-16_modular_focus_card_evaluator_replay_v1/REPORT.md)，不覆盖其证据。v1 后又补齐了多 token 源 class 键内部空白的归一化边界，并增加对应原生 San 状态测试；本目录重新绑定最终实现哈希。

原任务：`f3cf07b0c7e5462aaf1b1cd5a781b37a`。使用同一份原始接受产物，第 1 轮 SHA-256 `0ced63ec865d38bedf3cdc4d5a102780d35d48684639af75900675f69decaced`；没有改生成代码、Prompt 或质量阈值。

## 结果

- 当前旧静态验证器直接调用与新适配层调用：均通过，错误码均为空。
- 旧 `VisualEvalStage`：通过，DOM 结构／文本相似度均 100%；不将它冒称像素评估。
- 新 SSM／San AST TED：0，相似度 100%。
- 新源模板／San AST TED：0，相似度 100%。
- 实际 DOM：100%；UI：100%；SSIM：1；不同像素率：0%。
- 按原空交互配置重评：interaction 仍为 not_run。
- 独立补充的开始／停止点击场景：通过；不回填原任务。

详情和实现指纹见 [comparison.json](comparison.json)，原字节源码／接受产物／历史报告副本及截图由 [SHA256SUMS.json](SHA256SUMS.json) 校验。核对了 46 条历史文件／输入哈希记录（含重复引用）。清单覆盖脚本产生的 7 个文件，本说明随后追加，不在清单中。

本轮新增模型调用 **0**，未上传 LangSmith。原任务仍为 failed，原 3 次模型开始与 41391 Tokens 账本保持不变。此结果是开发校准，不是新模型成功样本或独立测试，也不证明全量旧样本均兼容。

后续只需重启 API／migration-worker 让新任务使用修正实现；无需为了验证这次评估修正付费重新生成组件。测试执行结果另见 migration_system/DEVELOPMENT_20261116.md。
