from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import json, hashlib
p=Path('C:/Users/soul/Desktop/swu/中期答辩/中期检查表-杨润生.docx')
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','ep':'http://schemas.openxmlformats.org/officeDocument/2006/extended-properties'}
with ZipFile(p) as z:
    root=E.fromstring(z.read('word/document.xml'))
    paras=[''.join(el.xpath('.//w:t/text()',namespaces=ns)) for el in root.findall('.//w:p',ns)]
    headings=[t for t in paras if len(t)<55 and any(t.startswith(str(i)+'.') for i in range(1,20))]
    props=E.fromstring(z.read('docProps/app.xml'))
    cached=props.find('ep:Pages',ns)
    print(json.dumps({'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'headings':headings,'cached_pages':cached.text if cached is not None else None,'tail':paras[-15:],'media_count':len([n for n in z.namelist() if n.startswith('word/media/')])},ensure_ascii=False,indent=2))
statepath=Path('docs/paper/中期报告续写/续写状态.json')
state=json.loads(statepath.read_text(encoding='utf-8-sig'))
state.update({'current_module':'16 后端技术栈','current_status':'用户已确认第15节通过，正在按实际代码续写第16节','approved_modules':[14,15],'current_draft':'16_后端技术栈_对齐原稿待审.md'})
statepath.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
