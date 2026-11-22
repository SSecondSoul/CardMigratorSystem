import importlib.util, json
from copy import deepcopy
from lxml import etree as E
from pathlib import Path

spec=importlib.util.spec_from_file_location('append15',Path(__file__).with_name('append_section15.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
record=json.loads((m.B/'prepared.json').read_text(encoding='utf-8'))
parts=m.load(m.TARGET); original=m.load(Path(record['backup']))
assert m.digest(m.TARGET)==record['candidate_sha256']
root=E.fromstring(parts['word/document.xml']); old=E.fromstring(original['word/document.xml'])
assert m.text(root).count('15. 前端界面')==1
assert '16. ' not in m.text(root)
cell=next(t for t in root.findall('.//w:tr',m.N) if t.findall('w:tc',m.N) and m.text(t.findall('w:tc',m.N)[0])=='论文研究进展').findall('w:tc',m.N)[-1]
children=list(cell)
start=next(i for i,x in enumerate(children) if x.tag==m.W+'p' and m.text(x)=='15. 前端界面')
end=next(i for i in range(start,len(children)) if '本人签字' in m.text(children[i]))
added=children[start:end]
assert len([x for x in added if x.tag==m.W+'tbl'])==1
assert len([x for x in added if x.findall('.//a:blip',m.N)])==1
picture=next(x for x in added if x.findall('.//a:blip',m.N))
assert picture.find('w:pPr/w:spacing',m.N).get(m.W+'lineRule')=='auto'
assert parts['word/media/section15-workbench.png']==m.FIGURE.read_bytes()
for x in added: cell.remove(x)
assert E.tostring(root,method='c14n')==E.tostring(old,method='c14n')
assert all(parts[k]==v for k,v in original.items() if k not in ('word/document.xml','word/_rels/document.xml.rels'))
report={'source_sha256':m.digest(m.TARGET),'sections_1_to_14_and_other_original_content_unchanged':True,'section15_present_once':True,'embedded_figure9_intact':True,'figure_spacing':'auto','table14_present':True,'section16_not_started':True,'new_section_preview_pages':2,'full_native_wps_pagination_verified':False}
(m.B/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
statepath=m.ROOT/'docs/paper/中期报告续写/续写状态.json'; state=json.loads(statepath.read_text(encoding='utf-8-sig'))
state.update({'current_module':'15 前端界面','current_status':'第14节已通过；第15节已写入原文件，图9与表14已核验，等待用户检查','current_draft':'15_前端界面_对齐原稿待审.md','current_word_draft':str(m.TARGET),'latest_report_sha256':m.digest(m.TARGET),'approved_modules':[14],'backup':record['backup'],'next_modules_started':False})
statepath.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
