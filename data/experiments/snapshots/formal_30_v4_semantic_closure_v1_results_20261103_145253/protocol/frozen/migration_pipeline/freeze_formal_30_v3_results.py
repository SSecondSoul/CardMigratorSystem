"""Freeze terminal formal_30_v3 results without altering canonical outputs."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH = "formal_30_v3"
SUMMARY = ROOT / f"data/experiments/batch_reports/{BATCH}_summary.json"
NOTES = ROOT / f"data/experiments/batch_reports/{BATCH}_execution_notes.json"
CONFIG = ROOT / f"migration_pipeline/batch_configs/{BATCH}.json"
SPLIT = ROOT / "data/datasets/splits/formal_30_v3_untouched_holdout.json"
PIPELINE = ROOT / f"data/experiments/pipeline/batches/{BATCH}"
REPORTS = ROOT / f"data/experiments/repair_reports/batches/{BATCH}"
PROTOCOL = ROOT / "data/experiments/protocols/formal_30_v3_frozen_20261022"
ANALYSIS = ROOT / "data/experiments/analysis/formal_30_v3_20261022"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_protocol() -> None:
    failures = []
    for line in (PROTOCOL / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = PROTOCOL / relative
        if not path.is_file() or digest(path) != expected:
            failures.append(relative)
    if failures:
        raise RuntimeError("Protocol verification failed: " + ", ".join(failures))


VERIFY_SCRIPT = '''"""Verify every file recorded in this frozen result snapshot."""

import hashlib
from pathlib import Path


HERE = Path(__file__).resolve().parent


def main():
    failures = []
    checked = 0
    for line in (HERE / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = HERE / relative
        if not path.is_file():
            failures.append(f"missing: {relative}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(f"hash mismatch: {relative}")
        checked += 1
    if failures:
        print("snapshot verification: FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"snapshot verification: PASS ({checked} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def main() -> None:
    required = (SUMMARY, NOTES, CONFIG, SPLIT, PIPELINE, REPORTS, PROTOCOL, ANALYSIS)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing v3 evidence: " + ", ".join(missing))
    verify_protocol()
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    aggregate = summary["aggregate"]
    if aggregate.get("configured") != 30 or aggregate.get("pending") != 0:
        raise RuntimeError("formal_30_v3 is not terminal; refusing to freeze")

    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / f"{BATCH}_results_{timestamp}"
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite {target}")
    target.mkdir(parents=True)

    shutil.copy2(SUMMARY, target / SUMMARY.name)
    shutil.copy2(NOTES, target / NOTES.name)
    shutil.copy2(CONFIG, target / CONFIG.name)
    shutil.copy2(SPLIT, target / SPLIT.name)
    shutil.copytree(PIPELINE, target / "pipeline")
    shutil.copytree(REPORTS, target / "repair_reports")
    shutil.copytree(PROTOCOL, target / "protocol")
    shutil.copytree(ANALYSIS, target / "analysis")
    (target / "verify_snapshot.py").write_text(VERIFY_SCRIPT, encoding="utf-8")

    manifest = {
        "snapshot_id": target.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "purpose": "Immutable automatic-result evidence for the post-remediation formal_30_v3 untouched holdout.",
        "protocol_id": PROTOCOL.name,
        "batch_id": BATCH,
        "status": "frozen_post_execution",
        "aggregate": aggregate,
        "execution_error_samples": [
            item["id"] for item in summary["samples"] if item.get("status") == "error"
        ],
        "failed_completed_samples": [
            item["id"]
            for item in summary["samples"]
            if item.get("status") == "completed" and not item.get("final_passed")
        ],
        "notes": [
            "No generated component or repair report was manually edited before freezing.",
            "Three generation timeouts reproduced once under the unchanged protocol and remain execution errors.",
            "Any later remediation requires a new batch/version; this snapshot is evidence only.",
        ],
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    files = sorted(
        path for path in target.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS.txt"
    )
    (target / "SHA256SUMS.txt").write_text(
        "\n".join(
            f"{digest(path)}  {path.relative_to(target).as_posix()}" for path in files
        ) + "\n",
        encoding="utf-8",
    )
    print(target.relative_to(ROOT))
    print(json.dumps({"aggregate": aggregate, "files": len(files)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
