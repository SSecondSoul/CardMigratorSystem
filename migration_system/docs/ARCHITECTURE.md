# 当前架构：一条主链、内部引擎、两个持久化职责

2026-11-18 闭环 v2：没有新增运行时或编排层。原 `bounded_semantics.cjs` 增加 computed 命名空间诊断／源声明约束下的值读取修复，既有修复入口及调度保护使用同一错误码；方法比较仅归一化普通对象表达式的等效表示。`dom_comparison.py` 提供有上限的控件身份／父拓扑证据，原候选门据此允许可证明的诊断细化，结构检查仍失败。详见 [闭环修复记录](CLOSED_LOOP_V2.md)。

2026-11-18 比较／契约增量：`browser/class-projection.mjs` 为源／目标提供对称、token 边界保守的 class 投影；`stages/dom_comparison.py` 保留原始证据并分类表示差异与控件属性／路径差异。内置 `method_interface_semantics.cjs` 在源码内部普通 data 键调用范围内核对 setter 形状、完整调用者函数及生命周期映射，支持保留 helper 或等效内联写入；不新增运行时、不重写源码、不替代模型生成。新范围 v4 与逐方法证据随新任务／报告持久化；原生成阶段、图和质量阈值不改。详见 [通用修复](SEMANTIC_COMPARISON_V1.md)。

2026-11-18 修复边界增量：`prompts/repair_context.py` 只负责发给修复模型的证据投影。`stages/repair.py` 保留原规则调度、语法分支、模型账本和候选机制，调用旧 Prompt builder 后替换全量 SSM 文本为有明确范围的相关证据，不再拼接整份评估。原 engine、生成阶段、原始评估数据和质量判定不改；没有增加迁移路径或兼容运行时。详见 [验证记录](verification/2026-11-18_repair_context_v1/README.md)。

当前更正：按用户要求删除 `stages/business.py` 及其生成／专用校验／停止分支。生产范围为 `san-supported-migration-v3`；动态 setter 不再单独触发源码预检查阻断，随后使用与其他源码相同的模型生成、原静态校验、原浏览器评估和有界修复。没有额外源到 San 编译器或实例代理接入。`runtime/san_business_v1` 与 `research/` 仅离线研究保留，不是生产依赖，也不纳入当前运行绑定。放行不代表完整契约实现。

2026-11-17 当前交付以 [PRODUCTION_CLOSURE_V1](PRODUCTION_CLOSURE_V1.md) 为准：唯一主链优先，公开实例研究暂停扩展、保留证据，不作为可用闭环的前置条件。`contracts/production_scope.py` 仅提供服务端请求／报告范围快照，不执行编译、代理或豁免校验；旧契约仍未完成。下文各研究阶段描述按其发生时状态保留，不表示仍须完成全部研究才能提交普通迁移任务。

本轮是依赖内聚与职责整理，不是重写迁移算法。开题要求的四维 SSM、few-shot／LoRA、结构 TED、Puppeteer／SSIM／像素／样式、规则＋模型闭环、LangGraph／LangSmith保留；不增加跨框架互操作或新的语义兼容层。

## 从这些文件开始读

| 需要理解什么 | 文件 | 职责 |
| --- | --- | --- |
| 入口与命令 | `scripts/run_system.py`、`interfaces/cli.py` | 定位本目录并分派命令，不编排迁移 |
| HTTP 提交／报告 | `interfaces/api/migrations.py` | 校验请求、入队、查询和下载，不在请求内跑模型 |
| 任务与账本 | `application/migrations.py` | 持久化任务、输入／版本、调用收据和幂等恢复 |
| 总流程 | `graph/migration.py` | LangGraph 节点与条件边，只有这里决定下一步及停止 |
| 初始生成 | `stages/generate.py`、`prompts/migration.py` | 原生成 Prompt＋few-shot 请求，交给统一模型调用账本 |
| SSM | `adapters/ssm.py` → `engine/SSM/` | 复用原 AST 提取与四维组装，区分解析失败和降级 |
| 静态校验与规则 | `adapters/legacy_checks.py` → `engine/migration_pipeline/` | 名字保留兼容；实际只执行本目录内置代码，不再适配父目录 |
| 语法与浏览器 | `adapters/syntax.py`、`adapters/browser.py` → `browser/` | 解析、隔离双端运行、快照／截图／动作，设施错误不伪装成目标错误 |
| 评分与候选 | `stages/evaluation.py`、`stages/dom_comparison.py` | 原多维检查和候选保护，不合并成一个可掩盖失败的分数 |
| 一轮修复 | `stages/repair.py` | 原有规则顺序／修复 Prompt，产出候选；不自行接受 |
| 数据与检查点 | `persistence/`、`migrations/` | 业务事实与 LangGraph checkpoint 分开保存，不依赖前端内存 |
| 模型／追踪／训练 | `adapters/model.py`、`observability/`、`training/` | Qwen／LoRA 后端、显式 LangSmith、离线训练，各有单一职责 |

以上包路径均相对于 `src/card_migration_system/`。

## 为什么保留 engine

`engine` 不是另一套系统：它不启动服务器、队列或旧 orchestrator。96 项源文件逐字节复制；另两项是无副作用包入口及从旧服务精确抽出的纯 Prompt builder。`MANIFEST.json` 逐项记录原路径、源指纹、内置指纹与转换理由。安装 Node 依赖后，源代码和依赖都在此目录内。

