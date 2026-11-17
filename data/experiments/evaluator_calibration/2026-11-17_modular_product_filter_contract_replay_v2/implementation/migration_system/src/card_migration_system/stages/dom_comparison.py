"""Keep raw DOM evidence; normalize only exact empty class under an approved policy."""
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
        if a!=b and len(differences)<32:differences.append({'expected':a,'actual':b})
    return {'equal':first==second,'source_count':len(first),'target_count':len(second),
            'differences':differences,'scope':'captured_live_control_properties_not_attribute_equivalence'}


def compare_dom(expected,actual,policy=None):
    raw=tree_distance(expected,actual)
    raw_differences=tree_differences(expected,actual)
    approved=bool(policy and policy.get('version')=='empty_class_presence_v1' and policy.get('approved') is True)
    changes=[]
    def project(node,path):
        copy={**node,'children':[project(child,path+'.'+str(i)) for i,child in enumerate(node.get('children',[]))]}
        attrs=node.get('attributes');tag=node.get('tag')
        if approved and isinstance(attrs,dict) and isinstance(tag,str) and attrs.get('class')=='':
            attrs={k:v for k,v in attrs.items() if k!='class'}
            # Only renderer-owned structured attributes, never parse label text
            # (attribute values can themselves contain pipes or equals signs).
            copy.update(attributes=attrs,label=tag+'|'+'|'.join(sorted(k+'='+str(v) for k,v in attrs.items())))
            changes.append({'path':path,'change':'empty_class_presence_removed_from_comparison_copy'})
        return copy
    first,second=project(expected,'source.root'),project(actual,'target.root')
    effective=tree_distance(first,second) if changes else raw
    return {'metric':effective,'raw_metric':raw,'differences':tree_differences(first,second),
            'raw_differences':raw_differences,'policy':policy or {'approved':False,'reasons':['policy_not_available']},
            'normalization_changes':changes,'raw_evidence_modified':False}
