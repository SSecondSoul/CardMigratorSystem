"""Offline source-proven array move closure; no model or canonical artifact writes."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot
from migration_pipeline.replay_formal_30_v4_source_render_dependency_closure_v1 import OUTPUT as BASE, SOURCE, PROTOCOL, BATCH
from migration_pipeline.utils.source_array_transaction_semantics import source_array_transaction_semantics
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.generate import GenerateStageInput, GenerateStageResult
from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.utils.repair_scheduler import candidate_gate

OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_source_array_transaction_closure_v1_20261111'
CHANGED={'migration_pipeline/stages/repair.py','migration_pipeline/stages/validate.py',
 'migration_pipeline/utils/repair_prompt.py','migration_pipeline/utils/repair_scheduler.py',
 'tests/test_source_render_dependency_closure.py','tests/test_source_dom_closure.py',
 'tests/test_source_inline_formatter_closure.py','tests/test_source_payload_closure.py',
 'tests/test_source_render_call_closure.py','tests/test_monitoring_remaining_bounded_fix.py'}
ADDED={'migration_pipeline/utils/source_array_transaction_semantics.py',
 'migration_pipeline/utils/source_array_transaction_semantics.cjs','tests/test_source_array_transaction_closure.py',
 'migration_pipeline/replay_formal_30_v4_source_array_transaction_closure_v1.py'}


def inventory():
    verify_snapshot(BASE.resolve())
    previous=json.loads((BASE/'live_inventory.json').read_text(encoding='utf-8'))
    now={name:digest(ROOT/name) for name in sorted(set(previous)|ADDED)}
    changed={name for name,sha in previous.items() if now[name]!=sha}
    if changed!=CHANGED:raise RuntimeError('Unexpected runtime delta: '+str(changed^CHANGED))
    return now


def offline_scheduler(code,vue,ssm,expected):
    class NoModel:
        def repair(self,_):raise AssertionError('Offline replay must never make an LLM repair request')
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'retained.san';path.write_text(code,encoding='utf-8')
        class FrozenGenerate:
            def run(self,_):return GenerateStageResult(source_file=str(vue),ssm=ssm,generation_code=code,
                saved_file_path=str(path),provider='retained_frozen_artifact',model='none',usage={},raw_response={})
        result=MigrationPipelineOrchestrator(FrozenGenerate(),ValidateStage(),VisualEvalStage(),RepairStage(NoModel())).run_generate_validate_visual_eval_and_repair_loop(
            GenerateStageInput(vue_file_path=str(vue),metadata={'repair_policy':'bounded_prepass_v1','semantic_rule_set':'residual_v2'}),max_repair_rounds=3)
        state=result.state;actual=Path(state['final_file_path']).read_text(encoding='utf-8')
        if not state['final_passed'] or state['llm_repair_calls']!=0 or state['deterministic_steps']!=1 or actual!=expected:
            raise RuntimeError('Full offline scheduler did not close the retained candidate with zero model requests')
        return {'input_kind':'retained_frozen_artifact_not_new_generation','final_passed':state['final_passed'],
            'llm_repair_calls':state['llm_repair_calls'],'deterministic_steps':state['deterministic_steps'],
            'stop_reason':state['stop_reason'],'normalizations':state['normalization_history'][0]['normalizations'],
            'candidate_gate':state['normalization_history'][0]['gate'],
            'output_sha256':hashlib.sha256(actual.encode('utf-8')).hexdigest(),
            'temporary_harness_files_removed':True,'manual_or_browser_interaction':False}


def replay():
    verified={name:verify_snapshot(path.resolve()) for name,path in [
        ('raw',SOURCE),('protocol',PROTOCOL),('source_render_dependency_closure',BASE)]}
    old={r['id']:r for r in json.loads((BASE/'replay.json').read_text(encoding='utf-8'))['retained_artifact_replays']}
    raw=json.loads((SOURCE/f'{BATCH}_summary.json').read_text(encoding='utf-8'))
    rows,artifacts=[],{}
    if len(old)!=30 or len(raw['samples'])!=30:raise RuntimeError('Expected full-30 inputs')
    for sample in raw['samples']:
        name=sample['id'];print('Offline static check: '+name,flush=True);prior=old[name]
        path=BASE/'TaskManager_source_render_dependency_offline.san' if name=='TaskManager' else ROOT/prior['input_path']
        code=path.read_text(encoding='utf-8');vue=ROOT/prior['vue_path'];source=vue.read_text(encoding='utf-8')
        state=json.loads((SOURCE/'repair_reports'/sample['complexity']/sample['report_file'].replace('\\','/').split('/')[-1]).read_text(encoding='utf-8'))['state']
        result=source_array_transaction_semantics(code,source,repair=True)
        if result.get('error'):raise RuntimeError('AST error '+name+': '+result['error'])
        fixed=result['code']
        def assess(text,visual=None):
            value=ValidateStage().run(ValidateStageInput(generated_code=text,ssm=state['ssm'],vue_file_path=str(vue))).to_state_update()
            value.update(generated_code=text,ssm=state['ssm'],vue_file_path=str(vue))
            if visual is None:
                vis=VisualEvalStage().run(VisualEvalStageInput(generated_code=text,vue_file_path=str(vue)))
                value.update(visual_eval_passed=vis.visual_eval_passed,visual_errors=vis.visual_eval_errors,
                    structure_similarity=vis.structure_similarity,visual_reexecuted=True)
            else:value.update(visual_eval_passed=visual,visual_reexecuted=False)
            return value
        before=assess(code,prior['after']['visual_eval_passed']);after=assess(fixed) if fixed!=code else before
        array_findings=[e for e in before['validation_errors'] if e['code']=='source_array_transaction_not_landed']
        if len(array_findings)!=(1 if name=='TaskManager' else 0):raise RuntimeError('Unexpected transaction finding: '+name)
        gate=candidate_gate(before,after)
        if gate['should_stop']:raise RuntimeError('Candidate rejected: '+name)
        again=source_array_transaction_semantics(fixed,source,repair=True)
        if again.get('error') or again['code']!=fixed or again['changes']:raise RuntimeError('Not a fixed point: '+name)
        if name!='TaskManager' and fixed!=code:raise RuntimeError('Additional rewrite needs review: '+name)
        if sample['final_passed'] and (fixed!=state['final_code'] or not after['validation_passed']):
            raise RuntimeError('Original passed raw artifact changed or now fails: '+name)
        compact=lambda d:{k:v for k,v in d.items() if k not in {'generated_code','ssm','validate_result'}}
        row={'id':name,'raw_original_automatic_passed':sample['final_passed'],
            'input_path':path.relative_to(ROOT).as_posix(),'input_sha256':digest(path),
            'vue_path':vue.relative_to(ROOT).as_posix(),'vue_sha256':digest(vue),
            'before':compact(before),'after':compact(after),'changes':result['changes'],'proofs':result['proofs'],
            'reviews':result['reviews'],'mapped_contracts':result['mapped_contracts'],'gate':gate}
        if name=='TaskManager':
            if {e['code'] for e in before['validation_errors']}!={'nested_state_mutation','source_array_transaction_not_landed'} or not after['validation_passed']:
                raise RuntimeError('Unexpected TaskManager diagnostic result')
            if after['validation_errors'] or len(result['proofs'])!=1 or result['proofs'][0]['contract']!='script.methods.moveTask@tasks':
                raise RuntimeError('Unexpected transaction proof')
            planned,steps=RepairStage._deterministic_repair_plan(code,before['validation_errors'],[],state['ssm'],str(vue),enable_residual_v2=True)
            if planned!=fixed:raise RuntimeError('Prepass differs from rule')
            reverse=candidate_gate(after,before)
            if not reverse['should_stop']:raise RuntimeError('Mutation/commit regression not rejected')
            row.update(prepass_steps=steps,reverse_gate=reverse,closed_transaction_proofs=again['proofs'],
                offline_scheduler=offline_scheduler(code,vue,state['ssm'],fixed))
            artifacts['TaskManager_source_array_transaction_offline.san']=fixed
        if name=='trip_itinerary_planner' and (fixed!=code or after['validation_passed'] or not any(e['code']=='source_render_dependency_not_landed' for e in after['validation_errors'])):
            raise RuntimeError('Do not erase the previous unproven external render dependency')
        rows.append(row)
    verify_snapshot(SOURCE.resolve());verify_snapshot(BASE.resolve())
    return artifacts,{'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'offline_source_array_transaction_closure_reused_development_not_new_batch',
        'source_verified_files':verified,'original_aggregate':raw['aggregate'],'model_requests':0,
        'original_score_modified':False,'canonical_san_or_manual_pages_modified':False,
        'manual_acceptance_inherited':False,'full_browser_interaction_executed':False,
        'runtime_inventory_count':len(inventory()),'original_passed_raw_artifacts_static_checked_unchanged':24,
        'initial_dom_reexecuted_ids':['TaskManager'],'retained_prior_derivative_risk_ids':['trip_itinerary_planner'],
        'retained_artifact_replays':rows}


def report(data):
    tests=data['unit_tests']
    return f'''# 源数组移动事务闭环 v1（2026-11-11，离线开发回归）

原始批次仍为 24/30、6 失败、0 执行异常、1,821,544 tokens。本轮接续父模板依赖闭环的冻结 TaskManager 中间件；不从 Vue 新生成，不改 canonical San 或人工页，不回填分数，不继承人工通过，不是独立测试。真实模型请求 0。

既有 _normalize_mutated_state_array_aliases 根据正则找到 alias/mutator/writeback，可在复制后仍保留错误提交时机，也无法证明整个方法与源一致。本轮 residual_v2 前后处理均禁用这一路较弱回退，保留非 residual_v2 legacy 行为；改用 source_array_transaction_semantics.py/.cjs，按完整 Vue 与导出 San 父方法、声明数组及整个规范化方法体证明“两次 splice 的局部移动事务”。不是按 TaskManager 名称特判。

仅支持一个 const 根数组别名、同一末尾成功 if 中的解构删除/单元素插入、纯局部索引调整和简单 findIndex 比较。比较源全部参数/默认布尔值、早退、过滤/原始索引、分支、拖拽状态和通知原文。拒绝未知效果/控制流、循环/提前返回、额外 splice、别名逃逸/重赋值、嵌套对象写、实时数组再读、未知回调、重复/条件提交、fallback、全局 Array 遮蔽/显式重写。浅复制仅隔离数组结构，不声称通用记录深复制或绝对证明外部运行时原型未被篡改。

自动改写只复制别名初始化，并把唯一数据提交放在最终插入后、清理拖拽状态/通知前。旧代码 tasks.splice 修改存储数组在先；旧 this.data.set('dragStartIndex',null) 后才 [...tasks] 提交。复制后若仍按旧位置提交，观察拖拽状态的逻辑可能见到旧列表，故必须恢复源“列表先改变，后续效果再发生”的顺序。元素对象保持身份，未移动分支不提交，不为源码已有缺陷猜新逻辑。

前处理、stub 模型返回后处理、共享 repair Prompt、验证器与候选保护同步。新增 source_array_transaction_not_landed / source_array_transaction_analysis_unavailable；即使 spread 去掉了旧 mutation 诊断，丢失提交或改变 guard/index/通知也不能通过新契约。旧 generation/服务器 Prompt 未改，不启动服务器。

开发初检暴露 Babel cloneNode 不保留 start/end，旧位置匹配导致分析器报错并原样返回，没有改坏产物；改为按原语句索引定位 clone。首轮 19 项、2 失败（57.001 秒）：测试错误预期紧凑 fixture 必被 legacy 行正则识别，以及 oracle 只识别 export default 而真实 Vue 使用 CommonJS。改测试使用真实 legacy 输入、共享 sourceParent 提取原方法，生产规则未放宽。后续精确结果以完整日志为准，开发摘要不冒称完整失败日志已保存。

修正后历史/针对组合 40/40（156.071 秒）通过；一次后续组合执行 68 项、1 error（219.945 秒），唯一 error 是命令误写不存在的 formatter 测试选择器，67 个实际测试通过，不称该轮全通过。按真实名称单独执行 formatter 测试 1/1（42.967 秒）通过；再从稳定清单重跑完整套件，不拼接散测作为完整通过。

加入完整调度器和源未知事务拒绝用例、加固原型字段与绑定丢失保护后，新规则单独 21/21（63.498 秒）通过。开发只读 30 项回放亦完成且不写文件；最终证据使用随后稳定代码重新执行的完整套件与回放，不把预检当成冻结结果。

完整套件 {tests['passed']}/{tests['passed']}、0 失败，{tests['elapsed_seconds']} 秒，完整输出 unit_tests.txt。真实安装 San 组件数据存储上比较源方法 oracle：向上/向下、过滤可见列表、末尾插入、null/undefined/越界、同一任务、目标已消失；核对原数组未变、元素身份保留、一次提交、清理/通知见到新顺序。真实 TaskManager 用原冻结源方法与精确目标方法的最小运行夹具，不触发整个组件的初始化/定时器；因此不是浏览器原生拖放证据。

实际 bounded_prepass_v1 调度器注入冻结产物提供器，不调用生成服务；用真实 ValidateStage/VisualEvalStage、禁止任何模型请求的 repair client，1 个确定性步骤、0 次 LLM，得到 final_passed=true，代码等于独立规则。这里 final_passed 只表示离线静态/轻量初始 DOM 自动门通过，不是新批次或人工/全交互通过。

累计 30 项重新静态验证/编译，只 TaskManager 改写；24 个原始通过件原字节且仍通过。仅 TaskManager 重做轻量初始 DOM，其余视觉标记沿用前层。TaskManager 按现行校验 2→0 条错误（旧 mutation 与同一新源事务的重叠诊断），validation_passed=true，migration_hints_not_landed 警告保留。正向接受、反向拒绝、固定点与组合前处理一致；原始批次不曾因此变成 25/30 或更高。

TripItineraryPlanner 上轮新暴露的外部 dayCountGetter/filter 渲染依赖仍失败，本轮不处理、不豁免。完整 TaskManager 初始化工厂/watch 时机、浏览器弹窗/实际拖放、持久化/计时器交互仍是 remaining_risk；不能从静态零错误推断全部业务已等价。下一步审查完整初始化和拖拽链，再决定是否进入人工验收，不立即付费复跑。

运行清单 {data['runtime_inventory_count']} 项，SHA256SUMS 覆盖新包代码、派生 San、回放、报告和完整日志；旧冻结包、协议和分数不改，未 commit/push。
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-evidence',action='store_true');args=parser.parse_args()
    if args.write_evidence and OUTPUT.exists():raise FileExistsError('Never overwrite frozen evidence')
    hashes=inventory();log=''
    if args.write_evidence:
        print('Running complete tests; no model requests.',flush=True)
        proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'],cwd=ROOT,
            env={**os.environ,'PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8')
        log=proc.stdout+proc.stderr
        if proc.returncode:raise RuntimeError('Full tests failed:\n'+log)
    artifacts,data=replay()
    if inventory()!=hashes:raise RuntimeError('Runtime changed during verification')
    if args.write_evidence:
        match=re.search(r'Ran (\d+) tests in ([\d.]+)s',log)
        if not match or '\nOK' not in log or re.search(r'OK\s*\(skipped=',log):raise RuntimeError('Missing complete non-skipped test success/count')
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
        'current_before_findings':2,'current_after_findings':0,'unit_tests':data.get('unit_tests'),
        'evidence_written':args.write_evidence,'new_batch_or_manual_pass_claimed':False}))


if __name__=='__main__':main()
