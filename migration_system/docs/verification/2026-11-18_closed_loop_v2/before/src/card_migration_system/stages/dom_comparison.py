"""Keep raw evidence; distinguish representation, structure and live properties."""
import re
from .structure import tree_distance,tree_differences


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
