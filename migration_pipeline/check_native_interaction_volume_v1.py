"""Read-only bounded native interaction audit. Never launches browser/model or changes scores."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/experiments/analysis/native_interaction_volume_v1_20261115'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise AssertionError(message)


def check_registry(result, count):
    registry = result['nativeRegistry']
    require(result['schemaVersion'] == 4 and registry['complete'], 'Native schema/registry incomplete')
    entries = registry['entries']
    require(len(entries) == count, 'Unexpected native page count')
    for field in ('sessionId', 'contextId', 'targetId', 'page'):
        require(len({e[field] for e in entries}) == count, 'Native identity reused: ' + field)
    require(all(e['identityVerified'] and e['contextDisposed'] for e in entries), 'Unverified or undisposed context')
    require(result['browserProcess']['exitCode'] == 0, 'Browser exit not clean')
    require(not result.get('cleanupErrors'), 'Cleanup failed')
    require(not result['transport']['protocolErrors'] and not result['transport']['blocked'], 'Protocol/network errors')
    require(result['browser']['executableSha256'] == '2497874639116d8edc3de34b3fd83f72fa099112a5d2a426e1f08fcf39a99612', 'Browser pin drift')
    return registry


def check_capture(folder, capture):
    require(capture['status'] == 'captured' and capture['stable'], 'Uncaptured/unstable stage')
    repeat = capture['repeatObservation']
    for key in ('styles', 'domValues', 'extent', 'componentEvidence', 'environment'):
        require(capture[key] == repeat[key], 'Unstable observations: ' + key)
    first = folder / capture['screenshot']
    second = first.with_name(first.stem + '-repeat.png')
    require(digest(first) == capture['screenshotSha256'] == digest(second) == capture['repeatScreenshotSha256'], 'PNG pin/stability mismatch')


def audit_volume(result=None, folder=None):
    folder = Path(folder or BASE / 'volume')
    result = result or read(folder / 'result.json')
    registry = check_registry(result, 4)
    require(not registry['events'] and not registry['integrityErrors'], 'Source/target diagnostic present')
    require(result['status'] == 'evaluated' and result['passed'], 'Visual pilot not passed')
    require(result['thresholds'] == {'pixelTolerance': 0, 'maxChangedPixelRatio': 0, 'minSSIM': 0.999999999}, 'Threshold drift')
    require(result['boundary']['modelCalls'] == 0 and not result['boundary']['productionIntegrated'], 'Authority drift')
    plans = {
        'range': [('initial',45,45,[]),('home_first',0,45,[0]),('end_max',100,100,[0,100]),('home_again',0,100,[0,100,0])],
        'mute': [('initial',45,45,[]),('mute',0,45,[0]),('restore',45,45,[0,45])],
    }
    require(set(result['stages']) == {s+'_'+f for s in plans for f in ('vue','san')}, 'Scene identity drift')
    require(len(result['comparisons']) == 7, 'Expected exactly seven paired visual checkpoints')
    expected_pairs = {(s+'_vue',s+'_san',p[0]) for s,plan in plans.items() for p in plan}
    require({(c['source'],c['target'],c['stage']) for c in result['comparisons']} == expected_pairs, 'Comparison stages drift')
    packaging = read(folder / 'packaging.json')
    input_data = read(folder / 'input.json')
    for entry in registry['entries']:
        page = next(p for p in input_data['pages'] if p['name'] == entry['page'])
        require(hashlib.sha256(page['html'].encode()).hexdigest() == entry['htmlSha256'] == packaging[entry['page']]['htmlSha256'], 'HTML identity mismatch')
        require(all(not m['scriptTransformed'] for m in packaging[entry['page']]['manifest']), 'Business script rewritten')
        require(len(entry['nativeObservations']) == len(page['actions'])+2, 'Step identity observations missing')
        for capture in result['stages'][entry['page']].values():
            require(capture['nativeSessionId'] == entry['sessionId'] and capture['nativeContextId'] == entry['contextId'] and capture['htmlSha256'] == entry['htmlSha256'], 'Stage/native identity mismatch')
    for scene, plan in plans.items():
        for framework in ('vue', 'san'):
            page = scene+'_'+framework
            require(list(result['stages'][page]) == [p[0] for p in plan], 'Stage order drift')
            actions = result['actions'][page]
            require([a['id'] for a in actions] == [p[0] for p in plan[1:]], 'Action order drift')
            require(all(a['status'] == 'executed' and a['driver'] == 'CDP Input' and not a['syntheticDispatchEvent'] for a in actions), 'Actions not native/completed')
            for index,(stage,volume,last,payloads) in enumerate(plan):
                c = result['stages'][page][stage]
                check_capture(folder,c)
                require(c['clean'], 'Dirty capture')
                e = c['componentEvidence']
                label = '已静音' if volume == 0 else str(volume)+'%'
                require(e['fields'] == {'initialVolume':45,'volume':volume,'lastVolume':last,'volumeLabel':label}, 'State value mismatch')
                require(e['emittedEvents'] == [{'name':'change','payload':v,'serializable':True} for v in payloads], 'Event count/order/payload mismatch')
                require(c['domValues']['range']['value'] == str(volume) and c['domValues']['label']['text'] == label, 'Visible DOM state mismatch')
                dom = e['nativeDOMEvents']
                require(all(d['trusted'] is True for d in dom), 'Untrusted DOM input')
                expected_types = ['keydown','input','change','keyup'] * index if scene == 'range' else ['click'] * index
                require([d['type'] for d in dom] == expected_types, 'Native input count/order mismatch')
                if scene == 'range':
                    require([d['key'] for d in dom if d['type'] == 'keydown'] == ['Home','End','Home'][:index], 'Native key order mismatch')
                    require([d['value'] for d in dom if d['type'] == 'input'] == [str(v) for v in payloads], 'Native range input values mismatch')
        for stage,*_ in plan:
            a = result['stages'][scene+'_vue'][stage]['componentEvidence']
            b = result['stages'][scene+'_san'][stage]['componentEvidence']
            for key in ('fields','emittedEvents','nativeDOMEvents'):
                require(a[key] == b[key], 'Paired semantic mismatch: '+key)
    for c in result['comparisons']:
        require(c['eligible'] and c['passed'] and not c['styleChanges'], 'Ineligible visual stage')
        require(c['metrics']['changedPixels'] == 0 and c['metrics']['changedPixelRatio'] == 0 and c['metrics']['ssim'] >= .999999999, 'Pixel mismatch')
    return {'scenarios':2,'component_pairs':1,'native_pages':4,'native_actions':10,'paired_visual_checkpoints':7,
            'state_event_dom_checkpoints':14,'trusted_dom_events_final_total':28,'production_or_semantic_pass':False}


def audit_controls(result=None, folder=None):
    folder = Path(folder or BASE / 'controls')
    result = result or read(folder / 'result.json')
    registry = check_registry(result,10)
    require(result['status'] == 'blocked' and result['passed'] is False, 'Negative controls incorrectly passed')
    require(len(result['comparisons']) == 15, 'Control stage count')
    def comparisons(kind):
        return [c for c in result['comparisons'] if c['source'] == kind+'_source']
    require(all(c['passed'] for c in comparisons('positive')), 'Positive native control failed')
    for side in ('source','target'):
        final = result['stages']['positive_'+side]['second']['componentEvidence']
        require(final == {'fields':{'value':2},'events':[{'trusted':True,'value':1},{'trusted':True,'value':2}]}, 'Native trusted click control failed')
    mismatch = comparisons('mismatch')
    require(mismatch[0]['passed'] and all(c['eligible'] and not c['passed'] and c['metrics']['changedPixels'] > 0 for c in mismatch[1:]), 'Mismatch falsely accepted')
    warning = comparisons('warning')
    require(all(not c['eligible'] and not c['passed'] for c in warning), 'Source warning failed to block')
    require(len(registry['events']) >= 1 and all(e['owner']['page'] == 'warning_source' and e['attribution'] == 'native_session' for e in registry['events']), 'Warning owner ambiguous')
    for kind in ('missing','disabled'):
        cs = comparisons(kind)
        require(cs[0]['passed'] and all(not c['passed'] and not c['eligible'] for c in cs[1:]), 'Unavailable target falsely passed')
        for side in ('source','target'):
            page = kind+'_'+side
            require(result['stages'][page]['initial']['status'] == 'captured', 'Lost initial evidence')
            require(result['stages'][page]['first']['status'] == 'blocked' and result['stages'][page]['second']['status'] == 'not_run', 'Blocked step not retained')
            require([a['status'] for a in result['actions'][page]] == ['blocked','not_run'], 'Action incorrectly executed')
    return {'synthetic_control_pairs':5,'native_pages':10,'expected_positive':1,'expected_negative':4,
            'source_warning_blocks':True,'unavailable_actions_preserve_initial_and_not_run':True,
            'component_migration_evidence':False}


def audit_protected():
    baseline = read(BASE / 'baseline.json')
    for group in ('protected','manual','supplemental_readonly'):
        for path,expected in baseline[group].items():
            require(digest(ROOT/path) == expected,'Protected drift: '+path)
    for pair in baseline['selection']:
        for role in ('source','target'):
            v = pair[role]
            require(digest(ROOT/v['path']) == v['sha256'],'Frozen SFC drift')
    prior = baseline['prior_seal']
    seal = ROOT/prior['path']
    require(digest(seal) == prior['sha256'], 'Prior seal drift')
    for line in seal.read_text(encoding='utf-8').splitlines():
        expected,relative = line.split('  ',1)
        require(digest(seal.parent/relative) == expected,'Prior payload drift: '+relative)
    old_summary = read(ROOT/'data/experiments/batch_reports/formal_30_v4_full_regression_v2_summary.json')['aggregate']
    require({k:old_summary[k] for k in baseline['original_batch']} == baseline['original_batch'], 'Old batch aggregate changed')
    scenario_plan = read(ROOT/'data/experiments/protocols/native_browser_admission_v1_draft_20261115/scenario_plan.json')
    require(len(scenario_plan['source_inventory']) == 30, 'Old source selection changed')
    for row in scenario_plan['source_inventory']:
        require(digest(ROOT/row['source_path']) == row['source_sha256'] == row['historical_source_sha256'] == digest(ROOT/row['historical_source_path']), 'Current/frozen primary Vue drift')
    return {'protected':len(baseline['protected']),'manual':len(baseline['manual']),
            'supplemental':len(baseline['supplemental_readonly']),'frozen_sfc':6,'prior_seal_payloads':prior['payloads'],
            'current_and_frozen_primary_vue_pairs':30,'old_batch':baseline['original_batch']}


def audit():
    return {'status':'bounded_calibration_verified','criteria_adopted_engineering_pending':True,
            'volume':audit_volume(),'controls':audit_controls(),'unchanged':audit_protected(),
            'model_calls':0,'comprehensive_migration_pass':False,
            'source_dynamic_assignment_unproven_still_blocks':True,
            'native_schema4_production_routing_integrated':False}


if __name__ == '__main__':
    print(json.dumps(audit(),ensure_ascii=False,indent=2))
