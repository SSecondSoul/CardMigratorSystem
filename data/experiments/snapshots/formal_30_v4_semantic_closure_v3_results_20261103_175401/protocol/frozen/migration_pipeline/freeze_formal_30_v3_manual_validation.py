"""Freeze the completed formal_30_v3 representative manual validation."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH = "formal_30_v3"
MANUAL_RECORD = (
    ROOT
    / "data/experiments/manual_validation/formal_30_v3_representative_manual_validation.json"
)
AUTOMATIC_SNAPSHOT = (
    ROOT / "data/experiments/snapshots/formal_30_v3_results_20261022_200548"
)
ANALYSIS = ROOT / "data/experiments/analysis/formal_30_v3_20261022"
REPORTS = ROOT / "data/experiments/repair_reports/batches/formal_30_v3"
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
        elif sha256(path) != expected:
            failures.append(f"hash mismatch: {relative}")
        checked += 1
    if failures:
        raise SystemExit("\\n".join(failures))
    print(f"snapshot verification passed: {checked} files")


if __name__ == "__main__":
    main()
'''


FREEZE_README = """# formal_30_v3 representative manual-validation freeze

This is an evidence-only snapshot of the post-execution browser comparison for
seven deliberately selected automatic-pass samples from formal_30_v3.

The manual result is 7/7 for this representative sample. It is not a full
30-sample manual result and does not replace the frozen automatic metrics of
18/30 configured or 18/27 completed.

The final San artifacts are byte-identical to the copies in the frozen
automatic-result snapshot. The snapshot also contains the corresponding Vue
sources, repair histories, analysis, manual runners, and the manual-validation
record.

