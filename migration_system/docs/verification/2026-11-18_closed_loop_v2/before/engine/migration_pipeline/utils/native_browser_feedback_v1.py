"""Pinned schema-3 browser evidence -> native-origin feedback, offline review only.

Never downgrade to legacy schema, run a browser/model, mutate caller state, or
grant production dispatch. Recorder observations require a trusted external pin;
checksums are not authentication of arbitrary producers or a hostile-code sandbox.
"""
from copy import deepcopy
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import uuid

from migration_pipeline.utils.browser_feedback_v1 import (
    FeedbackEvidenceError, FeedbackNotEligible, _finite, _issue, _metric_check,
    _pin, _png, sha, verify_seal,
)

NATIVE_STYLE_KEYS = {'rect','display','position','color','background-color','font-family',
    'font-size','font-weight','line-height','padding-top','padding-right','padding-bottom','padding-left',
    'margin-top','margin-right','margin-bottom','margin-left','border-top-width','border-top-color',
    'border-radius','opacity','visibility'}


def _load(text):
    def pairs(rows):
        out = {}
        for key, value in rows:
            if key in out:
                raise FeedbackEvidenceError('Duplicate JSON key: ' + key)
            out[key] = value
        return out

    def reject(value):
        raise FeedbackEvidenceError('Non-finite JSON: ' + value)
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=reject)
    except (TypeError, json.JSONDecodeError) as error:
        raise FeedbackEvidenceError('Invalid JSON evidence') from error


def _reader(root, sealed):
    def read(relative):
        if not isinstance(relative, (str, Path)):
            raise FeedbackEvidenceError('Artifact path must be explicit')
        path = (root / relative).resolve()
        if path not in sealed:
            raise FeedbackEvidenceError('Requested artifact is not sealed')
        return _load(path.read_text(encoding='utf-8'))
    return read


def _list(value, label):
    if not isinstance(value, list) or any(not isinstance(v, dict) for v in value):
        raise FeedbackEvidenceError('Malformed ' + label)
    return value


def _urls(details):
    urls = []
    def add(value):
        if value is not None and not isinstance(value, str):
            raise FeedbackEvidenceError('Malformed diagnostic URL')
        if value:
            urls.append(value)

    def trace(value):
        if value is None:
            return
        if not isinstance(value, dict):
            raise FeedbackEvidenceError('Malformed diagnostic stack')
        for frame in _list(value.get('callFrames', []), 'stack frames'):
            add(frame.get('url'))
        trace(value.get('parent'))
    add(details.get('url'))
    if 'log' in details:
        if not isinstance(details['log'], dict):
            raise FeedbackEvidenceError('Malformed browser log')
        add(details['log'].get('url'))
    trace(details.get('stackTrace'))
    if 'exception' in details:
        if not isinstance(details['exception'], dict):
            raise FeedbackEvidenceError('Malformed exception')
        trace(details['exception'].get('stackTrace'))
    return urls


