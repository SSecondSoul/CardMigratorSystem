"""Freeze explicit reporting-only contract, retaining default/throwing failures."""
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
from migration_pipeline.audit_formal_30_v4_parent_watch_boundaries_v1 import RAW
from migration_pipeline.stages.validate import ValidateStage,ValidateStageInput
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate,PARENT_WATCH_REVIEW_CODES

PRIOR=ROOT/'data/experiments/analysis/formal_30_v4_parent_alias_observer_v4_20261112'
SCOPE=ROOT/'data/experiments/analysis/formal_30_v4_parent_watch_scope_guard_v1_20261111'
OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_watch_error_router_v5_20261113'
NOTEBOOK=ROOT/'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
PREFIX_SHA='f36c1a4db47ee3ba8a217a8efb8686486194318f30fbbc22e70f8dcfa3c58225'
METADATA_SHA='da8e8b42bb4344c317ccdf5038310d76529bda61666c53ff805bcc19dbede418'
NAMES=['migration_pipeline/probe_parent_watch_error_router_v5.cjs',
       'migration_pipeline/audit_parent_watch_error_router_v5_runtime.cjs',
       'migration_pipeline/probe_formal_30_v4_watch_error_router_v5.py',
       'tests/test_parent_watch_error_router_v5.py']
ACCEPTANCE='tests/manual/formal-30-v4-runtime-acceptance.js'


