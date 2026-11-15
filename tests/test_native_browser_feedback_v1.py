"""Synthetic consistency/adversarial controls, not new browser measurements."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from migration_pipeline.utils.native_browser_feedback_v1 import (
    FeedbackEvidenceError, FeedbackNotEligible, NATIVE_STYLE_KEYS, build_repair_preview, convert_recording, sha,
)

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/native_browser_feedback_v1_20261115'
SOURCE='<template><main>source</main></template><script>module.exports={methods:{setValue(k,v){this[k]=v;}}};</script>'
TARGET='<template><main>target</main></template><script>const san=require("san");module.exports=san.defineComponent({setValue(k,v){this.data.set(k,v);}});</script>'


def png(gray):
    def chunk(kind,body):return struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body))
    raw=b''.join(b'\0'+bytes([gray,gray,gray,255])*320 for _ in range(240))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',320,240,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')


def fixture():
    origin='http://127.0.0.1:12345';run='00000000-0000-4000-8000-000000000001'
    pages,captures,bindings,images,entries,trace=[],{},{},{},[],[]
    def command(method,session=None):
        index=len(trace)//2+1
        trace.extend([{'phase':'send','id':index,'method':method,'sessionId':session},{'phase':'response','id':index,'error':None}])
    command('Browser.getVersion')
    for index,(name,framework,gray,code) in enumerate([('source','vue',100,SOURCE),('target','san',110,TARGET)]):
        url=origin+'/page/'+str(index);html='<main style="background:rgb({0},{0},{0})">fixture</main>'.format(gray);image=png(gray)
        pages.append({'name':name,'html':html,'selectors':{'root':'main'}})
        context,target,session,frame='context-'+name,'target-'+name,'session-'+name,'frame-'+name
        observation={'styles':{'root':{'rect':{'x':0,'y':0,'width':320,'height':80},'background-color':'rgb({0}, {0}, {0})'.format(gray)}},'extent':{'width':320,'height':240},'componentEvidence':None,'environment':{'width':320,'height':240,'dpr':1,'theme':True,'reducedMotion':True,'locale':'zh-CN','timezone':'Asia/Shanghai','time':1794700800000}}
        observation['styles']['root']={**{k:'fixture' for k in NATIVE_STYLE_KEYS-{'rect'}},**observation['styles']['root']}
        captures[name]={**deepcopy(observation),'repeatObservation':deepcopy(observation),'status':'captured','clean':True,'stable':True,'htmlSha256':sha(html.encode()),'screenshotSha256':sha(image),'repeatScreenshotSha256':sha(image),'nativeSessionId':session,'nativeContextId':context}
        bindings[name]={'htmlSha256':sha(html.encode()),'boundary':{'framework':framework},'input':{'sha256':sha(code.encode())},'props':{},'moduleManifest':[{'id':name+'.fixture','sha256':sha(code.encode())}]}
        images[name+'.png']=image;images[name+'-repeat.png']=image
        native={'targetInfo':{'type':'page','targetId':target,'browserContextId':context,'url':url},'mainFrame':{'id':frame,'url':url,'securityOrigin':origin}}
        entries.append({'runId':run,'index':index,'page':name,'url':url,'htmlSha256':sha(html.encode()),'contextId':context,'targetId':target,'sessionId':session,'mainFrameId':frame,
            'executionContexts':[{'id':1,'origin':origin,'frameId':frame,'isDefault':True}],
            'nativeObservations':[deepcopy(native),deepcopy(native)],'identityVerified':True,'contextDisposed':True,'lifecycle':'disposed','roles':[{'pair':0,'role':name}]})
        for method in ['Target.createBrowserContext','Target.createTarget','Target.attachToTarget','Target.getTargetInfo','Target.getTargetInfo']:
            command(method)
        command('Runtime.enable',session);command('Page.getFrameTree',session);command('Page.getFrameTree',session)
        command('Target.closeTarget');command('Target.disposeBrowserContext')
    command('Browser.close')
    threshold={'pixelTolerance':0,'maxChangedPixelRatio':0,'minSSIM':.999999999};pair={'source':'source','target':'target'}
    metric={'width':320,'height':240,'totalPixels':76800,'changedPixels':76800,'changedPixelRatio':1,'rgbMeanAbsoluteError':10,'maxChannelDelta':10,'ssim':(22000+6.5025)/(22100+6.5025)}
    return {'payload':{'pages':pages,'pairs':[pair],'thresholds':threshold,'viewport':{'width':320,'height':240},'capturePolicy':'viewport'},
        'result':{'schemaVersion':3,'environment':{'width':320,'height':240,'deviceScaleFactor':1,'locale':'zh-CN','timezone':'Asia/Shanghai','theme':'light','reducedMotion':'reduce','epoch':1794700800000,'seed':1729,'scrollbarGutter':'stable','maxPixels':4000000,'capturePolicy':'viewport','viewportOnly':True},'status':'evaluated','passed':False,'captures':captures,'comparisons':[{**pair,'metrics':metric,'eligible':True,'passed':False,'styleChanges':[]}],'thresholds':threshold,
            'nativeRegistry':{'runId':run,'origin':origin,'entries':entries,'events':[],'integrityErrors':[],'complete':True,'identitiesComplete':True,'isolationPolicy':'fresh_browser_context_per_page','storagePersistedAcrossPages':False},
            'exceptions':[],'consoleErrors':[],'transport':{'protocolErrors':[],'blocked':[],'requests':[{'method':'GET','path':'/page/0'},{'method':'GET','path':'/page/1'}]},'browserProcess':{'exitCode':0,'signalCode':None,'protocolTrace':trace}},
        'bindings':{'pages':bindings},'images':images}


class NativeRoutingTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='cardmig-native-feedback-unit-');self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.data=fixture()

    def write(self):
        folder=self.root/'run';folder.mkdir(exist_ok=True)
        for name,key in [('input.json','payload'),('result.json','result')]:
            (folder/name).write_text(json.dumps(self.data[key]),encoding='utf-8')
        (self.root/'bindings.json').write_text(json.dumps(self.data['bindings']),encoding='utf-8')
        for name,image in self.data['images'].items():(folder/name).write_bytes(image)
        self.reseal()

    def reseal(self):
        rows=[sha(p.read_bytes())+'  '+p.relative_to(self.root).as_posix() for p in sorted(self.root.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt']
        (self.root/'SHA256SUMS.txt').write_text('\n'.join(rows)+'\n',encoding='utf-8')
        self.pin=sha((self.root/'SHA256SUMS.txt').read_bytes())
        self.ref={'bundle_directory':self.root,'expected_seal_sha256':self.pin,'manifest_relative':'bindings.json'}

    def convert(self):
        self.write();return convert_recording(self.root,self.pin,'run',self.ref)

    def scene(self):return self.convert()['scenes'][0]

    def state(self):
        return {'vue_source':SOURCE,'generated_code':TARGET,'ssm':{},'validation_errors':[{'code':'source_dynamic_assignment_unproven','message':'retain arbitrary public key contract','location':'script.methods.setValue'}]}

    def preview(self,state=None):
        return build_repair_preview(self.state() if state is None else state,bundle_directory=self.root,expected_seal_sha256=self.pin,recording_relative='run',binding_reference=self.ref,scene_index=0)

    def event(self,side='source',kind='console_error'):
        entry=self.data['result']['nativeRegistry']['entries'][0 if side=='source' else 1]
        events=self.data['result']['nativeRegistry']['events']
        owner={k:entry[k] for k in ['runId','page','index','targetId','contextId','sessionId']}
        e={'sequence':len(events)+1,'kind':kind,'sessionId':entry['sessionId'],'owner':owner,'attribution':'native_session','reasons':[],
           'details':{'type':'error','executionContextId':1,'args':[{'value':'San failed' if side=='source' else 'Vue warning'}]}}
        events.append(e)
        self.data['result']['exceptions' if kind=='runtime_exception' else 'consoleErrors'].append(e)
        self.data['result']['captures'][side]['clean']=False
        return e

    def review(self):self.assertEqual(self.scene()['recommended_action'],'review_evaluator_or_evidence')
    def reject(self):
        with self.assertRaises(FeedbackEvidenceError):self.convert()

    def test_target_visual_difference_is_offline_candidate(self):
        s=self.scene();self.assertEqual(s['recommended_action'],'review_target_candidate');self.assertTrue(s['target_feedback_eligible']);self.assertFalse(s['repair_dispatch_allowed'])
    def test_native_source_event_needs_no_stack_url(self):
        self.event();self.assertEqual(self.scene()['recommended_action'],'review_source_oracle')
    def test_misleading_vue_text_stays_native_target(self):
        self.event('target');s=self.scene();self.assertIn('target_runtime',{i['channel'] for i in s['issues']});self.assertTrue(s['target_feedback_eligible'])
    def test_both_native_origins_retained_source_review_first(self):
        self.event();self.event('target');s=self.scene();self.assertEqual(s['recommended_action'],'review_source_oracle');self.assertTrue({'source_oracle','target_runtime'}.issubset({i['channel'] for i in s['issues']}))
    def test_unknown_session_not_assigned_from_stack(self):
        e=self.event();e['sessionId']='unknown';e['details']['stackTrace']={'callFrames':[{'url':'http://127.0.0.1:12345/page/0'}]};self.review()
    def test_forged_owner_is_not_authority(self):
        e=self.event();e['owner']['page']='target';self.review()
    def test_wrong_execution_context_blocks(self):
        self.event()['details']['executionContextId']=77;self.review()
    def test_boolean_execution_context_is_not_native_id(self):
        self.event()['details']['executionContextId']=True;self.review()
    def test_foreign_stack_port_blocks(self):
        self.event()['details']['stackTrace']={'callFrames':[{'url':'http://127.0.0.1:12346/page/0'}]};self.review()
    def test_foreign_nested_parent_trace_blocks(self):
        self.event()['details']['stackTrace']={'callFrames':[],'parent':{'callFrames':[{'url':'http://127.0.0.1:12345/page/1'}]}};self.review()
    def test_external_stack_url_blocks(self):
        self.event()['details']['stackTrace']={'callFrames':[{'url':'https://example.invalid/page/0'}]};self.review()
    def test_exception_nested_stack_is_checked(self):
        self.event(kind='runtime_exception')['details']['exception']={'stackTrace':{'callFrames':[{'url':'http://127.0.0.1:12345/page/1'}]}};self.review()
    def test_log_url_is_checked(self):
        self.event(kind='browser_log')['details']['log']={'url':'http://127.0.0.1:12345/page/1'};self.review()
    def test_disposal_chronology_concern_never_cleared(self):
        self.event()['reasons']=['event_after_context_disposal'];self.review()
    def test_false_stored_attribution_never_silently_cleared(self):
        self.event()['attribution']='unverified';self.review()
    def test_dropped_diagnostic_copy_rejected(self):
        self.event();self.data['result']['consoleErrors']=[];self.reject()
    def test_inserted_diagnostic_copy_rejected(self):
        self.event();self.data['result']['consoleErrors'].append({'details':{}});self.reject()
    def test_missing_sequence_rejected(self):
        self.event()['sequence']=2;self.reject()
    def test_duplicate_sequence_rejected(self):
        self.event();self.event('target')['sequence']=1;self.reject()
    def test_malformed_stack_rejected(self):
        self.event()['details']['stackTrace']={'callFrames':'wrong'};self.reject()
    def test_shared_context_rejected(self):
        entries=self.data['result']['nativeRegistry']['entries'];entries[1]['contextId']=entries[0]['contextId'];self.reject()
    def test_shared_session_rejected(self):
        entries=self.data['result']['nativeRegistry']['entries'];entries[1]['sessionId']=entries[0]['sessionId'];self.reject()
    def test_shared_target_rejected(self):
        entries=self.data['result']['nativeRegistry']['entries'];entries[1]['targetId']=entries[0]['targetId'];self.reject()
    def test_wrong_run_identity_rejected(self):
        self.data['result']['nativeRegistry']['entries'][0]['runId']='different';self.reject()
    def test_wrong_actual_origin_rejected(self):
        self.data['result']['nativeRegistry']['origin']='http://127.0.0.1:12346';self.reject()
    def test_out_of_range_port_rejected(self):
        self.data['result']['nativeRegistry']['origin']='http://127.0.0.1:99999';self.reject()
    def test_wrong_page_index_rejected(self):
        self.data['result']['nativeRegistry']['entries'][0]['index']=True;self.reject()
    def test_wrong_roles_rejected(self):
        self.data['result']['nativeRegistry']['entries'][0]['roles']=[{'pair':0,'role':'target'}];self.reject()
    def test_wrong_native_target_response_rejected(self):
        self.data['result']['nativeRegistry']['entries'][0]['nativeObservations'][1]['targetInfo']['targetId']='other';self.reject()
    def test_wrong_native_context_response_rejected(self):
        self.data['result']['nativeRegistry']['entries'][0]['nativeObservations'][1]['targetInfo']['browserContextId']='other';self.reject()
    def test_wrong_native_frame_response_rejected(self):
        self.data['result']['nativeRegistry']['entries'][0]['nativeObservations'][0]['mainFrame']['securityOrigin']='https://foreign.invalid';self.reject()
    def test_subframe_not_main_rejected(self):
        self.data['result']['nativeRegistry']['entries'][0]['nativeObservations'][0]['mainFrame']['parentId']='parent';self.reject()
    def test_missing_double_observation_blocks(self):
        self.data['result']['nativeRegistry']['entries'][0]['nativeObservations'].pop();self.review()
    def test_forged_complete_flags_cannot_restore_disposal(self):
        self.data['result']['nativeRegistry']['entries'][0]['contextDisposed']=False;self.review()
    def test_forged_complete_flags_cannot_restore_context(self):
        self.data['result']['nativeRegistry']['entries'][0]['executionContexts']=[];self.review()
    def test_missing_registry_blocks(self):
        del self.data['result']['nativeRegistry'];self.data['result']['captures']={};self.review()
    def test_missing_dispose_response_blocks(self):
        rows=self.data['result']['browserProcess']['protocolTrace'];call=next(r['id'] for r in rows if r.get('method')=='Target.disposeBrowserContext');rows[:]=[r for r in rows if not (r['id']==call and r['phase']=='response')];self.review()
    def test_dispose_response_error_blocks(self):
        rows=self.data['result']['browserProcess']['protocolTrace'];call=next(r['id'] for r in rows if r.get('method')=='Target.disposeBrowserContext');next(r for r in rows if r['id']==call and r['phase']=='response')['error']={'message':'failed'};self.review()
    def test_duplicate_trace_identity_rejected(self):
        rows=self.data['result']['browserProcess']['protocolTrace'];rows.append(deepcopy(rows[0]));self.reject()
    def test_unknown_trace_session_blocks(self):
        next(r for r in self.data['result']['browserProcess']['protocolTrace'] if r.get('method')=='Runtime.enable')['sessionId']='unknown';self.review()
    def test_browser_crash_blocks(self):
        self.data['result']['browserProcess']['exitCode']=1;self.review()
    def test_boolean_browser_exit_code_not_accepted(self):
        self.data['result']['browserProcess']['exitCode']=False;self.review()
    def test_cleanup_error_blocks(self):
        self.data['result']['cleanupErrors']=['task profile remains'];self.review()
    def test_unexpected_http_request_blocks(self):
        self.data['result']['transport']['requests'].append({'method':'GET','path':'/other'});self.review()
    def test_missing_native_document_request_blocks(self):
        self.data['result']['transport']['requests']=[];self.review()
    def test_storage_policy_cannot_be_weakened(self):
        self.data['result']['nativeRegistry']['storagePersistedAcrossPages']=True;self.review()
    def test_capture_session_mismatch_rejected(self):
        self.data['result']['captures']['target']['nativeSessionId']='session-source';self.reject()
    def test_capture_html_mismatch_rejected(self):
        self.data['result']['captures']['target']['htmlSha256']='0'*64;self.reject()
    def test_manifest_html_mismatch_rejected(self):
        self.data['bindings']['pages']['target']['htmlSha256']='0'*64;self.reject()
    def test_forged_clean_flag_keeps_source_diagnostic(self):
        self.event();self.data['result']['captures']['source']['clean']=True;s=self.scene();self.assertEqual(s['recommended_action'],'review_evaluator_or_evidence');self.assertIn('source_oracle',{i['channel'] for i in s['issues']})
    def test_forged_stable_flag_cannot_clear_repeat_difference(self):
        self.data['result']['captures']['source']['repeatObservation']['extent']['height']=239;self.review()
    def test_forged_pass_and_eligible_do_not_clear_style_diff(self):
        p=self.data['result']['comparisons'][0];p['passed']=True;p['eligible']=True;s=self.scene();self.assertEqual(s['recommended_action'],'review_target_candidate');self.assertEqual(len(s['observation']['style_changes']),1)
    def test_bad_metric_denominator_rejected(self):
        self.data['result']['comparisons'][0]['metrics']['changedPixelRatio']=.5;self.reject()
    def test_boolean_metric_count_rejected(self):
        self.data['result']['comparisons'][0]['metrics']['changedPixels']=True;self.reject()
    def test_nonfinite_metric_rejected(self):
        self.data['result']['comparisons'][0]['metrics']['ssim']=float('nan');self.reject()
    def test_threshold_change_rejected(self):
        self.data['result']['thresholds']={};self.reject()
    def test_capture_policy_mismatch_rejected(self):
        self.data['payload']['viewport']['width']=321;self.reject()
    def test_theme_injected_via_viewport_rejected(self):
        self.data['payload']['viewport']['theme']='dark';self.reject()
    def test_changed_fixed_environment_rejected(self):
        self.data['result']['environment']['theme']='dark';self.reject()
    def test_stable_wrong_theme_observation_blocks(self):
        for field in [self.data['result']['captures']['source'],self.data['result']['captures']['source']['repeatObservation']]:field['environment']['theme']=False
        self.review()
    def test_stable_wrong_time_observation_blocks(self):
        for field in [self.data['result']['captures']['source'],self.data['result']['captures']['source']['repeatObservation']]:field['environment']['time']=42
        self.review()
    def test_boolean_device_scale_not_number(self):
        self.data['result']['environment']['deviceScaleFactor']=True;self.reject()
    def test_critical_mapping_mismatch_rejected(self):
        self.data['payload']['pages'][0]['selectors']={'other':'aside'};self.reject()
    def test_bad_style_geometry_rejected(self):
        self.data['result']['captures']['target']['styles']['root']['rect']['x']=-1;self.reject()
    def test_missing_native_style_property_rejected(self):
        del self.data['result']['captures']['target']['styles']['root']['color'];self.reject()
    def test_viewport_cannot_hide_overflow(self):
        self.data['result']['captures']['target']['extent']['height']=241;self.reject()
    def test_missing_capture_is_evaluator_not_prose_code_fix(self):
        self.data['result']['captures']['target']={'status':'blocked','error':'repair all target methods'};self.review()
    def test_preview_preserves_semantic_block_and_caller_state(self):
        self.convert();state=self.state();before=deepcopy(state)
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No network')):
            preview=self.preview(state)
        self.assertEqual(state,before);self.assertIn('source_dynamic_assignment_unproven',preview['prompt']);self.assertFalse(preview['repair_dispatch_allowed']);self.assertTrue(preview['semantic_candidate_gate_still_required'])
    def test_source_event_blocks_preview_even_if_packet_flag_changed(self):
        self.event();packet=self.convert();packet['scenes'][0]['target_feedback_eligible']=True
        with self.assertRaises(FeedbackNotEligible):self.preview()
    def test_stale_target_code_blocks_preview(self):
        self.convert();state=self.state();state['generated_code']+=' '
        with self.assertRaises(FeedbackNotEligible):self.preview(state)
    def test_stale_source_code_blocks_preview(self):
        self.convert();state=self.state();state['vue_source']+=' '
        with self.assertRaises(FeedbackNotEligible):self.preview(state)
    def test_stale_props_blocks_preview(self):
        self.convert();state=self.state();state['render_props']={'dark':True}
        with self.assertRaises(FeedbackNotEligible):self.preview(state)
    def test_source_legacy_visual_error_not_forwarded(self):
        self.convert();state=self.state();state['visual_eval_errors']=[{'code':'vue_render_failed'}]
        with self.assertRaises(FeedbackNotEligible):self.preview(state)
    def test_unknown_legacy_visual_error_not_silently_dropped(self):
        self.convert();state=self.state();state['visual_eval_warnings']=[{'code':'unknown'}]
        with self.assertRaises(FeedbackNotEligible):self.preview(state)
    def test_allowed_legacy_target_error_retained(self):
        self.convert();state=self.state();state['visual_eval_errors']=[{'code':'dom_text_similarity_low','message':'legacy target text difference'}]
        self.assertEqual(self.preview(state)['visual_eval_errors'][0],state['visual_eval_errors'][0])
    def test_multimodule_preview_blocks_without_new_caller_contract(self):
        self.data['bindings']['pages']['source']['moduleManifest'].append({'id':'Child.vue','sha256':'a'*64});self.convert()
        with self.assertRaises(FeedbackNotEligible):self.preview()
    def test_no_bindings_means_no_component_preview(self):
        self.write();s=convert_recording(self.root,self.pin,'run')['scenes'][0];self.assertFalse(s['target_feedback_eligible'])
    def test_changed_payload_after_seal_rejected(self):
        self.convert();(self.root/'run/result.json').write_text('{}',encoding='utf-8')
        with self.assertRaises(FeedbackEvidenceError):convert_recording(self.root,self.pin,'run',self.ref)
    def test_wrong_external_recording_pin_rejected(self):
        self.write()
        with self.assertRaises(FeedbackEvidenceError):convert_recording(self.root,'0'*64,'run',self.ref)
    def test_wrong_external_binding_pin_rejected(self):
        self.write();self.ref['expected_seal_sha256']='0'*64
        with self.assertRaises(FeedbackEvidenceError):convert_recording(self.root,self.pin,'run',self.ref)
    def test_unsealed_recording_path_rejected(self):
        self.write()
        with self.assertRaises(FeedbackEvidenceError):convert_recording(self.root,self.pin,'../other',self.ref)
    def test_duplicate_json_key_rejected_even_if_resealed(self):
        self.write();(self.root/'run/result.json').write_text('{"schemaVersion":3,"schemaVersion":3}',encoding='utf-8');self.reseal()
        with self.assertRaises(FeedbackEvidenceError):convert_recording(self.root,self.pin,'run',self.ref)
    def test_legacy_schema_not_silently_downgraded_or_upgraded(self):
        self.data['result']['schemaVersion']=2;self.reject()


class RealPinnedNativeReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        baseline=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'))
        seal=ROOT/baseline['prior_seal']['path'];ref={**baseline['binding_reference'],'bundle_directory':ROOT/baseline['binding_reference']['bundle_directory']}
        cls.packet=convert_recording(seal.parent,baseline['prior_seal']['sha256'],'frozen_components',ref)
        cls.controls=convert_recording(seal.parent,baseline['prior_seal']['sha256'],'controls_verified')
        cls.failed=convert_recording(seal.parent,baseline['prior_seal']['sha256'],'context_smoke')

    def test_five_real_scenes_conservatively_routed(self):
        self.assertEqual([s['recommended_action'] for s in self.packet['scenes']],['visual_match_only']*4+['review_source_oracle'])
    def test_actual_source_diagnostics_native_not_message_inference(self):
        issues=self.packet['scenes'][-1]['issues'];source=[i for i in issues if i['channel']=='source_oracle']
        self.assertEqual(len(source),10);self.assertTrue(all(i['details']['provenance']=='native_session_registry' for i in source));self.assertFalse(any(i['channel']=='target_runtime' for i in issues))
    def test_actual_style_and_dimensions_retained(self):
        obs=self.packet['scenes'][-1]['observation'];self.assertEqual(len(obs['style_changes']),7);self.assertEqual(obs['dimensions'],{'source':[1280,1326],'target':[1280,1625]});self.assertIsNone(obs['metrics'])
    def test_no_real_target_preview_or_pass_certification(self):
        self.assertTrue(all(not s['target_feedback_eligible'] and not s['migration_pass_certified'] for s in self.packet['scenes']))
    def test_control_origin_conflict_blocks_all_not_selectively_hidden(self):
        self.assertTrue(all(s['recommended_action']=='review_evaluator_or_evidence' for s in self.controls['scenes']))
    def test_browser_failure_not_component_fix(self):
        self.assertEqual(self.failed['scenes'][0]['recommended_action'],'review_evaluator_or_evidence')
    def test_schema_and_dispatch_boundary(self):
        self.assertEqual(self.packet['recording_schema'],3);self.assertFalse(self.packet['repair_dispatch_allowed']);self.assertFalse(self.packet['semantic_gate_bypass_allowed']);self.assertEqual(self.packet['model_calls'],0)


if __name__=='__main__':unittest.main()
