import unittest
from pathlib import Path

from SSM.extractors.factory import SSMFactory
from SSM.extractors.vue_parser import VueSFCParser
from SSM.schema import v3


ROOT = Path(__file__).resolve().parents[1]
KANBAN_VUE = ROOT / "data/datasets/components/02_medium/KanbanColumnBoard/vue/KanbanColumnBoard.vue"
FORM_RULE_VUE = ROOT / "data/datasets/components/02_medium/FormRulePlayground/vue/FormRulePlayground.vue"
TASK_MANAGER_VUE = (
    ROOT
    / "data/experiments/protocols/formal_30_v3_frozen_20261022/frozen"
    / "data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue"
)


VUE_SOURCE = """<template>
  <section>
    <button @click="move(-1)">左移</button>
    <button @click="select(task.id)">选择</button>
  </section>
</template>

<script>
module.exports = {
  name: 'EventProbe',
  methods: {
    emitEvent(name, payload) {
      this.$emit(name, payload);
    },
    move(delta) {
      this.emitEvent('move', { delta });
    },
    select(id) {
      this.$emit('select', id);
    }
  }
};
</script>

<style>.probe { display: block; }</style>
"""

INLINE_COMPONENT_VUE = """<template><section><status-chip :label="label" /></section></template>
<script>
const StatusChip = {
  name: 'StatusChip',
  props: ['label'],
  template: '<strong>{{ label }}</strong>'
};
export default {
  name: 'InlineComponentHost',
  components: {'status-chip': StatusChip},
  data() { return {label: 'ready'}; }
};
</script>
<style>.host { display: block; }</style>
"""


