"""Freeze the formal_30_v1 experiment protocol as an immutable evidence bundle."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GIT_HEAD = "4c18a4b6a908139a285648be2f81b7ec8a75196c"
PROTOCOL_ID = "formal_30_v1_frozen_20261015"
TARGET = ROOT / "data/experiments/protocols" / PROTOCOL_ID
SPLIT_PATH = "data/datasets/splits/pilot_9_v6_development_and_formal_30_v1.json"
CONFIG_PATH = "migration_pipeline/batch_configs/formal_30_v1.json"


def git_output(*args: str) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def committed_bytes(path: str) -> bytes:
    return git_output("show", f"{GIT_HEAD}:{path}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def config_fingerprint(config: dict) -> str:
    canonical = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(canonical.encode("utf-8"))


def write_frozen(path: str, data: bytes) -> None:
    destination = TARGET / "frozen" / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)


def tracked_paths(prefixes: tuple[str, ...]) -> list[str]:
    paths = git_output("-c", "core.quotePath=false", "ls-tree", "-rz", "--name-only", GIT_HEAD, *prefixes).decode("utf-8").split("\0")
    return sorted(path for path in paths if path)


def protocol_markdown() -> str:
    return """# formal_30_v1 正式实验协议（冻结版）

冻结日期：2026-10-15（Asia/Shanghai）  
协议 ID：`formal_30_v1_frozen_20261015`  
代码基线：`4c18a4b6a908139a285648be2f81b7ec8a75196c`

## 1. 实验目的与数据边界

本实验评估 Vue 2 单文件组件经 SSM、LLM 生成、静态校验、DOM 结构评估和最多三轮 repair 后迁移为 San 组件的效果。

- 数据集共 100 对组件。
- 开发集 70 个：9 个 pilot 调优样本和 61 个未进入测试集的样本。
- 独立测试集 30 个：simple、medium、complex 各 10 个。
- pilot_9_v2-v6 使用过的 9 个样本不得进入独立测试集。
- 30 个测试样本的原始 Vue 是正式输入。
- 配对的参考 San 仅作为封存答案；正式自动运行结束前，禁止将其用于 prompt、repair、规则调整、样本剔除或人工纠错。

## 2. 固定系统与参数

- LLM provider：`qwen`
- LLM model：`qwen-plus`
- API：DashScope OpenAI-compatible chat completions 默认地址
- temperature：`0.2`
- generation timeout：`300` 秒
- repair timeout：`300` 秒
- LLM HTTP timeout：`120` 秒
- 最大 repair 轮数：`3`
- DOM structure similarity 阈值：`0.95`
- DOM text similarity 阈值：`0.8`
- 健康检查：启用
- 报告状态：使用 `--include-state` 保留完整过程证据
- 模型 API 不支持固定 seed，因此需将模型随机性列为实验局限；不得通过挑选多次运行中的最佳结果消除随机性。

## 3. 主评估口径

所有 30 个样本均进入主评估，禁止事后删除失败样本。报告至少包含：

1. 初次生成通过率与最终通过率；
2. simple、medium、complex 分层通过率；
3. repair 后转为通过的样本数、总轮数和平均轮数；
4. generation、repair 与总 token；
5. stop reason、静态错误码与视觉错误码分布；
6. execution error 单独统计，不得算作通过，也不得从分母移除；
7. 结构、标签和文本相似度等原始指标保留在逐样本报告中。

`final_passed` 是自动主结果。当前 formal 配置未预置确定性交互场景，因此自动通过不能表述为“全部交互正确”。

## 4. 人工验证口径

自动运行完成后，再对下列预注册的 9 个代表样本进行真实浏览器人工对照，每个复杂度 3 个：

- simple：`password_strength_meter`、`session_timeout_notice`、`delivery_phase_card`
- medium：`poll_results`、`image_crop_controls`、`attendance_roster`
- complex：`inventory_batch_manager`、`media_review_studio`、`energy_load_scheduler`

人工验证记录初始渲染、主要状态变化、动态样式、禁用状态和核心交互。人工结果作为次级结果单独报告，不覆盖自动结果，也不得据此修改本批输出后重新计分。

## 5. 冻结与偏差规则

正式运行开始后，以下内容不得改变：测试样本、Vue 输入、SSM 提取器、generation/repair prompt、validator、renderer、相似度阈值、模型、temperature 和最大 repair 轮数。

- 网络中断、限流或服务进程退出属于基础设施异常。可用同一命令从 checkpoint 继续，必须记录中断与恢复时间。
- 不得使用 `--force`，避免覆盖已完成样本并引入选择性重跑。
- 不得只重跑失败样本来替换正式结果。
- 如果发现算法或评估器缺陷，本批按原协议保留结果；修复后必须建立新的配置和协议版本，例如 `formal_30_v2`。
- 任何不可避免的协议偏差都必须写入最终报告，说明原因、时间和影响，原始结果不得删除。

