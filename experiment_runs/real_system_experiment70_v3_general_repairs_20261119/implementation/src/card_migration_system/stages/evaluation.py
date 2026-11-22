"""Multi-dimensional target checks. Missing coverage never becomes equivalence."""
from .structure import tree_distance,tree_differences,compare_styles,ssm_template_tree,target_template_tree
from .dom_comparison import compare_dom,compare_control_state,control_gate_evidence,proven_control_diagnostic_refinement


def assess(static,browser,actions,thresholds,ssm=None):
    ast=tree_distance(browser['source_ast']['tree'],browser['target_ast']['tree'])
    expected_tree=ssm_template_tree(ssm,browser['source_ast'].get('class_bindings')) if ssm and 'template' in ssm else browser['source_ast']['tree']
    actual_tree=target_template_tree(browser['target_ast']['tree']) if ssm and 'template' in ssm else browser['target_ast']['tree']
    structure=tree_distance(expected_tree,actual_tree)
    source=browser['vue'];target=browser['san'];image=browser['image']
    dom_comparison=compare_dom(source['snapshots'][0]['dom'],target['snapshots'][0]['dom'],browser.get('comparison_policy'))
    dom=dom_comparison['metric']
    styles=compare_styles(source['snapshots'][0]['styles'],target['snapshots'][0]['styles'])
    controls=compare_control_state(source['snapshots'][0]['styles'],target['snapshots'][0]['styles'])
    source_bad=bool(source['errors'] or source['warnings'] or source['blocked_requests'] or source['evidence_overflow'])
    target_bad=bool(target['errors'] or target['warnings'] or target['blocked_requests'] or target['evidence_overflow'])
    interaction=[]
    for a,b in zip(source['snapshots'][1:],target['snapshots'][1:]):
        comparison=compare_dom(a['dom'],b['dom'],browser.get('comparison_policy'))
        diff=comparison['metric'];css=compare_styles(a['styles'],b['styles'])
        # Form control state is not always reflected in HTML attributes.
        live_controls=compare_control_state(a['styles'],b['styles'])
        interaction.append({'name':a['name'],'dom':diff,'raw_dom':comparison['raw_metric'],
            'dom_differences':comparison['differences'],'raw_dom_differences':comparison['raw_differences'],
            'normalization_changes':comparison['normalization_changes'],'styles':css,'control_state_equal':live_controls['equal'],
            'representation_differences':comparison['representation_differences'],
            'control_state_differences':live_controls['differences'],
            'passed':diff['similarity']>thresholds['structure'] and css['similarity']>thresholds['ui'] and live_controls['equal']})
    ui=max(0,min(100,100*(.5*image['ssim']+.3*(1-image['different_pixel_ratio'])+.2*styles['similarity'])))
    dimensions={
        'static':'pass' if static['validation_passed'] else 'fail',
        'compile_runtime':'fail' if target_bad else 'pass',
        'structure':'pass' if structure['similarity']>thresholds['structure'] and dom['similarity']>thresholds['structure'] and controls['equal'] else 'fail',
        'visual':'pass' if ui/100>thresholds['ui'] and image['different_pixel_ratio']<thresholds['pixel_difference'] else 'fail',
        'interaction':('pass' if all(i['passed'] for i in interaction) else 'fail') if actions else 'not_run',
        'source_baseline':'blocked' if source_bad else 'pass'}
    required=['static','compile_runtime','structure','visual','source_baseline']+(['interaction'] if actions else [])
    diagnostics=static['validation_errors']+[{'code':'target_browser_error','message':m} for m in target['errors']]
    if structure['similarity']<=thresholds['structure']:
        diagnostics.append({'code':'template_structure_mismatch','message':'SSM/target template projection differs.',
            'differences':tree_differences(expected_tree,actual_tree)})
    if dom['similarity']<=thresholds['structure']:
        diagnostics.append({'code':'rendered_dom_mismatch','message':'Rendered DOM differs; preserve source structure and observable attributes.',
            'differences':dom_comparison['differences'],'raw_differences':dom_comparison['raw_differences'],
            'representation_differences':dom_comparison['representation_differences'],
            'comparison_policy':dom_comparison['policy'],'live_control_state':controls,
            'interpretation':'Equal live values do not prove HTML attribute presence equivalent; keep strict comparison unless an explicit policy is approved.'})
    if not controls['equal']:
        diagnostics.append({'code':'rendered_control_position_mismatch' if controls['values_equal_in_order'] else 'rendered_control_state_mismatch',
            'message':'Control paths differ; captured live values match in order. Inspect actual wrapper/structure changes.' if controls['values_equal_in_order'] else 'Initial live control values/types/counts differ even if screenshots or HTML attributes match.',
            'differences':controls['differences']})
    for item in interaction:
        if not item['passed']:
            diagnostics.append({'code':'representative_interaction_mismatch','message':'Configured action observation differs.',
                'action':item['name'],'dom_differences':item['dom_differences'],
                'style_differences':item['styles']['differences'][:30],'control_state_equal':item['control_state_equal'],
                'control_state_differences':item['control_state_differences']})
    passed=all(dimensions[key]=='pass' for key in required)
    return {'dimensions':dimensions,'required':required,'passed':passed,'source_blocked':source_bad,
        'structure_ted':structure,'source_ast_ted':ast,'dom_ted':dom,'styles':styles,'ui_restoration':ui,
        'raw_dom_ted':dom_comparison['raw_metric'],'dom_differences':dom_comparison['differences'],
        'raw_dom_differences':dom_comparison['raw_differences'],'dom_comparison_policy':dom_comparison['policy'],
        'dom_normalization_changes':dom_comparison['normalization_changes'],
        'dom_representation_differences':dom_comparison['representation_differences'],
        'initial_control_state':controls,
        'control_gate_evidence':control_gate_evidence(source['snapshots'][0],target['snapshots'][0],
            source_bad or target_bad),
        'structure_differences':tree_differences(expected_tree,actual_tree),
        'structure_projection':'ssm_v3_symmetric_class_tokens_ordered_conditional_siblings_v4',
        'projection_limitations':['mixed_text_child_order_checked_by_legacy_static_and_rendered_dom_not_ssm_ted','key_identity_not_proven_by_ted','script_binding_event_style_dimensions_checked_by_legacy_validator'],
        'ssim':image['ssim'],'different_pixel_ratio':image['different_pixel_ratio'],'interaction':interaction,
        'thresholds':thresholds,'coverage':'configured_props_and_representative_actions_only',
        'functional_equivalence':'not_proven','embedding_similarity':None,
        'source_method_contracts':static.get('source_method_contracts',[]),
        'diagnostics':diagnostics,
        'source_diagnostics':source['errors']+source['warnings'],
        'target_warnings':target['warnings'],'timing_ms':{'source':source['render_ms'],'target':target['render_ms']}}


