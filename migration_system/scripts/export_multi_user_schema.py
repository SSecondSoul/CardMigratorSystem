"""Export actual SQLite multi-user metadata as a future MySQL handoff; no DB IO."""
import json
from hashlib import sha256
from pathlib import Path
import argparse
import export_mysql_handoff as baseline

DESTINATION='docs/deployment/mysql_handoff_v2'
DATABASE='cardmigrator_multi_user_staging'
HEAD='0008_multi_user'
PURPOSES={**baseline.PURPOSES,**{
    'users':('多用户','账号、密码哈希、角色、启用与强制改密状态。'),
    'auth_sessions':('多用户','可撤销登录会话；只保存高熵凭据摘要。'),
    'user_limits':('多用户','按账号限制任务、调用、Token 停止线与已注册源码字节。'),
    'user_usage_daily':('多用户','按 UTC 日记录任务准入、调用预留和已知 Tokens。'),
    'input_owners':('多用户','源码所有者及实际源码字节数；不重写旧输入表。'),
    'job_owners':('多用户','真实迁移任务所有者；未分配的历史记录只允许管理员访问。'),
    'audit_logs':('多用户','账号、安全与关键任务操作审计，不保存明文密码或模型密钥。'),
    'auth_throttle':('多用户','持久化登录限流窗口，bucket 是账号/IP 组合摘要。'),
}}
MEANINGS={**baseline.MEANINGS,**{
    'username':'ASCII 登录名原值。','username_normalized':'后台小写规范化的唯一登录名。','display_name':'界面显示名称。',
    'password_hash':'Werkzeug scrypt 编码哈希，不能存明文密码。','role':'admin 或 user，实际权限由后台每次校验。',
    'is_active':'账号启用状态。','must_change_password':'管理员创建/重置密码后必须先改密。',
    'password_changed_at':'最近改密 Unix 秒。','user_id':'关联 users.id；不是由客户端自由指定的所有者。',
    'token_sha256':'256 位随机登录凭据的 SHA-256 摘要，不是密码哈希。',
    'origin':'登录绑定的完整同源地址。','revoked_at':'撤销时间，NULL 表示尚未撤销。',
    'max_active_jobs':'排队或执行中任务数上限。','daily_jobs':'UTC 日任务准入上限。',
    'daily_model_calls':'UTC 日模型调用预留次数上限。','daily_tokens_soft':'已知 Tokens 达线后停止下一调用，非硬计费上限。',
    'storage_bytes':'已注册源码字节上限，不包括生成代码和截图。','day':'UTC 日期 YYYY-MM-DD。',
    'jobs_count':'该日成功准入任务数，幂等重试不重复增加。','calls_count':'该日已持久预留的模型调用次数，未知调用也占用。',
    'known_tokens':'实际收据确认的总 Tokens，按调用开始的 UTC 日结算。',
    'byte_size':'对应上传源码的实际 UTF-8 字节数。','actor_id':'可选操作者用户 ID；初始化/失败登录可为空。',
    'target_id':'被操作对象的不透明 ID，不是数据库外键。','bucket':'不含明文凭据的登录限流摘要键。',
    'window_start':'限流窗口开始 Unix 秒。','failures':'当前窗口的已预留登录尝试计数。',
    'action':'当前表的操作类型：安全审计动作，或旧候选接受／回退决策。',
}}

