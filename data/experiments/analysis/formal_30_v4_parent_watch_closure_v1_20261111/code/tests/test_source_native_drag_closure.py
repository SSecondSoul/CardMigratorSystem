"""Source native drag body parity, fail-closed refusals and rollback."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from migration_pipeline.utils.source_native_drag_semantics import source_native_drag_semantics, _run
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.repair_client import RepairResult

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/experiments/analysis/formal_30_v4_source_child_initialization_closure_v1_20261111'
RAW = ROOT / 'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821'


def fixture():
    vue = '''const Item={props:['enabled','position'],template:`<article @dragstart="begin">row</article>`,
methods:{begin(event){if(!this.enabled)return;event.dataTransfer.setData('text/plain',this.position);
event.dataTransfer.effectAllowed='move';this.$emit('chosen',this.position);}}};
export default {components:{Item}};'''
    target = '''const san=require('san');const Item=san.defineComponent({
template:`<article on-dragstart="begin">row</article>`,dataTypes:{enabled:san.DataTypes.bool,position:san.DataTypes.number},
initData(){return {enabled:false,position:0};},begin(){if(!this.data.get('enabled'))return;
const index=this.data.get('position');this.fire('chosen',index);},keep(){return 1;}});
module.exports=san.defineComponent({components:{item:Item}});'''
    return '<template><main/></template><script>'+target+'</script><style>.keep{color:red}</style>', '<template><main/></template><script>'+vue+'</script>'


class SourceNativeDragClosureTests(unittest.TestCase):
    def apply(self, pair, repair=True):
        result = source_native_drag_semantics(*pair, repair=repair)
        self.assertNotIn('error', result, result)
        return result

    def state(self, code, vue):
        return {'generated_code': code, 'vue_source': vue, 'ssm': {},
            'validation_errors': self.apply((code, vue), repair=False)['findings']}

    def test_source_body_restored_without_touching_other_bytes_and_fixedpoint(self):
        code, vue = fixture(); r = self.apply((code, vue))
        self.assertEqual(r['changes'], ['restored_source_native_drag_transfer_contract'])
        self.assertEqual([e['code'] for e in r['findings']], ['source_native_drag_not_landed'])
        self.assertIn('event.dataTransfer.setData', r['code'])
        self.assertIn('event.dataTransfer.effectAllowed', r['code'])
        self.assertIn('keep(){return 1;}', r['code'])
        self.assertEqual(r['code'].split('</script>')[1], code.split('</script>')[1])
        again = self.apply((r['code'], vue))
        self.assertEqual(again['code'], r['code']); self.assertEqual(again['findings'], [])
        self.assertTrue(again['proofs'][0]['landed'])

    def test_non_task_names_and_fields_are_supported(self):
        code, vue = fixture()
        replacements = [('Item', 'Tile'), ('item', 'tile'), ('begin', 'grab'), ('position', 'ordinal'),
            ('enabled', 'canMove'), ('chosen', 'picked'), ('event', 'nativeEvent')]
        for old, new in replacements:
            code, vue = code.replace(old, new), vue.replace(old, new)
        r = self.apply((code, vue)); self.assertTrue(r['changes'])
        self.assertEqual(r['mapped_contracts'], ['script.tile.grab@native-dragstart'])
        self.assertEqual(self.apply((r['code'], vue))['findings'], [])

    def test_partial_transfer_or_effect_recovered_only_in_source_order(self):
        code, vue = fixture()
        for statement in ["native.dataTransfer.setData('text/plain',this.data.get('position'));",
                          "native.dataTransfer.effectAllowed='move';"]:
            partial = code.replace('begin(){', 'begin(native){').replace("this.fire('chosen',index)", statement+"this.fire('chosen',index)")
            self.assertTrue(self.apply((partial, vue))['changes'])

    def test_unknown_effect_wrong_guard_payload_mime_effect_or_order_is_refused(self):
        code, vue = fixture()
        fixed = self.apply((code, vue))['code']
        cases = [code.replace("this.fire('chosen',index)", "this.erase();this.fire('chosen',index)"),
            code.replace("!this.data.get('enabled')", "this.data.get('enabled')"),
            code.replace("this.fire('chosen',index)", "this.fire('different',index)"),
            fixed.replace('"text/plain"', '"text/html"').replace("'text/plain'", "'text/html'"),
            fixed.replace('"move"', '"copy"').replace("'move'", "'copy'"),
            fixed.replace('event.dataTransfer.effectAllowed=', 'event.other.effectAllowed=')]
        for candidate in cases:
            with self.subTest(candidate=candidate):
                self.assertNotEqual(candidate, code)
                self.assertNotEqual(candidate, fixed)
                result = self.apply((candidate, vue))
                self.assertEqual(result['code'], candidate); self.assertTrue(result['findings'])

    def test_inverted_transfer_emit_order_is_not_silently_reordered(self):
        code, vue = fixture(); fixed = self.apply((code, vue))['code']
        # Generate an explicit unexpected early emit rather than depend on quote formatting.
        broken = fixed.replace('event.dataTransfer.setData', "this.fire('extra',1);event.dataTransfer.setData")
        self.assertEqual(self.apply((broken, vue))['code'], broken)
        self.assertTrue(self.apply((broken, vue))['findings'])

    def test_unknown_source_handler_is_not_a_copy_template(self):
        code, vue = fixture()
        for extra in ['this.erase();', 'event.preventDefault();', 'return;']:
            changed = vue.replace("event.dataTransfer.effectAllowed='move';", "event.dataTransfer.effectAllowed='move';"+extra)
            self.assertEqual(self.apply((code, changed))['code'], code)
            self.assertEqual(self.apply((code, changed))['mapped_contracts'], [])

    def test_native_binding_required_and_custom_event_is_not_substituted(self):
        code, vue = fixture()
        for binding in ['on-drag-start="begin"', 'on-dragstart="begin()"', 'on-click="begin"']:
            changed = code.replace('on-dragstart="begin"', binding)
            r = self.apply((changed, vue)); self.assertEqual(r['code'], changed); self.assertTrue(r['findings'])
        explicit = code.replace('on-dragstart="begin"', 'on-dragstart="begin($event)"')
        self.assertTrue(self.apply((explicit, vue))['changes'])

    def test_external_or_dynamic_method_use_refuses_copy(self):
        code, vue = fixture()
        for value in ['this.begin();', 'this[key]();', 'this.fire=custom;']:
            changed = code.replace('keep(){return 1;}', 'keep(){'+value+'return 1;}')
            self.assertEqual(self.apply((changed, vue))['code'], changed)
        extra = code.replace('row</article>', '{{begin()}}</article>')
        self.assertEqual(self.apply((extra, vue))['code'], extra)
        overridden = code.replace('keep(){return 1;}', 'fire(){return 1;},keep(){return 1;}')
        self.assertEqual(self.apply((overridden, vue))['code'], overridden)

    def test_unregistered_escaping_constructor_mixins_and_runtime_replacement_refused(self):
        code, vue = fixture()
        for candidate in [code.replace('components:{item:Item}', 'components:{}'),
            code.replace('module.exports=', 'consume(Item);module.exports='),
            code.replace('initData(){', 'mixins:[],initData(){'),
            code.replace('components:{item:Item}', 'mixins:[],components:{item:Item}'),
            code.replace('const Item=', 'san.defineComponent=other;const Item=')]:
            self.assertEqual(self.apply((candidate, vue))['code'], candidate)

    def test_ambiguous_param_alias_and_unbound_global_event_refused(self):
        code, vue = fixture()
        changed = code.replace('begin(){', "begin(native){const event=this.data.get('position');")
        self.assertEqual(self.apply((changed, vue))['code'], changed)
        fixed = self.apply((code, vue))['code'].replace('begin(event)', 'begin()')
        self.assertEqual(self.apply((fixed, vue))['code'], fixed)

    def test_analysis_failure_no_source_and_readonly_are_nonmutating(self):
        code, vue = fixture()
        self.assertEqual(self.apply((code, vue), repair=False)['code'], code)
        self.assertEqual(source_native_drag_semantics(code, '', repair=True)['code'], code)
        _run.cache_clear()
        with patch('migration_pipeline.utils.source_native_drag_semantics.subprocess.run', side_effect=OSError):
            r = source_native_drag_semantics(code, vue, repair=True)
            self.assertEqual(r['code'], code); self.assertIn('error', r)
        _run.cache_clear()

    def test_gate_accepts_repair_rejects_transfer_regression_and_lost_mapping(self):
        code, vue = fixture(); fixed = self.apply((code, vue))['code']
        before, after = self.state(code, vue), self.state(fixed, vue)
        self.assertFalse(candidate_gate(before, after)['should_stop'])
        self.assertTrue(candidate_gate(after, before)['should_stop'])
        gate = candidate_gate(after, self.state('<template><main/></template>', vue))
        self.assertTrue(gate['should_stop'])
        self.assertEqual(gate['lost_source_native_drag_contracts'], ['script.item.begin@native-dragstart'])

    def test_postprocessing_prepass_and_legacy_boundary(self):
        code, vue = fixture()
        class Client:
            def repair(self, request):
                return RepairResult(code=code, saved_file_path=request.output_file_path,
                    source_file='', ssm={}, provider='stub', model='stub', raw_response={})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'source.vue'; path.write_text(vue, encoding='utf-8')
            expected = self.apply((code, vue))['code']
            legacy, _ = RepairStage._deterministic_repair_plan(code, [], [], {}, str(path))
            self.assertEqual(legacy, code)
            fixed, steps = RepairStage._deterministic_repair_plan(code, [], [], {}, str(path), enable_residual_v2=True)
            self.assertEqual(fixed, expected)
            self.assertIn(('source_native_drag_contracts', 'restored_source_native_drag_transfer_contract'), steps)
            out = RepairStage(Client()).run(RepairStageInput(ssm={}, generated_code=code,
                vue_file_path=str(path), output_file_path=str(Path(folder)/'out.san'),
                metadata={'skip_deterministic_prepass':True, 'semantic_rule_set':'residual_v2'}))
            self.assertEqual(out.repaired_code.rstrip(), expected.rstrip())
            self.assertIn('restored_source_native_drag_transfer_contract', out.raw_response['pipeline_postprocessing'])

    def test_prompt_preserves_native_effects_not_watch_order(self):
        prompt = build_repair_prompt(RepairPromptInput(current_code=fixture()[0], ssm={},
            validation_errors=[{'code':'source_native_drag_not_landed','message':'missing'}]))
        self.assertIn('dataTransfer.setData', prompt)
        self.assertIn('Do not change watch registration', prompt)

    def test_frozen_method_runtime_transfer_emit_and_disabled_guard(self):
        code = (BASE/'TaskManager_source_child_initialization_offline.san').read_text(encoding='utf-8')
        vue = (RAW/'protocol/frozen/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue').read_text(encoding='utf-8')
        fixed = self.apply((code, vue))['code']
        js = r'''const fs=require('fs'),san=require('san'),m={exports:{}};const code=JSON.parse(fs.readFileSync(0,'utf8'));
new Function('require','module',/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(code)[1])(require,m);
const C=m.exports.prototype.components['task-item'],out=[];
for(const enabled of [true,false]){const c=new C({data:{task:{id:1},index:0,draggable:enabled}}),log=[];
c.on('drag-start',value=>log.push(['emit',value]));const e={dataTransfer:{setData(...args){log.push(['setData',...args]);},
set effectAllowed(value){log.push(['effectAllowed',value]);}}};c.onDragStart(e);out.push(log);}
process.stdout.write(JSON.stringify(out));'''
        proc = subprocess.run(['node','-e',js], input=json.dumps(fixed), cwd=ROOT, text=True,
            encoding='utf-8', capture_output=True, timeout=20, check=True)
        self.assertEqual(json.loads(proc.stdout), [[['setData','text/plain',0],['effectAllowed','move'],['emit',0]], []])
        self.assertFalse(proc.stderr.strip())

    def test_frozen_validator_now_reports_missing_native_effects(self):
        code = (BASE/'TaskManager_source_child_initialization_offline.san').read_text(encoding='utf-8')
        vue = RAW/'protocol/frozen/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue'
        ssm = json.loads((RAW/'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']['ssm']
        def assess(text):
            return ValidateStage().run(ValidateStageInput(generated_code=text, ssm=ssm, vue_file_path=str(vue))).to_state_update()
        before = assess(code); fixed = self.apply((code, vue.read_text(encoding='utf-8')))['code']; after = assess(fixed)
        self.assertEqual({e['code'] for e in before['validation_errors']}, {'source_native_drag_not_landed','source_parent_watch_not_landed'})
        self.assertEqual({e['code'] for e in after['validation_errors']}, {'source_parent_watch_not_landed'})
        self.assertFalse(after['validation_passed'])


if __name__ == '__main__':
    unittest.main()
