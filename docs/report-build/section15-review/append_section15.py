from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
from copy import deepcopy
import hashlib, json, shutil, os, tempfile, sys
from docx import Document
from docx.shared import Inches

ROOT = Path(__file__).resolve().parents[3]
B = Path(__file__).parent
TARGET = Path('C:/Users/soul/Desktop/swu/中期答辩/中期检查表-杨润生.docx')
FIGURE = ROOT/'migration_system/var/workbench-ui-user-simplified-01/desktop-viewport.png'
N = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main', 'a':'http://schemas.openxmlformats.org/drawingml/2006/main', 'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships', 'wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
W = '{'+N['w']+'}'
RNS = 'http://schemas.openxmlformats.org/package/2006/relationships'

INTRO = '前端采用迁移工作台的形式，将任务入口、处理进度和结果查看放在同一个页面中，如图9所示。左侧导航提供新建迁移、任务记录等入口，中间列出最近任务，右侧展示选中任务的检查结果；顶部保留任务名称、状态及下载按钮，用户可以先了解本次任务的情况，再查看具体问题。'
EXAMPLE = '图9为已有冻结任务在临时测试环境中的页面截图。其中，结构一致性为24.0%，UI还原度为82.7%，像素差异率为2.1%，任务仍显示“检查未通过”。这说明用户需要结合各项检查判断结果，不能仅凭像素差异较小就认为迁移成功。上述数值只对应截图中的单个任务，不代表整个数据集的迁移效果。'
ROWS = [
    ['质量评估', '指标、界面对比及结构与语义检查。', '先看结论，再查未通过项。'],
    ['San代码', '当前接受版本的代码及文件标识。', '浏览、复制或下载生成代码。'],
    ['修复记录', '各轮候选、接受或回退结果及原因。', '查看修改结果与停止原因。'],
    ['产物与验收', '已登记文件、SSM下载入口及完整报告。', '查找和下载本次任务的文件。'],
]
FOLLOW = [
    '新建任务使用弹窗，集中填写任务名称、文件名和源码。用户可以上传或拖入一个UTF-8编码的Vue文件，也可以直接粘贴源码；文件大小限制为256 KiB，页面同步显示源码字节数，并提示格式、编码或大小问题。最大修复轮数可选0—3轮；props与代表性交互配置默认折叠，需要时再展开填写，减少首次使用时需要处理的内容。',
    '任务提交后，页面依次显示源码解析、SSM提取、代码生成、结构校验、视觉评估和自动修复六个阶段，并用文字、图标与颜色表示状态。结果区按表14划分页签，默认打开质量评估。界面对比支持并排、叠加和差异三种方式：并排查看整体布局，叠加观察位置偏移，差异图帮助寻找变化区域；结构与语义检查放在同一页，详情按需展开，便于结合画面和检查结果定位问题。',
    '检查未运行时显示“—”或“未测试”，暂时没有截图时给出说明。差异明细列出节点路径、属性、Vue源值和San结果，先显示少量记录，再按需加载。代码页展示当前接受版本，修复页保留候选被接受或回退的原因，方便用户追查结果；任务列表还提供名称、文件名或编号搜索及状态筛选。',
    '界面以浅色背景和白色内容区域区分层次，青绿色用于主要操作和当前选中项，异常状态同时配有文字与图标。已有本地页面检查覆盖1586、1024和390像素三种宽度，未发现页面横向溢出；在较窄屏幕下调整内容排列，表格和代码区域保留局部滚动，以便查看较长内容。'
]

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def text(p): return ''.join(p.xpath('.//w:t/text()', namespaces=N))
def load(p):
    with ZipFile(p) as z: return {n:z.read(n) for n in z.namelist()}
def write(p, parts):
    with ZipFile(p, 'w', ZIP_DEFLATED) as z:
        for n, b in parts.items(): z.writestr(n,b)
def paragraph(template, value):
    p = deepcopy(template)
    for key in list(p.attrib):
        if key.endswith('paraId') or key.endswith('textId'): del p.attrib[key]
    rpr = template.find('w:r/w:rPr', N)
    for c in list(p):
        if c.tag != W+'pPr': p.remove(c)
    r = E.SubElement(p, W+'r')
    if rpr is not None: r.append(deepcopy(rpr))
    E.SubElement(r, W+'t').text = value
    return p