def verification_sql(infos):
    """Read-only metadata and empty-row checks, never output business contents."""
    expected='\nUNION ALL\n'.join("SELECT '"+i['name']+"' AS table_name" for i in infos)
    counts='\nUNION ALL\n'.join(f"SELECT '{i['name']}' AS table_name, COUNT(*) AS rows_must_be_zero FROM `{DATABASE}`.`{i['name']}`" for i in infos)
    return f"""-- Read-only; expect {len(infos)} tables, zero missing/extra tables and zero rows in every table.
SELECT VERSION() AS mysql_version, @@hostname AS db_host, @@port AS db_port, @@SESSION.sql_mode AS sql_mode;
SELECT SCHEMA_NAME, DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='{DATABASE}';
SELECT COLLATION_NAME, PAD_ATTRIBUTE FROM information_schema.COLLATIONS WHERE COLLATION_NAME='utf8mb4_0900_bin';
SELECT COUNT(*) AS table_count_must_be_{len(infos)} FROM information_schema.TABLES WHERE TABLE_SCHEMA='{DATABASE}' AND TABLE_TYPE='BASE TABLE';
WITH expected AS (
{expected}
)
SELECT e.table_name AS missing_table FROM expected e LEFT JOIN information_schema.TABLES t ON t.TABLE_SCHEMA='{DATABASE}' AND t.TABLE_NAME=e.table_name AND t.TABLE_TYPE='BASE TABLE' WHERE t.TABLE_NAME IS NULL;
WITH expected AS (
{expected}
)
SELECT t.TABLE_NAME AS unexpected_table FROM information_schema.TABLES t LEFT JOIN expected e ON e.table_name=t.TABLE_NAME WHERE t.TABLE_SCHEMA='{DATABASE}' AND t.TABLE_TYPE='BASE TABLE' AND e.table_name IS NULL;
SELECT TABLE_NAME, ENGINE, TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA='{DATABASE}' ORDER BY TABLE_NAME;
SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA, CHARACTER_SET_NAME, COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='{DATABASE}' ORDER BY TABLE_NAME, ORDINAL_POSITION;
SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE, ENFORCED FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA='{DATABASE}' ORDER BY TABLE_NAME, CONSTRAINT_NAME;
SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, ORDINAL_POSITION, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE CONSTRAINT_SCHEMA='{DATABASE}' ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION;
SELECT TABLE_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, UPDATE_RULE, DELETE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA='{DATABASE}' ORDER BY TABLE_NAME, CONSTRAINT_NAME;
SELECT tc.TABLE_NAME, cc.CONSTRAINT_NAME, cc.CHECK_CLAUSE FROM information_schema.CHECK_CONSTRAINTS cc JOIN information_schema.TABLE_CONSTRAINTS tc ON tc.CONSTRAINT_SCHEMA=cc.CONSTRAINT_SCHEMA AND tc.CONSTRAINT_NAME=cc.CONSTRAINT_NAME WHERE tc.CONSTRAINT_SCHEMA='{DATABASE}' ORDER BY tc.TABLE_NAME, cc.CONSTRAINT_NAME;
SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME, SUB_PART FROM information_schema.STATISTICS WHERE TABLE_SCHEMA='{DATABASE}' ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;
{counts};
SELECT COUNT(*) AS alembic_rows_must_be_zero FROM `{DATABASE}`.alembic_version;
"""


