"""Freeze native browser-branch and ancestor counterexamples; no rule/model changes."""
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
from migration_pipeline.utils.repair_scheduler import PARENT_WATCH_REVIEW_CODES

PRIOR=ROOT/'data/experiments/analysis/formal_30_v4_watch_error_router_v5_20261113'
ALIAS=ROOT/'data/experiments/analysis/formal_30_v4_parent_alias_child_audit_v1_20261112'
SCOPE=ROOT/'data/experiments/analysis/formal_30_v4_parent_watch_scope_guard_v1_20261111'
OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_browser_error_chain_audit_v1_20261113'
NOTEBOOK=ROOT/'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
PREFIX_SHA='24002cc738a9e0b8ab3e40c5addcffc60d691e186e40ce5ec0c6ad0bad722316'
METADATA_SHA='da8e8b42bb4344c317ccdf5038310d76529bda61666c53ff805bcc19dbede418'
NAMES=['migration_pipeline/audit_browser_error_chain_v1_runtime.cjs',
       'migration_pipeline/audit_formal_30_v4_browser_error_chain_v1.py',
       'tests/test_browser_error_chain_audit_v1.py']


def stable(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def inventory():
    old=json.loads((PRIOR/'live_inventory.json').read_text(encoding='utf-8'))
    drift=[n for n,s in old.items() if digest(ROOT/n)!=s]
    if drift:raise RuntimeError('Prior 413 files changed: '+str(drift))
    d=json.loads((PRIOR/'audit.json').read_text(encoding='utf-8'))
    if any(digest(ROOT/n)!=s for n,s in d['application_policy_static_audit']['files_sha256'].items()):raise RuntimeError('Application pages/scripts changed')
    nb=json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    if stable(nb['cells'][:64])!=PREFIX_SHA or stable(nb['metadata'])!=METADATA_SHA:raise RuntimeError('Old Notebook cells/metadata changed')
    return {**old,**{n:digest(ROOT/n) for n in NAMES}}


def fixtures():
    sys.path.insert(0,str(ROOT/'tests'))
    spec=importlib.util.spec_from_file_location('browser_error_fixture',ROOT/NAMES[-1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


def gather():
    hashes=inventory();p=fixtures();old,payload=p.payload()
    verified={k:verify_snapshot(v.resolve()) for k,v in [('v5_candidate',PRIOR),('frozen_dom_adapter',ALIAS),('scope_guard',SCOPE)]}
    if verified!={'v5_candidate':9,'frozen_dom_adapter':7,'scope_guard':25}:raise RuntimeError('Evidence scope drift')
    extra=[PRIOR/'TaskManager_error_router_v5_offline.san',ALIAS/'code/migration_pipeline/audit_parent_alias_child_runtime.cjs']
    inputs={**old['source_inputs'],**{v.relative_to(ROOT).as_posix():digest(v) for v in extra}}
    for n,s in inputs.items():
        if digest(ROOT/n)!=s:raise RuntimeError('Source/runtime drift: '+n)
    if extra[0].read_text(encoding='utf-8')!=payload['san_v5']:raise RuntimeError('Frozen candidate mismatch')
    retained=json.loads((SCOPE/'replay.json').read_text(encoding='utf-8'))['retained_artifact_replays']
    if len(retained)!=30:raise RuntimeError('Expected 30 retained inputs')
    for row in retained:
        for key in ['input','vue']:
            if digest(ROOT/row[key+'_path'])!=row[key+'_sha256']:raise RuntimeError('Retained input drift: '+row['id'])
    observed=p.node(p.RUNTIME,payload)
    if observed!=p.node(p.RUNTIME,payload):raise RuntimeError('Nondeterministic native audit')
    if len(observed['runs'])!=22 or len(observed['pairs'])!=110 or sum(len(r['phases']) for r in observed['runs'])!=220:
        raise RuntimeError('Audit dimensions changed')
    controls=[r for r in observed['pairs'] if r['scenario'] in ['normal','global_handler_returns']]
    keys=['stateEqual','eventsEqual','rawConsoleEqual','unhandledRejectionsEqual']
    if len(controls)!=20 or not all(all(r[k] for k in keys) for r in controls):raise RuntimeError('Positive controls failed')
    failures=[]
    for spec in observed['scenarios']:
        if spec['name'] in ['normal','global_handler_returns']:continue
        rows=[r for r in observed['pairs'] if r['scenario']==spec['name']]
        mismatch=[r for r in rows if not all(r[k] for k in keys)]
        if not mismatch:raise RuntimeError('Negative route no longer exposes mismatch')
        failures.append({'scenario':spec['name'],'mismatch_phases':[r['phase'] for r in mismatch],
                         'state_matches_all_phases':all(r['stateEqual'] for r in rows)})
    for r in observed['runs']:
        if not r['nativeAncestorChain']:raise RuntimeError('Synthetic non-native parent chain')
        if r['variant']=='vue_source':
            frame=next(v for v in r['phases'] if v['name']=='primary_tick')
            if frame['state']['intervalDelays']!=[30000] or frame['unhandledRejections']:raise RuntimeError('Unexpected Vue browser continuation')
        else:
            control=r['nativeSanControl']
            if not control['nativeChildParentLink'] or not control['nearReturnedTrue'] or control['received']!=[
                {'ancestor':'near','originalError':True,'subjectIsChild':True,'info':'watch:value'}]:
                raise RuntimeError('Native San ancestor control failed')
    diagnostics=source_parent_watch_semantics(payload['san_v5'],payload['vue'])
    if {b['code'] for b in diagnostics['blocked_boundaries']}!=PARENT_WATCH_REVIEW_CODES:raise RuntimeError('Production boundaries lost')
    if inventory()!=hashes:raise RuntimeError('Files changed during audit')
    return {'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'negative_native_browser_branch_ancestor_audit_not_a_repair',
        'source_verified_payloads':verified,'source_inputs':inputs,'previous_inventory_unchanged':413,
        'production_runtime_inventory_unchanged':387,'inventory_count':len(hashes),
        'application_files_sha256':old['application_policy_static_audit']['files_sha256'],
        'retained_30_inputs_unchanged':True,'original_aggregate':old['original_aggregate'],
        'native_observations':observed,'negative_route_scenarios':failures,'production_diagnostics':diagnostics,
        'validation_reference':{'path':(PRIOR/'audit.json').relative_to(ROOT).as_posix(),
            'candidate_unchanged':True,'san_compile_passed':old['actual_validation']['san_compile_result']['passed'],
            'production_validation_passed':old['actual_validation']['validation_passed'],'new_compile_run_claimed':False},
        'finding':{'category':'remaining_risk','scope':'unpromoted_queue_source_error_context',
            'root_cause':'Merged Promise callback exceptions bypass native component error routing; San nearest-error-hook semantics also differ from Vue ancestor capture/global fallback.',
            'nine_scenarios_are_not_nine_production_defects':True,'status':'unresolved'},
        'evidence_boundary':{'runtime_versions':{'vue':'2.7.16','san':'3.15.6'},'vue_inBrowser_branch_executed':True,
            'real_browser_opened':False,'limited_dom_adapter':True,'native_ancestor_components_mounted':True,
            'subject_render_replaced':True,'subject_business_bodies_changed':False,
            'actual_canonical_TaskManager_UI_tested':False,'real_storage_or_business_timers':False,
            'host_process_rejection_listener_only_observes':True,'private_error_functions_called_by_harness':False,
            'eleven_separate_native_San_watch_controls_outside_main_phase_comparisons':True},
        'source_default_exception_contract_closed':False,'ancestor_and_reporter_fallback_fixed':False,
        'adapter_modified':False,'production_integration_enabled':False,'canonical_san_or_manual_pages_modified':False,
        'prior_probe_or_failure_evidence_modified':False,'production_rules_or_prompt_modified':False,
        'model_requests':0,'original_score_modified':False,'full_suite_reexecuted':False,'manual_or_browser_rechecked':False,
        'prior_full_suite_reference':old['prior_full_suite_reference'],
        'prior_notebook_cells':64,'prior_notebook_cells_sha256':PREFIX_SHA,'prior_notebook_metadata_sha256':METADATA_SHA}


def report(d):
    return f'''# 原生浏览器分支与祖先错误链审计 v1（2026-11-13）

**这是新增负向证据，不是修复成功。** 原批仍24/30、6失败、0执行异常、1,821,544 tokens；0模型调用，无新增人工验收。不改v5或任何生产规则/Prompt/页面。

## 方法

Vue2.7.16/San3.15.6在固定受限miniDOM中实际创建并挂载Far→Near→Subject，验证真实$parent/parentComponent身份；原TaskManager业务方法及生命周期身体不改，只将Subject根render/template替换为最小节点。配置的ancestor hooks/global handler是测试应用环境，不声称既有应用已部署。Vue真的执行inBrowser分支，未调用任何私有错误函数；这不是Chrome等真实浏览器、CSS、真实存储或业务timer验收。Node宿主只观察unhandledRejection，不给被测Promise补catch。原始Vue warning组件栈、Error严格身份、hook顺序及拒绝记录完整保留。

11场景×2变体×10阶段=22运行、220快照、110比较。正常/显式返回global handler两个控制组20/20阶段在状态、事件、原始console和拒绝上匹配。其余9组仍有差异；这是同一个未闭合错误上下文契约下的9种场景，不计为9条生产缺陷。

## 已确认的源约定

- 浏览器默认无handler时，Vue记录原错误后继续下一watcher；v5无报告器则Promise拒绝并漏掉本轮settings，同步interval没有启动。
- errorCaptured从近到远、同祖先按声明顺序执行；返回false停止传播，返回true不停止。hook的this是祖先，错误subject仍是原组件。
- 捕获钩子抛错时，次生错误按该祖先及errorCaptured hook归属进入全局路径；之后原错误仍可继续被远祖捕获。
- 全局handler抛不同错误时，浏览器分支先记录次生错误，再记录原错误并继续队列；重新抛原错误只记录一次。v5目前没有该fallback。
- 业务状态完全一致也可能错误链不一致：capture_returns_true_global、near_throw_global_returns两组的所有状态阶段相等，但hook路径/事件不等。

11个独立原生San watch阳性控制均证实原Error可到达最近ancestor.error。**最近error返回true时，San仍停止，不会像Vue errorCaptured那样继续向远祖冒泡。** 因此既不能说San钩子坏了，也不能直接把errorCaptured改名成error。自定义合并Promise队列的异常还绕过了这条可用的San原生链。

## 保留的失败

{json.dumps(d['negative_route_scenarios'],ensure_ascii=False,indent=2)}

上述所有原始帧/console/拒绝与应用hook事件在audit.json，无过滤成成功。未生成新San；仍使用上轮封存v5原字节。沿用其San编译通过/生产验证失败的已有记录，不声称本轮新编译。动态键/异常策略守卫继续保留。

## 验证、边界及下一步

定向测试：{json.dumps(d['scoped_tests'],ensure_ascii=False)}；并非完整703项重跑。旧413项（含387生产/既有运行文件）、30个保留输入/Vue、页面/验收脚本及Notebook旧64单元/元数据未改；新增3诊断文件后416项，7payload封存。

下一步设计独立的“源错误上下文桥”：明确映射source ancestor hook顺序、false短路、全局handler及浏览器fallback，同时保留原/次生错误身份与组件归属。不能把所有错误直接交给San最近error钩子、吞掉异常或仅凭UI状态相等放行。浏览器/SSR策略、依赖暂停和真实应用祖先配置仍需分别证明；在此之前不生产集成、不付费模型复跑、不更新原成绩。
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-evidence',action='store_true');args=parser.parse_args()
    if args.write_evidence and OUTPUT.exists():raise FileExistsError('Never overwrite frozen browser-error audit')
    hashes=inventory();d=gather();logs='';counts=[]
    if args.write_evidence:
        for suite in ['test_browser_error_chain_audit_v1.py','test_parent_watch_error_router_v5.py','test_parent_watch_scope_guard.py']:
            print('Running scoped suite: '+suite,flush=True)
            proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',suite,'-v'],cwd=ROOT,
                env={**os.environ,'PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8')
            part=proc.stdout+proc.stderr;logs+='\n### '+suite+'\n'+part;match=re.search(r'Ran (\d+) tests in ([\d.]+)s',part)
            if proc.returncode or not match or '\nOK' not in part or re.search(r'OK\s*\(skipped=',part):
                failed=OUTPUT.parent/(OUTPUT.name+'_failed_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.txt')
                with failed.open('x',encoding='utf-8') as stream:stream.write(logs)
                raise RuntimeError('Scoped failure log saved: '+str(failed))
            counts.append({'suite':suite,'passed':int(match[1]),'elapsed_seconds':float(match[2])})
        if inventory()!=hashes:raise RuntimeError('Files changed during verification')
        d['scoped_tests']={'passed':sum(r['passed'] for r in counts),'failed':0,'skipped':0,
            'elapsed_seconds':round(sum(r['elapsed_seconds'] for r in counts),3),'suites':counts,'not_a_full_suite':True}
        OUTPUT.mkdir(parents=True,exist_ok=False)
        for name in NAMES:
            target=OUTPUT/'code'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
        for name,value in [('audit.json',d),('live_inventory.json',hashes)]:
            with (OUTPUT/name).open('x',encoding='utf-8') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        for name,value in [('REPORT.md',report(d)),('scoped_tests.txt',logs)]:
            with (OUTPUT/name).open('x',encoding='utf-8') as stream:stream.write(value)
        files=sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        with (OUTPUT/'SHA256SUMS.txt').open('x',encoding='utf-8') as stream:
            stream.write('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files)+'\n')
        d['verified_payloads']=verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'written':args.write_evidence,'tests':d.get('scoped_tests'),'verified_payloads':d.get('verified_payloads'),
        'negative_route_groups':9,'adapter_modified':False,'production_integration_enabled':False,'model_requests':0},ensure_ascii=False))


if __name__=='__main__':main()
