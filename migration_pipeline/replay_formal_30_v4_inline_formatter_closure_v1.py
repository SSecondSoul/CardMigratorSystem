"""Freeze a partial source-formatter closure; no model calls or canonical writes."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot
from migration_pipeline.replay_formal_30_v4_source_template_closure_v1 import OUTPUT as BASE, SOURCE, PROTOCOL
from migration_pipeline.replay_formal_30_v4_parent_props_closure_v1 import OUTPUT as PROPS
from migration_pipeline.utils.residual_semantics import residual_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.stages.repair import RepairStage

OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_inline_formatter_closure_v1_20261110'
BATCH='formal_30_v4_full_regression_v2'
CHANGED={'migration_pipeline/utils/residual_semantics.cjs','migration_pipeline/stages/validate.py',
         'migration_pipeline/utils/repair_prompt.py','migration_pipeline/utils/repair_scheduler.py'}
ADDED={'migration_pipeline/utils/source_inline_formatter_semantics.cjs',
       'tests/test_source_inline_formatter_closure.py',
       'migration_pipeline/replay_formal_30_v4_inline_formatter_closure_v1.py'}


def inventory():
    verify_snapshot(BASE.resolve())
    prior=json.loads((BASE/'live_inventory.json').read_text(encoding='utf-8'))
    current={name:digest(ROOT/name) for name in sorted(set(prior)|ADDED)}
    changed={name for name,sha in prior.items() if current[name]!=sha}
    if changed!=CHANGED:raise RuntimeError(f'Unexpected runtime delta: {changed ^ CHANGED}')
    return current


def replay():
    verified={name:verify_snapshot(path.resolve()) for name,path in
              [('raw',SOURCE),('protocol',PROTOCOL),('template_closure',BASE),('props_closure',PROPS)]}
    raw=json.loads((SOURCE/f'{BATCH}_summary.json').read_text(encoding='utf-8'))
    config=json.loads((SOURCE/f'{BATCH}.json').read_text(encoding='utf-8'))
    prior=json.loads((BASE/'replay.json').read_text(encoding='utf-8'))
    old={r['id']:r for r in prior['retained_artifact_replays']}
    if [s['id'] for s in raw['samples']]!=[s['id'] for s in config['samples']]:raise RuntimeError('Order mismatch')
    rows,artifacts=[],{}
    for sample,plan in zip(raw['samples'],config['samples']):
        print('Offline static check: '+sample['id'],flush=True)
        state=json.loads((SOURCE/'repair_reports'/sample['complexity']/Path(sample['report_file']).name).read_text(encoding='utf-8'))['state']
        original=SOURCE/'pipeline'/sample['complexity']/Path(sample['final_file_path']).name
        start=original
        if sample['id'] in {'stock_reservation_badge','rule_builder'}:
            start=BASE/f"{plan['component_name']}_source_template_offline.san"
        elif old[sample['id']]['input_kind']=='prior_frozen_offline_parent_prop_candidate':
            start=PROPS/f"retained_{sample['id']}_parent_props_offline.san"
        code=start.read_text(encoding='utf-8')
        vue=SOURCE/'protocol/frozen'/plan['vue_file']
        result=residual_semantics(code,state['ssm'],repair=True)
        if result.get('error'):raise RuntimeError(f"AST failure: {sample['id']}: {result['error']}")
        fixed=result['code']
        def assess(text,visual=None):
            val=ValidateStage().run(ValidateStageInput(generated_code=text,ssm=state['ssm'],vue_file_path=str(vue))).to_state_update()
            out={'generated_code':text,'ssm':state['ssm'],'vue_file_path':str(vue),**val}
            if visual is None:
                vis=VisualEvalStage().run(VisualEvalStageInput(generated_code=text,vue_file_path=str(vue)))
                out.update(visual_eval_passed=vis.visual_eval_passed,visual_errors=vis.visual_eval_errors,
                           structure_similarity=vis.structure_similarity,visual_reexecuted=True)
            else:out.update(visual_eval_passed=visual,visual_reexecuted=False)
            return out
        before=assess(code,old[sample['id']]['after']['visual_eval_passed'])
        after=assess(fixed) if fixed!=code else before
        gate=candidate_gate(before,after)
        if gate['should_stop']:raise RuntimeError('Candidate gate rejected '+sample['id'])
        repeated=residual_semantics(fixed,state['ssm'],repair=True)
        if repeated['code']!=fixed or repeated['changes']:raise RuntimeError('Not a fixed point')
        if sample['final_passed'] and (fixed!=original.read_text(encoding='utf-8') or not after['validation_passed']):
            raise RuntimeError('Previously passed raw artifact changed or failed')
        if sample['id']!='TaskManager' and code!=fixed:raise RuntimeError('Unexpected additional rewrite')
        compact=lambda s:{k:v for k,v in s.items() if k not in {'generated_code','ssm','validate_result'}}
        row={'id':sample['id'],'raw_original_automatic_passed':sample['final_passed'],
             'input_path':start.relative_to(ROOT).as_posix(),'input_sha256':digest(start),
             'vue_path':vue.relative_to(ROOT).as_posix(),'vue_sha256':digest(vue),
             'changes':result['changes'],'formatter_proofs':result.get('formatter_proofs',[]),
             'before':compact(before),'after':compact(after),'gate':gate}
        if sample['id']=='TaskManager':
            if len(result.get('formatter_proofs',[]))!=5:raise RuntimeError('Expected five proven formatters')
            if len(before['validation_errors'])!=10 or len(after['validation_errors'])!=9:
                raise RuntimeError('Unexpected diagnostic count')
            if after['validation_passed']:raise RuntimeError('Partial closure must remain a failure')
            planned,steps=RepairStage._deterministic_repair_plan(code,before['validation_errors'],[],state['ssm'],str(vue),enable_residual_v2=True)
            if planned!=fixed:raise RuntimeError('Prepass differs from standalone rule')
            reverse=candidate_gate(after,before)
            if not reverse['should_stop']:raise RuntimeError('Reintroduced computed calls were not rejected')
            row.update(reverse_gate=reverse,prepass_steps=steps)
            artifacts['TaskManager_inline_formatter_offline.san']=fixed
        rows.append(row)
    verify_snapshot(SOURCE.resolve());verify_snapshot(BASE.resolve())
    return artifacts,{'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'partial_offline_source_formatter_closure_reused_development_not_new_batch',
        'source_verified_files':verified,'original_aggregate':raw['aggregate'],'model_requests':0,
        'canonical_san_or_manual_pages_modified':False,'original_score_modified':False,
        'manual_acceptance_inherited':False,'full_browser_interaction_executed':False,
        'original_passed_raw_artifacts_static_checked_unchanged':24,'runtime_inventory_count':len(inventory()),
        'initial_dom_reexecuted_ids':['TaskManager'],'retained_artifact_replays':rows}


def report(data):
    return f'''# 子组件 callable formatter 通用闭环 v1（2026-11-10）

这是部分离线修复，不是新生成批次或人工通过。原始成绩仍为 24/30、6 失败、0 执行异常；原始 tokens=1,821,544。

TaskManager 原始保留件有 10 类错误，完整确定性前处理原先零改写。本轮只闭合其中一类：两个内联子组件的五个格式化函数被迁入 computed，模板却按方法调用，造成优先级和日期显示风险。

新增规则按 SSM 注册标签解析唯一 Vue 内联源码与 San 注册对象，只接受字面量常量前缀加返回参数函数，且展开后方法 AST 必须与源方法完全相同、无响应状态读取/外部闭包/未知调用。保留标签映射、空日期回退和 Date/locale 格式；动态模板、脚本侧 computed 消费、同名冲突、组件引用逃逸、Date 遮蔽或不明确来源不猜补。无组件名特判。诊断仍由验证器产生，不删除错误或放宽通过条件。

通过 residual_v2 接入 repair 确定性前处理和模型返回后处理；repair Prompt 同步明确源表、回退值与日期格式保留义务。生成/服务器 Prompt 未改，不需重启服务器来加载本次批处理本地规则。更改批处理代码后须新启动 Python 批处理进程。

首次针对性 10 项测试暴露两处真实闭环缺口：逆向候选门未拒绝该类 computed 回退；补充约束只在部分 Prompt 路由出现。随后新增该诊断的回退保护及按 component.method 的结构化身份，允许旧集合缩小但拒绝新增方法/旧缺陷回归；将约束同时加入共享 repair Prompt。未通过的首次测试不算成功；最终结果见日志。

- 完整单元测试：{data['unit_tests']['passed']}/{data['unit_tests']['passed']}，{data['unit_tests']['elapsed_seconds']} 秒。
- 对累计离线链的 30 项重新静态验证/编译；24 个原通过原始产物字节不变且仍通过。Stock/Rule 沿用上轮模板派生件，Habit/Trip 沿用父 props 派生件，其余原始件；不据累计链拼接新批次分数。
- 仅 TaskManager 发生新改写；五个 formatter 的调用错误消除，静态诊断从 10 类降为 9 类，仍失败。实际轻量初始 DOM 重新检查，不代表设置、拖拽、表单等浏览器交互通过。
- 正向前处理/保护接受，反向回归拒绝，固定点成立；模型返回后处理以 stub 单元测试证明，不发生真实模型调用。没有宣称整轮调度器零模型修到通过。
- 本轮模型请求 0，不改 canonical San、测试页、旧校验和、原始统计；不继承此前不同产物的人工通过。

剩余：Math/成员函数模板表达式、多个 fire payload、事件/循环语法、key、设置遮罩 self 语义、隐藏响应依赖、原地移动任务；另有初始化等尚需继续审查，9 类诊断不代表穷尽全部缺陷。下一步继续独立闭合这些规则，暂不要求用户付费复跑或验收这个仍失败的中间件。
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write-evidence',action='store_true');args=p.parse_args()
    if args.write_evidence and OUTPUT.exists():raise FileExistsError('Never overwrite frozen evidence')
    hashes=inventory();tests=''
    if args.write_evidence:
        print('Running complete tests; no model requests.',flush=True)
        proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'],cwd=ROOT,
            env={**os.environ,'PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8')
        tests=proc.stdout+proc.stderr
        if proc.returncode:raise RuntimeError('Full tests failed:\n'+tests)
    artifacts,data=replay()
    if inventory()!=hashes:raise RuntimeError('Runtime changed during verification')
    if args.write_evidence:
        m=re.search(r'Ran (\d+) tests in ([\d.]+)s',tests)
        if not m or '\nOK' not in tests:raise RuntimeError('Missing test success/count')
        data['unit_tests']={'passed':int(m[1]),'failed':0,'elapsed_seconds':float(m[2])}
        OUTPUT.mkdir(parents=True)
        for name in sorted(CHANGED|ADDED):
            dest=OUTPUT/'code'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
        for name,code in artifacts.items():(OUTPUT/name).write_text(code,encoding='utf-8')
        data['derived_artifact_sha256']={name:digest(OUTPUT/name) for name in artifacts}
        for name,value in [('replay.json',data),('live_inventory.json',hashes)]:
            (OUTPUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (OUTPUT/'REPORT.md').write_text(report(data),encoding='utf-8');(OUTPUT/'unit_tests.txt').write_text(tests,encoding='utf-8')
        files=sorted(f for f in OUTPUT.rglob('*') if f.is_file())
        (OUTPUT/'SHA256SUMS.txt').write_text('\n'.join(f'{digest(f)}  {f.relative_to(OUTPUT).as_posix()}' for f in files)+'\n',encoding='utf-8')
        verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'model_requests':0,'original_passed':24,'target':'TaskManager','before_errors':10,
        'after_errors':9,'new_batch_pass_claimed':False,'unit_tests':data.get('unit_tests'),'evidence_written':args.write_evidence}))


if __name__=='__main__':main()
