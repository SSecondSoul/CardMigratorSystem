"""Source-proven public emit helpers; no model, browser or server."""
import json
from pathlib import Path
import subprocess
import unittest

from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.repair_client import RepairResult

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/experiments/analysis/formal_30_v4_trip_event_interface_v1_input_20261114'
CHANGE = 'restored_source_event_forwarding_interfaces'


def fixture(source=None, target=''):
    source = source or "emitEvent(name,payload){this.$emit(name,payload);},notify(items){this.emitEvent('change',items);},send(items){this.notify(items);}"
    vue = '<template><section></section></template><script>module.exports={data(){return {rows:[]};},methods:{' + source + '}};</script>'
    code = '<template><section></section></template><script>const san=require("san");module.exports=san.defineComponent({initData(){return {rows:[]};},send(items){this.fire("change",items);}' + (',' + target if target else '') + '});</script><style>section{color:red}</style>'
    return code, vue


class SourceEventForwardingInterfaceTests(unittest.TestCase):
    def apply(self, code, vue, repair=True):
        result = inspect_semantics(code, vue, repair=repair)
        self.assertNotIn('error', result, result)
        return result

    def test_restore_two_missing_helpers_without_changing_existing_handler(self):
        code, vue = fixture()
        result = self.apply(code, vue)
        self.assertIn(CHANGE, result['changes'])
        self.assertIn('this.fire(name, payload)', result['code'])
        self.assertIn("this.emitEvent('change', items)", result['code'])
        self.assertIn('send(items){this.fire("change",items);}', result['code'])
        self.assertEqual(result['code'].split('<script>')[0], code.split('<script>')[0])
        self.assertEqual(result['code'].split('</script>')[1], code.split('</script>')[1])

    def test_closed_graph_works_when_source_caller_precedes_leaf(self):
        code, vue = fixture("notify(items){this.emitEvent('change',items);},emitEvent(name,payload){this.$emit(name,payload);},send(items){this.notify(items);}")
        fixed = self.apply(code, vue)['code']
        self.assertNotIn('source_method_interface_not_landed', [f['code'] for f in self.apply(fixed, vue, False)['findings']])

    def test_idempotence_and_readonly_inspection(self):
        code, vue = fixture()
        self.assertEqual(self.apply(code, vue, False)['code'], code)
        fixed = self.apply(code, vue)['code']
        again = self.apply(fixed, vue)
        self.assertEqual(again['code'], fixed)
        self.assertEqual(again['changes'], [])

    def test_renamed_helpers_and_parameters_not_component_specific(self):
        code, vue = fixture("publish(kind,value){this.$emit(kind,value);},relay(data){this.publish('topic',data);},send(items){this.relay(items);}")
        result = self.apply(code, vue)
        self.assertIn('publish(kind, value)', result['code'])
        self.assertIn("this.publish('topic', data)", result['code'])
        self.assertIn(CHANGE, result['changes'])

    def test_effects_returns_async_spread_and_unknown_dependencies_not_copied(self):
        bodies = ["this.rows.push(payload);this.$emit(name,payload);", "return this.$emit(name,payload);",
                  "this.$emit(name,...payload);", "this.$emit(name,payload,1);", "this.$emit(name);",
                  "this.$emit(name,external);", "this.$emit(name,this.rows);", "this.$emit?.(name,payload);",
                  "this.unknown(name,payload);", "if(name)this.$emit(name,payload);", "'use strict';this.$emit(name,payload);"]
        for body in bodies:
            with self.subTest(body=body):
                code, vue = fixture('emitEvent(name,payload){' + body + '}')
                self.assertNotIn(CHANGE, self.apply(code, vue)['changes'])
        code, vue = fixture('async emitEvent(name,payload){this.$emit(name,payload);}')
        self.assertNotIn(CHANGE, self.apply(code, vue)['changes'])

    def test_recursive_forwarders_and_nonstandard_signatures_are_not_guessed(self):
        for methods in ["a(x){this.b(x);},b(x){this.a(x);}",
                        "emitEvent(name,payload=1){this.$emit(name,payload);}",
                        "emitEvent(name,{value}){this.$emit(name,value);}"]:
            code, vue = fixture(methods)
            self.assertNotIn(CHANGE, self.apply(code, vue)['changes'])

    def test_existing_wrong_or_noncallable_leaf_not_overwritten_or_used_by_new_wrapper(self):
        for target in ['emitEvent:0', 'emitEvent(name,payload){this.fire("wrong",payload);}',
                       'emitEvent(name,payload){return this.fire(name,payload);}']:
            code, vue = fixture(target=target)
            self.assertNotIn(CHANGE, self.apply(code, vue)['changes'])

    def test_source_overrides_of_framework_emit_and_target_fire_refused(self):
        code, vue = fixture()
        variants = [(code, vue.replace('methods:{', 'methods:{$emit(a,b){},')),
                    (code.replace('initData()', 'fire(){},initData()'), vue),
                    (code, vue.replace('rows:[]', '$emit:null,rows:[]'))]
        for c, v in variants:
            self.assertNotIn(CHANGE, self.apply(c, v)['changes'])

    def test_unknown_san_binding_mutation_dynamic_target_or_legacy_wrapper_refused(self):
        code, vue = fixture()
        variants = [code.replace('require("san")', 'require("other")'),
                    code.replace('module.exports=', 'san.defineComponent=external;module.exports='),
                    code.replace('send(items){this.fire("change",items);}', 'send(items){this[name](items);}'),
                    code.replace('send(items){this.fire("change",items);}', 'methods:{send(items){}}')]
        for bad in variants:
            self.assertNotIn(CHANGE, self.apply(bad, vue)['changes'])
        self.assertEqual(self.apply(code, '')['code'], code)

    def test_explicit_missing_target_callsite_not_silently_reinterpreted(self):
        code, vue = fixture()
        bad = code.replace('this.fire("change",items)', 'this.notify(items)')
        result = self.apply(bad, vue)
        self.assertNotIn('notify(items) {', result['code'])
        self.assertIn('script.methods.notify', [f['location'] for f in self.apply(result['code'], vue, False)['findings']])

    def test_exact_existing_leaf_allows_only_missing_wrapper(self):
        code, vue = fixture(target='emitEvent(name,payload){this.fire(name,payload);}')
        result = self.apply(code, vue)
        self.assertIn(CHANGE, result['changes'])
        self.assertEqual(result['code'].count('emitEvent(name,payload)'), 1)
        self.assertIn("this.emitEvent('change', items)", result['code'])

    def test_candidate_gate_accepts_restoration_and_rejects_removal(self):
        code, vue = fixture()
        fixed = self.apply(code, vue)['code']
        state = lambda c: {'generated_code': c, 'vue_source': vue, 'ssm': {},
                           'validation_errors': self.apply(c, vue, False)['findings']}
        self.assertFalse(candidate_gate(state(code), state(fixed))['should_stop'])
        self.assertTrue(candidate_gate(state(fixed), state(code))['should_stop'])

    def test_frozen_trip_restores_emit_helpers_and_projection_atomically_not_dynamic_setter(self):
        before = json.loads((BASE / 'baseline.json').read_text(encoding='utf-8'))
        code = (ROOT / before['input']['candidate']['path']).read_text(encoding='utf-8')
        vue = (ROOT / before['input']['vue']['path']).read_text(encoding='utf-8')
        fixed = self.apply(code, vue)['code']
        self.assertIn(CHANGE, self.apply(code, vue)['changes'])
        missing = [f['location'] for f in self.apply(fixed, vue, False)['findings'] if f['code']=='source_method_interface_not_landed']
        self.assertEqual(missing, ['script.methods.setValue'])
        self.assertIn('moveItem(index,delta){', fixed)
        self.assertIn('restored_source_shared_swap_shallow_projection',self.apply(code,vue)['changes'])
        self.assertEqual(self.apply(fixed, vue)['code'], fixed)

    def test_real_repair_prepass_uses_shared_rule_without_llm(self):
        code, vue = fixture()
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Source.vue'
            path.write_text(vue, encoding='utf-8')
            errors = self.apply(code, vue, False)['findings']
            fixed, changes = RepairStage._deterministic_repair_plan(code, errors, [], {}, str(path))
            self.assertIn(('bounded_ast_semantics', CHANGE), changes)
            self.assertNotEqual(fixed, code)

    def test_model_response_postprocessing_uses_same_rule_without_external_request(self):
        code, vue = fixture()
        class Client:
            def repair(self, request):
                return RepairResult(source_file='fixture', ssm={}, code=code,
                    saved_file_path=request.output_file_path, provider='fixture', model='offline', usage={})
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'Source.vue'
            source.write_text(vue, encoding='utf-8')
            result = RepairStage(Client()).run(RepairStageInput(ssm={}, generated_code=code,
                vue_file_path=str(source), output_file_path=str(Path(directory) / 'candidate.san'),
                metadata={'skip_deterministic_prepass': True}))
            self.assertIn(CHANGE, result.raw_response['pipeline_postprocessing'])
            # RepairStage writes a canonical trailing newline when saving.
            self.assertEqual(result.repaired_code, self.apply(code, vue)['code'] + '\n')

    def native_comparison(self, code, vue, event):
        js = r'''
const fs=require('fs'),san=require('san'),{parse}=require('@vue/compiler-sfc');
const x=JSON.parse(fs.readFileSync(0,'utf8')),Vue=require(x.vueRuntime);
const source={exports:{}};Function('module',parse(x.vue).descriptor.script.content)(source);
const target={exports:{}};Function('require','module',/<script>([\s\S]*?)<\/script>/.exec(x.code)[1])(require,target);
const a=new Vue(source.exports),b=new target.exports(),eventsA=[],eventsB=[];
const payload={nested:{value:7}},identities=[];
a.$on(x.event,p=>{eventsA.push(p);identities.push(p===payload);});
b.on(x.event,p=>{eventsB.push(p);identities.push(p===payload);});
const returns=[a.notify(payload),b.notify(payload),a.emitEvent(x.event,payload),b.emitEvent(x.event,payload)];
a.$destroy();b.dispose();
process.stdout.write(JSON.stringify({same:JSON.stringify(eventsA)===JSON.stringify(eventsB),count:eventsA.length,identities,undefinedReturns:returns.every(x=>x===undefined)}));
'''
        proc = subprocess.run(['node', '-e', js], cwd=ROOT, input=json.dumps({'vue':vue,'code':code,'event':event,
            'vueRuntime':str(ROOT/'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js')}),
            capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result=json.loads(proc.stdout)
        self.assertTrue(result['same']);self.assertEqual(result['count'],2)
        self.assertTrue(all(result['identities']));self.assertTrue(result['undefinedReturns'])

    def test_native_vue_and_san_forward_same_event_and_original_payload_identity(self):
        code, vue = fixture()
        self.native_comparison(self.apply(code, vue)['code'], vue, 'change')

    def test_actual_frozen_trip_public_helpers_with_native_vue_and_san(self):
        before=json.loads((BASE / 'baseline.json').read_text(encoding='utf-8'))
        code=(ROOT / before['input']['candidate']['path']).read_text(encoding='utf-8')
        vue=(ROOT / before['input']['vue']['path']).read_text(encoding='utf-8')
        self.native_comparison(self.apply(code, vue)['code'], vue, 'itinerary-change')


if __name__ == '__main__':
    unittest.main()
