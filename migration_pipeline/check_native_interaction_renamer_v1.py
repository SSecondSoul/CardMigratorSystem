"""Read-only native BatchRenamer calibration audit; no browser/model or score writes."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/native_interaction_renamer_v1_20261115'
ORIGINAL=['cover.png','hero.png','thumb.png']
RENAMED=['img-3.png','img-4.png','img-5.png']
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,msg):
    if not ok: raise AssertionError(msg)

def registry(result,pages):
    require(result['schemaVersion']==5,'Native schema mismatch')
    r=result['nativeRegistry'];entries=r['entries']
    require(r['complete'] and not r['integrityErrors'] and len(entries)==pages,'Incomplete native registry')
    for key in ['page','contextId','targetId','sessionId']:
        require(len({e[key] for e in entries})==pages,'Reused identity '+key)
    require(all(e['identityVerified'] and e['contextDisposed'] for e in entries),'Identity/disposal incomplete')
    require(result['browserProcess']['exitCode']==0 and not result.get('cleanupErrors'),'Browser exit/cleanup failed')
    require(not result['transport']['blocked'] and not result['transport']['protocolErrors'],'Network/protocol failure')
    require(result['browser']['executableSha256']=='2497874639116d8edc3de34b3fd83f72fa099112a5d2a426e1f08fcf39a99612','Browser drift')
    require(result['thresholds']=={'pixelTolerance':0,'maxChangedPixelRatio':0,'minSSIM':.999999999},'Threshold drift')
    return r

def capture_check(folder,c):
    require(c['status']=='captured' and c['stable'],'Missing/unstable capture')
    for k in ['styles','domValues','domCollections','extent','componentEvidence','environment']:
        require(c[k]==c['repeatObservation'][k],'Repeated observation changed '+k)
    p=(folder/c['screenshot']).resolve()
    require(p.is_relative_to(folder.resolve()),'Unsafe image path')
    require(sha(p)==sha(p.with_name(p.stem+'-repeat.png'))==c['screenshotSha256']==c['repeatScreenshotSha256'],'Image pin/stability mismatch')

def expected_fields(prefix='asset',start=1,visible=True,applied=False):
    current=RENAMED if applied else ORIGINAL
    names=[prefix+'-'+str(start+i)+'.png' for i in range(3)]
    return {'files':ORIGINAL,'currentFiles':current,'prefix':prefix,'startAt':start,'previewVisible':visible,
            'previews':[{'oldName':old,'newName':new} for old,new in zip(current,names)],'hasDuplicates':False}

def audit_renamer(result=None,folder=None):
    folder=Path(folder or BASE/'renamer');result=result or read(folder/'result.json')
    r=registry(result,6)
    require(not r['events'] and result['passed'] and result['status']=='evaluated','Dirty/not-passed real scenes')
    require(result['boundary']['modelCalls']==0 and not result['boundary']['productionIntegrated'],'Authority drift')
    plans={'edit':['initial','prefix_img','start_three'],'toggle':['initial','hide','show'],'apply':['initial','prefix_img','start_three','apply_names']}
    require(set(result['stages'])=={s+'_'+f for s in plans for f in ['vue','san']},'Scene inventory mismatch')
    require(len(result['comparisons'])==10,'Missing/extra comparison')
    require({(c['source'],c['target'],c['stage']) for c in result['comparisons']}=={(s+'_vue',s+'_san',t) for s,p in plans.items() for t in p},'Comparison identity mismatch')
    packaging=read(folder/'packaging.json');inp=read(folder/'input.json')
    for e in r['entries']:
        page=next(p for p in inp['pages'] if p['name']==e['page'])
        require(hashlib.sha256(page['html'].encode()).hexdigest()==e['htmlSha256']==packaging[e['page']]['htmlSha256'],'HTML binding mismatch')
        require(len(e['nativeObservations'])==len(page['actions'])+2,'Stage identity observations missing')
        require(all(not m['scriptTransformed'] for m in packaging[e['page']]['manifest']),'Business script rewritten')
        require(packaging[e['page']]['boundary']['passivePayloadRootIdentity'],'No passive identity observer')
        for c in result['stages'][e['page']].values():
            require(c['nativeSessionId']==e['sessionId'] and c['nativeContextId']==e['contextId'] and c['htmlSha256']==e['htmlSha256'],'Stage/native binding mismatch')
    trusted_total=0
    for scene,plan in plans.items():
        for framework in ['vue','san']:
            page=scene+'_'+framework
            require(list(result['stages'][page])==plan,'Stage order mismatch')
            actions=result['actions'][page]
            require([a['id'] for a in actions]==plan[1:],'Action order mismatch')
            require(all(a['status']=='executed' and a['executed'] and a['driver']=='CDP Input' and not a['syntheticDispatchEvent'] for a in actions),'Incomplete/non-native action')
            for index,stage in enumerate(plan):
                c=result['stages'][page][stage];capture_check(folder,c);require(c['clean'],'Dirty capture')
                prefix='img' if scene!='toggle' and index>=1 else 'asset'
                start=3 if scene!='toggle' and index>=2 else 1
                visible=stage!='hide';applied=stage=='apply_names'
                fields=expected_fields(prefix,start,visible,applied)
                e=c['componentEvidence'];require(e['fields']==fields,'State mismatch '+page+'/'+stage)
                events=[{'name':'apply','payload':RENAMED,'serializable':True,'payloadIdentity':{'currentFiles':False}}] if applied else []
                require(e['emittedEvents']==events,'Apply emission/copy-identity mismatch')
                require(c['domValues']['prefix']['value']==prefix and c['domValues']['start']['value']==str(start),'Visible input mismatch')
                require(c['domValues']['toggle']['text']==('隐藏预览' if visible else '显示预览'),'Toggle text mismatch')
                collections=c['domCollections']
                require(collections['table']['count']==int(visible) and collections['rows']['count']==(3 if visible else 0),'Preview DOM presence mismatch')
                require(collections['old_names']=={'count':3 if visible else 0,'texts':fields['currentFiles'] if visible else []},'Old-name cells mismatch')
                require(collections['new_names']=={'count':3 if visible else 0,'texts':[p['newName'] for p in fields['previews']] if visible else []},'New-name cells mismatch')
                dom=e['nativeDOMEvents'];require(all(d['trusted'] is True for d in dom),'Untrusted input event')
                expected_inputs=[] if scene=='toggle' or index==0 else ['img'] if index==1 else ['img','3']
                require([d['value'] for d in dom if d['type']=='input']==expected_inputs,'Native input values/order mismatch')
                expected_clicks=index if scene=='toggle' else int(applied)
                require(sum(d['type']=='click' for d in dom)==expected_clicks,'Native click count mismatch')
                require(sum(d['type']=='keydown' for d in dom)==len(expected_inputs)*2 and sum(d['type']=='keyup' for d in dom)==len(expected_inputs)*2,'Native keyboard count mismatch')
            trusted_total+=len(result['stages'][page][plan[-1]]['componentEvidence']['nativeDOMEvents'])
        for stage in plan:
            left=result['stages'][scene+'_vue'][stage];right=result['stages'][scene+'_san'][stage]
            for k in ['fields','emittedEvents','nativeDOMEvents']:
                require(left['componentEvidence'][k]==right['componentEvidence'][k],'Paired observation mismatch '+k)
    for c in result['comparisons']:
        require(c['eligible'] and c['passed'] and not c['styleChanges'],'Visual stage ineligible or different')
        require(c['metrics']['changedPixels']==0 and c['metrics']['changedPixelRatio']==0 and c['metrics']['ssim']>=.999999999,'Pixel mismatch')
    return {'components':1,'scenarios':3,'native_pages':6,'native_actions':14,'paired_visual_checkpoints':10,
            'single_side_semantic_checkpoints':20,'trusted_dom_events_final_total':trusted_total,
            'event_payload_distinct_from_current_files_at_emission':True,'comprehensive_migration_pass':False}

def audit_controls(result=None,folder=None):
    folder=Path(folder or BASE/'controls');result=result or read(folder/'result.json');r=registry(result,8)
    require(result['status']=='blocked' and not result['passed'],'Negative control must not pass')
    require(len(result['comparisons'])==12,'Control stage count mismatch')
    def comparisons(kind): return [c for c in result['comparisons'] if c['source']==kind+'_source']
    require(all(c['passed'] for c in comparisons('positive')),'Positive edit failed')
    for side in ['source','target']:
        e=result['stages']['positive_'+side]['replace_again']['componentEvidence']
        require(e=={'fields':{'value':'final'},'events':[{'trusted':True,'value':'img'},{'trusted':True,'value':'final'}]},'Trusted replacement not observed')
    require(comparisons('mismatch')[0]['passed'] and all(c['eligible'] and not c['passed'] and c['metrics']['changedPixels']>0 for c in comparisons('mismatch')[1:]),'Wrong state not detected')
    require(all(not c['eligible'] and not c['passed'] for c in comparisons('warning')),'Source warning not blocked')
    require(r['events'] and all(e['owner']['page']=='warning_source' and e['attribution']=='native_session' for e in r['events']),'Warning owner mismatch')
    require(comparisons('readonly')[0]['passed'],'Readonly initial comparison failed')
    for side in ['source','target']:
        page='readonly_'+side
        require(result['stages'][page]['initial']['status']=='captured','Lost initial evidence')
        require(result['stages'][page]['replace']['status']=='blocked' and result['stages'][page]['replace_again']['status']=='not_run','Readonly action not blocked')
        require([a['status'] for a in result['actions'][page]]==['blocked','not_run'],'Readonly action falsely executed')
    return {'synthetic_control_pairs':4,'native_pages':8,'positive':1,'expected_negative':3,'component_migration_evidence':False}

def audit_protected():
    b=read(BASE/'baseline.json')
    for group in ['protected','manual','supplemental_readonly']:
        for p,h in b[group].items(): require(sha(ROOT/p)==h,'Protected drift '+p)
    for pair in b['selection']:
        for key in ['source','target']: require(sha(ROOT/pair[key]['path'])==pair[key]['sha256'],'Frozen SFC drift')
    prior=b['prior_seal'];seal=ROOT/prior['path'];require(sha(seal)==prior['sha256'],'Prior seal drift')
    lines=seal.read_text(encoding='utf-8').splitlines();require(len(lines)==105,'Prior payload count drift')
    for line in lines:
        h,p=line.split('  ',1);require(sha(seal.parent/p)==h,'Prior payload drift '+p)
    close=b['prior_closeout'];require(sha(ROOT/close['path'])==close['sha256'],'Prior closeout drift')
    aggregate=read(ROOT/'data/experiments/batch_reports/formal_30_v4_full_regression_v2_summary.json')['aggregate']
    require({k:aggregate[k] for k in b['original_batch']}==b['original_batch'],'Old score changed')
    plan=read(ROOT/'data/experiments/protocols/native_browser_admission_v1_draft_20261115/scenario_plan.json')
    for row in plan['source_inventory']:
        require(sha(ROOT/row['source_path'])==row['source_sha256']==row['historical_source_sha256']==sha(ROOT/row['historical_source_path']),'Current/frozen primary source drift')
    return {'protected':len(b['protected']),'manual':len(b['manual']),'supplemental':len(b['supplemental_readonly']),
            'prior_payloads':105,'current_historical_vue_pairs':30,'old_batch':b['original_batch']}

def audit():
    return {'status':'bounded_renamer_calibration_verified','renamer':audit_renamer(),'controls':audit_controls(),
            'unchanged':audit_protected(),'model_calls':0,'new_manual_component_passes':0,'production_ready':False,
            'comprehensive_migration_pass':False,'arbitrary_public_key_contract_preserved':True,
            'analytics_source_warning_still_blocks':True,'schema5_production_dispatch_integrated':False}

if __name__=='__main__': print(json.dumps(audit(),ensure_ascii=False,indent=2))
