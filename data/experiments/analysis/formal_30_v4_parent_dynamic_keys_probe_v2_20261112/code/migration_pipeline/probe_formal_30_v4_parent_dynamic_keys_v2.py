"""Freeze the isolated nested-JSON-root compatibility fix; no model or promotion."""
import argparse
from datetime import datetime,timedelta,timezone
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
from migration_pipeline.audit_formal_30_v4_parent_watch_boundaries_v1 import RAW
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate,PARENT_WATCH_REVIEW_CODES
from migration_pipeline.stages.validate import ValidateStage,ValidateStageInput

CONTRACT=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_key_contract_v1_20261112'
PRIOR=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_keys_probe_v1_20261112'
SCOPE=ROOT/'data/experiments/analysis/formal_30_v4_parent_watch_scope_guard_v1_20261111'
OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_keys_probe_v2_20261112'
NAMES=['migration_pipeline/probe_parent_dynamic_key_adapter_v2.cjs',
       'migration_pipeline/probe_formal_30_v4_parent_dynamic_keys_v2.py','tests/test_parent_dynamic_key_json_root_v2.py']
NOTEBOOK=ROOT/'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
PREFIX_SHA='8e9dde43693e0c6cccab683fe57a6c9672391e2cb6711ef94552685b98ba32c5'
METADATA_SHA='da8e8b42bb4344c317ccdf5038310d76529bda61666c53ff805bcc19dbede418'


