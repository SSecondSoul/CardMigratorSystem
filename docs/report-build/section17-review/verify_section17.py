from pathlib import Path
from copy import deepcopy
from collections import Counter
import ast,json,sys
from lxml import etree as E
import append_section17 as M
import section17_content as C

B=Path(__file__).parent;ROOT=M.ROOT;N=M.N
info=json.loads((B/'prepared.json').read_text(encoding='utf-8'))
candidate='--candidate' in sys.argv
target=Path(info['candidate']) if candidate else M.TARGET
assert M.digest(target)==info['candidate_sha256']
parts=M.load(target);oldparts=M.load(Path(info['backup']));root=E.fromstring(parts['word/document.xml'])
assert M.text(root).count('17. 数据库设计')==1 and '18. ' not in M.text(root)
cell=next(t for t in root.findall('.//w:tr',N) if t.findall('w:tc',N) and M.text(t.findall('w:tc',N)[0])=='论文研究进展').findall('w:tc',N)[-1]
children=list(cell);start=next(i for i,x in enumerate(children) if M.text(x)=='17. 数据库设计')
end=next(i for i in range(start,len(children)) if '本人签字' in M.text(children[i]));added=children[start:end]
tables=[x for x in added if x.tag==M.W+'tbl'];pictures=[x for x in added if x.findall('.//a:blip',N)]
assert len(tables)==2 and len(pictures)==1
assert len(tables[0].findall('w:tr',N))==len(C.CORE_ROWS)+1==16
assert len(tables[1].findall('w:tr',N))==len(C.JOB_ROWS)+1==9
for table in tables:
    assert table.find('w:tr/w:trPr/w:tblHeader',N).get(M.W+'val')=='1'
    assert all(p.find('w:pPr/w:keepNext',N).get(M.W+'val')=='1' for p in table.findall('w:tr',N)[0].findall('w:tc/w:p',N))
assert pictures[0].find('w:pPr/w:spacing',N).get(M.W+'lineRule')=='auto'
assert parts['word/media/section17-database.png']==M.FIGURE.read_bytes()
for node in added:cell.remove(node)
assert E.tostring(root,method='c14n')==E.tostring(E.fromstring(oldparts['word/document.xml']),method='c14n')
assert all(parts[k]==v for k,v in oldparts.items() if k not in info['changed_original_parts'])
rels=E.fromstring(parts['word/_rels/document.xml.rels']);oldrels=E.fromstring(oldparts['word/_rels/document.xml.rels'])
assert len(rels)==len(oldrels)+1
assert [E.tostring(x,method='c14n') for x in list(rels)[:-1]]==[E.tostring(x,method='c14n') for x in oldrels]

schema_path=ROOT/'migration_system/docs/deployment/mysql_handoff_v2/schema_multi_user.json'
schema=json.loads(schema_path.read_text(encoding='utf-8'));data={t['name']:t for t in schema['tables']}
assert len(data)==schema['table_count']==34
groups=Counter(t['group'] for t in data.values())
assert groups['当前迁移主链']+groups['共享输入']==5
assert groups['多用户']==8 and groups['运行监控']+groups['版本管理']==2
assert sum(n for g,n in groups.items() if g.startswith('历史'))==19
current={t['name'] for t in data.values() if not t['group'].startswith('历史')}
assert {r[0] for r in C.CORE_ROWS}==current
for table,fields,_ in C.CORE_ROWS:
    names={c['name'] for c in data[table]['columns']}
    assert set(fields.split('、'))<=names
jobfields={c['name']:c for c in data['migration_jobs']['columns']}
for fields,kind,_ in C.JOB_ROWS:
    for field in fields.split('、'):assert jobfields[field]['mysql_type'].startswith(kind)
