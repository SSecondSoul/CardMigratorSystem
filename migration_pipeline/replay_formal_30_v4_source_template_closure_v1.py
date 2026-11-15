"""Source-template closure on frozen development artifacts; no models or canonical writes."""
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

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT,digest,verify_snapshot
from migration_pipeline.replay_formal_30_v4_parent_props_closure_v1 import OUTPUT as BASE,SOURCE,PROTOCOL,NoModel
from migration_pipeline.utils.source_template_semantics import source_template_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.stages.validate import ValidateStage,ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage,VisualEvalStageInput
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.generate import GenerateStageInput
from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.replay_formal_30_v4_repair_scheduling import ReplayGenerate

BATCH='formal_30_v4_full_regression_v2'
OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_source_template_closure_v1_20261110'
CHANGED={'migration_pipeline/stages/validate.py','migration_pipeline/stages/repair.py',
    'migration_pipeline/utils/repair_prompt.py','migration_pipeline/utils/repair_scheduler.py',
    'tests/test_parent_prop_contract_closure.py'}
ADDED={'migration_pipeline/utils/source_template_semantics.py','migration_pipeline/utils/source_template_semantics.cjs',
    'tests/test_source_template_closure.py','migration_pipeline/replay_formal_30_v4_source_template_closure_v1.py'}
TARGETS={'stock_reservation_badge','rule_builder'}


def inventory():
    verify_snapshot(BASE.resolve())
    prior=json.loads((BASE/'live_inventory.json').read_text(encoding='utf-8'))
    if len(prior)!=332:raise RuntimeError('Expected parent-prop closure inventory')
    current={name:digest(ROOT/name) for name in sorted(set(prior)|ADDED)}
    changed={name for name,sha in prior.items() if current[name]!=sha}
    if changed!=CHANGED:raise RuntimeError(f'Unexpected runtime changes: {changed^CHANGED}')
    return current


