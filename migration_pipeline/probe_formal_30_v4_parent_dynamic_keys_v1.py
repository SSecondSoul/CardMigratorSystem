"""Freeze an isolated dynamic-key candidate; never promote it or call a model."""
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

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot
from migration_pipeline.audit_formal_30_v4_parent_watch_boundaries_v1 import (
    BASE, RAW, SAN, VUE, VUE_RUNTIME, SAN_RUNTIME, OUTPUT as DIAGNOSTIC,
)
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import PARENT_WATCH_REVIEW_CODES, candidate_gate
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput

PREVIOUS=ROOT/'data/experiments/analysis/formal_30_v4_parent_watch_scope_guard_v1_20261111'
OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_keys_probe_v1_20261112'
NAMES=['migration_pipeline/probe_parent_dynamic_key_adapter.cjs',
       'migration_pipeline/probe_formal_30_v4_parent_dynamic_keys_v1.py',
       'tests/test_parent_dynamic_key_adapter_probe.py']
NOTEBOOK=ROOT/'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
PREFIX_SHA='c489041253b67c88a425d983cea28e417478f122448447ab9371a1a041e01fc3'
METADATA_SHA='da8e8b42bb4344c317ccdf5038310d76529bda61666c53ff805bcc19dbede418'
MANUAL_SHA={'tests/manual/vue-test-runner.html':'b2e193ef81bd1af84c2e7bd828ac67d4dd18c8f82c4b1100fc298e64a68e0d50',
            'tests/manual/san-test-runner.html':'5b704c7639d83050b0f5ce4ebcaaca166accf855dd541f43cf7498c2d7c46409'}


def structured_digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def inventory():
    prior=json.loads((PREVIOUS/'live_inventory.json').read_text(encoding='utf-8'))
    changed=[name for name,sha in prior.items() if digest(ROOT/name)!=sha]
    if changed:raise RuntimeError('Production/baseline files changed: '+str(changed))
    if any(digest(ROOT/name)!=sha for name,sha in MANUAL_SHA.items()):raise RuntimeError('Manual page changed')
    return {**prior,**{name:digest(ROOT/name) for name in NAMES}}


def notebook_prefix():
    nb=json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    if structured_digest(nb['cells'][:50])!=PREFIX_SHA or structured_digest(nb['metadata'])!=METADATA_SHA:
        raise RuntimeError('Original 50 Notebook cells or metadata changed')


