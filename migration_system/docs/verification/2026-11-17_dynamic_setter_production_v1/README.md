# 动态 setter 有限生产接入验证

2026-11-17，用户要求实际迁移现有复杂组件。范围为 san-supported-migration-v2，生产编译轮廓为 dynamic-setter-single-component-v1；完整公开实例契约仍未完成。

## 文件与口径

- `before/task.json`、`before/source.vue`：只读核对旧 API 任务 b05e37a0254b4f5583d9c30c0f1bd3bb 和仓库源码后保存。源 SHA-256 为 f84efcfbc0b57731e358ff24264f6600a3a64fa58e725290f77799f4e7ac1d02，旧阻断和零调用不改写。
- `before/runtime`、`before/migrations.py`、`before/production_scope.py`、`before/tests`：修改前的实际文件。研究测试原件保留，活跃测试仅更新生产版本沿革断言；研究 CJS、旧封存 payload 和行为预期不改。
- `after/standalone.json`：最终代码稳定后运行 verify_standalone.py 的实际成功结果及全实现／依赖辅助文件指纹。仓库外副本真实执行 AST／SSM、LangGraph、San、浏览器和 API 下载。复杂组件不使用模型替代，普通 CounterCard 检查原修复链时使用两次明确模型响应夹具，真实模型均未调用。
- `after/replay`：实际源／San 产物、manifest、SSM、9 步浏览器原始观察、截图／热图和重放结果。初始及每步 DOM／样式／控件检查，**图片是最终状态，不是逐步截图**。静态作用域为规范源方法／接收者和模板绑定复核，不冒充旧语义分析器已经理解新导出。
- `checks.json`：从成功命令输出整理的测试汇总，不是原始 unittest 日志；`inventory.json` 仅纯编译盘点，不是迁移通过统计。
- `after/implementation`：本轮生产接入／模板／表达式／DOM／运行时／前端及测试代码副本；不包含用户密钥／TOML，也不重新归档全部第三方依赖。精确依赖指纹在 manifest 中。

首轮中间观察发现选中状态未及时着色和 option 属性差异，后来真实修复。该中间观察来自测试输出，不将汇总冒充具有完整同指纹源码／原始截图的修复前重放；修复前材料的确切范围以上述 before 清单为准。

## 最终结果

CapacityPlanningBoard 初始与 9 步配置检查通过：六维通过，结构／DOM 相似度 1，UI 100%，最终 SSIM 1、不同像素 0。源 Vue 未改；生产导出任意外部键专项验证了 Symbol、字面点号／方括号、原生同名键、一次键转换和异常身份。规范产物／manifest／SSM 绑定篡改被拒绝，静态退化候选不能接受。

含该 setter 的 23 个 complex 中，17 个编译通过、6 个明确阻断。除 CapacityPlanningBoard 外，不宣称其余已进行真实整图／交互验收。旧失败、费用、独立测试集标签和分母不改判。

本轮没有操作用户真实数据库／队列、修改配置、调用付费模型、上传 LangSmith、训练、commit 或 push。用户下一步见 [指南](../../../SYSTEM_GUIDE.md)：重启、新建原源码任务、配置 9 步动作、查看确定性生成来源与六维结论，然后独立人工验收。
