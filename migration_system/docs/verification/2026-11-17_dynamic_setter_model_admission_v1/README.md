# 撤销规则生成，仅放行动态 setter 预检查

2026-11-17，用户明确纠正此前范围偏离：不允许用确定性转换替代模型生成。当前支持范围为 `san-supported-migration-v3`，不是新的论文实验批次。

## 当前变更

- 删除 `src/card_migration_system/stages/business.py` 及其生产计划／生成、专用静态校验和规则失败停止分支。
- 原 `stages/generate.py` 和 `graph/migration.py` 已恢复为最初模块化版本的相同字节；模型 Prompt、内置 engine、原验证、原规则／模型修复不改。
- 仅忽略源码契约识别器给出的 `source_dynamic_key_contract_unsupported` 预阻断，继续模型配置检查、SSM 和模型生成。其他契约错误、真实语法／依赖错误、费用及质量门不豁免。
- 不改源 `this[key] = value`，不按组件名或固定调用键判断，不缩小键域，不把放行写成等价证明。
- 离线 runtime/research 保留，但不在生产模块和运行绑定中使用。独立验证副本未复制该运行时目录，仍可执行原链。
- 历史 `dc9c942c547745ed989bc3db583af744` 规则结果不改判、不计为模型迁移成功；旧 79 个封存 payload 的 SHA-256 全部复核不变。

## 本次实际检查

| 检查 | 结果 |
| --- | --- |
| `test_modular_*.py` | 102 项通过，295.949 秒 |
| `test_dynamic_setter_production.py` | 7 项通过，22.865 秒 |
| `test_production_scope.py` | 5 项通过，2.686 秒 |
| `test_refactor_reuse.py` | 5 项通过，30.689 秒 |
| `test_san_business_contract_policy.py` | 7 项通过，0.166 秒 |
| 前端测试 | 22 项通过 |
| 前端类型检查及正式构建 | 通过 |
| 仓库外独立副本 | 通过，实际实现指纹见 [standalone.json](standalone.json) |

共 126 项上述 Python 检查，不是全部仓库测试或迁移样本数。真实云模型调用为 0，未修改用户配置／密钥、实际任务库／队列，未提交或推送。

独立副本使用真实 SSM、LangGraph、San、浏览器和明确的模型响应替代：CounterCard 经两次响应完成原修复、六维评估、下载及反馈；原 CapacityPlanningBoard 经一次响应证明其原源码进入模型 Prompt／记账并在生成后主动暂停，**没有声称复杂组件迁移质量通过**。专项另用故意错误响应配合实际 SSM，确认不等价复杂产物会失败；其他隔离用例检查原修复与候选门的调用顺序。

当前测试只证明流程恢复及边界保持。真实模型迁移结果仍需用户重启 API／Worker、刷新并创建新任务获得；不能以响应夹具通过代替论文效果。
