"""Ordered labelled tree edit distance (Zhang-Shasha unit insert/delete/rename)."""
from ..application.service import ServiceError
import re


def ssm_template_tree(ssm):
    """Project the actual extracted template dimension, not a source-code string diff."""
    def text(value):return re.sub(r'\s+',' ',value).strip()
    def visit(node):
        attrs=[str(k)+'='+(' '.join(sorted(set(str(v).split()))) if k=='class' else str(v))
               for k,v in node.get('static_attrs',{}).items() if k!='key']
        attrs+=['binding:'+item['target_attr'] for item in node.get('dynamic_attrs',[]) if item['target_attr']!='key']
        attrs+=['event:'+item.get('event_name',item.get('event','')) for item in node.get('event_bindings',[])]
        for directive in node.get('directives',[]):
            name=directive['directive_name'].removeprefix('v-')
            if name=='model':attrs.append('binding:value')
            elif name not in ('bind','on'):attrs.append('directive:'+name)
        content=text(''.join('@binding' if item.get('is_interpolation') else item.get('raw_text','') for item in node.get('text_bindings',[])))
        return {'label':node.get('san_tag',node.get('source_tag',''))+'|'+'|'.join(sorted(set(attrs)))+'|text:'+content,
                'children':[visit(child) for child in node.get('children',[]) if child.get('node_type') in ('element','component')]}
    return {'label':'#root','children':[visit(ssm['template']['dom_tree'])]}


def target_template_tree(tree):
    """Use the same element/text projection as the SSM schema (mixed text order is checked separately)."""
    def visit(node):
        if node['label']=='#root':return {'label':'#root','children':[visit(child) for child in node['children'] if not child['label'].startswith('#text:')]}
        label='|'.join(item for item in node['label'].split('|') if not item.startswith('binding:key') and not item.startswith('key='))
        content=''.join(child['label'].removeprefix('#text:') for child in node['children'] if child['label'].startswith('#text:'))
        return {'label':label+'|text:'+re.sub(r'\s+',' ',content).strip(),
                'children':[visit(child) for child in node['children'] if not child['label'].startswith('#text:')]}
    return visit(tree)


def tree_distance(first, second):
    def index(root):
        labels=['']; left=[0]
        def visit(node):
            children=[visit(child) for child in node.get('children', [])]
            labels.append(node['label']); n=len(labels)-1; left.append(left[children[0]] if children else n)
            return n
        visit(root)
        if len(labels)>1501: raise ServiceError('tree_edit_node_limit')
        last={l:i for i,l in enumerate(left) if i}
        return labels,left,sorted(last.values())
    a,la,ka=index(first);b,lb,kb=index(second)
    td=[[0]*len(b) for _ in a]
    for i in ka:
        for j in kb:
            ai,bj=la[i],lb[j]; rows=i-ai+2;cols=j-bj+2
            fd=[[0]*cols for _ in range(rows)]
            for x in range(rows): fd[x][0]=x
            for y in range(cols): fd[0][y]=y
            for x in range(1,rows):
                ix=ai+x-1
                for y in range(1,cols):
                    jy=bj+y-1
                    if la[ix]==ai and lb[jy]==bj:
                        fd[x][y]=min(fd[x-1][y]+1,fd[x][y-1]+1,fd[x-1][y-1]+(a[ix]!=b[jy]))
                        td[ix][jy]=fd[x][y]
                    else:
                        fd[x][y]=min(fd[x-1][y]+1,fd[x][y-1]+1,fd[la[ix]-ai][lb[jy]-bj]+td[ix][jy])
    distance=td[-1][-1];count=max(len(a)-1,len(b)-1)
    return {'distance':distance,'source_nodes':len(a)-1,'target_nodes':len(b)-1,
            'similarity':max(0,1-distance/count),'algorithm':'ordered_zhang_shasha_unit_cost_v1'}


def tree_differences(first,second,limit=30):
    """Bounded path/label evidence for diagnosis, not a replacement TED algorithm."""
    differences=[]
    def visit(a,b,path):
        if len(differences)>=limit:return
        if a is None or b is None or a['label']!=b['label']:
            differences.append({'path':path,'expected':a['label'][:500] if a else None,
                                'actual':b['label'][:500] if b else None})
        if a is not None and b is not None:
            ac,bc=a.get('children',[]),b.get('children',[])
            for i in range(max(len(ac),len(bc))):
                visit(ac[i] if i<len(ac) else None,bc[i] if i<len(bc) else None,path+'.'+str(i))
    visit(first,second,'root')
    return differences


def compare_styles(first, second):
    expected={item['path']:item for item in first};actual={item['path']:item for item in second}
    details=[];total=0;matches=0
    for key in sorted(set(expected)|set(actual)):
        a,b=expected.get(key),actual.get(key)
        for name in ('color','backgroundColor','fontSize','fontFamily','fontWeight','marginTop','marginLeft',
                     'paddingTop','paddingLeft','width','height','display','position'):
            total+=1
            av=a['styles'].get(name) if a else None; bv=b['styles'].get(name) if b else None
            if av==bv:matches+=1
            elif len(details)<500:details.append({'path':key,'property':name,'source':av,'target':bv})
    return {'similarity':matches/total if total else 1,'compared_properties':total,'differences':details,
            'matching':'child_index_path','truncated':total-matches>len(details)}
