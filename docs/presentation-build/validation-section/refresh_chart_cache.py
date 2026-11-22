from pathlib import Path
import zipfile,io,xml.etree.ElementTree as E,re
p=Path(__file__).parent/'candidate.pptx'
with zipfile.ZipFile(p) as z:parts={n:z.read(n) for n in z.namelist()}
S={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(io.BytesIO(parts['ppt/embeddings/Workbook1.xlsx'])) as w:
 root=E.fromstring(w.read('xl/worksheets/sheet1.xml')); cells={c.get('r'):c.find('s:v',S).text for c in root.findall('.//s:c',S)}
xml=parts['ppt/charts/chart1.xml'].decode('utf-8')
# Refresh numeric caches only from their exact existing workbook references.
# Source cache and worksheet differ only at floating-point serialization precision.
changes=[]
def ref(match):
 block=match.group(0)
 formula=re.search(r'<c:f>(.*?)</c:f>',block).group(1)
 m=re.search(r'!\$([A-Z]+)\$(\d+):\$([A-Z]+)\$(\d+)',formula)
 if not m:return block
 col,start,_,end=m.groups();start=int(start)
 def pt(mm):
  idx=int(mm.group(1));old=mm.group(2);value=cells[f'{col}{start+idx}']
  assert abs(float(old)-float(value))<1e-10
  if old!=value:changes.append((f'{col}{start+idx}',old,value))
  return mm.group(0).replace('>'+old+'<','>'+value+'<')
 return re.sub(r'<c:pt idx="(\d+)"><c:v>(.*?)</c:v></c:pt>',pt,block)
xml=re.sub(r'<c:numRef>.*?</c:numRef>',ref,xml,flags=re.S)
parts['ppt/charts/chart1.xml']=xml.encode('utf-8')
with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
 for n,b in parts.items():z.writestr(n,b)
print('Existing chart cache precision synchronized:',len(changes),'values; no displayed rounding changes.')
