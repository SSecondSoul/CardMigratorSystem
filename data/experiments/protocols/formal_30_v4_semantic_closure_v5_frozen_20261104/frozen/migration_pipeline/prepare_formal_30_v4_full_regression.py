"""Prepare/freeze all 30 original samples for current-v4 development regression.

No option in this script contacts a model. The operator runs the batch separately.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from migration_pipeline.run_batch_pipeline import config_fingerprint, validate_batch_config


ROOT = Path(__file__).resolve().parents[1]
BATCH_ID = "formal_30_v4_full_regression"
BASE_CONFIG = ROOT / "migration_pipeline/batch_configs/formal_30_v3.json"
BASE_PROTOCOL = ROOT / "data/experiments/protocols/formal_30_v3_frozen_20261022"
BASE_SUMMARY = ROOT / "data/experiments/batch_reports/formal_30_v3_summary.json"
BASE_RESULT = ROOT / "data/experiments/snapshots/formal_30_v3_results_20261022_200548/formal_30_v3_summary.json"
CONFIG = ROOT / f"migration_pipeline/batch_configs/{BATCH_ID}.json"
TARGET = ROOT / f"data/experiments/protocols/{BATCH_ID}_frozen_20261030"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def checked_command(args: list[str]) -> str:
    result = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = result.stdout.decode("utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"Command failed: {args}\n{output}")
    return output


def build_config() -> dict:
    frozen_config = BASE_PROTOCOL / "frozen" / relative(BASE_CONFIG)
    if digest(BASE_CONFIG) != digest(frozen_config):
        raise RuntimeError("Original v3 config differs from its frozen baseline")
    if digest(BASE_SUMMARY) != digest(BASE_RESULT):
        raise RuntimeError("Original v3 summary differs from the frozen result")
    baseline = json.loads(BASE_CONFIG.read_text(encoding="utf-8"))
    samples = baseline["samples"]
    if len(samples) != 30 or Counter(x["complexity"] for x in samples) != Counter(simple=10, medium=10, complex=10):
        raise RuntimeError("Expected the original 10/10/10 sample list")
    for sample in samples:
        source = (ROOT / sample["vue_file"]).resolve()
        if not source.is_relative_to(ROOT) or digest(source) != digest(BASE_PROTOCOL / "frozen" / sample["vue_file"]):
            raise RuntimeError(f"Original Vue input changed: {sample['id']}")
    config = {
        "batch_id": BATCH_ID,
        "description": "All 30 original v3 inputs rerun through current v4; reused development regression.",
        "classification": "reused_development_full_regression",
        "independent_holdout": False,
        "baseline_batch_id": "formal_30_v3",
        "baseline_config": relative(BASE_CONFIG),
        "baseline_config_sha256": digest(BASE_CONFIG),
        "baseline_summary": relative(BASE_SUMMARY),
        "baseline_summary_sha256": digest(BASE_SUMMARY),
        "source_split": baseline["source_split"],
        "source_split_sha256": baseline["source_split_sha256"],
        "max_repair_rounds": 3,
        "expected_counts": {"simple": 10, "medium": 10, "complex": 10},
        "samples": samples,
    }
    validate_batch_config(config)
    return config


def protocol_text() -> str:
    return """# 当前 v4：完整 30 样本开发回归协议

日期：2026-10-30（Asia/Shanghai）；批次 `formal_30_v4_full_regression`。

## 范围与口径

使用原 v3 的同一份 30 样本列表、顺序和逐字节一致的 Vue 输入，运行当前 v4 的 SSM、generation、repair、验证器及渲染器。简单／中等／复杂各 10 项，每样本最多 **3 轮 repair**。这是已接触样本的完整开发回归，不能当作独立未见测试。

本次直接检验最终 v4 代码在所有 30 项上的自动迁移表现。TaskManager 最近单样本运行使用 6 轮，本批只用 3 轮，不能预先沿用其通过结论。旧 v3 结果为 18 通过、9 失败、3 执行错误；配对比较保留原结果，且由于评估器也发生变化，差异不能全部归因于 Prompt。

冻结包内 `frozen/` 为本次磁盘代码与输入基线。已提交及未提交的有效运行文件都会复制；Git HEAD 单独不代表运行版本。参考 San 不进入生成／repair 请求。v5 探索性评估等待本批完成；若本批后又改动实现，v5 须另建冻结版本。

## 参数和结果

- Provider `qwen`、模型 `qwen-plus`、温度 `0.2`、`LLM_TIMEOUT=240`；generation／repair 客户端超时各 300 秒。
- 保留 `--include-state`，默认健康检查启用；不传 `--sample-id`，不传 `--force`。
- 报告 30 项分母的通过率、正常完成项通过率、分层结果、初次通过、repair 轮数、token 与执行异常；人工交互结果单列。
- 对照旧结果逐样本报告“保持通过／回归失败／改善通过／仍未通过”，执行异常另报。自动通过不代表全部浏览器交互正确。
- 全批保持同一版本；异常恢复使用原命令和 checkpoint。不能挑选重跑替换失败结果；发现缺陷后先冻结原结果，再在后续版本修复。

## 操作者执行

先确认已重启的本地服务器加载冻结代码，使用 `qwen-plus`。在旧服务器终端 Ctrl+C 后，重新设置环境并启动：

```powershell
$env:LLM_PROVIDER = "qwen"
$env:LLM_API_KEY = "<你的密钥>"
$env:LLM_MODEL = "qwen-plus"
$env:LLM_TIMEOUT = "240"
python -m local_server.app
```

