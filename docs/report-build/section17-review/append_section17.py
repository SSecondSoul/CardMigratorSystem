from pathlib import Path
from copy import deepcopy
from lxml import etree as E
from docx import Document
from docx.shared import Inches
from zipfile import ZipFile
import importlib.util,json,shutil,tempfile,os,sys
import section17_content as C

ROOT=Path(__file__).resolve().parents[3];B=Path(__file__).parent
spec=importlib.util.spec_from_file_location('report_package_helpers',B.parent/'section16-review/append_section16.py')
H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
N=H.N;W=H.W;load=H.load;write=H.write;digest=H.digest;paragraph=H.paragraph;text=H.text
TARGET=Path('C:/Users/soul/Desktop/swu/中期答辩/中期检查表-杨润生.docx')
SOURCE=B/'source.docx';FIGURE=B/'section17-database.png'

def table_from(template,headers,rows,widths):
    tab=deepcopy(template);previous=tab.findall('w:tr',N);head=deepcopy(previous[0]);pat=deepcopy(previous[1])
    for row in previous:tab.remove(row)
    for col,width in zip(tab.find('w:tblGrid',N),widths):col.set(W+'w',str(width))
    def fill(row,values):
        for cell,value,width in zip(row.findall('w:tc',N),values,widths):
            props=cell.find('w:tcPr',N);cw=props.find('w:tcW',N)
            if cw is not None:cw.set(W+'w',str(width));cw.set(W+'type','dxa')
            p0=cell.find('w:p',N)
            for child in list(cell):
                if child.tag!=W+'tcPr':cell.remove(child)
            p=paragraph(p0,value);pp=p.find('w:pPr',N)
            ind=pp.find('w:ind',N)
            if ind is not None:ind.set(W+'firstLine','0')
            cell.append(p)
        return row
    head=fill(head,headers)
    trpr=head.find('w:trPr',N)
    if trpr is None:trpr=E.Element(W+'trPr');head.insert(0,trpr)
    repeat=trpr.find('w:tblHeader',N)
    if repeat is None:repeat=E.SubElement(trpr,W+'tblHeader')
    repeat.set(W+'val','1')
    for p in head.findall('w:tc/w:p',N):
        pp=p.find('w:pPr',N);keep=pp.find('w:keepNext',N)
        if keep is None:keep=E.Element(W+'keepNext');pp.insert(0,keep)
        keep.set(W+'val','1')
    tab.append(head)
    for values in rows:tab.append(fill(deepcopy(pat),values))
    return tab

