"""Freeze one focused TaskManager repair probe's input, prompt, and implementation."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migration_pipeline import probe_formal_30_v4_task_manager_semantic_focus as probe


FILES = [
    Path("migration_pipeline/probe_formal_30_v4_task_manager_semantic_focus.py"),
    Path("migration_pipeline/freeze_formal_30_v4_task_manager_semantic_probe_pre_run.py"),
    Path("migration_pipeline/utils/repair_prompt.py"),
    Path("migration_pipeline/repair_client.py"),
    Path("migration_pipeline/stages/validate.py"),
    Path("migration_pipeline/stages/visual_eval.py"),
    Path("migration_pipeline/utils/san_compile.py"),
    Path("migration_pipeline/utils/san_render.py"),
    Path("migration_pipeline/utils/vue_render.py"),
    Path("migration_pipeline/utils/dom_compare.py"),
    Path("local_server/api/evaluation_routes.py"),
    Path("tests/test_semantic_residual_repair_prompt.py"),
    Path("data/experiments/analysis/formal_30_v4_generalization_gap_audit_20261027/task_manager_semantic_focus_v2_review.json"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    target = probe.PRE_RUN
    if target.exists():
        raise FileExistsError(target)
    for path in (probe.OUTPUT, probe.REPORT, probe.SERVER_DEFAULT):
        if path.exists():
            raise FileExistsError(f"Probe output already exists: {path}")
    manifest, state, code, prompt = probe.load_frozen_input()
    for relative in FILES:
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise RuntimeError(f"Missing implementation payload: {relative}")

    target.mkdir(parents=True)
    (target / "prompt.txt").write_text(prompt, encoding="utf-8")
    (target / "input.san").write_text(code, encoding="utf-8")
    errors = state["final_validate_result"]["validation_errors"]
    (target / "validation_errors.json").write_text(
        json.dumps(errors, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copy2(probe.SNAPSHOT / "manifest.json", target / "input_result_manifest.json")
    shutil.copy2(probe.SNAPSHOT / "SHA256SUMS.txt", target / "input_result_SHA256SUMS.txt")
    for relative in FILES:
        destination = target / "payload" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    record = {
        "snapshot_id": target.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_single_repair_probe_pre_run",
        "independent_holdout": False,
        "frozen_input_snapshot": manifest["snapshot_id"],
        "input_sha256": sha256(target / "input.san"),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_characters": len(prompt),
        "validation_error_codes": [issue.get("code") for issue in errors],
        "test_evidence": "6/6 semantic prompt tests and 167/167 full unittest tests passed; probe dry-run passed",
        "output_paths_empty_at_freeze": True,
        "boundary": "One repair request from a frozen failed development output, not a fresh source-to-San batch or an independent formal test.",
        "integrity_file": "SHA256SUMS.txt",
    }
    (target / "manifest.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    files = sorted(path for path in target.rglob("*") if path.is_file())
    (target / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.relative_to(target).as_posix()}" for path in files) + "\n",
        encoding="utf-8",
    )
    for line in (target / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if sha256(target / relative) != expected:
            raise RuntimeError(f"Pre-run snapshot checksum mismatch: {relative}")
    print(f"frozen: {target.relative_to(ROOT)} ({len(files)} verified payloads)")


if __name__ == "__main__":
    main()
