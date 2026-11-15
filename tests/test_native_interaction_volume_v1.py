"""Bounded pilot unit contract; no browser/model launched by discovery."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeInteractionUnitTests(unittest.TestCase):
    def node(self, body):
        result = subprocess.run(['node', '-e', body], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_allowed_plans(self):
        self.node("const a=require('./migration_pipeline/utils/native_interaction_actions_v1.cjs');const p=require('./migration_pipeline/probe_native_interaction_volume_v1.cjs');for(const x of Object.values(p.scenarios))a.validateActions(x);")

    def test_reject_unsupported_actions(self):
        cases = [None, [], [{}], [{'id': 'initial', 'op': 'click', 'selector': '#a'}],
                 [{'id': 'a', 'op': 'eval', 'selector': '#a'}],
                 [{'id': 'a', 'op': 'click', 'selector': '#a', 'code': 'danger'}],
                 [{'id': 'a', 'op': 'key', 'selector': '#a', 'key': 'ArrowUp'}],
                 [{'id': 'a', 'op': 'click', 'selector': '#a', 'key': 'Home'}],
                 [{'id': 'a', 'op': 'click', 'selector': ''}],
                 [{'id': 'a', 'op': 'click', 'selector': '#a'}] * 2,
                 [{'id': 'a' + str(i), 'op': 'click', 'selector': '#a'} for i in range(9)]]
        for case in cases:
            with self.subTest(case=case):
                self.node("const assert=require('assert');const {validateActions}=require('./migration_pipeline/utils/native_interaction_actions_v1.cjs');assert.throws(()=>validateActions(" + json.dumps(case) + "));")

    def test_key_uses_native_focus_and_input(self):
        self.node("""const assert=require('assert');const {executeAction}=require('./migration_pipeline/utils/native_interaction_actions_v1.cjs');
        (async()=>{const calls=[];const send=async(m,p,s)=>{calls.push([m,p,s]);return m==='DOM.getDocument'?{root:{nodeId:1}}:m==='DOM.querySelector'?{nodeId:2}:{};};
        const r=await executeAction({id:'home',op:'key',selector:'input',key:'Home'},send,async()=>({tag:'INPUT',type:'range',x:10,y:10}),'native-session');
        assert.deepEqual(calls.map(x=>x[0]),['DOM.getDocument','DOM.querySelector','DOM.focus','Input.dispatchKeyEvent','Input.dispatchKeyEvent']);
        assert(calls.every(x=>x[2]==='native-session'));assert.equal(r.syntheticDispatchEvent,false);})();""")

    def test_button_uses_native_input(self):
        self.node("""const assert=require('assert');const {executeAction}=require('./migration_pipeline/utils/native_interaction_actions_v1.cjs');
        (async()=>{const calls=[];await executeAction({id:'click',op:'click',selector:'button'},async(m,p)=>{calls.push([m,p]);return {};},async()=>({tag:'BUTTON',x:10,y:10}),'s');
        assert.deepEqual(calls.map(x=>x[1].type),['mouseMoved','mousePressed','mouseReleased']);})();""")

    def test_wrong_key_target_blocks(self):
        self.node("""const assert=require('assert');const {executeAction}=require('./migration_pipeline/utils/native_interaction_actions_v1.cjs');
        (async()=>{await assert.rejects(()=>executeAction({id:'home',op:'key',selector:'input',key:'Home'},async()=>{throw Error('must not send');},async()=>({tag:'INPUT',type:'text'}),'s'),/Range keyboard/);})();""")

    def test_action_preflight_failure_never_sends(self):
        self.node("""const assert=require('assert');const {executeAction}=require('./migration_pipeline/utils/native_interaction_actions_v1.cjs');
        (async()=>{await assert.rejects(()=>executeAction({id:'click',op:'click',selector:'button'},async()=>{throw Error('must not send');},async()=>{throw Error('occluded');},'s'),/occluded/);})();""")

    def test_pinned_volume_packaging(self):
        self.node("""const assert=require('assert');const {prepareVolume}=require('./migration_pipeline/probe_native_interaction_volume_v1.cjs');const {validate}=require('./migration_pipeline/run_controlled_browser_interaction_v1.cjs');
        const p=prepareVolume('not-created');validate(p.input);assert.equal(p.input.pages.length,4);for(const b of Object.values(p.packaging)){assert(b.boundary.businessBodiesUnmodified);assert(b.boundary.initializationEventsBeforeListenerNotCovered);assert.equal(b.manifest[0].scriptTransformed,false);}
        p.input.pages[0].actions=[{id:'different',op:'click',selector:'button'}];assert.throws(()=>validate(p.input),/identical/);""")

    def test_adoption_is_not_full_batch_authority(self):
        import hashlib
        record = json.loads((ROOT / 'data/experiments/protocols/native_browser_criteria_adopted_20261115/approval.json').read_text(encoding='utf-8'))
        ref = record['referenced_draft']
        self.assertEqual(hashlib.sha256((ROOT / ref['path']).read_bytes()).hexdigest(), ref['sha256'])
        self.assertFalse(any(record['authority'].values()))
        self.assertTrue(record['approved']['source_oracle']['console_warnings_block'])
        self.assertEqual(record['approved']['native_thresholds']['maxChangedPixelRatio'], 0)


class NativeInteractionRecordedTests(unittest.TestCase):
    """Recheck saved actual native evidence without launching Edge."""
    @classmethod
    def setUpClass(cls):
        from migration_pipeline import check_native_interaction_volume_v1 as audit
        cls.audit = audit
        cls.volume = audit.read(audit.BASE / 'volume/result.json')
        cls.controls = audit.read(audit.BASE / 'controls/result.json')

    def altered_volume(self, update):
        import copy
        result = copy.deepcopy(self.volume)
        update(result)
        with self.assertRaises(AssertionError):
            self.audit.audit_volume(result)

    def test_actual_volume_states_events_and_pixels(self):
        result = self.audit.audit_volume(self.volume)
        self.assertEqual(result['paired_visual_checkpoints'], 7)

    def test_actual_controls_detect_failures(self):
        self.assertEqual(self.audit.audit_controls(self.controls)['expected_negative'], 4)

    def test_protected_history_unchanged(self):
        self.assertEqual(self.audit.audit_protected()['protected'], 84)

    def test_visual_success_does_not_hide_wrong_state(self):
        self.altered_volume(lambda r: r['stages']['range_san']['home_first']['componentEvidence']['fields'].update(volume=45))

    def test_missing_event_is_rejected(self):
        self.altered_volume(lambda r: r['stages']['mute_san']['restore']['componentEvidence'].update(emittedEvents=[]))

    def test_untrusted_event_is_rejected(self):
        self.altered_volume(lambda r: r['stages']['range_vue']['home_first']['componentEvidence']['nativeDOMEvents'][0].update(trusted=False))

    def test_skip_action_is_rejected(self):
        self.altered_volume(lambda r: r['actions']['range_san'][1].update(status='not_run'))

    def test_session_reuse_is_rejected(self):
        self.altered_volume(lambda r: r['nativeRegistry']['entries'][1].update(sessionId=r['nativeRegistry']['entries'][0]['sessionId']))

    def test_source_warning_is_rejected(self):
        self.altered_volume(lambda r: r['nativeRegistry']['events'].append({'kind':'console_warning'}))

    def test_missing_checkpoint_is_rejected(self):
        self.altered_volume(lambda r: r['comparisons'].pop())

    def test_hidden_dom_value_difference_is_rejected(self):
        self.altered_volume(lambda r: r['stages']['range_san']['home_first']['domValues']['range'].update(value='45'))

    def test_changed_png_pin_is_rejected(self):
        self.altered_volume(lambda r: r['stages']['range_san']['initial'].update(screenshotSha256='0'*64))

    def test_zero_pixel_claim_with_style_difference_is_rejected(self):
        self.altered_volume(lambda r: r['comparisons'][0]['styleChanges'].append({'key':'range','property':'rect'}))

    def test_wrong_emission_order_is_rejected(self):
        self.altered_volume(lambda r: r['stages']['range_san']['end_max']['componentEvidence']['emittedEvents'].reverse())

    def test_step_identity_change_is_rejected(self):
        self.altered_volume(lambda r: r['stages']['range_san']['end_max'].update(nativeContextId='foreign-context'))


if __name__ == '__main__':
    unittest.main()
