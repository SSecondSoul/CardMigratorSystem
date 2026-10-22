"""Freeze the completed formal_30_v2 manual-validation evidence."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH = "formal_30_v2"
SOURCE_MANIFEST = (
    ROOT / "data/experiments/repair_reports/batches/formal_30_v2/manifest.json"
)
NOTEBOOK_DIR = ROOT / "notebooks/02-migration-experiments"
V1_SNAPSHOT = (
    ROOT / "data/experiments/snapshots/formal_30_v1_results_20261015_161053"
)
V1_PROTOCOL = ROOT / "data/experiments/protocols/formal_30_v1_frozen_20261015"
RUNNERS = (
    ROOT / "tests/manual/vue-test-runner.html",
    ROOT / "tests/manual/san-test-runner.html",
)


VERIFY_SCRIPT = '''"""Verify every file recorded in this frozen snapshot."""

from __future__ import annotations

import hashlib
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    failures = []
    checked = 0
    for line in (HERE / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        path = HERE / relative
        if not path.is_file():
            failures.append(f"missing: {relative}")
        else:
            actual = sha256(path)
            if actual.lower() != expected.lower():
                failures.append(
                    f"hash mismatch: {relative} expected={expected} actual={actual}"
                )
        checked += 1
    if failures:
        raise SystemExit("\\n".join(failures))
    print(f"snapshot verification passed: {checked} files")


if __name__ == "__main__":
    main()
'''


FREEZE_README = """# formal_30_v2 manual-validation freeze

This directory is an evidence-only snapshot of the completed formal_30_v2
manual-validation and targeted-repair layer.

Scope: 14 registered samples, all manually passed. This is not a new automatic
run of all 30 formal_30_v1 samples and must not be reported as a 30-sample
automatic pass rate.

The snapshot contains the exact final San artifact for every registered sample,
the corresponding pre-repair or unchanged baseline San artifact, Vue source,
manual report, available experiment notebooks, the manual test runners, and
parent formal_30_v1 evidence references.

Verify integrity from the repository root with:

    python <snapshot-directory>/verify_snapshot.py