Run `python verify_snapshot.py` in this directory to verify every payload file.
Do not edit this snapshot. Later validation or reinterpretation requires a new
record and a new snapshot directory.
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def workspace_file(value: str) -> Path:
    path = (ROOT / value).resolve()
    path.relative_to(ROOT.resolve())
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def verify_snapshot(snapshot: Path) -> int:
    failures = []
    checked = 0
    for line in (snapshot / "SHA256SUMS.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        path = snapshot / relative
        if not path.is_file() or sha256(path) != expected:
            failures.append(relative)
        checked += 1
    if failures:
        raise RuntimeError(
            "Automatic-result snapshot verification failed: " + ", ".join(failures)
        )
    return checked


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> None:
    required = [
        MANUAL_RECORD,
        AUTOMATIC_SNAPSHOT / "manifest.json",
        AUTOMATIC_SNAPSHOT / "SHA256SUMS.txt",
        AUTOMATIC_SNAPSHOT / "formal_30_v3_summary.json",
        ANALYSIS,
        REPORTS,
        *RUNNERS,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing freeze input: " + ", ".join(missing))

    parent_verified_files = verify_snapshot(AUTOMATIC_SNAPSHOT)
    record = load_json(MANUAL_RECORD)
    automatic_summary = load_json(
        AUTOMATIC_SNAPSHOT / "formal_30_v3_summary.json"
    )
    samples = record.get("samples", [])
    summary = record.get("summary", {})
    if record.get("batch_id") != BATCH:
        raise RuntimeError("Manual record belongs to a different batch")
    if summary.get("checked") != 7 or summary.get("passed") != 7:
        raise RuntimeError("Expected exactly seven checked and passed samples")
    if summary.get("failed") != 0 or len(samples) != 7:
        raise RuntimeError("Manual-validation summary is inconsistent")
    if summary.get("all_configured_samples_manually_checked") is not False:
        raise RuntimeError("Manual record must retain its representative-sample boundary")

    automatic_samples = {item["id"]: item for item in automatic_summary["samples"]}
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    target = (
        ROOT
        / "data/experiments/snapshots"
        / f"{BATCH}_manual_validation_{timestamp}"
    )
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite snapshot: {target}")
    target.mkdir(parents=True)

    sample_records = []
    try:
        copy_file(MANUAL_RECORD, target / "manual_validation" / MANUAL_RECORD.name)
        copy_file(Path(__file__), target / "freeze_tool.py")
        copy_file(
            AUTOMATIC_SNAPSHOT / "manifest.json",
            target / "parent_evidence/automatic_snapshot_manifest.json",
        )
        copy_file(
            AUTOMATIC_SNAPSHOT / "SHA256SUMS.txt",
            target / "parent_evidence/automatic_snapshot_SHA256SUMS.txt",
        )
        shutil.copytree(ANALYSIS, target / "analysis")
        for runner in RUNNERS:
            copy_file(runner, target / "test_runners" / runner.name)
        (target / "FREEZE.md").write_text(FREEZE_README, encoding="utf-8")
        (target / "verify_snapshot.py").write_text(VERIFY_SCRIPT, encoding="utf-8")

        for item in samples:
            sample_id = item["id"]
            component_name = item["component_name"]
            complexity = item["complexity"]
            automatic_item = automatic_samples.get(sample_id)
            if not automatic_item or not automatic_item.get("final_passed"):
                raise RuntimeError(f"Sample is not an automatic pass: {sample_id}")
            if not item.get("pipeline_passed") or not item.get("manual_browser_passed"):
                raise RuntimeError(f"Sample is not recorded as manually passed: {sample_id}")

            vue_source = workspace_file(item["vue_source"])
            san_artifact = workspace_file(item["san_artifact"])
            repair_report = REPORTS / complexity / f"{component_name}_repair_history.json"
            parent_artifact = (
                AUTOMATIC_SNAPSHOT / "pipeline" / complexity / san_artifact.name
            )
            parent_report = (
                AUTOMATIC_SNAPSHOT
                / "repair_reports"
                / complexity
                / repair_report.name
            )
            for path in (repair_report, parent_artifact, parent_report):
                if not path.is_file():
                    raise FileNotFoundError(path)
            if sha256(san_artifact) != sha256(parent_artifact):
                raise RuntimeError(
                    f"San artifact differs from frozen automatic evidence: {sample_id}"
                )
            if sha256(repair_report) != sha256(parent_report):
                raise RuntimeError(
                    f"Repair report differs from frozen automatic evidence: {sample_id}"
                )

            artifact_copy = Path("artifacts") / complexity / san_artifact.name
            vue_copy = Path("vue_sources") / complexity / vue_source.name
            report_copy = Path("repair_reports") / complexity / repair_report.name
            copy_file(parent_artifact, target / artifact_copy)
            copy_file(vue_source, target / vue_copy)
            copy_file(parent_report, target / report_copy)
            sample_records.append(
                {
                    "validation_order": item["validation_order"],
                    "id": sample_id,
                    "component_name": component_name,
                    "complexity": complexity,
                    "automatic_passed": True,
                    "manual_browser_passed": True,
                    "artifact": artifact_copy.as_posix(),
                    "artifact_sha256": sha256(parent_artifact),
                    "vue_source": vue_copy.as_posix(),
                    "vue_source_sha256": sha256(vue_source),
                    "repair_report": report_copy.as_posix(),
                    "repair_report_sha256": sha256(parent_report),
                }
            )

        manifest = {
            "snapshot_id": target.name,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "purpose": "Immutable evidence for the formal_30_v3 representative manual browser validation.",
            "batch_id": BATCH,
            "parent_snapshot_id": AUTOMATIC_SNAPSHOT.name,
            "parent_snapshot_verified_files": parent_verified_files,
            "status": "frozen_post_representative_manual_validation",
            "scope": {
                "configured_samples": 30,
                "automatic_passed": 18,
                "manual_checked": 7,
                "manual_passed": 7,
                "manual_failed": 0,
                "all_configured_samples_manually_checked": False,
                "interpretation": "Purposeful representative validation of seven automatic passes; not a full-batch manual pass rate.",
            },
            "samples": sample_records,
            "manual_record": f"manual_validation/{MANUAL_RECORD.name}",
            "integrity_file": "SHA256SUMS.txt",
            "verification_command": (
                f"python {target.relative_to(ROOT).as_posix()}/verify_snapshot.py"
            ),
            "notes": [
                "The frozen automatic-result snapshot was verified before this snapshot was created.",
                "Every copied San artifact and repair report matches the parent automatic snapshot byte for byte.",
                "No component or automatic-result artifact was edited by this freeze operation.",
                "Any later validation or reinterpretation requires a new snapshot directory.",
            ],
        }
        (target / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        files = sorted(
            path
            for path in target.rglob("*")
            if path.is_file() and path.name != "SHA256SUMS.txt"
        )
        (target / "SHA256SUMS.txt").write_text(
            "\n".join(
                f"{sha256(path)}  {path.relative_to(target).as_posix()}"
                for path in files
            )
            + "\n",
            encoding="utf-8",
        )
    except Exception:
        shutil.rmtree(target)
        raise

    print(target.relative_to(ROOT).as_posix())
    print(
        json.dumps(
            {
                "samples": len(sample_records),
                "files": len(files),
                "parent_verified_files": parent_verified_files,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
