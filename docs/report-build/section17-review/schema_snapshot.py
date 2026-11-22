from pathlib import Path
import json,hashlib
from zipfile import ZipFile
from lxml import etree as E
root=Path(__file__).resolve().parents[3];b=Path(__file__).parent
schema=json.loads((root/'migration_system/docs/deployment/mysql_handoff_v2/schema_multi_user.json').read_text(encoding='utf-8'))
names=['users','auth_sessions','user_limits','user_usage_daily','source_inputs','input_owners','migration_jobs','job_owners','migration_model_calls','migration_files','audit_logs']
tables={t['name']:t for t in schema['tables']}
for n in names:
    t=tables[n]
    print(json.dumps({'name':n,'primary_key':t['primary_key'],'unique':t['unique'],'foreign_keys':t['foreign_keys'],'columns':[(c['name'],c['mysql_type'],c['nullable']) for c in t['columns']]},ensure_ascii=False))
assert len(schema['tables'])==schema['table_count']==34
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','ep':'http://schemas.openxmlformats.org/officeDocument/2006/extended-properties'}
with ZipFile(b/'source.docx') as z:
    doc=E.fromstring(z.read('word/document.xml'));texts=[''.join(p.xpath('.//w:t/text()',namespaces=ns)) for p in doc.findall('.//w:p',ns)]
    app=E.fromstring(z.read('docProps/app.xml'));pg=app.find('ep:Pages',ns)
print(json.dumps({'source_sha256':hashlib.sha256((b/'source.docx').read_bytes()).hexdigest(),'section17_exists':any(t=='17. 数据库设计' for t in texts),'cached_pages':pg.text if pg is not None else None},ensure_ascii=False))
statep=root/'docs/paper/中期报告续写/续写状态.json';state=json.loads(statep.read_text(encoding='utf-8-sig'))
state.update({'current_module':'17 数据库设计','current_status':'用户已确认第16节通过；正在按MySQL实际数据表续写第17节','approved_modules':[14,15,16],'current_draft':'17_数据库设计_对齐原稿待审.md'})
statep.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
