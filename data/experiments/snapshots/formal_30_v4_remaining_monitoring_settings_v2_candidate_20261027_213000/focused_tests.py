import json
import subprocess
import unittest
from pathlib import Path

from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.replay_formal_30_v4_remaining_monitoring_syntax_fix import (
    OUTPUT,
    SOURCE_SHA256,
    build_candidate,
    check_candidate,
    sha256,
)
from migration_pipeline.replay_formal_30_v4_remaining_monitoring_settings_fix import (
    OUTPUT as SETTINGS_OUTPUT,
    SOURCE as SETTINGS_SOURCE,
    SOURCE_SHA256 as SETTINGS_SOURCE_SHA256,
    build_candidate as build_settings_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
FAILED = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_generalization_remaining_v1_monitoring_failed_20261027_205900"
)
SOURCE = FAILED / "MonitoringDashboard_repaired_repaired_repaired.san"
HISTORY = FAILED / "repair_history.json"


class MonitoringRemainingBoundedFixTests(unittest.TestCase):
    def test_frozen_failure_reproduces_four_error_classes(self):
        state = json.loads(HISTORY.read_text(encoding="utf-8"))["state"]
        result = ValidateStage().run(ValidateStageInput(
            generated_file_path=str(SOURCE),
            ssm=state["ssm"],
            vue_file_path=str(FAILED / "source.vue"),
            compile_check=True,
        ))
        self.assertEqual(
            {issue["code"] for issue in result.validation_errors},
            {
                "invalid_san_event_handler_syntax",
                "invalid_san_for_alias_syntax",
                "duplicate_class_attribute",
                "san_script_compile_error",
            },
        )
        self.assertIn(
            "Missing initializer in const declaration",
            str(result.san_compile_result),
        )

    def test_bounded_v1_replay_compiles_and_exposes_chart_dependencies(self):
        self.assertEqual(sha256(SOURCE), SOURCE_SHA256)
        candidate = build_candidate(SOURCE.read_text(encoding="utf-8"))
        self.assertEqual(candidate, OUTPUT.read_text(encoding="utf-8"))
        validation, visual = check_candidate(candidate)
        self.assertTrue(validation.validation_passed, validation.validation_errors)
        self.assertTrue(visual.visual_eval_passed, visual.visual_eval_errors)
        self.assertEqual(candidate.count("= san.defineComponent({"), 8)
        self.assertNotIn("const kpi-card =", candidate)
        self.assertIn("cx=\"{{getX(idx, dataPoints, width)}}\"", candidate)
        self.assertIn("cy=\"{{getY(point, height, maxValue, minValue)}}\"", candidate)
        self.assertIn("on-save=\"saveSettings($event)\"", candidate)

    def test_v2_settings_replay_is_source_guarded(self):
        self.assertEqual(sha256(SETTINGS_SOURCE), SETTINGS_SOURCE_SHA256)
        candidate = build_settings_candidate(SETTINGS_SOURCE.read_text(encoding="utf-8"))
        self.assertEqual(candidate, SETTINGS_OUTPUT.read_text(encoding="utf-8"))
        self.assertIn("this.data.set('localSettings', { ...(this.data.get('settings') || {}) });", candidate)
        self.assertIn('on-click="stop:onModalContentClick"', candidate)

    def test_v2_san_instances_copy_settings_and_keep_chart_geometry(self):
        script = r"""
const assert = require('assert');
const fs = require('fs');
const san = require('san');
const source = fs.readFileSync(process.argv[1], 'utf8');
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
const moduleRef = {exports: {}};
new Function('module', 'exports', 'require', script)(moduleRef, moduleRef.exports, require);
const children = moduleRef.exports.prototype.components;
const inputSettings = {refreshInterval: 13, alertThreshold: 72,
  logRetention: '30', autoRefresh: false, desktopNotifications: true};
const form = new children['settings-form']({data: {settings: inputSettings}});
assert.deepStrictEqual(form.data.get('localSettings'), inputSettings);
form.data.set('localSettings.refreshInterval', 21);
assert.strictEqual(inputSettings.refreshInterval, 13);
let saved;
form.on('save', payload => {saved = payload;});
form.handleSubmit();
assert.strictEqual(saved.refreshInterval, 21);
const chart = new children['real-time-chart']({data: {
  data: [{value: 10}, {value: 20}], height: 250, width: 600
}});
assert.strictEqual(chart.getX(0, [10, 20], 600), 0);
assert.strictEqual(chart.getX(1, [10, 20], 600), 600);
assert.strictEqual(chart.getY(10, 250, 20, 10), 250);
assert.strictEqual(chart.getY(20, 250, 20, 10), 0);
const request = new children['request-chart']({data: {data: [
  {count: 25}, {count: 50}
]}});
assert.strictEqual(request.getX(1, [{count: 25}, {count: 50}]), 402);
assert.strictEqual(request.getHeight(50, 100), 140);
"""
        completed = subprocess.run(
            ["node", "-e", script, str(SETTINGS_OUTPUT)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
