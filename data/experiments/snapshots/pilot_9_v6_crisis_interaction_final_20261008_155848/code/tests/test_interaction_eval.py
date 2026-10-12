import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from migration_pipeline.utils.interaction_eval import evaluate_interaction_scenario


ROOT = Path(__file__).resolve().parents[1]
VUE = ROOT / "data/datasets/components/02_medium/FormRulePlayground/vue/FormRulePlayground.vue"
V4_SAN = ROOT / "data/experiments/pipeline/batches/pilot_9_v4/medium/FormRulePlayground_repaired.san"
REFERENCE_SAN = ROOT / "data/datasets/components/02_medium/FormRulePlayground/san/FormRulePlayground.san"
PAGINATION_VUE = ROOT / "data/datasets/components/02_medium/DataPaginationTable/vue/DataPaginationTable.vue"
PAGINATION_SAN = ROOT / "data/datasets/components/02_medium/DataPaginationTable/san/DataPaginationTable.san"


SCENARIO = [{
    "name": "invalid_submission",
    "steps": [
        {"op": "set", "path": "form", "value": {"name": "ab", "email": "bad", "age": 17}},
        {"op": "call", "method": "submit", "args": [{"__event": True}]},
    ],
}]

PAGINATION_SCENARIOS = [
    {"name": "sort_by_score", "steps": [
        {"op": "call", "method": "setSort", "args": ["score"]},
    ]},
    {"name": "go_to_next_page", "steps": [
        {"op": "call", "method": "go", "args": [1]},
    ]},
    {"name": "change_page_size", "steps": [
        {
            "op": "call",
            "method": "updatePageSize",
            "args": [{"__event": True, "target": {"value": "6"}}],
        },
    ]},
    {"name": "select_row", "steps": [
        {"op": "call", "method": "select", "args": [5]},
    ]},
]


class InteractionEvalTests(unittest.TestCase):
    def test_date_now_uses_the_configured_deterministic_clock(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            vue_file = temp_path / "Clock.vue"
            san_file = temp_path / "Clock.san"
            vue_file.write_text(
                "<script>module.exports = {data() { return {stamp: 0}; }, methods: {tick() { this.stamp = Date.now(); }}};</script>",
                encoding="utf-8",
            )
            san_file.write_text(
                "<script>module.exports = {initData() { return {stamp: 0}; }, tick() { this.data.set('stamp', Date.now()); }};</script>",
                encoding="utf-8",
            )

            result = evaluate_interaction_scenario(
                vue_file,
                san_file,
                [{"name": "tick", "steps": [{"op": "call", "method": "tick"}]}],
                fixed_now_ms=1_791_446_400_000,
            )

        self.assertTrue(result.passed, result.scenarios)
        self.assertEqual(result.scenarios[0]["vue"][-1]["data"]["stamp"], 1_791_446_400_000)

    def test_object_key_order_does_not_create_a_false_mismatch(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            vue_file = temp_path / "KeyOrder.vue"
            san_file = temp_path / "KeyOrder.san"
            vue_file.write_text(
                "<script>module.exports = {data() { return {first: 1, second: 2}; }, methods: {noop() {}}};</script>",
                encoding="utf-8",
            )
            san_file.write_text(
                "<script>module.exports = {initData() { return {second: 2, first: 1}; }, noop() {}};</script>",
                encoding="utf-8",
            )

            result = evaluate_interaction_scenario(
                vue_file,
                san_file,
                [{"name": "noop", "steps": [{"op": "call", "method": "noop"}]}],
            )

        self.assertTrue(result.passed, result.scenarios)

    def test_form_submission_scenario_detects_v4_semantic_drift(self):
        result = evaluate_interaction_scenario(
            VUE,
            V4_SAN,
            SCENARIO,
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.scenarios[0]["name"], "invalid_submission")
        self.assertNotEqual(
            result.scenarios[0]["vue"][-1]["computed"],
            result.scenarios[0]["san"][-1]["computed"],
        )

    def test_reference_form_submission_ignores_san_computed_cache_fields(self):
        result = evaluate_interaction_scenario(VUE, REFERENCE_SAN, SCENARIO)
        self.assertTrue(result.passed, result.scenarios)

    def test_data_pagination_scenarios_compare_state_computed_and_events(self):
        result = evaluate_interaction_scenario(
            PAGINATION_VUE,
            PAGINATION_SAN,
            PAGINATION_SCENARIOS,
        )

        self.assertTrue(result.passed, result.scenarios)
        by_name = {scenario["name"]: scenario for scenario in result.scenarios}
        next_page = by_name["go_to_next_page"]["vue"][-1]
        page_size = by_name["change_page_size"]["vue"][-1]
        selected = by_name["select_row"]["vue"][-1]
        self.assertEqual(next_page["data"]["page"], 2)
        self.assertEqual(next_page["fired"], [{"name": "page", "payload": 2}])
        self.assertEqual(page_size["data"]["pageSize"], 6)
        self.assertEqual(page_size["computed"]["pageCount"], 2)
        self.assertEqual(selected["data"]["selectedId"], 5)
        self.assertEqual(selected["computed"]["selectedRow"]["id"], 5)
        self.assertEqual(selected["fired"], [{"name": "select", "payload": 5}])


if __name__ == "__main__":
    unittest.main()
