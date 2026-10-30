"""Create and freeze the post-remediation formal_30_v3 holdout protocol."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PARENT_SPLIT = ROOT / "data/datasets/splits/pilot_9_v6_development_and_formal_30_v1.json"
ANALYSIS_REPORT = ROOT / "data/experiments/analysis/formal_30_v1_v2_20261022/REPORT.md"
SPLIT = ROOT / "data/datasets/splits/formal_30_v3_untouched_holdout.json"
CONFIG = ROOT / "migration_pipeline/batch_configs/formal_30_v3.json"
PROTOCOL = ROOT / "data/experiments/protocols/formal_30_v3_frozen_20261022"
LEVELS = ("simple", "medium", "complex")
PER_LEVEL = 10

RUNTIME_PATHS = (
    "environment.yml",
    "requirements.txt",
    "package.json",
    "package-lock.json",
    "local_server",
    "SSM",
    "migration_pipeline/__init__.py",
    "migration_pipeline/config.py",
    "migration_pipeline/generation_client.py",
    "migration_pipeline/repair_client.py",
    "migration_pipeline/orchestrator.py",
    "migration_pipeline/run_pipeline.py",
    "migration_pipeline/run_batch_pipeline.py",
    "migration_pipeline/create_formal_30_v3_protocol.py",
    "migration_pipeline/stages",
    "migration_pipeline/utils",
    "tests/test_batch_pipeline_runner.py",
    "tests/test_interaction_eval.py",
    "tests/test_migration_pipeline_regressions.py",
    "tests/test_repair_prompt_and_loop.py",
    "tests/test_ssm_event_extraction.py",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_select(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Greedily maximize new feature coverage, using source order as tie-breaker."""
    selected: list[dict[str, Any]] = []
    covered: set[str] = set()
    pool = list(enumerate(candidates))
    while len(selected) < PER_LEVEL:
        index, candidate = max(
            pool,
            key=lambda pair: (
                len(set(pair[1].get("feature_signature", [])) - covered),
                len(set(pair[1].get("feature_signature", []))),
                -pair[0],
            ),
        )
        selected.append(candidate)
        covered.update(candidate.get("feature_signature", []))
        pool = [pair for pair in pool if pair[0] != index]
    return selected


def git_metadata() -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()

    status = run("status", "--short")
    return {
        "head": run("rev-parse", "HEAD"),
        "branch": run("branch", "--show-current"),
        "working_tree_clean": not bool(status),
        "working_tree_status": status.splitlines(),
        "note": "The frozen/ tree, not the Git commit alone, is the authoritative runtime evidence.",
    }


def iter_files(path: Path):
    if path.is_file():
        yield path
        return
    for child in sorted(path.rglob("*")):
        if not child.is_file():
            continue
        if "__pycache__" in child.parts or child.suffix in {".pyc", ".pyo"}:
            continue
        yield child


