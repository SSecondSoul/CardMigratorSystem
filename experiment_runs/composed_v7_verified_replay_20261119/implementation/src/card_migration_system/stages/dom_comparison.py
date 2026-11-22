"""Keep raw evidence; distinguish representation, structure and live properties."""
import re
from hashlib import sha256
import json
from .structure import tree_distance,tree_differences


def control_gate_evidence(source,target,overflow=False):
    """Small, versioned identity witnesses; NOT a substitute for DOM checks.

    Bound path-only diagnostic refinement to an already present target control
    and its unchanged parent topology. Text values stay in control identities;
    parent topology ignores text contents, not text/element boundaries.
    """
    def digest(value):return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    def shape(n):return {k:v for k,v in n.items() if k not in ('label','children')}|{
        'text_node':n.get('tag') is None,'children':[shape(c) for c in n.get('children',[])]}
    def witnesses(snapshot):
        nodes={}
        def walk(n,path):
            nodes[path]=n
            for i,c in enumerate(c for c in n.get('children',[]) if c.get('tag')):walk(c,path+'.'+str(i))
        walk(snapshot['dom'],'root')
        controls=[i for i in snapshot['styles'] if i.get('tag') in {'input','select','textarea','option','button'}]
        if len(controls)>128:return None
        result=[]
        for item in controls:
            path=item['path'];node=nodes.get(path);parent=nodes.get(path.rsplit('.',1)[0])
            if not node or not parent or node.get('tag')!=item['tag']:return None
            result.append({'path':path,'identity':digest(node),'parent_shape':digest(shape(parent))})
        return result
    first,second=witnesses(source),witnesses(target)
    return {'contract':'control_diagnostic_refinement_v1','complete':not overflow and first is not None and second is not None,
        'source_snapshot':digest({'dom':source['dom'],'controls':first}),'source':first,'target':second}


def proven_control_diagnostic_refinement(previous,candidate):
    """Only missing controls restored, with the remaining path defect unchanged.

    Missing/old/truncated witnesses refuse refinement. New wrapper changes,
    changed control identities, state changes, source changes all refuse it.
    The candidate STILL fails structure; this only allows useful repair progress.
    """
    a,b=previous.get('initial_control_state',{}),candidate.get('initial_control_state',{})
    x,y=previous.get('control_gate_evidence',{}),candidate.get('control_gate_evidence',{})
    if not (x.get('contract')==y.get('contract')=='control_diagnostic_refinement_v1'
            and x.get('complete') is True and y.get('complete') is True
            and x.get('source_snapshot')==y.get('source_snapshot') and x.get('source')==y.get('source')
            and a.get('source_count')==b.get('source_count')==b.get('target_count')
            and isinstance(a.get('target_count'),int) and a['target_count']<b['target_count']
            and b.get('values_equal_in_order') is True and b.get('equal') is False):return False
    if not (previous['structure_ted']['similarity']<=candidate['structure_ted']['similarity']
            and previous['dom_ted']['similarity']<candidate['dom_ted']['similarity']):return False
    source,target=y.get('source'),y.get('target');old={i['path']:i for i in x.get('target') or []}
    if not (isinstance(source,list) and isinstance(target,list) and len(source)==len(target)==b['source_count']):return False
    shifted=0
    for expected,actual in zip(source,target):
        if expected['identity']!=actual['identity']:return False
        if expected['path']!=actual['path']:
            shifted+=1
            if old.get(actual['path'])!=actual:return False
    return bool(shifted)


def proven_default_runtime_recovery(previous,candidate):
    """Only a source-proven missing prop default may reveal a position defect.

    Both are fresh trusted browser witnesses. The candidate must be byte-for-
    byte the existing rule's entire proposal, not merely have the same template
    projection. Keep the structure diagnostic/failure; permit repair progress,
    never equivalence. Unknown/old evidence and any additional edits refuse it.
    """
    x,y=previous.get('default_recovery_binding') or {},candidate.get('default_recovery_binding') or {}
    a,b=previous.get('control_gate_evidence',{}),candidate.get('control_gate_evidence',{})
    controls=candidate.get('initial_control_state',{})
    return bool(x.get('contract')==y.get('contract')=='source_prop_defaults_runtime_recovery_v1'
        and x.get('complete') is True and y.get('complete') is True
        and x.get('input_sha256') and x['input_sha256']==y.get('input_sha256')
        and x.get('runtime_sha256') and x['runtime_sha256']==y.get('runtime_sha256')
        and 'restored_source_parent_prop_defaults' in x.get('changes',[])
        and y.get('changes')==[] and x.get('normalized_sha256')==y.get('code_sha256')==y.get('normalized_sha256')
        and x.get('code_sha256')!=y.get('code_sha256')
        and previous['dimensions'].get('compile_runtime')=='fail' and candidate['dimensions'].get('compile_runtime')=='pass'
        and previous['dimensions'].get('source_baseline')==candidate['dimensions'].get('source_baseline')=='pass'
        and a.get('source_snapshot') and a['source_snapshot']==b.get('source_snapshot') and b.get('complete') is True
        and controls.get('equal') is False and controls.get('values_equal_in_order') is True
        and controls.get('source_count')==controls.get('target_count')
        and previous['structure_ted']['similarity']<=candidate['structure_ted']['similarity']
        and previous['dom_ted']['similarity']<candidate['dom_ted']['similarity'])


