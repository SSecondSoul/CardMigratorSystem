# 中间诊断：场景预期错误

本目录有完整原始浏览器观察及 SHA256SUMS 清单，但 explicit_expected_products_passed 为 false。双端实际列表顺序相同；夹具误用了输入数组顺序，并假设 clear 重置 sort。源组件实际先按名称排序，clear 只重置过滤字段而保留排序，后续 v4 据此修正预期并重新验证。

本目录仍然 passed=false；静态契约和严格 DOM 均未通过。不得将错误夹具的失败当作迁移回退，也不得把实际值相同当作完整交互通过。本说明在清单后补写，不在 payload 清单中。
