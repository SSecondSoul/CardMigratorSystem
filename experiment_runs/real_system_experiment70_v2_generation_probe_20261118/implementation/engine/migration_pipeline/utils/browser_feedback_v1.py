"""Sealed browser recordings -> origin-separated feedback + offline repair preview.

This module does not run a browser/model, change scores, mutate state, or install a
production admission policy. A trusted protocol must supply the seal fingerprint;
a hash proves consistency with that pin, not authenticity of arbitrary recordings.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import struct
from urllib.parse import urlsplit
import zlib


class FeedbackEvidenceError(ValueError):
    pass


class FeedbackNotEligible(ValueError):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _json(data):
    def reject(value):
        raise FeedbackEvidenceError('Non-finite JSON constant: ' + value)
    try:
        return json.loads(data, parse_constant=reject)
    except (TypeError, json.JSONDecodeError) as error:
        raise FeedbackEvidenceError('Invalid JSON') from error


def _finite(value):
    return type(value) in [int, float] and math.isfinite(value)


def _pin(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def verify_seal(directory, expected_sha256):
    directory = Path(directory).resolve()
    seal = directory / 'SHA256SUMS.txt'
    if not _pin(expected_sha256) or sha(seal.read_bytes()) != expected_sha256:
        raise FeedbackEvidenceError('Seal does not match the externally pinned fingerprint')
    files = {}
    for line in seal.read_text(encoding='utf-8').splitlines():
        try:
            digest, relative = line.split('  ', 1)
        except ValueError as error:
            raise FeedbackEvidenceError('Invalid seal row') from error
        path = (directory / relative).resolve()
        if not _pin(digest) or not path.is_relative_to(directory) or path == seal or path in files:
            raise FeedbackEvidenceError('Unsafe/duplicate seal member')
        if not path.is_file() or sha(path.read_bytes()) != digest:
            raise FeedbackEvidenceError('Sealed payload differs: ' + relative)
        files[path] = digest
    if not files:
        raise FeedbackEvidenceError('Empty seal')
    return directory, files


def _png(data):
    """Validate chunk framing/CRC and the 8-bit RGB(A) PNG header.

    No IDAT/alpha/filter decode or independent pixel/SSIM recomputation here.
    These remain pinned evaluator observations, not trusted claims from an
    unknown producer merely because someone generated a new matching checksum.
    """
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise FeedbackEvidenceError('Not a PNG')
    offset, dimensions, ended, has_data = 8, None, False, False
    while offset + 12 <= len(data):
        size = struct.unpack('>I', data[offset:offset + 4])[0]
        end = offset + size + 12
        if end > len(data):
            raise FeedbackEvidenceError('Truncated PNG')
        kind, body = data[offset + 4:offset + 8], data[offset + 8:offset + 8 + size]
        if zlib.crc32(data[offset + 4:offset + 8 + size]) != struct.unpack('>I', data[offset + 8 + size:end])[0]:
            raise FeedbackEvidenceError('PNG CRC differs')
        if kind == b'IHDR':
            if dimensions is not None or offset != 8 or size != 13:
                raise FeedbackEvidenceError('Invalid PNG header')
            width, height, depth, color, compression, filters, interlace = struct.unpack('>IIBBBBB', body)
            if not width or not height or width * height > 4000000 or depth != 8 or color not in [2, 6] or compression or filters or interlace:
                raise FeedbackEvidenceError('Unsupported PNG format')
            dimensions = [width, height]
        elif kind == b'IDAT':
            has_data = True
        elif kind == b'IEND':
            if size:
                raise FeedbackEvidenceError('Invalid PNG end')
            ended = True
            offset = end
            break
        offset = end
    if not dimensions or not ended or not has_data or offset != len(data):
        raise FeedbackEvidenceError('Incomplete/trailing PNG')
    return dimensions


def _frame_urls(event):
    urls = []
    if isinstance(event.get('url'), str) and event['url']:
        urls.append(event['url'])
    trace = event.get('stackTrace')
    while isinstance(trace, dict):
        frames = trace.get('callFrames', [])
        if not isinstance(frames, list):
            raise FeedbackEvidenceError('Malformed event stack frames')
        urls.extend(f['url'] for f in frames if isinstance(f, dict) and f.get('url'))
        trace = trace.get('parent')
    return urls


def _event_pages(events, names):
    """Legacy v2 lacks page/session registry: only unique loopback frame URLs bind.

    Never infer a page from message text or from 'Vue'/'San' tokens. Retain the
    weaker legacy provenance; it is not production-grade session attestation.
    """
    sessions, parsed = {}, []
    for kind, event in events:
        candidates, origins, uncertain = set(), set(), False
        for url in _frame_urls(event):
            if not isinstance(url, str):
                raise FeedbackEvidenceError('Malformed event frame URL')
            u = urlsplit(url)
            if u.scheme not in ['http', 'https']:
                uncertain = True
                continue
            match = re.fullmatch(r'/page/(0|[1-9][0-9]*)', u.path)
            try:
                port = u.port
            except ValueError:
                port = None
            if u.scheme != 'http' or u.hostname != '127.0.0.1' or not port or u.username or u.password or u.query or u.fragment or not match or int(match[1]) >= len(names):
                uncertain = True
                continue
            candidates.add(names[int(match[1])])
            origins.add(u.netloc)
        page = next(iter(candidates)) if len(candidates) == 1 and len(origins) == 1 and not uncertain else None
        session = event.get('session')
        if session is not None and not isinstance(session, str):
            raise FeedbackEvidenceError('Malformed event session')
        if isinstance(session, str):
            sessions.setdefault(session, set()).add(page)
        parsed.append({'kind': kind, 'page': page, 'session': session, 'event': event,
                       'provenance': 'legacy_unique_loopback_frame' if page else 'unattributed'})
    # Conflicting observations in one native session cannot be papered over.
    for item in parsed:
        if item['session'] in sessions and len(sessions[item['session']]) != 1:
            item['page'], item['provenance'] = None, 'conflicting_session_frames'
    return parsed


def _issue(channel, code, message, details=None):
    return {'channel': channel, 'code': code, 'message': message, 'details': details or {}}


def _metric_check(metrics, dimensions, thresholds, same_bytes):
    if not isinstance(metrics, dict):
        raise FeedbackEvidenceError('Metric observations missing')
    w, h = dimensions
    n, changed = metrics.get('totalPixels'), metrics.get('changedPixels')
    if metrics.get('width') != w or metrics.get('height') != h or type(n) is not int or n != w * h or type(changed) is not int or not 0 <= changed <= n:
        raise FeedbackEvidenceError('Metric dimensions/counts inconsistent with PNG')
    for key, lower, upper in [('changedPixelRatio', 0, 1), ('rgbMeanAbsoluteError', 0, 255), ('maxChannelDelta', 0, 255), ('ssim', -1, 1 + 1e-9)]:
        if not _finite(metrics.get(key)) or not lower <= metrics[key] <= upper:
            raise FeedbackEvidenceError('Invalid metric value: ' + key)
    if not math.isclose(metrics['changedPixelRatio'], changed / n, rel_tol=0, abs_tol=1e-12):
        raise FeedbackEvidenceError('Wrong changed-pixel denominator')
    if same_bytes and (changed or metrics['rgbMeanAbsoluteError'] or metrics['maxChannelDelta']):
        raise FeedbackEvidenceError('Identical image bytes reported as different')
    if thresholds['pixelTolerance'] == 0 and not changed and not same_bytes:
        # Conservative: metadata/compression could differ, but needs pixel revalidation.
        raise FeedbackEvidenceError('Zero-difference claim needs pixel revalidation')


def convert_recording(bundle_directory, expected_seal_sha256, recording_relative, bindings_relative=None):
    root, sealed = verify_seal(bundle_directory, expected_seal_sha256)

    def read(relative):
        path = (root / relative).resolve()
        if path not in sealed:
            raise FeedbackEvidenceError('Unsealed requested artifact')
        return _json(path.read_text(encoding='utf-8'))

    folder = Path(recording_relative)
    payload, result = read(folder / 'input.json'), read(folder / 'result.json')
    if not isinstance(payload, dict) or not isinstance(result, dict):
        raise FeedbackEvidenceError('Recording must be a JSON object')
    if result.get('schemaVersion') != 2:
        raise FeedbackEvidenceError('Only explicitly supported v2 recordings')
    pages, pairs = payload.get('pages'), payload.get('pairs')
    if not isinstance(pages, list) or not pages or not isinstance(pairs, list) or not pairs:
        raise FeedbackEvidenceError('Page/pair plan missing')
    if any(not isinstance(p, dict) or not isinstance(p.get('html'), str) for p in pages) or any(not isinstance(p, dict) for p in pairs):
        raise FeedbackEvidenceError('Malformed page/pair plan')
    names = [p.get('name') for p in pages]
    if any(not isinstance(n, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,50}', n) for n in names) or len(set(names)) != len(names):
        raise FeedbackEvidenceError('Invalid/duplicate page names')
    bindings = read(bindings_relative)['pages'] if bindings_relative else {}
    thresholds = payload.get('thresholds', {})
    if type(thresholds.get('pixelTolerance')) is not int or not 0 <= thresholds['pixelTolerance'] <= 255 or any(not _finite(thresholds.get(k)) or not 0 <= thresholds[k] <= 1 for k in ['maxChangedPixelRatio', 'minSSIM']):
        raise FeedbackEvidenceError('Invalid explicit thresholds')
    if thresholds != result.get('thresholds') and result.get('comparisons') is not None:
        raise FeedbackEvidenceError('Result thresholds differ from recorded input')
    comparisons = result.get('comparisons', [])
    if not isinstance(comparisons, list) or any(not isinstance(c, dict) for c in comparisons):
        raise FeedbackEvidenceError('Malformed comparisons')
    by_pair = {}
    for comparison in comparisons:
        key = (comparison.get('source'), comparison.get('target'))
        if key in by_pair:
            raise FeedbackEvidenceError('Duplicate comparison result')
        by_pair[key] = comparison
    expected_pairs = [(p.get('source'), p.get('target')) for p in pairs]
    if len(set(expected_pairs)) != len(expected_pairs) or any(a not in names or b not in names for a, b in expected_pairs) or set(by_pair) - set(expected_pairs):
        raise FeedbackEvidenceError('Input/result pair plan inconsistent')
    if any(not isinstance(result.get(key, []), list) for key in ['exceptions', 'consoleErrors']):
        raise FeedbackEvidenceError('Malformed diagnostic collection')
    raw_events = [('runtime_exception', e) for e in result.get('exceptions', [])]
    raw_events += [('console_diagnostic', e) for e in result.get('consoleErrors', [])]
    if any(not isinstance(e, dict) for _, e in raw_events):
        raise FeedbackEvidenceError('Malformed event evidence')
    events = _event_pages(raw_events, names)
    captures, artifacts, blockers = result.get('captures', {}), {}, {}
    if not isinstance(captures, dict) or any(not isinstance(c, dict) for c in captures.values()):
        raise FeedbackEvidenceError('Malformed capture collection')
    for page in pages:
        name, issues = page['name'], []
        html_sha = sha(page['html'].encode('utf-8'))
        capture = captures.get(name, {})
        if name in bindings and bindings[name].get('htmlSha256') != html_sha:
            raise FeedbackEvidenceError('Prepared manifest/payload HTML differs')
        if capture.get('status') != 'captured':
            issues.append(_issue('evaluation_integrity', 'capture_incomplete', 'No complete capture; do not diagnose target code from capture prose.', {'page': name, 'raw_error': capture.get('error', result.get('error'))}))
        else:
            if capture.get('htmlSha256') != html_sha:
                raise FeedbackEvidenceError('Capture/payload HTML differs')
            dims = []
            hashes = []
            for suffix, key in [('.png', 'screenshotSha256'), ('-repeat.png', 'repeatScreenshotSha256')]:
                image = (root / folder / (name + suffix)).resolve()
                if image not in sealed or capture.get(key) != sealed[image]:
                    raise FeedbackEvidenceError('Screenshot absent or fingerprint differs')
                dims.append(_png(image.read_bytes()))
                hashes.append(sealed[image])
            artifacts[name] = {'dimensions': dims[0], 'screenshot_sha256': hashes[0], 'repeat_sha256': hashes[1]}
            repeat = capture.get('repeatObservation')
            fields = ['styles', 'extent', 'componentEvidence', 'environment']
            stable = (isinstance(repeat, dict) and all(k in repeat and k in capture for k in fields)
                      and all(capture[k] == repeat[k] for k in fields) and dims[0] == dims[1] and hashes[0] == hashes[1])
            if not stable:
                issues.append(_issue('evaluation_integrity', 'capture_stability_unproven', 'Repeated image/observations are different or incomplete.', {'page': name}))
            if type(capture.get('stable')) is not bool or capture['stable'] != stable:
                issues.append(_issue('evaluation_integrity', 'capture_stability_flag_untrusted', 'Stored stable flag cannot override repeated evidence.', {'page': name}))
            matched = [e for e in events if e['page'] == name]
            if type(capture.get('clean')) is not bool or capture['clean'] != (not matched):
                issues.append(_issue('evaluation_integrity', 'event_cleanliness_unproven', 'Clean flag and attributed event evidence do not agree.', {'page': name}))
            if not isinstance(capture.get('styles'), dict) or not capture['styles']:
                issues.append(_issue('evaluation_integrity', 'critical_styles_missing', 'No explicit critical-element observations.', {'page': name}))
            else:
                if not isinstance(page.get('selectors'), dict) or set(page['selectors']) != set(capture['styles']):
                    raise FeedbackEvidenceError('Critical selector mapping differs from capture')
                for style in capture['styles'].values():
                    if not isinstance(style, dict) or not isinstance(style.get('rect'), dict) or any(not _finite(style['rect'].get(k)) for k in ['x', 'y', 'width', 'height']):
                        raise FeedbackEvidenceError('Malformed critical rectangle')
                    if style['rect']['width'] <= 0 or style['rect']['height'] <= 0 or any(not isinstance(v, str) for k, v in style.items() if k != 'rect'):
                        raise FeedbackEvidenceError('Malformed critical style value')
        blockers[name] = issues
    packet = {'schema_version': 1, 'scope': 'offline_browser_feedback_not_production_admission',
              'evidence': {'seal_sha256': expected_seal_sha256, 'recording': str(folder).replace('\\', '/'),
                           'result_sha256': sealed[(root / folder / 'result.json').resolve()],
                           'input_sha256': sealed[(root / folder / 'input.json').resolve()]},
              'thresholds': deepcopy(thresholds), 'scenes': [], 'repair_dispatch_allowed': False,
              'production_protocol_frozen': False, 'semantic_gate_bypass_allowed': False, 'model_calls': 0}
    transport = result.get('transport', {})
    for source, target in expected_pairs:
        issues = deepcopy(blockers[source] + blockers[target])
        if transport.get('protocolErrors') or transport.get('blocked') or result.get('protocolErrors') or result.get('cleanupErrors'):
            issues.append(_issue('evaluation_integrity', 'browser_transport_or_cleanup_blocked', 'Transport/cleanup errors require evaluator review, not code repair.'))
        for event in events:
            if event['page'] is None:
                issues.append(_issue('evaluation_integrity', 'event_origin_unproven', 'Event cannot be uniquely bound to a page; do not guess from its message.', event))
            elif event['page'] in [source, target]:
                channel = 'source_oracle' if event['page'] == source else 'target_runtime'
                issues.append(_issue(channel, ('source_' if channel == 'source_oracle' else 'target_') + event['kind'],
                                     'Recorded diagnostic belongs to ' + channel + '; raw channel retained.', event))
        before = captures.get(source, {}).get('styles', {})
        after = captures.get(target, {}).get('styles', {})
        style_changes = []
        if before and after:
            for key in sorted(set(before) | set(after)):
                if key not in before or key not in after:
                    style_changes.append({'key': key, 'property': 'mapping', 'source': before.get(key), 'target': after.get(key)})
                else:
                    for prop in sorted(set(before[key]) | set(after[key])):
                        if before[key].get(prop) != after[key].get(prop):
                            style_changes.append({'key': key, 'property': prop, 'source': before[key].get(prop), 'target': after[key].get(prop)})
        observation = {'style_changes': style_changes, 'dimensions': None, 'metrics': None}
        metric_passed = None
        if source in artifacts and target in artifacts:
            a, b = artifacts[source], artifacts[target]
            observation['dimensions'] = {'source': a['dimensions'], 'target': b['dimensions']}
            if a['dimensions'] != b['dimensions']:
                issues.append(_issue('visual_observation', 'browser_capture_dimension_mismatch', 'Native screenshot dimensions differ; no resize or fabricated SSIM.', observation['dimensions']))
                metric_passed = False
                if by_pair.get((source, target), {}).get('metrics') is not None:
                    raise FeedbackEvidenceError('Metric reported for unequal screenshot dimensions')
            else:
                metric = by_pair.get((source, target), {}).get('metrics')
                _metric_check(metric, a['dimensions'], thresholds, a['screenshot_sha256'] == b['screenshot_sha256'])
                observation['metrics'] = deepcopy(metric)
                metric_passed = metric['changedPixelRatio'] <= thresholds['maxChangedPixelRatio'] and metric['ssim'] >= thresholds['minSSIM']
                if not metric_passed:
                    issues.append(_issue('visual_observation', 'browser_pixel_or_ssim_mismatch', 'Recorded pixel/SSIM metrics exceed the declared calibration thresholds.', deepcopy(metric)))
        if style_changes:
            issues.append(_issue('visual_observation', 'browser_critical_style_mismatch', 'Critical computed styles/rectangles differ.', {'changes': style_changes}))
        channels = {i['channel'] for i in issues}
        if 'evaluation_integrity' in channels:
            action = 'review_evaluator_or_evidence'
        elif 'source_oracle' in channels:
            action = 'review_source_oracle'
        elif 'target_runtime' in channels or 'visual_observation' in channels:
            action = 'review_target_candidate'
        elif metric_passed is True:
            action = 'visual_match_only'
        else:
            action = 'review_evaluator_or_evidence'
        binding = {'source': deepcopy(bindings.get(source)), 'target': deepcopy(bindings.get(target))}
        component_pair = (source != target and binding['source'] and binding['target']
                          and binding['source'].get('boundary', {}).get('framework') == 'vue'
                          and binding['target'].get('boundary', {}).get('framework') == 'san')
        packet['scenes'].append({'source': source, 'target': target, 'issues': issues, 'observation': observation,
                                'recommended_action': action, 'component_pair_bound': bool(component_pair), 'binding': binding,
                                'target_feedback_eligible': action == 'review_target_candidate' and bool(component_pair),
                                'repair_dispatch_allowed': False, 'migration_pass_certified': False,
                                'provenance_note': 'Legacy frame binding only; no recorded session/page registry or production protocol.'})
    return packet


def build_repair_preview(state, *, bundle_directory, expected_seal_sha256, recording_relative,
                         bindings_relative, scene_index):
    """Build a target-only prompt for review; never call/enable the repair API.

    Re-read the pinned artifacts independently. Caller-supplied route flags or an
    edited packet never grant eligibility. The externally pinned seal must come
    from the trusted experiment protocol, not from an untrusted report itself.
    """
    packet = convert_recording(bundle_directory, expected_seal_sha256, recording_relative, bindings_relative)
    if type(scene_index) is not int or not 0 <= scene_index < len(packet['scenes']):
        raise FeedbackNotEligible('Invalid scene index')
    scene = packet['scenes'][scene_index]
    if not scene['target_feedback_eligible'] or any(i['channel'] not in ['target_runtime', 'visual_observation'] for i in scene['issues']):
        raise FeedbackNotEligible('Source/evaluator/unbound evidence must not reach target repair')
    for side, field in [('source', 'vue_source'), ('target', 'generated_code')]:
        expected = (scene['binding'][side] or {}).get('input', {}).get('sha256')
        value = state.get(field)
        if not _pin(expected) or not isinstance(value, str) or sha(value.encode('utf-8')) != expected:
            raise FeedbackNotEligible('Current code differs from rendered input: ' + side)
    current_props = state.get('visual_eval_render_props', state.get('render_props', {}))
    try:
        normalized_props = json.dumps(current_props, sort_keys=True, allow_nan=False)
        if any(json.dumps(scene['binding'][side].get('props', {}), sort_keys=True, allow_nan=False) != normalized_props for side in ['source', 'target']):
            raise FeedbackNotEligible('Current props differ from rendered input')
    except (TypeError, ValueError) as error:
        raise FeedbackNotEligible('Invalid/stale render props') from error
    allowed_legacy = {'san_render_failed', 'san_san_render_error', 'dom_structure_similarity_low', 'dom_critical_attribute_mismatch', 'dom_text_similarity_low'}
    legacy = state.get('visual_eval_errors', []) + state.get('visual_eval_warnings', [])
    if any(not isinstance(i, dict) or i.get('code') not in allowed_legacy for i in legacy):
        raise FeedbackNotEligible('Unclassified/source legacy visual feedback requires review')
    issues = [{'code': i['code'], 'message': i['message'], 'severity': 'error', 'location': 'browser.visual',
               'details': deepcopy(i['details'])} for i in scene['issues']]
    from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
    errors = deepcopy(state.get('visual_eval_errors', [])) + issues
    prompt = build_repair_prompt(RepairPromptInput(
        ssm=deepcopy(state.get('ssm', {})), current_code=state['generated_code'], vue_source=state['vue_source'],
        source_file=state.get('source_file', ''), validation_errors=deepcopy(state.get('validation_errors', [])),
        validation_warnings=deepcopy(state.get('validation_warnings', [])), visual_eval_errors=errors,
        visual_eval_warnings=deepcopy(state.get('visual_eval_warnings', [])), dom_compare_result=deepcopy(state.get('dom_compare_result')),
        extra_instruction='OFFLINE REVIEW ONLY: preserve source/semantic contracts. Repair only evidenced target defects; do not resize/mask screenshots, change thresholds, remove nodes or silence diagnostics to improve a score.'))
    return {'prompt': prompt, 'visual_eval_errors': errors, 'validation_errors': deepcopy(state.get('validation_errors', [])),
            'source_code_sha256': sha(state['vue_source'].encode()), 'target_code_sha256': sha(state['generated_code'].encode()),
            'repair_dispatch_allowed': False, 'semantic_candidate_gate_still_required': True, 'model_calls': 0,
            'production_protocol_frozen': False}
