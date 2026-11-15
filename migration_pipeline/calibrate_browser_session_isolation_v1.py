"""Explicit local-browser controls; never executed by unit-test discovery."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

STORAGE = r"""
(async()=>{
 const key='cardmig_isolation_probe', phase=sessionStorage.getItem(key+'_phase');
 const database=()=>new Promise((resolve,reject)=>{const q=indexedDB.open(key,1);q.onupgradeneeded=()=>q.result.createObjectStore('items');q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error);});
 const get=async()=>{const db=await database();try{return await new Promise((resolve,reject)=>{const q=db.transaction('items').objectStore('items').get('value');q.onsuccess=()=>resolve(q.result??null);q.onerror=()=>reject(q.error);});}finally{db.close();}};
 if(!phase){
   const empty={local:localStorage.length===0,session:sessionStorage.length===0,cookie:document.cookie==='',indexedDB:(await indexedDB.databases()).length===0,cache:(await caches.keys()).length===0};
   localStorage.setItem(key,'local');document.cookie=key+'=cookie;path=/;SameSite=Strict';
   const db=await database();await new Promise((resolve,reject)=>{const t=db.transaction('items','readwrite');t.objectStore('items').put('indexed','value');t.oncomplete=resolve;t.onerror=()=>reject(t.error);});db.close();
   await (await caches.open(key)).put(location.href,new Response('cached'));
   sessionStorage.setItem(key+'_empty',JSON.stringify(empty));sessionStorage.setItem(key+'_phase','reload');location.reload();return;
 }
 const cache=await caches.open(key),response=await cache.match(location.href);
 const persisted={local:localStorage.getItem(key)==='local',session:phase==='reload',cookie:document.cookie===key+'=cookie',indexedDB:await get()==='indexed',cache:!!response&&(await response.text())==='cached'};
 const evidence={initialEmpty:JSON.parse(sessionStorage.getItem(key+'_empty')),samePageReloadPersisted:persisted};
 window.__componentEvidence=()=>evidence;document.querySelector('main').textContent='storage isolated / reload preserved';window.__visualReady=true;
})().catch(e=>console.error(e));
"""


def page(name, script):
    return {'name': name, 'html': '<!doctype html><meta charset="utf-8"><link rel="icon" href="data:,"><style>body{margin:0}main{width:500px;height:100px;background:#ddeeff}</style><main>native session control</main><script>' + script + '</script>', 'selectors': {'root': 'main'}}


def execute(output_dir):
    output = Path(output_dir).resolve()
    if output.exists():
        raise FileExistsError('Refuse to overwrite browser evidence')
    ready = 'window.__visualReady=true;'
    pages = [page('storage_source', STORAGE), page('storage_target', STORAGE),
             page('source_warning', "console.error('San misleading target wording');" + ready),
             page('clean_peer', ready),
             page('target_warning', "console.warn('Vue misleading source wording');" + ready),
             # connect-src intentionally blocks fetch before CDP Fetch. An image
             # request is allowed by CSP and reaches the per-session route guard.
             page('cross_page', "new Image().src='/page/0';" + ready)]
    pairs = [{'source': 'storage_source', 'target': 'storage_target'},
             {'source': 'source_warning', 'target': 'clean_peer'},
             {'source': 'clean_peer', 'target': 'target_warning'},
             {'source': 'clean_peer', 'target': 'cross_page'}]
    payload = {'outputDir': str(output), 'pages': pages, 'pairs': pairs,
               'viewport': {'width': 640, 'height': 480}, 'capturePolicy': 'viewport',
               'thresholds': {'pixelTolerance': 0, 'maxChangedPixelRatio': 0, 'minSSIM': .999999999}}
    proc = subprocess.run(['node', str(ROOT/'migration_pipeline/run_controlled_browser_pixel_v3.cjs')],
                          cwd=ROOT, input=json.dumps(payload), text=True, encoding='utf-8',
                          capture_output=True, timeout=180)
    if proc.returncode != 2 or proc.stderr:
        raise RuntimeError('Expected negative controls blocked; inspect output: ' + proc.stderr)
    result = json.loads(proc.stdout)
    registry = result['nativeRegistry']
    captures = result['captures']
    entries = registry['entries']
    checks = {
        'native_identities_complete': registry['identitiesComplete'],
        'foreign_document_control_blocks_integrity': not registry['complete'],
        'six_unique_contexts': len({e['contextId'] for e in entries}) == len(entries) == 6,
        'six_unique_sessions': len({e['sessionId'] for e in entries}) == 6,
        'all_identities_verified_and_disposed': all(e['identityVerified'] and e['contextDisposed'] for e in entries),
        'five_stores_initially_empty_each_page': all(all(captures[n]['componentEvidence']['initialEmpty'].values()) for n in ['storage_source', 'storage_target']),
        'five_stores_survive_same_page_reload': all(all(captures[n]['componentEvidence']['samePageReloadPersisted'].values()) for n in ['storage_source', 'storage_target']),
        'isolated_pages_still_pixel_match': result['comparisons'][0]['metrics']['changedPixels']==0 and result['comparisons'][0]['styleChanges']==[],
        'source_text_not_used_to_choose_target': any(e['owner']['page'] == 'source_warning' and e['attribution'] == 'native_session' for e in registry['events']),
        'target_text_not_used_to_choose_source': any(e['owner']['page'] == 'target_warning' and e['attribution'] == 'native_session' for e in registry['events']),
        'clean_peer_not_contaminated_by_other_diagnostics': captures['clean_peer']['clean'],
        'source_and_target_warnings_not_silenced': not captures['source_warning']['clean'] and not captures['target_warning']['clean'],
        'cross_page_loopback_request_blocked': any(e['kind']=='blocked_request' and e['owner']['page']=='cross_page' for e in registry['events']),
        'known_session_foreign_document_is_review': any(e['owner']['page']=='cross_page' and 'foreign_document_url' in e['reasons'] for e in registry['events']),
        'no_production_integration_or_model': result['boundary']['modelCalls']==0 and not result['boundary']['productionIntegrated'],
    }
    (output/'calibration.json').write_text(json.dumps({'checks': checks, 'allPassed': all(checks.values()),
        'syntheticControlsOnly': True, 'browserExitCode': proc.returncode}, ensure_ascii=False, indent=2), encoding='utf-8')
    if not all(checks.values()):
        raise AssertionError('Failed calibration: ' + str([k for k,v in checks.items() if not v]))
    return checks


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    print(json.dumps(execute(parser.parse_args().output_dir), indent=2))