在另一终端验证文件，然后启动整批：

```powershell
python data/experiments/protocols/formal_30_v4_full_regression_frozen_20261030/verify_protocol.py --live
python migration_pipeline/run_batch_pipeline.py `
  --config-file migration_pipeline/batch_configs/formal_30_v4_full_regression.json `
  --include-state
```

中断后用同一批处理命令恢复。默认输出分别为 `data/experiments/pipeline/batches/formal_30_v4_full_regression/`、`data/experiments/repair_reports/batches/formal_30_v4_full_regression/` 和 `data/experiments/batch_reports/formal_30_v4_full_regression_summary.json`。

## 本次已验证的边界

冻结脚本执行旧协议完整性校验、全量单元测试及本批 dry-run，原始输出附在此目录。服务器加载版本须由重启操作确认；文件哈希不能证明旧进程已加载相同代码。此冻结脚本没有调用模型。
"""


def freeze(config: dict) -> None:
    output_paths = [
        ROOT / f"data/experiments/pipeline/batches/{BATCH_ID}",
        ROOT / f"data/experiments/repair_reports/batches/{BATCH_ID}",
        ROOT / f"data/experiments/batch_reports/{BATCH_ID}_summary.json",
    ]
    if TARGET.exists() or any(path.exists() for path in output_paths):
        raise FileExistsError("New protocol and unused batch output paths required")
    serialized = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    if CONFIG.exists() and json.loads(CONFIG.read_text(encoding="utf-8")) != config:
        raise RuntimeError("Existing regression config differs from the proposed plan")
    if not CONFIG.exists():
        CONFIG.write_text(serialized, encoding="utf-8")
    prior_check = checked_command([sys.executable, str(BASE_PROTOCOL / "verify_protocol.py")])
    tests = checked_command([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])
    dry_run = checked_command([sys.executable, "migration_pipeline/run_batch_pipeline.py", "--config-file", relative(CONFIG), "--include-state", "--dry-run"])
    plan = json.loads(dry_run)
    if len(plan["samples"]) != 30 or plan["max_repair_rounds"] != 3:
        raise RuntimeError("Unexpected batch dry-run plan")
    paths = checked_command(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "SSM", "local_server", "migration_pipeline", "tests"])
    files = {ROOT / name for name in paths.split("\0") if name and (name.startswith(("SSM/", "local_server/", "migration_pipeline/")) or name.startswith("tests/test_") and name.endswith(".py"))}
    files.update(ROOT / name for name in ("environment.yml", "requirements.txt", "package.json", "package-lock.json"))
    files.update((BASE_CONFIG, BASE_SUMMARY, CONFIG, ROOT / config["source_split"]))
    files.update(ROOT / sample["vue_file"] for sample in config["samples"])
    if any(not path.is_file() or not path.resolve().is_relative_to(ROOT) for path in files):
        raise RuntimeError("Missing or out-of-workspace evidence file")
    TARGET.mkdir(parents=True)
    for source in sorted(files):
        destination = TARGET / "frozen" / relative(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    shutil.copy2(BASE_PROTOCOL / "verify_protocol.py", TARGET / "verify_protocol.py")
    (TARGET / "PROTOCOL.md").write_text(protocol_text(), encoding="utf-8")
    for name, value in (("unit_tests.txt", tests), ("dry_run.json", dry_run), ("baseline_integrity.txt", prior_check)):
        (TARGET / name).write_text(value, encoding="utf-8")
    baseline = json.loads(BASE_SUMMARY.read_text(encoding="utf-8"))
    manifest = {
        "protocol_id": TARGET.name,
        "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "classification": config["classification"],
        "independent_holdout": False,
        "batch_id": BATCH_ID,
        "sample_count": 30,
        "max_repair_rounds": 3,
        "config_sha256": digest(CONFIG),
        "config_fingerprint": config_fingerprint(config),
        "baseline_summary_sha256": digest(BASE_SUMMARY),
        "baseline_aggregate": baseline["aggregate"],
        "all_30_live_vue_match_original_frozen_inputs": True,
        "sample_source_sha256": {s["id"]: digest(ROOT / s["vue_file"]) for s in config["samples"]},
        "git_head": checked_command(["git", "rev-parse", "HEAD"]).strip(),
        "worktree_clean": not bool(checked_command(["git", "status", "--short"]).strip()),
        "python_version": sys.version.split()[0],
        "server_loaded_code_confirmed": False,
        "model_request_performed": False,
        "output_paths_absent_at_freeze": True,
        "frozen_payload_files": len(files),
    }
    (TARGET / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payloads = sorted(path for path in TARGET.rglob("*") if path.is_file())
    (TARGET / "SHA256SUMS.txt").write_text("\n".join(f"{digest(path)}  {path.relative_to(TARGET).as_posix()}" for path in payloads) + "\n", encoding="utf-8")
    print(checked_command([sys.executable, str(TARGET / "verify_protocol.py"), "--live"]).strip())
    print(relative(TARGET))
    print("model_request_performed: false")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true", help="Write config, run local checks and freeze evidence; no LLM call.")
    args = parser.parse_args()
    config = build_config()
    print(f"batch={BATCH_ID}, samples=30 (10/10/10), max_repair_rounds=3")
    if args.freeze:
        freeze(config)
    else:
        print("Preview only; use --freeze to write the verified pre-run bundle.")


if __name__ == "__main__":
    main()
