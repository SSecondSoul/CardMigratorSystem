from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
from copy import deepcopy
import hashlib, json, shutil, os, tempfile, sys
from docx import Document
from docx.shared import Inches

ROOT=Path(__file__).resolve().parents[3]
B=Path(__file__).parent
TARGET=Path('C:/Users/soul/Desktop/swu/中期答辩/中期检查表-杨润生.docx')
FIGURE=B/'section16-backend.png'
N={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
W='{'+N['w']+'}'
RNS='http://schemas.openxmlformats.org/package/2006/relationships'

INTRO='后端以Python为主，采用Flask提供网页接口，并由独立的Worker执行迁移任务。接口负责接收请求、检查输入和账号权限、查询进度及提供文件下载；Worker负责调用前文介绍的迁移流程，便于复用已有的生成与校验程序。主要组件及其联系见图10，技术组成见表15。'
WORKER='用户提交后，接口先将任务写入业务数据库，返回任务编号和“已接收”状态。Worker从数据库中取出排队任务，执行时持续更新阶段和结果，网页定时查询这些信息。这样，用户可以先拿到任务编号，再查看进度，不必等整次迁移结束后才收到网页响应。当前采用单机单Worker串行处理，并通过运行锁避免同一时间重复执行任务。'
ROWS=[
    ['接口服务','Python、Flask','接收请求与查询下载。'],
    ['流程执行','Worker、LangGraph','组织各阶段与修复。'],
    ['源码处理','Node.js、Vue编译器、Babel','解析组件与检查语法。'],
    ['界面检查','Puppeteer、Edge或Chromium','运行页面并采集证据。'],
    ['模型调用','通义千问qwen-plus接口','生成代码与模型修复。'],
    ['数据管理','SQLAlchemy、Alembic','访问业务库与升级表结构。'],
    ['过程记录','本地记录、可选LangSmith','记录耗时与调用摘要。'],
]
FOLLOW=[
    'LangGraph把预检查、SSM提取、生成、评估、诊断、修复、候选再检查和结果保存连接起来。检查通过、源组件存在问题或修复轮数用完时，流程进入报告阶段；修复候选只有在比较后被接受，才替换当前版本。流程执行位置另存到SQLite检查点中，异常后可结合已保存状态处理，恢复时仍需检查任务与配置是否一致。',
    '源码解析和页面检查由Node.js辅助程序完成。Vue编译器与Babel负责读取模板、脚本等内容，Puppeteer控制Edge或Chromium运行Vue和San页面，采集DOM、控件状态和截图，再交给后端进行比较。Python负责组织任务，JavaScript工具负责处理组件和浏览器，两部分通过JSON交换输入与结果。',
    '当前模型配置使用qwen-plus，单次最大输出为32768 Token，单次网络请求的等待配置为240秒，每个任务最多调用4次，修复轮数最多3轮。这些数值是配置上限，实际次数随修复设置和检查结果变化；240秒也不等于整次迁移的耗时上限。模型采用非流式返回，后台收到完整代码后再编译和校验，输出被截断时会记录失败；遇到响应结果不明确的超时或断连时，不自动重复发送同一次调用。',
    '业务数据通过SQLAlchemy访问SQLite或MySQL，Alembic记录表结构的升级版本。任务、账号、调用和文件索引等记录保存在业务库中；LangGraph检查点使用独立SQLite文件，源码、San代码、SSM、截图和报告保存在文件目录中，并登记文件路径与SHA-256标识，读取时核对文件内容。具体数据表及其联系在下一节说明。',
    '多人模式下，后端检查登录状态、任务归属和管理员权限，并记录用户用量。模型密钥由执行任务的Worker从环境变量读取。各阶段耗时及异常保存在本地；需要集中查看时可开启LangSmith，目前配置中关闭该功能，开启后只上传阶段、耗时、标识等摘要。'
]

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def text(p):return ''.join(p.xpath('.//w:t/text()',namespaces=N))
def load(p):
    with ZipFile(p) as z:return {n:z.read(n) for n in z.namelist()}
def write(p,parts):
    with ZipFile(p,'w',ZIP_DEFLATED) as z:
        for n,b in parts.items():z.writestr(n,b)
def paragraph(template,value):
    p=deepcopy(template)
    for key in list(p.attrib):
        if key.endswith('paraId') or key.endswith('textId'):del p.attrib[key]
    rp=template.find('w:r/w:rPr',N)
    for c in list(p):
        if c.tag!=W+'pPr':p.remove(c)
    r=E.SubElement(p,W+'r')
    if rp is not None:r.append(deepcopy(rp))
    E.SubElement(r,W+'t').text=value
    return p

def prepare():
    original=load(TARGET);sha=digest(TARGET);root=E.fromstring(original['word/document.xml'])
    assert text(root).count('15. 前端界面')==1
    assert '16. 后端技术栈' not in text(root),'第16节已存在，停止重复追加'
    tr=next(t for t in root.findall('.//w:tr',N) if t.findall('w:tc',N) and text(t.findall('w:tc',N)[0])=='论文研究进展')
    cell=tr.findall('w:tc',N)[-1]
    sig=next(p for p in cell.findall('w:p',N) if '本人签字' in text(p))
    paras=cell.findall('w:p',N)
    heading=next(p for p in paras if text(p)=='15. 前端界面')
    body=next(p for p in paras if text(p).startswith('前端采用迁移工作台'))
    caption=next(p for p in paras if text(p).startswith('图9') and len(text(p))<45)
    tcaption=next(p for p in paras if text(p).startswith('表14') and len(text(p))<45)
    table=next(t for t in cell.findall('w:tbl',N) if [text(c) for c in t.findall('w:tr/w:tc',N)][:3]==['结果页签','主要内容','用户操作'])
    nodes=[paragraph(heading,'16. 后端技术栈'),paragraph(body,INTRO)]
    tmp=Document();p=tmp.add_paragraph();p.add_run().add_picture(str(FIGURE),width=Inches(5.5));tmp.save(B/'picture.docx')
    picparts=load(B/'picture.docx');pr=E.fromstring(picparts['word/document.xml']);pic=deepcopy(pr.find('w:body/w:p',N))
    pic.insert(0,deepcopy(caption.find('w:pPr',N)));pp=pic.find('w:pPr',N)
    spacing=pp.find('w:spacing',N);spacing.set(W+'line','240');spacing.set(W+'lineRule','auto');spacing.set(W+'after','80')
    keep=pp.find('w:keepNext',N)
    if keep is None:keep=E.SubElement(pp,W+'keepNext')
    keep.set(W+'val','1')
    rid='rIdSection16Figure10';pic.find('.//a:blip',N).set('{'+N['r']+'}embed',rid)
    nextid=max([int(x.get('id','0')) for x in root.findall('.//wp:docPr',N)]+[0])+1
    for x in pic.findall('.//wp:docPr',N):
        x.set('id',str(nextid));x.set('name','图10 后端主要组件与数据流');x.set('descr','网页经Flask接口登记和查询业务数据库中的任务；独立Worker读取任务并通过LangGraph组织模型、Node.js与浏览器、SQLite检查点及文件存储。')
    nodes += [pic,paragraph(caption,'图10  后端主要组件与数据流'),paragraph(body,WORKER),paragraph(tcaption,'表15  后端技术组成及作用')]
    tab=deepcopy(table);oldrows=tab.findall('w:tr',N);head=deepcopy(oldrows[0]);pat=deepcopy(oldrows[1])
    for row in oldrows:tab.remove(row)
    def fill(row,values):
        for c,value in zip(row.findall('w:tc',N),values):
            p0=c.find('w:p',N)
            for el in list(c):
                if el.tag!=W+'tcPr':c.remove(el)
            c.append(paragraph(p0,value))
        return row
    tab.append(fill(head,['技术组成','选用技术','作用']))
    for row in ROWS:tab.append(fill(deepcopy(pat),row))
    nodes.append(tab)
    for value in FOLLOW:
        p=paragraph(body,value);pp=p.find('w:pPr',N)
        keep=pp.find('w:keepLines',N)
        if keep is None:keep=E.SubElement(pp,W+'keepLines')
        keep.set(W+'val','1');nodes.append(p)
    at=list(cell).index(sig);oldchildren=[E.tostring(x,method='c14n') for x in cell]
    for i,node in enumerate(nodes):cell.insert(at+i,node)
    assert [E.tostring(x,method='c14n') for x in list(cell)[:at]]==oldchildren[:at]
    assert [E.tostring(x,method='c14n') for x in list(cell)[at+len(nodes):]]==oldchildren[at:]
    rels=E.fromstring(original['word/_rels/document.xml.rels']);assert not any(x.get('Id')==rid for x in rels)
    E.SubElement(rels,'{'+RNS+'}Relationship',Id=rid,Type=N['r']+'/image',Target='media/section16-backend.png')
    candidate=dict(original);candidate['word/document.xml']=E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
    candidate['word/_rels/document.xml.rels']=E.tostring(rels,encoding='UTF-8',xml_declaration=True,standalone=True);candidate['word/media/section16-backend.png']=FIGURE.read_bytes()
    backup=B/f'中期检查表-杨润生_续写第16节前备份_{sha[:8]}.docx'
    if not backup.exists():shutil.copy2(TARGET,backup)
    assert digest(backup)==sha
    out=B/'candidate.docx';write(out,candidate)
    changes=[n for n in original if original[n]!=candidate[n]];assert set(changes)=={'word/document.xml','word/_rels/document.xml.rels'}
    with ZipFile(out) as z:assert z.testzip() is None
    preview=deepcopy(root);b=preview.find('w:body',N);sect=deepcopy(b.find('w:sectPr',N))
    for ch in list(b):b.remove(ch)
    for node in nodes:b.append(deepcopy(node))
    page=sect.find('w:pgSz',N);mar=sect.find('w:pgMar',N);pw=int(page.get(W+'w'));m=(pw-8081)//2
    mar.set(W+'left',str(m));mar.set(W+'right',str(pw-8081-m));b.append(sect)
    qa=dict(candidate);qa['word/document.xml']=E.tostring(preview,encoding='UTF-8',xml_declaration=True,standalone=True);write(B/'section16-qa.docx',qa)
    record={'target':str(TARGET),'expected_original_sha256':sha,'candidate':str(out),'candidate_sha256':digest(out),'backup':str(backup),'changed_original_parts':changes,'added_parts':['word/media/section16-backend.png'],'existing_content_preserved':True,'inserted_before':'本人签字','new_section':'16. 后端技术栈','figure':10,'table':15,'image_spacing':'auto','next_module_started':False}
    (B/'prepared.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    (B/'artifact.md').write_text('# 第16节编辑与验证约定\n\n仅在最新原文档签字前追加第16节。保留用户最新保存的第1至15节与全部包部件；沿用第15节标题、正文、图题、表题及三线表样式。新增图10采用黑白图，图片使用自动行距。独立章节按进展栏8081 twip正文宽度渲染；当前环境没有LibreOffice，原生WPS完整分页未经自动验证。配置数据从当前system.toml读取，属于运行设置，不作为新实验成绩。\n\n'+json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    md='# 16. 后端技术栈\n\n'+INTRO+'\n\n图10  后端主要组件与数据流\n\n'+WORKER+'\n\n表15  后端技术组成及作用\n\n|技术组成|选用技术|作用|\n|---|---|---|\n'+'\n'.join('|'+ '|'.join(r)+'|' for r in ROWS)+'\n\n'+'\n\n'.join(FOLLOW)+'\n'
    (ROOT/'docs/paper/中期报告续写/16_后端技术栈_对齐原稿待审.md').write_text(md,encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False,indent=2))

def commit():
    data=json.loads((B/'prepared.json').read_text(encoding='utf-8'))
    assert digest(TARGET)==data['expected_original_sha256'],'原文件已变化，停止覆盖'
    candidate=Path(data['candidate']);assert digest(candidate)==data['candidate_sha256']
    assert digest(Path(data['backup']))==data['expected_original_sha256']
    fd,t=tempfile.mkstemp(prefix='.section16-',suffix='.docx',dir=str(TARGET.parent));os.close(fd);t=Path(t)
    try:
        shutil.copyfile(candidate,t)
        with ZipFile(t) as z:assert z.testzip() is None
        assert digest(TARGET)==data['expected_original_sha256']
        os.replace(t,TARGET)
    finally:
        if t.exists():t.unlink()
    assert digest(TARGET)==data['candidate_sha256']
    print('已写入原文件：'+str(TARGET))

if __name__=='__main__':commit() if '--commit' in sys.argv else prepare()
