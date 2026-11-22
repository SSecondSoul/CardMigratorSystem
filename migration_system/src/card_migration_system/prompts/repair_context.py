"""Model-only repair evidence projection; never changes evaluation or rule inputs.

Keep the vendored repair instructions/contract builder. Replace its full SSM
dump only at the transmission boundary, after source-aware contract extraction.
Unknown errors retain all SSM in compact JSON. Omitted evidence is not success.
"""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json

from ..application.service import ServiceError

POLICY='repair-evidence-projection-v1'


def encoded(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def fingerprint(value):return sha256(encoded(value).encode()).hexdigest()


def bounded(value,depth=0):
    """Bound observations, not source code/methods/defaults. Mark every omission."""
    if isinstance(value,str):
        return value if len(value)<=400 else {'excerpt':value[:400],'original_chars':len(value),'truncated':True}
    if isinstance(value,(int,float,bool)) or value is None:return value
    if depth>=4:return {'omitted_nested_observation':True,'sha256':fingerprint(value)}
    if isinstance(value,list):
        result=[bounded(item,depth+1) for item in value[:12]]
        if len(value)>12:result.append({'omitted_items':len(value)-12})
        return result
    if isinstance(value,dict):
        keys=sorted(value)
        result={key:bounded(value[key],depth+1) for key in keys[:20]}
        if len(keys)>20:result['_omitted_fields']=keys[20:]
        return result
    return str(value)[:400]


def observations(items,limit=12):
    unique={encoded(item):item for item in items if isinstance(item,dict)}
    values=list(unique.values())
    return {'recorded_count':len(items),'unique_count':len(values),
            'examples':[bounded(item) for item in values[:limit]],
            'omitted_unique_count':max(0,len(values)-limit)}


def style_summary(styles):
    """All property groups/counts, bounded path + actual/expected examples.

    The evaluator's 500-row cap is upstream, NOT evidence of only 500 errors.
    Keep its truncation flag and scores; never recalculate quality here.
    """
    rows=styles.get('differences',[]);groups={}
    for row in rows:
        prop=str(row.get('property','unknown'))
        group=groups.setdefault(prop,{'count':0,'kinds':Counter(),'examples':[],'_seen':set()})
        group['count']+=1
        kind='target_missing' if row.get('target') is None else ('source_missing' if row.get('source') is None else 'changed')
        group['kinds'][kind]+=1
        signature=encoded(row)
        if signature not in group['_seen'] and len(group['examples'])<2:
            group['examples'].append(bounded(row));group['_seen'].add(signature)
    names=sorted(groups)
    return {**{k:styles[k] for k in ('similarity','compared_properties','matching') if k in styles},
        'upstream_truncated':bool(styles.get('truncated',False)),
        'recorded_difference_count':len(rows),'property_group_count':len(names),
        'groups':[{k:v for k,v in {'property':name,**groups[name]}.items() if k!='_seen'} for name in names[:24]],
        'omitted_property_groups':names[24:],
        'sampling_policy':'at_most_two_recorded_paths_per_property_not_a_quality_verdict'}


def compact_issues(issues):
    result=[];seen={}
    for item in issues:
        # Preserve distinct locations. Only exact repeats are collapsed.
        signature=encoded(item)
        if signature in seen:
            seen[signature]['details']['duplicate_count']+=1
            continue
        issue={k:deepcopy(item[k]) for k in ('code','message','severity','location','suggestion') if k in item}
        for field in ('message','suggestion'):
            if isinstance(issue.get(field),str) and len(issue[field])>1200:
                issue[field]=issue[field][:1200]+' [truncated; full diagnostic retained in local evaluation]'
        details={'duplicate_count':1}
        for key,value in item.get('details',{}).items():
            details[key]=style_summary(value) if key=='styles' and isinstance(value,dict) else bounded(value)
        for key in ('differences','dom_differences','raw_dom_differences','control_state_differences','representation_differences'):
            if key in item:details[key]=observations(item[key])
        if 'style_differences' in item:details['style_summary']=style_summary({'differences':item['style_differences']})
        for key in ('comparison_policy','action','live_control_state'):
            if key in item:details[key]=bounded(item[key])
        issue['details']=details;seen[signature]=issue;result.append(issue)
    return result


def model_evidence(evaluation):
    errors=compact_issues(evaluation.get('diagnostics',[]))
    visual=[]
    if evaluation['dimensions']['visual'] not in ('pass','not_run'):
        # Per-action observations are already in representative interaction
        # diagnostics. Do not serialize that same evidence a second time.
        visual=[{'code':'visual_mismatch','message':'Repair observed visual differences; original thresholds still apply.',
            'details':{**{k:evaluation[k] for k in ('ui_restoration','different_pixel_ratio','ssim') if k in evaluation},
                'styles':style_summary(evaluation.get('styles',{})),
                'interaction_counts':dict(Counter('pass' if item.get('passed') else 'fail'
                                                 for item in evaluation.get('interaction',[])))}}]
    return errors,visual


TEMPLATE_CODES={'invalid_s_for_key_binding','event_arguments_not_landed','missing_event_bindings',
    'missing_event_handlers','rendered_dom_mismatch','rendered_control_state_mismatch',
    'rendered_control_position_mismatch','template_structure_mismatch','dom_child_order_mismatch',
    'representative_interaction_mismatch','hidden_template_reactive_dependency',
    'source_render_dependency_not_landed','dom_structure_similarity_low',
    'dom_critical_attribute_mismatch','source_class_binding_not_landed'}
SCRIPT_CODES={'source_semantic_analysis_unavailable','source_data_initialization_phase_not_landed','source_dynamic_assignment_unproven','event_arguments_not_landed',
    'missing_event_bindings','missing_event_handlers','rendered_control_state_mismatch',
    'hidden_template_reactive_dependency','source_render_dependency_not_landed',
    'missing_prop_defaults','missing_datatypes_for_props','datatypes_type_mismatch',
    'missing_data_types','nested_state_mutation','lifecycle_behavior_not_landed',
    'missing_lifecycle_mapping','invalid_san_computed_instance_method_call','invalid_san_computed_namespace_access',
    'invalid_san_init_data_store_access','missing_inline_prop_dependent_initialization'}
REACTIVE_CODES={'source_data_initialization_phase_not_landed','hidden_template_reactive_dependency','source_render_dependency_not_landed',
    'invalid_san_computed_instance_method_call','nested_state_mutation'}


def relevant_ssm(ssm,evaluation):
    codes={item.get('code','') for item in evaluation.get('diagnostics',[])}
    known=TEMPLATE_CODES|SCRIPT_CODES|{'visual_mismatch'}
    unknown=sorted(codes-known)
    if not codes or unknown:
        return deepcopy(ssm),{'selection':'full_ssm_fallback','reason':'unknown_or_absent_error_codes',
            'unknown_codes':unknown,'selected_sections':sorted(ssm),'omitted_sections':[]}
    names={'schema_version','schema_name','metadata','san_generation_contract'}
    if codes&TEMPLATE_CODES:names.add('template')
    if codes&SCRIPT_CODES:names.add('script')
    if codes&REACTIVE_CODES:names.add('binding_graph')
    visual_failed=evaluation['dimensions']['visual'] not in ('pass','not_run')
    if visual_failed or any('class' in code or 'style' in code for code in codes):
        names.add('styles' if ssm.get('styles') else 'style_model')
    # Compound sources keep their child definitions intact, not false empties.
    if ssm.get('sub_components'):names.add('sub_components')
    selected={key:deepcopy(value) for key,value in ssm.items() if key in names}
    if 'styles' in selected and selected['styles'].get('style_blocks'):
        # Source CSS blocks are canonical. Don't repeat the same CSS as a
        # parsed rule table and a second style_model inside the prompt.
        selected['styles']={k:v for k,v in selected['styles'].items() if k!='css_rules'}
    return selected,{'selection':'error_related_sections','unknown_codes':[],
        'selected_sections':sorted(selected),'omitted_sections':sorted(set(ssm)-set(selected)),
        'source_methods_defaults_and_selected_sections_not_truncated':True}


def project_prompt(prompt,ssm,evaluation):
    builder_chars=len(prompt)
    selected,selection=relevant_ssm(ssm,evaluation)
    original='--- SSM ---\n'+json.dumps(ssm,ensure_ascii=False,indent=2)+'\n\n'
    applied=False
    if original in prompt:
        if prompt.count(original)!=1:raise ServiceError('repair_ssm_projection_ambiguous')
        prompt=prompt.replace(original,'--- Relevant SSM Evidence ---\n'+encoded(selected)+'\n\n',1)
        applied=True
    elif '--- SSM ---\n' in prompt:
        raise ServiceError('repair_ssm_projection_unmatched')
    codes=Counter(str(item.get('code','unknown')) for item in evaluation.get('diagnostics',[]))
    notice={'policy':POLICY,'ssm_selection':selection if applied else {'selection':'existing_builder_already_focused'},
        'error_counts':dict(sorted(codes.items())),
        'required_quality_dimensions':evaluation.get('required',[]),
        'thresholds':evaluation.get('thresholds',{}),
        'notice':'Evidence is a repair-only projection, not a complete source specification or a pass. '
                 'Preserve all unlisted correct code and source contracts. Omitted observations and SSM fields '
                 'are not absent features or resolved errors. Full source-bound evidence remains local. '
                 'Never delete behavior or change thresholds to satisfy this prompt.'}
    result='Repair context policy:\n'+encoded(notice)+'\n\n'+prompt
    audit={'policy':POLICY,'evaluation_sha256':fingerprint(evaluation),'full_ssm_sha256':fingerprint(ssm),
        'selected_ssm_sha256':fingerprint(selected),'ssm_projection_applied':applied,
        **notice,'legacy_builder_chars':builder_chars,'model_prompt_chars':len(result),
        'full_evaluation_appended':False,'selection_if_full_builder_used':selection}
    return result,audit
