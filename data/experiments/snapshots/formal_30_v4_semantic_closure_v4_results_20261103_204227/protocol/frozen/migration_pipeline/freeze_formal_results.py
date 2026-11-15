"""Freeze a completed formal batch without altering its original outputs."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH = "formal_30_v1"
SUMMARY = ROOT / "data/experiments/batch_reports" / f"{BATCH}_summary.json"
CONFIG = ROOT / "migration_pipeline/batch_configs" / f"{BATCH}.json"
SPLIT = ROOT / "data/datasets/splits/pilot_9_v6_development_and_formal_30_v1.json"
PIPELINE = ROOT / "data/experiments/pipeline/batches" / BATCH
REPORTS = ROOT / "data/experiments/repair_reports/batches" / BATCH
PROTOCOL = ROOT / "data/experiments/protocols/formal_30_v1_frozen_20261015"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(source)
    shutil.copytree(source, destination)


def main() -> None:
    required = (SUMMARY, CONFIG, SPLIT, PIPELINE, REPORTS, PROTOCOL)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing formal result inputs: " + ", ".join(missing))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    aggregate = summary.get("aggregate", {})
    if aggregate.get("configured") != 30 or aggregate.get("pending") != 0:
        raise RuntimeError("Formal batch is not complete; refusing to freeze partial results")

    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / f"{BATCH}_results_{timestamp}"
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)

    shutil.copy2(SUMMARY, target / "formal_30_v1_summary.json")
    shutil.copy2(CONFIG, target / "formal_30_v1.json")
    shutil.copy2(SPLIT, target / "development_and_formal_split.json")
    copy_tree(PIPELINE, target / "pipeline")
    copy_tree(REPORTS, target / "repair_reports")
    shutil.copy2(PROTOCOL / "manifest.json", target / "protocol_manifest.json")

    files = sorted(path for path in target.rglob("*") if path.is_file())
    checksum_lines = [
        f"{sha256(path)}  {path.relative_to(target).as_posix()}"
        for path in files
    ]
    (target / "SHA256SUMS.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    manifest = {
        "snapshot_id": target.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "purpose": "Immutable post-execution evidence for formal_30_v1; original batch outputs remain at their canonical paths.",
        "protocol_id": "formal_30_v1_frozen_20261015",
        "batch_id": BATCH,
        "status": "frozen_post_execution",
        "summary": "formal_30_v1_summary.json",
        "aggregate": aggregate,
        "execution_error_samples": [
            item["id"] for item in summary.get("samples", []) if item.get("status") == "error"
        ],
        "failed_completed_samples": [
            item["id"]
            for item in summary.get("samples", [])
            if item.get("status") == "completed" and not item.get("final_passed", False)
        ],
        "canonical_outputs": {
            "summary": "data/experiments/batch_reports/formal_30_v1_summary.json",
            "pipeline": "data/experiments/pipeline/batches/formal_30_v1",
            "repair_reports": "data/experiments/repair_reports/batches/formal_30_v1",
        },
        "integrity_file": "SHA256SUMS.txt",
        "payload_file_count": len(files),
        "notes": [
            "No failed sample was regenerated or edited after completion.",
            "TopologyEditor ended with a repair request timeout and remains an execution error.",
            "This snapshot is evidence only; any repair requires a new protocol version and output directory.",
        ],
    }
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = sorted(path for path in target.rglob("*") if path.is_file() and path.name != "SHA256SUMS.txt")
    checksum_lines = [
        f"{sha256(path)}  {path.relative_to(target).as_posix()}"
        for path in files
    ]
    (target / "SHA256SUMS.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(target.relative_to(ROOT))
    print(json.dumps({"aggregate": aggregate, "files": len(files)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
