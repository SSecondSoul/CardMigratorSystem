# 通用修复 v9：生命周期 AST 与真实模板恢复

2026-11-20。最终有效离线结果 **35 → 43/70**，新增8项、原通过无回退，仍有27项未闭合。真实模型v3仍15/70，没有改写为43/70。最终报告和Notebook位于根目录 `experiment_runs/composed_v9_scope_review_20261120/`。

## 最终结果与口径

- 主规则版本249项同版回归及独立目录运行通过。完整70项登记回放得到42/70，暴露一项新增词法归属误报：局部回调变量module被算为CommonJS导出引用，错误影响CourseModuleAccordion。原42/70、全部失败及实现快照保留，不覆盖。
- 最后只修正父方法元数据的词法引用计数及引擎清单。保留修复前2项RED（1失败）；修正后既有7项＋新增2项共9项AST专项在当前版本通过，独立目录运行再次通过。249与9是不同实现版本，明确分列，不虚报258项同版通过。
- 对69份相同有效代码重新做语法／静态检查，没有提出新代码候选；只有父元数据函数变化，AST证明其余程序节点不变。源／目标代码、props、动作、阈值及全部渲染实现一致才显式复用65份旧捕获；CourseModuleAccordion额外保存当前版本真实浏览器确认1份。3份脚本语法失败仍先停，1项未知模型调用无产物不重试。旧恢复门证据没有重新授权或伪装成当前新证据。
- 新增通过：BatchRenamer、DataPaginationTable、FileDropIndicator、PollResults、SearchClearField、StatusSwitch、TipSplitCalculator、VolumeControl。AccessMatrix／MediaReviewStudio恢复运行但仍有其他诊断，不计完整通过。
- 7166个历史文件、955个主回放文件前后哈希不变；早期18项CommonJS入口中止预检、所有拒绝候选及主版本249项均保留。

生成仍为完整SSM＋模型，没有整体规则生成或公开实例代理；未调用真实模型、未写云数据库、未重启用户服务。现在不把一轮付费复跑当作27项问题已闭环的证明。

## 本轮实现

| 根因 | 修改位置 | 保留的保护 |
| --- | --- | --- |
| 生命周期正则漏认引号／函数属性，或认错子组件；局部module/exports名称被误计为全局命名空间 | `engine/.../bounded_semantics.cjs`、`stages/validate.py`：导出父对象的AST方法元数据、词法引用及真实方法体 | 空钩子、重复键、箭头／未知别名、子钩子、字符串、真正全局别名／San修改仍不构成证明 |
| 初始化恢复夹带其他修改，不能通过旧窄恢复证明 | `stages/normalization.py`、`adapters/legacy_worker.py`：先独立提出纯源初始化恢复 | 不是放宽所有新错误；额外CSS／业务变更不能借用源初始化证明 |
| 恢复运行后控件诊断从缺失变成位置差异 | `adapters/browser.py`、`stages/dom_comparison.py`、`stages/evaluation.py`：精确整份代码／源／props／动作／运行实现绑定 | 要求运行恢复、实际控件值和数量一致及DOM进展；位置／结构仍失败，其他新错误仍回退 |
| 合法原生绑定空白漏匹配 | `browser/attribute-syntax.mjs`：识别简单单向／双向绑定语法并反射实际HTML属性 | 不把未知复杂表达式或错字段当作相同绑定，不删除原绑定／事件 |
| 生成的多余文本span、属性或静态化option绑定 | 同上：源／目标原生标签及完整祖先作用域匹配后，局部修复真实模板 | 有属性span、错文本、源拥有的span、未知组件覆盖／展开／HTML内容、不同循环作用域不改 |
| Vue/San字符串class首尾空白序列化不同 | 同上：有限纯状态条件和精确源表达式的目标class trim | 保留空class属性和响应更新；CSS精确观察仍严格检查，不添加TED忽略项 |

生成和修复共享约束升级 `san-shared-generation-repair-v6`，同步要求保留原生属性、源DOM节点及class实际序列化。生成仍是完整SSM＋模型，没有整体AST规则生成、公开实例代理、组件名特判、预算或质量阈值变化。

## 验证及证据安排

- `experiment_runs/check_general_repairs_v9.py`：补齐导出入口后的固定实现与测试源码回归，最多2个隔离测试模块并行、验证进程上限480秒，不改变生产超时或额度。输出在 `docs/verification/2026-11-20_followup_v9/export_verified/`。首版247项报告及两次更早中止预检各自保留，不与新版本混合。
- `experiment_runs/replay_sequential_v9_verified.py`：只从v8门禁后的有效代码开始，在新目录重新检查全部有产物项，再经生产规则、真实浏览器及普通门禁；被拒候选不作父版本。旧 `composed_v9_final_replay_20261120/` 的18项预检有STOPPED、部分结果及原实现快照。
- `experiment_runs/summarize_sequential_v9.py`：保留主规则版本42/70、逐组件对照及249项同版验证。
- `experiment_runs/reassess_parent_scope_v9.py`、`summarize_parent_scope_v9.py`：最终43/70复核，捕获复用明确标注、当前9项专项及独立副本另存，生成最终逐组件原因、Notebook及校验清单。
- `docs/verification/2026-11-20_followup_v9/`：保留生命周期修复前RED和中止预检。
- `experiment_runs/composed_v9_call_owner_audit_20261120/`：对v8全部6项剩余动态赋值诊断做AST调用归属审计。3项有watch选项回调，另见定时器私有句柄、箭头体及局部缓存／完整调用体问题。仅为定位，不据此放行。

本轮不调用真实模型、不访问云数据库、不重启API／Worker、不修改历史源码／失败报告。完整结果尚未收齐时，不要求用户重跑70项付费批次。
