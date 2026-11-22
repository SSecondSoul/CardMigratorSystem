# class 原始空白与解析后内容的定位

2026-11-20。最初专项执行2项测试，1项失败：`test_finite_string_class_is_repaired_in_actual_dom_not_comparison_policy`。异常为未找到 `source_string_class_trim_v1`（`changes=[]`），该次执行16.889秒，不计入最终通过。

只读解析探针 `experiment_runs/probe_class_trim_v9.mjs` 定位：对目标 `class=" {{busy ? 'busy' : ''}}"`，compiler-dom 的 `value.content` 已去除最前面的空格，但 `value.loc.source` 仍保留字面原文。因而以解析后内容匹配源字符串前缀，恰好漏掉了要修的空白差异。

修复改为读取引号内原始字面字节，仅在有限纯状态条件、源表达式及所有原生祖先归属可证明时生成trim后的实际目标class；保留空class属性。初步专项2项通过（32.153秒），包括CSS直接观察class字节的真实浏览器测试。随后又补充所有新模板规则的祖先归属／展开拒绝保护，最终结论以 `composed_v9_closed` 的固定版本完整回归为准，不混用初步版本。

没有对DOM TED新增忽略规则，没有把CSS精确class观察判为不可见，也没有通过只修改评估报告来消除差异。
