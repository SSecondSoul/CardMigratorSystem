"""Bounded native text-edit unit checks and saved-evidence checks; no browser/model runs."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeRenamerUnitTests(unittest.TestCase):
    def node(self, body):
        p = subprocess.run(['node', '-e', body], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_three_plans_prepare_unchanged_frozen_scripts(self):
        self.node("const assert=require('assert');const {prepareRenamer}=require('./migration_pipeline/probe_native_interaction_renamer_v1.cjs');const {validate}=require('./migration_pipeline/run_controlled_browser_interaction_v2.cjs');const p=prepareRenamer('not-created');validate(p.input);assert.equal(p.input.pages.length,6);for(const b of Object.values(p.packaging)){assert(b.boundary.businessBodiesUnmodified&&b.boundary.passivePayloadRootIdentity);assert(b.manifest.every(m=>!m.scriptTransformed));}")

    def test_old_click_and_key_supported(self):
        self.node("const a=require('./migration_pipeline/utils/native_interaction_actions_v2.cjs');a.validateActions([{id:'click',op:'click',selector:'button'},{id:'home',op:'key',selector:'input',key:'Home'}]);")

    def test_new_text_action_is_rejected_by_old_version(self):
        self.node("const assert=require('assert');const a=require('./migration_pipeline/utils/native_interaction_actions_v1.cjs');assert.throws(()=>a.validateActions([{id:'edit',op:'replace_text',selector:'input',value:'img'}]));")

    def test_invalid_edits_rejected(self):
        base = {'id':'edit','op':'replace_text','selector':'input','value':'img'}
        for update in [{'value':''},{'value':'x'*81},{'value':'a\nb'},{'value':3},{'code':'script'},{'key':'Home'},{'id':'initial'},{'selector':''}]:
            with self.subTest(update=update):
                self.node("const assert=require('assert');const {validateActions}=require('./migration_pipeline/utils/native_interaction_actions_v2.cjs');assert.throws(()=>validateActions(["+json.dumps({**base,**update})+"]));")

    def test_duplicate_ids_rejected(self):
        self.node("const assert=require('assert');const {validateActions}=require('./migration_pipeline/utils/native_interaction_actions_v2.cjs');assert.throws(()=>validateActions([{id:'x',op:'click',selector:'button'},{id:'x',op:'replace_text',selector:'input',value:'img'}]));")

    def test_native_focus_control_a_and_insert_text(self):
        self.node("""const assert=require('assert');const {executeAction}=require('./migration_pipeline/utils/native_interaction_actions_v2.cjs');(async()=>{let i=0;const calls=[];
        const send=async(m,p,s)=>{calls.push([m,p,s]);return m==='DOM.getDocument'?{root:{nodeId:1}}:m==='DOM.querySelector'?{nodeId:2}:{};};
        const evaluate=async()=>++i===1?{tag:'INPUT',type:'text',x:10,y:10}:i===2?true:'img';
        const r=await executeAction({id:'edit',op:'replace_text',selector:'input',value:'img'},send,evaluate,'session');
        assert(calls.every(c=>c[2]==='session'));assert.equal(calls.at(-1)[0],'Input.insertText');assert.equal(calls.at(-1)[1].text,'img');assert.equal(calls.filter(c=>c[0]==='Input.dispatchKeyEvent').length,4);assert.equal(r.syntheticDispatchEvent,false);})();""")

    def test_failed_native_edit_does_not_force_value(self):
        self.node("""const assert=require('assert');const {executeAction}=require('./migration_pipeline/utils/native_interaction_actions_v2.cjs');(async()=>{let i=0;const send=async m=>m==='DOM.getDocument'?{root:{nodeId:1}}:m==='DOM.querySelector'?{nodeId:2}:{};await assert.rejects(()=>executeAction({id:'edit',op:'replace_text',selector:'input',value:'img'},send,async()=>++i===1?{tag:'INPUT',type:'text'}:i===2?true:'old','s'),/requested DOM value/);})();""")

    def test_numeric_out_of_range_rejected_before_input(self):
        self.node("""const assert=require('assert');const {executeAction}=require('./migration_pipeline/utils/native_interaction_actions_v2.cjs');(async()=>{for(const value of ['0','-1','2.5','1e4','7'])await assert.rejects(()=>executeAction({id:'edit',op:'replace_text',selector:'input',value},async()=>{throw Error('must not send');},async()=>({tag:'INPUT',type:'number',min:'1',max:'5',step:'1'}),'s'),/positive integer/);})();""")

    def test_readonly_target_blocks_before_input(self):
        self.node("""const assert=require('assert');const {executeAction}=require('./migration_pipeline/utils/native_interaction_actions_v2.cjs');(async()=>{await assert.rejects(()=>executeAction({id:'edit',op:'replace_text',selector:'input',value:'img'},async()=>{throw Error('must not send');},async()=>{throw Error('readonly target');},'s'),/readonly/);})();""")

    def test_optional_selector_map_must_be_explicit_and_bounded(self):
        self.node("const assert=require('assert');const {prepareRenamer}=require('./migration_pipeline/probe_native_interaction_renamer_v1.cjs');const {validate}=require('./migration_pipeline/run_controlled_browser_interaction_v2.cjs');const p=prepareRenamer('unused').input;delete p.pages[0].optionalSelectors;assert.throws(()=>validate(p),/optional DOM/);")


class NativeRenamerRecordedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from migration_pipeline import check_native_interaction_renamer_v1 as audit
        cls.audit=audit
        cls.result=audit.read(audit.BASE/'renamer/result.json')

    def altered(self, update):
        import copy
        result=copy.deepcopy(self.result)
        update(result)
        # Keep both observations internally stable: these mutations must be
        # rejected by semantic/identity assertions, not only by repeat drift.
        for stages in result['stages'].values():
            for capture in stages.values():
                for key in ['styles','domValues','domCollections','extent','componentEvidence','environment']:
                    capture['repeatObservation'][key]=copy.deepcopy(capture[key])
        with self.assertRaises(AssertionError): self.audit.audit_renamer(result)

    def test_actual_renamer_states_events_and_pixels(self):
        self.assertEqual(self.audit.audit_renamer(self.result)['paired_visual_checkpoints'],10)

    def test_actual_native_edit_controls(self):
        self.assertEqual(self.audit.audit_controls()['expected_negative'],3)

    def test_old_evidence_and_artifacts_unchanged(self):
        self.assertEqual(self.audit.audit_protected()['protected'],93)

    def test_wrong_start_value_rejected(self):
        self.altered(lambda r:r['stages']['edit_san']['start_three']['componentEvidence']['fields'].update(startAt=1))

    def test_hidden_table_that_remains_present_rejected(self):
        self.altered(lambda r:r['stages']['toggle_san']['hide']['domCollections']['table'].update(count=1))

    def test_wrong_visible_filename_rejected(self):
        self.altered(lambda r:r['stages']['edit_san']['start_three']['domCollections']['new_names'].update(texts=['wrong.png']*3))

    def test_missing_apply_event_rejected(self):
        self.altered(lambda r:r['stages']['apply_san']['apply_names']['componentEvidence'].update(emittedEvents=[]))

    def test_same_array_payload_rejected(self):
        self.altered(lambda r:r['stages']['apply_san']['apply_names']['componentEvidence']['emittedEvents'][0]['payloadIdentity'].update(currentFiles=True))

    def test_untrusted_edit_rejected(self):
        self.altered(lambda r:r['stages']['edit_san']['prefix_img']['componentEvidence']['nativeDOMEvents'][0].update(trusted=False))

    def test_skipped_step_rejected(self):
        self.altered(lambda r:r['actions']['edit_san'][0].update(status='not_run'))

    def test_foreign_step_context_rejected(self):
        self.altered(lambda r:r['stages']['apply_san']['apply_names'].update(nativeContextId='foreign'))

    def test_diagnostic_not_waived_rejected(self):
        self.altered(lambda r:r['nativeRegistry']['events'].append({'kind':'console_warning'}))

    def test_removed_comparison_rejected(self):
        self.altered(lambda r:r['comparisons'].pop())

    def test_pixel_forgery_rejected(self):
        self.altered(lambda r:r['stages']['edit_san']['initial'].update(screenshotSha256='0'*64))

    def test_style_drift_rejected(self):
        self.altered(lambda r:r['comparisons'][0]['styleChanges'].append({'key':'start','property':'rect'}))


if __name__ == '__main__':
    unittest.main()
