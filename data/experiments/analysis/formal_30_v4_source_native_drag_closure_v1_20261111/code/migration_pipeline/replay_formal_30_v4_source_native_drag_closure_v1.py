"""Frozen source-proven native drag closure; no LLM, browser or canonical writes."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone, timedelta

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot
from migration_pipeline.replay_formal_30_v4_source_child_initialization_closure_v1 import OUTPUT as BASE, SOURCE, PROTOCOL, BATCH, startup_runtime
from migration_pipeline.replay_formal_30_v4_source_array_transaction_closure_v1 import offline_scheduler
from migration_pipeline.utils.source_native_drag_semantics import source_native_drag_semantics
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.utils.repair_scheduler import candidate_gate

AUDIT = ROOT/'data/experiments/analysis/formal_30_v4_parent_lifecycle_drag_audit_v1_final_20261111'
OUTPUT = ROOT/'data/experiments/analysis/formal_30_v4_source_native_drag_closure_v1_20261111'
CHANGED = {'migration_pipeline/stages/repair.py', 'migration_pipeline/stages/validate.py',
 'migration_pipeline/utils/repair_prompt.py', 'migration_pipeline/utils/repair_scheduler.py',
 'tests/test_source_child_initialization_closure.py', 'tests/test_source_array_transaction_closure.py',
 'tests/test_source_render_dependency_closure.py', 'tests/test_source_dom_closure.py',
 'tests/test_source_payload_closure.py', 'tests/test_source_render_call_closure.py',
 'tests/test_source_inline_formatter_closure.py', 'tests/test_repair_regression_guard.py',
 'tests/test_monitoring_remaining_bounded_fix.py'}
ADDED = {'migration_pipeline/utils/source_native_drag_semantics.py',
 'migration_pipeline/utils/source_native_drag_semantics.cjs', 'tests/test_source_native_drag_closure.py',
 'migration_pipeline/replay_formal_30_v4_source_native_drag_closure_v1.py',
 'migration_pipeline/audit_formal_30_v4_task_manager_lifecycle_drag_v1.py',
 'migration_pipeline/audit_formal_30_v4_task_manager_lifecycle_drag_v1.cjs',
 'tests/test_task_manager_lifecycle_drag_audit.py'}


def inventory():
    verify_snapshot(BASE.resolve())
    previous = json.loads((BASE/'live_inventory.json').read_text(encoding='utf-8'))
    now = {name:digest(ROOT/name) for name in sorted(set(previous)|ADDED)}
    changed = {name for name, sha in previous.items() if now[name] != sha}
    if changed != CHANGED:
        raise RuntimeError('Unexpected runtime delta: '+str(changed ^ CHANGED))
    return now


def native_runtime(code, vue):
    path = AUDIT/'code/migration_pipeline/audit_formal_30_v4_task_manager_lifecycle_drag_v1.cjs'
    proc = subprocess.run(['node', str(path)], cwd=ROOT, input=json.dumps({'code':code,'vue':vue}),
        capture_output=True, text=True, encoding='utf-8', check=True, timeout=30)
    if proc.stderr.strip():
        raise RuntimeError('Unexpected runtime warning/error: '+proc.stderr)
    data = json.loads(proc.stdout)
    data.pop('loadedModuleSha256')
    return data


def replay():
    verified = {name:verify_snapshot(path.resolve()) for name,path in
        [('raw',SOURCE),('protocol',PROTOCOL),('child_initialization',BASE),('parent_drag_audit',AUDIT)]}
    previous = {r['id']:r for r in json.loads((BASE/'replay.json').read_text(encoding='utf-8'))['retained_artifact_replays']}
    raw = json.loads((SOURCE/f'{BATCH}_summary.json').read_text(encoding='utf-8'))
    if len(previous)!=30 or len(raw['samples'])!=30:
        raise RuntimeError('Expected full-30 frozen inputs')
    rows, artifacts = [], {}
    for sample in raw['samples']:
        name = sample['id']; print('Offline static check: '+name, flush=True); prior = previous[name]
        path = BASE/'TaskManager_source_child_initialization_offline.san' if name=='TaskManager' else ROOT/prior['input_path']
        code = path.read_text(encoding='utf-8'); vue = ROOT/prior['vue_path']; source = vue.read_text(encoding='utf-8')
        history = SOURCE/'repair_reports'/sample['complexity']/sample['report_file'].replace('\\','/').split('/')[-1]
        state = json.loads(history.read_text(encoding='utf-8'))['state']
        result = source_native_drag_semantics(code, source, repair=True)
        if result.get('error'):
            raise RuntimeError('AST error '+name+': '+result['error'])
        fixed = result['code']
        def assess(text, visual=None):
            value = ValidateStage().run(ValidateStageInput(generated_code=text,ssm=state['ssm'],vue_file_path=str(vue))).to_state_update()
            value.update(generated_code=text,ssm=state['ssm'],vue_file_path=str(vue))
            if visual is None:
                vis = VisualEvalStage().run(VisualEvalStageInput(generated_code=text,vue_file_path=str(vue)))
                value.update(visual_eval_passed=vis.visual_eval_passed,visual_errors=vis.visual_eval_errors,
                    structure_similarity=vis.structure_similarity,visual_reexecuted=True)
            else:
                value.update(visual_eval_passed=visual,visual_reexecuted=False)
            return value
        before = assess(code,prior['after']['visual_eval_passed']); after = assess(fixed) if fixed!=code else before
        findings = [e for e in before['validation_errors'] if e['code'].startswith('source_native_drag_')]
        if len(findings)!=(1 if name=='TaskManager' else 0):
            raise RuntimeError('Unexpected native drag finding: '+name)
        gate = candidate_gate(before,after)
        if gate['should_stop']:
            raise RuntimeError('Candidate rejected: '+name)
        again = source_native_drag_semantics(fixed,source,repair=True)
        if again.get('error') or again['code']!=fixed or again['changes']:
            raise RuntimeError('Not a fixed point: '+name)
        if name!='TaskManager' and fixed!=code:
            raise RuntimeError('Additional rewrite needs review: '+name)
        if sample['final_passed'] and (fixed!=state['final_code'] or not after['validation_passed']):
            raise RuntimeError('Original passed raw artifact changed or now fails: '+name)
        compact = lambda d:{k:v for k,v in d.items() if k not in {'generated_code','ssm','validate_result'}}
        row = {'id':name,'raw_original_automatic_passed':sample['final_passed'],
            'input_path':path.relative_to(ROOT).as_posix(),'input_sha256':digest(path),
            'vue_path':vue.relative_to(ROOT).as_posix(),'vue_sha256':digest(vue),
            'before':compact(before),'after':compact(after),'changes':result['changes'],'proofs':result['proofs'],
            'reviews':result['reviews'],'mapped_contracts':result['mapped_contracts'],'gate':gate}
        if name=='TaskManager':
            if {e['code'] for e in before['validation_errors']}!={'source_native_drag_not_landed'} or not after['validation_passed']:
                raise RuntimeError('Unexpected TaskManager static result')
            planned, steps = RepairStage._deterministic_repair_plan(code,before['validation_errors'],[],state['ssm'],str(vue),enable_residual_v2=True)
            if planned!=fixed:
                raise RuntimeError('Prepass differs from independent rule')
            reverse = candidate_gate(after,before)
            if not reverse['should_stop']:
                raise RuntimeError('Native event regression not rejected')
            runtime_before, runtime_after = native_runtime(code,source), native_runtime(fixed,source)
            saved = json.loads((AUDIT/'audit.json').read_text(encoding='utf-8'))['observations']; saved.pop('loadedModuleSha256')
            if runtime_before!=saved:
                raise RuntimeError('Frozen diagnostic observation changed')
            if runtime_before['lifecycle']!=runtime_after['lifecycle'] or runtime_before['watcher']!=runtime_after['watcher']:
                raise RuntimeError('Do not change watcher/lifecycle behavior in native event repair')
            for original, current in zip(runtime_before['drag'],runtime_after['drag']):
                for field in ['order','sourceExpectedOrder','startIndex','finalDragIndex','notes','bubblePrevented',
                              'oldArrayUnchanged','elementIdentitiesPreserved']:
                    if original[field]!=current[field]:raise RuntimeError('Drag chain regression: '+field)
                expected = [] if current['operation']=='disabled' else [{'kind':'setData','args':['text/plain',current['startIndex']]}]
                if [c for c in current['calls'] if c['kind']=='setData']!=expected:
                    raise RuntimeError('Source dataTransfer payload not restored')
                if current['dataTransferEffectAllowed']!=(None if current['operation']=='disabled' else 'move'):
                    raise RuntimeError('Source effectAllowed not restored')
            startup = startup_runtime(fixed,source)
            if startup!=prior['startup_runtime_after']:
                raise RuntimeError('Factory/root watcher closure regression')
            row.update(prepass_steps=steps,reverse_gate=reverse,landed_native_proofs=again['proofs'],
                native_runtime_before=runtime_before,native_runtime_after=runtime_after,
                child_startup_runtime_after=startup,offline_scheduler=offline_scheduler(code,vue,state['ssm'],fixed))
            artifacts['TaskManager_source_native_drag_offline.san'] = fixed
        if name=='trip_itinerary_planner' and (fixed!=code or after['validation_passed'] or not any(
                e['code']=='source_render_dependency_not_landed' for e in after['validation_errors'])):
            raise RuntimeError('Do not waive previously unproven external render dependency')
        rows.append(row)
    return artifacts, {'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'offline_source_native_drag_closure_reused_development_not_new_batch',
        'source_verified_files':verified,'original_aggregate':raw['aggregate'],'model_requests':0,
        'original_score_modified':False,'canonical_san_or_manual_pages_modified':False,
        'manual_acceptance_inherited':False,'full_browser_interaction_executed':False,
        'runtime_inventory_count':len(inventory()),'original_passed_raw_artifacts_static_checked_unchanged':24,
        'initial_dom_reexecuted_ids':['TaskManager'],'retained_prior_derivative_risk_ids':['trip_itinerary_planner'],
        'parent_watch_timing_fixed':False,'retained_artifact_replays':rows,
        'development_test_attempts':[{'tests':16,'errors':1,'elapsed_seconds':55.826,
            'cause':'New test used generated_code instead of RepairPromptInput.current_code; harness corrected, production rule unchanged.'},
            {'tests':16,'errors':0,'elapsed_seconds':51.475}],
        'historical_startup_targeted_tests': {'passed':20,'elapsed_seconds':90.098},
        'historical_audit_notebook_live_hash_assertion': 'Old audit code cell intentionally checks its 363 live runtime identities and now flags expected code drift. Historical cells are retained; new evidence checks snapshots, not unchanged production forever.'}


def report(data):
    tests = data['unit_tests']
    return f'''# 有界原生拖拽方法体闭环 v1（2026-11-11）

本轮不是整批重生成或独立测试。原始成绩仍 24/30、6 失败、0 执行异常、1,821,544 tokens；模型请求 0；不改 canonical San、人工页、旧冻结结果，不 commit/push。

新增 source_native_drag_semantics.py/.cjs：按真实父注册映射唯一不逃逸的内联子组件，不用 TaskManager/方法/字段名特判。完整源 AST 必须证明：单一原生 dragstart 绑定、单事件参数、声明字段的禁用守卫、dataTransfer.setData 字符串格式与字段值、effectAllowed 字符串、单 payload emit 及源顺序。目标仅允许同源 guard/emit 与两条 transfer 操作的有序子集，可消去纯 const 字段别名；未知副作用、错误 MIME/值/guard/payload/次序、重复或非原生绑定、其他调用、动态 this 引用、构造器逃逸/mixins/框架替换均拒绝。源本身不在闭合形态内不发明修复。只替换通过证明的目标方法，保留其余字节。

residual_v2 修复前处理与返回后处理、共享 repair Prompt、Validate、候选保护同步；新增 source_native_drag_not_landed / source_native_drag_analysis_unavailable，补 lost_source_native_drag_contracts。generation/服务器 Prompt、legacy 前处理、父 watch/生命周期均不改。模型遵从 Prompt 效果未测，不把文字约束当修复证据。

新规则初次16项因测试误用 RepairPromptInput 参数失败1项（55.826秒），改正测试参数后16/16（51.475秒）；不隐藏失败，不归为组件回归。历史用例保留旧错误并增加新检测及组合预处理期望，不删旧断言、不篡改冻结原分数。最终独立完整套件 {tests['passed']}/{tests['passed']}、0失败、0跳过，{tests['elapsed_seconds']} 秒，日志 unit_tests.txt，非拼接散测。

累计30个冻结件重做静态/编译，仅 TaskManager 改写，原24个通过件字节未变且仍静态通过。当前 TaskManager 1→0 原生副作用错误，migration_hints_not_landed 警告保留；只重跑它的轻量初始 DOM。真实调度器注入冻结代码、禁止模型：1个确定性步骤、0 LLM、当前自动门通过；不是新批次或全交互验收。

用上轮冻结的San bundle合成事件装置复跑前后：6个拖拽场景保留排序、索引、drop.stop、dragover.prevent、元素身份；恢复 setData(text/plain,index) 与 effectAllowed=move，禁用时均不发生。新测试还记录 transfer→effectAllowed→emit 顺序。此前子工厂/首次props/根监听运行观察完全一致；父生命周期4存储分支与watch观察前后完全一致，父监听时机风险仍存在，不虚报已修复。无浏览器attach/原生手势、无真实存储/应用定时器；San3.15.6不是人工页3.15.3的验证。TripItineraryPlanner 外部渲染依赖仍未证明，不豁免。

运行清单 {data['runtime_inventory_count']} 项；SHA覆盖代码、派生件、回放、测试日志、报告。上轮诊断Notebook代码含当时363项实时哈希断言，生产规则更新后该断言应提示漂移；保留历史40个单元，不改写为“旧版本从未失败”。新增单元校验冻结身份与新派生运行事实，不声称旧实时哈希断言仍全绿。下一步应单独建立源Vue异步watch/恢复存储/计时器顺序oracle后处理父监听，暂不付费复跑或准备独立测试。
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-evidence',action='store_true');args=parser.parse_args()
    if args.write_evidence and OUTPUT.exists():raise FileExistsError('Never overwrite frozen evidence')
    hashes=inventory();log=''
    if args.write_evidence:
        print('Running complete tests, no model requests.',flush=True)
        proc=subprocess.Popen([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py','-v'],cwd=ROOT,
            env={**os.environ,'PYTHONIOENCODING':'utf-8'},stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8')
        chunks=[];completed=0
        for line in proc.stdout:
            chunks.append(line)
            if line.rstrip().endswith('... ok'):
                completed+=1
                if completed%25==0:print(f'Unit tests completed: {completed}',flush=True)
            if line.startswith(('FAIL:', 'ERROR:')):print(line.strip(),flush=True)
        log=''.join(chunks)
        if proc.wait():raise RuntimeError('Full tests failed:\n'+log)
    artifacts,data=replay()
    if inventory()!=hashes:raise RuntimeError('Runtime changed during verification')
    if args.write_evidence:
        match=re.search(r'Ran (\d+) tests in ([\d.]+)s',log)
        if not match or '\nOK' not in log or re.search(r'OK\s*\(skipped=',log):raise RuntimeError('Missing complete non-skipped test success')
        data['unit_tests']={'passed':int(match[1]),'failed':0,'elapsed_seconds':float(match[2])}
        OUTPUT.mkdir(parents=True)
        for name in sorted(CHANGED|ADDED):
            path=OUTPUT/'code'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,path)
        for name,code in artifacts.items():(OUTPUT/name).write_text(code,encoding='utf-8')
        data['derived_artifact_sha256']={name:digest(OUTPUT/name) for name in artifacts}
        for name,value in [('replay.json',data),('live_inventory.json',hashes)]:
            (OUTPUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (OUTPUT/'REPORT.md').write_text(report(data),encoding='utf-8');(OUTPUT/'unit_tests.txt').write_text(log,encoding='utf-8')
        files=sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        (OUTPUT/'SHA256SUMS.txt').write_text('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files)+'\n',encoding='utf-8')
        verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'model_requests':0,'original_passed':24,'target':'TaskManager',
        'current_before_findings':1,'current_after_findings':0,'parent_watch_timing_fixed':False,
        'unit_tests':data.get('unit_tests'),'evidence_written':args.write_evidence}))


if __name__=='__main__':main()
