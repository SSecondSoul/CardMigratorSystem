"""Freeze bounded object/array assignment compatibility; never promote or call LLMs."""
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

PRIOR=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_keys_probe_v2_20261112'
CONTRACT=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_key_contract_v1_20261112'
SCOPE=ROOT/'data/experiments/analysis/formal_30_v4_parent_watch_scope_guard_v1_20261111'
OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_keys_probe_v3_20261112'
NAMES=['migration_pipeline/probe_parent_dynamic_key_adapter_v3.cjs',
       'migration_pipeline/audit_parent_dynamic_key_object_values_runtime.cjs',
       'migration_pipeline/probe_formal_30_v4_parent_dynamic_keys_v3.py',
       'tests/test_parent_dynamic_key_object_values_v3.py']
NOTEBOOK=ROOT/'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
PREFIX_SHA='6ea5cd78d3dd9078269e1860f0e360db7f51e9ea3aae56c3aef8b62a90694d20'
METADATA_SHA='da8e8b42bb4344c317ccdf5038310d76529bda61666c53ff805bcc19dbede418'


def stable(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def inventory():
    old=json.loads((PRIOR/'live_inventory.json').read_text(encoding='utf-8'))
    changed=[name for name,sha in old.items() if digest(ROOT/name)!=sha]
    if changed:raise RuntimeError('Previous 397 files changed: '+str(changed))
    if any(digest(ROOT/name)!=sha for name,sha in MANUAL_SHA.items()):raise RuntimeError('Manual page changed')
    nb=json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    if stable(nb['cells'][:56])!=PREFIX_SHA or stable(nb['metadata'])!=METADATA_SHA:raise RuntimeError('Old Notebook cells/metadata changed')
    return {**old,**{name:digest(ROOT/name) for name in NAMES}}


def fixtures():
    sys.path.insert(0,str(ROOT/'tests'))
    spec=importlib.util.spec_from_file_location('object_values_v3_fixture',ROOT/NAMES[-1])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def probe():
    hashes=inventory()
    verified={name:verify_snapshot(folder.resolve()) for name,folder in [('v2_candidate',PRIOR),('original_contract',CONTRACT),('scope_guard',SCOPE)]}
    old=json.loads((PRIOR/'audit.json').read_text(encoding='utf-8'))
    for name,sha in old['source_inputs'].items():
        if digest(ROOT/name)!=sha:raise RuntimeError('Source/runtime drift: '+name)
    scope=json.loads((SCOPE/'replay.json').read_text(encoding='utf-8'))
    for row in scope['retained_artifact_replays']:
        for prefix in ['input','vue']:
            if digest(ROOT/row[prefix+'_path'])!=row[prefix+'_sha256']:raise RuntimeError('Retained input drift: '+row['id'])
    p=fixtures();base=p.original_payload();candidate=p.adapt(base['normal'],base['vue'])
    if not candidate['changes'] or candidate['production_eligible']:raise RuntimeError('Expected unpromoted v3 candidate')
    generic=p.adapt(base['generic']['normal'],base['generic']['vue'])
    payload={**base,'candidate':candidate['code'],'generic':{**base['generic'],'candidate':generic['code']}}
    contract=p.node(CONTRACT/'code/migration_pipeline/audit_parent_dynamic_key_reachability_runtime.cjs',payload)
    supported=[r for r in contract['pairs'] if r['variant']=='san_dynamic_candidate']
    if len(supported)!=30 or not all(r['stateEqual'] and r['eventsEqual'] and r['errorsEqual'] for r in supported):raise RuntimeError('Contract object-value/control mismatch')
    for variant in ['vue_source','san_normal_flow']:
        if [r for r in contract['runs'] if r['variant']==variant]!=[r for r in old['contract_runtime_observations']['runs'] if r['variant']==variant]:raise RuntimeError('Source/control observations changed')
    for scenario in ['restore_extra_nested_object','restore_declared_object_value']:
        if [r for r in contract['runs'] if r['scenario']==scenario]!=[r for r in old['contract_runtime_observations']['runs'] if r['scenario']==scenario]:raise RuntimeError('v2 restoration regression')
    boundary=p.node(p.BOUNDARY/'code/migration_pipeline/audit_formal_30_v4_parent_watch_boundaries_v1.cjs',
        {'code':candidate['code'],'vue':base['vue'],'vueRuntime':base['vueRuntime'],'sanRuntime':base['sanRuntime']})
    normal=[r for r in boundary['pairs'] if not r['scenario'].startswith('write_failure')]
    if len(normal)!=70 or not all(r['stateEqual'] and r['businessEffectsEqual'] for r in normal):raise RuntimeError('Boundary key-control regression')
    for scenario in ['write_failure_captured','write_failure_headless_default']:
        if [r for r in boundary['runs'] if r['scenario']==scenario]!=[r for r in old['boundary_runtime_observations']['runs'] if r['scenario']==scenario]:raise RuntimeError('Exception policy changed')
    normal_code,normal_vue=p.sequence_fixture()
    from test_parent_dynamic_key_json_root_v2 import adapt as adapt_v2
    v2=adapt_v2(normal_code,normal_vue);v3=p.adapt(normal_code,normal_vue)
    sequence_fixture={'normal':normal_code,'vue':normal_vue,'v2':v2['code'],'v3':v3['code']}
    sequence=p.node(p.OBJECT_RUNTIME,{**sequence_fixture,'vueRuntime':base['vueRuntime'],'sanRuntime':base['sanRuntime']})
    matched=[r for r in sequence['pairs'] if r['variant']=='v3']
    if len(matched)!=26 or not all(r['stateEqual'] and r['eventsEqual'] and r['errorsEqual'] and r['warningsEqual'] for r in matched):raise RuntimeError('Object/array identity sequence mismatch')
    guards=p.node(p.GUARDS,{'code':v3['code'],'sanRuntime':base['sanRuntime']})
    if len(guards['rows'])!=9 or not all(r['unchanged'] and r['error']=='Dynamic-key probe: unsupported key or value' for r in guards['rows']):raise RuntimeError('Unsupported value guard changed')
    if not guards['previousUnchanged'] or guards['previousError']!='Dynamic-key probe: unsupported previous reactive value':raise RuntimeError('Previous-ref state was overwritten')
    structure=p.node(p.STRUCTURE,{'before':old['candidate']['code'],'after':candidate['code']})
    if structure!={'helpers':1,'writers':1,'rest_of_script_unchanged':True}:raise RuntimeError('Changed more than value guards/preconditions')
    nested_normal,nested_vue=p.nested_pair();nested_candidate=p.adapt(nested_normal,nested_vue)
    extended=p.node(p.EXTENDED,{'code':nested_candidate['code'],'vue':nested_vue,'vueRuntime':base['vueRuntime'],'sanRuntime':base['sanRuntime']})
    if not extended['equal'] or len(extended['vue']['snapshots'])!=31:raise RuntimeError('Earlier nested/identity sequence regressed')
    ssm=json.loads((RAW/'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']['ssm']
    vue_path=ROOT/next(name for name in old['source_inputs'] if name.endswith('.vue'))
    validation=ValidateStage().run(ValidateStageInput(generated_code=candidate['code'],ssm=ssm,vue_file_path=str(vue_path))).to_state_update()
    if validation['validation_passed'] or not validation['san_compile_result']['passed']:raise RuntimeError('Expected compilable but still blocked candidate')
    diagnostics=source_parent_watch_semantics(candidate['code'],base['vue'])
    if {r['code'] for r in diagnostics['blocked_boundaries']}!=PARENT_WATCH_REVIEW_CODES:raise RuntimeError('Lost production boundary')
    before={'generated_code':base['normal'],'vue_source':base['vue'],
        'validation_errors':source_parent_watch_semantics(base['normal'],base['vue'])['findings']}
    gate=candidate_gate(before,{**before,'generated_code':candidate['code'],'validation_errors':[],'validation_passed':True})
    if not gate['should_stop'] or len(gate['waived_source_parent_watch_boundaries'])!=2:raise RuntimeError('Forged pass not rejected')
    if inventory()!=hashes:raise RuntimeError('Files changed during probe')
    return {'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'isolated_v3_bounded_plain_data_value_assignment_not_production_closure',
        'source_verified_payloads':verified,'source_inputs':old['source_inputs'],
        'previous_inventory_unchanged':397,'production_runtime_inventory_unchanged':387,'inventory_count':len(hashes),
        'manual_page_sha256':MANUAL_SHA,'retained_30_inputs_unchanged':True,'original_aggregate':old['original_aggregate'],
        'candidate':candidate,'generic_fixture':payload['generic'],'object_sequence_fixture':sequence_fixture,
        'nested_array_fixture':{'normal':nested_normal,'vue':nested_vue,'candidate':nested_candidate['code']},
        'contract_runtime_observations':contract,'boundary_runtime_observations':boundary,
        'object_assignment_observations':sequence,'nested_array_extended_observations':extended,
        'unsupported_guard_observations':guards,'exact_scope_structure_check':structure,
        'actual_validation':validation,'production_diagnostics':diagnostics,'forged_pass_gate':gate,
        'frozen_public_plain_object_case_fixed':True,'bounded_object_array_assignment_verified':True,
        'public_arbitrary_value_contract_closed':False,'deep_alias_reactivity_proven':False,'exception_policy_fixed':False,
        'production_integration_enabled':False,'source_api_or_storage_schema_restricted':False,
        'canonical_san_or_manual_pages_modified':False,'v1_v2_probe_or_failure_evidence_modified':False,
        'production_rules_or_prompt_modified':False,'model_requests':0,'original_score_modified':False,
        'full_suite_reexecuted':False,'manual_or_browser_rechecked':False,'prior_full_suite_reference':old['prior_full_suite_reference'],
        'prior_notebook_cells':56,'prior_notebook_cells_sha256':PREFIX_SHA,'prior_notebook_metadata_sha256':METADATA_SHA}


def report(data):
    tests=data['scoped_tests']
    return f'''# 隔离动态键候选 v3：普通对象/数组赋值兼容（2026-11-12）

**已修复冻结的公开普通对象写入反例，但没有闭合任意公开输入语义。** 本v3是formal_30_v4开发回归中的隔离探针版本，不是历史正式实验v3。候选不接入生产；原批次仍24/30、6失败、0执行异常、1,821,544 tokens。0模型请求，无新人工验收。

## 通用修复范围

在v2源码证明及根恢复方案上派生v3，不改v1/v2或旧失败证据。普通数据对象/稠密数组可作为赋值传入值，保留原对象和调用者传入值的引用，不JSON克隆、不过滤/补默认值。新增键不通知；已观察键按Object.is判定变化，保持源回调/通知尾部和原异步入队。原型键仍用旧保护，不把普通对象放开规则套到__proto__。

新增受约束值检查及“旧响应式值为Ref样状态时拒绝覆盖”前态保护，排除__v_isRef标记，避免把Vue Ref setter误当普通替换。拒绝行为只属于未部署探针，不是修改源API允许范围，也不是Ref兼容已实现。结构复核：除一个值检查函数、写入准入条件及一条前态保护外，v2脚本AST（实际赋值语句、通知、根记账、队列、子组件、销毁）不变。

## 原生对照

- 未修改冻结契约装置：5场景×3变体×6阶段=15运行、90快照、60对。其中源/v3的30/30对状态、全部存储/计时器事件和错误匹配，公开普通对象写入的6阶段不再报错。源及旧正常流程对照完整观察不变；v2两个嵌套恢复成功场景也原样保留。
- 新增独立原生赋值序列：Vue2.7.16、旧正常流程San、v2、v3共4变体，12次操作加挂载共每变体26阶段，104快照/78对。源/v3的26/26对状态、事件、错误、警告匹配。覆盖新增键对象/重复对象、已观察键对象/数组、同引用重复、同内容不同引用、借用已有子值、标量替换、computed类型更新及销毁前排队。借用身份检查不等于已经证明随后任意别名深层修改。
- 未修改冻结边界装置：正常键70/70对仍匹配；两种存储异常完整观察仍失败且与v2一致，不吞异常或过滤事件。
- 既有嵌套数组/旧根身份/两实例/NaN/正负零序列31/31对（62快照）仍匹配。
- 9类不支持输入明确拒绝、原写入状态不变；额外旧Ref样状态拒绝覆盖。未声称对访问器、Proxy、Ref、Symbol、循环图或反射可见的Vue内部观察元数据等价。

Vue使用空render，San直接attached；无真实浏览器DOM attach/真实存储/业务timer执行。原生框架、Promise队列、computed和赋值被实际执行，不是模拟Data实现。两个旧对照装置没有为适配候选而改动。

## 验证与阻断

定向测试{tests['passed']}/{tests['passed']}，0失败/0跳过，{tests['elapsed_seconds']}秒。候选San编译通过，生产验证仍失败；两项unproven边界、额外结构/状态诊断及伪造通过保护均未删除。没有重跑完整703项；703/703只引用旧完整日志，不能与本轮拼接成新的完整成绩。

397项上轮清单（含387项生产/既有运行文件）、30个保留输入及Vue源码、两个测试页面均未改。新增4个探针/装置/测试文件后清单401项；旧Notebook56单元/元数据保留。候选San只写入新的证据目录，不覆盖canonical产物，原生产Prompt、服务器、规则及调度器不改。

## 下一步

继续验证借用值/外部别名的嵌套修改与实际子组件传播，并解决应用异常路由契约。普通数据赋值匹配不等于Vue完整观察系统已移植；生产保护继续阻断，不通过修改原API/schema、删除诊断或反复模型试跑放行。当前不需用户付费复跑。
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-evidence',action='store_true');args=parser.parse_args()
    if args.write_evidence and OUTPUT.exists():raise FileExistsError('Never overwrite frozen v3 evidence')
    hashes=inventory();data=probe();logs='';counts=[]
    if args.write_evidence:
        for suite in ['test_parent_dynamic_key_object_values_v3.py','test_parent_dynamic_key_json_root_v2.py',
                      'test_parent_dynamic_key_contract_audit.py','test_parent_dynamic_key_adapter_probe.py','test_parent_watch_scope_guard.py']:
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
        for name,text in [('REPORT.md',report(data)),('scoped_tests.txt',logs),('TaskManager_dynamic_key_v3_offline.san',data['candidate']['code'])]:
            with (OUTPUT/name).open('x',encoding='utf-8') as stream:stream.write(text)
        files=sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        with (OUTPUT/'SHA256SUMS.txt').open('x',encoding='utf-8') as stream:
            stream.write('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files)+'\n')
        data['verified_payloads']=verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'evidence_written':args.write_evidence,'tests':data.get('scoped_tests'),
        'frozen_plain_object_case_fixed':True,'arbitrary_value_contract_closed':False,'production_integration_enabled':False,
        'model_requests':0,'verified_payloads':data.get('verified_payloads')},ensure_ascii=False))


if __name__=='__main__':main()
