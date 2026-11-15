"""Offline parent readonly render DAG closure; no generation or model request."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot
from migration_pipeline.replay_formal_30_v4_source_render_call_closure_v1 import OUTPUT as BASE, SOURCE, PROTOCOL, BATCH
from migration_pipeline.utils.source_render_dependency_semantics import source_render_dependency_semantics
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.utils.repair_scheduler import candidate_gate

OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_source_render_dependency_closure_v1_20261111'
CHANGED={'migration_pipeline/stages/repair.py','migration_pipeline/stages/validate.py',
 'migration_pipeline/utils/repair_prompt.py','migration_pipeline/utils/repair_scheduler.py',
 'migration_pipeline/utils/source_render_call_semantics.cjs','tests/test_source_dom_closure.py',
 'tests/test_source_inline_formatter_closure.py','tests/test_source_payload_closure.py',
 'tests/test_source_render_call_closure.py','tests/test_monitoring_remaining_bounded_fix.py',
 'tests/test_repair_regression_guard.py'}
ADDED={'migration_pipeline/utils/source_render_dependency_semantics.py',
 'migration_pipeline/utils/source_render_dependency_semantics.cjs',
 'tests/test_source_render_dependency_closure.py',
 'migration_pipeline/replay_formal_30_v4_source_render_dependency_closure_v1.py'}


def inventory():
    verify_snapshot(BASE.resolve())
    previous=json.loads((BASE/'live_inventory.json').read_text(encoding='utf-8'))
    now={name:digest(ROOT/name) for name in sorted(set(previous)|ADDED)}
    changed={name for name,sha in previous.items() if now[name]!=sha}
    if changed!=CHANGED:raise RuntimeError('Unexpected runtime delta: '+str(changed^CHANGED))
    return now


def replay():
    verified={name:verify_snapshot(path.resolve()) for name,path in [
        ('raw',SOURCE),('protocol',PROTOCOL),('source_render_call_closure',BASE)]}
    previous=json.loads((BASE/'replay.json').read_text(encoding='utf-8'))
    old={row['id']:row for row in previous['retained_artifact_replays']}
    raw=json.loads((SOURCE/f'{BATCH}_summary.json').read_text(encoding='utf-8'))
    rows,artifacts=[],{}
    if len(old)!=30 or len(raw['samples'])!=30:raise RuntimeError('Expected full-30 inputs')
    for sample in raw['samples']:
        name=sample['id'];print('Offline static check: '+name,flush=True)
        prior=old[name]
        path=BASE/'TaskManager_source_render_call_offline.san' if name=='TaskManager' else ROOT/prior['input_path']
        code=path.read_text(encoding='utf-8');vue=ROOT/prior['vue_path'];source=vue.read_text(encoding='utf-8')
        state=json.loads((SOURCE/'repair_reports'/sample['complexity']/sample['report_file'].replace('\\','/').split('/')[-1]).read_text(encoding='utf-8'))['state']
        result=source_render_dependency_semantics(code,source,repair=True)
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

        before=assess(code,prior['after']['visual_eval_passed']);after=assess(fixed) if code!=fixed else before
        new_findings=[e for e in before['validation_errors'] if e['code']=='source_render_dependency_not_landed']
        expected_new=1 if name in {'TaskManager','trip_itinerary_planner'} else 0
        if len(new_findings)!=expected_new:raise RuntimeError('Unexpected new dependency diagnostics: '+name)
        gate=candidate_gate(before,after)
        if gate['should_stop']:raise RuntimeError('Candidate rejected: '+name)
        again=source_render_dependency_semantics(fixed,source,repair=True)
        if again.get('error') or again['code']!=fixed or again['changes']:raise RuntimeError('Not a fixed point: '+name)
        if name!='TaskManager' and fixed!=code:raise RuntimeError('Additional rewrite needs review: '+name)
        if sample['final_passed'] and (fixed!=state['final_code'] or not after['validation_passed']):
            raise RuntimeError('Original passed raw artifact changed or now fails: '+name)
        compact=lambda d:{k:v for k,v in d.items() if k not in {'generated_code','ssm','validate_result'}}
        row={'id':name,'raw_original_automatic_passed':sample['final_passed'],
            'input_path':path.relative_to(ROOT).as_posix(),'input_sha256':digest(path),
            'vue_path':vue.relative_to(ROOT).as_posix(),'vue_sha256':digest(vue),
            'before':compact(before),'after':compact(after),'changes':result['changes'],'proofs':result['proofs'],
            'reviews':result['reviews'],'mapped_bindings':result['mapped_bindings'],
            'new_dependency_findings':new_findings,'gate':gate}
        if name=='TaskManager':
            if len(before['validation_errors'])!=3 or [e['code'] for e in after['validation_errors']]!=['nested_state_mutation']:
                raise RuntimeError('Unexpected partial TaskManager diagnostics')
            if after['validation_passed']:raise RuntimeError('Still partial, not a pass')
            if len(result['proofs'])!=1 or result['proofs'][0]['methods']!=['getTaskCount','isOverdue'] or result['proofs'][0]['fields']!=['tasks']:
                raise RuntimeError('Unexpected dependency graph proof')
            planned,steps=RepairStage._deterministic_repair_plan(code,before['validation_errors'],[],state['ssm'],str(vue),enable_residual_v2=True)
            if planned!=fixed:raise RuntimeError('Prepass differs from rule')
            reverse=candidate_gate(after,before)
            if not reverse['should_stop']:raise RuntimeError('Dependency regression not rejected')
            row.update(prepass_steps=steps,reverse_gate=reverse,explicit_reanalysis_proofs=again['proofs'])
            artifacts['TaskManager_source_render_dependency_offline.san']=fixed
        if name=='trip_itinerary_planner':
            if fixed!=code or after['validation_passed'] or not any(r['reason']=='unproven_readonly_method' for r in result['reviews']):
                raise RuntimeError('Do not waive unproven external helper dependency')
            row['classification']='newly_exposed_preexisting_risk_in_prior_offline_derivative_not_new_repair_regression'
        if name=='localization_workspace':
            if not result['proofs'] or not all(p.get('explicit') and p.get('preexisting_public_call') for p in result['proofs']):
                raise RuntimeError('Existing explicit public graph must be body-proven')
        rows.append(row)
    verify_snapshot(SOURCE.resolve());verify_snapshot(BASE.resolve())
    return artifacts,{'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'partial_offline_source_render_dependency_closure_reused_development_not_new_batch',
        'source_verified_files':verified,'original_aggregate':raw['aggregate'],'model_requests':0,
        'original_score_modified':False,'canonical_san_or_manual_pages_modified':False,
        'manual_acceptance_inherited':False,'full_browser_interaction_executed':False,
        'runtime_inventory_count':len(inventory()),'original_passed_raw_artifacts_static_checked_unchanged':24,
        'initial_dom_reexecuted_ids':['TaskManager'],
        'newly_exposed_prior_derivative_risk_ids':['trip_itinerary_planner'],
        'retained_artifact_replays':rows}


def report(data):
    tests=data['unit_tests']
    return f'''# 父模板只读渲染依赖 DAG 闭环 v1（2026-11-11，部分修复）

原始批次仍为 24/30、6 失败、0 执行异常、1,821,544 tokens。这是接续源内联渲染调用冻结派生件的离线开发回归，不是独立测试或新生成批次；本轮模型请求 0，不改标准 San 与人工测试页，不继承人工通过，不回填原始分数。

问题：父模板 getTaskCount(filter.value) 隐藏 tasks，且其 overdue 分支间接调用 isOverdue。只改根方法或只加 Prompt 不能证明整条调用链响应性。新增 source_render_dependency_semantics.py/.cjs，按完整 Vue、导出 San 父组件、同路径/作用域/静态 class/邻接文本的根调用映射，建立无环只读方法图；规范化 Vue 字段读和 San data.get 及顶层 const 数据别名后，比较完整函数体、分支、参数与所有实例调用边。

有界规则只接受源证明的数组 filter、Math 纯操作与新建局部 Date 的指定方法；拒绝递归、未知/外部调用、突变、传统函数回调、未知数组、全局遮蔽/显式重写、上下文漂移和依赖字段被循环别名遮蔽。Date 仍按原调用时刻求值，不发明时钟字段或自动刷新定时器，也不声称已证明环境原型绝对未被外部代码篡改。

保留公开 getTaskCount/isOverdue 签名、函数体及全部脚本调用者；增加私有只读图副本，把 tasks 经模板根及所有需要它的内部调用显式传递。原方法区和 CSS 不改，验证重分析需证明完整副本，而不是看辅助函数名或错误数减少。现有已显式传依赖的公共方法也须完整体/参数/调用边证明，不能只凭名称豁免。

修复前处理、stub 模型后处理、共享 repair Prompt、验证器、候选保护一致接入。新增 source_render_dependency_not_landed / source_render_dependency_analysis_unavailable；丢失已匹配绑定或引入错误均拒绝，正向进展可接受。旧非 residual_v2 前处理不启用新规则。generation/服务器 Prompt 未改，本轮无需启动服务器。

开发首轮 18 项测试 1 error（33.642 秒）：测试夹具方法 state 与真实冻结类状态同名冲突；改夹具名为 fixture_state，不放宽生产规则。随后 19/19（43.572 秒）通过。测试包含真实安装 San 的公开解析/求值器与 data.set、显式间接依赖、公开调用者、固定时钟下六个任务分支、无效日期、参数/字段/图体篡改、未知调用/突变拒绝、正反向保护、前后处理与 legacy 边界。这些控制台摘要不是保存了完整开发失败日志的声明。

完整套件 {tests['passed']}/{tests['passed']}、0 失败，{tests['elapsed_seconds']} 秒；输出 unit_tests.txt。30 个累计输入重做静态验证/编译，仅 TaskManager 改写；原始 24 个通过件字节未变且仍静态通过。TaskManager 只重做轻量初始 DOM，其余视觉标记沿用前层，不冒充浏览器全交互复验。

TaskManager 当前校验从 3 条到 1 条：旧 hidden_template_reactive_dependency 与新重叠源契约诊断关闭，仍有 moveTask 的 nested_state_mutation，validation_passed=false。因此不是整个组件通过，也不切换人工页面。正向候选接受、反向拒绝、固定点、组合前处理等于独立规则已复核。

跨样本审查：LocalizationWorkspace 的 translationFor(record,language) 已显式带 language，完整 AST 证明后原字节保留。TripItineraryPlanner 是原始失败样本的既有 parent-props 离线派生件；dayCount 经外部 dayCountGetter/filter 隐藏 items，超出本规则实例 DAG 范围。新增校验暴露这一既有未证明路径，派生件现行 validation_passed=false；未改其字节、不豁免、不称本次修复引入回归，也不继续沿用此前派生件的整体验证通过结论。原始 24/30 不受其影响。

历史精确诊断断言只补新契约/组合步骤，保留旧诊断和 fail-closed 要求；旧冻结报告不改。event-v3 单例额外复核 1 项失败（8.805 秒），是精确错误集合漏列新计数契约，真实位置为 template/div[0]/div[2]/div[0]/div[1]/button[0]/span[0]#text:0@getTaskCount。核对后只补错误码及该位置，仍要求 prepare fail closed，不修改规则豁免；保留此开发失败摘要，不冒称保存完整失败日志。

首次历史组合检查为 197 项、1 失败（292.172 秒），唯一失败同为上述 event-v3 精确集合。修正断言后的 event-v3 与 MonitoringDashboard 第三次历史件复测 2/2（17.243 秒）通过；不将 196/197 拼为完整通过，之后从稳定清单重跑完整套件。开发只读 30 项预检期间更新过测试/重放脚本，因此清单一致性保护按设计拒绝该预检完成，不写冻结成功包，最终重放须重新执行。

清单 {data['runtime_inventory_count']} 项，SHA256SUMS 覆盖本包代码、报告、测试日志与中间 San。下一步优先闭合任务移动的不可变更新，再审查初始化/拖拽实际行为；Trip 外部辅助函数另列待审查，不以继续付费试跑代替闭环。
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
        if not match or '\nOK' not in log:raise RuntimeError('Missing complete test success/count')
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
        'current_before_findings':3,'current_after_findings':1,'unit_tests':data.get('unit_tests'),
        'evidence_written':args.write_evidence,'new_batch_pass_claimed':False}))


if __name__=='__main__':main()
