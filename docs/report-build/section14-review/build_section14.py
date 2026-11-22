from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
from copy import deepcopy
import json,hashlib,subprocess
from docx import Document
from docx.shared import Inches

ROOT=Path(__file__).resolve().parents[3]
BUILD=Path(__file__).parent
SRC=Path(r'C:/Users/soul/Desktop/swu/中期答辩/中期检查表-杨润生.docx')
OUT=ROOT/'output/reports/第14节_功能设计_按现有报告格式待审.docx'
N={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing','pic':'http://schemas.openxmlformats.org/drawingml/2006/picture'}
W='{'+N['w']+'}'
with ZipFile(SRC) as z:parts={name:z.read(name) for name in z.namelist()}
sha=hashlib.sha256(SRC.read_bytes()).hexdigest()
root=E.fromstring(parts['word/document.xml']);paras=root.findall('.//w:p',N)
def text(el):return ''.join(el.xpath('.//w:t/text()',namespaces=N))
heading=next(p for p in paras if text(p)=='13. 生成San代码')
body_style=next(p for p in paras if text(p).startswith('系统已实现San单文件组件的生成'))
caption_style=next(p for p in paras if text(p)=='图7  规则修复与大模型修复的选择流程')
table_caption_style=next(p for p in paras if text(p).startswith('表12  San单文件组件'))
table_style=next(t for t in root.findall('.//w:tbl',N) if [text(c) for c in t.findall('w:tr/w:tc',N)][:3]==['检查方面','检查内容','检查目的或示例'])
def paragraph(template,value):
 p=deepcopy(template)
 for key in list(p.attrib):
  if key.endswith('paraId') or key.endswith('textId'):del p.attrib[key]
 rpr=template.find('w:r/w:rPr',N)
 for child in list(p):
  if child.tag!=W+'pPr':p.remove(child)
 r=E.SubElement(p,W+'r')
 if rpr is not None:r.append(deepcopy(rpr))
 E.SubElement(r,W+'t').text=value
 return p
intro='目前已将前述迁移流程整合到网页系统中，用户可以提交源码、查看进度、检查结果和下载文件。功能以一次迁移任务为主线，并补充历史记录、账号管理和运行状态查看，主要划分见图8，具体作用见表13。'
rows=[['任务创建','上传或粘贴Vue源码，填写任务和检查配置。','统一提交一次迁移任务。'],['迁移运行','查看执行阶段、自动修复和停止原因。','了解任务进度及停止原因。'],['结果查看','比较两端界面，查看检查差异、代码和修复记录。','了解迁移效果及存在的问题。'],['文件与历史记录','下载代码与报告，查找并重新打开任务。','保存结果，便于后续查看。'],['账号管理','用户管理本人账号；管理员管理账号和使用额度。','分开管理不同用户的任务。'],['运行状态查看','查看后台连接、执行程序及模型信息。','发现服务未启动等运行问题。']]
follow=[
'使用时，用户先上传Vue文件或粘贴源码，填写任务名称，并选择最多修复几轮，目前允许设置0—3轮。任务提交后，系统按前述流程处理，页面显示排队、执行中或已结束等状态；出现问题时给出原因，方便用户继续查看。',
'结果页面把检查结论、界面对比、San代码和修复记录放在一起。用户可以先看哪些检查通过、哪些没有通过，再查看具体差异或下载文件。没有配置交互检查时，系统显示“未测试”；已经生成代码和检查全部通过也分别记录，避免只看到文件就认为迁移成功。',
'多人使用时，普通用户只能查看和操作自己的任务，并可以修改密码、查看本人用量；管理员可以创建、启用或禁用账号，并设置使用额度。“设置与连接”页面主要用于查看服务状态，模型密钥和主要运行参数仍由后台配置。'
]
nodes=[paragraph(heading,'14. 功能设计'),paragraph(body_style,intro)]
# Drawings are generated in a small temporary package, then inserted with source typography.
tmp=Document();p=tmp.add_paragraph();p.add_run().add_picture(str(BUILD/'section14-functions.png'),width=Inches(5.4));tmp.save(BUILD/'picture.docx')
with ZipFile(BUILD/'picture.docx') as z:
 picroot=E.fromstring(z.read('word/document.xml'));picp=deepcopy(picroot.find('w:body/w:p',N))
 oldr=E.fromstring(z.read('word/_rels/document.xml.rels'));embed=picp.find('.//a:blip',N);oldid=embed.get('{'+N['r']+'}embed');target=next(x.get('Target') for x in oldr if x.get('Id')==oldid);png=z.read('word/'+target)
picp.insert(0,deepcopy(caption_style.find('w:pPr',N)))
image_spacing=picp.find('w:pPr/w:spacing',N)
image_spacing.set(W+'line','240');image_spacing.set(W+'lineRule','auto');image_spacing.set(W+'after','80')
embed.set('{'+N['r']+'}embed','rIdSection14Figure8')
for d in picp.findall('.//wp:docPr',N):d.set('id','14008');d.set('name','图8 系统主要功能划分')
nodes += [picp,paragraph(caption_style,'图8  系统主要功能划分'),paragraph(table_caption_style,'表13  系统主要功能及作用')]
tab=deepcopy(table_style);allrows=tab.findall('w:tr',N);headrow=deepcopy(allrows[0]);rowpattern=deepcopy(allrows[1])
for r in allrows:tab.remove(r)
def fill_row(row,values):
 for cell,value in zip(row.findall('w:tc',N),values):
  p0=cell.find('w:p',N)
  for child in list(cell):
   if child.tag!=W+'tcPr':cell.remove(child)
  cell.append(paragraph(p0,value))
 return row
tab.append(fill_row(headrow,['功能模块','主要操作','作用']))
for values in rows:tab.append(fill_row(deepcopy(rowpattern),values))
nodes.append(tab);nodes.extend(paragraph(body_style,t) for t in follow)
newroot=deepcopy(root);container=newroot.find('w:body',N);sect=deepcopy(container.find('w:sectPr',N))
for child in list(container):container.remove(child)
for node in nodes:container.append(node)
# Match the writing width inside the report's progress cell, without reproducing the form furniture.
page=sect.find('w:pgSz',N);mar=sect.find('w:pgMar',N);pagew=int(page.get(W+'w'))
margin=(pagew-8081)//2;mar.set(W+'left',str(margin));mar.set(W+'right',str(pagew-8081-margin))
container.append(sect)
parts['word/document.xml']=E.tostring(newroot,encoding='UTF-8',xml_declaration=True,standalone=True)
rels=E.fromstring(parts['word/_rels/document.xml.rels']);RNS='http://schemas.openxmlformats.org/package/2006/relationships'
E.SubElement(rels,'{'+RNS+'}Relationship',Id='rIdSection14Figure8',Type=N['r']+'/image',Target='media/section14-functions.png')
parts['word/_rels/document.xml.rels']=E.tostring(rels,encoding='UTF-8',xml_declaration=True,standalone=True)
parts['word/media/section14-functions.png']=png
OUT.parent.mkdir(parents=True,exist_ok=True)
with ZipFile(OUT,'w',ZIP_DEFLATED) as z:
 for name,data in parts.items():z.writestr(name,data)
assert hashlib.sha256(SRC.read_bytes()).hexdigest()==sha
record={'source':str(SRC),'source_sha256':sha,'scope':'第14节单节待审稿；未合并和覆盖原报告；后续模块未开始','heading_font':'黑体 12pt','body_font':'宋体 11pt','body_line_spacing':'固定17pt','caption_font':'宋体 9.5pt','table_font':'宋体 9.5pt','figure_number':8,'table_number':13,'output':str(OUT)}
(BUILD/'artifact.md').write_text('# 第14节样式与编辑范围\n\n'+json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
md='# 14. 功能设计\n\n'+intro+'\n\n![图8 系统主要功能划分](14_系统功能划分_对齐原稿.png)\n\n图8  系统主要功能划分\n\n表13  系统主要功能及作用\n\n|功能模块|主要操作|作用|\n|---|---|---|\n'+'\n'.join('|'+ '|'.join(row)+'|' for row in rows)+'\n\n'+'\n\n'.join(follow)+'\n'
(ROOT/'docs/paper/中期报告续写/14_功能设计_对齐原稿待审.md').write_text(md,encoding='utf-8')
state_path=ROOT/'docs/paper/中期报告续写/续写状态.json';state=json.loads(state_path.read_text(encoding='utf-8'));state.update({'latest_report_reference':str(SRC),'latest_report_sha256':sha,'current_status':'已按第1至13节的格式和口吻生成第14节单节待审稿，等待用户确认','format_match_verified':True,'current_draft':'14_功能设计_对齐原稿待审.md','current_word_draft':str(OUT),'next_modules_started':False});state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False,indent=2))