assert ['idempotency_key'] in data['migration_jobs']['unique']
assert ['job_id','ordinal'] in data['migration_model_calls']['unique']
assert data['input_owners']['primary_key']==['input_id'] and data['job_owners']['primary_key']==['job_id']
relations=[('input_owners','input_id','source_inputs','id'),('input_owners','user_id','users','id'),('job_owners','job_id','migration_jobs','id'),('job_owners','user_id','users','id'),('migration_jobs','input_id','source_inputs','id'),('migration_model_calls','job_id','migration_jobs','id'),('migration_files','job_id','migration_jobs','id')]
for table,column,parent,key in relations:
    assert any(f['columns']==[column] and f['target_table']==parent and f['target_columns']==[key] for f in data[table]['foreign_keys'])

model_files=['schema_v1.py','migrations.py','accounts.py','worker_health.py'];modeltables={}
for name in model_files:
    source=ROOT/'migration_system/src/card_migration_system/persistence'/name
    tree=ast.parse(source.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='Table' and node.args and isinstance(node.args[0],ast.Constant):
            columns={c.args[0].value for c in node.args[2:] if isinstance(c,ast.Call) and isinstance(c.func,ast.Name) and c.func.id=='Column' and c.args and isinstance(c.args[0],ast.Constant)}
            modeltables[node.args[0].value]=columns
for name in current-{'alembic_version'}:
    assert modeltables[name]=={c['name'] for c in data[name]['columns']},name
native_path=ROOT/'migration_system/docs/verification/2026-11-18_mysql_cloud_integration/bootstrap_native_checks_passed.json'
native=json.loads(native_path.read_text(encoding='utf-8'))
assert native['schema']['actual_tables']==34 and native['schema']['differences_total']==0
assert native['schema_revision']==schema['schema_basis']=='0008_multi_user'
checks=['json_unicode_and_null','epoch_roundtrip','unique_enforced','foreign_key_enforced','insert_readback_and_rollback','two_connection_lock_exclusion']
assert all(native['native_checks'][key] is True for key in checks)

sources=[schema_path,native_path]+[ROOT/'migration_system/src/card_migration_system/persistence'/p for p in model_files]+[ROOT/'migration_system/src/card_migration_system/application/migrations.py',ROOT/'migration_system/src/card_migration_system/application/accounts.py',ROOT/'migration_system/src/card_migration_system/graph/migration.py',ROOT/'migration_system/src/card_migration_system/config.py']
result={'verified_file':str(target),'sha256':M.digest(target),'section17_present_once':True,'sections_1_to_16_and_other_original_content_preserved':True,'figure11_embedded_intact':True,'picture_spacing':'auto','table16_current_tables':15,'table17_field_groups':8,'repeated_headers_keep_with_next_row':True,'mysql_schema_tables':34,'historical_tables':19,'local_models_match_schema_snapshot':True,'diagram_relations_verified':len(relations),'schema_revision':'0008_multi_user','database_checks_source':'existing 2026-11-18 native verification records; no new cloud experiment','new_section_preview_pages':len(list((B/'qa-final-delivery').glob('page-*.png'))),'combined_sections14_to17_preview_pages':len(list((B/'combined-qa-final-delivery').glob('page-*.png'))),'whole_native_wps_pagination_verified':False,'whole_report_page_target':'13页左右，用户最新要求','source_evidence':{str(p.relative_to(ROOT)):M.digest(p) for p in sources}}
(B/('verification-candidate.json' if candidate else 'verification.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
if not candidate:
    statepath=ROOT/'docs/paper/中期报告续写/续写状态.json';state=json.loads(statepath.read_text(encoding='utf-8-sig'))
    state.update({'objective':'从第14节起续写功能设计、前端界面、后端技术栈、数据库设计；全文约13页，逐模块经用户检查通过后推进','current_module':'17 数据库设计','current_status':'第16节已通过；第17节已写入原文档，图11及表16、表17已核验，等待用户检查内容与全文页数','current_draft':'17_数据库设计_对齐原稿待审.md','current_word_draft':str(M.TARGET),'latest_report_sha256':M.digest(M.TARGET),'approved_modules':[14,15,16],'backup':info['backup'],'next_modules_started':False,'page_budget_scope':'用户最新要求整份报告13页左右；数据库部分已精简，完整WPS页数待用户打开检查'})
    statepath.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='source_evidence'},ensure_ascii=False,indent=2))
