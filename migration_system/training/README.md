# 模型训练

早期此目录仅为预留；当前已有以下执行模块。实际权重、硬件、许可与训练证据仍待落实。
# 当前 LoRA 与数据模块

2026-11-16 已实现 `src/card_migration_system/training/data.py` 和 `lora.py`，不是只列配置的占位：包含 SSM／San 指令数据构建、group／split 精确重复保护、提示部分 labels=-100、PEFT LoRA、可训练参数检查、Trainer、训练日志、适配器保存和加载推理。没有实际安装训练依赖、下载权重或启动训练，因此没有训练成果或效果提升结论。

建议另建 Python 3.12 训练环境；当前 Web 系统的 Python 3.14 环境不自动安装 Torch。参考 `requirements.txt` 在训练机器解析并保存依赖锁，记录 GPU／驱动／CUDA／包版本。基础模型必须已有本地权重、正确 tokenizer、许可允许；`trust_remote_code=False`／`local_files_only=True`，不会自动下载或执行远程模型代码。

1. 复制 `pairs.example.json`，填写本人审核的 Vue／San 对、来源 group 与 train／validation／test。路径相对清单文件；同组不能跨集合，相同源码／目标字节拒绝重复。精确去重不能代替人工审核同源变体和早期接触。
2. 在训练环境安装本包及可选依赖后，从仓库根目录构建：

```powershell
python migration_system/scripts/run_system.py build-training-data --manifest path/to/pairs.json --output migration_system/var/training/dataset-v1
```

3. 复制 `config.example.json`，填写本地基座、数据路径、显卡可承受的参数、全新输出目录，在核实许可后设 `license_confirmed=true`。显式执行：

```powershell
python migration_system/scripts/run_system.py train-lora --training-config path/to/train.json --execute
```

4. 保存请求、基座文件哈希、数据哈希、可训练参数数目、环境版本、逐步日志、训练／验证指标、adapter 权重／配置与 tokenizer。数据过长会阻断，不静默截掉目标答案。
5. 推理环境也需训练依赖；在 `configs/system.toml` 选择 `model.backend="local_lora"`，填写 `learning.base_model_path` 与 `adapter_path`，创建新任务。该模型通过同一评估／修复／候选门，不绕过质量检查。权重内容在调用前登记并复核漂移。

默认 few-shot 使用系统自建的两个小型开发演示；研究数据可将 manifest 指向构建出的 `few-shot.json`。只选 train 样本，排除当前源码／组和批量评估全部组；实际选中内容在请求中冻结。示例正确性和数据来源仍需审核，不能将验证／测试答案混入 train。

实际训练后再进行基座／LoRA 同基座对照。不同云 API 和本地基座的差异不能全归因 LoRA。下文旧预留说明保留为历史，不代表当前代码仍未实现。

