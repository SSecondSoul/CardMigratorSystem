from lxml import etree as E
from collections import Counter
import append_section17 as M
root=E.fromstring(M.load(M.SOURCE)['word/document.xml'])
tr=next(t for t in root.findall('.//w:tr',M.N) if t.findall('w:tc',M.N) and M.text(t.findall('w:tc',M.N)[0])=='论文研究进展')
cell=tr.findall('w:tc',M.N)[-1];ps=cell.findall('w:p',M.N)
blank=[p for p in ps if not M.text(p).strip() and not p.findall('.//w:drawing',M.N) and not p.findall('.//w:object',M.N) and not p.findall('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath')]
print('Direct paragraphs',len(ps),'empty text/no drawing/math',len(blank))
for p in blank:
    print(E.tostring(p,encoding='unicode')[:500])
print('Spacing counts',Counter(tuple(sorted(p.find('w:pPr/w:spacing',M.N).attrib.items())) for p in ps if p.find('w:pPr/w:spacing',M.N) is not None))
