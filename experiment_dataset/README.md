# 新一轮实验数据集：70／20／10

用于开展新一轮实验，独立放置在仓库根目录的 `experiment_dataset/`，不在 `migration_system` 内。共 100 个组件，按复杂度分层划分为实验集、验证集和测试集，比例为 **7∶2∶1**。

| 复杂度 | 实验集 experiment | 验证集 validation | 测试集 test | 合计 |
| --- | ---: | ---: | ---: | ---: |
| 简单 | 24 | 7 | 3 | 34 |
| 中等 | 23 | 7 | 3 | 33 |
| 复杂 | 23 | 6 | 4 | 33 |
| 合计 | **70** | **20** | **10** | **100** |

## 目录与用途

```text
experiment_dataset/
├─ experiment/         70 个，用于实验开发、Prompt／规则调整
├─ validation/         20 个，用于版本比较、阈值与方案选择
├─ test/               10 个，用于方案冻结后的本轮测试
├─ manifest.json       组件清单、划分记录、来源和哈希
├─ SHA256SUMS.txt       组件文件及各清单的完整性摘要
├─ prepare_split.py    只读重建分配计划／校验，不自动覆盖文件
└─ tests/              划分与文件完整性回归
```

各集合下保留 `01_simple／02_medium／03_complex/组件名/vue／san` 层级和组件附带文件。同一组件的 Vue 与 San 放在同一集合中，每个集合有自己的 `manifest.json`。

实验时使用 Vue 作为输入，`san/` 作为参考版本；本轮生成代码、报告和统计另存，不覆盖数据文件或复用旧运行结果。验证集用于选择方案，方案冻结后再运行测试集。

固定划分种子为 `20261118`，详细分配规则与来源记录保留在 `prepare_split.py` 和 `manifest.json`。

## 校验

在本文件夹中：

```powershell
python prepare_split.py --check
```

在原仓库位置还可核对原组件和来源清单未变化：

```powershell
python prepare_split.py --check-sources
python -m unittest discover -s tests -p test_split.py -v
```

`--plan-json` 输出划分与复制计划，不自动覆盖文件。
