"""Prepare the balanced post-v4 candidate split and batch plan without a model.

This file selects sample identifiers, hashes dataset inputs, and optionally writes
the batch configuration. It does not freeze a protocol or launch a batch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "data/datasets/splits/formal_30_v3_untouched_holdout.json"
OUTPUT = ROOT / "data/datasets/splits/formal_30_v5_candidate_20261030.json"
CONFIG = ROOT / "migration_pipeline/batch_configs/formal_30_v5.json"
PARENT_SHA256 = "972a47f257ed7f34e6ecbcf28a0498e0adc1bb2dc126e676e7459eb4f44c9481"
SPLIT_SHA256 = "5cb5cda78d054feb3c0f7069db886131af8d99a0da671d4c8e8a1323dd80f3db"
LEVELS = ("simple", "medium", "complex")
PER_LEVEL = 10


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_select(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Use the v3 feature-coverage rule with parent order as final tie-breaker."""
    if len(candidates) < PER_LEVEL:
        raise ValueError("Fewer than ten candidates in a complexity stratum")
    selected: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
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
        newly_covered = sorted(set(candidate.get("feature_signature", [])) - covered)
        trace.append({
            "rank": len(selected) + 1,
            "id": candidate["id"],
            "new_feature_count": len(newly_covered),
            "total_feature_count": len(set(candidate.get("feature_signature", []))),
            "parent_stratum_index": index,
        })
        selected.append(candidate)
        covered.update(candidate.get("feature_signature", []))
        pool = [pair for pair in pool if pair[0] != index]
    return selected, trace


def build_split(parent: dict[str, Any], *, parent_sha256: str) -> dict[str, Any]:
    remaining = parent.get("remaining_development")
    earlier = parent.get("samples")
    if not isinstance(remaining, list) or not isinstance(earlier, list) or len(remaining) != 31:
        raise ValueError("Expected the frozen v3 split with exactly 31 remaining entries")
    ids = [item.get("id") for item in remaining]
    if len(set(ids)) != len(ids) or set(ids) & {item.get("id") for item in earlier}:
        raise ValueError("Duplicate or previously selected sample ID")
    counts = Counter(item.get("complexity") for item in remaining)
    if counts != Counter({"simple": 11, "medium": 10, "complex": 10}):
        raise ValueError(f"Unexpected remaining stratum counts: {counts}")
    selected: list[dict[str, Any]] = []
    selection_trace: dict[str, list[dict[str, Any]]] = {}
    for level in LEVELS:
        candidates = [item for item in remaining if item["complexity"] == level]
        chosen, trace = stable_select(candidates)
        selected.extend(chosen)
        selection_trace[level] = trace
    selected_ids = {item["id"] for item in selected}
    excluded = [item for item in remaining if item["id"] not in selected_ids]
    if len(selected) != 30 or len(excluded) != 1 or excluded[0]["complexity"] != "simple":
        raise ValueError("Balanced selection did not leave one simple candidate")
    samples = []
    for item in selected:
        vue = (ROOT / item["vue_file"]).resolve()
        san = (ROOT / item["san_file"]).resolve()
        if not vue.is_relative_to(ROOT) or not san.is_relative_to(ROOT):
            raise ValueError(f"Out-of-workspace source path: {item['id']}")
        if not vue.is_file() or not san.is_file():
            raise FileNotFoundError(f"Missing dataset source/reference: {item['id']}")
        samples.append({
            **item,
            "vue_sha256": sha256(vue),
            "reference_san_sha256": sha256(san),
        })
    return {
        "split_id": "formal_30_v5_candidate_20261030",
        "status": "exploratory_candidate_pending_protocol_and_runtime_freeze",
        "independent_holdout_result": False,
        "parent_split": PARENT.relative_to(ROOT).as_posix(),
        "parent_split_sha256": parent_sha256,
        "selection_method": {
            "candidate_pool": "v3 remaining_development only",
            "stratification": "complexity",
            "per_complexity": PER_LEVEL,
            "algorithm": "Greedy maximum new feature-signature coverage; total signature size and parent order break ties, exactly as in v3.",
            "outcome_blind": True,
        },
        "counts": {
            "candidate_pool": len(remaining),
            "selected": len(samples),
            "excluded": len(excluded),
            "selected_by_complexity": dict(Counter(item["complexity"] for item in samples)),
        },
        "selection_trace": selection_trace,
        "excluded": [{"id": item["id"], "complexity": item["complexity"]} for item in excluded],
        "samples": samples,
        "evidence_boundary": [
            "Sample IDs have no documented batch/config/report use in the 2026-10-30 audit.",
            "All source Vue files were bulk-copied into an earlier pilot evidence bundle, not shown to be model inputs.",
            "23 of 30 component names appear in early dataset-validation notebooks; prior migration-tuning use cannot be excluded.",
            "This set is for an exploratory evaluation with early-contact disclosure, not a strict independent holdout.",
            "No v5 model call or formal protocol freeze has occurred.",
        ],
    }


def build_config(split: dict[str, Any], *, split_sha256: str) -> dict[str, Any]:
    if split["counts"]["selected_by_complexity"] != {level: PER_LEVEL for level in LEVELS}:
        raise ValueError("Candidate split is not balanced")
    return {
        "batch_id": "formal_30_v5",
        "description": "Post-v4 exploratory evaluation with disclosed early contact; not executable until protocol and runtime are frozen.",
        "split_id": split["split_id"],
        "source_split": OUTPUT.relative_to(ROOT).as_posix(),
        "source_split_sha256": split_sha256,
        "max_repair_rounds": 3,
        "expected_counts": {level: PER_LEVEL for level in LEVELS},
        "samples": [
            {
                "id": item["id"],
                "component_name": item["component_name"],
                "complexity": item["complexity"],
                "vue_file": item["vue_file"],
                **({"coverage_focus": item["feature_signature"]} if item["feature_signature"] else {}),
            }
            for item in split["samples"]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the candidate split once.")
    parser.add_argument("--write-config", action="store_true", help="Write the batch plan once from the verified candidate split.")
    args = parser.parse_args()
    if sha256(PARENT) != PARENT_SHA256:
        raise RuntimeError("Parent split checksum changed")
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    split = build_split(parent, parent_sha256=PARENT_SHA256)
    print("selected:", split["counts"]["selected_by_complexity"])
    print("excluded:", split["excluded"])
    print("model_request_performed: false")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("candidate_split:", OUTPUT.relative_to(ROOT))
        print("sha256:", sha256(OUTPUT))
    if args.write_config:
        if sha256(OUTPUT) != SPLIT_SHA256:
            raise RuntimeError("Candidate split checksum changed")
        if CONFIG.exists():
            raise FileExistsError(CONFIG)
        config = build_config(split, split_sha256=SPLIT_SHA256)
        CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("candidate_config:", CONFIG.relative_to(ROOT))
        print("config_sha256:", sha256(CONFIG))


if __name__ == "__main__":
    main()
