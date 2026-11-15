"""Prepare an isolated longer-timeout experiment; no model request is made."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import verify_snapshot
from migration_pipeline.prepare_formal_30_v4_full_regression import digest, checked_command
from migration_pipeline.run_batch_pipeline import validate_batch_config, config_fingerprint
from migration_pipeline.run_formal_30_v4_timeout_diagnostic import BATCH_ID, CONFIG, PROTOCOL, ROOT, EXPECTED_ENV


PRIOR = ROOT / "data/experiments/snapshots/formal_30_v4_full_regression_results_20261030_231238"
IDS = ("TaskManager", "MonitoringDashboard")


def build_config() -> dict:
    old = json.loads((PRIOR / "formal_30_v4_full_regression.json").read_text(encoding="utf-8"))
    result = json.loads((PRIOR / "formal_30_v4_full_regression_summary.json").read_text(encoding="utf-8"))
    chosen = [sample for sample in old["samples"] if sample["id"] in IDS]
    if tuple(sample["id"] for sample in chosen) != IDS:
        raise RuntimeError("Expected the original two timeout samples in order")
    observed = {sample["id"]: sample for sample in result["samples"]}
    for sample in chosen:
        if observed[sample["id"]]["status"] != "error" or "read operation timed out" not in observed[sample["id"]]["error_message"]:
            raise RuntimeError("Prior result is not the frozen timeout failure")
        if digest(ROOT / sample["vue_file"]) != digest(PRIOR / "protocol/frozen" / sample["vue_file"]):
            raise RuntimeError(f"Vue source changed: {sample['id']}")
    config = {
        "batch_id": BATCH_ID,
        "description": "Two reused complex samples under longer read timeouts; separate infrastructure diagnostic, not a replacement for the 30-sample result.",
        "classification": "longer_timeout_development_diagnostic",
        "independent_holdout": False,
        "prior_result_snapshot": PRIOR.name,
        "prior_result_summary_sha256": digest(PRIOR / "formal_30_v4_full_regression_summary.json"),
        "max_repair_rounds": 3,
        "expected_counts": {"simple": 0, "medium": 0, "complex": 2},
        "required_launch_environment": EXPECTED_ENV,
        "environment_note": "Metadata only; use the dedicated launcher to enforce child-process environment before settings are imported.",
        "samples": chosen,
    }
    validate_batch_config(config)
    return config


def protocol_text() -> str:
    return """# v4 超时诊断 v1：600／660 秒

日期：2026-11-02（Asia/Shanghai）。批次 `formal_30_v4_timeout_diagnostic_v1`。

## 目的和解释范围

仅复用 TaskManager、MonitoringDashboard 两项，在相同 v4 源码、Prompt、qwen/qwen-plus、温度 0.2、最多 3 轮 repair 下，将上游非流式读取超时从 240 秒增至 600 秒，将两类批处理 HTTP 客户端从 300 秒增至 660 秒。采用新的生成路径、repair report 和 checkpoint。

原完整回归及同条件重试均为 25 通过、3 评估失败、2 执行超时；原结果保留。这是改变超时条件的诊断，不能将新通过项回填原批次，不能宣称严格独立泛化。LLM 随机输出不同，若成功，只能说明更长超时条件下本次运行完成，不能仅凭一次结果证明失败唯一根因是时间不足。

旧 TaskManager 产物和任何参考 San 都不作为本次生成输入。先冻结本次原始结果再诊断。一次运行完成或发生异常后交回检查，暂不自行反复重试，不加 --force。3 项原评估失败仍留在后续修复清单中，v5 等待。

## 配置生效方式

JSON 中 required_launch_environment 是记录性字段，原批处理不会从中设置超时。必须使用专用 launcher，它在新子进程导入配置前设置环境：LLM_TIMEOUT=600、MIGRATION_GENERATION_TIMEOUT=660、MIGRATION_REPAIR_TIMEOUT=660，固定原默认的 provider/model/API 地址。仓库全局默认值未改。

## 两个 PowerShell 窗口

先在旧服务器终端 Ctrl+C。窗口 A 激活 cardmig、进入仓库根目录，设置密钥后启动：

```powershell
$env:LLM_API_KEY = "<你的密钥>"
python -m migration_pipeline.run_formal_30_v4_timeout_diagnostic --server
```

密钥只存在环境中，不写入仓库。launcher 会先核对协议 live 哈希并打印非密钥配置，然后启动新的本地服务器。健康检查只能返回 provider/model，不证明已存在旧进程的超时；因此必须真正停止旧服务并用 --server 重启。若 8787 端口占用，不继续执行模型批次。

窗口 B 激活 cardmig、进入仓库根目录，先验证计划，再执行一次：

```powershell
python -m migration_pipeline.run_formal_30_v4_timeout_diagnostic --dry-run
python -m migration_pipeline.run_formal_30_v4_timeout_diagnostic --execute
```

