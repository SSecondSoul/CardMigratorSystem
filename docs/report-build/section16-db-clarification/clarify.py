from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
from copy import deepcopy
import json,hashlib,os,shutil,tempfile,sys

ROOT=Path(__file__).resolve().parents[3]; B=Path(__file__).parent
TARGET=Path('C:/Users/soul/Desktop/swu/中期答辩/中期检查表-杨润生.docx')
SNAPSHOT=B/'current-shared-snapshot.docx'
N={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
W='{'+N['w']+'}'
FLOW='LangGraph把预检查、SSM提取、生成、评估、诊断、修复、候选再检查和结果保存连接起来。检查通过、源组件存在问题或修复轮数用完时，流程进入报告阶段；修复候选只有在比较后被接受，才替换当前版本。LangGraph还会记录已经执行的阶段和中间状态，便于异常后检查与恢复；恢复时仍需核对任务和配置是否一致。'
DATA='当前系统使用MySQL保存任务、账号、模型调用和文件索引等业务数据。Python通过SQLAlchemy和PyMySQL读写MySQL，Alembic负责管理数据表结构及版本。流程检查点仍由LangGraph单独保存在本地langgraph.sqlite3文件中，用来记录执行到哪一步及中间状态，采用SQLite格式；这部分与MySQL业务库分开保存。源码、San代码、SSM、截图和报告保存在文件目录中，数据库登记文件路径与SHA-256标识，读取时核对文件内容。具体数据表及其联系在下一节说明。'
def text(el):return ''.join(el.xpath('.//w:t/text()',namespaces=N))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
    with ZipFile(p) as z:return {n:z.read(n) for n in z.namelist()}
def write(p,parts):
    with ZipFile(p,'w',ZIP_DEFLATED) as z:
        for n,b in parts.items():z.writestr(n,b)
def replace(p,value):
    old=text(p); ts=p.findall('.//w:t',N);assert ts
    ts[0].text=value
    for t in ts[1:]:t.text=''
    return old
def prepare():
    original=load(SNAPSHOT);sha=digest(SNAPSHOT);root=E.fromstring(original['word/document.xml'])
    tr=next(t for t in root.findall('.//w:tr',N) if t.findall('w:tc',N) and text(t.findall('w:tc',N)[0])=='论文研究进展')
    cell=tr.findall('w:tc',N)[-1];children=list(cell)
    start=next(i for i,x in enumerate(children) if text(x)=='16. 后端技术栈')
    end=next(i for i in range(start,len(children)) if '本人签字' in text(children[i]))
    nodes=children[start:end];paras=[p for node in nodes for p in ([node] if node.tag==W+'p' else node.findall('.//w:p',N))]
    flow=next(p for p in paras if text(p).startswith('LangGraph把预检查'))
    data=next(p for p in paras if text(p).startswith('业务数据通过SQLAlchemy访问SQLite或MySQL'))
    changes=[]
    def change(p,value):
        item={'path':root.getroottree().getpath(p),'original_xml':E.tostring(p,encoding='unicode'),'old':text(p),'new':value}
        replace(p,value);changes.append(item)
    change(flow,FLOW);change(data,DATA)
    table=next(x for x in nodes if x.tag==W+'tbl')
    row=next(r for r in table.findall('w:tr',N) if text(r.findall('w:tc',N)[0])=='数据管理')
    cells=row.findall('w:tc',N)
    for c,value in [(cells[1],'MySQL、SQLAlchemy、Alembic'),(cells[2],'业务存储与表结构管理。')]:
        change(c.find('w:p',N),value)
    caption_index=next(i for i,x in enumerate(nodes) if text(x).startswith('图10') and len(text(x))<50)
    figure=nodes[caption_index-1];embed=figure.find('.//a:blip',N).get('{'+N['r']+'}embed')
    rels=E.fromstring(original['word/_rels/document.xml.rels']);target=next(x.get('Target') for x in rels if x.get('Id')==embed)
    media='word/'+target.lstrip('/') if not target.startswith('/') else target.lstrip('/')
    assert media.startswith('word/media/')
    new=dict(original);new['word/document.xml']=E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True);new[media]=(B/'section16-backend-mysql.png').read_bytes()
    out=B/'candidate.docx';write(out,new)
    # Compare the whole XML after reversing exactly the four text edits.
    restored=deepcopy(root)
    for change in changes:
        p=restored.xpath(change['path'],namespaces=N)[0]
        p.getparent().replace(p,E.fromstring(change['original_xml'].encode()))
    assert E.tostring(restored,method='c14n')==E.tostring(E.fromstring(original['word/document.xml']),method='c14n')
    changed=[k for k in original if original[k]!=new[k]];assert set(changed)=={'word/document.xml',media}
    preview=deepcopy(root);body=preview.find('w:body',N);sect=deepcopy(body.find('w:sectPr',N))
    for c in list(body):body.remove(c)
    for node in nodes:body.append(deepcopy(node))
    pg=sect.find('w:pgSz',N);margin=sect.find('w:pgMar',N);width=int(pg.get(W+'w'));m=(width-8081)//2
    margin.set(W+'left',str(m));margin.set(W+'right',str(width-8081-m));body.append(sect)
    qa=dict(new);qa['word/document.xml']=E.tostring(preview,encoding='UTF-8',xml_declaration=True,standalone=True);write(B/'section16-qa.docx',qa)
    backup=B/f'中期检查表-杨润生_数据库表述修订前_{sha[:8]}.docx'
    if not backup.exists():shutil.copy2(SNAPSHOT,backup)
    info={'target':str(TARGET),'snapshot_sha256':sha,'candidate':str(out),'candidate_sha256':digest(out),'backup':str(backup),'changed_parts':changed,'text_changes':changes,'scope':'仅修订第16节数据库说明、表15数据管理行及图10数据库标签；没有修改系统代码和存储方式','preserved_other_content':True}
    (B/'prepared.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    (B/'artifact.md').write_text('# 第16节数据库表述修订\n\n按实际MySQL运行配置区分业务库、数据库访问工具和LangGraph本地流程检查点。保留原文格式，仅四处文字及图10标签变化。所有其他XML及原包部件逐项保持。渲染新增章节进行图文检查；完整WPS分页不由当前渲染器验证。\n\n'+json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in info.items() if k!='text_changes'},ensure_ascii=False,indent=2))
def commit():
    data=json.loads((B/'prepared.json').read_text(encoding='utf-8'))
    assert digest(TARGET)==data['snapshot_sha256'],'原文档已变化，停止覆盖'
    assert digest(Path(data['candidate']))==data['candidate_sha256']
    fd,t=tempfile.mkstemp(prefix='.clarify-db-',suffix='.docx',dir=TARGET.parent);os.close(fd);t=Path(t)
    try:
        shutil.copyfile(data['candidate'],t)
        assert digest(TARGET)==data['snapshot_sha256']
        os.replace(t,TARGET)
    finally:
        if t.exists():t.unlink()
    assert digest(TARGET)==data['candidate_sha256']
    print('已写入原文档')
def verify():
    info=json.loads((B/'prepared.json').read_text(encoding='utf-8'))
    assert digest(TARGET)==info['candidate_sha256']
    parts=load(TARGET);oldparts=load(Path(info['backup']))
    root=E.fromstring(parts['word/document.xml']);current=text(root)
    assert '业务数据通过SQLAlchemy访问SQLite或MySQL' not in current
    assert '流程执行位置另存到SQLite检查点中' not in current
    assert FLOW in current and DATA in current
    assert 'MySQL、SQLAlchemy、Alembic' in current
    for change in info['text_changes']:
        p=root.xpath(change['path'],namespaces=N)[0]
        assert text(p)==change['new']
        p.getparent().replace(p,E.fromstring(change['original_xml'].encode()))
    assert E.tostring(root,method='c14n')==E.tostring(E.fromstring(oldparts['word/document.xml']),method='c14n')
    media=next(k for k in info['changed_parts'] if k!='word/document.xml')
    assert parts[media]==(B/'section16-backend-mysql.png').read_bytes()
    assert all(v==parts[k] for k,v in oldparts.items() if k not in info['changed_parts'])
    statepath=ROOT/'docs/paper/中期报告续写/续写状态.json';state=json.loads(statepath.read_text(encoding='utf-8-sig'))
    state.update({'current_status':'第16节已按用户反馈修订：明确MySQL业务库、SQLAlchemy和Alembic工具、本地SQLite流程检查点的区别，等待检查','latest_report_sha256':digest(TARGET),'backup':info['backup']})
    statepath.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    draft=ROOT/'docs/paper/中期报告续写/16_后端技术栈_对齐原稿待审.md'
    if draft.exists():
        md=draft.read_text(encoding='utf-8')
        for c in info['text_changes']:md=md.replace(c['old'],c['new'])
        draft.write_text(md,encoding='utf-8')
    result={'sha256':digest(TARGET),'current_business_store':'MySQL','access_tools':'SQLAlchemy + PyMySQL','schema_version_tool':'Alembic','graph_checkpoints':'local SQLite langgraph.sqlite3','original_content_outside_four_text_edits_and_figure10_preserved':True,'section17_started':False,'original_document_updated':True}
    (B/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
    if '--commit' in sys.argv:commit()
    elif '--verify' in sys.argv:verify()
    else:prepare()