def _native(payload, result):
    """Reconstruct ownership; stored owner/complete/clean flags grant no authority."""
    problems, events, by_session, by_name = [], [], {}, {}
    def block(code, details=None):
        problems.append(_issue('evaluation_integrity', code, 'Native evidence needs review; do not repair component code from it.', details))
    registry = result.get('nativeRegistry')
    if not isinstance(registry, dict):
        block('native_registry_missing')
        return events, by_name, problems
    origin, run_id = registry.get('origin'), registry.get('runId')
    if not isinstance(origin, str) or not re.fullmatch(r'http://127\.0\.0\.1:[1-9][0-9]{0,4}', origin):
        raise FeedbackEvidenceError('Invalid actual loopback origin')
    try:
        if not 1 <= urlsplit(origin).port <= 65535:
            raise ValueError('Port out of range')
    except ValueError as error:
        raise FeedbackEvidenceError('Invalid actual loopback port') from error
    try:
        if str(uuid.UUID(run_id)) != run_id:
            raise ValueError('Not canonical')
    except (ValueError, TypeError, AttributeError) as error:
        raise FeedbackEvidenceError('Invalid run identity') from error
    entries = _list(registry.get('entries'), 'native registry entries')
    if len(entries) != len(payload['pages']):
        block('native_registry_incomplete')
    seen = {k: set() for k in ['index', 'contextId', 'targetId', 'sessionId']}
    for entry in entries:
        index = entry.get('index')
        if type(index) is not int or not 0 <= index < len(payload['pages']):
            raise FeedbackEvidenceError('Native page index outside plan')
        for key in seen:
            value = entry.get(key)
            if key != 'index' and (not isinstance(value, str) or not value):
                raise FeedbackEvidenceError('Missing native identity: ' + key)
            if value in seen[key]:
                raise FeedbackEvidenceError('Reused native identity: ' + key)
            seen[key].add(value)
        page = payload['pages'][index]
        expected = {'runId': run_id, 'page': page['name'], 'index': index,
                    'targetId': entry['targetId'], 'contextId': entry['contextId'], 'sessionId': entry['sessionId']}
        if entry.get('runId') != run_id or entry.get('page') != page['name'] or entry.get('url') != origin+'/page/'+str(index) or entry.get('htmlSha256') != sha(page['html'].encode('utf-8')):
            raise FeedbackEvidenceError('Native identity/HTML/actual origin mismatch')
        roles = [role for i, pair in enumerate(payload['pairs']) for role in
                 ([{'pair': i, 'role': 'source'}] if pair['source'] == page['name'] else []) +
                 ([{'pair': i, 'role': 'target'}] if pair['target'] == page['name'] else [])]
        if entry.get('roles') != roles:
            raise FeedbackEvidenceError('Native roles differ from declared comparisons')
        observations = _list(entry.get('nativeObservations', []), 'native target/frame observations')
        if len(observations) != 2:
            block('native_double_observation_missing', {'page': page['name']})
        for observation in observations:
            info, frame = observation.get('targetInfo'), observation.get('mainFrame')
            if not isinstance(info, dict) or not isinstance(frame, dict):
                raise FeedbackEvidenceError('Missing raw native target/frame response')
            if (info.get('type') != 'page' or info.get('targetId') != entry['targetId'] or
                info.get('browserContextId') != entry['contextId'] or info.get('url') != entry['url'] or
                frame.get('url') != entry['url'] or frame.get('id') != entry.get('mainFrameId') or
                not frame.get('id') or frame.get('parentId') or frame.get('securityOrigin') != origin):
                raise FeedbackEvidenceError('Raw native target/frame identity mismatch')
        contexts = _list(entry.get('executionContexts', []), 'execution contexts')
        context_ids = set()
        for context in contexts:
            if type(context.get('id')) is not int or context['id'] <= 0 or context['id'] in context_ids or type(context.get('isDefault')) is not bool:
                raise FeedbackEvidenceError('Invalid/reused execution context identity')
            context_ids.add(context['id'])
        if not any(c.get('origin') == origin and c.get('frameId') == entry.get('mainFrameId') and c.get('isDefault') for c in contexts):
            block('native_document_execution_context_missing', {'page': page['name']})
        if entry.get('identityVerified') is not True or entry.get('contextDisposed') is not True or entry.get('lifecycle') != 'disposed':
            block('native_identity_or_disposal_incomplete', {'page': page['name']})
        by_session[entry['sessionId']] = (entry, expected)
        by_name[page['name']] = entry
    raw_events = _list(registry.get('events'), 'native events')
    if [e.get('sequence') for e in raw_events] != list(range(1, len(raw_events)+1)) or any(type(e.get('sequence')) is not int for e in raw_events):
        raise FeedbackEvidenceError('Missing/duplicate/reordered diagnostic sequence')
    known_kinds = {'runtime_exception', 'console_error', 'console_warning', 'browser_log', 'blocked_request'}
    for event in raw_events:
        if event.get('kind') not in known_kinds or not isinstance(event.get('details'), dict):
            raise FeedbackEvidenceError('Unsupported native diagnostic evidence')
        session = event.get('sessionId')
        if session is not None and not isinstance(session, str):
            raise FeedbackEvidenceError('Malformed native event session')
        owned = by_session.get(session)
        reasons = []
        entry, expected = owned if owned else (None, None)
        if not entry:
            reasons.append('unknown_native_session')
        if event.get('owner') != expected:
            reasons.append('stored_owner_mismatch')
        if entry:
            context_id = event['details'].get('executionContextId')
            if context_id is not None:
                matched = [c for c in entry['executionContexts'] if type(context_id) is int and c['id'] == context_id]
                if not matched or any(c.get('origin') != origin or c.get('frameId') != entry.get('mainFrameId') for c in matched):
                    reasons.append('unknown_or_foreign_execution_context')
            if any(url != entry['url'] for url in _urls(event['details'])):
                reasons.append('foreign_or_unproven_document_url')
        stored_reasons = event.get('reasons')
        if not isinstance(stored_reasons, list) or any(not isinstance(v, str) for v in stored_reasons):
            raise FeedbackEvidenceError('Malformed native attribution reasons')
        # Event-vs-disposal chronology is not in the old trace; never clear a recorder concern.
        if stored_reasons or event.get('attribution') != 'native_session':
            reasons.append('recorded_attribution_concern')
        events.append({'kind': event['kind'], 'page': entry['page'] if entry else None,
                       'session': session, 'provenance': 'native_session_registry',
                       'origin_verified': not reasons, 'reasons': reasons, 'event': deepcopy(event)})
    expected_exceptions = [e for e in raw_events if e['kind'] == 'runtime_exception']
    expected_console = [e for e in raw_events if e['kind'] in ['console_error','console_warning','browser_log']]
    if result.get('exceptions') != expected_exceptions or result.get('consoleErrors') != expected_console:
        raise FeedbackEvidenceError('Diagnostic collections differ from native registry (dropped/inserted event)')
    transport = result.get('transport', {})
    if not isinstance(transport, dict):
        raise FeedbackEvidenceError('Malformed transport evidence')
    blocked = [e['details'].get('url') for e in raw_events if e['kind'] == 'blocked_request']
    if transport.get('blocked', []) != blocked:
        raise FeedbackEvidenceError('Blocked request collection differs from registry')
    if registry.get('integrityErrors') or blocked or transport.get('protocolErrors') or result.get('protocolErrors') or result.get('cleanupErrors'):
        block('native_transport_registry_or_cleanup_blocked')
    allowed_paths = {'/page/'+str(i) for i in range(len(payload['pages']))}
    requests = _list(transport.get('requests', []), 'HTTP requests')
    if any(r.get('method') != 'GET' or r.get('path') not in allowed_paths for r in requests):
        block('unexpected_http_request')
    if any('/page/'+str(e['index']) not in [r.get('path') for r in requests] for e in entries if e.get('identityVerified') is True):
        block('native_document_request_missing')
    process = result.get('browserProcess', {})
    if not isinstance(process, dict):
        raise FeedbackEvidenceError('Malformed browser process evidence')
    trace = _list(process.get('protocolTrace', []), 'CDP trace')
    calls, responses = {}, {}
    for row in trace:
        call_id = row.get('id')
        if type(call_id) is not int or call_id <= 0 or row.get('phase') not in ['send','response']:
            block('native_trace_incomplete')
            continue
        dest = calls if row['phase'] == 'send' else responses
        if call_id in dest:
            raise FeedbackEvidenceError('Duplicate CDP message identity')
        dest[call_id] = row
        if row['phase'] == 'response' and call_id not in calls:
            block('native_response_without_call')
    if set(calls) != set(responses) or any(r.get('error') is not None for r in responses.values()):
        block('native_command_not_completed')
    for method in ['Target.createBrowserContext','Target.createTarget','Target.attachToTarget','Target.closeTarget','Target.disposeBrowserContext']:
        if len([c for c in calls.values() if c.get('method') == method]) != len(payload['pages']):
            block('native_lifecycle_trace_incomplete', {'method': method})
    for entry in entries:
        if len([c for c in calls.values() if c.get('method') == 'Page.getFrameTree' and c.get('sessionId') == entry['sessionId']]) != 2:
            block('native_frame_trace_incomplete', {'page': entry['page']})
    if not any(c.get('method') == 'Browser.close' for c in calls.values()) or type(process.get('exitCode')) is not int or process['exitCode'] != 0 or process.get('signalCode') is not None:
        block('browser_shutdown_unproven')
    if any(c.get('sessionId') is not None and c['sessionId'] not in by_session for c in calls.values()):
        block('unknown_native_command_session')
    if registry.get('isolationPolicy') != 'fresh_browser_context_per_page' or registry.get('storagePersistedAcrossPages') is not False:
        block('native_storage_policy_unproven')
    # No use of registry.complete/identitiesComplete or result.passed/eligible as permission.
    return events, by_name, problems


