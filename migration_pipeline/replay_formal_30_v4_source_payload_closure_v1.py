"""Partial source-proven single event payload closure; no model requests."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot
from migration_pipeline.replay_formal_30_v4_source_dom_closure_v1 import OUTPUT as BASE, SOURCE, PROTOCOL, BATCH
from migration_pipeline.utils.source_payload_semantics import source_payload_semantics
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.utils.repair_scheduler import candidate_gate

OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_source_payload_closure_v1_20261110'
CHANGED={'migration_pipeline/stages/repair.py','migration_pipeline/stages/validate.py',
 'migration_pipeline/utils/repair_prompt.py','migration_pipeline/utils/repair_scheduler.py',
 'migration_pipeline/utils/repair_regression_guard.py','tests/test_source_dom_closure.py',
 'tests/test_source_inline_formatter_closure.py','tests/test_monitoring_remaining_bounded_fix.py'}
ADDED={'migration_pipeline/utils/source_payload_semantics.py','migration_pipeline/utils/source_payload_semantics.cjs',
 'tests/test_source_payload_closure.py','migration_pipeline/replay_formal_30_v4_source_payload_closure_v1.py'}
REMAINING={'unsupported_san_inline_template_math_global','unsupported_san_inline_template_member_call',
 'hidden_template_reactive_dependency','nested_state_mutation'}


def inventory():
    verify_snapshot(BASE.resolve())
    previous=json.loads((BASE/'live_inventory.json').read_text(encoding='utf-8'))
    now={name:digest(ROOT/name) for name in sorted(set(previous)|ADDED)}
    changed={name for name,sha in previous.items() if now[name]!=sha}
    if changed!=CHANGED:raise RuntimeError('Unexpected runtime delta: '+str(changed^CHANGED))
    return now


def replay():
    verified={name:verify_snapshot(p.resolve()) for name,p in [('raw',SOURCE),('protocol',PROTOCOL),('source_dom_closure',BASE)]}
    previous=json.loads((BASE/'replay.json').read_text(encoding='utf-8'))
    old={row['id']:row for row in previous['retained_artifact_replays']}
    raw=json.loads((SOURCE/f'{BATCH}_summary.json').read_text(encoding='utf-8'))
    rows,artifacts=[],{}
    if len(old)!=30 or len(raw['samples'])!=30:raise RuntimeError('Expected full-30 inputs')
    for sample in raw['samples']:
        name=sample['id'];print('Offline static check: '+name,flush=True)
        prior=old[name];path=BASE/'TaskManager_source_dom_offline.san' if name=='TaskManager' else ROOT/prior['input_path']
        code=path.read_text(encoding='utf-8');vue=ROOT/prior['vue_path']
        state=json.loads((SOURCE/'repair_reports'/sample['complexity']/sample['report_file'].replace('\\','/').split('/')[-1]).read_text(encoding='utf-8'))['state']
        result=source_payload_semantics(code,vue.read_text(encoding='utf-8'),state['ssm'],repair=True)
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
        gate=candidate_gate(before,after)
        if gate['should_stop']:raise RuntimeError('Candidate rejected: '+name)
        again=source_payload_semantics(fixed,vue.read_text(encoding='utf-8'),state['ssm'],repair=True)
        if again['code']!=fixed or again['changes']:raise RuntimeError('Not a fixed point: '+name)
        if name!='TaskManager' and fixed!=code:raise RuntimeError('Additional rewrite needs review: '+name)
        if sample['final_passed'] and (fixed!=state['final_code'] or not after['validation_passed']):
            raise RuntimeError('Original passed raw artifact changed or now fails: '+name)
        compact=lambda d:{k:v for k,v in d.items() if k not in {'generated_code','ssm','validate_result'}}
        row={'id':name,'raw_original_automatic_passed':sample['final_passed'],'input_path':path.relative_to(ROOT).as_posix(),
            'input_sha256':digest(path),'vue_path':vue.relative_to(ROOT).as_posix(),'vue_sha256':digest(vue),
            'before':compact(before),'after':compact(after),'changes':result['changes'],'proofs':result['proofs'],
            'reviews':result['reviews'],'mapped_contracts':result['mapped_contracts'],'gate':gate}
        if name=='TaskManager':
            if len(before['validation_errors'])!=6 or len(after['validation_errors'])!=4 or {e['code'] for e in after['validation_errors']}!=REMAINING:
                raise RuntimeError('Unexpected partial TaskManager diagnostics')
            if after['validation_passed']:raise RuntimeError('Still partial, not a pass')
            if result['proofs'][0]['emissions']!=4 or result['proofs'][0]['fields']!=['key','value']:raise RuntimeError('Unexpected event proof')
            planned,steps=RepairStage._deterministic_repair_plan(code,before['validation_errors'],[],state['ssm'],str(vue),enable_residual_v2=True)
            if planned!=fixed:raise RuntimeError('Prepass differs from rule')
            reverse=candidate_gate(after,before)
            if not reverse['should_stop']:raise RuntimeError('Payload regression not rejected')
            row.update(prepass_steps=steps,reverse_gate=reverse)
            artifacts['TaskManager_source_payload_offline.san']=fixed
        rows.append(row)
    verify_snapshot(SOURCE.resolve());verify_snapshot(BASE.resolve())
    return artifacts,{'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'partial_offline_source_payload_closure_reused_development_not_new_batch',
        'source_verified_files':verified,'original_aggregate':raw['aggregate'],'model_requests':0,
        'original_score_modified':False,'canonical_san_or_manual_pages_modified':False,
        'manual_acceptance_inherited':False,'full_browser_interaction_executed':False,
        'runtime_inventory_count':len(inventory()),'original_passed_raw_artifacts_static_checked_unchanged':24,
        'initial_dom_reexecuted_ids':['TaskManager'],'retained_artifact_replays':rows}


def report(data):
    return f'''# 源自定义事件双端单 payload 闭环 v1（2026-11-10，部分修复）

原始批次仍为 24/30、6 失败、0 执行异常、1,821,544 tokens。输入是前一 DOM 闭环冻结派生件及已披露累计输入，不是重新生成批次、独立测试或人工通过。真实模型请求 0，标准产物/人工测试页不改。

新增 source_payload_semantics.py/.cjs，以完整 Vue SFC 的真实子组件注册和 SSM inline_definition AST 一致为前提，按源元素结构、循环/条件作用域证明 source inline emit 与目标 method/direct fire 参数逐项相同，再用实际父接收方法形参命名对象字段。只支持 2–4 个普通形参和简单参数路径。所有同事件发送入口和对应父实例一起修改；接收方法签名/方法体/其他调用保持原字节。拒绝未知 handler、冲突别名、构造器逃逸、多余消费者、源/目标动态或额外 emitter、destructuring、动态模板和结构不匹配；这些 unsupported/review 不是等价通过。

本冻结 TaskManager 有 4 个 settings-panel.update 发送入口、1 个父实例。打包 key/value，并把父绑定改为 updateSettings($event.key,$event.value)。不是只把 fire 改成对象而让父方法继续接收错位参数。已有 syncInterval 数值转换及英文键名通知保留源行为；不擅自汉化源文案。规则没有 TaskManager 组件名分支。

residual_v2 确定性前处理、模型返回后处理、共享 repair Prompt、验证器及候选保护均接入。新增 source_event_payload_not_landed/source_event_payload_analysis_unavailable；只修一端仍诊断，丢失已映射契约或反向重引入缺陷拒绝。事件追溯只接受双端源码证明的明确解包绑定，不按别名猜测。

开发首轮 15 项中 2 失败（33.727 秒）：未声明的其他注册别名边界不足；stub 后处理会追加末尾换行导致过强的全文断言。前者收紧为同一规范化源标签别名，后者仅忽略已有格式化末尾换行，不放宽协议断言。后续 15/15 通过（32.613 秒）。扩展组合执行 60 项中 2 失败（98.453 秒）来自历史 DOM/formatter 精确诊断数预期；保留旧 9 类与逐节点 DOM 诊断，只另核对新增 payload 残留，组合前处理则必须确实闭合两端。这些是开发控制台摘要，不冒充保留了原始失败完整日志。

最终完整测试 {data['unit_tests']['passed']}/{data['unit_tests']['passed']}、0 失败，{data['unit_tests']['elapsed_seconds']} 秒；完整日志另存。真实 San fire/listener 夹具验证对象解包和冻结件的默认视图、两个 false 布尔值、syncInterval 字符串转数字；仅构造不 attach，未启动浏览器、初始化/存储/同步 hook，也不证明整套设置 UI 已通过。stub 后处理不是模型调用。

另一次 24 项定向检查中 1 失败（56.696 秒）：历史 MonitoringDashboard 非法 JavaScript 产物在新增分析器下正确保留 analysis_unavailable，但旧精确诊断集合未列入。仅追加该不可证明诊断，保留原编译失败及所有旧错误，不追改原冻结结果。真实设置入口和两项历史组合用例另有 3/3 通过（28.020 秒）。最终完整结果以本次完整日志为准。

30 个累计输入重新静态验证/编译，仅 TaskManager 新改写；原始 24 通过件字节不变且仍静态通过。仅 TaskManager 重做轻量初始 DOM，其余视觉标志沿用前层冻结结果，不将累计修补拼成新分数。先前 5 类静态残留中的 multi-argument fire 关闭；新验证又将同一事件的双端契约列为一条重叠诊断，当前输入按新验证为 6→4，不是原始实验曾有 6 类错误。仍有 Math/成员模板调用、隐藏响应依赖、任务原地修改，validation_passed=false。

正向候选接受、逆向拒绝、固定点、前处理一致均验证。原始及前层 SHA 不改。新 San 仅留在本目录，不继承旧人工确认。下一步处理渲染显式依赖、moveTask 复制/提交顺序，并继续审查初始化/拖拽方法体；不要立即付费复跑或验收仍失败的中间件。
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
    print(json.dumps({'model_requests':0,'original_passed':24,'target':'TaskManager','previous_diagnostic_families':5,
        'current_before_findings':6,'current_after_findings':4,'unit_tests':data.get('unit_tests'),
        'evidence_written':args.write_evidence,'new_batch_pass_claimed':False}))


if __name__=='__main__':main()