class SSMEventExtractionTests(unittest.TestCase):
    def _build(self, **kwargs):
        return SSMFactory(**kwargs).build(VUE_SOURCE, "EventProbe.vue")

    def _assert_event_contract(self, ssm):
        dom_events = {
            event["handler_name"]: event
            for event in ssm["event_model"]["dom_events"]
        }
        self.assertEqual(dom_events["move"]["arguments"], ["-1"])
        self.assertEqual(dom_events["move"]["san_event_syntax"], 'on-click="move(-1)"')
        self.assertEqual(dom_events["select"]["arguments"], ["task.id"])
        self.assertEqual(
            dom_events["select"]["san_event_syntax"],
            'on-click="select(task.id)"',
        )

        custom_events = {
            event["event_name"]: event
            for event in ssm["event_model"]["custom_events"]
        }
        self.assertEqual(set(custom_events), {"move", "select"})
        self.assertEqual(custom_events["move"]["emit_points"], ["move"])
        self.assertIn("emitEvent('move', ...)", custom_events["move"]["emit_expression"])
        self.assertEqual(custom_events["move"]["san_emit"], "this.fire('move', ...)")
        self.assertEqual(custom_events["select"]["emit_points"], ["select"])
        self.assertEqual(custom_events["select"]["san_emit"], "this.fire('select', ...)")

        patterns = {
            item["pattern_id"]
            for item in ssm["migration_hints"]["detected_patterns"]
        }
        self.assertIn("emit", patterns)

    def test_node_bridge_preserves_arguments_and_resolves_emit_wrapper(self):
        self._assert_event_contract(self._build())

    def test_python_fallback_preserves_arguments_and_resolves_emit_wrapper(self):
        self._assert_event_contract(self._build(use_node_bridge=False))

    def test_v3_schema_resolution_variants_remain_compatible(self):
        factories = [
            SSMFactory(schema_module="v3"),
            SSMFactory(schema_module="SSM.schema.v3"),
            SSMFactory(schema_module=v3),
        ]
        for factory in factories:
            with self.subTest(schema=factory.schema.__name__):
                ssm = factory.build(VUE_SOURCE, "EventProbe.vue")
                self.assertEqual(ssm["schema_version"], "3.0")
                self._assert_event_contract(ssm)

    def test_kanban_component_exposes_real_event_contract(self):
        ssm = SSMFactory().build_from_file(str(KANBAN_VUE))
        dom_events = {
            event["handler_expression"]: event["san_event_syntax"]
            for event in ssm["event_model"]["dom_events"]
        }
        self.assertEqual(dom_events["move(-1)"], 'on-click="move(-1)"')
        self.assertEqual(dom_events["move(1)"], 'on-click="move(1)"')
        self.assertEqual(
            dom_events["select(task.id)"],
            'on-click="select(task.id)"',
        )

        custom_events = {
            event["event_name"]: event
            for event in ssm["event_model"]["custom_events"]
        }
        self.assertEqual(set(custom_events), {"move", "add"})
        self.assertEqual(custom_events["move"]["emit_points"], ["move"])
        self.assertEqual(custom_events["add"]["emit_points"], ["add"])
        self.assertEqual(custom_events["move"]["san_emit"], "this.fire('move', ...)")
        self.assertEqual(custom_events["add"]["san_emit"], "this.fire('add', ...)")

    def test_data_defaults_are_complete_and_static_for_node_and_fallback(self):
        for use_node_bridge in (True, False):
            with self.subTest(use_node_bridge=use_node_bridge):
                ssm = SSMFactory(use_node_bridge=use_node_bridge).build_from_file(
                    str(FORM_RULE_VUE)
                )
                fields = {
                    item["name"]: item
                    for item in ssm["script"]["options"]["data"]
                }

                self.assertIn('"age": 18', fields["form"]["default_value_expression"])
                self.assertEqual(fields["form"]["default_value"]["age"], 18)
                self.assertTrue(fields["form"]["default_value_static"])
                self.assertIn('"name"', fields["enabled"]["default_value_expression"])
                self.assertEqual(
                    fields["enabled"]["default_value"],
                    ["email", "adult", "name"],
                )
                self.assertTrue(fields["enabled"]["default_value_static"])

    def test_computed_and_method_sources_are_not_truncated(self):
        ssm = SSMFactory().build_from_file(str(FORM_RULE_VUE))
        computed = {item["name"]: item for item in ssm["script"]["options"]["computed"]}
        methods = {item["name"]: item for item in ssm["script"]["options"]["methods"]}
        self.assertIn("Number(this.form.age)", computed["errors"]["getter_body_full"])
        self.assertGreater(len(computed["errors"]["getter_body_full"]), len(computed["errors"]["getter_body"]))
        self.assertIn("this.emitEvent", methods["submit"]["body_full"])

    def test_multi_component_sfc_uses_root_export_in_bridge_and_fallback(self):
        for use_node_bridge in (True, False):
            with self.subTest(use_node_bridge=use_node_bridge):
                ssm = SSMFactory(use_node_bridge=use_node_bridge).build_from_file(
                    str(TASK_MANAGER_VUE)
                )
                options = ssm["script"]["options"]
                methods = {item["name"] for item in options["methods"]}
                data_fields = {item["name"] for item in options["data"]}

                self.assertEqual(ssm["metadata"]["component_name"], "TaskManager")
                self.assertEqual(options["name"], "TaskManager")
                self.assertEqual(options["props"], [])
                self.assertIn("tasks", data_fields)
                self.assertIn("showNotification", methods)

    def test_task_manager_node_bridge_parses_watch_object_methods(self):
        source = TASK_MANAGER_VUE.read_text(encoding="utf-8")
        parsed = VueSFCParser(use_node_bridge=True)._try_node_bridge(
            source,
            str(TASK_MANAGER_VUE),
        )

        self.assertIsNotNone(parsed)
        options = parsed["analysis"]["script"]["options"]
        self.assertEqual(parsed["component_name"], "TaskManager")
        self.assertEqual(options["name"], "TaskManager")
        self.assertEqual(
            {watch["expression"] for watch in options["watch"]},
            {"tasks", "settings"},
        )
        self.assertTrue(all(watch["handler_body"] for watch in options["watch"]))

    def test_inline_event_assignments_are_not_method_handlers(self):
        ssm = SSMFactory().build_from_file(str(TASK_MANAGER_VUE))
        assignments = [
            event
            for event in ssm["event_model"]["dom_events"]
            if event["handler_expression"].startswith("showSettings =")
        ]

        self.assertEqual(len(assignments), 3)
        self.assertTrue(all(event["handler_type"] == "inline_expression" for event in assignments))
        self.assertTrue(all(event["handler_name"] == "" for event in assignments))

    def test_inline_registered_component_source_is_preserved(self):
        for use_node_bridge in (True, False):
            with self.subTest(use_node_bridge=use_node_bridge):
                ssm = SSMFactory(use_node_bridge=use_node_bridge).build(
                    INLINE_COMPONENT_VUE,
                    "InlineComponentHost.vue",
                )
                component = ssm["script"]["options"]["components"][0]
                sub_component = ssm["sub_components"][0]

                self.assertEqual(component["source_name"], "StatusChip")
                self.assertEqual(component["definition_location"], "inline")
                self.assertIn(
                    "template: '<strong>{{ label }}</strong>'",
                    component["inline_definition"]["source_code"],
                )
                self.assertTrue(sub_component["is_inline"])
                self.assertFalse(sub_component["is_imported"])
                self.assertEqual(
                    sub_component["inline_definition"],
                    component["inline_definition"],
                )


if __name__ == "__main__":
    unittest.main()