def stable(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def inventory():
    old=json.loads((PRIOR/'live_inventory.json').read_text(encoding='utf-8'))
    changed=[n for n,s in old.items() if digest(ROOT/n)!=s]
    if changed:raise RuntimeError('409 prior runtime files changed: '+str(changed))
    evidence=json.loads((PRIOR/'audit.json').read_text(encoding='utf-8'))
    if any(digest(ROOT/n)!=s for n,s in evidence['manual_page_sha256'].items()):raise RuntimeError('Manual pages changed')
    nb=json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    if stable(nb['cells'][:62])!=PREFIX_SHA or stable(nb['metadata'])!=METADATA_SHA:raise RuntimeError('Old Notebook cells/metadata changed')
    return {**old,**{n:digest(ROOT/n) for n in NAMES}}


def fixtures():
    sys.path.insert(0,str(ROOT/'tests'))
    spec=importlib.util.spec_from_file_location('error_v5_fixture',ROOT/NAMES[-1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


def gather():
    hashes=inventory();p=fixtures();old,base,common,candidate=p.payloads()
    verified={'v4_candidate':verify_snapshot(PRIOR.resolve()),'scope_guard':verify_snapshot(SCOPE.resolve())}
    for n,s in old['source_inputs'].items():
        if digest(ROOT/n)!=s:raise RuntimeError('Source/runtime drift: '+n)
    retained=json.loads((SCOPE/'replay.json').read_text(encoding='utf-8'))['retained_artifact_replays']
    if len(retained)!=30:raise RuntimeError('Expected 30 retained inputs')
    for row in retained:
        for key in ['input','vue']:
            if digest(ROOT/row[key+'_path'])!=row[key+'_sha256']:raise RuntimeError('Retained input drift: '+row['id'])
    payload={'vue':base['vue'],'san_v4':old['candidate']['code'],'san_v5':candidate['code'],**common}
    observed=p.node(p.RUNTIME,payload)
    if observed!=p.node(p.RUNTIME,payload):raise RuntimeError('Nondeterministic explicit-policy audit')
    rows=[r for r in observed['pairs'] if r['variant']=='san_v5' and r['positiveContract']]
    if len(rows)!=60 or not all(r['stateEqual'] and r['businessAndApplicationErrorEventsEqual'] and r['warningsEqual'] for r in rows):
        raise RuntimeError('Returning reporting-only policy mismatch')
    negative=[]
    for s in observed['scenarios']:
        if s['positive']:continue
        rows=[r for r in observed['pairs'] if r['variant']=='san_v5' and r['scenario']==s['name']]
        mismatch=[r for r in rows if not(r['stateEqual'] and r['businessAndApplicationErrorEventsEqual'] and r['warningsEqual'])]
        if not mismatch:raise RuntimeError('Out-of-contract case incorrectly marked closed')
        negative.append({'scenario':s['name'],'mismatch_phases':[r['phase'] for r in mismatch]})
    structure=p.node(p.STRUCTURE,{'before':old['candidate']['code'],'after':candidate['code']})
    if structure!={'configure':1,'catches':1,'rest_of_script_unchanged':True}:raise RuntimeError('Changed more than dispatch and reporter slot')
    boundary=p.node(p.BOUNDARY/'code/migration_pipeline/audit_formal_30_v4_parent_watch_boundaries_v1.cjs',
        {'code':candidate['code'],'vue':base['vue'],**common})
    if boundary!=old['boundary_observations']:raise RuntimeError('Unconfigured old oracle changed')
    f=old['mounted_fixture'];generic=p.adapt(f['normal'],f['vue'])
    mounted=p.node(p.OLD_ALIAS/'code/migration_pipeline/audit_parent_alias_child_runtime.cjs',
        {**f,'v3':generic['code'],**common})
    if mounted!=old['mounted_observations']:raise RuntimeError('v4 native child behavior changed')
    ssm=json.loads((RAW/'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']['ssm']
    vue_path=ROOT/next(n for n in old['source_inputs'] if n.endswith('.vue'))
    validation=ValidateStage().run(ValidateStageInput(generated_code=candidate['code'],ssm=ssm,vue_file_path=str(vue_path))).to_state_update()
    if validation['validation_passed'] or not validation['san_compile_result']['passed']:raise RuntimeError('Expected compilable but still blocked candidate')
    diagnostics=source_parent_watch_semantics(candidate['code'],base['vue'])
    if {r['code'] for r in diagnostics['blocked_boundaries']}!=PARENT_WATCH_REVIEW_CODES:raise RuntimeError('Lost production boundary')
    before={'generated_code':base['code'],'vue_source':base['vue'],'validation_errors':source_parent_watch_semantics(base['code'],base['vue'])['findings']}
    gate=candidate_gate(before,{**before,'generated_code':candidate['code'],'validation_errors':[],'validation_passed':True})
    if not gate['should_stop'] or len(gate['waived_source_parent_watch_boundaries'])!=2:raise RuntimeError('Forged pass was not refused')
    application_paths={**old['manual_page_sha256'],ACCEPTANCE:digest(ROOT/ACCEPTANCE)}
    vue_runner=(ROOT/'tests/manual/vue-test-runner.html').read_text(encoding='utf-8')
    san_runner=(ROOT/'tests/manual/san-test-runner.html').read_text(encoding='utf-8')
    acceptance=(ROOT/ACCEPTANCE).read_text(encoding='utf-8')
    application={'files_sha256':application_paths,'evidence_level':'local_script_static_only_not_CDN_or_live_browser_state',
        'vue_runner_contains_explicit_global_handler':'Vue.config.errorHandler' in vue_runner,
        'vue_CDN_floating_major':'vue@2/dist/vue.js' in vue_runner,
        'san_runner_CDN_version_3153':'san@3.15.3/' in san_runner,
        'manual_runtime_versions_not_equal_to_pinned_pair':True,
        'acceptance_listens_to_unhandledrejection':"addEventListener('unhandledrejection'" in acceptance,
        'acceptance_observer_is_not_a_watcher_error_router':True,
        'existing_application_reporter_implementation_identified':False}
    excerpts=[]
    for label,lines,marker,count in [('vue',common['vueRuntime'].splitlines(),'function globalHandleError(err, vm, info)',28),
                                   ('vue',common['vueRuntime'].splitlines(),'function logError(err, vm, info)',13),
                                   ('san',common['sanRuntime'].splitlines(),'function handleError(e, component, info)',17)]:
        hits=[i for i,line in enumerate(lines) if marker in line]
        if len(hits)!=1:raise RuntimeError('Pinned error source excerpt changed')
        at=hits[0];excerpts.append({'runtime':label,'line':at+1,'text':'\n'.join(lines[at:at+count])})
    if inventory()!=hashes or any(digest(ROOT/n)!=s for n,s in application_paths.items()):raise RuntimeError('Files changed during audit')
    return {'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'isolated_explicit_reporting_only_policy_not_default_exception_closure',
        'source_verified_payloads':verified,'source_inputs':old['source_inputs'],'manual_page_sha256':old['manual_page_sha256'],
        'previous_inventory_unchanged':409,'production_runtime_inventory_unchanged':387,'inventory_count':len(hashes),
        'retained_30_inputs_unchanged':True,'original_aggregate':old['original_aggregate'],
        'candidate':candidate,'generic_candidate':generic,'application_policy_static_audit':application,
        'pinned_error_source_excerpts':excerpts,'explicit_policy_observations':observed,
        'out_of_contract_failures':negative,'exact_scope_structure_check':structure,
        'old_unconfigured_boundary_observations':boundary,'mounted_observations':mounted,
        'actual_validation':validation,'production_diagnostics':diagnostics,'forged_pass_gate':gate,
        'returning_reporting_only_contract_matched':True,'source_default_exception_contract_closed':False,
        'browser_default_or_errorCaptured_proven':False,'throwing_or_async_reporter_proven':False,
        'application_reporter_deployed':False,'production_integration_enabled':False,
        'canonical_san_or_manual_pages_modified':False,'prior_probe_or_failure_evidence_modified':False,
        'production_rules_or_prompt_modified':False,'source_api_or_storage_schema_restricted':False,
        'model_requests':0,'original_score_modified':False,'full_suite_reexecuted':False,'manual_or_browser_rechecked':False,
        'prior_full_suite_reference':old['prior_full_suite_reference'],
        'prior_notebook_cells':62,'prior_notebook_cells_sha256':PREFIX_SHA,'prior_notebook_metadata_sha256':METADATA_SHA}


def report(d):
    return f'''# 显式应用错误报告器：隔离候选 v5（2026-11-13）

**只闭合“显式提供、同步返回、只记录而不读写组件状态的报告器”这一测试约定；默认异常策略没有闭合。** formal_30_v4开发探针，非正式独立测试或新30样本成绩。原批24/30、6失败、0执行异常、1,821,544 tokens不变；0模型请求，无新增人工验收。

## 根因和实际改动

Vue原生逐个调用用户watcher时处理异常；原合并Promise队列中的一个回调抛错会退出flush，使后续回调不执行。v5只在源顺序队列的单个dispatch外加try/catch，以及一个实例级报告器配置方法。报告器收到原Error对象、当前组件及精确watcher归属，以null作为this；返回后继续下一个watcher，但绝不恢复已失败回调内部的剩余语句。不重试存储、不加默认日志、不改Promise拒绝或全局框架配置。没有报告器就重新抛出原异常，报告器自身抛错也继续向外传播；这些失败不是已实现的Vue全局回退。

AST差分仅一个dispatch catch和一个配置方法；队列排序/去重/取消、v4引用/观察桥、完整源赋值右侧及业务方法/事件/生命周期其余脚本不变。需要显式experimental及error_policy参数；配置方法是实验应用适配入口，未在生产应用接入，不是给原源API添加限制。

## 原生运行时对照

固定Vue2.7.16/San3.15.6。9场景×3变体×10阶段=27运行、270快照、180源/目标阶段比较。6个明确报告约定场景中，源/v5的60/60阶段在状态、完整业务事件（含应用错误报告）、警告上匹配。覆盖无异常、tasks失败后settings继续、settings失败不执行自身后续同步、同轮两个watcher各报一次、后轮失败保留旧计时器、报告器返回false不误终止队列。错误身份、组件归属、watcher信息、先后顺序均检查。

rawErrors保留Vue.config.errorHandler与San实例报告器的不同通道，不能说原生框架报错标签相同；共同应用报告事件的比较不是删除原始错误。旧v4无报告器对照也保留。localStorage/应用timer是明确的故障注入装置，不是真实浏览器存储或业务timer执行；原生框架/Promise实际运行。

## 仍失败的边界（完整保留）

{json.dumps(d['out_of_contract_failures'],ensure_ascii=False,indent=2)}

这三组共30阶段里仍有差异。源Node默认抛错会影响原生调度队列后续状态；v4/v5未实现这一策略。缺少目标报告器不能静默退回console；报告器抛错的全局回退、errorCaptured、异步/可重入报告器、组件状态依赖收集、浏览器默认路由也未证明。旧冻结9场景原装置在不配置报告器时的全部观察与v4逐字节相同，旧两种异常失败没被替换为成功；旧native子组件装置观察也原样保留。

## 应用现状（仅本地脚本静态核对）

本地Vue runner没有显式Vue.config.errorHandler声明；San runner没有接入上述实验入口。验收页的window error/unhandledrejection监听只记录事件，不构成watcher恢复策略。Vue CDN为@2浮动主版本，San页引用3.15.3，而探针使用固定2.7.16/3.15.6；未联网取CDN、未启动页面，不推断浏览器实际全局配置，更不改测试页。故不能把本次显式测试约定自动当作现有应用默认策略。

## 验证及证据

定向测试：{json.dumps(d['scoped_tests'],ensure_ascii=False)}。未重跑完整703项；历史完整成绩仅引用旧日志。候选San编译通过，生产验证仍失败；动态键/异常策略诊断及伪造通过保护均保留。原409文件（含387生产/既有运行文件）、30个保留输入/Vue、两个测试页及旧Notebook62单元/元数据保留；新增4文件后413项，9个payload封存。

下一步应验证源浏览器默认错误链/祖先捕获和报告器异常回退，或先明确应用真正采用的报告契约；在此之前不接入生产、不启动模型复跑、不改原批成绩。当前显式报告约定是候选可选能力，不是完整异常闭环。
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-evidence',action='store_true');args=parser.parse_args()
    if args.write_evidence and OUTPUT.exists():raise FileExistsError('Never overwrite frozen v5 evidence')
    hashes=inventory();d=gather();logs='';counts=[]
    if args.write_evidence:
        for suite in ['test_parent_watch_error_router_v5.py','test_parent_alias_observer_v4.py','test_parent_watch_scope_guard.py']:
            print('Running scoped suite: '+suite,flush=True)
            proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',suite,'-v'],cwd=ROOT,
                env={**os.environ,'PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8')
            part=proc.stdout+proc.stderr;logs+='\n### '+suite+'\n'+part;match=re.search(r'Ran (\d+) tests in ([\d.]+)s',part)
            if proc.returncode or not match or '\nOK' not in part or re.search(r'OK\s*\(skipped=',part):
                failed=OUTPUT.parent/(OUTPUT.name+'_failed_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.txt')
                with failed.open('x',encoding='utf-8') as stream:stream.write(logs)
                raise RuntimeError('Scoped failure log saved: '+str(failed))
            counts.append({'suite':suite,'passed':int(match[1]),'elapsed_seconds':float(match[2])})
        if inventory()!=hashes:raise RuntimeError('Runtime changed during verification')
        d['scoped_tests']={'passed':sum(r['passed'] for r in counts),'failed':0,'skipped':0,
            'elapsed_seconds':round(sum(r['elapsed_seconds'] for r in counts),3),'suites':counts,'not_a_full_suite':True}
        OUTPUT.mkdir(parents=True,exist_ok=False)
        for name in NAMES:
            target=OUTPUT/'code'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
        for name,value in [('audit.json',d),('live_inventory.json',hashes)]:
            with (OUTPUT/name).open('x',encoding='utf-8') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        for name,value in [('REPORT.md',report(d)),('scoped_tests.txt',logs),('TaskManager_error_router_v5_offline.san',d['candidate']['code'])]:
            with (OUTPUT/name).open('x',encoding='utf-8') as stream:stream.write(value)
        files=sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        with (OUTPUT/'SHA256SUMS.txt').open('x',encoding='utf-8') as stream:
            stream.write('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files)+'\n')
        d['verified_payloads']=verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'written':args.write_evidence,'tests':d.get('scoped_tests'),'verified_payloads':d.get('verified_payloads'),
        'returning_reporting_only_contract_matched':True,'source_default_exception_contract_closed':False,
        'production_integration_enabled':False,'model_requests':0},ensure_ascii=False))


if __name__=='__main__':main()
