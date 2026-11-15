"""Origin routing, evidence consistency and repair-preview separation.
Synthetic PNG/JSON are unit fixtures, not newly executed browser observations.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from migration_pipeline.utils.browser_feedback_v1 import (
    FeedbackEvidenceError, FeedbackNotEligible, build_repair_preview, convert_recording, sha,
)
from migration_pipeline.replay_browser_feedback_v1 import replay


SOURCE = '<template><main>source</main></template><script>module.exports={methods:{setValue(k,v){this[k]=v;}}};</script>'
TARGET = '<template><main>target</main></template><script>const san=require("san");module.exports=san.defineComponent({setValue(k,v){this.data.set(k,v);}});</script>'


def png(gray):
    def chunk(name, body):
        return struct.pack('>I', len(body)) + name + body + struct.pack('>I', zlib.crc32(name + body))
    raw = b''.join(b'\0' + bytes([gray, gray, gray, 255]) * 16 for _ in range(16))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 16, 16, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def fixture():
    pages, captures, bindings, images = [], {}, {}, {}
    for name, framework, gray, code in [('source', 'vue', 100, SOURCE), ('target', 'san', 110, TARGET)]:
        html = '<main style="background:rgb({0},{0},{0})">fixture</main>'.format(gray)
        image = png(gray)
        pages.append({'name': name, 'html': html, 'selectors': {'root': 'main'}})
        observed = {'styles': {'root': {'rect': {'x': 0, 'y': 0, 'width': 16, 'height': 16}, 'background-color': 'rgb({0}, {0}, {0})'.format(gray)}},
                    'extent': {'width': 16, 'height': 16}, 'componentEvidence': None, 'environment': {'time': 1}}
        captures[name] = {**deepcopy(observed), 'repeatObservation': deepcopy(observed), 'status': 'captured', 'clean': True, 'stable': True,
                          'htmlSha256': sha(html.encode()), 'screenshotSha256': sha(image), 'repeatScreenshotSha256': sha(image)}
        bindings[name] = {'htmlSha256': sha(html.encode()), 'boundary': {'framework': framework},
                          'input': {'sha256': sha(code.encode()), 'path': name + '.fixture'}, 'props': {}}
        images[name + '.png'] = image
        images[name + '-repeat.png'] = image
    threshold = {'pixelTolerance': 0, 'maxChangedPixelRatio': 0, 'minSSIM': .999999999}
    pair = {'source': 'source', 'target': 'target'}
    metric = {'width': 16, 'height': 16, 'totalPixels': 256, 'changedPixels': 256, 'changedPixelRatio': 1,
              'rgbMeanAbsoluteError': 10, 'maxChannelDelta': 10, 'ssim': (22000 + 6.5025) / (22100 + 6.5025)}
    return {'payload': {'pages': pages, 'pairs': [pair], 'thresholds': threshold},
            'result': {'schemaVersion': 2, 'status': 'evaluated', 'passed': False, 'captures': captures,
                       'comparisons': [{**pair, 'metrics': metric, 'eligible': True, 'passed': False, 'styleChanges': []}],
                       'thresholds': threshold, 'exceptions': [], 'consoleErrors': [], 'transport': {'protocolErrors': [], 'blocked': []}},
            'bindings': {'pages': bindings}, 'images': images}


def event(index, message='diagnostic', session='session'):
    return {'session': session, 'type': 'error', 'args': [{'type': 'string', 'value': message}],
            'stackTrace': {'callFrames': [{'url': 'http://127.0.0.1:12345/page/' + str(index)}]}}


class RoutingUnitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cardmig-feedback-unit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = fixture()

    def seal(self):
        directory = self.root / 'run'
        directory.mkdir(exist_ok=True)
        for name, value in [('input.json', self.data['payload']), ('result.json', self.data['result'])]:
            (directory / name).write_text(json.dumps(value), encoding='utf-8')
        (self.root / 'bindings.json').write_text(json.dumps(self.data['bindings']), encoding='utf-8')
        for name, raw in self.data['images'].items():
            (directory / name).write_bytes(raw)
        rows = [sha(p.read_bytes()) + '  ' + p.relative_to(self.root).as_posix() for p in sorted(self.root.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS.txt']
        (self.root / 'SHA256SUMS.txt').write_text('\n'.join(rows) + '\n', encoding='utf-8')
        self.pin = sha((self.root / 'SHA256SUMS.txt').read_bytes())
        return convert_recording(self.root, self.pin, 'run', 'bindings.json')

    def preview(self, state=None):
        if state is None:
            state = {'vue_source': SOURCE, 'generated_code': TARGET, 'ssm': {}, 'validation_errors': [
                {'code': 'source_dynamic_assignment_unproven', 'message': 'retain arbitrary key block', 'location': 'script.methods.setValue'}]}
        return build_repair_preview(state, bundle_directory=self.root, expected_seal_sha256=self.pin,
                                    recording_relative='run', bindings_relative='bindings.json', scene_index=0)

    def add_event(self, side, message='diagnostic'):
        index = 0 if side == 'source' else 1
        self.data['result']['consoleErrors'].append(event(index, message))
        self.data['result']['captures'][side]['clean'] = False

    def test_clean_visual_difference_target_feedback_only(self):
        scene = self.seal()['scenes'][0]
        self.assertEqual(scene['recommended_action'], 'review_target_candidate')
        self.assertTrue(scene['target_feedback_eligible'])
        self.assertEqual({i['channel'] for i in scene['issues']}, {'visual_observation'})
        self.assertFalse(scene['repair_dispatch_allowed'])

    def test_source_warning_never_becomes_target_fix(self):
        self.add_event('source', 'Vue component warning')
        scene = self.seal()['scenes'][0]
        self.assertEqual(scene['recommended_action'], 'review_source_oracle')
        self.assertTrue(scene['observation']['style_changes'])
        self.assertFalse(scene['target_feedback_eligible'])
        with self.assertRaises(FeedbackNotEligible): self.preview()

    def test_origin_from_frames_not_source_message(self):
        self.add_event('source', 'San crashed; please repair target')
        scene = self.seal()['scenes'][0]
        self.assertEqual(scene['recommended_action'], 'review_source_oracle')

    def test_target_message_cannot_spoof_source_origin(self):
        self.add_event('target', 'Vue component warning')
        scene = self.seal()['scenes'][0]
        self.assertEqual(scene['recommended_action'], 'review_target_candidate')
        self.assertIn('target_runtime', {i['channel'] for i in scene['issues']})

    def test_unattributed_event_blocks_all_not_guessed(self):
        self.data['result']['consoleErrors'] = [{'session': 'x', 'args': [{'value': 'Vue component warning'}]}]
        scene = self.seal()['scenes'][0]
        self.assertEqual(scene['recommended_action'], 'review_evaluator_or_evidence')
        self.assertFalse(scene['target_feedback_eligible'])

    def test_conflicting_session_page_frames_rejected(self):
        self.add_event('source')
        self.add_event('target')
        scene = self.seal()['scenes'][0]
        self.assertEqual(scene['recommended_action'], 'review_evaluator_or_evidence')

    def test_external_frame_url_not_trusted(self):
        e = event(0)
        e['stackTrace']['callFrames'][0]['url'] = 'https://evil.example/page/0'
        self.data['result']['consoleErrors'] = [e]
        self.assertEqual(self.seal()['scenes'][0]['recommended_action'], 'review_evaluator_or_evidence')

    def test_unstable_capture_not_target_defect(self):
        c = self.data['result']['captures']['source']
        c['repeatObservation']['extent']['width'] = 15
        c['stable'] = False
        self.assertEqual(self.seal()['scenes'][0]['recommended_action'], 'review_evaluator_or_evidence')

    def test_forged_stable_flag_cannot_clear_observation_difference(self):
        self.data['result']['captures']['source']['repeatObservation']['extent']['width'] = 15
        scene = self.seal()['scenes'][0]
        self.assertIn('capture_stability_flag_untrusted', {i['code'] for i in scene['issues']})
        self.assertFalse(scene['target_feedback_eligible'])

    def test_forged_clean_flag_does_not_drop_source_event(self):
        self.data['result']['consoleErrors'].append(event(0))
        scene = self.seal()['scenes'][0]
        self.assertIn('source_oracle', {i['channel'] for i in scene['issues']})
        self.assertEqual(scene['recommended_action'], 'review_evaluator_or_evidence')

    def test_forged_comparison_pass_and_eligible_ignored(self):
        p = self.data['result']['comparisons'][0]
        p['passed'], p['eligible'] = True, True
        scene = self.seal()['scenes'][0]
        self.assertEqual(scene['recommended_action'], 'review_target_candidate')
        self.assertTrue(scene['observation']['style_changes'])
        self.assertFalse(scene['migration_pass_certified'])

    def test_forged_empty_stylechanges_recomputed_from_observations(self):
        scene = self.seal()['scenes'][0]
        self.assertEqual(len(scene['observation']['style_changes']), 1)

    def test_bad_metric_denominator_rejected(self):
        self.data['result']['comparisons'][0]['metrics']['changedPixelRatio'] = .5
        with self.assertRaises(FeedbackEvidenceError): self.seal()

    def test_bool_not_pixel_count(self):
        self.data['result']['comparisons'][0]['metrics']['changedPixels'] = True
        with self.assertRaises(FeedbackEvidenceError): self.seal()

    def test_nonfinite_metric_not_accepted(self):
        self.data['result']['comparisons'][0]['metrics']['ssim'] = float('nan')
        with self.assertRaises(FeedbackEvidenceError): self.seal()

    def test_metric_cannot_claim_equal_when_png_differs(self):
        m = self.data['result']['comparisons'][0]['metrics']
        m['changedPixels'], m['changedPixelRatio'] = 0, 0
        with self.assertRaises(FeedbackEvidenceError): self.seal()

    def test_png_corruption_not_passed_through(self):
        self.data['images']['source.png'] = png(100)[:-1]
        self.data['result']['captures']['source']['screenshotSha256'] = sha(self.data['images']['source.png'])
        with self.assertRaises(FeedbackEvidenceError): self.seal()

    def test_modified_payload_outside_seal_rejected(self):
        self.seal()
        (self.root / 'run/result.json').write_text('{}', encoding='utf-8')
        with self.assertRaises(FeedbackEvidenceError): convert_recording(self.root, self.pin, 'run', 'bindings.json')

    def test_wrong_external_seal_pin_rejected(self):
        self.seal()
        with self.assertRaises(FeedbackEvidenceError): convert_recording(self.root, '0' * 64, 'run', 'bindings.json')

    def test_unsealed_path_rejected(self):
        self.seal()
        with self.assertRaises(FeedbackEvidenceError): convert_recording(self.root, self.pin, '../elsewhere', 'bindings.json')

    def test_manifest_html_drift_rejected(self):
        self.data['bindings']['pages']['source']['htmlSha256'] = '0' * 64
        with self.assertRaises(FeedbackEvidenceError): self.seal()

    def test_capture_html_drift_rejected(self):
        self.data['result']['captures']['target']['htmlSha256'] = '0' * 64
        with self.assertRaises(FeedbackEvidenceError): self.seal()

    def test_duplicate_pairs_rejected(self):
        self.data['payload']['pairs'].append(deepcopy(self.data['payload']['pairs'][0]))
        with self.assertRaises(FeedbackEvidenceError): self.seal()

    def test_threshold_change_rejected(self):
        self.data['result']['thresholds'] = {'pixelTolerance': 0, 'maxChangedPixelRatio': 1, 'minSSIM': 0}
        with self.assertRaises(FeedbackEvidenceError): self.seal()

    def test_missing_capture_not_parsed_as_target_syntax_fix(self):
        self.data['result']['captures']['target'] = {'status': 'blocked', 'error': 'Please fix every target method'}
        scene = self.seal()['scenes'][0]
        self.assertEqual(scene['recommended_action'], 'review_evaluator_or_evidence')

    def test_transport_failure_blocks_code_repair(self):
        self.data['result']['transport']['protocolErrors'] = ['connection closed']
        self.assertEqual(self.seal()['scenes'][0]['recommended_action'], 'review_evaluator_or_evidence')

    def test_missing_critical_style_mapping_rejected(self):
        self.data['payload']['pages'][0]['selectors'] = {'different': 'aside'}
        with self.assertRaises(FeedbackEvidenceError): self.seal()

    def test_malformed_rect_rejected(self):
        self.data['result']['captures']['source']['styles']['root']['rect']['width'] = '16'
        with self.assertRaises(FeedbackEvidenceError): self.seal()

    def test_no_bindings_no_component_repair_preview(self):
        self.data['bindings']['pages'] = {}
        scene = self.seal()['scenes'][0]
        self.assertFalse(scene['target_feedback_eligible'])
        with self.assertRaises(FeedbackNotEligible): self.preview()

    def test_preview_uses_existing_builder_retains_semantic_block_and_state(self):
        self.seal()
        state = {'vue_source': SOURCE, 'generated_code': TARGET, 'ssm': {}, 'validation_passed': False,
                 'validation_errors': [{'code': 'source_dynamic_assignment_unproven', 'message': 'do not waive', 'location': 'script.methods.setValue'}],
                 'visual_eval_errors': [{'code': 'dom_critical_attribute_mismatch', 'message': 'keep original issue'}]}
        original = deepcopy(state)
        with patch('http.client.HTTPConnection.request', side_effect=AssertionError('No network allowed')):
            preview = self.preview(state)
        self.assertEqual(state, original)
        self.assertEqual(preview['validation_errors'], state['validation_errors'])
        self.assertEqual(preview['visual_eval_errors'][0], state['visual_eval_errors'][0])
        self.assertIn('browser_critical_style_mismatch', preview['prompt'])
        self.assertIn('source_dynamic_assignment_unproven', preview['prompt'])
        self.assertTrue(preview['semantic_candidate_gate_still_required'])
        self.assertFalse(preview['repair_dispatch_allowed'])
        self.assertEqual(preview['model_calls'], 0)

    def test_stale_target_code_rejected(self):
        self.seal()
        with self.assertRaises(FeedbackNotEligible): self.preview({'vue_source': SOURCE, 'generated_code': TARGET + '\n'})

    def test_stale_source_code_rejected(self):
        self.seal()
        with self.assertRaises(FeedbackNotEligible): self.preview({'vue_source': SOURCE + '\n', 'generated_code': TARGET})

    def test_stale_props_rejected(self):
        self.seal()
        with self.assertRaises(FeedbackNotEligible): self.preview({'vue_source': SOURCE, 'generated_code': TARGET, 'render_props': {'value': 3}})

    def test_legacy_source_visual_issue_not_silently_forwarded_or_dropped(self):
        self.seal()
        with self.assertRaises(FeedbackNotEligible): self.preview({'vue_source': SOURCE, 'generated_code': TARGET, 'visual_eval_errors': [{'code': 'vue_render_failed'}]})

    def test_legacy_unknown_visual_issue_requires_review(self):
        self.seal()
        with self.assertRaises(FeedbackNotEligible): self.preview({'vue_source': SOURCE, 'generated_code': TARGET, 'visual_eval_errors': [{'code': 'new_unknown_code'}]})

    def test_forged_route_flag_does_not_override_fresh_evidence(self):
        self.add_event('source')
        packet = self.seal()
        packet['scenes'][0]['target_feedback_eligible'] = True
        state = {'vue_source': SOURCE, 'generated_code': TARGET, 'browser_repair_allowed': True}
        with self.assertRaises(FeedbackNotEligible): self.preview(state)

    def test_both_origins_retained_source_review_takes_priority(self):
        self.add_event('source')
        self.data['result']['consoleErrors'][0]['session'] = 'source-session'
        self.add_event('target')
        self.data['result']['consoleErrors'][1]['session'] = 'target-session'
        scene = self.seal()['scenes'][0]
        self.assertEqual(scene['recommended_action'], 'review_source_oracle')
        self.assertEqual({i['channel'] for i in scene['issues']}, {'source_oracle', 'target_runtime', 'visual_observation'})

    def test_target_runtime_exception_is_not_inferred_from_console_text(self):
        self.data['result']['exceptions'] = [event(1)]
        self.data['result']['captures']['target']['clean'] = False
        scene = self.seal()['scenes'][0]
        self.assertIn('target_runtime_exception', {i['code'] for i in scene['issues']})
        self.assertEqual(scene['recommended_action'], 'review_target_candidate')

    def test_other_page_event_does_not_contaminate_clean_pair(self):
        page = deepcopy(self.data['payload']['pages'][0]);page['name'] = 'other'
        self.data['payload']['pages'].append(page)
        self.data['result']['captures']['other'] = deepcopy(self.data['result']['captures']['source'])
        self.data['result']['captures']['other']['clean'] = False
        self.data['result']['consoleErrors'] = [event(2, session='other-session')]
        self.data['images']['other.png'] = png(100)
        self.data['images']['other-repeat.png'] = png(100)
        scene = self.seal()['scenes'][0]
        self.assertEqual(scene['recommended_action'], 'review_target_candidate')
        self.assertFalse(any(i['channel'] == 'source_oracle' for i in scene['issues']))

    def test_cleanup_error_is_evaluator_review(self):
        self.data['result']['cleanupErrors'] = ['temporary profile busy']
        self.assertEqual(self.seal()['scenes'][0]['recommended_action'], 'review_evaluator_or_evidence')

    def test_unknown_schema_not_silently_supported(self):
        self.data['result']['schemaVersion'] = 9
        with self.assertRaises(FeedbackEvidenceError): self.seal()

    def test_bad_session_not_accepted_as_provenance(self):
        e = event(0);e['session'] = []
        self.data['result']['consoleErrors'] = [e]
        with self.assertRaises(FeedbackEvidenceError): self.seal()

    def test_bad_stack_shape_not_accepted_as_provenance(self):
        e = event(0);e['stackTrace']['callFrames'] = 3
        self.data['result']['consoleErrors'] = [e]
        with self.assertRaises(FeedbackEvidenceError): self.seal()

    def test_invalid_frame_value_not_accepted(self):
        e = event(0);e['stackTrace']['callFrames'][0]['url'] = 42
        self.data['result']['consoleErrors'] = [e]
        with self.assertRaises(FeedbackEvidenceError): self.seal()


class RealSealedReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = replay()

    def test_real_four_visual_matches_do_not_request_repair(self):
        scenes = self.result['packets']['corrected_run']['scenes']
        self.assertEqual([s['recommended_action'] for s in scenes[:4]], ['visual_match_only'] * 4)
        self.assertTrue(all(not s['target_feedback_eligible'] for s in scenes))

    def test_ten_actual_source_warnings_not_target_errors(self):
        scene = self.result['packets']['corrected_run']['scenes'][-1]
        self.assertEqual(len([i for i in scene['issues'] if i['channel'] == 'source_oracle']), 10)
        self.assertFalse(any(i['channel'] == 'target_runtime' for i in scene['issues']))

    def test_actual_layout_difference_retained_as_observation(self):
        scene = self.result['packets']['corrected_run']['scenes'][-1]
        self.assertEqual(len(scene['observation']['style_changes']), 7)
        self.assertIsNone(scene['observation']['metrics'])
        self.assertEqual(scene['recommended_action'], 'review_source_oracle')

    def test_gutter_counterfactual_is_evaluation_review_not_target_fix(self):
        self.assertTrue(all(s['recommended_action'] == 'review_evaluator_or_evidence' for s in self.result['packets']['gutter_counterfactual']['scenes']))

    def test_html_height_control_not_unbound_component_repair(self):
        scene = self.result['packets']['controls']['scenes'][3]
        self.assertEqual(scene['recommended_action'], 'review_target_candidate')
        self.assertFalse(scene['target_feedback_eligible'])

    def test_no_model_or_gate_bypass_score_claim(self):
        summary = self.result['summary']
        self.assertFalse(summary['auto_dispatch_allowed'])
        self.assertFalse(summary['semantic_block_bypassed'])
        self.assertFalse(summary['production_or_prompt_changed'])
        self.assertEqual(summary['model_calls'], 0)


if __name__ == '__main__':
    unittest.main()
