"""Freeze native child/borrowed-alias counterexamples, without promoting or repairing v3."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot
from migration_pipeline.probe_formal_30_v4_parent_dynamic_keys_v1 import MANUAL_SHA
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import PARENT_WATCH_REVIEW_CODES

PRIOR=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_keys_probe_v3_20261112'
CONTRACT=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_key_contract_v1_20261112'
SCOPE=ROOT/'data/experiments/analysis/formal_30_v4_parent_watch_scope_guard_v1_20261111'
OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_parent_alias_child_audit_v1_20261112'
NOTEBOOK=ROOT/'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
NAMES=['migration_pipeline/audit_parent_alias_child_runtime.cjs',
       'migration_pipeline/audit_formal_30_v4_parent_alias_child_v1.py',
       'tests/test_parent_alias_child_audit.py']
PREFIX_SHA='25bd11f4a12c9efdd1a25cb5b99f9246914bab98ebb32cec4485c5666c462481'
METADATA_SHA='da8e8b42bb4344c317ccdf5038310d76529bda61666c53ff805bcc19dbede418'


def stable(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def inventory():
    old=json.loads((PRIOR/'live_inventory.json').read_text(encoding='utf-8'))
    changed=[p for p,sha in old.items() if digest(ROOT/p)!=sha]
    if changed:raise RuntimeError('Previous 401-file inventory changed: '+str(changed))
    if any(digest(ROOT/p)!=sha for p,sha in MANUAL_SHA.items()):raise RuntimeError('Manual page drift')
    nb=json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    if stable(nb['cells'][:58])!=PREFIX_SHA or stable(nb['metadata'])!=METADATA_SHA:
        raise RuntimeError('Historical Notebook cells/metadata changed')
    return {**old,**{p:digest(ROOT/p) for p in NAMES}}


def fixture_module():
    sys.path.insert(0,str(ROOT/'tests'))
    spec=importlib.util.spec_from_file_location('alias_child_fixture',ROOT/NAMES[-1])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def frame(observed,scenario,variant,phase='action_tick'):
    return next(f for r in observed['runs'] if r['scenario']==scenario and r['variant']==variant
                for f in r['frames'] if f['name']==phase)


def inspect():
    hashes=inventory()
    verified={k:verify_snapshot(p.resolve()) for k,p in [('v3_candidate',PRIOR),('original_contract',CONTRACT),('scope_guard',SCOPE)]}
    if verified!={'v3_candidate':9,'original_contract':8,'scope_guard':25}:raise RuntimeError('Evidence scope drift')
    old=json.loads((PRIOR/'audit.json').read_text(encoding='utf-8'))
    for p,sha in old['source_inputs'].items():
        if digest(ROOT/p)!=sha:raise RuntimeError('Source/runtime drift: '+p)
    scope=json.loads((SCOPE/'replay.json').read_text(encoding='utf-8'))
    retained=scope['retained_artifact_replays']
    if len(retained)!=30:raise RuntimeError('Expected 30 retained inputs')
    for row in retained:
        for key in ['input','vue']:
            if digest(ROOT/row[key+'_path'])!=row[key+'_sha256']:raise RuntimeError('Retained input drift: '+row['id'])
    p=fixture_module();fixture=p.fixture()
    payload={**fixture,'vueRuntime':p.VUE_RUNTIME.read_bytes().decode('utf-8'),
             'sanRuntime':p.SAN_RUNTIME.read_bytes().decode('utf-8')}
    observed=p.node(p.RUNTIME,payload)
    if observed!=p.node(p.RUNTIME,payload):raise RuntimeError('Nondeterministic native audit')
    if len(observed['runs'])!=27 or sum(len(r['frames']) for r in observed['runs'])!=108 or len(observed['pairs'])!=72:
        raise RuntimeError('Unexpected audit dimensions')
    if not observed['rejectionListenerRestored']:raise RuntimeError('Rejection listener leaked')
    for run in observed['runs']:
        if not run['nativeParentAndChildAttached'] or run['errors']:raise RuntimeError('Mount/runtime failed')
        if any(f['errors'] or f['warnings'] for f in run['frames']):raise RuntimeError('Runtime warning/error')
        mounted=frame(observed,run['scenario'],run['variant'],'mount_tick')
        if mounted['state']['domText']!='false|initial|1|1' or not mounted['state']['child']['sharesRoot']:
            raise RuntimeError('Mount control failed')
    cases=[]
    for scenario in observed['scenarios']:
        src=frame(observed,scenario,'vue_source')
        for variant in ['normal','v3']:
            target=frame(observed,scenario,variant)
            cases.append({'scenario':scenario,'variant':variant,
                'parent_state_equal':src['state']['parentSettings']==target['state']['parentSettings'],
                'parent_count_equal':src['state']['count']==target['state']['count'],
                'child_raw_equal':src['state']['child']['raw']==target['state']['child']['raw'],
                'child_computed_equal':src['state']['child']['computed']==target['state']['child']['computed'],
                'dom_text_equal':src['state']['domText']==target['state']['domText'],
                'watch_effects_equal':src['events']==target['events'],
                'source_text':src['state']['domText'],'target_text':target['state']['domText']})
    if not all(r['parent_state_equal'] and r['child_raw_equal'] for r in cases):raise RuntimeError('Raw-state control drift')
    writers=[r for r in cases if r['scenario'].startswith('writer_')]
    for r in writers:
        if not r['watch_effects_equal'] or not r['parent_count_equal']:raise RuntimeError('Writer parent watch changed')
        if r['dom_text_equal']!=(r['variant']=='normal') or r['child_computed_equal']!=(r['variant']=='normal'):
            raise RuntimeError('Expected v3-only native child propagation counterexample')
    aliases=[r for r in cases if r['scenario'] in ['borrowed_existing_property','borrowed_array_push','borrowed_nested_item']]
    # recount derives count from enabled, so a missed invocation does NOT imply
    # a different count for these nested-only edits. Compare the call trace itself.
    if len(aliases)!=6 or any(r['watch_effects_equal'] or not r['parent_count_equal'] or r['dom_text_equal'] or r['child_computed_equal'] for r in aliases):
        raise RuntimeError('Expected both-target borrowed-alias counterexamples')
    controls=[r for r in cases if r not in writers and r not in aliases]
    if len(controls)!=8 or not all(all(r[k] for k in ['parent_count_equal','watch_effects_equal','dom_text_equal','child_computed_equal']) for r in controls):
        raise RuntimeError('Passing controls regressed')
    synthetic=source_parent_watch_semantics(fixture['v3'],fixture['vue'])
    actual_vue=ROOT/next(n for n in old['source_inputs'] if n.endswith('.vue'))
    actual=source_parent_watch_semantics(old['candidate']['code'],actual_vue.read_text(encoding='utf-8'))
    if {r['code'] for r in synthetic['blocked_boundaries']}!={'source_parent_watch_dynamic_key_unproven'}:
        raise RuntimeError('Synthetic no-storage boundary drift')
    if {r['code'] for r in actual['blocked_boundaries']}!=PARENT_WATCH_REVIEW_CODES:
        raise RuntimeError('Actual TaskManager boundaries lost')
    runtime_lines=payload['sanRuntime'].splitlines()
    excerpts=[]
    for marker,following in [('if (this.get(expr) === value && !option.force)',3),
                             ('me.data.set(setExpr, evalExpr(updateExpr, me.scope, me.owner)',6)]:
        for at,line in enumerate(runtime_lines):
            if marker in line:excerpts.append({'line':at+1,'text':'\n'.join(runtime_lines[at:at+following])})
    if len(excerpts)!=3:raise RuntimeError('Pinned San equality/binding source evidence changed')
    if inventory()!=hashes:raise RuntimeError('Files changed during audit')
    return {'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'negative_native_alias_child_audit_not_a_semantic_fix',
        'source_verified_payloads':verified,'source_inputs':old['source_inputs'],
        'previous_inventory_unchanged':401,'production_runtime_inventory_unchanged':387,
        'inventory_count':len(hashes),'manual_page_sha256':MANUAL_SHA,'retained_30_inputs_unchanged':True,
        'original_aggregate':old['original_aggregate'],'fixture':fixture,'runtime_observations':observed,
        'action_tick_comparisons':cases,'san_runtime_source_excerpts':excerpts,
        'synthetic_boundary_diagnostics':synthetic,'actual_task_manager_boundary_diagnostics':actual,
        'findings':[
            {'id':'AC1','category':'repair_regression','scope':'unpromoted_v3_synthetic_fixture_only',
             'triggers':['writer_scalar','writer_object'],'status':'unresolved',
             'root_cause':'Forced same-reference parent root SET is forwarded by native binding without force; child Data.set equality check returns before computed notification.',
             'not_counted_as_canonical_production_defect':True},
            {'id':'AC2','category':'remaining_risk','scope':'normal_flow_and_v3_source_alias_compatibility',
             'triggers':['borrowed_existing_property','borrowed_array_push','borrowed_nested_item'],'status':'unresolved',
             'root_cause':'Vue observes existing nested properties and array mutations; raw borrowed San objects bypass Data notifications and the parent watch queue.',
             'not_counted_as_canonical_production_defect':True}],
        'evidence_boundary':{'real_framework_versions':{'vue':'2.7.16','san':'3.15.6'},
             'minimal_dom_adapter':True,'framework_data_or_prop_binding_mocked':False,
             'native_component_mount_and_text_patching':True,'synthetic_bound_child':True,
             'parent_render_replaced_by_harness':True,'canonical_TaskManager_child_tested':False,
             'real_browser_or_css_layout_tested':False,'real_storage_or_timers_tested':False,
             'dom_operation_log_includes_cleanup':True,'cleanup_not_compared':True},
        'initial_test_attempt':{'tests':16,'failures':1,'elapsed_seconds':4.190,'raw_stdout_preserved':False,
             'failure':'Incorrect test expected storage-exception boundary on synthetic fixture without storage.',
             'correction':'Synthetic fixture asserts dynamic-key boundary only; actual frozen TaskManager separately asserts both boundaries. Production guard unchanged.'},
        'initial_driver_preflight':{'status':'failed_before_any_artifact_write',
             'error':'Expected both-target borrowed-alias counterexamples',
             'cause':'Preflight incorrectly expected count to differ when recount was missed; recount derives enabled?1:0, which remains 0 in the nested-only cases.',
             'correction':'Retain equal count as a control and use the actual callback trace plus child computed/text to detect the missing notification.'},
        'native_child_propagation_closed':False,'deep_alias_reactivity_closed':False,
        'exception_policy_closed':False,'production_integration_enabled':False,
        'production_rules_or_prompt_modified':False,'prior_probe_or_failure_evidence_modified':False,
        'canonical_san_or_manual_pages_modified':False,'source_api_or_storage_schema_restricted':False,
        'model_requests':0,'original_score_modified':False,'full_suite_reexecuted':False,
        'prior_full_suite_reference':old['prior_full_suite_reference'],
        'prior_notebook_cells':58,'prior_notebook_cells_sha256':PREFIX_SHA,'prior_notebook_metadata_sha256':METADATA_SHA}


def report(data):
    t=data['scoped_tests']
    return f'''# 原生父子传播与借用别名审计 v1（2026-11-12）

本轮是 formal_30_v4 的开发诊断，不是新正式测试或修复成功证据。发现并冻结两个未闭合机制；没有更改生产规则、Prompt、旧探针或 canonical San。原批仍24/30通过、6失败、0执行异常、1,821,544 tokens；0模型调用，无新增人工验收。

## 方法与边界

在固定Vue2.7.16/San3.15.6上，真实创建/挂载父子组件，执行框架原生属性绑定、computed、Promise更新队列与文本节点patch。不是模拟Data/watch，也没有手工把父数据传入子组件或调用私有更新器。

使用明确受限的miniDOM节点适配器，不是真实浏览器；HTML解析/选择器不实现（调用会失败），CSS布局/交互/真实存储和业务计时器不测。父组件为受控合成fixture，仅将根数据扩为嵌套结构；装置替换父render/template以绑定合成子组件，业务方法/hooks不改。没有测试canonical TaskManager的真实SettingsPanel，不可外推为生产组件人工通过/失败。清理在快照后执行；DOM操作日志含清理，但清理行为不比较。

9个独立场景×Vue/旧正常流程San/v3三变体=27运行，4阶段=108快照，72个源/目标阶段对照。所有运行原生父子挂载成功，无运行错误/警告，重复执行观察一致。

## 两个反例机制（非新增生产缺陷计数）

1. **AC1：未部署v3候选的子组件传播回归。** 标量和对象两种公开writer调用后，父状态/监听副作用与源一致，子组件原始props也已经改变，但子computed及DOM仍停在`false|initial|1|1`。标量源应为`true|initial|1|1`，对象源应为`false|object|1|8`。旧clone对照可更新。原因是v3原地修改并force通知父根；原生绑定向子组件转发相同引用时不携带force，子Data.set相等判断提前返回。两个表象属于同一根因，不能算两条生产缺陷。
2. **AC2：借用深层别名响应式兼容风险。** 已有嵌套属性赋值、数组push、数组项属性赋值三种场景中，旧正常流程和v3的原始状态虽与Vue相同，但都没有执行源的recount，子computed和DOM未更新。Vue观察过的已有属性/数组修改会通知，而San原始对象别名修改绕过Data通知；赋值身份一致不足以证明深层响应性。

action_tick共18个源/目标比较：8个负向对照（writer的2个v3对照、借用修改的6个对照），10个匹配（writer的2个旧clone对照、4种控制的8个对照）。这里的比例仅描述装置覆盖，不是组件缺陷率或修复通过率。

## 阳性/阴性控制与未解决事项

挂载初值、同值赋值、整根替换、San Data API深路径set均符合预期；新增普通键在Vue2中本来不响应，三变体都不多发通知。完整原始帧、监听调用、文本、错误、警告及DOM操作保存在audit.json，不能只看原始JSON状态。

生产动态键及存储异常两项边界仍保留。合成无存储fixture只应有动态键边界；第一次16项测试有1项因错误要求它也有存储边界而失败（4.190秒，原stdout未保存，仅保留失败摘要）。已修正测试预期，并另查真实冻结TaskManager确有两项边界；没有放宽生产守卫。

首次封存驱动预检也曾因错误预期“漏调recount必然改变count”而中止，未写出证据目录。实际recount只按enabled生成0/1，嵌套修改时count均为0；已保留此相等控制，按真实回调轨迹及子computed/文本识别差异，而非伪造计数差异。

修正后本轮定向测试{t['passed']}/{t['passed']}，0失败/0跳过，{t['elapsed_seconds']}秒。测试通过表示成功检测/锁定反例，不表示候选语义通过。未重跑完整703项；旧完整测试仅作为历史引用。

401项上轮清单（含387项生产/既有运行文件）、30个保留输入/Vue、两个测试页面、旧Notebook58单元/元数据未改。新增3个诊断文件后404项；7个payload经SHA-256封存。

## 下一步

先针对冻结反例设计隔离修复：既保留源对象/借用身份，也使子属性及已有嵌套属性/数组修改得到正确通知；随后复测同值、新键、根替换、旧根/两实例/销毁等控制，异常策略单独闭合。不能以clone恢复UI就宣布引用语义等价，也不能给公开API增加限制或删诊断放行。当前仍不接入生产，不要求付费模型复跑。
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-evidence',action='store_true');args=parser.parse_args()
    if args.write_evidence and OUTPUT.exists():raise FileExistsError('Never overwrite frozen alias/child evidence')
    hashes=inventory();data=inspect();logs='';counts=[]
    if args.write_evidence:
        for suite in ['test_parent_alias_child_audit.py','test_parent_dynamic_key_object_values_v3.py','test_parent_watch_scope_guard.py']:
            print('Running scoped suite: '+suite,flush=True)
            proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',suite,'-v'],cwd=ROOT,
                env={**os.environ,'PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8')
            part=proc.stdout+proc.stderr;logs+='\n### '+suite+'\n'+part
            match=re.search(r'Ran (\d+) tests in ([\d.]+)s',part)
            if proc.returncode or not match or '\nOK' not in part or re.search(r'OK\s*\(skipped=',part):
                failed=OUTPUT.parent/(OUTPUT.name+'_failed_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.txt')
                with failed.open('x',encoding='utf-8') as stream:stream.write(logs)
                raise RuntimeError('Scoped failure log saved: '+str(failed))
            counts.append({'suite':suite,'passed':int(match[1]),'elapsed_seconds':float(match[2])})
        if inventory()!=hashes:raise RuntimeError('Files changed during verification')
        data['scoped_tests']={'passed':sum(r['passed'] for r in counts),'failed':0,'skipped':0,
            'elapsed_seconds':round(sum(r['elapsed_seconds'] for r in counts),3),'suites':counts,'not_a_full_suite':True}
        OUTPUT.mkdir(parents=True,exist_ok=False)
        for name in NAMES:
            target=OUTPUT/'code'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
        for name,value in [('audit.json',data),('live_inventory.json',hashes)]:
            with (OUTPUT/name).open('x',encoding='utf-8') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        for name,value in [('REPORT.md',report(data)),('scoped_tests.txt',logs)]:
            with (OUTPUT/name).open('x',encoding='utf-8') as stream:stream.write(value)
        files=sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        with (OUTPUT/'SHA256SUMS.txt').open('x',encoding='utf-8') as stream:
            stream.write('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files)+'\n')
        data['verified_payloads']=verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'evidence_written':args.write_evidence,'tests':data.get('scoped_tests'),
        'counterexample_mechanisms':2,'production_integration_enabled':False,'model_requests':0,
        'verified_payloads':data.get('verified_payloads')},ensure_ascii=False))


if __name__=='__main__':main()