def load_probe_tests():
    # Reuse the new independent native-runtime fixture; this is an offline probe,
    # not a dependency of any production stage.
    sys.path.insert(0,str(ROOT/'tests'))
    spec=importlib.util.spec_from_file_location('dynamic_probe_fixture',ROOT/NAMES[-1])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def probe():
    notebook_prefix();hashes=inventory()
    verified={name:verify_snapshot(path.resolve()) for name,path in [
        ('scope_guard',PREVIOUS),('normal_flow',BASE),('boundary_oracle',DIAGNOSTIC),('raw',RAW)]}
    before=json.loads((PREVIOUS/'replay.json').read_text(encoding='utf-8'))
    prior=json.loads((DIAGNOSTIC/'audit.json').read_text(encoding='utf-8'))
    for name,sha in prior['inputs'].items():
        if digest(ROOT/name)!=sha:raise RuntimeError('Oracle input drift: '+name)
    for row in before['retained_artifact_replays']:
        for prefix in ['input','vue']:
            if digest(ROOT/row[prefix+'_path'])!=row[prefix+'_sha256']:
                raise RuntimeError('Retained 30-sample input changed: '+row['id'])
    p=load_probe_tests();code=SAN.read_text(encoding='utf-8');vue=VUE.read_text(encoding='utf-8')
    candidate=p.adapt(code,vue)
    if not candidate['changes'] or candidate['production_eligible']:raise RuntimeError('Expected an isolated candidate')
    payload={'code':candidate['code'],'vue':vue,'vueRuntime':VUE_RUNTIME.read_bytes().decode('utf-8'),
             'sanRuntime':SAN_RUNTIME.read_bytes().decode('utf-8')}
    observed=p.node(p.DIAGNOSTIC/'code/migration_pipeline/audit_formal_30_v4_parent_watch_boundaries_v1.cjs',payload)
    normal=[r for r in observed['pairs'] if not r['scenario'].startswith('write_failure')]
    if len(normal)!=70 or not all(r['stateEqual'] and r['businessEffectsEqual'] for r in normal):
        raise RuntimeError('Candidate did not close the seven bounded key scenarios')
    source_runs=[r for r in observed['runs'] if r['variant']=='vue_source']
    if source_runs!=[r for r in prior['observations']['runs'] if r['variant']=='vue_source']:
        raise RuntimeError('Source oracle changed')
    for scenario in ['write_failure_captured','write_failure_headless_default']:
        if [r for r in observed['runs'] if r['scenario']==scenario]!=[r for r in prior['observations']['runs'] if r['scenario']==scenario]:
            raise RuntimeError('Candidate must not claim an invented exception policy')
        if all(r['stateEqual'] and r['businessEffectsEqual'] for r in observed['pairs'] if r['scenario']==scenario):
            raise RuntimeError('Expected the exception boundary to remain unclosed')
    generic_code,generic_vue=p.generic_pair();generic_candidate=p.adapt(generic_code,generic_vue)
    extended=p.node(p.EXTENDED,{**payload,'code':generic_candidate['code'],'vue':generic_vue})
    if not extended['equal'] or len(extended['vue']['snapshots'])!=31:raise RuntimeError('Generic native-runtime mismatch')
    unsupported=p.node(p.UNSUPPORTED,{**payload,'code':generic_candidate['code']})
    if len(unsupported)!=5 or not all(r['unchanged'] and r['error']=='Dynamic-key probe: unsupported key or value' for r in unsupported):
        raise RuntimeError('Probe bounds were silently expanded')
    source_diagnostics=source_parent_watch_semantics(candidate['code'],vue)
    if {b['code'] for b in source_diagnostics['blocked_boundaries']}!=PARENT_WATCH_REVIEW_CODES:
        raise RuntimeError('Production boundary finding was suppressed')
    state={'generated_code':code,'vue_source':vue,'validation_errors':source_parent_watch_semantics(code,vue)['findings']}
    forged={**state,'generated_code':candidate['code'],'validation_errors':[],'validation_passed':True}
    gate=candidate_gate(state,forged)
    if not gate['should_stop'] or len(gate['waived_source_parent_watch_boundaries'])!=2:
        raise RuntimeError('Production waiver protection bypassed')
    ssm=json.loads((RAW/'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']['ssm']
    validation=ValidateStage().run(ValidateStageInput(generated_code=candidate['code'],ssm=ssm,vue_file_path=str(VUE))).to_state_update()
    if validation['validation_passed'] or not validation['san_compile_result']['passed']:
        raise RuntimeError('Expected a compilable, explicitly NOT production-accepted candidate')
    if inventory()!=hashes:raise RuntimeError('Runtime changed while probing')
    return {'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'isolated_bounded_candidate_not_production_closure_or_independent_test',
        'source_verified_payloads':verified,'model_requests':0,'production_runtime_inventory_unchanged':387,
        'inventory_count':len(hashes),'original_aggregate':before['original_aggregate'],
        'original_score_modified':False,'retained_30_inputs_sha256_checked_unchanged':True,
        'manual_page_sha256':MANUAL_SHA,
        'inputs':prior['inputs'],'oracle_script':
            (DIAGNOSTIC/'code/migration_pipeline/audit_formal_30_v4_parent_watch_boundaries_v1.cjs').relative_to(ROOT).as_posix(),
        'candidate':candidate,'generic_candidate':generic_candidate,
        'native_frozen_oracle_observations':observed,'native_generic_observations':extended,
        'unsupported_input_refusals':unsupported,'normal_key_pairs':70,'normal_key_pairs_matched':70,
        'exception_scenarios_closed':False,'exception_observations_identical_to_failed_baseline':True,
        'production_diagnostics':source_diagnostics,'actual_validation':validation,'forged_pass_gate':gate,
        'production_integration_enabled':False,'public_arbitrary_dynamic_key_semantics_proven':False,
        'full_suite_reexecuted':False,'prior_full_suite':{'passed':703,'elapsed_seconds':1117.584,
            'path':(PREVIOUS/'unit_tests.txt').relative_to(ROOT).as_posix()},
        'browser_or_manual_recheck':False,'canonical_san_modified':False,
        'prior_notebook_cells':50,'prior_notebook_cells_sha256':PREFIX_SHA,'prior_notebook_metadata_sha256':METADATA_SHA,
        'preliminary_scoped_attempt':{'tests':12,'failures':1,'elapsed_seconds':14.749,
            'cause':'Corruption test used pretty-print whitespace against compact frozen code; fixture asserted input changed before calling adapter.',
            'resolution':'Correct the test mutation strings; no production/candidate rule relaxed.',
            'evidence_kind':'tool_output_summary_not_complete_raw_stdout'},
        'preliminary_evidence_harness_attempt':{'error':'KeyError: tests/manual/vue-test-runner.html',
            'cause':'Existing 387-entry runtime inventory excludes manual pages; the initial report tried to index them there.',
            'resolution':'Verify page hashes independently against the pre-step baseline; no runtime rule or fixture changed.',
            'output_folder_created':False,'evidence_kind':'tool_traceback_summary'}}


def report(data):
    tests=data['scoped_tests']
    return f'''# 动态键受约束候选验证 v1（2026-11-12）

本步只完成隔离候选实现与可重复的运行时验证，**未接入生产修复流程**。不改 generate/repair/validate、调度器或 Prompt，也不撤销动态键及异常策略诊断。不是整批复跑、独立测试或人工验收；原批次仍为24/30、6失败、0执行异常、1,821,544 tokens。

## 实现与证据

- 新增通用 AST 候选：从完整源码对照已通过的父监听队列与动态赋值方法导出，不按 TaskManager 名称分支；保留原尾部通知、异步队列、回调顺序、计时器及销毁逻辑。
- 用每实例 WeakMap 记录每个已观察根对象的原有键。真实根替换时记录新对象，重新使用旧对象时保留旧键集合。新增键进行原生赋值但不通知；已观察键变更时在保持对象身份的前提下发出 Data.set(force) 并显式入队。San根watch会跳过同一对象，因此不能仅靠force实现通知。
- 原生赋值保留新增undefined自有属性与局部__proto__语义，不使用对象spread假装等价。宿主/VM的Object.prototype均未污染。
- 复用未修改的冻结边界装置、真实Vue2.7.16及San3.15.6：9场景×2框架×10阶段=18运行、180快照、90对。7类正常键场景的70/70对状态及**全部业务事件**匹配；2种存储异常场景仍失败且完整观察与旧失败基线一致，未过滤错误或事件。输入是程序导出的新候选，不是原冻结San；装置内部“sanCodeChanged:false”仅代表装置没有再改写其收到的代码，不能解读为本步未产生派生代码。
- 重命名通用夹具用真实框架增加2实例、根对象替换/旧身份恢复、同值、NaN、正负零、局部原型和销毁前排队等序列：每框架31快照，共62快照、31对匹配。5类不支持输入显式拒绝且不改变原状态。
- 候选San编译通过，但生产验证仍失败；伪造通过会被现有保护拒绝。

## 不能部署的边界

只证明字符串键（排除Vue内部__ob__）、平坦标量观察对象、标量写入及受限的局部原型替换。任意访问器、Proxy、Symbol键、对象/Ref值、外部别名和嵌套变更不在已证范围。探针遇到不支持输入会在写入前抛出明确TypeError，这**不是源公开接口对任意输入的等价实现**，因此不能直接替换生产方法，也不能清除动态键诊断。浏览器渲染/计算依赖传播及异常策略亦未闭环。

## 验证与冻结

本轮定向测试{tests['passed']}/{tests['passed']}，0失败/0跳过，{tests['elapsed_seconds']}秒。首轮12项中1项因测试破坏字符串空格不匹配而失败，记录保留；修正夹具后独立重新执行。生产清单387项原字节不变，加入3个探针/测试文件后记录390项。没有重跑完整703项；703/703仅引用上轮不可变日志，不能与本轮定向测试拼接成新的完整套件成绩。30个保留输入及Vue源码指纹、两个测试页面均未变，0模型请求。冻结前Notebook前50单元与元数据核验不变。

首次证据整理因错误地从运行清单索引测试页面而出现KeyError，尚未创建冻结目录；已改为独立校验预先记录的页面指纹。保留该整理失败，不视为组件缺陷或候选规则失败。

## 下一步

先完成可部署契约：证明或明确限制公开写入接口的可达键/值与别名，补充真实渲染依赖检查；存储异常路由仍需明确应用运行策略。然后才接入通用规则、验证器、候选拒绝保护和调度器，运行完整回归。此时不需要用户启动付费模型复跑。
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-evidence',action='store_true');args=parser.parse_args()
    if args.write_evidence and OUTPUT.exists():raise FileExistsError('Never overwrite frozen candidate evidence')
    hashes=inventory();data=probe();log=''
    if args.write_evidence:
        suites=['test_parent_dynamic_key_adapter_probe.py','test_parent_watch_scope_guard.py',
                'test_source_parent_watch_closure.py','test_parent_watch_boundaries_audit.py']
        counts=[];seconds=0
        for suite in suites:
            print('Running scoped suite: '+suite,flush=True)
            proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',suite,'-v'],cwd=ROOT,
                env={**os.environ,'PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8')
            part=proc.stdout+proc.stderr;log+='\n### '+suite+'\n'+part
            match=re.search(r'Ran (\d+) tests in ([\d.]+)s',part)
            if proc.returncode or not match or '\nOK' not in part or re.search(r'OK\s*\(skipped=',part):
                failed=OUTPUT.parent/(OUTPUT.name+'_failed_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.txt')
                with failed.open('x',encoding='utf-8') as stream:stream.write(log)
                raise RuntimeError('Complete scoped failure log retained at '+str(failed))
            counts.append({'suite':suite,'passed':int(match[1]),'elapsed_seconds':float(match[2])});seconds+=float(match[2])
        if inventory()!=hashes:raise RuntimeError('Runtime changed during scoped tests')
        notebook_prefix()
        data['scoped_tests']={'passed':sum(r['passed'] for r in counts),'failed':0,'skipped':0,
            'elapsed_seconds':round(seconds,3),'suites':counts,'not_a_full_suite':True}
        OUTPUT.mkdir(parents=True)
        for name in NAMES:
            target=OUTPUT/'code'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
        for name,value in [('audit.json',data),('live_inventory.json',hashes)]:
            with (OUTPUT/name).open('x',encoding='utf-8') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        for name,text in [('REPORT.md',report(data)),('scoped_tests.txt',log),
                          ('TaskManager_dynamic_key_probe_offline.san',data['candidate']['code'])]:
            with (OUTPUT/name).open('x',encoding='utf-8') as stream:stream.write(text)
        files=sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        with (OUTPUT/'SHA256SUMS.txt').open('x',encoding='utf-8') as stream:
            stream.write('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files)+'\n')
        data['verified_payloads']=verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'evidence_written':args.write_evidence,'production_integration_enabled':False,
        'normal_key_pairs_matched':70,'exception_scenarios_closed':False,
        'tests':data.get('scoped_tests'),'model_requests':0,'verified_payloads':data.get('verified_payloads')},ensure_ascii=False))


if __name__=='__main__':main()