保留原内部模块名是为了避免一次性修改近百个 Python／CJS 互相引用，从而降低搬迁回归风险；业务只通过阶段边界调用它，不需要开发者同时理解两套编排。未来实验改进只能显式整合并更新清单，不会因父目录文件被修改而自动改变独立系统。

本目录 `.gitattributes` 对内置 engine 与验证 payload 禁止自动换行转换，避免 Git checkout 悄悄改变已封存字节。其余实现绑定仍以实际运行字节为准；不能拿新指纹静默恢复旧任务。

`Settings.repository_root` 是旧字段兼容名，其值现在固定为 `本系统/engine`；`engine_root` 是清晰别名，不存在“找不到就回退父目录”的逻辑。

## 不再混在主链中的内容

- 前端旧夹具工作台在单独、延迟加载的历史页；真实迁移默认不挂载它，也不轮询开发队列。
- G1—G3 的离线传输／批准验证模块为旧记录及测试保留，不能替代真实迁移 Worker；主链不串行经过这些历史图。
- 依赖旧快照的重放脚本属于实验工具区，不是系统部署依赖。
- 旧 README／启动说明原文在 `docs/history/`，其中相对路径按旧位置记录，已被当前 README／SYSTEM_GUIDE 替代。

新系统不自动导入旧数据库或恢复旧任务。这避免新实现绑定、旧候选和已付费用量混用；本轮没有改变原样本失败状态、通过率或源代码。

## 后续授权的实例边界研究

`research/public_instance_v1` 是用户随后授权的独立公开实例代理原型，不由上述主链导入，不改变默认组件导出方式或旧契约。当前只完成有限原生与浏览器对照，仍有对象身份及公开框架 API 等差异；详见 [原型验证](PUBLIC_INSTANCE_PROXY_V1.md)。这不是第二条迁移生产链，也不因研究代码存在就解除 `source_dynamic_key_contract_unsupported`。

后续 `research/public_instance_v2` 在独立响应式内核上修复对象／ref、computed／watcher 和原生读取／DOM 更新；它也未接入主链。完整私有图、部分原生写策略和真实组件编译尚未闭合；新内核依赖如实披露，见 [v2 记录](PUBLIC_INSTANCE_PROXY_V2.md)。上述 v1 是历史阶段，不将其原证据改写为修复后结果。

`research/public_instance_v3` 继续研究原生双向控件嵌套写入：保留源对象／ref 身份并按根合并原生通知，两张实际页面已验证输入／勾选／下拉选择。它不是生产 Data API 全等价实现，也不关闭私有图、生命周期／作用域和真实编译／加载缺口；见 [v3 记录](PUBLIC_INSTANCE_PROXY_V3.md)。主链及源契约门不变。

v4 研究将有限原生渲染完成与 nextTick 连接，修复旧 v3 的真实调度反例，并分开非 DOM 屏障测试替代与真实浏览器证据；见 [v4 记录](PUBLIC_INSTANCE_PROXY_V4.md)。仍未实现完整生命周期／实例图或接入生产，不增加迁移流水线层次。

v5 研究以私有 root owner helper 连接有限生命周期与 watcher 清理，直接原生销毁也经过同一清理路径；不是完整组件树／私有实例图或新的生产编排层。依赖、实际失败及尚未支持的父子／循环作用域等见 [v5 记录](PUBLIC_INSTANCE_PROXY_V5.md)，主链阻断不变。

v6 研究增加有限 owner family 和实际子组件／keyed 循环对照，树行为 3/4，保留原生 San keyed 实例重建差异，未进入生产。详见 [v6 部分结果](PUBLIC_INSTANCE_PROXY_V6.md)，不把工程反例检查全绿当成完整兼容。

v7 仅在 research 中增加有上游版本／SHA-256 门的 San 内存候选，修复已验证的单元素根 keyed 组件移动，有限树场景 4/4；没有引入新的生产适配器、改 engine 原件或缩减公开 setValue 契约。未闭合的动态代理子 props、私有实例图及编译／加载等仍阻断，见 [v7 研究边界](PUBLIC_INSTANCE_PROXY_V7.md)。

## 保持 San 目标后的业务运行时（部分实现，未接入）

用户后续确认 [San 业务契约](SAN_BUSINESS_INSTANCE_CONTRACT_V1.md)，不要求复制 Vue 私有实例图，但公共功能仍需实现或明确拒绝。`runtime/san_business_v1` 是一个组件运行时及离线编译模块，不是第二套 API、数据库或 LangGraph 主链；主生产编排仍只有上述链路。它在真实 San constructor 内隔离业务实例，自动从源 Options／AST 产生脚本、布局及 DOM 策略，并将实现和依赖指纹绑定到新产物。独立响应式／显示工具被披露，不引入 Vue 组件渲染器，也不读取父工程源码。

目前未从默认 `MigrationService` 导入，旧源 gate 保持。主链生成／验证／修复的版本化接入、自动源组件树和部分公共能力尚待完成；有限父子夹具不能当作完整接入证明。见 [当前已完成和剩余项](SAN_BUSINESS_RUNTIME_V1.md)。
