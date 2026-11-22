# 70 项真实运行复盘与通用修复 v6

2026-11-19。本页是实际实现与验证记录，不表示全部问题已解决。

## 结果与口径

- 真实模型 v3 批次仍为 **15/70**，没有覆盖原报告或重新调用模型。
- 对该批次 70 个冻结父版本执行当前通用规则重放：**28/70** 满足配置检查，比历史接受父版本新增 13 项、原通过无回退。仍有 **42 项** 未解决／无完整产物；这是离线已有代码修复结果，不是新生成通过率。
- 42 个父版本产生了候选，26 个严格改善被接受，16 个仍因回退／没有进展被拒。语法、结构、控件、视觉及静态语义门没有降低。
- 全量重放前后核对 **7,166 个冻结文件**，原失败代码、报告、Tokens 与 TaskManager 的未知调用均保留；未重试未知请求。
- **194 项关联回归通过**，另有 **2 项持久化图／账本的修复后处理测试通过**。后者明确使用模型和检查替身，不是实际迁移通过样本。
- 仓库外独立副本验证通过：真实 SSM AST、持久化 LangGraph、API／前端／下载、真实浏览器和候选门；模型为明确的记录响应替身，真实模型调用 0，原数据库未更新。

## 根因与修改位置

| 根因 | 通用改动 | 保留的边界 |
| --- | --- | --- |
| 可解析模板直接返回，未执行已有属性修复 | `browser/target-syntax.mjs` 在可解析模板中也运行源匹配属性修复；外层循环／脚本修复后再次检查新显现属性 | 未知表达式不猜；真正未闭合脚本仍失败 |
| 属性定位使用通用 XML 式解析 | `attribute-syntax.mjs` 使用 DOM HTML 解析入口，识别 void elements 与 SVG namespace | 不把 SVG 当原生 HTML 属性写入 |
| 模型修复结果缺少同轮规则复核 | `stages/normalization.py` 每个提案最多 3 次“语法→最新静态检查→既有规则”；`stages/repair.py` 对模型输出也执行 | 不增加模型调用；原始输出存入 `model-outputs/`，逐步哈希存入 `normalizations/`；最终仍复测、回退 |
| computed 搬迁与消费者不同步 | `bounded_semantics.cjs` 对完整源 getter 翻译一致的依赖组原子搬迁，并修正已知源消费者把值当零参方法的误调用 | 函数体变化、参数调用、未知消费者、缺失依赖不自动放行 |
| 新建 reduce 累加器被误当外部状态写入 | AST 只允许由该 reduce 调用新建的字面量累加器变更 | 状态对象、集合项、外部参数变更仍拒绝 |
| 完整 caller 恢复误拒标准闭包 | `method_interface_semantics.cjs` 允许 Date/Object/Array 标准引用，保留双端同名遮蔽检查 | 未知键、未知 this owner、任意外部公开键仍不证明 |
| San 普通绑定未反射真实 HTML value／空 class | 源匹配的受限非空 input `:value` 使用原生 defaultValue；字符串条件 class 使用原生 className | 实际修补 DOM，不删除差异；nullable props、v-model、未知键、SVG 等仍保守拒绝；CSS 属性观察不豁免 |

内置引擎仍为 98 项：89 项逐字节原件、2 项既有封装转换、7 项明确演进。保留原始来源 SHA，更新 bundled SHA 与演进说明；生成仍是完整 SSM＋模型，没有整体源 AST 确定性生成，没有新增组件名称白名单，也没有继续堆积 Prompt。

## 尚未闭合，不能现在宣布全部修好

1. **恢复运行后的诊断谱系**：部分默认值修复已生效，但新增“控件位置不同”诊断导致候选退回。只读调查发现 4 个组件的 11 次相关候选，其中 4 条静态模板逐字一致。尚未更改候选门；不能直接删除错误或允许所有新错误。
2. **原生控件属性与状态**：进一步的 VALUE 原生属性校准已验证 input／select／textarea 的 null→字符串→null 原始 DOM 对照；但 select 初始空值仍存在 live selection 差异。因此该后续方案**未接入生产，不算修复完成**。
3. **复杂源语义**：剩余动态键流、初始化时序、复杂 getter／内联子组件、真实节点／事件缺失和未闭合脚本继续保留失败，不能用分数提高替代逐类证明。
4. TaskManager 的未知调用仍没有返回产物；未作为零费用、代码失败或自动重试处理。

应继续按遗留清单补齐上述机制，再冻结新配置；目前不建议直接启动下一次 70 项模型重跑。

## 证据位置

- 两轮逐项、全部修复轨迹：[对照报告](../../experiment_runs/analysis_v3_vs_first70_20261119/REPORT.md)。首轮由 v1 的 49 项与 v2 补充 21 项组成，不能叫单版本基线；v2 两项复跑单独保留。
- 本次完整离线结果与 Notebook：[复核报告](../../experiment_runs/composed_v6_review_20261119/REPORT.md)、[Notebook](../../experiment_runs/composed_v6_review_20261119/analysis.ipynb)。`remaining.json` 逐项列出 42 项，`coverage.json` 覆盖两轮全部观测诊断。
- 真实浏览器、候选与门禁：根目录 `experiment_runs/composed_v6_final_replay_20261119/`；未变代码明确复用历史捕获，不冒充全部重新启动浏览器。
- 回归：`docs/verification/2026-11-19_general_repairs_v1/test-results-composed_v6_verified.json`、`post-model-v6.json`。
- 独立运行：`var/refactor-verification/composed_v6_20261119.json`。
- 早期中断的预检目录已有 `INTERRUPTED` 标记，不混入完整重放结果。

本轮未修改云库／用户源码、未启动付费模型任务、未重启用户服务。以后接入新任务前须重启使用同一云库配置的 API 与 Worker；旧实现的检查点不得改绑成新实现。
