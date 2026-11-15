"""Freeze bounded parent-prop repairs on immutable artifacts; never request a model."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot
from migration_pipeline.replay_formal_30_v4_evaluator_calibration_v1 import SOURCE, PROTOCOL, OUTPUT as BASE
from migration_pipeline.utils.parent_prop_semantics import parent_prop_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.generate import GenerateStageInput
from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.replay_formal_30_v4_repair_scheduling import ReplayGenerate

BATCH = 'formal_30_v4_full_regression_v2'
OUTPUT = ROOT / 'data/experiments/analysis/formal_30_v4_parent_props_closure_v1_20261104'
CHANGED = {'migration_pipeline/stages/validate.py', 'migration_pipeline/stages/repair.py',
           'migration_pipeline/utils/repair_prompt.py'}
ADDED = {'migration_pipeline/utils/parent_prop_semantics.py', 'migration_pipeline/utils/parent_prop_semantics.cjs',
         'migration_pipeline/replay_formal_30_v4_parent_props_closure_v1.py', 'tests/test_parent_prop_contract_closure.py'}


class NoModel:
    def repair(self, request):
        raise AssertionError('Offline closure must not request a model')


def inventory():
    verify_snapshot(BASE.resolve())
    prior = json.loads((BASE / 'live_inventory.json').read_text(encoding='utf-8'))
    if len(prior) != 328:
        raise RuntimeError('Expected the frozen calibration inventory')
    current = {name: digest(ROOT / name) for name in sorted(set(prior) | ADDED)}
    changed = {name for name, sha in prior.items() if sha != current[name]}
    if changed != CHANGED:
        raise RuntimeError(f'Unexpected runtime changes: {changed ^ CHANGED}')
    return current


def replay():
    verified = {'raw': verify_snapshot(SOURCE.resolve()), 'protocol': verify_snapshot(PROTOCOL.resolve()),
                'calibration': verify_snapshot(BASE.resolve())}
    summary = json.loads((SOURCE / f'{BATCH}_summary.json').read_text(encoding='utf-8'))
    config = json.loads((SOURCE / f'{BATCH}.json').read_text(encoding='utf-8'))
    if len(config['samples']) != 30 or [s['id'] for s in summary['samples']] != [s['id'] for s in config['samples']]:
        raise RuntimeError('Frozen full-30 order mismatch')
    rows, candidates, artifacts = [], [], {}
    def assess(code, state, vue, *, visual, frozen_visual=False):
        result = ValidateStage().run(ValidateStageInput(generated_code=code, ssm=state['ssm'],
            vue_file_path=str(vue), compile_check=True)).to_state_update()
        if visual is None:
            vis = VisualEvalStage().run(VisualEvalStageInput(generated_code=code, vue_file_path=str(vue)))
            result['visual_eval_passed'] = vis.visual_eval_passed
            result['visual_errors'] = vis.visual_eval_errors
            result['structure_similarity'] = vis.structure_similarity
        else:
            result['visual_eval_passed'] = visual
        result.update({'generated_code':code, 'ssm':state['ssm'], 'vue_file_path':str(vue),
                       'visual_reexecuted': not frozen_visual})
        return result
    compact = lambda state: {k: v for k,v in state.items() if k not in {'ssm', 'generated_code', 'validate_result'}}
    habit_state = habit_vue = None
    for plan, sample in zip(config['samples'], summary['samples']):
        print(f"Checking {sample['id']} (offline)", flush=True)
        state = json.loads((SOURCE / 'repair_reports' / sample['complexity'] / Path(sample['report_file']).name).read_text(encoding='utf-8'))['state']
        vue = SOURCE / 'protocol/frozen' / plan['vue_file']
        original = state['final_code']
        path = SOURCE / 'pipeline' / sample['complexity'] / Path(sample['final_file_path']).name
        if path.read_text(encoding='utf-8') != original:
            raise RuntimeError('Frozen final code mismatch')
        result = parent_prop_semantics(original, vue.read_text(encoding='utf-8'), repair=True)
        if 'error' in result:
            raise RuntimeError(f"Unexpected AST failure on {sample['id']}: {result['error']}")
        fixed = result['code']
        before = assess(original, state, vue, visual=state['final_visual_eval_result']['visual_eval_passed'], frozen_visual=True)
        after = assess(fixed, state, vue, visual=None) if fixed != original or not sample['final_passed'] else before
        if sample['final_passed'] and (fixed != original or not after['validation_passed']):
            raise RuntimeError('A previously passed final changed or gained validation errors')
        gate = candidate_gate(before, after)
        if fixed != original and gate['should_stop']:
            raise RuntimeError(f"Parent-prop rewrite introduced a regression: {sample['id']}")
        second = parent_prop_semantics(fixed, vue.read_text(encoding='utf-8'), repair=True)
        if second['code'] != fixed or second['changes']:
            raise RuntimeError('Parent-prop rewrite is not a fixed point')
        if fixed != original:
            artifacts[f"retained_{sample['id']}_parent_props_offline.san"] = fixed
        rows.append({'id':sample['id'], 'original_automatic_passed':sample['final_passed'], 'source_sha256':digest(path),
            'vue_sha256':digest(vue), 'source_contracts':result.get('contracts', []),
            'source_contract_review_reason':result.get('schema_review_reason') or result.get('reason'),
            'changes':result['changes'], 'before':compact(before), 'after':compact(after), 'gate':gate, 'fixed_point':True,
            'offline_static_and_visual_passed':bool(after['validation_passed'] and after['visual_eval_passed'])})
        if sample['id'] == 'habit_week_tracker':
            habit_state, habit_vue = state, vue
        if not sample['retained_previous_candidate']:
            continue
        rejected = SOURCE / 'pipeline' / sample['complexity'] / Path(state['rejected_candidate_file']).name
        candidate = rejected.read_text(encoding='utf-8')
        if candidate != state['repair_history'][-1]['repair_result']['repaired_code']:
            raise RuntimeError('Rejected candidate bytes differ')
        repair = parent_prop_semantics(candidate, vue.read_text(encoding='utf-8'), repair=True)
        old = assess(candidate, state, vue, visual=state['repair_history'][-1]['visual_eval_passed'], frozen_visual=True)
        new = assess(repair['code'], state, vue, visual=None)
        local_gate = candidate_gate(old, new)
        if repair['code'] != candidate:
            artifacts[f"rejected_{sample['id']}_parent_props_offline.san"] = repair['code']
        candidates.append({'id':sample['id'], 'source_sha256':digest(rejected), 'changes':repair['changes'],
            'before':compact(old), 'after':compact(new), 'local_rewrite_gate':local_gate,
            'versus_retained_gate':candidate_gate(before,new),
            'offline_static_and_visual_passed':bool(new['validation_passed'] and new['visual_eval_passed']),
            'canonical_candidate_replaced':False, 'model_continuation_simulated':False})
    monitor = next(r for r in rows if r['id']=='MonitoringDashboard')
    if [e['code'] for e in monitor['after']['validation_errors']] != ['source_watch_persistence_unproven']:
        raise RuntimeError('Persistence uncertainty was lost')
    rule = next(r for r in candidates if r['id']=='rule_builder')
    if not rule['offline_static_and_visual_passed'] or rule['local_rewrite_gate']['should_stop']:
        raise RuntimeError('Source-literal default closure failed on the RuleBuilder candidate')
    # Exercise the real scheduler, not a hand-assembled successful state.
    with tempfile.TemporaryDirectory() as tmp:
        generate = ReplayGenerate(habit_state, habit_state['final_code'], Path(tmp)/'before.san')
        runner = MigrationPipelineOrchestrator(generate, ValidateStage(), VisualEvalStage(), RepairStage(NoModel()))
        real = runner.run_generate_validate_visual_eval_and_repair_loop(GenerateStageInput(vue_file_path=str(habit_vue),
            metadata={'repair_policy':'bounded_prepass_v1','semantic_rule_set':'residual_v2'}),max_repair_rounds=3).state
        if not real['final_passed'] or real['llm_repair_calls'] or real['deterministic_steps'] != 1:
            raise RuntimeError('Actual scheduler failed to close HabitWeekTracker without a model')
        scheduler = {k:real[k] for k in ('final_passed','llm_repair_calls','deterministic_steps','normalization_history')}
    verify_snapshot(SOURCE.resolve())
    return artifacts, {'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'offline_source_parent_prop_closure_on_reused_development_not_fresh_batch',
        'source_verified_files':verified, 'source_snapshot':SOURCE.relative_to(ROOT).as_posix(),
        'original_aggregate':summary['aggregate'], 'model_requests':0, 'original_score_modified':False,
        'canonical_artifacts_modified':False, 'manual_or_browser_interaction_pass_claimed':False,
        'prior_passed_artifacts_checked_unchanged':sum(r['original_automatic_passed'] for r in rows),
        'fresh_model_batch_pass_rate_inferred':False, 'exception_policy_changed':False,
        'earlier_full_test_observation':{'tests_run':448,'failures':1,'elapsed_seconds':372.979,
            'failed_test':'test_computed_method_call_only_uses_focused_repair_prompt',
            'cause':'New parent-default focused routing discarded full SSM without complete source evidence',
            'fix':'Require complete parent prop contracts for newly focused families; otherwise retain generic full context',
            'evidence_kind':'summary_of_captured_console_not_a_preserved_complete_raw_test_log'},
        'retained_artifact_replays':rows, 'rejected_candidate_replays':candidates, 'actual_scheduler':scheduler}


def report(data):
    changed = [r['id'] for r in data['retained_artifact_replays'] if r['changes']]
    return f'''# 父组件 props 通用修复 v1（离线证据）

原始批次仍为 24/30，6 失败、0 执行异常；本报告不是新模型批次，不回填分数。

- 根据完整 Vue AST 添加缺失的父组件 dataTypes 和静态字面量默认值，仅在 residual_v2 修复前处理及模型返回后处理启用。
- 默认值工厂仅允许无参、无副作用的字面量返回；initData 支持直接返回对象及此前只有字面量常量/已证明字面量返回助手的形式。不覆盖已有值或验证器，不处理任意闭包、自定义/联合类型或不明确选项。
- statics/props/propTypes 等替代声明位置、外置类声明及命名空间改写不自动覆盖；source_contract_review_reason 会单独记录。排除自动修复不代表这些契约已经正确或已被完整验证。
- 修正注释/字符串造成的 methods 包装误报，真实父/子包装仍检测；AST 失败或不明确组件选项不获得豁免。
- 完整测试：{data['unit_tests']['passed']}/{data['unit_tests']['passed']}，{data['unit_tests']['elapsed_seconds']} 秒。
- 首次完整测试 448 项、1 失败（372.979 秒）：缺少完整 Vue 证据时，新聚焦路由丢失完整 SSM。现已收紧为有完整父 props 契约才启用新增聚焦族，否则保留完整上下文；旧测试不放宽，并新增反例。此条是控制台观察摘要，不冒充完整原始日志。
- 30 个保留产物均重新静态验证/编译，原来通过的 24 项不改字节且仍通过。实际修改的保留件：{', '.join(changed)}。
- 6 个原失败保留件、5 个旧回退候选单独执行离线 DOM/视觉评估；24 个未变通过件仅引用冻结视觉标志，不伪称完整新视觉回归。
- HabitWeekTracker 通过实际调度器，以 0 次模型调用、1 次确定性步骤闭合。RuleBuilder 的旧回退候选补齐默认值后通过离线静态和视觉检查，不等于本批保留件已通过。
- StockReservationBadge 的注释不再误报；视觉残留、TaskManager 复杂交互、TripItineraryPlanner 其余语义残留继续按 replay.json 记录。MonitoringDashboard 的持久化异常行为仍为 unproven/error。

完整数据见 replay.json；代码与测试见 code/，校验和见 SHA256SUMS.txt。派生产物仅存本离线证据目录，不覆盖 canonical San 或测试页面。
下一步应继续对真实残留做有边界修复及离线反例验证，再决定新运行协议；不能据本次离线结果宣布全批通过或独立测试通过。
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-evidence', action='store_true')
    args = parser.parse_args()
    if args.write_evidence and OUTPUT.exists():
        raise FileExistsError('Never replace frozen closure evidence')
    hashes = inventory()
    tests = ''
    if args.write_evidence:
        print('Running complete tests; no model requests.', flush=True)
        p = subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'],cwd=ROOT,
            env={**os.environ,'PYTHONIOENCODING':'utf-8'},text=True,encoding='utf-8',capture_output=True)
        tests = p.stdout+p.stderr
        if p.returncode:
            raise RuntimeError('Complete tests failed:\n'+tests)
    artifacts, data = replay()
    if inventory() != hashes:
        raise RuntimeError('Runtime changed during verification')
    if args.write_evidence:
        match = re.search(r'Ran (\d+) tests in ([\d.]+)s',tests)
        if not match or '\nOK' not in tests:
            raise RuntimeError('Full test success/count missing')
        data['unit_tests'] = {'passed':int(match[1]),'failed':0,'elapsed_seconds':float(match[2])}
        OUTPUT.mkdir(parents=True)
        for name in sorted(CHANGED|ADDED):
            target = OUTPUT/'code'/name; target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/name,target)
        for name,code in artifacts.items():
            (OUTPUT/name).write_text(code,encoding='utf-8')
        data['derived_artifact_sha256'] = {name:digest(OUTPUT/name) for name in artifacts}
        for name,value in (('replay.json',data),('live_inventory.json',hashes)):
            (OUTPUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (OUTPUT/'unit_tests.txt').write_text(tests,encoding='utf-8')
        (OUTPUT/'REPORT.md').write_text(report(data),encoding='utf-8')
        files = sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        (OUTPUT/'SHA256SUMS.txt').write_text('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files)+'\n',encoding='utf-8')
        verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'model_requests':0,'original_passed':data['original_aggregate']['passed'],
        'changed_retained_ids':[r['id'] for r in data['retained_artifact_replays'] if r['changes']],
        'scheduler':{k:v for k,v in data['actual_scheduler'].items() if k!='normalization_history'},
        'unit_tests':data.get('unit_tests'),'evidence_written':args.write_evidence}))


if __name__ == '__main__':
    main()
