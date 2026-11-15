"""Source-matched payload and hook relocation: positive, runtime and refusal cases."""

import json
import subprocess
import unittest
from pathlib import Path

from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.utils.san_compile import check_san_compile
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.utils.repair_scheduler import candidate_gate


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'data/experiments/snapshots/formal_30_v4_semantic_closure_v2_results_20261103_160541'


def fixtures():
    vue = '''<template><div><item-card v-for="(item, index) in items" @click="choose(item)"/></div></template>
<script>export default {
  data() { return {items: [], settings: {autoRefresh: false}}; },
  watch: {settings: {handler(v) {}, deep: true}},
  mounted() { this.initData(); this.start(); if (this.settings.autoRefresh) { this.refresh(); } this.notify('ready'); },
  methods: {
    initData() { this.seed(); this.load(); }, seed() {}, load() {}, start() {}, refresh() {},
    choose(item) { this.notify(`Selected ${item.title}`); }, notify(message) {}
  }
}</script>'''
    code = '''<template><div><item-card s-for="item, index in items" on-click="choose"></item-card></div></template>
<script>const san = require('san');
const child = san.defineComponent({template: `<div></div>`, attached() {this.childStart();}, childStart() {}});
module.exports = san.defineComponent({
  components: {'item-card': child},
  initData() {return {items: [], settings: {autoRefresh: false}};},
  inited() { this.watch('settings', v => {}); this.seed(); this.load(); this.start(); },
  attached() { if (this.data.get('settings').autoRefresh) {this.refresh();} this.notify('ready'); },
  seed() {}, load() {}, start() {}, refresh() {}, notify(message) {},
  choose(e) {const list = this.data.get('items'); const item = list[e.index]; this.notify(`Selected ${item.title}`);}
});</script><style></style>'''
    ssm = {'script': {'options': {'data': [{'name': 'items'}, {'name': 'settings'}]}}}
    return code, vue, ssm