def tracked_files(path: Path):
    relative = path.relative_to(ROOT).as_posix()
    result = subprocess.run(
        ["git", "ls-files", "--", relative],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    for line in result.stdout.splitlines():
        candidate = ROOT / line
        if candidate.is_file():
            yield candidate


def freeze_file(source: Path, frozen_root: Path) -> None:
    relative = source.relative_to(ROOT)
    target = frozen_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def protocol_markdown(selected: list[dict[str, Any]]) -> str:
    counts = Counter(item["complexity"] for item in selected)
    sample_rows = "\n".join(
        f"| {item['id']} | {item['component_name']} | {item['complexity']} |"
        for item in selected
    )
    return f"""# formal_30_v3 frozen protocol

Frozen date: 2026-10-22

## 1. Purpose and evidence boundary

`formal_30_v3` measures the generalized Vue-to-San pipeline after the post-hoc
remediation derived from `formal_30_v1` and the targeted manual `formal_30_v2`
review. The v1 and v2 samples are development evidence for this comparison and
must not be counted as an untouched evaluation of the remediated pipeline.

The v3 holdout contains 30 samples selected only from the 61 entries recorded as
`development_unseen` in the parent split. It excludes all nine pilot samples and
all 30 formal_30_v1 samples. Selection happened before any v3 model run or result
inspection.

This is a fixed test protocol. After the first v3 model call:

- do not change Prompt, SSM extraction, Validator, renderer, repair loop, model,
  temperature, or maximum repair rounds;
- do not use `--force` or selectively replace failed results;
- infrastructure failures may resume through the unchanged checkpoint command;
- any algorithm or evaluator correction requires a new batch and protocol version;
- manual browser review, if performed, is reported separately from automatic pass rates.

## 2. Frozen configuration

- Batch: `formal_30_v3`
- Samples: 30 (`simple={counts['simple']}`, `medium={counts['medium']}`, `complex={counts['complex']}`)
- Maximum repair rounds: 3
- Provider: `qwen`
- Model: `qwen-plus`
- Pipeline outputs include full state for evidence reconstruction.

The reference San files are frozen only for later blinded analysis. They are not
provided to generation or repair requests.

## 3. Primary metrics

1. Automatic final pass rate among all 30 configured samples.
2. Automatic final pass rate among normally completed samples.
3. Initial pass rate and repaired-to-pass count.
4. Pass rate by simple, medium, and complex strata.
5. Repair-round and token totals.
6. Execution-error and final validation/visual error-code distributions.

The v1-to-v3 comparison is a between-sample comparison over two independently
frozen, complexity-balanced holdouts. It is not a paired rerun of the same 30
components and must be described with that limitation.

## 4. Selection algorithm

Within each complexity stratum, greedily choose the component that adds the most
previously uncovered feature-signature tags. Break ties by total signature size,
then by stable order in the parent split. Select 10 per stratum.

## 5. Samples

| ID | Component | Complexity |
| --- | --- | --- |
{sample_rows}

## 6. Preflight

```powershell
python data/experiments/protocols/formal_30_v3_frozen_20261022/verify_protocol.py --live
python -m unittest discover -s tests -p "test_*.py" -v
python migration_pipeline/run_batch_pipeline.py `
  --config-file migration_pipeline/batch_configs/formal_30_v3.json `
  --include-state `
  --dry-run
```

All three commands must pass before the first model call.

## 7. Formal run

Start `local_server` in a terminal with `LLM_API_KEY`, `LLM_PROVIDER=qwen`, and
`LLM_MODEL=qwen-plus`, then run in another activated `cardmig` terminal:

```powershell
python migration_pipeline/run_batch_pipeline.py `
  --config-file migration_pipeline/batch_configs/formal_30_v3.json `
  --include-state
```

Use exactly the same command to resume an infrastructure interruption. Do not add
`--force`.

## 8. Fixed outputs

- Generated code: `data/experiments/pipeline/batches/formal_30_v3/`
- Per-sample reports: `data/experiments/repair_reports/batches/formal_30_v3/`
- Checkpoint/summary: `data/experiments/batch_reports/formal_30_v3_summary.json`
- Later frozen result snapshot: a new timestamped `formal_30_v3_results_*` directory
"""


VERIFY_SCRIPT = '''"""Verify the frozen protocol and optionally its live inputs/runtime."""

import argparse
import hashlib
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    failures = []
    entries = []
    for line in (HERE / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        entries.append((expected, relative))
        frozen = HERE / relative
        if not frozen.is_file():
            failures.append(f"missing protocol file: {relative}")
        elif digest(frozen) != expected:
            failures.append(f"protocol checksum mismatch: {relative}")
        if args.live and relative.startswith("frozen/"):
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
    if PROTOCOL.exists():
        raise FileExistsError(f"Refusing to overwrite frozen protocol: {PROTOCOL}")

    parent = json.loads(PARENT_SPLIT.read_text(encoding="utf-8"))
    candidates = parent["development_unseen"]
    by_level = {
        level: [item for item in candidates if item["complexity"] == level]
        for level in LEVELS
    }
    selected = [
        item
        for level in LEVELS
        for item in stable_select(by_level[level])
    ]
    selected_ids = {item["id"] for item in selected}
    remaining = [item for item in candidates if item["id"] not in selected_ids]

    split_payload = {
        "split_id": "formal_30_v3_untouched_holdout",
        "created_date": str(date.today()),
        "parent_split": PARENT_SPLIT.relative_to(ROOT).as_posix(),
        "parent_split_sha256": digest(PARENT_SPLIT),
        "evidence_boundary": {
            "formal_30_v1": "Independent automatic baseline; later used for post-hoc diagnosis.",
            "formal_30_v2": "Targeted manual review/repair layer; development evidence only.",
            "formal_30_v3": "New post-remediation holdout selected before any v3 model run.",
        },
        "exclusions": {
            "development_pilot_ids": sorted(item["id"] for item in parent["development_pilot"]),
            "formal_30_v1_ids": sorted(item["id"] for item in parent["independent_test"]["samples"]),
        },
        "selection_method": {
            "candidate_pool": "parent development_unseen only",
            "stratification": "complexity",
            "samples_per_complexity": PER_LEVEL,
            "algorithm": "Greedy maximum new feature-signature coverage; total signature size and parent order break ties.",
        },
        "counts": {
            "candidate_pool": len(candidates),
            "selected": len(selected),
            "remaining_development": len(remaining),
            "selected_by_complexity": dict(Counter(item["complexity"] for item in selected)),
        },
        "samples": selected,
        "remaining_development": remaining,
    }
    SPLIT.parent.mkdir(parents=True, exist_ok=True)
    SPLIT.write_text(json.dumps(split_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    config_payload = {
        "batch_id": "formal_30_v3",
        "description": "Post-remediation untouched holdout, complexity-balanced and frozen before model execution.",
        "split_id": split_payload["split_id"],
        "source_split": SPLIT.relative_to(ROOT).as_posix(),
        "source_split_sha256": digest(SPLIT),
        "max_repair_rounds": 3,
        "expected_counts": {level: PER_LEVEL for level in LEVELS},
        "samples": [
            {
                "id": item["id"],
                "component_name": item["component_name"],
                "complexity": item["complexity"],
                "vue_file": item["vue_file"],
                "coverage_focus": item["feature_signature"],
            }
            for item in selected
        ],
    }
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(config_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    frozen_root = PROTOCOL / "frozen"
    for relative in RUNTIME_PATHS:
        source_path = ROOT / relative
        sources = iter_files(source_path) if source_path.is_file() else tracked_files(source_path)
        for source in sources:
            freeze_file(source, frozen_root)
    for source in (PARENT_SPLIT, SPLIT, CONFIG, ANALYSIS_REPORT):
        freeze_file(source, frozen_root)
    for item in selected:
        freeze_file(ROOT / item["vue_file"], frozen_root)
        freeze_file(ROOT / item["san_file"], frozen_root)

    PROTOCOL.mkdir(parents=True, exist_ok=True)
    (PROTOCOL / "PROTOCOL.md").write_text(protocol_markdown(selected), encoding="utf-8")
    (PROTOCOL / "verify_protocol.py").write_text(VERIFY_SCRIPT, encoding="utf-8")

    frozen_files = list(iter_files(frozen_root))
    manifest = {
        "protocol_id": PROTOCOL.name,
        "created_date": str(date.today()),
        "batch_id": "formal_30_v3",
        "split_file": SPLIT.relative_to(ROOT).as_posix(),
        "config_file": CONFIG.relative_to(ROOT).as_posix(),
        "sample_count": len(selected),
        "counts_by_complexity": dict(Counter(item["complexity"] for item in selected)),
        "git": git_metadata(),
        "frozen_payload_files": len(frozen_files),
        "selection_completed_before_model_run": True,
        "formal_outputs_existed_at_freeze": any(
            path.exists()
            for path in (
                ROOT / "data/experiments/pipeline/batches/formal_30_v3",
                ROOT / "data/experiments/repair_reports/batches/formal_30_v3",
                ROOT / "data/experiments/batch_reports/formal_30_v3_summary.json",
            )
        ),
    }
    (PROTOCOL / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    checksum_targets = [
        PROTOCOL / "PROTOCOL.md",
        PROTOCOL / "manifest.json",
        PROTOCOL / "verify_protocol.py",
        *frozen_files,
    ]
    checksum_lines = [
        f"{digest(path)}  {path.relative_to(PROTOCOL).as_posix()}"
        for path in sorted(checksum_targets)
    ]
    (PROTOCOL / "SHA256SUMS.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    print(f"wrote {SPLIT.relative_to(ROOT)}")
    print(f"wrote {CONFIG.relative_to(ROOT)}")
    print(f"froze {PROTOCOL.relative_to(ROOT)}")
    print("selected counts:", dict(Counter(item["complexity"] for item in selected)))
    print("remaining development:", len(remaining))


if __name__ == "__main__":
    main()
