"""Bounds for the TaskManager pre-mount no-op replay."""

import json
import unittest
from pathlib import Path

from migration_pipeline.replay_formal_30_v4_task_manager_premount_noop_fix import (
    remove_redundant_parent_writes,
)
from migration_pipeline.stages.repair import RepairStage


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_four_residual_probe_v1_result_20261029_224507/candidate.san"
)
HISTORY = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_source_events_regression_v1_TaskManager_automatic_fail_20261029_222317/repair_history.json"
)


class TaskManagerPremountNoopFixTests(unittest.TestCase):
    def test_frozen_candidate_changes_only_four_expected_lines(self):
        before = SOURCE.read_text(encoding="utf-8")
        after = remove_redundant_parent_writes(before)
        expected = before
        for field in ("settings", "notification"):
            expected = expected.replace(
                f"    const {field} = this.data.get('{field}');\n", "", 1
            ).replace(
                f"    this.data.set('{field}', {field});\n", "", 1
            )
        self.assertEqual(after, expected)
        self.assertIn("this.watch('settings'", after)
        self.assertIn("this.loadInitialData();", after)
        self.assertIn("this.startAutoSync();", after)

    def test_missing_pair_fails_closed(self):
        before = SOURCE.read_text(encoding="utf-8")
        without_getter = before.replace(
            "    const settings = this.data.get('settings');\n", "", 1
        )
        with self.assertRaisesRegex(RuntimeError, "settings"):
            remove_redundant_parent_writes(without_getter)

    def test_inline_child_pair_is_not_treated_as_parent_pair(self):
        code = """const san = require('san');
const Child = san.defineComponent({
    inited() {
        const settings = this.data.get('settings');
        this.data.set('settings', settings);
    }
});
module.exports = san.defineComponent({
    inited() {
        const settings = this.data.get('settings');
        const notification = this.data.get('notification');
        this.data.set('settings', settings);
        this.data.set('notification', notification);
    },
    attached() { this.loadInitialData(); }
});"""
        after = remove_redundant_parent_writes(code)
        self.assertEqual(after.count("const settings = this.data.get('settings');"), 1)
        self.assertEqual(after.count("this.data.set('settings', settings);"), 1)
        self.assertIn("attached() { this.loadInitialData(); }", after)

    def test_production_rule_replays_frozen_candidate_exactly(self):
        before = SOURCE.read_text(encoding="utf-8")
        ssm = json.loads(HISTORY.read_text(encoding="utf-8"))["state"]["ssm"]
        expected = remove_redundant_parent_writes(before)
        actual = RepairStage._normalize_parent_premount_noop_writes(before, ssm)
        self.assertEqual(actual, expected)
        self.assertEqual(
            RepairStage._normalize_parent_premount_noop_writes(actual, ssm), actual
        )

    def test_production_rule_fails_closed_on_created_or_real_local_use(self):
        before = SOURCE.read_text(encoding="utf-8")
        ssm = json.loads(HISTORY.read_text(encoding="utf-8"))["state"]["ssm"]
        with_created = json.loads(json.dumps(ssm))
        with_created["script"]["options"]["lifecycle_hooks"].append(
            {"vue_hook": "created", "san_hook": "inited", "body": "{}"}
        )
        self.assertEqual(
            RepairStage._normalize_parent_premount_noop_writes(before, with_created),
            before,
        )
        used = before.replace(
            "    const settings = this.data.get('settings');\n",
            "    const settings = this.data.get('settings');\n"
            "    this.audit(settings);\n",
            1,
        )
        after = RepairStage._normalize_parent_premount_noop_writes(used, ssm)
        self.assertIn("    this.data.set('settings', settings);", after)
        self.assertNotIn("    this.data.set('notification', notification);", after)

    def test_production_rule_requires_mounted_source_write_evidence(self):
        before = SOURCE.read_text(encoding="utf-8")
        ssm = json.loads(HISTORY.read_text(encoding="utf-8"))["state"]["ssm"]
        no_writes = json.loads(json.dumps(ssm))
        for method in no_writes["script"]["options"]["methods"]:
            if method.get("name") in {"loadInitialData", "showNotification"}:
                method["writes_inferred"] = []
        self.assertEqual(
            RepairStage._normalize_parent_premount_noop_writes(before, no_writes),
            before,
        )


if __name__ == "__main__":
    unittest.main()