def compare_control_state(expected,actual):
    """Compare live properties separately; never waive HTML attribute presence."""
    tags={'input','select','textarea','option','button'}
    def controls(items):
        return [(i['path'],i['tag'],i.get('value'),i.get('checked'),i.get('selected_values'))
                for i in items if i.get('tag') in tags]
    first,second=controls(expected),controls(actual)
    differences=[]
    for index in range(max(len(first),len(second))):
        a=first[index] if index<len(first) else None
        b=second[index] if index<len(second) else None
        if a!=b and len(differences)<32:
            kind='control_added_or_removed' if a is None or b is None else (
                'control_type_changed' if a[1]!=b[1] else 'live_property_changed' if a[2:]!=b[2:] else 'control_path_changed')
            differences.append({'expected':a,'actual':b,'kind':kind})
    return {'equal':first==second,'source_count':len(first),'target_count':len(second),
            'values_equal_in_order':[i[1:] for i in first]==[i[1:] for i in second],
            'paths_equal':[i[0] for i in first]==[i[0] for i in second],
            'differences':differences,'scope':'captured_live_control_properties_not_attribute_equivalence'}


def compare_dom(expected,actual,policy=None):
    raw=tree_distance(expected,actual)
    raw_differences=tree_differences(expected,actual)
    version=(policy or {}).get('version')
    approved=bool(policy and version in ('empty_class_presence_v1','class_serialization_v2') and policy.get('approved') is True)
    changes=[]
    representations=[]
    def class_tokens(value):return sorted(set(re.split(r'[\t\n\f\r ]+',value.strip(' \t\n\f\r')))-{''})
    def classify(a,b,path):
        aa,bb=a.get('attributes'),b.get('attributes')
        if a.get('tag')==b.get('tag') and isinstance(aa,dict) and isinstance(bb,dict):
            av,bv=aa.get('class'),bb.get('class')
            if av!=bv and class_tokens(av or '')==class_tokens(bv or ''):
                representations.append({'path':path,'attribute':'class','source':av,'target':bv,
                    'kind':'empty_class_presence' if av is None or bv is None else 'class_token_serialization',
                    'normalized':approved and (version=='class_serialization_v2' or av in (None,'') and bv in (None,''))})
        for i,(ac,bc) in enumerate(zip(a.get('children',[]),b.get('children',[]))):classify(ac,bc,path+'.'+str(i))
    classify(expected,actual,'root')
    def project(node,path):
        copy={**node,'children':[project(child,path+'.'+str(i)) for i,child in enumerate(node.get('children',[]))]}
        attrs=node.get('attributes');tag=node.get('tag')
        if approved and isinstance(attrs,dict) and isinstance(tag,str) and 'class' in attrs and (
                attrs['class']=='' or version=='class_serialization_v2'):
            attrs=dict(attrs)
            value=' '.join(class_tokens(attrs['class'])) if version=='class_serialization_v2' else ''
            if value==attrs['class'] and value:return copy
            if value:attrs['class']=value
            else:attrs.pop('class')
            # Only renderer-owned structured attributes, never parse label text
            # (attribute values can themselves contain pipes or equals signs).
            copy.update(attributes=attrs,label=tag+'|'+'|'.join(sorted(k+'='+str(v) for k,v in attrs.items())))
            changes.append({'path':path,'change':'class_serialization_normalized_in_comparison_copy' if value else 'empty_class_presence_removed_from_comparison_copy'})
        return copy
    first,second=project(expected,'source.root'),project(actual,'target.root')
    effective=tree_distance(first,second) if changes else raw
    return {'metric':effective,'raw_metric':raw,'differences':tree_differences(first,second),
            'raw_differences':raw_differences,'policy':policy or {'approved':False,'reasons':['policy_not_available']},
            'representation_differences':representations,
            'normalization_changes':changes,'raw_evidence_modified':False}