def candidate_decision(previous,candidate):
    # No trading a formerly passing required dimension for a higher aggregate score.
    regressions=[k for k,v in previous['dimensions'].items() if v=='pass' and candidate['dimensions'].get(k)!='pass']
    old_errors={item['code'] for item in previous.get('diagnostics',[])}
    new_errors={item['code'] for item in candidate.get('diagnostics',[])}
    added=new_errors-old_errors
    old_syntax=previous.get('syntax',{});new_syntax=candidate.get('syntax',{})
    if old_syntax.get('status')=='fail' and not candidate['source_blocked'] and not regressions:
        if new_syntax.get('status')=='pass':
            # Previously deferred semantic checks are newly observable, not a regression.
            # The candidate remains failed unless ALL required checks now pass.
            return {'accepted':True,'reason':'syntax_unblocked_semantic_checks',
                    'newly_observed_errors':sorted(added),'migration_passed':candidate['passed']}
        if new_syntax.get('status')=='fail' and not added and not new_syntax.get('overflow') and not old_syntax.get('overflow'):
            improved=new_syntax['diagnostic_count']<old_syntax['diagnostic_count']
            return {'accepted':improved,'reason':'syntax_diagnostics_reduced' if improved else 'no_syntax_progress'}
    refinements=[]
    if ('rendered_control_position_mismatch' in added and 'rendered_control_state_mismatch' in old_errors
            and 'rendered_control_state_mismatch' not in new_errors
            and proven_control_diagnostic_refinement(previous,candidate)):
        added.remove('rendered_control_position_mismatch')
        refinements.append('rendered_control_state_mismatch_to_existing_position_defect')
    if candidate['source_blocked'] or regressions or added:
        return {'accepted':False,'reason':'candidate_regression','dimensions':regressions,'added_errors':sorted(added)}
    def score(value):return (sum(v=='pass' for v in value['dimensions'].values()),-len(value.get('diagnostics',[])),
        value['structure_ted']['similarity'],value.get('dom_ted',{}).get('similarity',0),value['ui_restoration'])
    decision={'accepted':score(candidate)>score(previous),'reason':'strict_improvement' if score(candidate)>score(previous) else 'no_strict_improvement'}
    if refinements:decision.update(diagnostic_refinements=refinements,migration_passed=candidate['passed'])
    return decision