def build():
    tables=baseline.model_tables(include_accounts=True);infos=[baseline.describe(t,purposes=PURPOSES,meanings=MEANINGS) for t in tables]
    from card_migration_system.persistence.database import HEAD as current_head
    if current_head!=HEAD or set(PURPOSES)!={i['name'] for i in infos}:raise ValueError('Review schema changes before updating the handoff')
    sql='-- FUTURE MYSQL PREPARATION ONLY. Runtime is currently tested on SQLite.\n'
    sql+=f'CREATE DATABASE `{DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;\nUSE `{DATABASE}`;\n\n'
    sql+='\n\n'.join(baseline.ddl(t,purposes=PURPOSES,meanings=MEANINGS) for t in tables)+'\n'
    sources=['src/card_migration_system/persistence/'+n+'.py' for n in baseline.MODULES+['accounts']]
    sources += [str(p.relative_to(baseline.PROJECT)).replace('\\','/') for p in sorted((baseline.PROJECT/'migrations/versions').glob('*.py'))]
    hashes={p:sha256((baseline.PROJECT/p).read_bytes()).hexdigest() for p in sources}
    data={'schema_basis':HEAD,'table_count':len(tables),'status':'implemented_sqlite_mysql_runtime_not_adapted',
          'mysql_version_target':'8.4','database':DATABASE,'collation':baseline.COLLATION,'alembic_version_rows':0,
          'tables':infos,'source_sha256':hashes,'schema_sql_sha256':sha256(sql.encode('utf-8')).hexdigest(),
          'constraint_counts':{'primary_keys':len(infos),'unique':sum(len(i['unique']) for i in infos),
                               'foreign_keys':sum(len(i['foreign_keys']) for i in infos),'checks':sum(len(i['checks']) for i in infos)}}
    template=Path(__file__).resolve().parent/'templates'
    doc=(template/'mysql_handoff_v2_intro.md').read_text(encoding='utf-8')+'\n'
    doc+='| 表 | 分组 | 作用 |\n| --- | --- | --- |\n'
    for info in infos:doc+=f"| `{info['name']}` | {info['group']} | {info['purpose']} |\n"
    doc+='\n关系简图（具体 FK 以逐字段约束为准）：\n\n```text\nusers 1 → N auth_sessions / user_usage_daily / input_owners / job_owners / audit_logs(actor_id)\nusers 1 → 0..1 user_limits（应用创建账号时同时创建）\nsource_inputs 1 → 0..1 input_owners；migration_jobs 1 → 0..1 job_owners\nsource_inputs 1 → N migration_jobs → N migration_files / migration_model_calls / migration_feedback\nsource_inputs 1 → N tasks → N runs → N artifact_revisions / attempts / evaluations / candidate_decisions / run_events / worker_locks\nsource_inputs 1 → N ssm_extractions → N ssm_extraction_files / generation_jobs / provider_generation_jobs / generation_approvals\ngeneration_jobs 1 → 0..1 generation_attempts / generation_candidates；1 → N generation_files\nprovider_generation_jobs 1 → 0..1 provider_generation_attempts；1 → N provider_generation_files\ngeneration_approvals 1 → N generation_approval_files\n```\n\nauth_throttle 独立按摘要 bucket 限流；worker_health 是心跳表，不是用户所有权。旧数据允许无 owner，不能把可选关系改成必填并自动归档到新账号。\n\n## 4. 全部字段与约束\n\n除自增事件 ID 外没有数据库生成的业务默认值。NULL／非空、PRIMARY KEY、UNIQUE、FK、CHECK 均按当前模型导出，不补造约束。\n\n'
    for info in infos:
        doc+=f"### {info['name']}\n\n{info['purpose']}\n\n| 字段 | 类型 | 可空 | 含义 |\n|---|---|---|---|\n"
        for c in info['columns']:doc+=f"| `{c['name']}` | {c['mysql_type']} | {'是' if c['nullable'] else '否'} | {c['meaning']}{'；PK' if c['name'] in info['primary_key'] else ''} |\n"
        doc+='\n主键：('+', '.join(info['primary_key'])+')；额外 UNIQUE：'+('；'.join('('+', '.join(u)+')' for u in info['unique']) or '无')+'。\n\n'
        if info['checks']:doc+='CHECK：'+'；'.join('`'+c+'`' for c in info['checks'])+'。\n\n'
        for f in info['foreign_keys']:doc+=f"- `{info['name']}({', '.join(f['columns'])})` → `{f['target_table']}({', '.join(f['target_columns'])})`。\n"
        doc+='\n'
    doc+='## 5. 完整建库 SQL（仅新的空准备库）\n\n包含全部 34 表；不插入用户、版本或业务数据。确认目标实例后执行，遇错停止。\n\n```sql\n'+sql+'```\n\n'
    verify=verification_sql(infos)
    doc+='## 6. 完整只读核验 SQL\n\n建表成功后执行，所有业务表和版本表必须为空。不能代替第 7 节约束实测。\n\n```sql\n'+verify+'```\n\n'
    doc+=(template/'mysql_handoff_v2_finish.md').read_text(encoding='utf-8')+'\n'
    doc+='\n'.join(f'| `{p}` | `{h}` |' for p,h in hashes.items())+'\n'
    return {'MYSQL_MULTI_USER_HANDOFF.md':doc,'schema_multi_user.sql':sql,'schema_multi_user.json':json.dumps(data,ensure_ascii=False,indent=2)+'\n','verify_schema.sql':verify}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--json',action='store_true');parser.add_argument('--check',action='store_true');args=parser.parse_args()
    files=build()
    if args.check:
        drift=[n for n,s in files.items() if not (baseline.PROJECT/DESTINATION/n).is_file() or (baseline.PROJECT/DESTINATION/n).read_text(encoding='utf-8')!=s]
        print(json.dumps({'status':'drift' if drift else 'matched','different_files':drift,'database_connected':False}));return bool(drift)
    if not args.json:parser.error('Use --json with apply_patch or --check; exporter never writes files')
    print(json.dumps({DESTINATION+'/'+n:s for n,s in files.items()},ensure_ascii=True));return 0
if __name__=='__main__':raise SystemExit(main())
