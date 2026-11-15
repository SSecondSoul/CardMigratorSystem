"""Freeze conservative watcher-scope guard, current diagnostics and zero-model review stop."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot
from migration_pipeline.audit_formal_30_v4_parent_watch_boundaries_v1 import BASE, RAW, OUTPUT as DIAGNOSTIC, CODE_NAMES
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import PARENT_WATCH_REVIEW_CODES, candidate_gate
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.generate import GenerateStageInput, GenerateStageResult
from migration_pipeline.stages.visual_eval import VisualEvalStage
from migration_pipeline.orchestrator import MigrationPipelineOrchestrator

OUTPUT = ROOT/'data/experiments/analysis/formal_30_v4_parent_watch_scope_guard_v1_20261111'
CHANGED = {'migration_pipeline/utils/source_parent_watch_semantics.py','migration_pipeline/utils/source_parent_watch_semantics.cjs',
    'migration_pipeline/stages/validate.py','migration_pipeline/utils/repair_prompt.py','migration_pipeline/utils/repair_scheduler.py',
    'tests/test_source_parent_watch_closure.py','tests/test_source_array_transaction_closure.py',
    'tests/test_source_child_initialization_closure.py','tests/test_source_dom_closure.py','tests/test_source_render_dependency_closure.py',
    'tests/test_source_native_drag_closure.py','tests/test_source_inline_formatter_closure.py','tests/test_source_payload_closure.py',
    'tests/test_source_render_call_closure.py','tests/test_repair_regression_guard.py','tests/test_semantic_regression_gate.py'}
ADDED = set(CODE_NAMES)|{'migration_pipeline/replay_formal_30_v4_parent_watch_scope_guard_v1.py','tests/test_parent_watch_scope_guard.py'}


def inventory():
    previous=json.loads((BASE/'live_inventory.json').read_text(encoding='utf-8'))
    now={name:digest(ROOT/name) for name in sorted(set(previous)|ADDED)}
    changed={name for name,sha in previous.items() if now[name]!=sha}
    if changed!=CHANGED:
        raise RuntimeError('Unexpected production delta: '+str(changed^CHANGED))
    for name in CODE_NAMES:
        if digest(ROOT/name)!=digest(DIAGNOSTIC/'code'/name):
            raise RuntimeError('Boundary diagnostic code must remain unchanged: '+name)
    return now


def scheduler(code,vue,ssm):
    class NoModel:
        def repair(self,_):raise AssertionError('Scope review must not spend a model call')
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'retained.san';path.write_text(code,encoding='utf-8')
        class Generate:
            def run(self,_):return GenerateStageResult(source_file=str(vue),ssm=ssm,generation_code=code,
                saved_file_path=str(path),provider='retained_frozen_artifact',model='none',usage={},raw_response={})
        state=MigrationPipelineOrchestrator(Generate(),ValidateStage(),VisualEvalStage(),RepairStage(NoModel())).run_generate_validate_visual_eval_and_repair_loop(
            GenerateStageInput(vue_file_path=str(vue),metadata={'repair_policy':'bounded_prepass_v1','semantic_rule_set':'residual_v2'}),max_repair_rounds=3).state
        actual=Path(state['final_file_path']).read_text(encoding='utf-8')
        if state['final_passed'] or state['llm_repair_calls'] or state['deterministic_steps'] or actual!=code:
            raise RuntimeError('Review boundary was rewritten, bypassed, or sent to a model')
        if state['stop_reason']!='source_parent_watch_scope_requires_review':
            raise RuntimeError('Missing explicit review stop reason')
        return {'input_kind':'retained_frozen_artifact_not_new_generation','final_passed':state['final_passed'],
            'stop_reason':state['stop_reason'],'review_codes':state['source_parent_watch_review_codes'],
            'llm_repair_calls':state['llm_repair_calls'],'deterministic_steps':state['deterministic_steps'],
            'code_unchanged':actual==code,'output_text_sha256':hashlib.sha256(actual.encode('utf-8')).hexdigest(),
            'temporary_harness_files_removed':True,'manual_or_browser_interaction':False}


def frozen_boundary_runtime(task):
    prior=json.loads((DIAGNOSTIC/'audit.json').read_text(encoding='utf-8'))
    paths=prior['inputs']
    for name,sha in paths.items():
        if digest(ROOT/name)!=sha:raise RuntimeError('Boundary input changed: '+name)
    vue_runtime=ROOT/next(p for p in paths if p.endswith('vue.runtime.common.dev.js'))
    san_runtime=ROOT/next(p for p in paths if p.endswith('san.dev.js'))
    payload={'code':(ROOT/task['input_path']).read_text(encoding='utf-8'),
        'vue':(ROOT/task['vue_path']).read_text(encoding='utf-8'),
        'vueRuntime':vue_runtime.read_bytes().decode('utf-8'),'sanRuntime':san_runtime.read_bytes().decode('utf-8')}
    proc=subprocess.run(['node',str(DIAGNOSTIC/'code/migration_pipeline/audit_formal_30_v4_parent_watch_boundaries_v1.cjs')],
        cwd=ROOT,input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True,check=True,timeout=40)
    if proc.stderr.strip():raise RuntimeError(proc.stderr)
    actual=json.loads(proc.stdout)
    if actual!=prior['observations']:raise RuntimeError('Retained boundary oracle observations changed')
    return {'unchanged':True,'runs':len(actual['runs']),'phase_snapshots':sum(len(r['phases']) for r in actual['runs']),
        'pairs':len(actual['pairs']),'exception_or_dynamic_key_semantics_fixed':False,
        'evidence_path':(DIAGNOSTIC/'audit.json').relative_to(ROOT).as_posix()}


def replay():
    verified={name:verify_snapshot(path.resolve()) for name,path in [('normal_flow_closure',BASE),('boundary_diagnostic',DIAGNOSTIC),('raw',RAW)]}
    previous=json.loads((BASE/'replay.json').read_text(encoding='utf-8'))
    raw_summary=json.loads((RAW/'formal_30_v4_full_regression_v2_summary.json').read_text(encoding='utf-8'))
    samples={sample['id']:sample for sample in raw_summary['samples']}
    rows=[]
    for prior in previous['retained_artifact_replays']:
        name=prior['id'];print('Offline scope check: '+name,flush=True)
        path=BASE/'TaskManager_parent_async_watch_offline.san' if name=='TaskManager' else ROOT/prior['input_path']
        code=path.read_text(encoding='utf-8');vue=ROOT/prior['vue_path'];source=vue.read_text(encoding='utf-8')
        current=source_parent_watch_semantics(code,source,repair=True)
        if current.get('error') or current['code']!=code or current['changes']:
            raise RuntimeError('Unexpected rewrite or analyzer failure: '+name)
        sample=samples[name]
        history=RAW/'repair_reports'/sample['complexity']/sample['report_file'].replace('\\','/').split('/')[-1]
        state=json.loads(history.read_text(encoding='utf-8'))['state']
        assessed=ValidateStage().run(ValidateStageInput(generated_code=code,ssm=state['ssm'],vue_file_path=str(vue))).to_state_update()
        gate_state={**assessed,'generated_code':code,'vue_file_path':str(vue),'ssm':state['ssm'],
            'visual_eval_passed':prior['after']['visual_eval_passed']}
        gate=candidate_gate(gate_state,gate_state)
        if gate['should_stop']:raise RuntimeError('Unchanged correctly reported candidate rejected: '+name)
        if prior['raw_original_automatic_passed'] and (code!=state['final_code'] or not assessed['validation_passed']):
            raise RuntimeError('Original passed raw artifact changed or now failed: '+name)
        if bool(current['blocked_boundaries'])!=(name=='TaskManager'):
            raise RuntimeError('Additional scope boundary needs review: '+name)
        row={'id':name,'raw_original_automatic_passed':prior['raw_original_automatic_passed'],
            'input_path':path.relative_to(ROOT).as_posix(),'input_sha256':digest(path),
            'vue_path':vue.relative_to(ROOT).as_posix(),'vue_sha256':digest(vue),
            'historical_normal_flow_validation_passed':prior['after']['validation_passed'],
            'current_validation':assessed,'visual_reexecuted':False,
            'prior_visual_eval_passed':prior['after']['visual_eval_passed'],'code_unchanged':True,
            **{k:current[k] for k in ['changes','proofs','reviews','mapped_contracts','blocked_boundaries']},'gate':gate}
        if name=='TaskManager':
            if {e['code'] for e in assessed['validation_errors']}!=PARENT_WATCH_REVIEW_CODES:
                raise RuntimeError('Both boundaries must remain unresolved')
            fake={**gate_state,'validation_errors':[],'validation_passed':True}
            rejected=candidate_gate(gate_state,fake)
            if not rejected['should_stop'] or len(rejected['waived_source_parent_watch_boundaries'])!=2:
                raise RuntimeError('Forged validation pass was not rejected')
            native=ROOT/prior['input_path'];native_code=native.read_text(encoding='utf-8')
            declined=source_parent_watch_semantics(native_code,source,repair=True)
            plan,steps=RepairStage._deterministic_repair_plan(native_code,declined['findings'],[],state['ssm'],str(vue),enable_residual_v2=True)
            if plan!=native_code or steps or declined['code']!=native_code:
                raise RuntimeError('Unsafe new queue/clone rewrite was not declined')
            row.update(forged_pass_gate=rejected,normal_candidate_scheduler=scheduler(code,vue,state['ssm']),
                pre_watch_candidate_scheduler=scheduler(native_code,vue,state['ssm']),
                blocked_new_queue_input_path=native.relative_to(ROOT).as_posix(),blocked_new_queue_input_sha256=digest(native),
                boundary_oracle=frozen_boundary_runtime(row))
        rows.append(row)
    if len(rows)!=30:raise RuntimeError('Expected all 30 retained artifacts')
    return {'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'conservative_scope_guard_not_exception_or_dynamic_key_semantic_repair',
        'source_verified_files':verified,'runtime_inventory_count':len(inventory()),'model_requests':0,
        'original_aggregate':previous['original_aggregate'],'original_score_modified':False,
        'original_passed_raw_artifacts_static_checked_unchanged':24,'canonical_san_or_manual_pages_modified':False,
        'full_browser_interaction_executed':False,'manual_acceptance_inherited':False,'initial_dom_reexecuted_ids':[],
        'exception_semantics_fixed':False,'dynamic_key_semantics_fixed':False,
        'preliminary_full_suite':{'run_tests':702,'failed':2,'elapsed_seconds':1237.042,
            'evidence_kind':'tool_output_summary_not_complete_raw_stdout',
            'failures':['test_semantic_regression_gate.SemanticRegressionGateTests.test_actual_loop_restores_previous_failed_candidate_and_keeps_rejected_evidence',
                        'test_source_child_initialization_closure.SourceChildInitializationClosureTests.test_actual_offline_scheduler_closes_startup_with_zero_model_calls'],
            'resolution':'Update earlier review-stop expectations and retain rollback coverage with a non-boundary synthetic component; do not relax production guards.'},
        'retained_artifact_replays':rows}


def report(data):
    t=data['unit_tests']
    return f'''# 父监听自动修复范围收紧 v1（2026-11-11）

本轮是拒绝未证明分支的安全闭环，不是修好了存储异常或任意键语义。原批次24/30、6失败、0执行异常、1,821,544 tokens保持不变；0模型请求，无新生成/独立测试/人工通过。canonical San和测试页均不改，保留旧正常流程证据、边界诊断与分数，不commit/push。

## 通用规则、验证器、候选保护和停止条件

source_parent_watch_semantics遍历源watch回调的传递调用链；访问localStorage时标记source_parent_watch_exception_policy_unproven。保守地包括已有try/catch，不假定它就是完整运行时错误适配器。独立扫描源methods对被监听初始对象的写入，未限定计算键、静态新增/继承/原型键、delete、解构写入均标记source_parent_watch_dynamic_key_unproven；不依赖目标方法先被正确识别，避免旧缺陷遮挡后才暴露。

有上述边界则不自动生成新队列或同值clone保护；已冻结正常队列可保持normal_flow_only的landed事实，但automatic_repair_eligible=false、两项诊断持续存在。纯非存储、已知静态属性形状的合成组仍可规范化并保持不动点；字段/方法改名、传递调用、先有其他语句、缺失目标方法等均有测试。不宣称证明JavaScript所有异常、任意对象形状、间接别名、动态反射或整个组件接口。

validate输出明确建议；共享repair Prompt禁止猜catch-and-continue、吞错误、删除未知键或强行让Vue2新增属性响应式。现有repair.py前/后处理通过调用该规则自动遵守拒绝条件，无需修改generation/服务器Prompt或legacy入口。bounded调度器保留可证明的其他规范化，遇两类诊断在LLM前停于source_parent_watch_scope_requires_review；保留候选、final_passed=false，0模型调用。候选门独立重算源边界：伪造通过/删诊断会因waived_source_parent_watch_boundaries被拒绝，不阻挡仍如实报告边界的无关进步。

## 验证结果

最终独立完整测试{t['passed']}/{t['passed']}、0失败/跳过、{t['elapsed_seconds']}秒；不拼接先前672与16项。387项运行清单中仅允许列出的生产/历史断言变化，新诊断装置原字节不变。

30个累计冻结产物均静态/编译检查，原24通过产物原字节仍静态通过，全部30均未改写。本轮不重做初始DOM，引用旧视觉结果不等于当前浏览器验收。TaskManager冻结正常路径产物由历史静态0错误变为现行2项边界错误，这是同一字节被更严格判定，不是新代码回归；原未补watch的产物也被拒绝自动扩展，两种输入的真实离线bounded调度器均0规范化步/0LLM、明确待复核。Trip外部渲染依赖风险继续保留。

原边界装置重新执行18次、180快照、90对，与冻结诊断完全相同；差异仍存在，证明本轮没有用改业务或吞异常“修成通过”。源Vue2.7.16/San3.15.6，模拟存储/应用timer，实际Promise队列，无浏览器/完整DOM attach，不继承人工通过。

开发检查的失败保留：新增目标方法缺失测试最初用紧凑空格串匹配格式化源码，未实际修改测试输入而失败；改为匹配真实方法声明后重新验证，非生产规则缺陷/部署回归。历史用例不删除旧错误断言，只补两项新边界；原组合修复成功断言改为保留三项未完成诊断，调度器用例改为验证0LLM安全停止，不能为保留旧“全通过”口径而放宽规则。

首次完整预检为702项、1237.042秒、2失败：旧子组件调度用例仍期待全通过，旧TaskManager回退用例期待先进入模型阶段。新策略已在更早的语义边界停止，因此这两个预期失效。最终补充真实非边界合成组件的候选回退用例，保留“原文件恢复、拒绝文件/历史保留”的全部断言；冻结TaskManager另验证0LLM停止，不通过屏蔽生产诊断恢复旧行为。生产规则未因这两项测试而放宽。首次失败完整stdout未落盘，以上计数/失败名来自工具输出，不伪称保存了完整原始日志；最终完整日志单独保存。

下一步在可证明的源/运行配置范围内实现键/属性形状与错误传播策略，再用同一冻结失败oracle验收；目前只完成“不会把未证明分支自动修成通过”的防线，尚不应付费复跑或宣布全语义修复完成。
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-evidence',action='store_true');args=parser.parse_args()
    if args.write_evidence and OUTPUT.exists():raise FileExistsError('Never overwrite frozen scope evidence')
    hashes=inventory();log=''
    if args.write_evidence:
        print('Running complete tests; no model calls.',flush=True)
        proc=subprocess.Popen([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py','-v'],cwd=ROOT,
            env={**os.environ,'PYTHONIOENCODING':'utf-8'},stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8')
        chunks=[];count=0
        for line in proc.stdout:
            chunks.append(line)
            if line.rstrip().endswith('... ok'):
                count+=1
                if count%25==0:print(f'Unit tests completed: {count}',flush=True)
            if line.startswith(('FAIL:','ERROR:')):print(line.strip(),flush=True)
        log=''.join(chunks)
        if proc.wait():
            failed=OUTPUT.parent/(OUTPUT.name+'_failed_tests_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.txt')
            with failed.open('x',encoding='utf-8') as stream:stream.write(log)
            raise RuntimeError('Full tests failed; complete log preserved at '+str(failed)+'\n'+log[-12000:])
    data=replay()
    if inventory()!=hashes:raise RuntimeError('Runtime changed during verification')
    if args.write_evidence:
        match=re.search(r'Ran (\d+) tests in ([\d.]+)s',log)
        if not match or '\nOK' not in log or re.search(r'OK\s*\(skipped=',log):raise RuntimeError('Missing complete test success')
        data['unit_tests']={'passed':int(match[1]),'failed':0,'elapsed_seconds':float(match[2])}
        OUTPUT.mkdir(parents=True)
        for name in sorted(CHANGED|ADDED):
            dest=OUTPUT/'code'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
        for name,value in [('replay.json',data),('live_inventory.json',hashes)]:
            (OUTPUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (OUTPUT/'REPORT.md').write_text(report(data),encoding='utf-8');(OUTPUT/'unit_tests.txt').write_text(log,encoding='utf-8')
        files=sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        (OUTPUT/'SHA256SUMS.txt').write_text('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files)+'\n',encoding='utf-8')
        verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'evidence_written':args.write_evidence,'model_requests':0,'original_passed':24,
        'semantic_boundaries_fixed':False,'scope_guard_and_review_stop_verified':True,'tests':data.get('unit_tests')}))


if __name__=='__main__':main()
