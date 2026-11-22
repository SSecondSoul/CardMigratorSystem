from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
from copy import deepcopy
import hashlib,json,shutil,os,tempfile,sys
from docx import Document
from docx.shared import Inches

ROOT=Path(__file__).resolve().parents[3]
B=ROOT/'docs/report-build/section14-inplace';B.mkdir(parents=True,exist_ok=True)
TARGET=Path(r'C:/Users/soul/Desktop/swu/中期答辩/中期检查表-杨润生.docx')
REVIEW=ROOT/'output/reports/第14节_功能设计_按现有报告格式待审.docx'
N={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing','pic':'http://schemas.openxmlformats.org/drawingml/2006/picture'}
W='{'+N['w']+'}';RNS='http://schemas.openxmlformats.org/package/2006/relationships'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def text(p):return ''.join(p.xpath('.//w:t/text()',namespaces=N))
def load(p):
 with ZipFile(p) as z:return {n:z.read(n) for n in z.namelist()}
def write(p,parts):
 with ZipFile(p,'w',ZIP_DEFLATED) as z:
  for n,b in parts.items():z.writestr(n,b)

def prepare():
 original=load(TARGET);sha=digest(TARGET);root=E.fromstring(original['word/document.xml'])
 assert '14. 功能设计' not in text(root),'第14节已经存在，停止重复追加'
 tr=next(t for t in root.findall('.//w:tr',N) if t.findall('w:tc',N) and text(t.findall('w:tc',N)[0])=='论文研究进展')
 cell=tr.findall('w:tc',N)[-1]
 signature=next(p for p in cell.findall('w:p',N) if '本人签字' in text(p))
 old_children=[E.tostring(x,method='c14n') for x in cell]
 review=load(REVIEW);rr=E.fromstring(review['word/document.xml']);nodes=[deepcopy(x) for x in rr.find('w:body',N) if x.tag!=W+'sectPr']
 assert text(nodes[0])=='14. 功能设计'
 assert sum(x.tag==W+'tbl' for x in nodes)==1
 # Use the checked figure asset even if a local editor removed the preview image.
 tmp=Document();p=tmp.add_paragraph();p.add_run().add_picture(str(ROOT/'docs/report-build/section14-review/section14-functions.png'),width=Inches(5.4));tmp.save(B/'figure.docx')
 figparts=load(B/'figure.docx');fr=E.fromstring(figparts['word/document.xml']);fp=deepcopy(fr.find('w:body/w:p',N))
 fp.insert(0,deepcopy(nodes[2].find('w:pPr',N)))
 image_spacing=fp.find('w:pPr/w:spacing',N)
 image_spacing.set(W+'line','240');image_spacing.set(W+'lineRule','auto');image_spacing.set(W+'after','80')
 frels=E.fromstring(figparts['word/_rels/document.xml.rels']);blip=fp.find('.//a:blip',N);oldrid=blip.get('{'+N['r']+'}embed');media=next(x.get('Target') for x in frels if x.get('Id')==oldrid)
 rid='rIdSection14Figure8';rels=E.fromstring(original['word/_rels/document.xml.rels'])
 assert not any(x.get('Id')==rid for x in rels)
 blip.set('{'+N['r']+'}embed',rid)
 nextid=max([int(x.get('id','0')) for x in root.findall('.//wp:docPr',N)]+[0])+1
 for x in fp.findall('.//wp:docPr',N):x.set('id',str(nextid));x.set('name','图8 系统主要功能划分')
 nodes[2]=fp
 for node in nodes:
  for p in node.iter():
   for key in list(p.attrib):
    if key.endswith('paraId') or key.endswith('textId'):del p.attrib[key]
  for mark in node.findall('.//w:bookmarkStart',N)+node.findall('.//w:bookmarkEnd',N):mark.getparent().remove(mark)
 at=list(cell).index(signature)
 for i,node in enumerate(nodes):cell.insert(at+i,node)
 assert [E.tostring(x,method='c14n') for x in list(cell)[:at]]==old_children[:at]
 assert [E.tostring(x,method='c14n') for x in list(cell)[at+len(nodes):]]==old_children[at:]
 E.SubElement(rels,'{'+RNS+'}Relationship',Id=rid,Type=N['r']+'/image',Target='media/section14-functions.png')
 candidate=dict(original);candidate['word/document.xml']=E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True);candidate['word/_rels/document.xml.rels']=E.tostring(rels,encoding='UTF-8',xml_declaration=True,standalone=True);candidate['word/media/section14-functions.png']=figparts['word/'+media]
 backup=B/f'中期检查表-杨润生_续写第14节前备份_{sha[:8]}.docx'
 if not backup.exists():shutil.copy2(TARGET,backup)
 assert digest(backup)==sha
 out=B/'candidate.docx';write(out,candidate)
 with ZipFile(out) as z:assert z.testzip() is None
 assert text(root).count('14. 功能设计')==1 and '15. 前端界面' not in text(root)
 changes=[n for n in original if original[n]!=candidate[n]]
 assert set(changes)=={'word/document.xml','word/_rels/document.xml.rels'}
 # Isolate the appended block for reliable visual QA of every new element.
 preview=deepcopy(root);body=preview.find('w:body',N);sect=deepcopy(body.find('w:sectPr',N))
 for child in list(body):body.remove(child)
 for node in nodes:body.append(deepcopy(node))
 page=sect.find('w:pgSz',N);mar=sect.find('w:pgMar',N);pw=int(page.get(W+'w'));m=(pw-8081)//2;mar.set(W+'left',str(m));mar.set(W+'right',str(pw-8081-m));body.append(sect)
 qa=dict(candidate);qa['word/document.xml']=E.tostring(preview,encoding='UTF-8',xml_declaration=True,standalone=True);write(B/'section14-qa.docx',qa)
 record={'target':str(TARGET),'expected_original_sha256':sha,'candidate':str(out),'candidate_sha256':digest(out),'backup':str(backup),'changed_original_parts':changes,'added_parts':['word/media/section14-functions.png'],'existing_progress_elements_preserved':True,'inserted_before':'本人签字','new_sections':['14. 功能设计'],'next_module_started':False}
 (B/'prepared.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(record,ensure_ascii=False,indent=2))

def commit():
 data=json.loads((B/'prepared.json').read_text(encoding='utf-8'))
 assert digest(TARGET)==data['expected_original_sha256'],'原文件已变化，停止覆盖'
 candidate=Path(data['candidate']);assert digest(candidate)==data['candidate_sha256']
 assert digest(Path(data['backup']))==data['expected_original_sha256']
 fd,temporary=tempfile.mkstemp(prefix='.section14-',suffix='.docx',dir=str(TARGET.parent));os.close(fd);temporary=Path(temporary)
 try:
  shutil.copyfile(candidate,temporary)
  with ZipFile(temporary) as z:assert z.testzip() is None
  assert digest(TARGET)==data['expected_original_sha256']
  os.replace(temporary,TARGET)
 finally:
  if temporary.exists():temporary.unlink()
 assert digest(TARGET)==data['candidate_sha256']
 print('已写入原文件：'+str(TARGET))

if __name__=='__main__':commit() if '--commit' in sys.argv else prepare()