class SourcePhaseSemanticsTests(unittest.TestCase):
    def repair(self, code=None, vue=None):
        default_code, default_vue, ssm = fixtures()
        return inspect_semantics(default_code if code is None else code,
                                 default_vue if vue is None else vue, repair=True, ssm=ssm)

    def test_repairs_both_sides_and_moves_only_proven_suffix(self):
        result = self.repair()
        self.assertNotIn('error', result)
        self.assertEqual(set(result['changes']), {
            'restored_source_loop_payload_handler', 'restored_source_mounted_phase_order'})
        self.assertIn('on-click="choose(item)"', result['code'])
        self.assertIn('choose(item)', result['code'])
        self.assertNotIn('list[e.index]', result['code'])
        self.assertIn("this.watch('settings', v => {});", result['code'])
        self.assertIn('attached() {this.childStart();}', result['code'])
        self.assertTrue(check_san_compile(result['code']).passed)
        self.assertEqual(self.repair(code=result['code'])['code'], result['code'])

    def test_installed_san_listener_receives_loop_item_not_empty_child_payload(self):
        fixed = self.repair()['code']
        script = fixed.split('<script>')[1].split('</script>')[0]
        js = r'''const fs=require('fs'),san=require('san');
const listener=require('san/src/view/get-event-listener');
const Data=require('san/src/runtime/data');
const m={exports:{}}; new Function('require','module',fs.readFileSync(0,'utf8'))(require,m);
const component=new m.exports(); const calls=[];
component.notify=x=>calls.push(x);
const event=san.parseTemplate('<item-card on-click="choose(item)"></item-card>').children[0].events[0];
listener(event,component,new Data({item:{title:'actual'}}),true)();
process.stdout.write(JSON.stringify(calls));'''
        result = subprocess.run(['node', '-e', js], input=script, text=True, encoding='utf-8', capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ['Selected actual'])

    def test_hook_order_runtime_watch_registration_stays_early(self):
        fixed = self.repair()['code']
        script = fixed.split('<script>')[1].split('</script>')[0]
        # Capture the actual defineComponent options without starting real timers.
        js = r'''const fs=require('fs'),objects=[];
const m={exports:{}}; const san={defineComponent(o){objects.push(o);return o;}};
new Function('require','module',fs.readFileSync(0,'utf8'))(name=>san,m);
const p=m.exports,calls=[],ctx={data:{get:()=>({autoRefresh:true})},watch:()=>calls.push('watch')};
for(const name of ['seed','load','start','refresh','notify'])ctx[name]=()=>calls.push(name);
p.inited.call(ctx); const early=calls.slice(); p.attached.call(ctx);
process.stdout.write(JSON.stringify({early,all:calls}));'''
        result = subprocess.run(['node', '-e', js], input=script, text=True, encoding='utf-8', capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'early': ['watch'], 'all': ['watch','seed','load','start','refresh','notify']})

    def test_payload_refuses_extra_effects_wrong_loop_ambiguous_binding_or_source(self):
        code, vue, _ = fixtures()
        cases = [code.replace('list[e.index]', 'list[e.other]'),
                 code.replace('this.notify(`Selected ${item.title}`);}', 'this.erase(); this.notify(`Selected ${item.title}`);}'),
                 code.replace('item, index in items', 'item, index in other'),
                 code.replace('</div></template>', '<item-card s-for="item in items" on-click="choose"></item-card></div></template>'),
                 code.replace('on-click="choose"', 'on-click="choose(other)"')]
        for candidate in cases:
            with self.subTest(candidate=candidate):
                fixed = self.repair(code=candidate)
                self.assertNotIn('restored_source_loop_payload_handler', fixed['changes'])
        self.assertNotIn('restored_source_loop_payload_handler', self.repair(vue=vue.replace('choose(item)"','choose(index)"'))['changes'])
        self.assertEqual(self.repair(vue='')['code'], code)

    def test_hook_refuses_reordered_duplicate_or_unknown_actions(self):
        code, vue, _ = fixtures()
        cases = [code.replace('this.seed(); this.load();', 'this.load(); this.seed();'),
                 code.replace('this.seed(); this.load();', 'this.seed(); this.seed(); this.load();'),
                 code.replace('this.seed(); this.load();', 'this.erase(); this.seed(); this.load();'),
                 code.replace("this.notify('ready');", "this.notify('changed');"),
                 code.replace("this.watch('settings', v => {});", "this.watch('settings', v => {}, {immediate:true});")]
        for candidate in cases:
            with self.subTest(candidate=candidate):
                self.assertNotIn('restored_source_mounted_phase_order', self.repair(code=candidate)['changes'])
        for changed in (vue.replace('mounted() {', 'created() {}, mounted() {'),
                        vue.replace('this.seed(); this.load();', 'this.seed(); this.load(); return 1;'),
                        vue.replace('export default {', 'export default {mixins: [other],')):
            self.assertNotIn('restored_source_mounted_phase_order', self.repair(vue=changed)['changes'])

    def test_source_parse_failure_is_fail_closed(self):
        code, _, _ = fixtures()
        self.assertEqual(self.repair(vue='<template><div></template><script>bad</script>')['code'], code)

    def test_missing_hook_mapping_uses_focused_route_with_source_evidence(self):
        prompt = build_repair_prompt(RepairPromptInput(current_code=fixtures()[0], ssm={},
            validation_errors=[{'code': 'missing_lifecycle_mapping'}]))
        self.assertTrue(prompt.startswith('You are repairing a standalone San'))
        self.assertIn('watcher side effects', prompt)
        self.assertIn('$event.index', prompt)

    def test_actual_frozen_failure_both_repairs_apply_without_touching_children(self):
        state = json.loads((SNAPSHOT / 'repair_reports/complex/MonitoringDashboard_repair_history.json').read_text(encoding='utf-8'))['state']
        vue = (SNAPSHOT / 'protocol/frozen/data/datasets/components/03_complex/MonitoringDashboard/vue/MonitoringDashboard.vue').read_text(encoding='utf-8')
        code = state['generated_code']
        fixed = inspect_semantics(code, vue, repair=True, ssm=state['ssm'])
        self.assertNotIn('error', fixed)
        self.assertEqual(set(fixed['changes']), {'restored_source_loop_payload_handler',
            'restored_source_mounted_phase_order', 'restored_source_watch_persistence'})
        self.assertEqual(code.split('module.exports')[0].split('<script>')[1],
                         fixed['code'].split('module.exports')[0].split('<script>')[1])
        self.assertTrue(check_san_compile(fixed['code']).passed)
        self.assertEqual(inspect_semantics(fixed['code'], vue, repair=True, ssm=state['ssm'])['code'], fixed['code'])

    def watch_case(self):
        code, vue, ssm = fixtures()
        vue = vue.replace('handler(v) {}', '''handler(v) {
            if (v.autoRefresh) {this.refresh();}
            localStorage.setItem('preferences', JSON.stringify(v));
        }''')
        code = code.replace("v => {}", 'v => {if (v.autoRefresh) {this.refresh();}}')
        return code, vue, ssm

    def test_source_watch_write_is_diagnosed_repaired_and_idempotent(self):
        code, vue, ssm = self.watch_case()
        before = inspect_semantics(code, vue, ssm=ssm)
        self.assertEqual(before['code'], code)
        self.assertIn('source_watch_persistence_not_landed', [f['code'] for f in before['findings']])
        fixed = inspect_semantics(code, vue, repair=True, ssm=ssm)
        self.assertIn('restored_source_watch_persistence', fixed['changes'])
        self.assertIn("localStorage.setItem('preferences', JSON.stringify(v));", fixed['code'])
        self.assertEqual(inspect_semantics(fixed['code'], vue, ssm=ssm)['findings'], [])
        self.assertEqual(inspect_semantics(fixed['code'], vue, repair=True, ssm=ssm)['code'], fixed['code'])

    def test_watch_unknown_body_existing_write_or_different_parameter_is_not_guessed(self):
        code, vue, ssm = self.watch_case()
        for candidate in (code.replace('v =>', 'other =>'),
                          code.replace('if (v.autoRefresh)', 'if (!v.autoRefresh)'),
                          code.replace('this.refresh();}', "this.refresh();} localStorage.setItem('other', JSON.stringify(v));")):
            self.assertNotIn('restored_source_watch_persistence', inspect_semantics(candidate, vue, repair=True, ssm=ssm)['changes'])
        for source in (vue.replace('JSON.stringify(v)', 'JSON.stringify(external)'),
                       vue.replace('deep: true', 'deep: true, immediate: true'),
                       vue.replace('export default', 'const localStorage = customStorage; export default')):
            self.assertNotIn('restored_source_watch_persistence', inspect_semantics(code, source, repair=True, ssm=ssm)['changes'])

    def test_frozen_source_watch_validation_and_regression_gate_close_loop(self):
        state = json.loads((SNAPSHOT / 'repair_reports/complex/MonitoringDashboard_repair_history.json').read_text(encoding='utf-8'))['state']
        vue = SNAPSHOT / 'protocol/frozen/data/datasets/components/03_complex/MonitoringDashboard/vue/MonitoringDashboard.vue'
        code = state['generated_code']
        fixed = inspect_semantics(code, vue.read_text(encoding='utf-8'), repair=True, ssm=state['ssm'])['code']
        def validate(text):
            return ValidateStage().run(ValidateStageInput(generated_code=text, ssm=state['ssm'], vue_file_path=str(vue)))
        before, after = validate(code), validate(fixed)
        self.assertIn('source_watch_persistence_not_landed', [e['code'] for e in before.validation_errors])
        # A local watcher repair must not hide independent historical child
        # loop-key syntax. Compose the source DOM prepass to close both.
        self.assertFalse(after.validation_passed)
        self.assertEqual([e['code'] for e in after.validation_errors], ['source_dom_loop_not_landed'] * 2)
        combined, rules = RepairStage._deterministic_repair_plan(fixed, after.validation_errors, [],
            state['ssm'], str(vue), enable_residual_v2=True)
        self.assertIn('restored_source_loop_syntax', [rule for _, rule in rules])
        complete = validate(combined)
        self.assertTrue(complete.validation_passed, complete.validation_errors)
        restored = {'generated_code': combined, 'validation_errors': complete.validation_errors, 'ssm': state['ssm'], 'vue_file_path': str(vue)}
        regressed = {**restored, 'generated_code': code, 'validation_errors': before.validation_errors}
        gate = candidate_gate(restored, regressed)
        self.assertTrue(gate['should_stop'])
        self.assertIn('source_watch_persistence_not_landed', [e['code'] for e in gate['introduced_semantic_findings']])

    def test_reordered_attached_calls_are_detected_but_not_blindly_sorted(self):
        code, vue, ssm = fixtures()
        fixed = inspect_semantics(code, vue, repair=True, ssm=ssm)['code']
        bad = fixed.replace('this.seed();\nthis.load();', 'this.load();\nthis.seed();')
        self.assertNotEqual(bad, fixed)
        result = inspect_semantics(bad, vue, repair=True, ssm=ssm)
        self.assertIn('source_mounted_order_not_landed', [f['code'] for f in result['findings']])
        self.assertEqual(result['code'], bad)


if __name__ == '__main__':
    unittest.main()
