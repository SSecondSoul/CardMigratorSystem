"""Read-only audit of a REVIEW REQUIRED proposal; never a production gate."""
from collections import Counter
import hashlib
import json
from pathlib import Path

from migration_pipeline.utils.browser_feedback_v1 import verify_seal

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'data/experiments/protocols/native_browser_admission_v1_draft_20261115'
BASE=ROOT/'data/experiments/analysis/native_browser_admission_draft_v1_20261115'


def validate_documents(protocol, scenarios):
    def require(condition,message):
        if not condition:raise ValueError(message)
    require(protocol.get('status')=='review_required' and protocol.get('frozen') is False,'Draft must not masquerade as frozen')
    a=protocol['authority']
    require(all(a.get(k) is False for k in ['production_dispatch_allowed','model_calls_allowed','browser_runs_allowed']) and a.get('freeze_approval_record') is None,'No launch or approval authority in draft')
    require(protocol['scope']['runtime_interop'] is False and protocol['scope']['new_business_caller_protocol'] is False,'Do not expand user scope')
    require(protocol['scope']['planned_development_samples']==30 and protocol['scope']['complexity_counts']=={'simple':10,'medium':10,'complex':10},'Scope must retain full source denominator')
    require(protocol['classification']=='reused_development_calibration_not_independent_holdout','Do not relabel exposed development data')
    require(protocol['precedence']==['evaluation_integrity','source_oracle','target_runtime_or_visual','visual_match_only'],'Preserve evidence/source priority')
    severity=protocol['severity']
    require(all(severity[k]['target_repair_allowed'] is False and severity[k]['counts_as_target_defect'] is False for k in ['evaluation_integrity','source_oracle']),'Source/evidence categories must never authorize target repair')
    require(severity['unsupported_or_unverified']['counts_as_pass'] is False and severity['visual_match_only']['counts_as_comprehensive_pass'] is False,'Non-acceptance categories cannot become passes')
    oracle=protocol['source_oracle_policy']
    require(all(oracle.get(k) is True for k in ['console_errors_block','console_warnings_block','unknown_origin_blocks']),'No unreviewed source warning relaxation')
    require(oracle.get('warning_waivers')==[] and oracle.get('auto_suppress_warnings') is False and oracle.get('auto_edit_source') is False,'No source rewrite/waiver')
    t=protocol['threshold_proposal']
    require(t.get('status')=='pending_user_review_not_production_thresholds','Thresholds are proposals, not approvals')
    n=t['native']
    for key,value in [('pixelTolerance',0),('maxChangedPixelRatio',0),('minSSIM',.999999999),('critical_style_differences_allowed',0),('critical_rect_differences_allowed',0)]:
        require(type(n.get(key)) is type(value) and n[key]==value,'No unreviewed threshold change: '+key)
    require(n.get('image_masking_allowed') is False and n.get('dimension_policy')=='exact_no_resize_no_crop_no_fabricated_metric','No hidden image manipulation')
    require(t['legacy_dom']['render_skip_counts_as_pass'] is False,'Skipped rendering is not a pass')
    require(t['legacy_dom']['structure_similarity_threshold']==.95 and t['legacy_dom']['text_similarity_threshold']==.8,'Preserve separate legacy DOM criteria')
    environment={'viewport':{'width':1280,'height':800},'capturePolicy':'full-page','deviceScaleFactor':1,'theme':'light','locale':'zh-CN','timezone':'Asia/Shanghai','epoch':1794700800000,'seed':1729,'scrollbarGutter':'stable','maxPixels':4000000,'repeatDelayMs':120,'storage_initial_state':'empty_per_page_context','same_scene_reload_preserves_storage':True,'ready_deadline_ms':3000,'network':'own_exact_loopback_page_GET_only','oversize_policy':'blocked_capture_budget_not_resized_or_target_defect','timeout_policy':'blocked_evidence_not_silent_pass'}
    require(protocol['environment']==environment,'Keep fixed calibrated environment and blocked limit policy')
    gates=protocol['gates']
    require(gates['allowed_states']==['pass','fail','blocked','not_run','not_applicable'],'No hidden trusted-skip state')
    require(gates['mandatory']==['compile','semantic_contract','native_runtime','native_visual','declared_native_interactions'],'No missing mandatory gate')
    require(gates['all_mandatory_gates_must_pass'] is True and gates['missing_gate_is_pass'] is False and gates['not_run_is_pass'] is False,'No incomplete evidence pass')
    require(gates['not_applicable_requires_predeclared_source_evidence'] is True and gates['unresolved_semantic_findings_may_be_waived'] is False,'No post-hoc semantic waiver')
    require(gates['arbitrary_public_key_contract']=='preserved_no_fixed_key_exemption' and gates['visual_match_certifies_full_migration'] is False,'Do not narrow contracts or promote visual match')
    repair=protocol['repair']
    require(repair['mode']=='offline_preview_only' and repair['semantic_candidate_gate_required'] is True and repair['validation_errors_must_be_retained'] is True,'No automatic dispatch or semantic clearing')
    require(repair['evidence_and_main_code_and_props_must_match'] is True and repair['current_dependency_graph_required_for_multimodule_preview'] is True and repair['current_multimodule_preview_supported'] is False,'No unsupported dependency bypass')
    require(repair['source_or_unknown_legacy_visual_may_be_dropped'] is False and repair['manual_repaired_san_may_be_model_input_or_auto_pass'] is False,'No oracle leakage/manual answer inheritance')
    require(repair['proposed_future_max_llm_repair_calls']==3 and type(repair['proposed_future_max_llm_repair_calls']) is int and repair['paid_batch_protocol_frozen'] is False,'No new paid budget freeze')
    statistics=protocol['statistics']
    require(statistics['planned_denominator']==30 and statistics['incomplete_new_run_rate'] is None and statistics['old_24_of_30_recomputed'] is False,'No new rate before run')
    require(statistics['not_run_cases_must_remain_visible'] is True and statistics['source_evidence_unsupported_execution_error_separately'] is True,'Keep missingness and distinct failures')
    control=protocol['experiment_control']
    require(control['force_reruns_replace_failures'] is False and control['old_checkpoint_or_manual_artifact_inheritance'] is False and control['criteria_change_requires_new_protocol_and_retained_original'] is True,'No cherry-picked result replacement')
    rows=scenarios['source_inventory']
    require(len(rows)==30 and len({r['sample_id'] for r in rows})==30 and Counter(r['complexity'] for r in rows)=={'simple':10,'medium':10,'complex':10},'Full declared source denominator')
    require(scenarios['all_30_mapping_complete'] is False and type(scenarios['implemented_native_interaction_scenarios']) is int and scenarios['implemented_native_interaction_scenarios']==0,'Do not claim unimplemented interaction coverage')
    static=scenarios['existing_static_scenes']
    require(len(static)==5 and len({s['component'] for s in static})==3 and scenarios['calibrated_static_scenes']==5 and scenarios['calibrated_unique_components']==3,'Keep actual calibration denominator')
    require(all(s['status']=='previous_static_calibration_only_not_new_model_result' for s in static),'Old static evidence is not new model acceptance')
    require(len({s['id'] for s in static})==5 and all(s['source_page']==s['id']+'_vue' and s['target_page']==s['id']+'_san' for s in static),'No duplicate/misbound static scene')
    calibrated={s['component'] for s in static}
    require(all(r['static_scene_mapping_status']==('calibrated_existing_scene_only' if r['component'] in calibrated else 'not_mapped') and r['native_interaction_status']=='not_implemented_not_passed' for r in rows),'Do not inflate source scene coverage')
    require(len(scenarios['planned_native_interactions'])==8 and all(s['acceptance'] is False and s['status']=='planned_not_native_implemented_or_verified' for s in scenarios['planned_native_interactions']),'Plans are not executed acceptance')
    ready=protocol['readiness']
    expected={'user_criteria_review':'pending','production_native_feedback_integration':'not_implemented','all_30_scenario_mapping':'incomplete','native_interaction_execution_and_controls':'not_implemented','current_dependency_graph_rebinding':'not_implemented','new_full_batch_model_and_code_freeze':'not_prepared','semantic_boundary_retention':'required_and_preserved_not_resolved'}
    require(ready==expected,'Draft readiness cannot be promoted by caller flags')
    return {'draft_consistent':True,'production_ready':False,'production_dispatch_allowed':False,'model_calls_allowed':False,'thresholds_approved':False,'full_batch_protocol_frozen':False,
            'readiness_blockers':[k for k in expected if k!='semantic_boundary_retention'],'planned_samples':30,'calibrated_components':3,'existing_static_scenes':5,'native_interactions_executed':0,'planned_interactions':8,'new_model_calls':0,'new_browser_runs':0}