Do not edit this snapshot. Any later repair or reinterpretation requires a new
version and a new snapshot directory.
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def workspace_path(value: str) -> Path:
    path = ROOT / value
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    required = [SOURCE_MANIFEST, V1_SNAPSHOT / "manifest.json", V1_SNAPSHOT / "SHA256SUMS.txt", V1_PROTOCOL / "manifest.json", *RUNNERS]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing freeze input: " + ", ".join(missing))

    source_manifest = load_json(SOURCE_MANIFEST)
    samples = source_manifest.get("samples", [])
    summary = source_manifest.get("manual_validation_summary", {})
    if source_manifest.get("status") != "manual_validation_complete":
        raise RuntimeError("Manual validation is not marked complete")
    if len(samples) != 14 or any(item.get("manual_validation") != "passed" for item in samples):
        raise RuntimeError("Expected exactly 14 passed manual-validation samples")
    if summary != {"registered": 14, "passed": 14, "failed": 0, "pending": 0}:
        raise RuntimeError("Manual-validation summary is inconsistent")

    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / f"{BATCH}_manual_results_{timestamp}"
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite snapshot: {target}")
    target.mkdir(parents=True)

    sample_records = []
    try:
        copy_file(SOURCE_MANIFEST, target / "manual_validation_manifest.json")
        copy_file(Path(__file__), target / "freeze_tool.py")
        (target / "FREEZE.md").write_text(FREEZE_README, encoding="utf-8")
        (target / "verify_snapshot.py").write_text(VERIFY_SCRIPT, encoding="utf-8")

        for runner in RUNNERS:
            copy_file(runner, target / "test_runners" / runner.name)

        copy_file(
            V1_SNAPSHOT / "manifest.json",
            target / "parent_evidence/formal_30_v1_snapshot_manifest.json",
        )
        copy_file(
            V1_SNAPSHOT / "SHA256SUMS.txt",
            target / "parent_evidence/formal_30_v1_SHA256SUMS.txt",
        )
        copy_file(
            V1_PROTOCOL / "manifest.json",
            target / "parent_evidence/formal_30_v1_protocol_manifest.json",
        )

        for notebook in sorted(NOTEBOOK_DIR.glob("*formal_v2*.ipynb")):
            load_json(notebook)
            copy_file(notebook, target / "notebooks" / notebook.name)

        for item in samples:
            sample_id = item["sample_id"]
            complexity = item["complexity"]
            artifact = workspace_path(item["artifact"])
            report_path = workspace_path(item["report"])
            report = load_json(report_path)

            if sha256(artifact).upper() != item["sha256"].upper():
                raise RuntimeError(f"Artifact hash mismatch for {sample_id}")
            if report.get("status") != "passed":
                raise RuntimeError(f"Report is not passed for {sample_id}")

            vue_value = report.get("source_vue") or report.get("vue_file")
            baseline_value = report.get("source_san") or report.get("san_file")
            if not vue_value or not baseline_value:
                raise RuntimeError(f"Missing source paths in report for {sample_id}")
            vue_source = workspace_path(vue_value)
            baseline = workspace_path(baseline_value)

            artifact_copy = Path("artifacts") / complexity / f"{sample_id}.san"
            baseline_copy = Path("baseline_artifacts") / complexity / f"{sample_id}.san"
            vue_copy = Path("vue_sources") / complexity / f"{sample_id}.vue"
            report_copy = Path("repair_reports") / complexity / report_path.name
            copy_file(artifact, target / artifact_copy)
            copy_file(baseline, target / baseline_copy)
            copy_file(vue_source, target / vue_copy)
            copy_file(report_path, target / report_copy)

            sample_records.append(
                {
                    "sample_id": sample_id,
                    "complexity": complexity,
                    "manual_validation": "passed",
                    "canonical_artifact": item["artifact"],
                    "artifact": artifact_copy.as_posix(),
                    "artifact_sha256": sha256(artifact),
                    "canonical_baseline": baseline_value,
                    "baseline_artifact": baseline_copy.as_posix(),
                    "baseline_sha256": sha256(baseline),
                    "canonical_vue_source": vue_value,
                    "vue_source": vue_copy.as_posix(),
                    "vue_source_sha256": sha256(vue_source),
                    "canonical_report": item["report"],
                    "report": report_copy.as_posix(),
                    "report_sha256": sha256(report_path),
                }
            )

        created_at = datetime.now().astimezone().isoformat(timespec="seconds")
        snapshot_manifest = {
            "snapshot_id": target.name,
            "created_at": created_at,
            "purpose": "Immutable post-validation evidence for formal_30_v2 targeted repairs and manual browser checks.",
            "batch_id": BATCH,
            "parent_batch_id": "formal_30_v1",
            "parent_snapshot_id": V1_SNAPSHOT.name,
            "status": "frozen_post_manual_validation",
            "scope": {
                "registered_samples": 14,
                "manual_passed": 14,
                "manual_failed": 0,
                "manual_pending": 0,
                "interpretation": "Targeted manual-validation set; not a rerun or pass rate for all 30 formal samples.",
            },
            "samples": sample_records,
            "notebooks": [
                path.relative_to(target).as_posix()
                for path in sorted((target / "notebooks").glob("*.ipynb"))
            ],
            "integrity_file": "SHA256SUMS.txt",
            "verification_command": f"python {target.relative_to(ROOT).as_posix()}/verify_snapshot.py",
            "notes": [
                "The formal_30_v1 protocol, outputs, and frozen snapshot were not modified.",
                "Artifacts copied from formal_30_v1 are unchanged samples that passed manual validation.",
                "Artifacts copied from formal_30_v2 are targeted repairs supported by per-sample reports.",
                "Any later change requires a new version and snapshot directory.",
            ],
        }
        (target / "manifest.json").write_text(
            json.dumps(snapshot_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        files = sorted(
            path for path in target.rglob("*")
            if path.is_file() and path.name != "SHA256SUMS.txt"
        )
        checksum_lines = [
            f"{sha256(path)}  {path.relative_to(target).as_posix()}"
            for path in files
        ]
        (target / "SHA256SUMS.txt").write_text(
            "\n".join(checksum_lines) + "\n", encoding="utf-8"
        )
    except Exception:
        shutil.rmtree(target)
        raise

    print(target.relative_to(ROOT).as_posix())
    print(json.dumps({"samples": len(sample_records), "files": len(files)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
