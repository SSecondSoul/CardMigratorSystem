"""Partial source-proven inline render call closure; no model requests."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot
from migration_pipeline.replay_formal_30_v4_source_payload_closure_v1 import OUTPUT as BASE, SOURCE, PROTOCOL, BATCH
from migration_pipeline.utils.source_render_call_semantics import source_render_call_semantics
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.utils.repair_scheduler import candidate_gate

OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_source_render_call_closure_v1_20261110'
CHANGED={'migration_pipeline/stages/repair.py','migration_pipeline/stages/validate.py',
 'migration_pipeline/utils/repair_prompt.py','migration_pipeline/utils/repair_scheduler.py',
 'tests/test_source_dom_closure.py','tests/test_source_payload_closure.py',
 'tests/test_source_inline_formatter_closure.py','tests/test_monitoring_remaining_bounded_fix.py',
 'tests/test_repair_regression_guard.py','tests/test_migration_pipeline_regressions.py'}
ADDED={'migration_pipeline/utils/source_render_call_semantics.py','migration_pipeline/utils/source_render_call_semantics.cjs',
 'tests/test_source_render_call_closure.py','migration_pipeline/replay_formal_30_v4_source_render_call_closure_v1.py'}
REMAINING={'hidden_template_reactive_dependency','nested_state_mutation'}


def inventory():
    verify_snapshot(BASE.resolve())
    previous=json.loads((BASE/'live_inventory.json').read_text(encoding='utf-8'))
    now={name:digest(ROOT/name) for name in sorted(set(previous)|ADDED)}
    changed={name for name,sha in previous.items() if now[name]!=sha}
    if changed!=CHANGED:raise RuntimeError('Unexpected runtime delta: '+str(changed^CHANGED))
    return now


def replay():
    verified={name:verify_snapshot(p.resolve()) for name,p in [('raw',SOURCE),('protocol',PROTOCOL),('source_payload_closure',BASE)]}
    previous=json.loads((BASE/'replay.json').read_text(encoding='utf-8'))
    old={row['id']:row for row in previous['retained_artifact_replays']}
    raw=json.loads((SOURCE/f'{BATCH}_summary.json').read_text(encoding='utf-8'))
    rows,artifacts=[],{}
    if len(old)!=30 or len(raw['samples'])!=30:raise RuntimeError('Expected full-30 inputs')
    for sample in raw['samples']:
        name=sample['id'];print('Offline static check: '+name,flush=True)
        prior=old[name];path=BASE/'TaskManager_source_payload_offline.san' if name=='TaskManager' else ROOT/prior['input_path']
        code=path.read_text(encoding='utf-8');vue=ROOT/prior['vue_path']
        state=json.loads((SOURCE/'repair_reports'/sample['complexity']/sample['report_file'].replace('\\','/').split('/')[-1]).read_text(encoding='utf-8'))['state']
        result=source_render_call_semantics(code,vue.read_text(encoding='utf-8'),state['ssm'],repair=True)
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
        again=source_render_call_semantics(fixed,vue.read_text(encoding='utf-8'),state['ssm'],repair=True)
        if again['code']!=fixed or again['changes']:raise RuntimeError('Not a fixed point: '+name)
        if name!='TaskManager' and fixed!=code:raise RuntimeError('Additional rewrite needs review: '+name)
        if sample['final_passed'] and (fixed!=state['final_code'] or not after['validation_passed']):
            raise RuntimeError('Original passed raw artifact changed or now fails: '+name)
        compact=lambda d:{k:v for k,v in d.items() if k not in {'generated_code','ssm','validate_result'}}
        row={'id':name,'raw_original_automatic_passed':sample['final_passed'],'input_path':path.relative_to(ROOT).as_posix(),
            'input_sha256':digest(path),'vue_path':vue.relative_to(ROOT).as_posix(),'vue_sha256':digest(vue),
            'before':compact(before),'after':compact(after),'changes':result['changes'],'proofs':result['proofs'],
            'reviews':result['reviews'],'mapped_bindings':result['mapped_bindings'],'gate':gate}
        if name=='TaskManager':
            if len(before['validation_errors'])!=6 or len(after['validation_errors'])!=2 or {e['code'] for e in after['validation_errors']}!=REMAINING:
                raise RuntimeError('Unexpected partial TaskManager diagnostics')
            if after['validation_passed']:raise RuntimeError('Still partial, not a pass')
            if len(result['proofs'])!=2 or {p['kind'] for p in result['proofs']}!={'math','includes'}:raise RuntimeError('Unexpected render-call proof')
            planned,steps=RepairStage._deterministic_repair_plan(code,before['validation_errors'],[],state['ssm'],str(vue),enable_residual_v2=True)
            if planned!=fixed:raise RuntimeError('Prepass differs from rule')
            reverse=candidate_gate(after,before)
            if not reverse['should_stop']:raise RuntimeError('Render operand regression not rejected')
            row.update(prepass_steps=steps,reverse_gate=reverse)
            artifacts['TaskManager_source_render_call_offline.san']=fixed
        rows.append(row)
    verify_snapshot(SOURCE.resolve());verify_snapshot(BASE.resolve())
    return artifacts,{'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'partial_offline_source_render_call_closure_reused_development_not_new_batch',
        'source_verified_files':verified,'original_aggregate':raw['aggregate'],'model_requests':0,
        'original_score_modified':False,'canonical_san_or_manual_pages_modified':False,
        'manual_acceptance_inherited':False,'full_browser_interaction_executed':False,
        'runtime_inventory_count':len(inventory()),'original_passed_raw_artifacts_static_checked_unchanged':24,
        'initial_dom_reexecuted_ids':['TaskManager'],'retained_artifact_replays':rows}


def report(data):
    return f'''# 源内联渲染调用显式操作数闭环 v1（2026-11-10，部分修复）

原始批次仍为 24/30、6 失败、0 执行异常、1,821,544 tokens。本轮接续前一 payload 包冻结派生件，不是新生成批次、独立测试或人工通过；真实模型请求 0，标准产物/测试页不改。

新增 source_render_call_semantics.py/.cjs，按完整 Vue 的真实注册、唯一且不逃逸的子组件绑定及 SSM inline_definition 完整 AST 一致建立映射。只比较同一元素路径、循环/条件/插槽作用域的完整渲染表达式，并保留静态 class 与相邻文本锚点。无关图标子树不强求整树同形，但不将整个 StatCard 追认为已经等价。单 class 对象条件可严格归一化为对应 token/空串；清理 AST 位置及 raw 引号元数据后再比较，不能猜条件或标签内容。

只提升明确白名单的 Math 纯调用及源声明数组路径上的 includes，一并将全部操作数作为模板方法实参。数组路径必须由 Array prop 或简单 data 返回/单返回工厂的所有条件分支及覆盖顺序证明；不凭字段名猜数组。拒绝 random/突变/未知调用、未知工厂/后置 spread、Math/Array 遮蔽或显式重写、模板转义、未知操作数、构造器逃逸和冲突别名。保留 native null/NaN/负零语义，不增加空数组/零回退。

真实 TaskManager 两处：StatCard 的趋势百分值与 TaskForm 的标签选中条件。新方法只封装原调用，不访问 this/data；显式传入 trend 或 formData.tags/tag。保留 %、class token、条件和参数顺序，脚本其他方法和 CSS 原字节不动。getTaskCount 的间接 isOverdue 依赖链、moveTask 原地修改未在本轮处理；初始化/拖拽方法体及表单构造仍未证明。

前处理、stub 模型返回后处理、共享 repair Prompt、验证器与候选保护同步。新增 source_render_call_not_landed/source_render_call_analysis_unavailable；辅助方法或操作数错误、源文本/class 被改、已匹配绑定丢失均拒绝。旧非 residual_v2 前处理不启用本规则，generation/服务器 Prompt 不改。

开发首轮 19 项中 2 失败（40.477 秒）：直接加载 San 内部 eval-expr 触发 eval-args 循环依赖；以及测试误将一个循环绑定不匹配要求为所有独立修复均停止。改用安装包公开 san.evalExpr，并保留独立 Math 可进展、未知循环 includes 不改的断言。随后包含四项历史组合检查的 23/23 通过（62.614 秒）。源 class 对象转字符串初检曾因 raw 引号差异被误判，修正 AST 规范化而不放宽源条件/操作数匹配。这些为开发控制台观察，不冒充保存的完整失败日志。

完整测试 {data['unit_tests']['passed']}/{data['unit_tests']['passed']}、0 失败，{data['unit_tests']['elapsed_seconds']} 秒，完整输出已保存。安装 San 的解析/公开求值器与数据更新夹具确认趋势数字/%、标签类随显式操作数变化；另验证 NaN、负零、includes NaN、空数组及 null 的原生异常，未运行浏览器重绘。stub 后处理不是模型请求，不声称整个调度器已零模型修至通过。

累计 30 个输入重新静态验证/编译，仅 TaskManager 新改写；24 个原始通过件字节不变且仍静态通过。仅 TaskManager 重做轻量初始 DOM，其余视觉标志沿用前层。两项旧 Math/member 诊断关闭；新校验为同一渲染契约另记两个重叠节点诊断，所以现行输入计数为 6→2，而不是原始实验曾有 6 类错误。仍有 hidden_template_reactive_dependency 和 nested_state_mutation，validation_passed=false。正向接受、反向拒绝、固定点、前处理一致已核对。

额外复核 event-v3 历史探针曾有 1/1 失败（5.387 秒）：旧标签辅助调用未匹配源 includes，新增错误集合未收录。只补这一错误码和精确 TaskForm class 节点断言，保留所有旧错误及探针必须 fail closed 的要求；未修改生产规则以豁免。为此主动中止过一轮尚未冻结的完整运行，不计作通过，更新后重新完整执行。

一轮完整执行实际为 554 项、1 失败（701.660 秒），未冻结为成功包。唯一失败为 MonitoringDashboard 第三次历史修正件的精确诊断集合漏列新源渲染诊断；真实位置为 script.kpi-card.template/div[0]/div[1]/div[2]#text:1，仍是其原有 Math.abs(trend) 渲染残留。只补新错误码和精确位置断言，保留原 Math/member、初始化、watcher 和响应性等所有错误；仅 wrapper 展开不能冒称整个历史件通过。生产规则未因此放宽，完整套件更新后重新执行，旧失败控制台摘要保留。

19 项冻结 payload、351 项运行清单可复算；旧原始及前层 SHA 不改。新 San 仅为本目录的中间件，不继承历史人工通过，不切换测试页、不回填分数。下一步审查计数渲染的完整依赖调用图及不可变任务移动，再继续初始化/拖拽行为；不要立即付费复跑或验收仍失败的中间件。
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
    print(json.dumps({'model_requests':0,'original_passed':24,'target':'TaskManager','previous_diagnostic_families':4,
        'current_before_findings':6,'current_after_findings':2,'unit_tests':data.get('unit_tests'),
        'evidence_written':args.write_evidence,'new_batch_pass_claimed':False}))


if __name__=='__main__':main()
