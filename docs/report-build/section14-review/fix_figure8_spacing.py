from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
from copy import deepcopy
import hashlib,json,shutil,tempfile,os,sys
ROOT=Path(__file__).resolve().parents[3];B=ROOT/'docs/report-build/section14-imagefix';B.mkdir(parents=True,exist_ok=True)
TARGET=Path(r'C:/Users/soul/Desktop/swu/中期答辩/中期检查表-杨润生.docx')
N={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'};W='{'+N['w']+'}'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def text(x):return ''.join(x.xpath('.//w:t/text()',namespaces=N))
def write(p,parts):
 with ZipFile(p,'w',ZIP_DEFLATED) as z:
  for n,b in parts.items():z.writestr(n,b)
def prepare():
 with ZipFile(TARGET) as z:original={n:z.read(n) for n in z.namelist()}
 source_sha=digest(TARGET);r=E.fromstring(original['word/document.xml']);ps=r.findall('.//w:p',N)
 caption=next(p for p in ps if text(p)=='图8  系统主要功能划分');picture=caption.getprevious()
 assert picture.find('.//a:blip',N) is not None
 old_other=[E.tostring(p,method='c14n') for p in ps if p is not picture]
 spacing=picture.find('w:pPr/w:spacing',N);old=dict(spacing.attrib)
 spacing.set(W+'line','240');spacing.set(W+'lineRule','auto');spacing.set(W+'before','0');spacing.set(W+'after','80')
 pr=picture.find('w:pPr',N);keep=pr.find('w:keepNext',N)
 if keep is None:keep=E.Element(W+'keepNext');pr.insert(0,keep)
 keep.set(W+'val','1')
 assert [E.tostring(p,method='c14n') for p in r.findall('.//w:p',N) if p is not picture]==old_other
 parts=dict(original);parts['word/document.xml']=E.tostring(r,encoding='UTF-8',xml_declaration=True,standalone=True)
 backup=B/f'中期检查表-杨润生_图8显示修复前_{source_sha[:8]}.docx'
 if not backup.exists():shutil.copy2(TARGET,backup)
 assert digest(backup)==source_sha
 candidate=B/'candidate.docx';write(candidate,parts)
 assert [n for n in parts if parts[n]!=original[n]]==['word/document.xml']
 with ZipFile(candidate) as z:assert z.testzip() is None
 preview=deepcopy(r);body=preview.find('w:body',N);sect=deepcopy(body.find('w:sectPr',N));cell=next(p for p in preview.findall('.//w:p',N) if text(p)=='14. 功能设计').getparent()
 children=list(cell);a=next(i for i,p in enumerate(children) if text(p)=='14. 功能设计');b=next(i for i,p in enumerate(children[a:],a) if '本人签字' in text(p))
 nodes=[deepcopy(p) for p in children[a:b]]
 for p in list(body):body.remove(p)
 for p in nodes:body.append(p)
 pg=sect.find('w:pgSz',N);mar=sect.find('w:pgMar',N);pw=int(pg.get(W+'w'));m=(pw-8081)//2;mar.set(W+'left',str(m));mar.set(W+'right',str(pw-8081-m));body.append(sect)
 qa=dict(parts);qa['word/document.xml']=E.tostring(preview,encoding='UTF-8',xml_declaration=True,standalone=True);write(B/'section14-qa.docx',qa)
 report={'target':str(TARGET),'original_sha256':source_sha,'candidate':str(candidate),'candidate_sha256':digest(candidate),'backup':str(backup),'changed_parts':['word/document.xml'],'changed_scope':'仅图8图片段落的行距和与图题保持同页设置','old_spacing':old,'new_spacing':dict(spacing.attrib),'other_paragraphs_unchanged':True}
 (B/'prepared.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
def commit():
 d=json.loads((B/'prepared.json').read_text(encoding='utf-8'));assert digest(TARGET)==d['original_sha256'],'原文件已变化，停止覆盖';p=Path(d['candidate']);assert digest(p)==d['candidate_sha256']
 fd,tmp=tempfile.mkstemp(prefix='.figure8-fix-',suffix='.docx',dir=str(TARGET.parent));os.close(fd);tmp=Path(tmp)
 try:
  shutil.copyfile(p,tmp)
  assert digest(TARGET)==d['original_sha256'];os.replace(tmp,TARGET)
 finally:
  if tmp.exists():tmp.unlink()
 assert digest(TARGET)==d['candidate_sha256'];print('原文件图8行距已修复')
if __name__=='__main__':commit() if '--commit' in sys.argv else prepare()