--execute 会再次核对 live 哈希，并通过健康检查后启动独立批次；不会复跑原 28 个 completed 样本。两个样本都从原 Vue 重新生成，不接续旧 repair 步。上游调用可能接近 10 分钟，整批会更久。

## 记录与输出

- 配置：migration_pipeline/batch_configs/formal_30_v4_timeout_diagnostic_v1.json
- pipeline：data/experiments/pipeline/batches/formal_30_v4_timeout_diagnostic_v1/
- reports：data/experiments/repair_reports/batches/formal_30_v4_timeout_diagnostic_v1/
- summary：data/experiments/batch_reports/formal_30_v4_timeout_diagnostic_v1_summary.json
- Notebook：notebooks/02-migration-experiments/2026-11-02_formal_30_v4_timeout_diagnostic.ipynb

报告生成／repair 失败阶段、耗时、实际返回模型、轮数及可获得 token，异常请求用量缺失单列。健康检查、启动终端非密钥设置和服务器实际重启需由操作者确认；文件包不能独立证明运行进程配置。

原运行代码／源输入与旧冻结字节一致性、旧快照校验、完整单元测试和新批次 dry-run 结果随本文件封存。首次模型请求后保持本诊断的参数和实现不变；任何新修复或参数变化另建版本。
"""


def freeze(config: dict) -> None:
    paths = [PROTOCOL, ROOT / f"data/experiments/pipeline/batches/{BATCH_ID}",
             ROOT / f"data/experiments/repair_reports/batches/{BATCH_ID}",
             ROOT / f"data/experiments/batch_reports/{BATCH_ID}_summary.json"]
    if any(path.exists() for path in paths):
        raise FileExistsError("Require a new protocol and unused output paths")
    verified = verify_snapshot(PRIOR)
    base = PRIOR / "protocol"
    canonical_protocol = ROOT / "data/experiments/protocols/formal_30_v4_full_regression_frozen_20261030"
    base_live = checked_command([sys.executable, str(canonical_protocol / "verify_protocol.py"), "--live"])
    if CONFIG.exists() and json.loads(CONFIG.read_text(encoding="utf-8")) != config:
        raise RuntimeError("Existing diagnostic config differs")
    if not CONFIG.exists():
        CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tests = checked_command([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])
    dry = checked_command([sys.executable, "-m", "migration_pipeline.run_formal_30_v4_timeout_diagnostic", "--dry-run"])
    # Reuse every baseline frozen path, including untracked implementation files.
    files = {ROOT / p.relative_to(base / "frozen") for p in (base / "frozen").rglob("*") if p.is_file()}
    files.update((CONFIG, Path(__file__).resolve(), ROOT / "migration_pipeline/run_formal_30_v4_timeout_diagnostic.py",
                  ROOT / "tests/test_timeout_diagnostic_launch.py"))
    if any(not p.is_file() or not p.resolve().is_relative_to(ROOT) for p in files):
        raise RuntimeError("Missing/out-of-workspace protocol file")
    PROTOCOL.mkdir(parents=True)
    for source in sorted(files):
        destination = PROTOCOL / "frozen" / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    shutil.copy2(base / "verify_protocol.py", PROTOCOL / "verify_protocol.py")
    shutil.copy2(PRIOR / "formal_30_v4_full_regression_summary.json", PROTOCOL / "prior_retry_summary.json")
    for name, content in (("PROTOCOL.md", protocol_text()), ("unit_tests.txt", tests), ("dry_run.txt", dry), ("prior_live_verification.txt", base_live)):
        (PROTOCOL / name).write_text(content, encoding="utf-8")
    manifest = {
        "protocol_id": PROTOCOL.name, "batch_id": BATCH_ID,
        "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "classification": config["classification"], "independent_holdout": False,
        "sample_ids": list(IDS), "max_repair_rounds": 3,
        "runtime_env": EXPECTED_ENV, "config_sha256": digest(CONFIG),
        "config_fingerprint": config_fingerprint(config), "prior_snapshot": PRIOR.name,
        "prior_verified_files": verified, "baseline_live_files_match": True,
        "frozen_payload_files": len(files), "server_restart_confirmed": False,
        "model_request_performed": False,
    }
    (PROTOCOL / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payloads = sorted(p for p in PROTOCOL.rglob("*") if p.is_file())
    (PROTOCOL / "SHA256SUMS.txt").write_text("\n".join(f"{digest(p)}  {p.relative_to(PROTOCOL).as_posix()}" for p in payloads) + "\n", encoding="utf-8")
    print(checked_command([sys.executable, str(PROTOCOL / "verify_protocol.py"), "--live"]).strip())
    print("protocol:", PROTOCOL.relative_to(ROOT))
    print("model_request_performed: false")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    config = build_config()
    print("samples:", [s["id"] for s in config["samples"]], flush=True)
    if args.freeze:
        freeze(config)
    else:
        print("preview only; --freeze creates config and pre-run evidence without model calls")


if __name__ == "__main__":
    main()