def convert_recording(bundle_directory, expected_seal_sha256, recording_relative, binding_reference=None):
    root, sealed = verify_seal(bundle_directory, expected_seal_sha256)
    read = _reader(root, sealed)
    folder = Path(recording_relative)
    payload, result = read(folder/'input.json'), read(folder/'result.json')
    if not isinstance(payload, dict) or not isinstance(result, dict) or type(result.get('schemaVersion')) is not int or result['schemaVersion'] != 3:
        raise FeedbackEvidenceError('Only explicitly supported native schema 3')
    pages, pairs = _list(payload.get('pages'), 'pages'), _list(payload.get('pairs'), 'pairs')
    if not 1 <= len(pages) <= 24 or not pairs:
        raise FeedbackEvidenceError('Explicit bounded page/pair plan required')
    names = [p.get('name') for p in pages]
    if any(not isinstance(n, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,50}', n) for n in names) or len(set(names)) != len(names) or any(not isinstance(p.get('html'), str) for p in pages):
        raise FeedbackEvidenceError('Malformed HTML/page plan')
    planned = [(p.get('source'),p.get('target')) for p in pairs]
    if any(a not in names or b not in names for a,b in planned) or len(set(planned)) != len(planned):
        raise FeedbackEvidenceError('Invalid/duplicate comparison plan')
    thresholds = payload.get('thresholds', {})
    if not isinstance(thresholds, dict) or type(thresholds.get('pixelTolerance')) is not int or not 0 <= thresholds['pixelTolerance'] <= 255 or not _finite(thresholds.get('maxChangedPixelRatio')) or not 0 <= thresholds['maxChangedPixelRatio'] <= 1 or not _finite(thresholds.get('minSSIM')) or not -1 <= thresholds['minSSIM'] <= 1:
        raise FeedbackEvidenceError('Invalid explicit thresholds')
    comparisons = _list(result.get('comparisons', []), 'comparisons')
    if any(not isinstance(c.get('source'),str) or not isinstance(c.get('target'),str) for c in comparisons):
        raise FeedbackEvidenceError('Malformed comparison names')
    if comparisons and result.get('thresholds') != thresholds:
        raise FeedbackEvidenceError('Thresholds differ from input')
    by_pair = {(c.get('source'),c.get('target')): c for c in comparisons}
    if len(by_pair) != len(comparisons) or set(by_pair)-set(planned):
        raise FeedbackEvidenceError('Result comparisons differ from plan')
    events, entries, global_issues = _native(payload, result)
    bindings, binding_evidence = {}, None
    if binding_reference is not None:
        if not isinstance(binding_reference, dict) or set(binding_reference) != {'bundle_directory','expected_seal_sha256','manifest_relative'}:
            raise FeedbackEvidenceError('Explicit independently pinned binding reference required')
        binding_root, binding_sealed = verify_seal(binding_reference['bundle_directory'],binding_reference['expected_seal_sha256'])
        manifest = _reader(binding_root,binding_sealed)(binding_reference['manifest_relative'])
        if not isinstance(manifest,dict) or not isinstance(manifest.get('pages'),dict):
            raise FeedbackEvidenceError('Malformed component binding manifest')
        bindings = manifest['pages']
        binding_evidence = {'seal_sha256':binding_reference['expected_seal_sha256'],'manifest':str(binding_reference['manifest_relative'])}
    viewport = payload.get('viewport', {})
    if not isinstance(viewport,dict) or set(viewport) != {'width','height'} or any(type(viewport.get(k)) is not int for k in ['width','height']) or not 320 <= viewport['width'] <= 1920 or not 240 <= viewport['height'] <= 1200 or payload.get('capturePolicy') not in ['viewport','full-page']:
        raise FeedbackEvidenceError('Invalid capture policy/viewport')
    environment = result.get('environment', {})
    if not isinstance(environment,dict) or any(environment.get(k) != viewport[k] for k in ['width','height']):
        raise FeedbackEvidenceError('Recorded environment differs from input viewport')
    fixed={'deviceScaleFactor':1,'locale':'zh-CN','timezone':'Asia/Shanghai','theme':'light','reducedMotion':'reduce','epoch':1794700800000,'seed':1729,'scrollbarGutter':'stable','maxPixels':4000000}
    if any(type(environment.get(k)) is not type(v) or environment[k] != v for k,v in fixed.items()) or environment.get('capturePolicy') != payload['capturePolicy'] or type(environment.get('viewportOnly')) is not bool or environment['viewportOnly'] != (payload['capturePolicy']=='viewport'):
        raise FeedbackEvidenceError('Unsupported/changed native capture environment')
    captures = result.get('captures', {})
    if not isinstance(captures,dict) or set(captures)-set(names):
        raise FeedbackEvidenceError('Invalid capture plan')
    artifacts, blockers = {}, {}
    for page in pages:
        name, capture = page['name'], captures.get(page['name'], {})
        if not isinstance(capture,dict):
            raise FeedbackEvidenceError('Malformed capture')
        issues = []
        if name in bindings:
            binding = bindings[name]
            if not isinstance(binding,dict) or binding.get('htmlSha256') != sha(page['html'].encode('utf-8')):
                raise FeedbackEvidenceError('Binding/payload HTML differs')
        if capture.get('status') != 'captured':
            issues.append(_issue('evaluation_integrity','capture_incomplete','Incomplete page capture; do not infer a component fix from prose.',{'page':name,'raw_error':capture.get('error',result.get('error'))}))
        else:
            entry = entries.get(name)
            if not entry or capture.get('nativeSessionId') != entry['sessionId'] or capture.get('nativeContextId') != entry['contextId'] or capture.get('htmlSha256') != entry['htmlSha256']:
                raise FeedbackEvidenceError('Capture is not bound to native session/context/HTML')
            dimensions, hashes = [], []
            for suffix,key in [('.png','screenshotSha256'),('-repeat.png','repeatScreenshotSha256')]:
                image = (root/folder/(name+suffix)).resolve()
                if image not in sealed or capture.get(key) != sealed[image]:
                    raise FeedbackEvidenceError('Missing/changed native screenshot')
                dimensions.append(_png(image.read_bytes())); hashes.append(sealed[image])
            repeat = capture.get('repeatObservation')
            fields = ['styles','extent','componentEvidence','environment']
            stable = isinstance(repeat,dict) and all(k in capture and k in repeat and capture[k] == repeat[k] for k in fields) and dimensions[0] == dimensions[1] and hashes[0] == hashes[1]
            if not stable or capture.get('stable') is not True:
                issues.append(_issue('evaluation_integrity','capture_stability_unproven','Raw/repeat observations do not prove stable capture.',{'page':name}))
            observed_env=capture.get('environment')
            expected_env={**viewport,'dpr':1,'theme':True,'reducedMotion':True,'timezone':'Asia/Shanghai','locale':'zh-CN','time':1794700800000}
            if not isinstance(observed_env,dict) or any(type(observed_env.get(k)) is not type(v) or observed_env[k] != v for k,v in expected_env.items()):
                issues.append(_issue('evaluation_integrity','capture_environment_not_applied','Stable capture alone does not prove the fixed environment was applied.',{'page':name}))
            actual_clean = not any(e['page'] == name for e in events)
            if type(capture.get('clean')) is not bool or capture['clean'] != actual_clean:
                issues.append(_issue('evaluation_integrity','capture_clean_flag_inconsistent','Clean flag cannot remove native diagnostics.',{'page':name}))
            extent = capture.get('extent')
            if not isinstance(extent,dict) or any(not _finite(extent.get(k)) or extent[k] <= 0 for k in ['width','height']) or extent['width'] > viewport['width']:
                raise FeedbackEvidenceError('Invalid page extent')
            height = viewport['height'] if payload['capturePolicy'] == 'viewport' else extent['height']
            if extent['height'] < viewport['height'] or (payload['capturePolicy']=='viewport' and extent['height'] > viewport['height']) or dimensions[0] != [viewport['width'],height] or viewport['width']*height > 4000000:
                raise FeedbackEvidenceError('Image dimensions differ from declared capture policy')
            styles = capture.get('styles')
            if not isinstance(styles,dict) or not styles or not isinstance(page.get('selectors'),dict) or set(styles) != set(page['selectors']):
                raise FeedbackEvidenceError('Critical selectors/styles differ')
            for style in styles.values():
                if not isinstance(style,dict) or set(style) != NATIVE_STYLE_KEYS or not isinstance(style.get('rect'),dict) or any(not _finite(style['rect'].get(k)) for k in ['x','y','width','height']):
                    raise FeedbackEvidenceError('Invalid critical rectangle')
                r=style['rect']
                if r['x'] < 0 or r['y'] < 0 or r['width'] <= 0 or r['height'] <= 0 or r['x']+r['width'] > viewport['width'] or r['y']+r['height'] > height or any(not isinstance(v,str) for k,v in style.items() if k!='rect'):
                    raise FeedbackEvidenceError('Invalid critical style geometry/value')
            artifacts[name]={'dimensions':dimensions[0],'sha256':hashes[0]}
        blockers[name]=issues
    packet={'schema_version':2,'recording_schema':3,'scope':'offline_native_browser_feedback_not_production_admission',
        'evidence':{'seal_sha256':expected_seal_sha256,'recording':folder.as_posix(),'input_sha256':sealed[(root/folder/'input.json').resolve()],'result_sha256':sealed[(root/folder/'result.json').resolve()],'binding':binding_evidence},
        'thresholds':deepcopy(thresholds),'scenes':[],'repair_dispatch_allowed':False,'production_protocol_frozen':False,'semantic_gate_bypass_allowed':False,'model_calls':0}
    for source,target in planned:
        issues=deepcopy(global_issues+blockers[source]+blockers[target])
        for event in events:
            if not event['origin_verified']:
                issues.append(_issue('evaluation_integrity','native_event_origin_unproven','Unknown/conflicting native event; no owner inferred from message or stack.',event))
            elif event['page'] in [source,target]:
                channel='evaluation_integrity' if event['kind']=='blocked_request' else ('source_oracle' if event['page']==source else 'target_runtime')
                issues.append(_issue(channel,channel+'_'+event['kind'],'Diagnostic bound to native page session; retain raw details.',event))
        before,after=captures.get(source,{}).get('styles',{}),captures.get(target,{}).get('styles',{})
        changes=[]
        if before and after:
            for key in sorted(set(before)|set(after)):
                if key not in before or key not in after:
                    changes.append({'key':key,'property':'mapping','source':before.get(key),'target':after.get(key)})
                else:
                    for prop in sorted(set(before[key])|set(after[key])):
                        if before[key].get(prop)!=after[key].get(prop):
                            changes.append({'key':key,'property':prop,'source':before[key].get(prop),'target':after[key].get(prop)})
        observation={'style_changes':changes,'dimensions':None,'metrics':None}
        metric_passed=None
        if source in artifacts and target in artifacts:
            a,b=artifacts[source],artifacts[target]
            observation['dimensions']={'source':a['dimensions'],'target':b['dimensions']}
            metric=by_pair.get((source,target),{}).get('metrics')
            if a['dimensions']!=b['dimensions']:
                if metric is not None:raise FeedbackEvidenceError('Metric supplied for different image dimensions')
                issues.append(_issue('visual_observation','browser_capture_dimension_mismatch','Dimensions differ; no resize or fabricated SSIM.',observation['dimensions']))
                metric_passed=False
            else:
                _metric_check(metric,a['dimensions'],thresholds,a['sha256']==b['sha256'])
                observation['metrics']=deepcopy(metric)
                metric_passed=metric['changedPixelRatio']<=thresholds['maxChangedPixelRatio'] and metric['ssim']>=thresholds['minSSIM']
                if not metric_passed:issues.append(_issue('visual_observation','browser_pixel_or_ssim_mismatch','Recorded metrics exceed declared thresholds.',metric))
        if changes:issues.append(_issue('visual_observation','browser_critical_style_mismatch','Critical native styles/rectangles differ.',{'changes':changes}))
        channels={i['channel'] for i in issues}
        action=('review_evaluator_or_evidence' if 'evaluation_integrity' in channels else 'review_source_oracle' if 'source_oracle' in channels else 'review_target_candidate' if channels&{'target_runtime','visual_observation'} else 'visual_match_only' if metric_passed is True else 'review_evaluator_or_evidence')
        binding={'source':deepcopy(bindings.get(source)),'target':deepcopy(bindings.get(target))}
        bound=source!=target and all(isinstance(binding[s],dict) and binding[s].get('boundary',{}).get('framework')==f and _pin(binding[s].get('input',{}).get('sha256')) for s,f in [('source','vue'),('target','san')])
        packet['scenes'].append({'source':source,'target':target,'issues':issues,'observation':observation,'recommended_action':action,'binding':binding,'component_pair_bound':bool(bound),
            'target_feedback_eligible':action=='review_target_candidate' and bool(bound),'repair_dispatch_allowed':False,'migration_pass_certified':False,'provenance_note':'Native session/context/frame observations from a trusted pinned recorder, not arbitrary-producer authentication.'})
    return packet


def build_repair_preview(state, *, bundle_directory, expected_seal_sha256, recording_relative, binding_reference, scene_index):
    packet=convert_recording(bundle_directory,expected_seal_sha256,recording_relative,binding_reference)
    if type(scene_index) is not int or not 0 <= scene_index < len(packet['scenes']):
        raise FeedbackNotEligible('Invalid scene index')
    scene=packet['scenes'][scene_index]
    if not scene['target_feedback_eligible'] or any(i['channel'] not in ['target_runtime','visual_observation'] for i in scene['issues']):
        raise FeedbackNotEligible('Source/evaluator/unbound evidence cannot reach target preview')
    for side,field in [('source','vue_source'),('target','generated_code')]:
        binding=scene['binding'][side];value=state.get(field)
        if not isinstance(value,str) or sha(value.encode('utf-8'))!=binding['input']['sha256']:
            raise FeedbackNotEligible('Current code differs from rendered '+side)
        modules=binding.get('moduleManifest')
        # No invented caller dependency protocol; until current graph rebinding is
        # implemented, never claim a main-file hash validates changed child files.
        if not isinstance(modules,list) or len(modules)!=1 or not isinstance(modules[0],dict) or modules[0].get('sha256')!=binding['input']['sha256']:
            raise FeedbackNotEligible('Multi-module/current dependency binding not supported for preview')
    try:
        props=json.dumps(state.get('visual_eval_render_props',state.get('render_props',{})),sort_keys=True,allow_nan=False)
        if any(json.dumps(scene['binding'][s].get('props',{}),sort_keys=True,allow_nan=False)!=props for s in ['source','target']):
            raise FeedbackNotEligible('Current props differ from native capture')
    except (TypeError,ValueError) as error:
        raise FeedbackNotEligible('Invalid/stale props') from error
    allowed={'san_render_failed','san_san_render_error','dom_structure_similarity_low','dom_critical_attribute_mismatch','dom_text_similarity_low'}
    legacy=state.get('visual_eval_errors',[])+state.get('visual_eval_warnings',[])
    if any(not isinstance(i,dict) or i.get('code') not in allowed for i in legacy):
        raise FeedbackNotEligible('Source/unknown legacy visual diagnostics require review')
    additions=[{'code':i['code'],'message':i['message'],'severity':'error','location':'browser.native','details':deepcopy(i['details'])} for i in scene['issues']]
    from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
    errors=deepcopy(state.get('visual_eval_errors',[]))+additions
    prompt=build_repair_prompt(RepairPromptInput(ssm=deepcopy(state.get('ssm',{})),current_code=state['generated_code'],vue_source=state['vue_source'],source_file=state.get('source_file',''),
        validation_errors=deepcopy(state.get('validation_errors',[])),validation_warnings=deepcopy(state.get('validation_warnings',[])),visual_eval_errors=errors,visual_eval_warnings=deepcopy(state.get('visual_eval_warnings',[])),
        dom_compare_result=deepcopy(state.get('dom_compare_result')),extra_instruction='OFFLINE REVIEW ONLY: preserve source/semantic contracts. Repair only native-evidenced target defects; do not resize/mask screenshots, change thresholds, remove nodes or silence diagnostics.'))
    return {'prompt':prompt,'visual_eval_errors':errors,'validation_errors':deepcopy(state.get('validation_errors',[])),
        'source_code_sha256':sha(state['vue_source'].encode('utf-8')),'target_code_sha256':sha(state['generated_code'].encode('utf-8')),
        'repair_dispatch_allowed':False,'semantic_candidate_gate_still_required':True,'production_protocol_frozen':False,'model_calls':0,'recording_schema':3}
