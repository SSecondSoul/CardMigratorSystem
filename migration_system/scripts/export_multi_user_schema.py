"""Export actual SQLite multi-user metadata as a future MySQL handoff; no DB IO."""
import json
from hashlib import sha256
from pathlib import Path
import argparse
import export_mysql_handoff as baseline

DESTINATION='docs/deployment/mysql_handoff_v2'
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
}}

def build():
    tables=baseline.model_tables(include_accounts=True);infos=[baseline.describe(t,purposes=PURPOSES,meanings=MEANINGS) for t in tables]
    sql='-- FUTURE MYSQL PREPARATION ONLY. Runtime is currently tested on SQLite.\n'
    sql+='CREATE DATABASE `cardmigrator_multi_user_staging` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;\nUSE `cardmigrator_multi_user_staging`;\n\n'
    sql+='\n\n'.join(baseline.ddl(t,purposes=PURPOSES,meanings=MEANINGS) for t in tables)+'\n'
    sources=['src/card_migration_system/persistence/'+n+'.py' for n in baseline.MODULES+['accounts']]
    sources += [str(p.relative_to(baseline.PROJECT)).replace('\\','/') for p in sorted((baseline.PROJECT/'migrations/versions').glob('*.py'))]
    hashes={p:sha256((baseline.PROJECT/p).read_bytes()).hexdigest() for p in sources}
    data={'schema_basis':'0008_multi_user','table_count':len(tables),'status':'implemented_sqlite_mysql_runtime_not_adapted','tables':infos,'source_sha256':hashes}
    doc='''# 多用户数据库交接 v2：与 SQLite 0008 实现对齐

日期：2026-11-18。此文件替代 v1 草案用于后续 MySQL 适配：users、会话、所有权、额度、审计与限流已在本电脑的 SQLite 实现；**MySQL 驱动、初始化、事务、备份与检查点仍未适配，不代表切换连接串即可使用。**

仅允许另一台 AI 经确认后，在 MySQL 8.4 的全新 `cardmigrator_multi_user_staging` 准备库执行下方 SQL；不得覆盖 v1 准备库、原 SQLite 或任何现有库。遇到同名库/语句失败立即停止，不用 IF NOT EXISTS、关闭外键检查或删表掩盖错误。DDL 不保证整批回滚。密码、模型 Key、演示用户和 Alembic 版本行不包含在 SQL 中。

本文件可单独交给另一台 AI；同目录 SQL/JSON 是对应副本。网络监听、最小权限账号、TLS、验收和非敏感回报模板继续参考 v1 第 1、8、9 节，但**本版表数与字段以本文件为准**。另一个 AI 不应执行 v1 第 7 节旧草案，尤其不能另加已被实现替代的字段。

## 结构与边界

- 保留原 26 张基线表，再新增 8 张账号相关表，共 34 张。不修改旧 request、binding、哈希或实验来源。
- `users → input_owners → source_inputs`，`users → job_owners → migration_jobs`。创建任务时后台在事务中验证源码所属账号与任务账号相同；当前没有为此新增复合数据库 FK，不要误称数据库单独证明了所有权。
- `users → auth_sessions / user_limits / user_usage_daily / audit_logs(actor_id)`。audit_logs.target_id 是不透明审计对象，不是所有表的通用外键。
- 任务文件、模型调用和人工反馈沿 job 所有权鉴权；历史无 owner 的记录仅管理员访问，不自动分配。
- 任务表仍是全局 UNIQUE(idempotency_key)，后台把用户 ID 与客户端幂等键一起哈希后保存，实现用户范围内幂等；不擅自用草案的复合唯一键替换。
- Auth Cookie 明文不入库；CSRF 从当前随机 Cookie 凭据派生并校验，不存在草案中的 csrf_token_sha256 列。账号密码使用 scrypt；登录 token 的 SHA-256 不是密码存储方案。
- user_usage_daily 的调用次数在模型发出前与调用开始记录同事务预留；响应未知/用量未知阻断该用户后续调用，重放收据不重复结算。Token 限制是软停止线，源码配额不包含全部产物。
- Float 映射为 DOUBLE 保持 Unix 秒精度；INTEGER 为有符号 32 位，后续搬迁若有超范围值必须先审查，不截断。字符串保持原长度与区分大小写的 utf8mb4_0900_bin。保留 JSON、NULL、CHECK、UNIQUE 和 FK，引用删除使用 RESTRICT。
- Vue/San/SSM/截图等文件仍在应用产物目录，数据库不是文件备份。LangGraph 检查点仍由 SQLite saver 管理，不手工猜建检查点表。
- alembic_version 在准备库保持空表，不能手动 stamp 为 0008 冒充完成 MySQL 接入；实际升级由后续已验证的迁移流程执行。
- 用户初始数据应由应用 init-admin 隐藏密码提示和管理界面创建，不在 SQL 中填默认管理员/明文密码。

## 字段与约束

'''
    for info in infos:
        doc+=f"### {info['name']}\n\n{info['purpose']}\n\n| 字段 | 类型 | 可空 | 含义 |\n|---|---|---|---|\n"
        for c in info['columns']:doc+=f"| `{c['name']}` | {c['mysql_type']} | {'是' if c['nullable'] else '否'} | {c['meaning']}{'；PK' if c['name'] in info['primary_key'] else ''} |\n"
        doc+='\nUNIQUE：'+str(info['unique'])+'；CHECK：'+str(info['checks'])+'。\n\n'
        for f in info['foreign_keys']:doc+=f"- `{info['name']}({', '.join(f['columns'])})` → `{f['target_table']}({', '.join(f['target_columns'])})`。\n"
        doc+='\n'
    doc+='## 完整 SQL（仅新空库，未在真实 MySQL 实机执行）\n\n```sql\n'+sql+'```\n\n'
    doc+='## 回报要求\n\n报告 MySQL 版本、内网地址/端口、准备库名、专用账号名（不含密码）、来源 IP 限制/TLS、34 张表的核验、失败语句、CHECK/FK/UNIQUE 负例结果、空 Alembic 版本表。不得宣称账号表建好即完成公网不可信代码执行隔离；系统当前支持受邀可信账号、单 Worker 排队，公网任意源码沙箱尚未交付。\n'
    return {'MYSQL_MULTI_USER_HANDOFF.md':doc,'schema_multi_user.sql':sql,'schema_multi_user.json':json.dumps(data,ensure_ascii=False,indent=2)+'\n'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--json',action='store_true');parser.add_argument('--check',action='store_true');args=parser.parse_args()
    files=build()
    if args.check:
        drift=[n for n,s in files.items() if not (baseline.PROJECT/DESTINATION/n).is_file() or (baseline.PROJECT/DESTINATION/n).read_text(encoding='utf-8')!=s]
        print(json.dumps({'status':'drift' if drift else 'matched','different_files':drift,'database_connected':False}));return bool(drift)
    if not args.json:parser.error('Use --json with apply_patch or --check; exporter never writes files')
    print(json.dumps({DESTINATION+'/'+n:s for n,s in files.items()},ensure_ascii=True));return 0
if __name__=='__main__':raise SystemExit(main())
