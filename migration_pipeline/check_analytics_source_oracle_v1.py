"""Read-only Analytics source-oracle diagnosis; never admits migration or rewrites source."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/analytics_source_oracle_audit_v1_20261115'
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,msg):
    if not ok: raise AssertionError(msg)
def verify_seal(ref):
    seal=ROOT/ref['path'];require(sha(seal)==ref['sha256'],'Prior checksum pin drift')
    lines=seal.read_text(encoding='utf-8').splitlines()
    require(len(lines)==ref['payloads'],'Prior payload count drift')
    for line in lines:
        h,p=line.split('  ',1);target=(seal.parent/p).resolve()
        require(target.is_relative_to(seal.parent.resolve()) and sha(target)==h,'Prior payload drift '+p)
    return seal.parent
def audit_protected():
    b=read(BASE/'baseline.json')
    for group in ['protected','manual','supplemental_readonly']:
        for p,h in b[group].items(): require(sha(ROOT/p)==h,'Protected drift '+p)
    for pair in b['selection']:
        for role in ['source','target']: require(sha(ROOT/pair[role]['path'])==pair[role]['sha256'],'Frozen component drift')
    verify_seal(b['prior_seal']);verify_seal(b['native_recording_seal'])
    ref=b['prior_closeout'];require(sha(ROOT/ref['path'])==ref['sha256'],'Prior closeout drift')
    aggregate=read(ROOT/'data/experiments/batch_reports/formal_30_v4_full_regression_v2_summary.json')['aggregate']
    require({k:aggregate[k] for k in b['original_batch']}==b['original_batch'],'Historical score drift')
    plan=read(ROOT/'data/experiments/protocols/native_browser_admission_v1_draft_20261115/scenario_plan.json')
    require(len(plan['source_inventory'])==30,'Source inventory drift')
    for r in plan['source_inventory']:
        require(sha(ROOT/r['source_path'])==r['source_sha256']==r['historical_source_sha256']==sha(ROOT/r['historical_source_path']),'Current/frozen main Vue drift')
    return {'protected':len(b['protected']),'manual':3,'supplemental':4,'frozen_sfc':6,'prior_payloads':114,'older_native_payloads':96,'source_pairs':30,'old_batch':b['original_batch']}

def audit_native(result=None,folder=None):
    folder=Path(folder or BASE/'native_retry');r=result or read(folder/'result.json');binding=read(folder/'binding.json');inp=read(folder/'input.json')
    require(r['schemaVersion']==3 and r['status']=='blocked' and not r['passed'],'Expected blocked source oracle')
    registry=r['nativeRegistry'];entries=registry['entries'];events=registry['events']
    require(registry['complete'] and not registry['integrityErrors'] and len(entries)==12,'Incomplete native provenance')
    for key in ['page','sessionId','contextId','targetId']:
        require(len({e[key] for e in entries})==12,'Native identity reused')
    require(all(e['identityVerified'] and e['contextDisposed'] and len(e['nativeObservations'])==2 for e in entries),'Native identity/cleanup incomplete')
    require(r['browserProcess']['exitCode']==0 and not r.get('cleanupErrors'),'Browser process failed')
    require(not r['transport']['blocked'] and not r['transport']['protocolErrors'] and not r['exceptions'],'Facility/runtime failure, not source-key diagnosis')
    require(r['thresholds']=={'pixelTolerance':0,'maxChangedPixelRatio':0,'minSSIM':.999999999},'Threshold drift')
    require(r['browser']['executableSha256']=='2497874639116d8edc3de34b3fd83f72fa099112a5d2a426e1f08fcf39a99612','Browser pin drift')
    require(binding['boundary']['namespaceVariantIsMechanismControlNotSourceCorrection'] and not binding['boundary']['productionOrMigrationPass'],'Control boundary drift')
    source='analytics_default_vue';target='analytics_default_san'
    counts={e['page']:[] for e in entries}
    for event in events:
        require(event['attribution']=='native_session','Unknown diagnostic owner')
        owner=next(e for e in entries if e['sessionId']==event['sessionId'])
        require(event['owner']['page']==owner['page'],'Diagnostic owner changed')
        args=event['details'].get('args',[])
        require(len(args)>=3 and args[0].get('value')=='Vue component warning' and 'Duplicate keys detected:' in args[1].get('value','') and 'TrendChart' in args[2].get('value',''),'Unexpected non-key source diagnostic')
        counts[owner['page']].append(args[1]['value'])
    require(len(counts[source])==10 and not counts[target],'Full source diagnostics changed')
    for entry in entries:
        c=r['captures'][entry['page']]
        require(c['status']=='captured' and c['stable'],'Capture incomplete/unstable')
        require(c['nativeSessionId']==entry['sessionId'] and c['nativeContextId']==entry['contextId'],'Capture native identity drift')
        page=next(p for p in inp['pages'] if p['name']==entry['page'])
        require(c['htmlSha256']==entry['htmlSha256']==hashlib.sha256(page['html'].encode()).hexdigest(),'HTML binding drift')
        require(c['clean']==(not counts[entry['page']]),'Diagnostic clean flag mismatch')
        for key in ['styles','extent','componentEvidence','environment']:
            require(c[key]==c['repeatObservation'][key],'Repeat observation drift')
        p=folder/(entry['page']+'.png');require(sha(p)==c['screenshotSha256']==sha(folder/(entry['page']+'-repeat.png'))==c['repeatScreenshotSha256'],'Capture pixel hash drift')
    full=r['captures'][source]['componentEvidence']['keyAudit']
    require(full['gridGroups']==5 and full['pointGroups']==30 and full['duplicateKeys']==[1,2,3,4,5],'Source sibling key overlap not observed')
    grid=[n['key'] for n in full['keyed'] if n['kind']=='grid'];points=[n['key'] for n in full['keyed'] if n['kind']=='point']
    require(grid==list(range(1,6)) and points==list(range(30)),'Source normalized VNode key inventory mismatch')
    require('key:i' in full['compilerRender'] and 'key:idx' in full['compilerRender'],'Compiled key evidence absent')
    old=read(ROOT/'data/experiments/analysis/browser_session_isolation_v1_20261115/frozen_components/result.json')
    for page in [source,target]:
        c=r['captures'][page];prior=old['captures'][page]
        require(c['componentEvidence']['fields']==prior['componentEvidence']['fields'],'Full business observation changed')
        require(c['screenshotSha256']==prior['screenshotSha256'],'Full screenshot changed beyond passive observation')
    first=r['comparisons'][0]
    require(first['source']==source and first['target']==target and not first['eligible'] and not first['passed'] and first['metrics'] is None,'Source wrongly admitted')
    require(first['dimensions']=={'source':[1280,1326],'target':[1280,1625]} and len(first['styleChanges'])==7,'Independent old layout difference lost')
    require(len(r['comparisons'])==6,'Control comparison count drift')
    cases=[]
    for index,n in enumerate([1,2,7,30,90],1):
        a='trend_'+str(n)+'_original';b='trend_'+str(n)+'_namespaced'
        original=r['captures'][a]['componentEvidence']['keyAudit'];fixed=r['captures'][b]['componentEvidence']['keyAudit']
        overlap=list(range(1,min(5,n-1)+1))
        require(original['duplicateKeys']==overlap and fixed['duplicateKeys']==[],'Key mechanism falsified')
        require(original['gridGroups']==fixed['gridGroups']==5 and original['pointGroups']==fixed['pointGroups']==n,'VNode group count changed')
        require(original['domCircles']==fixed['domCircles']==n and original['domGridLines']==fixed['domGridLines']==5,'Control DOM count mismatch')
        require(original['points']==fixed['points'],'Control geometry differs')
        require([x['key'] for x in fixed['keyed'] if x['kind']=='grid']==['grid-'+str(i) for i in range(1,6)],'Grid namespace not observed')
        require([x['key'] for x in fixed['keyed'] if x['kind']=='point']==['point-'+str(i) for i in range(n)],'Point namespace not observed')
        require(len(counts[a])==2*len(overlap) and counts[b]==[],'Native warning count does not match collisions')
        c=r['comparisons'][index]
        require(c['source']==a and c['target']==b and not c['styleChanges'] and c['metrics']['changedPixels']==0,'Mechanism control unexpectedly changes picture')
        require(c['passed']==(n==1) and c['eligible']==(n==1),'Warning waiver or invalid control admission')
        cases.append({'points':n,'overlap_keys':overlap,'original_warnings':len(counts[a]),'namespaced_warnings':0,'visual_changed_pixels':0,'migration_evidence':False})
    require(len(events)==42,'Diagnostic inventory drift')
    return {'source_oracle_status':'blocked_duplicate_sibling_keys','native_pages':12,'native_source_warnings':10,'total_native_diagnostics':42,'key_sites':binding['keySites'],'mechanism_controls':cases,'full_source_and_target_screenshots_unchanged':True,'unresolved_layout_differences':7,'comprehensive_migration_pass':False,'interaction_scenarios_executed':0}

def audit():
    return {'status':'diagnosis_complete_source_oracle_blocked','native':audit_native(),'unchanged':audit_protected(),
            'source_or_target_artifacts_modified':False,'source_correction_authorized':False,'warning_waiver_granted':False,
            'arbitrary_public_key_contract_preserved':True,'production_ready':False,'model_calls':0,'new_manual_component_passes':0}

if __name__=='__main__': print(json.dumps(audit(),ensure_ascii=False,indent=2))
