# TaskManager 人工反馈后的 textarea 修复

验证：279/279 测试通过（85.535 秒），含 10 项 textarea 正反例；修复候选包 13 文件、原始快照 297 文件校验通过。后续用户于 2026-11-03 回复“通过”，当前修复候选状态为 passed_by_user。

日期：2026-11-03。用户在本轮冻结产物中报告“新建任务的任务描述里面有代码”。这是原初始 DOM／静态检测没有覆盖的隐藏模态框缺陷，原模型批次自动通过记录保持，但人工结论尚未通过。

源 Vue 使用 `<textarea v-model="formData.description"></textarea>`，San 错把 `{= formData.description =}` 写进标签文本。通用修复将它移至 `value` 双向绑定、清空仅含该标记的正文。已加静态错误 invalid_san_textarea_binding、repair 预处理／返回后修复、Prompt 规则及语义退化保护。

分析限制在真实 SFC 和 san.defineComponent 内联 template；字面正文、混合文字、已有 value、非可赋值表达式不猜改。解析到其它标签错误时仅独立处理无本地错误、结构明确的 textarea，不顺带改其它 HTML。测试包括原真实失败产物、San AST 的双向 value 属性、Unicode／引号偏移、歧义拒修和事件回退保护。

用户确认提示是“设置已更新：defaultView”。Vue 源 `updateSettings` 也使用 `设置已更新：${key}`，所以这是源页面本来暴露内部键名，不是 San 新增英文；本次不改，保持迁移对齐。若需要全中文提示，应另行修改源设计和对齐版本，不能把它归为本次迁移缺陷。

复验包：`data/experiments/manual_followups/formal_30_v4_semantic_closure_v2_TaskManager_textarea_v1_20261103`。13 文件校验，原 297 文件快照不变；修复前新检查发现 textarea 错误，修复后静态通过，候选为 TaskManager_textarea_fixed.san。没有调用模型，没有修改原 batch summary。此候选归属人工反馈后的确定性跟进，不能回填为原三轮预算内的纯自动结果。

San 测试页仅换 componentPath，Vue 页仍使用本轮冻结源。交给用户的复查范围包括：新建时描述为空／placeholder 正常，输入后创建再编辑可保存并回显，内部点击／关闭、标签、拖拽和筛选无回退。这些是复查要求，不是助手实测结果。候选冻结时为 pending_retest，后续用户回复“通过”；只记录该整体人工确认，不据此编造逐项操作日志。

## 后续人工确认（2026-11-03）

独立记录：`TaskManager_manual_acceptance_20261103.json`。通过对象为 `TaskManager_textarea_fixed.san`，SHA-256：`8286510708e7a273388b205af6217a60f527a535786cdb25ec67f81fdc771b46`。人工反馈 JSON 已更新候选状态，原件发现缺陷的状态保留。候选冻结包中的 pending_retest 是封存时状态，保持不变，由本次独立记录补充后续确认。

原始模型批次仍为 2 项完成、1 项自动通过、1 项失败；不回填此次人工反馈触发的修复，不宣称完整 30 项回归完成。助手未执行浏览器交互测试，本次没有额外模型调用。

新检测／规则改变了 live 代码基线，因此旧协议不再用于新模型运行；旧冻结包与分数不修改。后续任何模型实验仍须建立新的预运行版本。
