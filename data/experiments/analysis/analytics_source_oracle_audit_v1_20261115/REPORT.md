# AnalyticsDashboard 源基准警告审查 v1

日期：2026-11-15。结论：**诊断完成，源端对照仍阻断；未修正冻结源码、未执行正式交互验收。**

## 1. 已确证根因

冻结 Vue 源码内联 TrendChart 的两个循环在同一 svg 下：

- 第 148 行：网格 g 使用 `:key="i"`，实际键为 1、2、3、4、5。
- 第 173 行：数据点 g 使用 `:key="idx"`，默认 30 点的键为 0–29。

模板编译和 Vue 2.7.16 规范化后的真实 VNode 显示，这 35 个带键 g 是同一组兄弟节点，不存在由两个 v-for 自动提供的独立 key 命名空间。因此键 1–5 冲突。全组件原生重放仍产生 10 条 TrendChart 重复键警告，与此前封存记录一致；旧日志的 console_error 是验收打包器把 Vue warnHandler 转送 console.error，并不是 10 个不同业务异常。不能根据日志传输等级改变已批准的源 warning 阻断口径。

这是真实源输入的重复兄弟键问题，不是本轮 San 生成/repair Prompt 出错，也不是根据 San 症状猜测。旧打包器没有改内联模板；本步仅增加只读 VNode 观察，完整源/目标业务字段、截图 SHA 与旧原生记录一致。没有去掉 warning、切生产版 Vue、修改阈值或暗改源码。

## 2. 机制对照，不是组件修复

在诊断夹具中使用同一源脚本导出的 TrendChart，正常父传 props 更新两次；只给控制版本的两个 key 加命名空间（grid-/point-）。源码文件、生产规则和目标产物不写回。

| 数据点数 | 原模板重复键 | 原模板警告数 | 命名空间对照警告数 | 两者像素差 |
|---|---|---|---|---|
| 1 | 无 | 0 | 0 | 0 |
| 2 | 1 | 2 | 0 | 0 |
| 7 | 1–5 | 10 | 0 | 0 |
| 30 | 1–5 | 10 | 0 | 0 |
| 90 | 1–5 | 10 | 0 | 0 |

最终一次原生运行 12 页：完整 Vue/San 2 页 + 5 对机制夹具 10 页。身份/独立上下文/处置完整，总 42 条原生诊断均可归属，其中完整 Vue 10 条、机制原模板 32 条；命名空间对照及完整 San 无诊断。5 个可比夹具的 PNG 指标独立解码重算一致；完整组件尺寸不同，不编造 SSIM 或缩放。

这里验证的是重复键的成因与一种受限改法，并未运行根组件“7天/90天切换、刷新”验收。控制用父更新和 VNode 检查不是人的实际下拉选择，也不能证明任意序列或完整业务等价。没有新组件综合或人工通过。

## 3. 仍独立存在的问题

完整 Vue 高度 1326，San 高度 1625，7 项关键矩形差异和旧截图保持。**不把这些差异一概归因于重复 key，也不宣称 key 命名空间能消除它们。**即使未来经批准修正源 key，仍需新的源基准验证、输入重新绑定，再单独诊断目标布局/后续交互。

当前严格源 warning/error 策略保留，Analytics 的三个拟交互场景继续未验收。任意公开键、通知/异常等既有语义边界不豁免，生产接入/全量场景/依赖重绑定/全批冻结不因本步就绪。

## 4. 失败尝试及测试

首次诊断的 12 页尝试保留在 `native/`，另有其自身 checksum 和 `failed_implementation.json`，不是组件生产失败：

1. 新只读观察箭头表达式括号错误导致完整源页 SyntaxError / readiness timeout。
2. 单点折线是零面积 SVG 几何，不适合列为“必须有正面积”的关键元素，两个单点夹具被设施检查阻断。

它们属于诊断夹具问题。只修正观察表达式、增加全部页面脚本的启动前语法检查，将单点夹具的必需关键元素改为可见 legend，继续只读记录折线 points；未改通用渲染器、裁切画面或放宽阈值。新目录 `native_retry/` 重跑完成，旧失败不覆盖。首次 registry incomplete / passed=false 保留，不能拼成通过。

最终 **205/205 定向测试**，失败/错误/跳过 0：本步 16 + 历史口径 46 + 原生反馈 90 + 会话归属 53。不是全仓库或上步 249 项 campaign；上步 100 个实现/测试/说明指纹稳定，不声称重跑其余测试。

## 5. 已记录及未授权事项

保持不变：100 个旧相关文件、3 个人工配置、4 份参考、6 个选中冻结 SFC、30 对当前/历史主 Vue、上步 114 payload/closeout 和旧原生 96 payload。旧批次仍 24/30、失败 6、执行错误 0、token 1,821,544。

Notebook 只追加两个单元，保留原 145 单元及 metadata；检查 JSON、编译全部代码，并从根目录和 Notebook 目录执行新增只读单元。不启动 Notebook UI。报告技能用于把源基准 remaining_risk、诊断夹具失败、机制对照与目标迁移缺陷分开，不回填旧缺陷率。

本步模型/新人工组件通过/commit/push 均 0。源码勘误尚未授权。建议下一步请用户决定：是否另建一个**独立源码勘误版本，仅命名空间化两个 key**，旧输入、旧产物、旧成绩全部保留；批准后仍要重建源基准、绑定新 SHA，并分别处理布局/交互。若不修源，就保留源基准阻断，不吞警告、剔除样本或认定通过。

## 复核入口

项目根目录：

```powershell
python migration_pipeline/check_analytics_source_oracle_v1.py
python -m unittest discover -s tests -p test_analytics_source_oracle_v1.py -v
```

上述只读检查不启动浏览器或模型。浏览器诊断如需再跑，必须另用新目录：

```powershell
node migration_pipeline/audit_analytics_source_oracle_v1.cjs data/experiments/analysis/analytics_source_oracle_v1_retry --execute
```

证据索引：`baseline.json`、`native/`、`native_retry/`、`failed_implementation.json`、`audit.json`、`implementation.json`、`tests.json`、`metric_replay.json`、`notebook_append.json`、`verification.json`、`SHA256SUMS.txt`。封存后执行与 checksum 外部固定记录另存相邻 `analytics_source_oracle_audit_v1_20261115_closeout.json`。本机字体/完整传递依赖和 CDP 完整参数时序认证等已知边界仍保留，不新增互操作功能或用户业务材料要求。
