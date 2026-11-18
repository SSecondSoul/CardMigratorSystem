# CardMigrator：独立迁移系统

当前交付目标已收敛为[有明确支持范围的迁移闭环](docs/PRODUCTION_CLOSURE_V1.md)：优先跑通真实主链，不以完整公开实例代理兼容为前提。下面的代理研究是保留成果，未启用，也不代表其阻断样本已修复。

当前更正：按用户要求撤销源 AST 规则生成路径，范围更新为 `san-supported-migration-v3`。动态 setter 不再单独触发预检查阻断，统一使用原有 SSM＋模型生成＋校验＋有界修复；不启用业务实例代理、不改 Vue 源码、不豁免质量检查。下文研究成果仅离线保留，不参与生产生成。历史规则结果保留但不计作模型迁移效果。

本目录可独立复制、安装和运行，**运行时不读取父目录的 `migration_pipeline`、`SSM`、`local_server` 或实验数据**。旧实验仍留在原仓库；可复用实现已按来源指纹内置于 `engine/`，不在启动时动态套用外部代码。

## 先看这些文档

- [SQLite 多用户版](MULTI_USER_GUIDE.md)：账号登录、管理员、任务隔离、配额及独立库的启动命令；当前适用于受邀可信账号，不是已完成公网任意源码沙箱。
- [启动与使用](SYSTEM_GUIDE.md)：安装、启动 API／Worker、提交组件、查看报告。
- [架构与代码导航](docs/ARCHITECTURE.md)：各模块只负责什么、应从哪个文件开始读。
- [实验复用清单](docs/REUSE_MATRIX.md)：保留哪些实现、为什么保留、没有做哪些“优化”。

## 唯一默认主链

Vue → 内置 SSM 提取 → 原实验生成 Prompt／few-shot → San → 静态／编译／结构／视觉／交互检查 → 原规则或模型修复 → 同口径复测 → 接受／回退 → 报告。

LangGraph 负责真实编排；LangSmith 为显式启用的追踪；LoRA 数据／训练／推理属于研究模块，不参与每次在线迁移训练。没有用新的模型、Prompt 或规则替换实验实现。

```text
migration_system/
├─ frontend/              网页工作台
├─ src/card_migration_system/
│  ├─ interfaces/         HTTP API 与 CLI
│  ├─ application/        任务、版本和调用账本
│  ├─ graph/              LangGraph 主图
│  ├─ stages/             生成、检查、评估、修复
│  ├─ adapters/           内置引擎、模型与浏览器边界
│  ├─ prompts/            固定生成／修复请求构造
│  ├─ persistence/        数据库、检查点与备份
│  └─ training/           few-shot 语料及 LoRA
├─ engine/                内置实验实现＋来源 MANIFEST
├─ browser/               Puppeteer、截图和指标
├─ configs/               配置及自建 few-shot 示例
├─ migrations/            数据库升级
├─ scripts/               统一入口和独立性检查
├─ tests/                 工程回归与复用对照
├─ docs/                  当前架构、复用说明及历史文档
└─ var/                   本系统自己的数据库、产物与验证结果
```

早期控制夹具页面只在点击“开发验证与历史”时加载，默认迁移页不查询其队列。G1—G3 是历史边界验证代码，不是额外的迁移主流程。相关历史说明在 [docs/history](docs/history/)；依赖旧实验数据的诊断脚本已移回实验仓库的 `tools/migration_system_history/`，不随独立系统运行。

## 数据及效果边界

新默认数据库为 `var/runtime/`，产物为 `var/artifacts/`。**原 `var/business.sqlite3` 和父目录中的历史实验文件没有移动或删除**；新工作台不自动混入它们，也不覆盖旧失败或用量。已有服务需停止并按新指南显式初始化新路径后重启。

重构验证不等于重新获得真实模型迁移成功率。既有未支持语义仍明确阻断，不降低阈值以恢复表面通过率；API Key、LangSmith 及 LoRA 权重配置见 [SETUP_PENDING.md](SETUP_PENDING.md)。本目录部署支持源码目录形态，不能直接移动 `.venv` 或宣称单独 wheel 已包含前端和 Node 依赖。

用户另行授权的公开实例代理在 `research/public_instance_v1` 至 `public_instance_v7` 研究，尚未接入主链。v2 修对象／watcher，v3 补嵌套控件，v4 修有限调度，v5 连接 root owner，v6 验证父子／循环 scope。**v6 的 keyed 失败已在 v7 研究候选中修复，有限树场景由 3/4 到 4/4**；仅对固定 San 生成内存候选，不改生产 engine。完整契约及生产阻断保持，原生无 owner 的最终销毁顺序差异仍披露。见 [当前 v7 记录](docs/PUBLIC_INSTANCE_PROXY_V7.md)、[v6 历史失败](docs/PUBLIC_INSTANCE_PROXY_V6.md) 及此前研究记录。

用户随后确认保持 San 目标，不再要求复制 Vue 私有实例／vnode 图。新的 [San 业务实例契约](docs/SAN_BUSINESS_INSTANCE_CONTRACT_V1.md) 和 [可执行实现进度](docs/SAN_BUSINESS_RUNTIME_V1.md) 与旧证据分开：`runtime/san_business_v1` 已有自动源 Options 编译、独立导出、props／watch／DOM／公共 API 的有限对照及冻结商品筛选样本的 11 步交互重放。**默认 Worker 尚未接入，不是完整任意键契约发布**；重启服务器不会自动启用该目录，不要为启用该研究模块而付费复跑。普通范围内的新任务按当前启动指南验收，不受这项研究是否完成影响。
