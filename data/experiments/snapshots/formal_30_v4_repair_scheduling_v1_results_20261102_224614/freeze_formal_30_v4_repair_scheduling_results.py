"""Freeze scheduling-policy raw results without modifying generated artifacts."""

import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from migration_pipeline.freeze_formal_30_v3_results import VERIFY_SCRIPT
from migration_pipeline.prepare_formal_30_v4_full_regression import digest
from migration_pipeline.run_batch_pipeline import config_fingerprint
from migration_pipeline.run_formal_30_v4_repair_scheduling import ROOT, BATCH_ID, CONFIG, PROTOCOL


def main():
    subprocess.run([sys.executable, str(PROTOCOL / "verify_protocol.py"), "--live"], cwd=ROOT, check=True)
    summary_path = ROOT / f"data/experiments/batch_reports/{BATCH_ID}_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    samples = summary["samples"]
    statuses = Counter(s["status"] for s in samples)
    passed = sum(s.get("final_passed") is True for s in samples if s["status"] == "completed")
    counts = {"configured": len(config["samples"]), "completed": statuses["completed"],
              "passed": passed, "failed": statuses["completed"] - passed,
              "execution_errors": statuses["error"], "pending": 0}
    if (summary["batch_id"] != BATCH_ID or summary["config_sha256"] != config_fingerprint(config)
            or summary["max_repair_rounds"] != 3
            or [s["id"] for s in samples] != [s["id"] for s in config["samples"]]
            or set(statuses) - {"completed", "error"}
            or any(summary["aggregate"][key] != value for key, value in counts.items())
            or any(s["status"] == "completed" and (
                s.get("repair_policy") != "bounded_prepass_v1"
                or s.get("repair_budget_unit") != "llm_calls"
                or not 0 <= s["llm_repair_calls"] <= 3
                or not 0 <= s["deterministic_steps"] <= 12) for s in samples)):
        raise RuntimeError("Scheduling result/config mismatch")
    files = {summary_path: Path(summary_path.name), CONFIG: Path(CONFIG.name)}
    for source, name in ((ROOT / f"data/experiments/pipeline/batches/{BATCH_ID}", "pipeline"),
                         (ROOT / f"data/experiments/repair_reports/batches/{BATCH_ID}", "repair_reports"),
                         (PROTOCOL, "protocol")):
        if not source.is_dir():
            raise FileNotFoundError(source)
        for path in source.rglob("*"):
            if path.is_file():
                if not path.resolve().is_relative_to(ROOT):
                    raise RuntimeError(f"Out-of-workspace file: {path}")
                files[path] = Path(name) / path.relative_to(source)
    included = {p.resolve() for p in files}
    for sample in samples:
        if sample["status"] == "completed":
            for key in ("report_file", "final_file_path"):
                source = Path(sample[key])
                source = source if source.is_absolute() else ROOT / source
                if source.resolve() not in included:
                    raise RuntimeError(f"Missing evidence: {sample['id']}/{key}")
    hashes = {source: digest(source) for source in files}
    now = datetime.now(timezone(timedelta(hours=8)))
    target = ROOT / "data/experiments/snapshots" / f"{BATCH_ID}_results_{now:%Y%m%d_%H%M%S}"
    target.mkdir(parents=True, exist_ok=False)
    for source, relative in files.items():
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if digest(source) != hashes[source] or digest(destination) != hashes[source]:
            raise RuntimeError(f"Evidence changed during freeze: {source}")
    shutil.copy2(Path(__file__), target / Path(__file__).name)
    (target / "verify_snapshot.py").write_text(VERIFY_SCRIPT, encoding="utf-8")
    manifest = {
        "snapshot_id": target.name, "created_at": now.isoformat(timespec="seconds"),
        "batch_id": BATCH_ID, "classification": "repair_scheduling_policy_development_regression_raw_result",
        "independent_holdout": False, "summary_sha256": digest(summary_path),
        "config_sha256": digest(CONFIG), "config_fingerprint": config_fingerprint(config),
        "protocol_id": PROTOCOL.name, "protocol_live_verified_at_result_freeze": True,
        "server_runtime_env_independently_proven": False,
        "repair_budget_unit": "llm_calls", "aggregate": summary["aggregate"],
        "boundary": "Raw results frozen before detailed diagnosis; three LLM calls are not equal to the prior three mixed attempts.",
    }
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payloads = sorted(p for p in target.rglob("*") if p.is_file())
    (target / "SHA256SUMS.txt").write_text("\n".join(f"{digest(p)}  {p.relative_to(target).as_posix()}" for p in payloads) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(target / "verify_snapshot.py")], cwd=ROOT, check=True)
    print(target.relative_to(ROOT))
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