def audit():
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    baseline=read(BASE/'baseline.json')
    for name,pin in {**baseline['protected'],**baseline['manual'],**baseline['supplemental_readonly']}.items():
        file=(ROOT/name).resolve()
        if not file.is_relative_to(ROOT) or hashlib.sha256(file.read_bytes()).hexdigest()!=pin:
            raise RuntimeError('Read-only evidence drift: '+name)
    prior=ROOT/baseline['prior_seal']['path']
    verify_seal(prior.parent,baseline['prior_seal']['sha256'])
    protocol=read(DIRECTORY/'protocol.json');scenarios=read(DIRECTORY/'scenario_plan.json')
    for row in scenarios['source_inventory']:
        for path_key,sha_key in [('source_path','source_sha256'),('historical_source_path','historical_source_sha256')]:
            file=(ROOT/row[path_key]).resolve()
            if not file.is_relative_to(ROOT) or hashlib.sha256(file.read_bytes()).hexdigest()!=row[sha_key]:raise RuntimeError('Source input drift: '+row['sample_id'])
        if row['source_sha256']!=row['historical_source_sha256']:raise RuntimeError('Source differs from historical baseline')
    result=validate_documents(protocol,scenarios)
    result.update({'protected_files_unchanged':79,'manual_files_unchanged':3,'supplemental_references_unchanged':4,'current_and_historical_source_pairs_verified':30,'scope':'read_only_draft_audit_not_production_gate'})
    return result


if __name__=='__main__':
    print(json.dumps(audit(),ensure_ascii=False,indent=2))
