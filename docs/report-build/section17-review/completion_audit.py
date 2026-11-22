from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import json,hashlib,posixpath,re

B=Path(__file__).parent;ROOT=B.parents[2];SOURCE=B/'completion-audit-source.docx'
N={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','m':'http://schemas.openxmlformats.org/officeDocument/2006/math','ep':'http://schemas.openxmlformats.org/officeDocument/2006/extended-properties'}
W='{'+N['w']+'}'
def text(p):return ''.join(p.xpath('.//w:t/text()',namespaces=N))
def norm(s):return re.sub(r'\s+','',s)
with ZipFile(SOURCE) as z:
    assert z.testzip() is None
    parts={n:z.read(n) for n in z.namelist()}
root=E.fromstring(parts['word/document.xml']);paras=root.findall('.//w:p',N)
sections={14:'功能设计',15:'前端界面',16:'后端技术栈',17:'数据库设计'}
headings={n:next(p for p in paras if norm(text(p))==f'{n}.{title}') for n,title in sections.items()}
assert all(sum(norm(text(p))==f'{n}.{title}' for p in paras)==1 for n,title in sections.items())
rels={x.get('Id'):x.get('Target') for x in E.fromstring(parts['word/_rels/document.xml.rels'])}
figure_names={8:'系统主要功能划分',9:'迁移工作台本地测试界面',10:'后端主要组件与数据流',11:'网页迁移任务核心表关系'}
figures={}
for number,name in figure_names.items():
    caption=next(p for p in paras if norm(text(p))==f'图{number}{name}')
    picture=caption.getprevious()
    while picture is not None and not picture.findall('.//a:blip',N):picture=picture.getprevious()
    assert picture is not None
    rid=picture.find('.//a:blip',N).get('{'+N['r']+'}embed');target=rels[rid]
    media=target.lstrip('/') if target.startswith('/') else posixpath.normpath('word/'+target)
    assert media in parts and len(parts[media])>100
    spacing=picture.find('w:pPr/w:spacing',N)
    figures[str(number)]={'caption':text(caption),'embedded_asset':media,'sha256':hashlib.sha256(parts[media]).hexdigest(),'image_paragraph_line_rule':spacing.get(W+'lineRule') if spacing is not None else None}
tables={13:'系统主要功能及作用',14:'任务结果页签与查看内容',15:'后端技术组成及作用',16:'核心数据表及主要内容',17:'迁移任务表主要字段说明'}
for number,name in tables.items():assert any(norm(text(p))==f'表{number}{name}' for p in paras)
chapter16=headings[16];section16=[];p=chapter16
while p is not None and p is not headings[17]:section16.append(text(p));p=p.getnext()
chapter16text=''.join(section16)
assert 'FastAPI' in chapter16text and 'Flask' not in chapter16text and '计划采用' not in chapter16text
assert 'MySQL' in chapter16text and 'langgraph.sqlite3' in chapter16text
math_count=len(root.findall('.//m:oMath',N))
font_evidence={}
for n in [13,14,15,16,17]:
    p=next(p for p in paras if text(p).startswith(str(n)+'. '))
    spacing=p.find('w:pPr/w:spacing',N);rfonts=p.find('w:r/w:rPr/w:rFonts',N);size=p.find('w:r/w:rPr/w:sz',N)
    font_evidence[str(n)]={'title':text(p),'font_attributes':dict(rfonts.attrib) if rfonts is not None else {},'size_half_points':size.get(W+'val') if size is not None else None,'spacing':dict(spacing.attrib) if spacing is not None else {}}
state=json.loads((ROOT/'docs/paper/中期报告续写/续写状态.json').read_text(encoding='utf-8-sig'))
cached=E.fromstring(parts['docProps/app.xml']).find('ep:Pages',N)
audit={'current_docx_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'matches_last_written_version':hashlib.sha256(SOURCE.read_bytes()).hexdigest()==state['latest_report_sha256'],'requirements':{'requested_sections_14_to_17_present_once':True,'figures_8_to_11_embedded_and_resolvable':True,'tables_13_to_17_present':True,'native_math_objects_in_existing_report':math_count,'fastapi_wording_in_approved_section16':True,'mysql_business_database_and_separate_local_checkpoint_explained':True,'section17_schema_field_evidence':'verification.json','section17_user_approval':'pending','whole_report_target_latest_user_instruction':'约13页，覆盖旧的5至10页要求','whole_native_wps_pagination':'pending user review; bundled native renderer and WPS COM unavailable'},'approved_sections':state['approved_modules'],'figures':figures,'heading_style_evidence':font_evidence,'cached_page_count_not_current_pagination_proof':cached.text if cached is not None else None,'completion_proven':False,'remaining_gates':['用户审核第17节内容与图表','WPS实际全文篇幅符合约13页目标']}
(B/'completion-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:audit[k] for k in ['current_docx_sha256','matches_last_written_version','requirements','remaining_gates']},ensure_ascii=False,indent=2))
print(json.dumps({'heading_spacing_before':{n:v['spacing'].get(W+'before') for n,v in font_evidence.items()}},ensure_ascii=False))
