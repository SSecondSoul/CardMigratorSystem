"""Read-only audit of candidate names in early dataset-validation notebooks.

A name mention is evidence of dataset-production contact, not proof that the
component entered a migration model request or was used to tune a prompt.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from migration_pipeline.prepare_formal_30_v5_candidate_split import OUTPUT, ROOT, SPLIT_SHA256, sha256


NOTEBOOKS = (
    "notebooks/01-data-exploration/2026-09-02_vue_san_batch_validation_issues.ipynb",
    "notebooks/01-data-exploration/2026-09-04_vue_san_batch_30_validation_issues.ipynb",
    "notebooks/01-data-exploration/2026-09-10_vue_san_batch_39_validation_issues.ipynb",
)


def audit() -> dict:
    if sha256(OUTPUT) != SPLIT_SHA256:
        raise RuntimeError("Candidate split checksum changed")
    samples = json.loads(OUTPUT.read_text(encoding="utf-8"))["samples"]
    hits: dict[str, list[str]] = {}
    for relative in NOTEBOOKS:
        notebook = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        notebook_text = "\n".join(
            "".join(cell.get("source", [])) for cell in notebook.get("cells", [])
        )
        hits[relative] = [
            sample["id"] for sample in samples
            if re.search(
                r"(?<![A-Za-z0-9_])" + re.escape(sample["component_name"]) + r"(?![A-Za-z0-9_])",
                notebook_text,
                re.IGNORECASE,
            )
        ]
    mentioned = {sample_id for ids in hits.values() for sample_id in ids}
    return {
        "candidate_split_sha256": SPLIT_SHA256,
        "notebook_name_hits": hits,
        "unique_candidate_names_mentioned": len(mentioned),
        "mentioned_by_complexity": {
            level: sum(sample["id"] in mentioned and sample["complexity"] == level for sample in samples)
            for level in ("simple", "medium", "complex")
        },
        "not_mentioned_in_these_notebooks": [
            sample["id"] for sample in samples if sample["id"] not in mentioned
        ],
        "limitation": "Name mentions are not proof of migration-model or prompt-tuning exposure; absence is not proof of no exposure.",
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