def replay():
    verified={'raw':verify_snapshot(SOURCE.resolve()),'protocol':verify_snapshot(PROTOCOL.resolve()),
              'prior_parent_prop_closure':verify_snapshot(BASE.resolve())}
    raw=json.loads((SOURCE/f'{BATCH}_summary.json').read_text(encoding='utf-8'))
    config=json.loads((SOURCE/f'{BATCH}.json').read_text(encoding='utf-8'))
    prior=json.loads((BASE/'replay.json').read_text(encoding='utf-8'))
    old={r['id']:r for r in prior['retained_artifact_replays']}
    if len(raw['samples'])!=30 or [s['id'] for s in raw['samples']]!=[s['id'] for s in config['samples']]:
        raise RuntimeError('Frozen full-30 order mismatch')
    rows,artifacts,schedulers=[],{},{}
    for plan,sample in zip(config['samples'],raw['samples']):
        print(f"Checking {sample['id']} (offline)",flush=True)
        state=json.loads((SOURCE/'repair_reports'/sample['complexity']/Path(sample['report_file']).name).read_text(encoding='utf-8'))['state']
        original=SOURCE/'pipeline'/sample['complexity']/Path(sample['final_file_path']).name
        if original.read_text(encoding='utf-8')!=state['final_code']:raise RuntimeError('Raw bytes differ from history')
        previous_name=f"retained_{sample['id']}_parent_props_offline.san"
        start=BASE/previous_name if previous_name in prior['derived_artifact_sha256'] else original
        code=start.read_text(encoding='utf-8')
        vue=SOURCE/'protocol/frozen'/plan['vue_file']
        result=source_template_semantics(code,vue.read_text(encoding='utf-8'),repair=True)
        if result.get('error'):raise RuntimeError(f"AST error: {sample['id']}: {result['error']}")
        fixed=result['code']
        def assess(text,visual):
            val=ValidateStage().run(ValidateStageInput(generated_code=text,ssm=state['ssm'],vue_file_path=str(vue))).to_state_update()
            output={'generated_code':text,'ssm':state['ssm'],'vue_file_path':str(vue),**val}
            if visual is None:
                vis=VisualEvalStage().run(VisualEvalStageInput(generated_code=text,vue_file_path=str(vue)))
                output.update({'visual_eval_passed':vis.visual_eval_passed,'visual_errors':vis.visual_eval_errors,
                    'structure_similarity':vis.structure_similarity,'visual_reexecuted':True})
            else:output.update({'visual_eval_passed':visual,'visual_reexecuted':False})
            return output
        before=assess(code,old[sample['id']]['after']['visual_eval_passed'])
        after=assess(fixed,None) if fixed!=code else before
        gate=candidate_gate(before,after)
        if gate['should_stop']:raise RuntimeError('New template rule introduced a regression')
        repeated=source_template_semantics(fixed,vue.read_text(encoding='utf-8'),repair=True)
        if repeated['code']!=fixed or repeated['changes']:raise RuntimeError('Not a fixed point')
        if sample['id'] not in TARGETS and fixed!=code:raise RuntimeError('Unexpected additional rewrite')
        if sample['final_passed'] and (fixed!=original.read_text(encoding='utf-8') or not after['validation_passed']):
            raise RuntimeError('A previously passed raw artifact changed or gained a validation error')
        compact=lambda s:{k:v for k,v in s.items() if k not in {'ssm','generated_code','validate_result'}}
        row={'id':sample['id'],'raw_original_automatic_passed':sample['final_passed'],
            'raw_sha256':digest(original),'input_sha256':digest(start),'vue_sha256':digest(vue),
            'input_kind':'prior_frozen_offline_parent_prop_candidate' if start.parent==BASE else 'raw_frozen_retained_candidate',
            'before':compact(before),'after':compact(after),'changes':result['changes'],'proofs':result['proofs'],
            'gate':gate,'fixed_point':True,'fresh_model_or_manual_pass_claimed':False}
        rows.append(row)
        if sample['id'] in TARGETS:
            if not result['changes'] or not after['validation_passed'] or not after['visual_eval_passed']:
                raise RuntimeError('Target did not close static/initial-DOM checks')
            for tag in ('script','style'):
                segment=lambda text:re.search(fr'<{tag}\b[^>]*>([\s\S]*?)</{tag}\s*>',text,re.I)[1]
                if segment(code)!=segment(fixed):raise RuntimeError('New template rule edited script or CSS')
            reverse=candidate_gate(after,before)
            if not reverse['should_stop']:raise RuntimeError('Reintroducing the repaired defect was not rejected')
            row['reverse_gate']=reverse
            artifacts[f"{plan['component_name']}_source_template_offline.san"]=fixed
            # Exercise the real repair scheduler starting from the original raw
            # failure, not the prior offline prop candidate or a synthetic pass.
            with tempfile.TemporaryDirectory() as tmp:
                generate=ReplayGenerate(state,state['final_code'],Path(tmp)/'before.san')
                runner=MigrationPipelineOrchestrator(generate,ValidateStage(),VisualEvalStage(),RepairStage(NoModel()))
                actual=runner.run_generate_validate_visual_eval_and_repair_loop(GenerateStageInput(vue_file_path=str(vue),
                    metadata={'repair_policy':'bounded_prepass_v1','semantic_rule_set':'residual_v2'}),max_repair_rounds=3).state
                if (not actual['final_passed'] or actual['llm_repair_calls'] or actual['deterministic_steps']!=1
                    or actual['final_code']!=fixed):raise RuntimeError('Actual zero-model scheduler proof failed')
                schedulers[sample['id']]={k:actual[k] for k in ('final_passed','llm_repair_calls','deterministic_steps',
                    'normalization_history','normalization_stop_reasons')}
    if {r['id'] for r in rows if r['changes']}!=TARGETS:raise RuntimeError('Unexpected target set')
    monitor=next(r for r in rows if r['id']=='MonitoringDashboard')
    if [e['code'] for e in monitor['after']['validation_errors']]!=['source_watch_persistence_unproven']:
        raise RuntimeError('Persistence uncertainty was lost')
    if not next(r for r in rows if r['id']=='TaskManager')['after']['validation_errors']:
        raise RuntimeError('TaskManager residual errors were waived')
    verify_snapshot(SOURCE.resolve());verify_snapshot(BASE.resolve())
    return artifacts,{'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'client_study_date':'2026-11-10','classification':'offline_source_template_closure_reused_development_not_fresh_batch',
        'source_verified_files':verified,'original_aggregate':raw['aggregate'],'model_requests':0,
        'original_score_modified':False,'canonical_san_or_manual_pages_modified':False,
        'browser_interaction_test_or_manual_pass_claimed':False,'exception_policy_changed':False,
        'original_passed_raw_artifacts_static_checked_unchanged':24,
        'base_lineage_note':'Three inputs use the prior frozen offline parent-prop candidates; all others use raw retained bytes. No fresh full-batch pass rate inferred.',
        'initial_dom_reexecuted_ids':sorted(TARGETS),'retained_artifact_replays':rows,'actual_schedulers':schedulers}


