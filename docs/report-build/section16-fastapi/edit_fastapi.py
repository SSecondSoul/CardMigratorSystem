from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
from copy import deepcopy
import json,hashlib,shutil,os,tempfile,sys

ROOT=Path(__file__).resolve().parents[3];B=Path(__file__).parent
TARGET=Path('C:/Users/soul/Desktop/swu/中期答辩/中期检查表-杨润生.docx')
SOURCE=B/'source.docx';FIGURE=B/'section16-backend-fastapi.png'
N={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing','pic':'http://schemas.openxmlformats.org/drawingml/2006/picture'}
W='{'+N['w']+'}'
def text(el):return ''.join(el.xpath('.//w:t/text()',namespaces=N))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
    with ZipFile(p) as z:return {n:z.read(n) for n in z.namelist()}
def write(p,parts):
    with ZipFile(p,'w',ZIP_DEFLATED) as z:
        for k,v in parts.items():z.writestr(k,v)
def prepare():
    original=load(SOURCE);sha=digest(SOURCE);root=E.fromstring(original['word/document.xml'])
    tr=next(t for t in root.findall('.//w:tr',N) if t.findall('w:tc',N) and text(t.findall('w:tc',N)[0])=='论文研究进展')
    cell=tr.findall('w:tc',N)[-1];children=list(cell)
    start=next(i for i,x in enumerate(children) if text(x)=='16. 后端技术栈')
    end=next(i for i in range(start,len(children)) if '本人签字' in text(children[i]))
    nodes=children[start:end];changes=[]
    for node in nodes:
        for el in node.iter():
            if el.tag==W+'t' and el.text and 'Flask' in el.text:
                old=el.text;el.text=old.replace('Flask','FastAPI')
                changes.append({'path':root.getroottree().getpath(el),'kind':'text','old':old,'new':el.text})
            for key,value in list(el.attrib.items()):
                if 'Flask' in value:
                    new=value.replace('Flask','FastAPI');el.set(key,new)
                    changes.append({'path':root.getroottree().getpath(el),'kind':'attribute','key':key,'old':value,'new':new})
    assert changes,'No Flask text or metadata to update'
    section=''.join(text(x) for x in nodes)
    assert 'Flask' not in section and 'FastAPI' in section
    assert '计划采用' not in section and '拟采用FastAPI' not in section
    assert 'MySQL、SQLAlchemy、Alembic' in section
    i=next(i for i,x in enumerate(nodes) if text(x).startswith('图10') and len(text(x))<50)
    figure=nodes[i-1];rid=figure.find('.//a:blip',N).get('{'+N['r']+'}embed')
    rels=E.fromstring(original['word/_rels/document.xml.rels']);target=next(x.get('Target') for x in rels if x.get('Id')==rid)
    media=target.lstrip('/') if target.startswith('/') else 'word/'+target
    assert media.startswith('word/media/')
    candidate=dict(original);candidate['word/document.xml']=E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True);candidate[media]=FIGURE.read_bytes()
    changed=[k for k in original if original[k]!=candidate[k]]
    assert set(changed)=={'word/document.xml',media}
    restored=deepcopy(root)
    for c in changes:
        el=restored.xpath(c['path'],namespaces=N)[0]
        if c['kind']=='text':el.text=c['old']
        else:el.set(c['key'],c['old'])
    assert E.tostring(restored,method='c14n')==E.tostring(E.fromstring(original['word/document.xml']),method='c14n')
    backup=B/f'中期检查表-杨润生_FastAPI表述调整前_{sha[:8]}.docx'
    if not backup.exists():shutil.copy2(SOURCE,backup)
    out=B/'candidate.docx';write(out,candidate)
    preview=deepcopy(root);body=preview.find('w:body',N);sect=deepcopy(body.find('w:sectPr',N))
    for ch in list(body):body.remove(ch)
    for node in nodes:body.append(deepcopy(node))
    pg=sect.find('w:pgSz',N);margin=sect.find('w:pgMar',N);pw=int(pg.get(W+'w'));m=(pw-8081)//2
    margin.set(W+'left',str(m));margin.set(W+'right',str(pw-8081-m));body.append(sect)
    qa=dict(candidate);qa['word/document.xml']=E.tostring(preview,encoding='UTF-8',xml_declaration=True,standalone=True);write(B/'section16-qa.docx',qa)
    record={'target':str(TARGET),'source_sha256':sha,'candidate':str(out),'candidate_sha256':digest(out),'backup':str(backup),'media':media,'changed_parts':changed,'edits':changes,'scope':'按用户指定技术方向，将第16节接口技术及图10标签统一为FastAPI；不加入计划措辞'}
    (B/'prepared.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    (B/'artifact.md').write_text('# 第16节接口框架表述调整\n\n按用户要求直接写FastAPI。保留已确定的MySQL业务库与本地SQLite流程检查点说明。仅修订第16节的接口名称及图10，同步无障碍描述。该文档修改不代表代码迁移已经实施。章节预览使用原稿样式和正文宽度，不作为完整WPS分页证据。\n\n'+json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k!='edits'},ensure_ascii=False,indent=2))
def commit():
    info=json.loads((B/'prepared.json').read_text(encoding='utf-8'))
    assert digest(TARGET)==info['source_sha256'],'原文档已变化，停止覆盖'
    assert digest(Path(info['candidate']))==info['candidate_sha256']
    fd,tmp=tempfile.mkstemp(prefix='.fastapi-doc-',suffix='.docx',dir=TARGET.parent);os.close(fd);tmp=Path(tmp)
    try:
        shutil.copyfile(info['candidate'],tmp)
        assert digest(TARGET)==info['source_sha256']
        os.replace(tmp,TARGET)
    finally:
        if tmp.exists():tmp.unlink()
    assert digest(TARGET)==info['candidate_sha256']
    print('已写回原文件')
def verify():
    info=json.loads((B/'prepared.json').read_text(encoding='utf-8'))
    assert digest(TARGET)==info['candidate_sha256']
    parts=load(TARGET);original=load(Path(info['backup']));root=E.fromstring(parts['word/document.xml'])
    for c in info['edits']:
        el=root.xpath(c['path'],namespaces=N)[0]
        if c['kind']=='text':
            assert el.text==c['new'];el.text=c['old']
        else:
            assert el.get(c['key'])==c['new'];el.set(c['key'],c['old'])
    assert E.tostring(root,method='c14n')==E.tostring(E.fromstring(original['word/document.xml']),method='c14n')
    assert parts[info['media']]==FIGURE.read_bytes()
    assert all(parts[k]==v for k,v in original.items() if k not in info['changed_parts'])
    statepath=ROOT/'docs/paper/中期报告续写/续写状态.json';state=json.loads(statepath.read_text(encoding='utf-8-sig'))
    state.update({'current_status':'第16节已按用户要求统一接口技术为FastAPI，不加计划措辞；正文、表15和图10已对齐，等待检查','latest_report_sha256':digest(TARGET),'backup':info['backup']})
    statepath.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    draft=ROOT/'docs/paper/中期报告续写/16_后端技术栈_对齐原稿待审.md'
    if draft.exists():draft.write_text(draft.read_text(encoding='utf-8').replace('Flask','FastAPI'),encoding='utf-8')
    result={'original_document_updated':True,'sha256':digest(TARGET),'only_requested_text_metadata_and_figure10_changed':True,'interface_label':'FastAPI','plan_qualifiers_added':False,'code_migration_performed':False}
    (B/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
    if '--commit' in sys.argv:commit()
    elif '--verify' in sys.argv:verify()
    else:prepare()
