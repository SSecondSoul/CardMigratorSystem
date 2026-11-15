"""Checks for outcome-blind selection of the next independent-test candidates."""

import json
import unittest

from migration_pipeline.prepare_formal_30_v5_candidate_split import (
    CONFIG,
    OUTPUT,
    PARENT,
    PARENT_SHA256,
    SPLIT_SHA256,
    build_config,
    build_split,
    sha256,
    stable_select,
)
from migration_pipeline.audit_formal_30_v5_candidate_exposure import audit


class Formal30V5CandidateSplitTests(unittest.TestCase):
    def test_stable_select_prefers_new_coverage_then_parent_order(self):
        candidates = [
            {"id": f"item_{index}", "feature_signature": [f"feature_{index}"]}
            for index in range(11)
        ]
        selected, trace = stable_select(candidates)
        self.assertEqual([item["id"] for item in selected], [f"item_{i}" for i in range(10)])
        self.assertEqual([item["parent_stratum_index"] for item in trace], list(range(10)))

    def test_actual_split_is_balanced_disjoint_and_reproducible(self):
        self.assertEqual(sha256(PARENT), PARENT_SHA256)
        parent = json.loads(PARENT.read_text(encoding="utf-8"))
        split = build_split(parent, parent_sha256=PARENT_SHA256)
        self.assertEqual(split, build_split(parent, parent_sha256=PARENT_SHA256))
        self.assertEqual(split["status"], "exploratory_candidate_pending_protocol_and_runtime_freeze")
        self.assertFalse(split["independent_holdout_result"])
        self.assertEqual(split["counts"]["selected_by_complexity"], {
            "simple": 10, "medium": 10, "complex": 10,
        })
        self.assertEqual(split["excluded"], [{"id": "quote_card", "complexity": "simple"}])
        selected_ids = {item["id"] for item in split["samples"]}
        self.assertEqual(len(selected_ids), 30)
        self.assertFalse(selected_ids & {item["id"] for item in parent["samples"]})
        self.assertTrue(all(len(item["vue_sha256"]) == 64 for item in split["samples"]))
        self.assertTrue(all(len(item["reference_san_sha256"]) == 64 for item in split["samples"]))

    def test_batch_plan_follows_split_and_three_round_decision(self):
        parent = json.loads(PARENT.read_text(encoding="utf-8"))
        split = build_split(parent, parent_sha256=PARENT_SHA256)
        config = build_config(split, split_sha256=SPLIT_SHA256)
        self.assertEqual(config["max_repair_rounds"], 3)
        self.assertEqual(config["source_split_sha256"], SPLIT_SHA256)
        self.assertEqual(config["expected_counts"], {"simple": 10, "medium": 10, "complex": 10})
        self.assertEqual([item["id"] for item in config["samples"]], [item["id"] for item in split["samples"]])
        self.assertNotIn("coverage_focus", next(item for item in config["samples"] if item["id"] == "stock"))
        self.assertEqual(sha256(OUTPUT), SPLIT_SHA256)
        self.assertEqual(json.loads(OUTPUT.read_text(encoding="utf-8")), split)
        self.assertEqual(json.loads(CONFIG.read_text(encoding="utf-8")), config)

    def test_early_dataset_notebook_exposure_is_not_missed_by_id_search(self):
        result = audit()
        self.assertEqual(result["unique_candidate_names_mentioned"], 23)
        self.assertEqual(result["mentioned_by_complexity"], {
            "simple": 7, "medium": 8, "complex": 8,
        })
        self.assertEqual(len(result["not_mentioned_in_these_notebooks"]), 7)


if __name__ == "__main__":
    unittest.main()