def stable(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def inventory():
    old=json.loads((CONTRACT/'live_inventory.json').read_text(encoding='utf-8'))
    changed=[name for name,sha in old.items() if digest(ROOT/name)!=sha]
    if changed:raise RuntimeError('Previous 394 files changed before verification: '+str(changed))
    if any(digest(ROOT/name)!=sha for name,sha in MANUAL_SHA.items()):raise RuntimeError('Manual page changed')
    nb=json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    if stable(nb['cells'][:54])!=PREFIX_SHA or stable(nb['metadata'])!=METADATA_SHA:raise RuntimeError('Old Notebook cells/metadata changed')
    return {**old,**{name:digest(ROOT/name) for name in NAMES}}


def fixtures():
    sys.path.insert(0,str(ROOT/'tests'))
    spec=importlib.util.spec_from_file_location('json_root_v2_fixture',ROOT/NAMES[-1])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def probe():
    hashes=inventory()
    verified={name:verify_snapshot(folder.resolve()) for name,folder in [('contract_counterexamples',CONTRACT),('v1_candidate',PRIOR),('scope_guard',SCOPE)]}
    old=json.loads((CONTRACT/'audit.json').read_text(encoding='utf-8'))
    for name,sha in old['source_inputs'].items():
        if digest(ROOT/name)!=sha:raise RuntimeError('Pinned source/runtime drift: '+name)
    scope=json.loads((SCOPE/'replay.json').read_text(encoding='utf-8'))
    for row in scope['retained_artifact_replays']:
        for prefix in ['input','vue']:
            if digest(ROOT/row[prefix+'_path'])!=row[prefix+'_sha256']:raise RuntimeError('Retained input drift: '+row['id'])
    p=fixtures();base=p.v1_payload();candidate=p.adapt(base['normal'],base['vue'])
    if not candidate['changes'] or candidate['production_eligible']:raise RuntimeError('Expected an isolated v2 candidate')
    generic=p.adapt(base['generic']['normal'],base['generic']['vue'])
    payload={**base,'candidate':candidate['code'],'generic':{**base['generic'],'candidate':generic['code']}}
    actual=p.node(CONTRACT/'code/migration_pipeline/audit_parent_dynamic_key_reachability_runtime.cjs',payload)
    restored=[]
    for scenario in ['restore_extra_nested_object','restore_declared_object_value']:
        pairs=[r for r in actual['pairs'] if r['scenario']==scenario and r['variant']=='san_dynamic_candidate']
        runs=[r for r in actual['runs'] if r['scenario']==scenario and r['variant']=='san_dynamic_candidate']
        if len(pairs)!=6 or not all(r['stateEqual'] and r['eventsEqual'] and r['errorsEqual'] for r in pairs):raise RuntimeError('Frozen restoration regression persists')
        if not all(q['state']['taskIds']==[901] and not q['warnings'] and not q['errors'] for r in runs for q in r['phases']):raise RuntimeError('Task loss/warning during restore')
        restored.append({'scenario':scenario,'matched_phase_pairs':6,'task_ids_all_phases':[901],
            'previous_candidate_task_ids':[1,2,3],'status':'fixed_in_isolated_v2_not_production'})
    for variant in ['vue_source','san_normal_flow']:
        if [r for r in actual['runs'] if r['variant']==variant]!=[r for r in old['runtime_observations']['runs'] if r['variant']==variant]:raise RuntimeError('Source/control observations drifted')
    if [r for r in actual['runs'] if r['scenario']=='public_new_object_value']!=[r for r in old['runtime_observations']['runs'] if r['scenario']=='public_new_object_value']:
        raise RuntimeError('Public object-write limitation was silently changed')
    key_payload={'code':candidate['code'],'vue':base['vue'],'vueRuntime':base['vueRuntime'],'sanRuntime':base['sanRuntime']}
    boundary=p.node(p.BOUNDARY/'code/migration_pipeline/audit_formal_30_v4_parent_watch_boundaries_v1.cjs',key_payload)
    previous_boundary=json.loads((p.BOUNDARY/'audit.json').read_text(encoding='utf-8'))['observations']
    normal=[r for r in boundary['pairs'] if not r['scenario'].startswith('write_failure')]
    if len(normal)!=70 or not all(r['stateEqual'] and r['businessEffectsEqual'] for r in normal):raise RuntimeError('Existing key-control regression')
    for scenario in ['write_failure_captured','write_failure_headless_default']:
        if [r for r in boundary['runs'] if r['scenario']==scenario]!=[r for r in previous_boundary['runs'] if r['scenario']==scenario]:raise RuntimeError('Exception policy changed')
    normal_code,normal_vue=p.nested_pair();normal_candidate=p.adapt(normal_code,normal_vue)
    extended=p.node(p.EXTENDED,{**key_payload,'code':normal_candidate['code'],'vue':normal_vue})
    if not extended['equal'] or len(extended['vue']['snapshots'])!=31:raise RuntimeError('Nested-array/identity oracle mismatch')
    descriptors=p.node(p.DESCRIPTORS,{'code':candidate['code']})
    if len(descriptors['rows'])!=13 or not all(r['actual']==r['expected'] for r in descriptors['rows']) or descriptors['getterCalls']:
        raise RuntimeError('Descriptor-validator failure or getter executed')
    structure=p.node(p.STRUCTURE,{'before':base['candidate'],'after':candidate['code']})
    if structure!={'added':1,'replaced':1,'rest_of_script_unchanged':True}:raise RuntimeError('Changed more than observation root guard')
    ssm=json.loads((RAW/'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']['ssm']
    vue_path=ROOT/next(name for name in old['source_inputs'] if name.endswith('.vue'))
    validation=ValidateStage().run(ValidateStageInput(generated_code=candidate['code'],ssm=ssm,vue_file_path=str(vue_path))).to_state_update()
    if validation['validation_passed'] or not validation['san_compile_result']['passed']:raise RuntimeError('Expected compilable but still unaccepted candidate')
    diagnostics=source_parent_watch_semantics(candidate['code'],base['vue'])
    if {r['code'] for r in diagnostics['blocked_boundaries']}!=PARENT_WATCH_REVIEW_CODES:raise RuntimeError('Lost production boundary')
    before={'generated_code':base['normal'],'vue_source':base['vue'],
        'validation_errors':source_parent_watch_semantics(base['normal'],base['vue'])['findings']}
    gate=candidate_gate(before,{**before,'generated_code':candidate['code'],'validation_errors':[],'validation_passed':True})
    if not gate['should_stop'] or len(gate['waived_source_parent_watch_boundaries'])!=2:raise RuntimeError('Forged pass not rejected')
    if inventory()!=hashes:raise RuntimeError('Files changed during probe')
    return {'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'isolated_v2_nested_root_compatibility_fix_reused_development_not_production_closure',
        'source_verified_payloads':verified,'source_inputs':old['source_inputs'],
        'previous_inventory_unchanged':394,'production_runtime_inventory_unchanged':387,'inventory_count':len(hashes),
        'manual_page_sha256':MANUAL_SHA,'retained_30_inputs_unchanged':True,
        'original_aggregate':old['original_aggregate'],'original_score_modified':False,'model_requests':0,
        'candidate':candidate,'generic_fixture':payload['generic'],'nested_array_fixture':{'normal':normal_code,'vue':normal_vue,'candidate':normal_candidate['code']},
        'contract_runtime_observations':actual,'boundary_runtime_observations':boundary,'nested_array_extended_observations':extended,
        'descriptor_guard_observations':descriptors,'exact_scope_structure_check':structure,'restored_counterexamples':restored,
        'actual_validation':validation,'production_diagnostics':diagnostics,'forged_pass_gate':gate,
        'production_integration_enabled':False,'public_object_write_gap_fixed':False,'exception_policy_fixed':False,
        'source_api_or_storage_schema_restricted':False,'canonical_san_or_manual_pages_modified':False,
        'v1_probe_or_failure_evidence_modified':False,'production_rules_or_prompt_modified':False,
        'full_suite_reexecuted':False,'manual_or_browser_rechecked':False,'prior_full_suite_reference':old['prior_full_suite_reference'],
        'prior_notebook_cells':54,'prior_notebook_cells_sha256':PREFIX_SHA,'prior_notebook_metadata_sha256':METADATA_SHA}


def report(data):
    tests=data['scoped_tests']
    return f'''# 隔离动态键候选 v2：历史嵌套设置恢复修复（2026-11-12）

已在**隔离v2候选**修复上一轮两个冻结恢复反例：源与v2的已保存任务ID均保持[901]，不再被初始化catch换成[1,2,3]。两个场景各6个阶段的状态、全部存储/计时器事件、错误一致，无新增警告。不是生产规则已完成，也不是新批次/独立测试/人工验收；原批次24/30、6失败、0执行异常、1,821,544 tokens不变。

## 修改范围

新建通用v2 AST派生器，保留v1和失败证据。只给已观察根对象的记账增加递归描述符检查，接受受约束的嵌套普通数据对象/稠密数组，仍按原对象身份记录键；不克隆、过滤、补默认值或修改嵌套数据。没有新增源API白名单或存储schema。结构核对证明：除一个根检查函数和一次调用替换外，v1脚本（包括原写入器、原型键保护、异步队列、子组件及销毁）AST不变。

## 对照与回归证据

- 使用未修改的冻结契约装置：5场景×3变体×6阶段=15运行、90快照、60对源/目标比较。源/旧正常流程的完整观察与上一轮完全一致；v2支持的4个场景共24/24个候选对照匹配。公开对象值写入仍拒绝，完整旧失败观察未改，不能把它计为兼容已闭环。
- 使用未修改的冻结边界装置：9场景×2框架×10阶段=18运行、180快照、90对。7类正常键场景70/70对匹配，两类存储异常观察仍与旧失败基线一致。
- 通用嵌套数组夹具，真实Vue/San执行根替换、恢复旧身份、同值、NaN/正负零、两实例隔离和销毁取消：31/31对、62快照一致。
- 13个纯描述符检查用例覆盖嵌套数组、共享DAG、undefined叶值，以及访问器、循环、Symbol、稀疏/附加属性数组、特殊原型和观察器元数据拒绝；getter调用0次。这是检查器用例，不冒充浏览器或框架交互用例，也不证明Proxy行为。
- San编译通过，生产验证仍失败，生产边界和伪造通过拒绝保护仍有效。实际验证错误完整保存在audit.json，没有删除或降级诊断来放行。

## 尚未闭合

根恢复兼容不等于任意JSON/公开对象值/Ref/访问器/Proxy/循环图、外部别名/嵌套更新或实际子组件DOM传播均兼容。JSON形支持范围仍排除观察器元数据等特殊形状；写入器仍是v1的标量值保护。存储异常策略仍需明确应用运行契约。探针的拒绝TypeError不是源公开接口对任意输入的等价实现。因此不接入生产、不调用模型，也不要求人工重测页面。

## 冻结与检查

本轮定向测试{tests['passed']}/{tests['passed']}，0失败/0跳过，{tests['elapsed_seconds']}秒；没有重跑完整703项，703/703仅引用既有冻结日志。394项既有清单（其中387项生产/既有运行文件）、30个保留输入及Vue源码、两个测试页面原字节不变；仅新增3个v2探针/测试文件，清单397项。旧Notebook54单元/元数据保留。上轮失败候选与两个恢复反例原样保存，本轮另冻v2，不能覆盖旧记录。

下一步优先在隔离候选中处理公开方法对象值的源语义，再验证别名/嵌套更新与子组件传播；继续保留生产阻断，不通过缩窄原接口或吞异常制造通过。当前不付费复跑。
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-evidence',action='store_true');args=parser.parse_args()
    if args.write_evidence and OUTPUT.exists():raise FileExistsError('Never overwrite frozen v2 evidence')
    hashes=inventory();data=probe();logs='';counts=[]
    if args.write_evidence:
        for suite in ['test_parent_dynamic_key_json_root_v2.py','test_parent_dynamic_key_contract_audit.py',
                      'test_parent_dynamic_key_adapter_probe.py','test_parent_watch_scope_guard.py']:
            print('Running scoped suite: '+suite,flush=True)
            proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',suite,'-v'],cwd=ROOT,
                env={**os.environ,'PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8')
            part=proc.stdout+proc.stderr;logs+='\n### '+suite+'\n'+part
            match=re.search(r'Ran (\d+) tests in ([\d.]+)s',part)
            if proc.returncode or not match or '\nOK' not in part or re.search(r'OK\s*\(skipped=',part):
                failed=OUTPUT.parent/(OUTPUT.name+'_failed_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.txt')
                with failed.open('x',encoding='utf-8') as stream:stream.write(logs)
                raise RuntimeError('Complete scoped failure log saved: '+str(failed))
            counts.append({'suite':suite,'passed':int(match[1]),'elapsed_seconds':float(match[2])})
        if inventory()!=hashes:raise RuntimeError('Runtime changed during verification')
        data['scoped_tests']={'passed':sum(r['passed'] for r in counts),'failed':0,'skipped':0,
            'elapsed_seconds':round(sum(r['elapsed_seconds'] for r in counts),3),'suites':counts,'not_a_full_suite':True}
        OUTPUT.mkdir(parents=True)
        for name in NAMES:
            target=OUTPUT/'code'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
        for name,value in [('audit.json',data),('live_inventory.json',hashes)]:
            with (OUTPUT/name).open('x',encoding='utf-8') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        for name,text in [('REPORT.md',report(data)),('scoped_tests.txt',logs),('TaskManager_dynamic_key_v2_offline.san',data['candidate']['code'])]:
            with (OUTPUT/name).open('x',encoding='utf-8') as stream:stream.write(text)
        files=sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        with (OUTPUT/'SHA256SUMS.txt').open('x',encoding='utf-8') as stream:
            stream.write('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files)+'\n')
        data['verified_payloads']=verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'evidence_written':args.write_evidence,'tests':data.get('scoped_tests'),
        'restored_counterexamples':data['restored_counterexamples'],'production_integration_enabled':False,
        'model_requests':0,'verified_payloads':data.get('verified_payloads')},ensure_ascii=False))


if __name__=='__main__':main()