def prepare():
    original = load(TARGET); sha = digest(TARGET)
    root = E.fromstring(original['word/document.xml'])
    assert '15. 前端界面' not in text(root), '第15节已存在，停止重复追加'
    assert text(root).count('14. 功能设计') == 1
    tr = next(t for t in root.findall('.//w:tr',N) if t.findall('w:tc',N) and text(t.findall('w:tc',N)[0]) == '论文研究进展')
    cell = tr.findall('w:tc',N)[-1]
    sig = next(p for p in cell.findall('w:p',N) if '本人签字' in text(p))
    paras = cell.findall('w:p',N)
    heading = next(p for p in paras if text(p)=='14. 功能设计')
    body = next(p for p in paras if text(p).startswith('目前已将前述迁移流程'))
    caption = next(p for p in paras if text(p)=='图8  系统主要功能划分')
    tcaption = next(p for p in paras if text(p)=='表13  系统主要功能及作用')
    table = next(t for t in cell.findall('w:tbl',N) if [text(c) for c in t.findall('w:tr/w:tc',N)][:3]==['功能模块','主要操作','作用'])
    nodes = [paragraph(heading,'15. 前端界面'),paragraph(body,INTRO)]
    tmp=Document(); p=tmp.add_paragraph(); p.add_run().add_picture(str(FIGURE),width=Inches(5.5)); tmp.save(B/'picture.docx')
    picparts=load(B/'picture.docx'); pr=E.fromstring(picparts['word/document.xml'])
    pic=deepcopy(pr.find('w:body/w:p',N)); pic.insert(0,deepcopy(caption.find('w:pPr',N)))
    pp=pic.find('w:pPr',N); spacing=pp.find('w:spacing',N)
    spacing.set(W+'line','240'); spacing.set(W+'lineRule','auto'); spacing.set(W+'after','80')
    keep=pp.find('w:keepNext',N)
    if keep is None: keep=E.SubElement(pp,W+'keepNext')
    keep.set(W+'val','1')
    rid='rIdSection15Figure9'; pic.find('.//a:blip',N).set('{'+N['r']+'}embed',rid)
    nextid=max([int(x.get('id','0')) for x in root.findall('.//wp:docPr',N)]+[0])+1
    for x in pic.findall('.//wp:docPr',N):
        x.set('id',str(nextid)); x.set('name','图9 迁移工作台本地测试界面'); x.set('descr','已有冻结任务的本地测试截图。左侧为导航和最近任务，顶部为执行阶段，右侧为质量评估与Vue、San界面对比。')
    nodes += [pic,paragraph(caption,'图9  迁移工作台本地测试界面'),paragraph(body,EXAMPLE),paragraph(tcaption,'表14  任务结果页签与查看内容')]
    tab=deepcopy(table); oldrows=tab.findall('w:tr',N); head=deepcopy(oldrows[0]); pat=deepcopy(oldrows[1])
    for row in oldrows: tab.remove(row)
    def fill(row,values):
        for c,value in zip(row.findall('w:tc',N),values):
            p0=c.find('w:p',N)
            for el in list(c):
                if el.tag!=W+'tcPr': c.remove(el)
            c.append(paragraph(p0,value))
        return row
    tab.append(fill(head,['结果页签','主要内容','用户操作']))
    for row in ROWS: tab.append(fill(deepcopy(pat),row))
    nodes.append(tab)
    for value in FOLLOW:
        p=paragraph(body,value); pp=p.find('w:pPr',N)
        keep=pp.find('w:keepLines',N)
        if keep is None: keep=E.SubElement(pp,W+'keepLines')
        keep.set(W+'val','1'); nodes.append(p)
    oldchildren=[E.tostring(x,method='c14n') for x in cell]; at=list(cell).index(sig)
    for i,node in enumerate(nodes): cell.insert(at+i,node)
    assert [E.tostring(x,method='c14n') for x in list(cell)[:at]]==oldchildren[:at]
    assert [E.tostring(x,method='c14n') for x in list(cell)[at+len(nodes):]]==oldchildren[at:]
    rels=E.fromstring(original['word/_rels/document.xml.rels'])
    assert not any(x.get('Id')==rid for x in rels)
    E.SubElement(rels,'{'+RNS+'}Relationship',Id=rid,Type=N['r']+'/image',Target='media/section15-workbench.png')
    candidate=dict(original)
    candidate['word/document.xml']=E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
    candidate['word/_rels/document.xml.rels']=E.tostring(rels,encoding='UTF-8',xml_declaration=True,standalone=True)
    candidate['word/media/section15-workbench.png']=FIGURE.read_bytes()
    backup=B/f'中期检查表-杨润生_续写第15节前备份_{sha[:8]}.docx'
    if not backup.exists(): shutil.copy2(TARGET,backup)
    assert digest(backup)==sha
    out=B/'candidate.docx'; write(out,candidate)
    changes=[n for n in original if original[n]!=candidate[n]]
    assert set(changes)=={'word/document.xml','word/_rels/document.xml.rels'}
    with ZipFile(out) as z: assert z.testzip() is None
    # Isolate the new block using the report's cell writing width for visual QA.
    preview=deepcopy(root); b=preview.find('w:body',N); sect=deepcopy(b.find('w:sectPr',N))
    for ch in list(b): b.remove(ch)
    for node in nodes: b.append(deepcopy(node))
    page=sect.find('w:pgSz',N); mar=sect.find('w:pgMar',N); pw=int(page.get(W+'w')); m=(pw-8081)//2
    mar.set(W+'left',str(m)); mar.set(W+'right',str(pw-8081-m)); b.append(sect)
    qa=dict(candidate); qa['word/document.xml']=E.tostring(preview,encoding='UTF-8',xml_declaration=True,standalone=True); write(B/'section15-qa.docx',qa)
    record={'target':str(TARGET),'expected_original_sha256':sha,'candidate':str(out),'candidate_sha256':digest(out),'backup':str(backup),'changed_original_parts':changes,'added_parts':['word/media/section15-workbench.png'],'existing_progress_elements_preserved':True,'inserted_before':'本人签字','new_sections':['15. 前端界面'],'figure':9,'table':14,'image_spacing':'auto','next_module_started':False}
    (B/'prepared.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    (B/'artifact.md').write_text('# 第15节续写范围与核验\n\n原稿第1至14节保持不变；仅在本人签字前追加第15节。字体、段距、表格样式沿用已批准第14节；截图采用自动行距，避免裁剪。图9来自已有冻结任务的本地测试，不作为新增实验数据。页面验证采用独立章节预览，不能替代WPS对完整嵌套表格的分页。\n\n'+json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    draft='# 15. 前端界面\n\n'+INTRO+'\n\n图9  迁移工作台本地测试界面\n\n'+EXAMPLE+'\n\n表14  任务结果页签与查看内容\n\n|结果页签|主要内容|用户操作|\n|---|---|---|\n'+'\n'.join('|'+ '|'.join(r)+'|' for r in ROWS)+'\n\n'+'\n\n'.join(FOLLOW)+'\n'
    (ROOT/'docs/paper/中期报告续写/15_前端界面_对齐原稿待审.md').write_text(draft,encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False,indent=2))

def commit():
    data=json.loads((B/'prepared.json').read_text(encoding='utf-8'))
    assert digest(TARGET)==data['expected_original_sha256'], '原文件已变化，停止覆盖'
    candidate=Path(data['candidate']); assert digest(candidate)==data['candidate_sha256']
    assert digest(Path(data['backup']))==data['expected_original_sha256']
    fd,t=tempfile.mkstemp(prefix='.section15-',suffix='.docx',dir=str(TARGET.parent)); os.close(fd); t=Path(t)
    try:
        shutil.copyfile(candidate,t)
        with ZipFile(t) as z: assert z.testzip() is None
        assert digest(TARGET)==data['expected_original_sha256']
        os.replace(t,TARGET)
    finally:
        if t.exists(): t.unlink()
    assert digest(TARGET)==data['candidate_sha256']
    print('已写入原文件：'+str(TARGET))

if __name__=='__main__': commit() if '--commit' in sys.argv else prepare()
