"""Freeze isolated observer candidate evidence; never mutate production or call models."""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT,digest,verify_snapshot
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate,PARENT_WATCH_REVIEW_CODES
from migration_pipeline.stages.validate import ValidateStage,ValidateStageInput
from migration_pipeline.audit_formal_30_v4_parent_watch_boundaries_v1 import RAW,OUTPUT as BOUNDARY

PRIOR=ROOT/'data/experiments/analysis/formal_30_v4_parent_alias_child_audit_v1_20261112'
V3=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_keys_probe_v3_20261112'
CONTRACT=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_key_contract_v1_20261112'
SCOPE=ROOT/'data/experiments/analysis/formal_30_v4_parent_watch_scope_guard_v1_20261111'
OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_parent_alias_observer_v4_20261112'
FAILED=ROOT/'data/experiments/analysis/formal_30_v4_parent_alias_observer_v4_writer_rhs_failed_20261112'
NOTEBOOK=ROOT/'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
PREFIX_SHA='95774a56e2b55a416663344e996e120ee881ecbc2aac488b20ea100aa7d60e94'
METADATA_SHA='da8e8b42bb4344c317ccdf5038310d76529bda61666c53ff805bcc19dbede418'
NAMES=['migration_pipeline/probe_parent_alias_observer_v4.cjs',
       'migration_pipeline/probe_parent_dynamic_key_adapter_v4.cjs',
       'migration_pipeline/audit_parent_alias_observer_v4_runtime.cjs',
       'migration_pipeline/probe_formal_30_v4_parent_alias_observer_v4.py',
       'tests/test_parent_alias_observer_v4.py']