def prepare():
    original=load(SOURCE);sha=digest(SOURCE);root=E.fromstring(original['word/document.xml'])
    assert text(root).count('16. 后端技术栈')==1 and '17. 数据库设计' not in text(root)
    tr=next(t for t in root.findall('.//w:tr',N) if t.findall('w:tc',N) and text(t.findall('w:tc',N)[0])=='论文研究进展')
    cell=tr.findall('w:tc',N)[-1];paras=cell.findall('w:p',N)
    signature=next(p for p in paras if '本人签字' in text(p))
    heading=next(p for p in paras if text(p)=='16. 后端技术栈')
    body=next(p for p in paras if text(p).startswith('用户提交后，接口先将任务'))
    caption=next(p for p in paras if text(p).startswith('图10') and len(text(p))<50)
    tcaption=next(p for p in paras if text(p).startswith('表15') and len(text(p))<50)
    template=next(t for t in cell.findall('w:tbl',N) if [text(c) for c in t.findall('w:tr/w:tc',N)][:3]==['技术组成','选用技术','作用'])
    nodes=[paragraph(heading,'17. 数据库设计'),paragraph(body,C.INTRO)]
    doc=Document();p=doc.add_paragraph();p.add_run().add_picture(str(FIGURE),width=Inches(5.5));doc.save(B/'picture.docx')
    pictmp=load(B/'picture.docx');picroot=E.fromstring(pictmp['word/document.xml']);pic=deepcopy(picroot.find('w:body/w:p',N))
    pic.insert(0,deepcopy(caption.find('w:pPr',N)));pp=pic.find('w:pPr',N);spacing=pp.find('w:spacing',N)
    spacing.set(W+'line','240');spacing.set(W+'lineRule','auto');spacing.set(W+'after','80')
    keep=pp.find('w:keepNext',N)
    if keep is None:keep=E.SubElement(pp,W+'keepNext')
    keep.set(W+'val','1')
    rid='rIdSection17Figure11';pic.find('.//a:blip',N).set('{'+N['r']+'}embed',rid)
    nextid=max([int(x.get('id','0')) for x in root.findall('.//wp:docPr',N)]+[0])+1
    for el in pic.findall('.//wp:docPr',N):
        el.set('id',str(nextid));el.set('name','图11 网页迁移任务核心表关系');el.set('descr','用户通过源码归属和任务归属表关联记录。源码可对应多个迁移任务，每个任务再对应多个模型调用和文件索引；归属记录至多一条。')
    nodes += [pic,paragraph(caption,'图11  网页迁移任务核心表关系'),paragraph(body,C.RELATION),paragraph(tcaption,'表16  核心数据表及主要内容')]
    nodes.append(table_from(template,['表名','关键字段示例','存储内容'],C.CORE_ROWS,[2800,2600,2560]))
    nodes += [paragraph(body,C.CORE_NOTE),paragraph(body,C.JOB_INTRO),paragraph(tcaption,'表17  迁移任务表主要字段说明')]
    nodes.append(table_from(template,['字段','类型','说明'],C.JOB_ROWS,[2500,1700,3760]))
    nodes.extend(paragraph(body,t) for t in C.FOLLOW)
    old=[E.tostring(x,method='c14n') for x in cell];at=list(cell).index(signature)
    for i,node in enumerate(nodes):cell.insert(at+i,node)
    assert [E.tostring(x,method='c14n') for x in list(cell)[:at]]==old[:at]
    assert [E.tostring(x,method='c14n') for x in list(cell)[at+len(nodes):]]==old[at:]
    rels=E.fromstring(original['word/_rels/document.xml.rels']);assert not any(x.get('Id')==rid for x in rels)
    E.SubElement(rels,'{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',Id=rid,Type=N['r']+'/image',Target='media/section17-database.png')
    candidate=dict(original);candidate['word/document.xml']=E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
    candidate['word/_rels/document.xml.rels']=E.tostring(rels,encoding='UTF-8',xml_declaration=True,standalone=True);candidate['word/media/section17-database.png']=FIGURE.read_bytes()
    changed=[k for k in original if original[k]!=candidate[k]];assert set(changed)=={'word/document.xml','word/_rels/document.xml.rels'}
    backup=B/f'中期检查表-杨润生_续写第17节前备份_{sha[:8]}.docx'
    if not backup.exists():shutil.copy2(SOURCE,backup)
    assert digest(backup)==sha
    out=B/'candidate.docx';write(out,candidate)
    with ZipFile(out) as z:assert z.testzip() is None
    def preview_for(block,path):
        preview=deepcopy(root);b=preview.find('w:body',N);sect=deepcopy(b.find('w:sectPr',N))
        for child in list(b):b.remove(child)
        for node in block:b.append(deepcopy(node))
        page=sect.find('w:pgSz',N);mar=sect.find('w:pgMar',N);pw=int(page.get(W+'w'));m=(pw-8081)//2
        mar.set(W+'left',str(m));mar.set(W+'right',str(pw-8081-m));b.append(sect)
        parts=dict(candidate);parts['word/document.xml']=E.tostring(preview,encoding='UTF-8',xml_declaration=True,standalone=True);write(path,parts)
    preview_for(nodes,B/'section17-qa.docx')
    children=list(cell);first=next(i for i,x in enumerate(children) if text(x)=='14. 功能设计');last=list(cell).index(signature)
    preview_for(children[first:last],B/'sections14-17-qa.docx')
    record={'target':str(TARGET),'source_sha256':sha,'candidate':str(out),'candidate_sha256':digest(out),'backup':str(backup),'changed_original_parts':changed,'added_parts':['word/media/section17-database.png'],'existing_sections_1_to_16_preserved':True,'new_section':'17. 数据库设计','figure':11,'tables':[16,17],'body_width_twips':8081,'table16_widths':[2800,2600,2560],'table17_widths':[2500,1700,3760],'next_module_started':False,'page_budget_scope':'用户最新明确：整份报告13页左右；新增数据库部分已精简，完整WPS页数待用户打开检查'}
    (B/'prepared.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    (B/'artifact.md').write_text('# 第17节编辑与核验约定\n\n以当前原文档为格式依据，仅在本人签字前追加数据库设计。保留第16节用户已确认的FastAPI和MySQL表述。图11使用黑白关系图，正文宋体11pt、固定17pt，标题沿用原稿；表格沿用三线表，按字段长度调整列宽。图片使用自动行距。\n\n数据来自当前模型、MySQL结构快照及已有原生核验记录；34为表数，不代表业务记录条数。仅介绍实际字段和约束，不添加无实现依据的公式。已知当前环境没有LibreOffice，章节及新增部分由第一方画布渲染检查，不作为完整WPS页数证明。\n\n'+json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    def mdtable(headers,rows):return '|'+ '|'.join(headers)+'|\n|'+'|'.join(['---']*len(headers))+'|\n'+'\n'.join('|'+ '|'.join(r)+'|' for r in rows)
    md='# 17. 数据库设计\n\n'+C.INTRO+'\n\n图11  网页迁移任务核心表关系\n\n'+C.RELATION+'\n\n表16  核心数据表及主要内容\n\n'+mdtable(['表名','关键字段示例','存储内容'],C.CORE_ROWS)+'\n\n'+C.CORE_NOTE+'\n\n'+C.JOB_INTRO+'\n\n表17  迁移任务表主要字段说明\n\n'+mdtable(['字段','类型','说明'],C.JOB_ROWS)+'\n\n'+'\n\n'.join(C.FOLLOW)+'\n'
    (ROOT/'docs/paper/中期报告续写/17_数据库设计_对齐原稿待审.md').write_text(md,encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False,indent=2))

def commit():
    info=json.loads((B/'prepared.json').read_text(encoding='utf-8'))
    assert digest(TARGET)==info['source_sha256'],'原文档已变化，停止覆盖'
    assert digest(Path(info['candidate']))==info['candidate_sha256']
    fd,tmp=tempfile.mkstemp(prefix='.section17-',suffix='.docx',dir=TARGET.parent);os.close(fd);tmp=Path(tmp)
    try:
        shutil.copyfile(info['candidate'],tmp)
        assert digest(TARGET)==info['source_sha256']
        os.replace(tmp,TARGET)
    finally:
        if tmp.exists():tmp.unlink()
    assert digest(TARGET)==info['candidate_sha256'];print('第17节已写入原文档')

if __name__=='__main__':commit() if '--commit' in sys.argv else prepare()
