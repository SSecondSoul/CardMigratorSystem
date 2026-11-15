"""Freeze UI/public/persistence reachability evidence before changing the candidate."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT,digest,verify_snapshot
from migration_pipeline.probe_formal_30_v4_parent_dynamic_keys_v1 import MANUAL_SHA

PREVIOUS=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_keys_probe_v1_20261112'
SCOPE=ROOT/'data/experiments/analysis/formal_30_v4_parent_watch_scope_guard_v1_20261111'
OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_key_contract_v1_20261112'
NAMES=['migration_pipeline/audit_parent_dynamic_key_contract.cjs',
 'migration_pipeline/audit_parent_dynamic_key_reachability_runtime.cjs',
 'migration_pipeline/audit_formal_30_v4_parent_dynamic_key_contract_v1.py',
 'tests/test_parent_dynamic_key_contract_audit.py']
NOTEBOOK=ROOT/'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
PREFIX_SHA='80ed25d450919eeb931055bf784ebd9e1e353ed87f9c0ec5e24068b2d9ba015f'
METADATA_SHA='da8e8b42bb4344c317ccdf5038310d76529bda61666c53ff805bcc19dbede418'


def stable(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def inventory():
    old=json.loads((PREVIOUS/'live_inventory.json').read_text(encoding='utf-8'))
    changed=[p for p,sha in old.items() if digest(ROOT/p)!=sha]
    if changed:raise RuntimeError('Previous runtime/probe changed before counterexample freeze: '+str(changed))
    if any(digest(ROOT/p)!=sha for p,sha in MANUAL_SHA.items()):raise RuntimeError('Manual page changed')
    nb=json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    if stable(nb['cells'][:52])!=PREFIX_SHA or stable(nb['metadata'])!=METADATA_SHA:
        raise RuntimeError('Previous 52 Notebook cells or metadata changed')
    return {**old,**{p:digest(ROOT/p) for p in NAMES}}


def fixtures():
    sys.path.insert(0,str(ROOT/'tests'))
    spec=importlib.util.spec_from_file_location('contract_audit_fixture',ROOT/NAMES[-1])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def audit():
    hashes=inventory();verified={'previous_probe':verify_snapshot(PREVIOUS.resolve()),'previous_scope_guard':verify_snapshot(SCOPE.resolve())}
    prior=json.loads((PREVIOUS/'audit.json').read_text(encoding='utf-8'))
    for name,sha in prior['inputs'].items():
        if digest(ROOT/name)!=sha:raise RuntimeError('Pinned source/runtime changed: '+name)
    scope=json.loads((SCOPE/'replay.json').read_text(encoding='utf-8'))
    for row in scope['retained_artifact_replays']:
        for prefix in ['input','vue']:
            if digest(ROOT/row[prefix+'_path'])!=row[prefix+'_sha256']:raise RuntimeError('Retained input changed: '+row['id'])
    fixture=fixtures();payload=fixture.payload()
    source=fixture.node(fixture.STATIC,{'vue':payload['vue']})
    generic_source=fixture.node(fixture.STATIC,{'vue':payload['generic']['vue']})
    runtime=fixture.node(fixture.RUNTIME,payload)
    writer=source['writers'][0]
    if writer['observed_ui_keys']!=['autoSave','defaultView','notifications','syncInterval'] or not writer['ui_routes_finite_in_supported_templates']:
        raise RuntimeError('Unexpected UI producer route evidence')
    if source['public_contract_closed'] or source['production_eligible'] or writer['public_domain_proven']:
        raise RuntimeError('UI routes must not close the public interface')
    def phase(s,v,p):return next(q for r in runtime['runs'] if r['scenario']==s and r['variant']==v for q in r['phases'] if q['name']==p)
    counterexamples=[]
    for scenario in ['restore_extra_nested_object','restore_declared_object_value']:
        a=phase(scenario,'vue_source','mount_tick');b=phase(scenario,'san_normal_flow','mount_tick');c=phase(scenario,'san_dynamic_candidate','mount_tick')
        if a['state']!=b['state'] or a['state']['taskIds']!=[901] or c['state']['taskIds']==[901]:raise RuntimeError('Startup counterexample not reproduced')
        counterexamples.append({'scenario':scenario,'source_task_ids':a['state']['taskIds'],
            'normal_candidate_task_ids':b['state']['taskIds'],'dynamic_candidate_task_ids':c['state']['taskIds'],
            'cause':'Candidate rejects observed root with nested value; source loadInitialData catch replaces saved tasks with sample tasks.',
            'production_defect_count_increment':0,'category':'unpromoted_candidate_repair_regression'})
    public=phase('public_new_object_value','san_dynamic_candidate','action_tick')
    if not any(e['message']=='Dynamic-key probe: unsupported key or value' for e in public['errors']):raise RuntimeError('Public API gap not reproduced')
    computed=[r for r in runtime['pairs'] if r['scenario']=='computed_root_dependency']
    if not all(r['stateEqual'] and r['eventsEqual'] and r['errorsEqual'] for r in computed):raise RuntimeError('Scalar computed control needs review')
    if inventory()!=hashes:raise RuntimeError('Code changed during read-only audit')
    return {'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'source_contract_and_native_counterexample_audit_reused_development_only',
        'source_verified_payloads':verified,'source_inputs':prior['inputs'],
        'previous_probe_inventory_unchanged':390,'production_runtime_inventory_unchanged':387,'inventory_count':len(hashes),
        'manual_page_sha256':MANUAL_SHA,'retained_30_inputs_unchanged':True,'original_aggregate':prior['original_aggregate'],
        'source_contract':source,'generic_source_contract':generic_source,'runtime_observations':runtime,
        'generic_fixture':payload['generic'],'startup_counterexamples':counterexamples,
        'public_object_write_compatibility_gap':True,'scalar_computed_staleness_hypothesis_reproduced':False,
        'production_integration_enabled':False,'source_api_or_storage_schema_restricted':False,
        'candidate_or_canonical_san_modified':False,'production_rules_or_prompt_modified':False,'model_requests':0,
        'full_suite_reexecuted':False,'manual_or_browser_rechecked':False,'original_score_modified':False,
        'prior_full_suite_reference':prior['prior_full_suite'],
        'prior_notebook_cells':52,'prior_notebook_cells_sha256':PREFIX_SHA,'prior_notebook_metadata_sha256':METADATA_SHA,
        'preliminary_attempts':[
            {'kind':'command_construction_failure','runtime_started':False,
             'description':'PowerShell/native -c quoting caused Python SyntaxError in a one-off computed probe; no component runtime ran.'},
            {'kind':'scoped_suite_failure','tests':17,'failures':2,'elapsed_seconds':6.016,
             'evidence_kind':'tool_output_summary_not_saved_raw_log',
             'causes':['Python sliced UTF-16 Babel offsets as Unicode code points.',
                       'Scalar computed staleness was hypothesized but native runtime produced the correct on value.'],
             'resolution':'Label offsets UTF-16 and decode correctly; retain the computed scenario as a passing control, not an invented defect.'}]}


def report(data):
    tests=data['scoped_tests'];table=[]
    for c in data['startup_counterexamples']:
        table.append('| '+c['scenario']+' | '+str(c['source_task_ids'])+' | '+str(c['normal_candidate_task_ids'])+' | '+str(c['dynamic_candidate_task_ids'])+' |')
    return f'''# 动态键公开接口与持久化契约审计 v1（2026-11-12）

**结论：上一轮隔离候选仍不能接入生产。** 4个已知UI键不等于公开接口和历史数据范围。源组件/既有产物不改，未限制原接口、未增加存储schema，未改Prompt或生产规则。0模型请求；原批次24/30、6失败、0执行异常、1,821,544 tokens不变。

## 静态证据

通用AST+模板审计连接父组件方法引用、注册内联子组件、4个原生输入emit：autoSave/notifications为checkbox布尔值；defaultView为list/board字符串；syncInterval为0/30/60/300字符串（父方法负责Number转换）。位置以UTF-16单位记录，并有源码定位测试。重命名及动态事件键均有测试；这是支持语法内的路线证据，不是对任意Vue程序的完备可达性证明。

源updateSettings在写入前没有键/值校验，仍是公开方法。本地JSON中的data.settings经spread合并，不能证明恢复对象仍是扁平标量；saveToLocalStorage还持有聚合对象里的根引用。不能仅按4个UI输入裁剪接口，不能把借用当成绝无别名。

## 原生运行时反例（未修复）

冻结源Vue2.7.16、旧正常流程San和上一轮隔离候选San3.15.6，共5场景×3变体×6阶段=15次运行、90份快照、60对源/目标比较。无浏览器DOM attach；源Vue用空render，San直接attached，存储和业务timer为隔离模拟，真实框架原生队列与computed执行。完整状态/存储事件/错误/警告保留，不只比较最终画面。

| 恢复场景 | Vue任务ID | 旧正常流程San | 隔离动态键候选 |
| --- | --- | --- | --- |
{chr(10).join(table)}

两种嵌套设置都被源与旧正常流程产物接受；候选的平坦标量检查抛错，落入源已有loadInitialData的catch，导致保存任务变成示例任务。这是**同一根因造成的两个反例、一个未部署候选的修复回归**，不是两个新的生产缺陷。另一个公开方法对象值调用在源中成功，在候选中被显式拒绝，属于尚未弥合的接口兼容范围，不得静默当成源也禁止该输入。

原先怀疑“同对象强制通知导致根依赖computed过期”，在本轮扁平标量夹具中**未重现**：源、旧正常流程和候选同步/下一轮的label均更新为on。保留该夹具作为正常控制，不将假设写成缺陷；它仍不证明实际页面的子组件prop/DOM传播。

## 验证与证据边界

定向测试{tests['passed']}/{tests['passed']}，0失败/0跳过，{tests['elapsed_seconds']}秒。不是完整703项重跑；703/703仅引用既有冻结日志。390项上轮清单（含387项生产/既有运行文件）原字节不变，增加4个审计/测试文件后394项；30个保留输入与Vue指纹和两个测试页面不变，Notebook旧52单元/元数据不变。

保留首次探针命令引号错误（未启动运行时），以及首次17项中2项失败：UTF-16定位测试错误和未被观察支持的computed过期假设。修正证据处理/预期后独立重跑，不改源、候选或生产规则来迁就测试。

## 下一步

先修复隔离候选对已观察根对象的平坦值假设，使历史JSON嵌套数据不触发初始化兜底；再补足公开方法对象值、别名/嵌套更新与实际子组件传播证明。保持原公开接口/存储兼容性和两项生产边界阻断，不通过新增白名单或删除诊断来制造通过。存储异常策略仍单独待复核，暂不付费复跑。
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-evidence',action='store_true');args=parser.parse_args()
    if args.write_evidence and OUTPUT.exists():raise FileExistsError('Never overwrite frozen contract evidence')
    hashes=inventory();data=audit();logs='';counts=[]
    if args.write_evidence:
        for suite in ['test_parent_dynamic_key_contract_audit.py','test_parent_dynamic_key_adapter_probe.py','test_parent_watch_scope_guard.py']:
            print('Running scoped suite: '+suite,flush=True)
            proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',suite,'-v'],cwd=ROOT,
                env={**os.environ,'PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8')
            part=proc.stdout+proc.stderr;logs+='\n### '+suite+'\n'+part
            match=re.search(r'Ran (\d+) tests in ([\d.]+)s',part)
            if proc.returncode or not match or '\nOK' not in part or re.search(r'OK\s*\(skipped=',part):
                failed=OUTPUT.parent/(OUTPUT.name+'_failed_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.txt')
                with failed.open('x',encoding='utf-8') as stream:stream.write(logs)
                raise RuntimeError('Full scoped failure log saved: '+str(failed))
            counts.append({'suite':suite,'passed':int(match[1]),'elapsed_seconds':float(match[2])})
        if inventory()!=hashes:raise RuntimeError('Runtime changed during audit/tests')
        data['scoped_tests']={'passed':sum(r['passed'] for r in counts),'failed':0,'skipped':0,
            'elapsed_seconds':round(sum(r['elapsed_seconds'] for r in counts),3),'suites':counts,'not_a_full_suite':True}
        OUTPUT.mkdir(parents=True)
        for name in NAMES:
            target=OUTPUT/'code'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
        for name,value in [('audit.json',data),('live_inventory.json',hashes)]:
            with (OUTPUT/name).open('x',encoding='utf-8') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        for name,text in [('REPORT.md',report(data)),('scoped_tests.txt',logs)]:
            with (OUTPUT/name).open('x',encoding='utf-8') as stream:stream.write(text)
        files=sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        with (OUTPUT/'SHA256SUMS.txt').open('x',encoding='utf-8') as stream:
            stream.write('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files)+'\n')
        data['verified_payloads']=verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'evidence_written':args.write_evidence,'tests':data.get('scoped_tests'),
        'startup_counterexamples':data['startup_counterexamples'],'production_integration_enabled':False,
        'model_requests':0,'verified_payloads':data.get('verified_payloads')},ensure_ascii=False))


if __name__=='__main__':main()
