"""Create the reproducible development/formal-test split for the component dataset.

The selector is intentionally deterministic: pilot samples are excluded from the
formal test set, then each complexity stratum is selected by greedy feature
coverage with manifest order as the tie breaker.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/datasets/dataset_manifest.json"
TAGS = ROOT / "data/datasets/features/pattern_tags.json"
SPLIT = ROOT / "data/datasets/splits/pilot_9_v6_development_and_formal_30_v1.json"
CONFIG = ROOT / "migration_pipeline/batch_configs/formal_30_v1.json"
PILOT_IDS = {
    "step_card",
    "bookmark_toggle_card",
    "star_rating_input",
    "kanban_column_board",
    "data_pagination_table",
    "form_rule_playground",
    "crisis_communication_hub",
    "warehouse_picking_wave",
    "workflow_diagram_editor",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def tag_key(component: dict, tags: dict, index: dict[str, str]) -> str | None:
    candidates = [
        component["id"],
        component["path"].rstrip("/").split("/")[-1],
        Path(component["vue_file"]).stem,
        component["id"].replace("_", "-"),
    ]
    for candidate in candidates:
        if normalize(candidate) in index:
            return index[normalize(candidate)]
    return None


def feature_set(component: dict, tags: dict, index: dict[str, str]) -> tuple[str | None, set[str]]:
    key = tag_key(component, tags, index)
    item = tags.get(key, {}) if key else {}
    features: set[str] = set()
    for group in ("templates", "scripts", "styles"):
        features.update(f"{group}.{name}" for name, enabled in item.get(group, {}).items() if enabled)
    features.update(f"migration.{name}" for name in item.get("migration_patterns", []))
    return key, features


def select_formal(components: list[dict], features: dict[str, set[str]]) -> dict[str, list[dict]]:
    selected: dict[str, list[dict]] = {}
    for level in ("simple", "medium", "complex"):
        pool = [c for c in components if c["complexity"] == level and c["id"] not in PILOT_IDS]
        chosen: list[dict] = []
        covered: set[str] = set()
        while len(chosen) < 10:
            candidate = max(
                pool,
                key=lambda item: (
                    len(features[item["id"]] - covered),
                    len(features[item["id"]]),
                    -components.index(item),
                ),
            )
            chosen.append(candidate)
            covered.update(features[candidate["id"]])
            pool.remove(candidate)
        selected[level] = chosen
    return selected


def relative_vue_path(component: dict) -> str:
    return f"data/datasets/{component['path']}vue/{component['vue_file']}"


def main() -> None:
    manifest_bytes = MANIFEST.read_bytes()
    tags_bytes = TAGS.read_bytes()
    manifest = json.loads(manifest_bytes)
    tags = json.loads(tags_bytes)
    components = manifest["components"]
    tag_index = {normalize(key): key for key in tags}
    tag_keys: dict[str, str | None] = {}
    features: dict[str, set[str]] = {}
    for component in components:
        key, values = feature_set(component, tags, tag_index)
        tag_keys[component["id"]] = key
        features[component["id"]] = values

    formal = select_formal(components, features)
    formal_ids = [item["id"] for level in ("simple", "medium", "complex") for item in formal[level]]
    pilot = [item for item in components if item["id"] in PILOT_IDS]
    development_unseen = [item for item in components if item["id"] not in PILOT_IDS and item["id"] not in formal_ids]

    def record(item: dict) -> dict:
        return {
            "id": item["id"],
            "component_name": Path(item["vue_file"]).stem,
            "complexity": item["complexity"],
            "vue_file": relative_vue_path(item),
            "san_file": f"data/datasets/{item['path']}san/{item['san_file']}",
            "pattern_tag_key": tag_keys[item["id"]],
            "feature_signature": sorted(features[item["id"]]),
        }

    split = {
        "split_id": "pilot_9_v6_development_and_formal_30_v1",
        "created_date": str(date.today()),
        "source_manifest": "data/datasets/dataset_manifest.json",
        "source_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "source_pattern_tags": "data/datasets/features/pattern_tags.json",
        "source_pattern_tags_sha256": hashlib.sha256(tags_bytes).hexdigest(),
        "counts": {"total": len(components), "development": 70, "independent_test": 30},
        "selection_method": {
            "stratification": "complexity",
            "independent_test_per_complexity": 10,
            "pilot_exclusion": "The nine pilot_9_v2-v6 calibration samples are development_pilot only.",
            "algorithm": "Greedy maximum feature-signature coverage within each complexity stratum; manifest order breaks ties.",
        },
        "pilot_exclusion_ids": sorted(PILOT_IDS),
        "development_pilot": [record(item) for item in pilot],
        "development_unseen": [record(item) for item in development_unseen],
        "independent_test": {
            "counts_by_complexity": {level: len(formal[level]) for level in ("simple", "medium", "complex")},
            "samples": [record(item) for level in ("simple", "medium", "complex") for item in formal[level]],
        },
        "tag_mapping": {
            "matched": sum(value is not None for value in tag_keys.values()),
            "unmatched_ids": sorted(key for key, value in tag_keys.items() if value is None),
            "normalization": "id, directory name, Vue stem, and snake_case-to-kebab variants normalized to lowercase alphanumeric.",
        },
    }
    SPLIT.parent.mkdir(parents=True, exist_ok=True)
    SPLIT.write_text(json.dumps(split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    samples = []
    for level in ("simple", "medium", "complex"):
        for item in formal[level]:
            samples.append(
                {
                    "id": item["id"],
                    "component_name": Path(item["vue_file"]).stem,
                    "complexity": item["complexity"],
                    "vue_file": relative_vue_path(item),
                    "coverage_focus": sorted(features[item["id"]]),
                }
            )
    config = {
        "batch_id": "formal_30_v1",
        "description": "Independent stratified formal test set derived from pilot_9_v6 development calibration.",
        "split_id": split["split_id"],
        "source_split": "data/datasets/splits/pilot_9_v6_development_and_formal_30_v1.json",
        "source_split_sha256": digest(SPLIT),
        "max_repair_rounds": 3,
        "expected_counts": {"simple": 10, "medium": 10, "complex": 10},
        "samples": samples,
    }
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {SPLIT}")
    print(f"wrote {CONFIG}")
    print("formal counts:", {level: len(formal[level]) for level in ("simple", "medium", "complex")})
    print("tag mapping:", split["tag_mapping"])


if __name__ == "__main__":
    main()