## 6. 正式运行命令

先在一个 PowerShell 终端配置密钥并启动服务（密钥不得写入仓库）：

```powershell
$env:LLM_API_KEY="<secret>"
$env:LLM_PROVIDER="qwen"
$env:LLM_MODEL="qwen-plus"
python -m local_server.app
```

在另一个已激活 `cardmig` 环境的 PowerShell 终端运行：

```powershell
python migration_pipeline/run_batch_pipeline.py `
  --config-file migration_pipeline/batch_configs/formal_30_v1.json `
  --include-state
```

若发生可恢复的基础设施中断，使用完全相同的命令继续。checkpoint 会跳过状态为 completed 的样本。

## 7. 固定输出位置

- 生成代码：`data/experiments/pipeline/batches/formal_30_v1/`
- 逐样本报告：`data/experiments/repair_reports/batches/formal_30_v1/`
- 汇总 checkpoint：`data/experiments/batch_reports/formal_30_v1_summary.json`
- 人工验证记录：应新建在 `data/experiments/manual_validation/`，不得修改自动报告。

## 8. 完整性校验

正式运行前执行：

```powershell
python data/experiments/protocols/formal_30_v1_frozen_20261015/verify_protocol.py --live
```

只有协议包校验和与 live 文件均通过，才允许开始正式实验。
"""


def verifier_source() -> str:
    return '''"""Verify the frozen protocol payload and optionally the live workspace."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Also compare frozen files with the workspace.")
    args = parser.parse_args()
    failures = []
    entries = []
    for line in (HERE / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        entries.append((expected, relative))
        path = HERE / relative
        if not path.is_file():
            failures.append(f"missing protocol file: {relative}")
        elif digest(path) != expected:
            failures.append(f"protocol checksum mismatch: {relative}")
    if args.live:
        for expected, relative in entries:
            if not relative.startswith("frozen/"):
                continue
            live_relative = relative[len("frozen/"):]
            live = ROOT / live_relative
            if not live.is_file():
                failures.append(f"missing live file: {live_relative}")
            elif digest(live) != expected:
                failures.append(f"live file differs from frozen baseline: {live_relative}")
    if failures:
        print("protocol verification: FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"protocol verification: PASS ({len(entries)} checksums, live={args.live})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(f"Refusing to overwrite frozen protocol: {TARGET}")
    if git_output("rev-parse", "HEAD").decode().strip() != GIT_HEAD:
        raise RuntimeError("Git HEAD differs from the preregistered baseline commit")
    for output in (
        ROOT / "data/experiments/batch_reports/formal_30_v1_summary.json",
        ROOT / "data/experiments/pipeline/batches/formal_30_v1",
        ROOT / "data/experiments/repair_reports/batches/formal_30_v1",
    ):
        if output.exists():
            raise RuntimeError(f"Formal output already exists; pre-execution freeze aborted: {output}")

    if subprocess.run(["git", "diff", "--quiet", GIT_HEAD, "--"], cwd=ROOT).returncode != 0:
        raise RuntimeError("Tracked workspace files differ from the preregistered baseline commit")

    split_bytes = (ROOT / SPLIT_PATH).read_bytes()
    config_bytes = (ROOT / CONFIG_PATH).read_bytes()
    split = json.loads(split_bytes)
    config = json.loads(config_bytes)
    samples = split["independent_test"]["samples"]
    if len(samples) != 30 or len(config["samples"]) != 30:
        raise RuntimeError("Formal split or config does not contain exactly 30 samples")

    code_paths = tracked_paths(("SSM", "local_server", "migration_pipeline", "tests"))
    root_paths = [path for path in ("environment.yml", "requirements.txt", "package.json", "package-lock.json") if (ROOT / path).is_file()]
    dataset_paths = [
        "data/datasets/dataset_manifest.json",
        "data/datasets/features/pattern_tags.json",
        SPLIT_PATH,
    ]
    sample_paths = []
    for sample in samples:
        sample_paths.extend((sample["vue_file"], sample["san_file"]))
    archived_paths = sorted(set(code_paths + root_paths + dataset_paths + sample_paths))
    for path in archived_paths:
        source = ROOT / path
        if not source.is_file():
            raise FileNotFoundError(f"Tracked protocol input is missing: {path}")
        write_frozen(path, source.read_bytes())

    manual_sample_ids = [
        "password_strength_meter",
        "session_timeout_notice",
        "delivery_phase_card",
        "poll_results",
        "image_crop_controls",
        "attendance_roster",
        "inventory_batch_manager",
        "media_review_studio",
        "energy_load_scheduler",
    ]
    manifest = {
        "protocol_id": PROTOCOL_ID,
        "status": "frozen_pre_execution",
        "frozen_at": "2026-10-15T14:28:31+08:00",
        "timezone": "Asia/Shanghai",
        "git_head": GIT_HEAD,
        "git_commit_time": "2026-10-13T17:11:28+08:00",
        "git_commit_subject": "更新交接文档，划分测试集和实验集pilot_9_v6_development_and_formal_30_v1.json",
        "tracked_worktree_clean_before_freeze": True,
        "batch": {
            "id": "formal_30_v1",
            "config": CONFIG_PATH,
            "config_sha256": sha256_bytes(config_bytes),
            "config_git_blob_sha256": sha256_bytes(committed_bytes(CONFIG_PATH)),
            "config_fingerprint": config_fingerprint(config),
            "split": SPLIT_PATH,
            "split_sha256": sha256_bytes(split_bytes),
            "split_git_blob_sha256": sha256_bytes(committed_bytes(SPLIT_PATH)),
            "sample_count": 30,
            "counts_by_complexity": {"simple": 10, "medium": 10, "complex": 10},
            "max_repair_rounds": 3,
        },
        "model": {
            "provider": "qwen",
            "model": "qwen-plus",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            "temperature": 0.2,
            "seed": None,
            "seed_note": "The current client does not send a seed; stochasticity is a documented limitation.",
            "api_key_stored": False,
        },
        "pipeline": {
            "generation_api_url": "http://127.0.0.1:8787/api/evaluation/generate",
            "repair_api_url": "http://127.0.0.1:8787/api/evaluation/repair",
            "generation_timeout_seconds": 300,
            "repair_timeout_seconds": 300,
            "llm_timeout_seconds": 120,
            "structure_similarity_threshold": 0.95,
            "text_similarity_threshold": 0.8,
            "health_check": True,
            "include_state": True,
            "force": False,
        },
        "primary_evaluation": {
            "population": "all 30 independent-test samples",
            "metrics": [
                "initial and final pass rate",
                "pass rate by complexity",
                "repaired-to-pass count and repair rounds",
                "generation, repair, and total tokens",
                "stop reason and error-code distributions",
                "per-sample DOM similarity metrics",
            ],
            "execution_errors_remain_in_denominator": True,
            "interaction_claim_excluded": True,
        },
        "manual_secondary_evaluation": {
            "preregistered_sample_ids": manual_sample_ids,
            "count": len(manual_sample_ids),
            "per_complexity": 3,
            "performed_after_automated_batch": True,
        },
        "reference_san_policy": "Frozen for integrity only; embargoed from prompts, repair, tuning, and sample selection until the automated batch is complete.",
        "execution_command": "python migration_pipeline/run_batch_pipeline.py --config-file migration_pipeline/batch_configs/formal_30_v1.json --include-state",
        "resume_policy": "Repeat the identical command after infrastructure interruption; checkpoint skips completed samples; never use --force.",
        "output_paths": {
            "pipeline": "data/experiments/pipeline/batches/formal_30_v1",
            "repair_reports": "data/experiments/repair_reports/batches/formal_30_v1",
            "summary": "data/experiments/batch_reports/formal_30_v1_summary.json",
        },
        "preflight": {
            "dry_run": "passed",
            "unittest_command": "python -m unittest tests.test_batch_pipeline_runner tests.test_interaction_eval tests.test_migration_pipeline_regressions tests.test_repair_prompt_and_loop tests.test_ssm_event_extraction",
            "unittest_result": "30 tests passed",
            "python": "3.14.7",
            "node": "24.19.0",
            "npm": "11.17.0",
            "flask": "3.1.3",
            "pyyaml": "6.0.3",
            "formal_outputs_absent": True,
        },
        "frozen_payload_root": "frozen",
        "frozen_payload_file_count": len(archived_paths),
        "integrity_file": "SHA256SUMS.txt",
        "verification_command": f"python data/experiments/protocols/{PROTOCOL_ID}/verify_protocol.py --live",
        "known_limitations": [
            "The LLM request has temperature 0.2 and no fixed seed.",
            "Automated final_passed does not establish full browser interaction equivalence.",
            "The observed Python runtime is 3.14.7 while environment.yml declares Python 3.12.",
        ],
    }

    TARGET.mkdir(parents=True, exist_ok=True)
    (TARGET / "PROTOCOL.md").write_text(protocol_markdown(), encoding="utf-8")
    (TARGET / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (TARGET / "verify_protocol.py").write_text(verifier_source(), encoding="utf-8")

    checksum_paths = sorted(path for path in TARGET.rglob("*") if path.is_file() and path.name != "SHA256SUMS.txt")
    checksum_lines = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(TARGET).as_posix()}" for path in checksum_paths]
    (TARGET / "SHA256SUMS.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(f"frozen protocol: {TARGET.relative_to(ROOT)}")
    print(f"payload files: {len(archived_paths)}")
    print(f"checksums: {len(checksum_lines)}")


if __name__ == "__main__":
    main()
