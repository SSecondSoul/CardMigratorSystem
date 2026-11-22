import importlib.util, json, tomllib, sys
from pathlib import Path
from lxml import etree as E

spec=importlib.util.spec_from_file_location('append16',Path(__file__).with_name('append_section16.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
record=json.loads((m.B/'prepared.json').read_text(encoding='utf-8'))
target=Path(record['candidate']) if '--candidate' in sys.argv else m.TARGET
parts=m.load(target); original=m.load(Path(record['backup']))
assert m.digest(target)==record['candidate_sha256']
root=E.fromstring(parts['word/document.xml']); old=E.fromstring(original['word/document.xml'])
assert m.text(root).count('16. 后端技术栈')==1
assert '17. ' not in m.text(root)
cell=next(t for t in root.findall('.//w:tr',m.N) if t.findall('w:tc',m.N) and m.text(t.findall('w:tc',m.N)[0])=='论文研究进展').findall('w:tc',m.N)[-1]
children=list(cell)
start=next(i for i,x in enumerate(children) if x.tag==m.W+'p' and m.text(x)=='16. 后端技术栈')
end=next(i for i in range(start,len(children)) if '本人签字' in m.text(children[i]))
added=children[start:end];tables=[x for x in added if x.tag==m.W+'tbl'];pictures=[x for x in added if x.findall('.//a:blip',m.N)]
assert len(tables)==len(pictures)==1
assert len(tables[0].findall('w:tr',m.N))==8
assert pictures[0].find('w:pPr/w:spacing',m.N).get(m.W+'lineRule')=='auto'
assert parts['word/media/section16-backend.png']==m.FIGURE.read_bytes()
for x in added:cell.remove(x)
assert E.tostring(root,method='c14n')==E.tostring(old,method='c14n')
assert all(parts[k]==v for k,v in original.items() if k not in ('word/document.xml','word/_rels/document.xml.rels'))
rels=E.fromstring(parts['word/_rels/document.xml.rels']);oldrels=E.fromstring(original['word/_rels/document.xml.rels'])
assert len(rels)==len(oldrels)+1
assert [E.tostring(x,method='c14n') for x in list(rels)[:-1]]==[E.tostring(x,method='c14n') for x in oldrels]
config=tomllib.loads((m.ROOT/'migration_system/configs/system.toml').read_text(encoding='utf-8'))
params={k:config['model'][k] for k in ['backend','model','max_output_tokens','timeout_seconds','max_calls']}
assert params=={'backend':'qwen','model':'qwen-plus','max_output_tokens':32768,'timeout_seconds':240,'max_calls':4}
assert config['tracing']['enabled'] is False
source_paths=['migration_system/pyproject.toml','migration_system/configs/system.toml','migration_system/src/card_migration_system/interfaces/api/app.py','migration_system/src/card_migration_system/interfaces/api/migrations.py','migration_system/src/card_migration_system/workers/migration.py','migration_system/src/card_migration_system/graph/migration.py','migration_system/src/card_migration_system/adapters/model.py','migration_system/src/card_migration_system/adapters/browser.py','migration_system/src/card_migration_system/persistence/database.py','migration_system/src/card_migration_system/application/storage.py','migration_system/src/card_migration_system/observability/traces.py','migration_system/browser/evaluate.mjs']
report={'verified_file':str(target),'sha256':m.digest(target),'original_content_including_approved_sections_1_to_15_preserved':True,'section16_present_once':True,'embedded_figure10_intact':True,'figure_spacing':'auto','table15_rows_including_header':8,'section17_not_started':True,'runtime_parameters_from_configuration':params,'new_section_preview_pages':2,'whole_report_native_wps_pagination_verified':False,'evidence_sources':{p:m.digest(m.ROOT/p) for p in source_paths}}
candidate='--candidate' in sys.argv
(m.B/('verification-candidate.json' if candidate else 'verification.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if not candidate:
    statepath=m.ROOT/'docs/paper/中期报告续写/续写状态.json';state=json.loads(statepath.read_text(encoding='utf-8-sig'))
    state.update({'current_module':'16 后端技术栈','current_status':'第15节已通过；第16节已写入原文件，图10与表15已核验，等待用户检查','current_draft':'16_后端技术栈_对齐原稿待审.md','current_word_draft':str(m.TARGET),'latest_report_sha256':m.digest(m.TARGET),'approved_modules':[14,15],'backup':record['backup'],'next_modules_started':False})
    statepath.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='evidence_sources'},ensure_ascii=False,indent=2))