def report(data):
    return f'''# 源模板通用修复 v1（2026-11-10，离线）

原始批次仍为 24/30、6 失败、0 执行异常。本包不是新生成批次，也不是独立测试或人工通过。

StockReservationBadge 的脚本 Data API 被错误写入模板，影响 class、文字和 disabled；RuleBuilder 的两个条件 class 重复声明，其中一个还缺少插值闭括号。旧前处理因混合错误/视觉失败而未进入这些独立语法修复。

新增规则按 Vue 源表达式、整棵元素结构及循环/条件作用域证明映射，只修改外层模板。字段名必须同时为源与目标的已声明状态/props/computed，不能与循环别名冲突。只有两侧 computed 都证明返回相同非空字符串集合时，才去掉冗余空串 fallback。单 token 对象 class 必须与目标条件及 token 完全对应，才合并重复属性或补一个已证明缺失的闭括号。未知映射、多个候选/括号、实体转义冲突和内联子模板不猜补。

新增 render API 诊断（含内联字面量模板）、源 class 的逐节点诊断、分析不可用错误；与前处理、模型返回后处理、回退保护和 repair Prompt 对齐。脚本中的 Data API 不改，class 部分修复不被分组消息变化误判成新增错误；回退引入旧缺陷会拒绝。

- 完整测试：{data['unit_tests']['passed']}/{data['unit_tests']['passed']}，{data['unit_tests']['elapsed_seconds']} 秒。
- 30 项重新静态验证/编译，仅 StockReservationBadge、RuleBuilder 两个输入被新模板规则改写并重新执行初始 DOM/视觉比较。其余标志引用上一冻结报告，不伪称完整新视觉回归。
- 原始通过的 24 项字节不变且静态仍通过。三个输入沿用上一轮已冻结的离线父 props 候选，其他使用原始保留件；这条累计离线链不能回填批次成绩。
- 两个目标另从各自原始失败代码进入真实调度器，均为 0 次模型调用、1 次确定性步骤，静态/初始 DOM 通过；RuleBuilder 同一步组合已有 props 规则。
- 单元测试使用已安装 San 的 parser/evalExpr/Data 验证 class 在状态改变后重新求值。没有真实浏览器自动重绘/人工交互通过声明，也没有安装额外 DOM 库。
- TaskManager/TripItineraryPlanner 的既有残留以及 MonitoringDashboard 的持久化 unproven/error 不被豁免。

派生 San 只存本目录；不覆盖标准产物、不修改测试页面、不调用模型。完整数据见 replay.json，校验和见 SHA256SUMS.txt。下一步再按顺序人工检查这两个派生产物，或继续完成复杂语义残留；不要直接据本包启动全量复跑或宣布全批通过。
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write-evidence',action='store_true');args=p.parse_args()
    if args.write_evidence and OUTPUT.exists():raise FileExistsError('Never replace frozen evidence')
    hashes=inventory();tests=''
    if args.write_evidence:
        print('Running complete tests; no model requests.',flush=True)
        proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'],cwd=ROOT,
            env={**os.environ,'PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8')
        tests=proc.stdout+proc.stderr
        if proc.returncode:raise RuntimeError('Complete tests failed:\n'+tests)
    artifacts,data=replay()
    if inventory()!=hashes:raise RuntimeError('Runtime changed during verification')
    if args.write_evidence:
        match=re.search(r'Ran (\d+) tests in ([\d.]+)s',tests)
        if not match or '\nOK' not in tests:raise RuntimeError('Test success/count missing')
        data['unit_tests']={'passed':int(match[1]),'failed':0,'elapsed_seconds':float(match[2])}
        OUTPUT.mkdir(parents=True)
        for name in sorted(CHANGED|ADDED):
            target=OUTPUT/'code'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
        for name,code in artifacts.items():(OUTPUT/name).write_text(code,encoding='utf-8')
        data['derived_artifact_sha256']={name:digest(OUTPUT/name) for name in artifacts}
        for name,value in (('replay.json',data),('live_inventory.json',hashes)):
            (OUTPUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (OUTPUT/'unit_tests.txt').write_text(tests,encoding='utf-8');(OUTPUT/'REPORT.md').write_text(report(data),encoding='utf-8')
        files=sorted(f for f in OUTPUT.rglob('*') if f.is_file())
        (OUTPUT/'SHA256SUMS.txt').write_text('\n'.join(f'{digest(f)}  {f.relative_to(OUTPUT).as_posix()}' for f in files)+'\n',encoding='utf-8')
        verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'model_requests':0,'original_passed':24,'changed_ids':sorted(TARGETS),
        'schedulers':{name:{k:v for k,v in s.items() if k not in {'normalization_history','normalization_stop_reasons'}}
                      for name,s in data['actual_schedulers'].items()},'unit_tests':data.get('unit_tests'),'evidence_written':args.write_evidence}))


if __name__=='__main__':main()
