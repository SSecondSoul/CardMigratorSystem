"""Partial source-scoped DOM closure on frozen development inputs; no models."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT,digest,verify_snapshot
from migration_pipeline.replay_formal_30_v4_inline_formatter_closure_v1 import OUTPUT as BASE,SOURCE,PROTOCOL
from migration_pipeline.utils.source_dom_semantics import source_dom_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.stages.validate import ValidateStage,ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage,VisualEvalStageInput
from migration_pipeline.stages.repair import RepairStage

OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_source_dom_closure_v1_20261110'
BATCH='formal_30_v4_full_regression_v2'
CHANGED={'migration_pipeline/stages/repair.py','migration_pipeline/stages/validate.py',
 'migration_pipeline/utils/repair_prompt.py','migration_pipeline/utils/repair_scheduler.py',
 'migration_pipeline/utils/repair_regression_guard.py','tests/test_source_inline_formatter_closure.py'}
CHANGED |= {'tests/test_source_phase_semantics.py','tests/test_startup_phase_closure.py',
 'tests/test_monitoring_remaining_bounded_fix.py','tests/test_migration_pipeline_regressions.py',
 'tests/test_repair_regression_guard.py'}
ADDED={'migration_pipeline/utils/source_dom_semantics.py','migration_pipeline/utils/source_dom_semantics.cjs',
 'tests/test_source_dom_closure.py','migration_pipeline/replay_formal_30_v4_source_dom_closure_v1.py'}
REMAINING={'unsupported_san_inline_template_math_global','unsupported_san_inline_template_member_call',
 'invalid_san_multi_argument_fire','hidden_template_reactive_dependency','nested_state_mutation'}


def inventory():
    verify_snapshot(BASE.resolve())
    prior=json.loads((BASE/'live_inventory.json').read_text(encoding='utf-8'))
    now={name:digest(ROOT/name) for name in sorted(set(prior)|ADDED)}
    changed={name for name,sha in prior.items() if now[name]!=sha}
    if changed!=CHANGED:raise RuntimeError(f'Unexpected runtime delta: {changed ^ CHANGED}')
    return now


def replay():
    verified={name:verify_snapshot(p.resolve()) for name,p in [('raw',SOURCE),('protocol',PROTOCOL),('formatter_closure',BASE)]}
    raw=json.loads((SOURCE/f'{BATCH}_summary.json').read_text(encoding='utf-8'))
    prior=json.loads((BASE/'replay.json').read_text(encoding='utf-8'))
    old={r['id']:r for r in prior['retained_artifact_replays']}
    if len(raw['samples'])!=30 or len(old)!=30:raise RuntimeError('Expected full-30 inputs')
    artifacts,rows={},[]
    for sample in raw['samples']:
        name=sample['id'];print('Offline static check: '+name,flush=True)
        row=old[name]
        start=BASE/'TaskManager_inline_formatter_offline.san' if name=='TaskManager' else ROOT/row['input_path']
        code=start.read_text(encoding='utf-8');vue=ROOT/row['vue_path']
        state=json.loads((SOURCE/'repair_reports'/sample['complexity']/Path(sample['report_file']).name).read_text(encoding='utf-8'))['state']
        r=source_dom_semantics(code,vue.read_text(encoding='utf-8'),state['ssm'],repair=True)
        if r.get('error'):raise RuntimeError(f"AST failure {name}: {r['error']}")
        fixed=r['code']
        def assess(text,visual=None):
            val=ValidateStage().run(ValidateStageInput(generated_code=text,ssm=state['ssm'],vue_file_path=str(vue))).to_state_update()
            result={'generated_code':text,'ssm':state['ssm'],'vue_file_path':str(vue),**val}
            if visual is None:
                vis=VisualEvalStage().run(VisualEvalStageInput(generated_code=text,vue_file_path=str(vue)))
                result.update(visual_eval_passed=vis.visual_eval_passed,visual_errors=vis.visual_eval_errors,
                    structure_similarity=vis.structure_similarity,visual_reexecuted=True)
            else:result.update(visual_eval_passed=visual,visual_reexecuted=False)
            return result
        before=assess(code,row['after']['visual_eval_passed'])
        after=assess(fixed) if fixed!=code else before
        gate=candidate_gate(before,after)
        if gate['should_stop']:raise RuntimeError('Candidate rejected: '+name)
        again=source_dom_semantics(fixed,vue.read_text(encoding='utf-8'),state['ssm'],repair=True)
        if again['code']!=fixed or again['changes']:raise RuntimeError('Not a fixed point: '+name)
        if name!='TaskManager' and fixed!=code:raise RuntimeError('Additional rewrite requires review: '+name)
        if sample['final_passed'] and (fixed!=state['final_code'] or not after['validation_passed']):
            raise RuntimeError('Previously passed raw artifact changed or failed: '+name)
        compact=lambda s:{k:v for k,v in s.items() if k not in {'generated_code','ssm','validate_result'}}
        entry={'id':name,'raw_original_automatic_passed':sample['final_passed'],
            'input_path':start.relative_to(ROOT).as_posix(),'input_sha256':digest(start),
            'vue_path':vue.relative_to(ROOT).as_posix(),'vue_sha256':digest(vue),
            'before':compact(before),'after':compact(after),'changes':r['changes'],
            'proofs':r['proofs'],'reviews':r['reviews'],'source_dom_findings':r['findings'],'gate':gate}
        if name=='TaskManager':
            if len(before['validation_errors'])!=22 or {e['code'] for e in after['validation_errors']}!=REMAINING:
                raise RuntimeError('Unexpected TaskManager diagnostics')
            if after['validation_passed']:raise RuntimeError('Partial closure cannot pass')
            planned,steps=RepairStage._deterministic_repair_plan(code,before['validation_errors'],[],state['ssm'],str(vue),enable_residual_v2=True)
            if planned!=fixed:raise RuntimeError('Prepass differs from proof')
            reverse=candidate_gate(after,before)
            if not reverse['should_stop']:raise RuntimeError('Old DOM defects not rejected')
            entry.update(reverse_gate=reverse,prepass_steps=steps)
            artifacts['TaskManager_source_dom_offline.san']=fixed
        rows.append(entry)
    verify_snapshot(SOURCE.resolve());verify_snapshot(BASE.resolve())
    return artifacts,{'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'partial_offline_source_dom_closure_reused_development_not_new_batch',
        'source_verified_files':verified,'original_aggregate':raw['aggregate'],'model_requests':0,
        'original_score_modified':False,'canonical_san_or_manual_pages_modified':False,
        'manual_acceptance_inherited':False,'full_browser_interaction_executed':False,
        'runtime_inventory_count':len(inventory()),'original_passed_raw_artifacts_static_checked_unchanged':24,
        'initial_dom_reexecuted_ids':['TaskManager'],'retained_artifact_replays':rows}


def report(data):
    return f'''# 源作用域 DOM 事件/循环闭环 v1（2026-11-10，部分修复）

原始批次仍为 24/30、6 失败、0 执行异常、1,821,544 tokens。这是累计离线开发修复，不是新生成批次、独立测试或人工通过。

仅匹配完整元素结构和循环/条件作用域；父组件由完整 Vue SFC 提供证据，内联子组件由 SSM 注册标签、唯一词法绑定与源 template 提供证据。不改自定义组件事件名、不全局替换字符串、不猜冲突 key 或未知 handler；mixins/extends、插槽作用域、模板结构变化、引用逃逸、动态模板、遮蔽/无法映射的属性保持未证明。StatCard 的结构不匹配留在 reviews，不自动修补。

修复范围：声明状态的布尔赋值 .self 及已知零参 .self 方法改为带显式 $event 的单动作守卫；native stop/prevent 的 dotted 语法改为 San value modifier；modifier-only dragover 绑定真实 no-op；源 drop/dragend 绑定恢复；源匹配 tuple alias 和冗余 key/trackby 合并为 San 内联 trackby。恢复绑定不证明拖拽方法内部 dataTransfer 副作用已经等价，仍需继续审查。

安装的 San 运行时证实：enter:handler 会被解析但不做按键过滤。现改为 event.key 优先、缺失时回退 keyCode 的显式 Enter 守卫，并以真实 San listener 验证 Esc/普通键不触发、Enter 触发；.self 内部点击不关闭，stop/prevent 生效。这些是无浏览器的运行时夹具，不是截图或完整交互验收。

开发验证曾有一次 21 项测试中 4 失败/1 错误（35.313 秒）：新增的 AST 字面量规范化把 Babel 构造节点的默认元数据差异当作语义差异，导致已证明守卫和不同引号的相同 payload 不被识别。改为去掉位置/原始字面量元数据后进行规范化代码比较，不删除行为检查；随后 21/21 通过（41.125 秒）。开发期间运行中的只读预检不作为冻结证据，最终使用稳定代码清单重新执行。

新诊断 source_dom_event_not_landed/source_dom_loop_not_landed 按 scope/element/event 身份输出；分析不可用不算通过。验证器、候选保护、前处理、stub 模型返回后处理与共享 repair Prompt 同步；正确 source Enter/self 守卫由源码+AST证明后才进入事件可追溯性，不凭方法名给别名豁免。旧非残留 profile 保持原入口，服务器/generation Prompt 不改。

补充反例审查时中止过两次尚未冻结的完整测试：删除整个事件或全部 key 元数据不能用来躲避诊断；现在即使不自动补猜，仍保留缺失契约错误。候选失去原先已建立的元素映射作用域或改变祖先循环/条件导致节点映射消失，也会拒绝；原本已不匹配的 StatCard 不被追认为新回归，但仍未证明。最终完整套件在这些拒绝检查稳定后重新运行，中止运行不计作通过。

第一轮完整执行 510 项、8 失败（527.057 秒），没有冻结为成功包。复核发现：已存在的 self 守卫经一个零参 setter 间接做同一布尔写入，之前未被识别；现仅展开这一完整单表达式动作，不凭别名豁免。另有历史图表的真实 item 属性 key 缺失，被新诊断暴露；现在仅在源明示且作用域完全匹配时补该 item 路径。旧 helper 的局部修复不能冒称整体通过，相关历史用例需保留新增残留及验证规则组合。索引 key 则进入 runtime identity unproven review：San 只为 item 前缀的 trackby 建立键 getter，不能据默认索引分支就宣称所有 splice/reorder 与 Vue 等价；这一未知语义未被自动修补或证明通过。

第二轮完整执行 512 项、1 失败（537.896 秒）：历史 event-v3 探针的精确诊断集合未列入新增源事件错误。检查后只补充该错误码及四个明确节点位置断言，保留探针必须 fail closed、旧 API 丢失仍检测和 legacy 前处理不改写等断言。并未把该历史探针的失败产物改为通过；最终完整套件在更新这一回归预期后重新执行。

- 完整测试 {data['unit_tests']['passed']}/{data['unit_tests']['passed']}，{data['unit_tests']['elapsed_seconds']} 秒。
- 累计链的 30 项重新静态验证/编译，仅 TaskManager 有新改写；24 个原始通过件字节不变且仍通过。其余视觉标志沿用冻结报告，仅 TaskManager 重新做初始轻量 DOM。
- TaskManager 先前 9 类静态诊断中消除 4 类；现行校验另将原先未覆盖的源契约拆成 13 个节点诊断，因此本轮同一输入按新校验为 22→5，而非将 22 当作原始实验的错误数。剩余 Math/成员模板调用、多个 fire payload、隐藏响应依赖与任务原地修改，仍失败。
- 正向前处理接受、反向重引入缺陷拒绝、固定点成立；模型后处理以 stub 测试证明，无真实模型请求。没有称整轮调度器已将 TaskManager 修至通过。
- 上一 formatter 用例更新为保留 9 个旧诊断并另核对新增 DOM 诊断不丢失，前处理允许组合新规则；没有将旧错误豁免成通过。

新派生 San 只在本证据目录，不覆盖 canonical San/测试页，不继承其他产物人工通过，不回填旧分数。下一步仍需闭合 fire 两端单 payload、显式响应依赖、复制/提交顺序及未覆盖初始化/拖拽方法行为，不要立即付费复跑或验收这个仍失败的中间件。
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
    print(json.dumps({'model_requests':0,'original_passed':24,'target':'TaskManager',
        'previous_diagnostic_families':9,'current_before_findings':22,'current_after_findings':5,
        'new_batch_pass_claimed':False,'unit_tests':data.get('unit_tests'),'evidence_written':args.write_evidence}))


if __name__=='__main__':main()
