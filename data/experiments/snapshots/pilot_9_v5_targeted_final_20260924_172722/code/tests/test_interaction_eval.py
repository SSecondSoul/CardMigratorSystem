import unittest
from pathlib import Path

from migration_pipeline.utils.interaction_eval import evaluate_interaction_scenario


ROOT = Path(__file__).resolve().parents[1]
VUE = ROOT / "data/datasets/components/02_medium/FormRulePlayground/vue/FormRulePlayground.vue"
V4_SAN = ROOT / "data/experiments/pipeline/batches/pilot_9_v4/medium/FormRulePlayground_repaired.san"
REFERENCE_SAN = ROOT / "data/datasets/components/02_medium/FormRulePlayground/san/FormRulePlayground.san"


SCENARIO = [{
    "name": "invalid_submission",
    "steps": [
        {"op": "set", "path": "form", "value": {"name": "ab", "email": "bad", "age": 17}},
        {"op": "call", "method": "submit", "args": [{"__event": True}]},
    ],
}]


class InteractionEvalTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
