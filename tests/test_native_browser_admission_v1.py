"""Draft checks are not production approval and do not execute components."""
from copy import deepcopy
import json
import unittest

from migration_pipeline.audit_native_browser_admission_v1 import DIRECTORY, audit, validate_documents


class DraftContractTests(unittest.TestCase):
    def setUp(self):
        self.protocol=json.loads((DIRECTORY/'protocol.json').read_text(encoding='utf-8'))
        self.scenes=json.loads((DIRECTORY/'scenario_plan.json').read_text(encoding='utf-8'))

    def check(self):return validate_documents(self.protocol,self.scenes)
    def reject(self):
        with self.assertRaises(ValueError):self.check()

    def test_consistent_draft_is_not_production_ready(self):
        r=self.check();self.assertTrue(r['draft_consistent']);self.assertFalse(r['production_ready']);self.assertFalse(r['production_dispatch_allowed'])
    def test_six_readiness_gaps_stay_visible(self):self.assertEqual(len(self.check()['readiness_blockers']),6)
    def test_no_model_or_browser_execution(self):
        r=self.check();self.assertFalse(r['model_calls_allowed']);self.assertEqual(r['new_model_calls'],0);self.assertEqual(r['new_browser_runs'],0)
    def test_cannot_claim_frozen_by_flag(self):self.protocol['frozen']=True;self.reject()
    def test_cannot_claim_approved_by_status(self):self.protocol['status']='approved';self.reject()
    def test_cannot_enable_dispatch(self):self.protocol['authority']['production_dispatch_allowed']=True;self.reject()
    def test_cannot_enable_paid_calls(self):self.protocol['authority']['model_calls_allowed']=True;self.reject()
    def test_cannot_invent_approval_record(self):self.protocol['authority']['freeze_approval_record']='approved';self.reject()
    def test_no_runtime_interop_extension(self):self.protocol['scope']['runtime_interop']=True;self.reject()
    def test_no_new_business_protocol(self):self.protocol['scope']['new_business_caller_protocol']=True;self.reject()
    def test_not_independent_holdout(self):self.protocol['classification']='independent_holdout';self.reject()
    def test_source_precedes_target_feedback(self):self.protocol['precedence'].reverse();self.reject()
    def test_no_source_warning_suppression(self):
        self.protocol['source_oracle_policy']['console_warnings_block']=False;self.reject()
        self.protocol['source_oracle_policy']['console_warnings_block']=True
        self.protocol['severity']['source_oracle']['target_repair_allowed']=True;self.reject()
    def test_no_source_warning_waiver(self):self.protocol['source_oracle_policy']['warning_waivers']=['Duplicate keys'];self.reject()
    def test_no_source_auto_edit(self):self.protocol['source_oracle_policy']['auto_edit_source']=True;self.reject()
    def test_no_threshold_promotion_without_review(self):self.protocol['threshold_proposal']['status']='production';self.reject()
    def test_no_pixel_tolerance_relaxation(self):self.protocol['threshold_proposal']['native']['pixelTolerance']=5;self.reject()
    def test_no_ratio_relaxation(self):self.protocol['threshold_proposal']['native']['maxChangedPixelRatio']=.01;self.reject()
    def test_no_ssim_relaxation(self):self.protocol['threshold_proposal']['native']['minSSIM']=.95;self.reject()
    def test_boolean_not_numeric_threshold(self):self.protocol['threshold_proposal']['native']['pixelTolerance']=False;self.reject()
    def test_no_image_masking(self):self.protocol['threshold_proposal']['native']['image_masking_allowed']=True;self.reject()
    def test_no_skipped_render_pass(self):self.protocol['threshold_proposal']['legacy_dom']['render_skip_counts_as_pass']=True;self.reject()
    def test_no_environment_theme_change(self):self.protocol['environment']['theme']='dark';self.reject()
    def test_no_environment_time_change(self):self.protocol['environment']['epoch']+=1;self.reject()
    def test_no_storage_sharing(self):self.protocol['environment']['storage_initial_state']='shared_previous_user_profile';self.reject()
    def test_missing_mandatory_gate_not_accepted(self):self.protocol['gates']['mandatory'].remove('declared_native_interactions');self.reject()
    def test_not_run_cannot_pass(self):
        self.protocol['gates']['not_run_is_pass']=True;self.reject()
        self.protocol['gates']['not_run_is_pass']=False
        self.protocol['gates']['allowed_states'].append('trusted_skip');self.reject()
    def test_no_posthoc_not_applicable(self):self.protocol['gates']['not_applicable_requires_predeclared_source_evidence']=False;self.reject()
    def test_no_arbitrary_key_contract_narrowing(self):self.protocol['gates']['arbitrary_public_key_contract']='six_keys_only';self.reject()
    def test_no_semantic_waiver(self):self.protocol['gates']['unresolved_semantic_findings_may_be_waived']=True;self.reject()
    def test_no_visual_match_as_full_migration(self):self.protocol['gates']['visual_match_certifies_full_migration']=True;self.reject()
    def test_no_manual_correct_answer_inheritance(self):self.protocol['repair']['manual_repaired_san_may_be_model_input_or_auto_pass']=True;self.reject()
    def test_no_unknown_legacy_diagnostic_drop(self):self.protocol['repair']['source_or_unknown_legacy_visual_may_be_dropped']=True;self.reject()
    def test_multimodule_binding_gap_not_hidden(self):self.protocol['repair']['current_multimodule_preview_supported']=True;self.reject()
    def test_budget_six_not_silently_imported(self):self.protocol['repair']['proposed_future_max_llm_repair_calls']=6;self.reject()
    def test_no_new_rate_before_run(self):self.protocol['statistics']['incomplete_new_run_rate']=1;self.reject()
    def test_no_omitting_pending_cases(self):self.protocol['statistics']['not_run_cases_must_remain_visible']=False;self.reject()
    def test_no_force_cherry_pick(self):self.protocol['experiment_control']['force_reruns_replace_failures']=True;self.reject()
    def test_no_dropping_sample_denominator(self):
        self.protocol['scope']['planned_development_samples']=29;self.reject()
        self.protocol['scope']['planned_development_samples']=30
        self.scenes['source_inventory'].pop();self.reject()
    def test_no_reusing_sample_id(self):self.scenes['source_inventory'][1]['sample_id']=self.scenes['source_inventory'][0]['sample_id'];self.reject()
    def test_no_inventing_interaction_completion(self):self.scenes['implemented_native_interaction_scenarios']=8;self.reject()
    def test_no_plan_as_acceptance(self):self.scenes['planned_native_interactions'][0]['acceptance']=True;self.reject()
    def test_no_inflated_static_coverage(self):self.scenes['source_inventory'][1]['static_scene_mapping_status']='calibrated_existing_scene_only';self.reject()
    def test_no_duplicate_static_scene(self):self.scenes['existing_static_scenes'][1]=deepcopy(self.scenes['existing_static_scenes'][0]);self.reject()
    def test_no_readiness_flag_bypass(self):self.protocol['readiness']['production_native_feedback_integration']='done';self.reject()
    def test_readonly_audit_checks_actual_frozen_and_live_sources(self):
        r=audit();self.assertEqual(r['current_and_historical_source_pairs_verified'],30);self.assertFalse(r['production_ready']);self.assertEqual(r['protected_files_unchanged'],79)


if __name__=='__main__':unittest.main()