def stable(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def inventory():
    old=json.loads((PRIOR/'live_inventory.json').read_text(encoding='utf-8'))
    drift=[name for name,sha in old.items() if digest(ROOT/name)!=sha]
    if drift:raise RuntimeError('Prior 404 files changed: '+str(drift))
    data=json.loads((PRIOR/'audit.json').read_text(encoding='utf-8'))
    if any(digest(ROOT/n)!=s for n,s in data['manual_page_sha256'].items()):raise RuntimeError('Manual page drift')
    nb=json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    if stable(nb['cells'][:60])!=PREFIX_SHA or stable(nb['metadata'])!=METADATA_SHA:raise RuntimeError('Old Notebook changed')
    return {**old,**{p:digest(ROOT/p) for p in NAMES}}


def fixtures():
    sys.path.insert(0,str(ROOT/'tests'))
    spec=importlib.util.spec_from_file_location('alias_v4_fixture',ROOT/NAMES[-1]);p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    return p


def gather():
    hashes=inventory();p=fixtures();old,common,generic=p.payloads();f=old['fixture']
    verified={k:verify_snapshot(v.resolve()) for k,v in [('negative_alias_audit',PRIOR),('v3_candidate',V3),('original_contract',CONTRACT),('scope_guard',SCOPE)]}
    for n,s in old['source_inputs'].items():
        if digest(ROOT/n)!=s:raise RuntimeError('Source/runtime drift: '+n)
    retained=json.loads((SCOPE/'replay.json').read_text(encoding='utf-8'))['retained_artifact_replays']
    if len(retained)!=30:raise RuntimeError('Expected 30 retained inputs')
    for row in retained:
        for key in ['input','vue']:
            if digest(ROOT/row[key+'_path'])!=row[key+'_sha256']:raise RuntimeError('Retained input drift: '+row['id'])
    mounted=p.node(PRIOR/'code/migration_pipeline/audit_parent_alias_child_runtime.cjs',{**f,'v3':generic['code'],**common})
    candidate_pairs=[r for r in mounted['pairs'] if r['variant']=='v3']
    if len(candidate_pairs)!=36 or not all(all(r[k] for k in ['parentStateEqual','childComputedEqual','domTextEqual','effectsEqual','errorsEqual']) for r in candidate_pairs):
        raise RuntimeError('Frozen alias/child counterexample not fixed')
    for variant in ['vue_source','normal']:
        if [r for r in mounted['runs'] if r['variant']==variant]!=[r for r in old['runtime_observations']['runs'] if r['variant']==variant]:raise RuntimeError('Frozen source/clone control changed')
    extended=p.node(p.RUNTIME,{'vue':f['vue'],'v4':generic['code'],**common})
    if len(extended['pairs'])!=56 or not all(all(r[k] for k in ['stateEqual','eventsEqual','errorsEqual','warningsEqual']) for r in extended['pairs']):raise RuntimeError('Extended alias/array/identity mismatch')
    if not all(r['frameworkPrototypeUnchanged'] and r['instanceWrappersRemoved'] for r in extended['runs']):raise RuntimeError('Prototype/lifetime isolation failed')
    base=p.original_payload();actual=p.adapt(base['normal'],base['vue']);contract_generic=p.adapt(base['generic']['normal'],base['generic']['vue'])
    contract=p.node(CONTRACT/'code/migration_pipeline/audit_parent_dynamic_key_reachability_runtime.cjs',
        {**base,'candidate':actual['code'],'generic':{**base['generic'],'candidate':contract_generic['code']}})
    pairs=[r for r in contract['pairs'] if r['variant']=='san_dynamic_candidate']
    if len(pairs)!=30 or not all(r['stateEqual'] and r['eventsEqual'] and r['errorsEqual'] for r in pairs):raise RuntimeError('Old 30-pair contract regression')
    normal,vue=p.sequence_fixture();value_candidate=p.adapt(normal,vue)
    previous=json.loads((V3/'audit.json').read_text(encoding='utf-8'));sequence_fixture=previous['object_sequence_fixture']
    sequence=p.node(ROOT/'migration_pipeline/audit_parent_dynamic_key_object_values_runtime.cjs',
        {**sequence_fixture,'v3':value_candidate['code'],**common})
    if not all(r['stateEqual'] and r['eventsEqual'] and r['errorsEqual'] and r['warningsEqual'] for r in sequence['pairs'] if r['variant']=='v3'):
        raise RuntimeError('Old object assignment identity sequence regression')
    identity=p.node(p.EXTENDED,{'code':contract_generic['code'],'vue':base['generic']['vue'],**common})
    if not identity['equal']:raise RuntimeError('Old root/numeric/instance controls regressed')
    boundary=p.node(BOUNDARY/'code/migration_pipeline/audit_formal_30_v4_parent_watch_boundaries_v1.cjs',
        {'code':actual['code'],'vue':base['vue'],**common})
    mismatches=[r for r in boundary['pairs'] if not r['scenario'].startswith('write_failure') and not(r['stateEqual'] and r['businessEffectsEqual'])]
    exceptions=[name for name in boundary['scenarios'] if name.startswith('write_failure')]
    if len(exceptions)!=2:raise RuntimeError('Expected two exception policies')
    for name in exceptions:
        if [r for r in boundary['runs'] if r['scenario']==name]!=[r for r in previous['boundary_runtime_observations']['runs'] if r['scenario']==name]:raise RuntimeError('Exception policy was changed')
    ssm=json.loads((RAW/'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']['ssm']
    vue_path=ROOT/next(n for n in old['source_inputs'] if n.endswith('.vue'))
    validation=ValidateStage().run(ValidateStageInput(generated_code=actual['code'],ssm=ssm,vue_file_path=str(vue_path))).to_state_update()
    if validation['validation_passed'] or not validation['san_compile_result']['passed']:raise RuntimeError('Expected compilable but still blocked candidate')
    diag=source_parent_watch_semantics(actual['code'],base['vue'])
    if {r['code'] for r in diag['blocked_boundaries']}!=PARENT_WATCH_REVIEW_CODES:raise RuntimeError('Production boundaries lost')
    before={'generated_code':base['normal'],'vue_source':base['vue'],'validation_errors':source_parent_watch_semantics(base['normal'],base['vue'])['findings']}
    gate=candidate_gate(before,{**before,'generated_code':actual['code'],'validation_errors':[],'validation_passed':True})
    if not gate['should_stop'] or len(gate['waived_source_parent_watch_boundaries'])!=2:raise RuntimeError('Forged pass not refused')
    if inventory()!=hashes:raise RuntimeError('Files changed during probe')
    return {'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'isolated_v4_bounded_existing_property_array_observer_not_production_closure',
        'source_verified_payloads':verified,'source_inputs':old['source_inputs'],
        'previous_inventory_unchanged':404,'production_runtime_inventory_unchanged':387,'inventory_count':len(hashes),
        'manual_page_sha256':old['manual_page_sha256'],'retained_30_inputs_unchanged':True,'original_aggregate':old['original_aggregate'],
        'generic_candidate':generic,'candidate':actual,'mounted_fixture':f,
        'mounted_slot_alias':{'frozen_slot_name':'v3','actual_candidate_version':'v4','frozen_harness_modified':False},
        'mounted_observations':mounted,'extended_alias_array_observations':extended,
        'contract_fixture':{**base['generic'],'candidate':contract_generic['code']},'contract_observations':contract,
        'object_sequence_fixture':{**sequence_fixture,'v3':value_candidate['code']},'object_sequence_observations':sequence,
        'legacy_identity_observations':identity,'boundary_observations':boundary,'normal_boundary_mismatches':mismatches,
        'actual_validation':validation,'production_diagnostics':diag,'forged_pass_gate':gate,
        'frozen_alias_child_counterexamples_fixed_within_fixture':True,'arbitrary_observer_contract_closed':False,
        'reflection_equivalence_proven':False,'exception_policy_fixed':False,'production_integration_enabled':False,
        'canonical_san_or_manual_pages_modified':False,'prior_probe_or_failure_evidence_modified':False,
        'production_rules_or_prompt_modified':False,'source_api_or_storage_schema_restricted':False,
        'model_requests':0,'original_score_modified':False,'full_suite_reexecuted':False,'manual_or_browser_rechecked':False,
        'evidence_boundary':{'mounted_uses_limited_miniDOM_not_browser':True,'mounted_child_is_synthetic':True,
            'actual_TaskManager_child_DOM_tested':False,'extended_identity_suite_headless':True,
            'receiver_invalidation_is_candidate_code':True,'native_binding_still_owns_prop_replacement':True,
            'no_framework_prototype_patch':True,'runtime_versions':{'vue':'2.7.16','san':'3.15.6'}},
        'development_attempt_summary':{'initial_draft_source_not_frozen':True,
            'first_draft_observation':'36-pair frozen audit had six synchronous child-computed mismatches while eventual texts matched.',
            'correction':'Synchronously invalidate existing shared child values and route exact existing static deep writes through observed setters; native prop replacement remains scheduled.'},
        'prior_full_suite_reference':old['prior_full_suite_reference'],
        'prior_notebook_cells':60,'prior_notebook_cells_sha256':PREFIX_SHA,'prior_notebook_metadata_sha256':METADATA_SHA}


def report(data,failed):
    tests=data.get('scoped_tests')
    return f'''# 隔离别名观察／子组件通知候选 v4（2026-11-12）

状态：{'失败预检冻结，禁止放行' if failed else '受约束装置验证通过，仍禁止生产放行'}。这是formal_30_v4开发探针，不是历史正式实验v4的一轮全新30样本通过成绩。原批24/30、6失败、0执行异常、1,821,544 tokens不变；0模型调用，无新增人工验收。

## 改了哪里

只新增隔离AST适配器和运行时观察桥，不改生产repair/generate/validate、Prompt、旧探针或人工页面。已有普通属性用getter/setter观察；稠密数组包装7类变异方法，保留对象/数组/传入值身份。新键和新键原始对象保持Vue2非响应行为；复用旧根不补成响应键。根依赖按当前可达性计算，脱离别名不通知当前根；两实例共享时各自入队，销毁移除自己的订阅/实例包装。

对子组件已绑定共享值同步失效，保留原生prop绑定处理根替换；通过每个实例的Data.set包装及版本控制补通知，没有全局框架原型patch或调用私有renderer。接收器遍历依赖固定San3.15.6的子树结构，属于实验适配边界。普通静态已有深路径setter采用观察属性赋值；其他force/silent/动态Data API不声称等价。

## 验证证据

未修改旧冻结装置，输入槽名仍叫v3，但本次装入的是v4（见mounted_slot_alias）。9场景×3变体×4阶段=27运行108快照72比较，其中源/v4的36/36比较中父状态、子computed、实际文本、事件、错误一致；源与旧clone对照全部原始观察和负向冻结记录一致。同步读取也检查，不只等下一轮DOM更新。

额外27操作，含挂载共56阶段：Vue/v4两运行112快照、56/56对照状态/身份/回调/错误/警告匹配。覆盖7类数组变异、插入对象别名、同值/新键、旧根恢复、脱离别名、两实例共享及逐个销毁。此组仅headless，不声称子组件DOM验证。

旧契约30/30源/候选阶段、对象赋值26/26阶段、旧根/数值/两实例31/31阶段匹配。正常边界未匹配阶段数：{len(data['normal_boundary_mismatches'])}（完整原始观察均保留，不能删失败项）；两种存储异常完整观察与v3不变，仍未修复。候选San可编译，生产验证仍失败；动态键/异常边界及伪造通过保护均保留。

定向测试：{json.dumps(tests,ensure_ascii=False)}。本轮不是完整703项重跑。生产守卫拒绝仍须维持，不能把受约束观察桥的拒绝行为解释为源API的合法新限制。

## 失败与证据限制

初稿只修复异步文本却漏掉6个同步子computed差异，仅保留开发摘要（初稿代码未完整封存），随后补同步失效。另一次正常边界预检发现writer包装误用了原始参数，丢失源赋值右侧的数字转换，字符串30未转为数字30；失败候选及全观察独立封存后再修正，不改旧证据。

受限miniDOM只验证原生创建/绑定/文本patch，不是真实浏览器、CSS布局或canonical TaskManager SettingsPanel验收。getter/setter描述符、数组自有非枚举包装方法等反射结果与Vue不等价；Proxy/Ref/访问器/Symbol/循环图及任意输入、异常路由、复杂动态生命周期仍未闭合。不能据此宣称整个Vue观察器已迁移。

404项旧清单（含387生产/既有运行文件）、30个保留输入/Vue、两个页面、旧Notebook60单元/元数据均保留。新增5文件后409项。本轮不做模型复跑、不更新原批成绩、不部署。下一步先处理剩余异常策略及观察器适用范围，再决定生产集成与端到端回归。
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group()
    group.add_argument('--write-evidence',action='store_true');group.add_argument('--freeze-preflight',action='store_true');args=parser.parse_args()
    output=FAILED if args.freeze_preflight else OUTPUT
    write=args.write_evidence or args.freeze_preflight
    if write and output.exists():raise FileExistsError('Never overwrite frozen evidence: '+str(output))
    hashes=inventory();data=gather();logs=''
    if args.freeze_preflight:
        if len(data['normal_boundary_mismatches'])!=6:raise RuntimeError('Expected writer-RHS negative preflight')
    elif data['normal_boundary_mismatches']:raise RuntimeError('Normal boundary regression; freeze failure before correction')
    if args.write_evidence:
        if verify_snapshot(FAILED.resolve())!=9:raise RuntimeError('Missing frozen failed preflight')
        data['writer_rhs_failure_evidence']=FAILED.relative_to(ROOT).as_posix();counts=[]
        for suite in ['test_parent_alias_observer_v4.py','test_parent_alias_child_audit.py','test_parent_dynamic_key_object_values_v3.py','test_parent_watch_scope_guard.py']:
            print('Running scoped suite: '+suite,flush=True)
            proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',suite,'-v'],cwd=ROOT,
                env={**os.environ,'PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8')
            part=proc.stdout+proc.stderr;logs+='\n### '+suite+'\n'+part;match=re.search(r'Ran (\d+) tests in ([\d.]+)s',part)
            if proc.returncode or not match or '\nOK' not in part or re.search(r'OK\s*\(skipped=',part):
                path=output.parent/(output.name+'_failed_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.txt')
                with path.open('x',encoding='utf-8') as stream:stream.write(logs)
                raise RuntimeError('Scoped failure log saved: '+str(path))
            counts.append({'suite':suite,'passed':int(match[1]),'elapsed_seconds':float(match[2])})
        data['scoped_tests']={'passed':sum(r['passed'] for r in counts),'failed':0,'skipped':0,
            'elapsed_seconds':round(sum(r['elapsed_seconds'] for r in counts),3),'suites':counts,'not_a_full_suite':True}
    if write:
        if inventory()!=hashes:raise RuntimeError('Files changed during verification')
        data['failed_preflight']=args.freeze_preflight;output.mkdir(parents=True,exist_ok=False)
        for name in NAMES:
            target=output/'code'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
        for name,value in [('audit.json',data),('live_inventory.json',hashes)]:
            with (output/name).open('x',encoding='utf-8') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        for name,value in [('REPORT.md',report(data,args.freeze_preflight)),('TaskManager_alias_v4_offline.san',data['candidate']['code'])]+([('scoped_tests.txt',logs)] if logs else []):
            with (output/name).open('x',encoding='utf-8') as stream:stream.write(value)
        files=sorted(p for p in output.rglob('*') if p.is_file())
        with (output/'SHA256SUMS.txt').open('x',encoding='utf-8') as stream:
            stream.write('\n'.join(f'{digest(p)}  {p.relative_to(output).as_posix()}' for p in files)+'\n')
        data['verified_payloads']=verify_snapshot(output.resolve())
    print(json.dumps({'written':write,'failed_preflight':args.freeze_preflight,'tests':data.get('scoped_tests'),
        'normal_boundary_mismatches':len(data['normal_boundary_mismatches']),'verified_payloads':data.get('verified_payloads'),
        'production_integration_enabled':False,'model_requests':0},ensure_ascii=False))


if __name__=='__main__':main()
