"""Offline source-proven parent watcher closure; no model or canonical writes."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot
from migration_pipeline.replay_formal_30_v4_source_native_drag_closure_v1 import OUTPUT as BASE, SOURCE, PROTOCOL, BATCH
from migration_pipeline.audit_formal_30_v4_parent_watch_oracle_v1 import OUTPUT as ORACLE, VENDOR, VENDOR_NAMES, verify_vendor
from migration_pipeline.replay_formal_30_v4_source_array_transaction_closure_v1 import offline_scheduler
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.utils.repair_scheduler import candidate_gate

OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_parent_watch_closure_v1_20261111'
CHANGED={'migration_pipeline/stages/repair.py','migration_pipeline/stages/validate.py',
 'migration_pipeline/utils/repair_prompt.py','migration_pipeline/utils/repair_scheduler.py',
 'tests/test_source_child_initialization_closure.py','tests/test_source_array_transaction_closure.py',
 'tests/test_source_render_dependency_closure.py','tests/test_source_dom_closure.py','tests/test_source_payload_closure.py',
 'tests/test_source_render_call_closure.py','tests/test_source_inline_formatter_closure.py',
 'tests/test_repair_regression_guard.py','tests/test_monitoring_remaining_bounded_fix.py','tests/test_source_native_drag_closure.py'}
ADDED={'migration_pipeline/utils/source_parent_watch_semantics.py','migration_pipeline/utils/source_parent_watch_semantics.cjs',
 'tests/test_source_parent_watch_closure.py','migration_pipeline/replay_formal_30_v4_parent_watch_closure_v1.py',
 'migration_pipeline/audit_formal_30_v4_parent_watch_oracle_v1.py','migration_pipeline/audit_formal_30_v4_parent_watch_oracle_v1.cjs',
 'tests/test_parent_watch_oracle_audit.py'} | {str((VENDOR/name).relative_to(ROOT).as_posix()) for name in VENDOR_NAMES}


def inventory():
    verify_snapshot(BASE.resolve());previous=json.loads((BASE/'live_inventory.json').read_text(encoding='utf-8'))
    now={name:digest(ROOT/name) for name in sorted(set(previous)|ADDED)}
    changed={name for name,sha in previous.items() if now[name]!=sha}
    if changed!=CHANGED:raise RuntimeError('Unexpected runtime delta: '+str(changed^CHANGED))
    return now


def oracle_runtime(code,vue):
    fixture=ORACLE/'code/migration_pipeline/audit_formal_30_v4_parent_watch_oracle_v1.cjs'
    js=r'''const fs=require('fs'),{createRequire}=require('module');const x=JSON.parse(fs.readFileSync(0,'utf8')),m={exports:{}};
let source=fs.readFileSync(x.fixture,'utf8');const old="['vue_source','san_current','san_naive_early']";
if(source.split(old).length!==3)throw Error('Frozen oracle fixture shape drift');
source=source.split(old).join("['vue_source','san_current']");
new Function('require','module',source)(createRequire(x.fixture),m);
m.exports.audit(x.payload).then(r=>process.stdout.write(JSON.stringify(r))).catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});'''
    payload={'fixture':str(fixture),'payload':{'code':code,'vue':vue,
        'vueRuntime':(ORACLE/'vendor/package/dist/vue.runtime.common.dev.js').read_bytes().decode('utf-8'),
        'sanRuntime':(ROOT/'node_modules/san/dist/san.dev.js').read_bytes().decode('utf-8')}}
    proc=subprocess.run(['node','-e',js],cwd=ROOT,input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True,timeout=40,check=True)
    if proc.stderr.strip():raise RuntimeError(proc.stderr)
    data=json.loads(proc.stdout);groups={(r['scenario'],r['variant']):r for r in data['runs']};pairs=[]
    for scenario in data['scenarios']:
        source=groups[(scenario,'vue_source')];target=groups[(scenario,'san_current')]
        for a,b in zip(source['phases'],target['phases']):
            project=lambda p:[e for e in p['events'] if e['kind'] not in {'hook','watch-register','watch-callback'}]
            pairs.append({'scenario':scenario,'phase':a['name'],'state_equal':a['state']==b['state'],
                'business_effects_equal':project(a)==project(b),'source_effects':project(a),'target_effects':project(b)})
    return {'observations':data,'pairs':pairs,'matched':all(p['state_equal'] and p['business_effects_equal'] for p in pairs),
        'fixture_adaptation':'Only the two explicit variant lists exclude obsolete naive counterfactual; source/target/hook/mutation logic unchanged.',
        'projection':'Remove framework hook labels, watch registration and low-level listener notification instrumentation; retain every business method/storage/timer event.'}


def replay():
    verified={name:verify_snapshot(path.resolve()) for name,path in [('raw',SOURCE),('protocol',PROTOCOL),('native_drag',BASE),('parent_watch_oracle',ORACLE)]}
    verify_vendor();old={r['id']:r for r in json.loads((BASE/'replay.json').read_text(encoding='utf-8'))['retained_artifact_replays']}
    raw=json.loads((SOURCE/f'{BATCH}_summary.json').read_text(encoding='utf-8'));rows=[];artifacts={}
    if len(old)!=30 or len(raw['samples'])!=30:raise RuntimeError('Expected full 30 frozen inputs')
    for sample in raw['samples']:
        name=sample['id'];print('Offline static check: '+name,flush=True);prior=old[name]
        path=BASE/'TaskManager_source_native_drag_offline.san' if name=='TaskManager' else ROOT/prior['input_path']
        code=path.read_text(encoding='utf-8');vue=ROOT/prior['vue_path'];source=vue.read_text(encoding='utf-8')
        state=json.loads((SOURCE/'repair_reports'/sample['complexity']/sample['report_file'].replace('\\','/').split('/')[-1]).read_text(encoding='utf-8'))['state']
        result=source_parent_watch_semantics(code,source,repair=True)
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
        parent_errors=[e for e in before['validation_errors'] if e['code'].startswith('source_parent_watch_')]
        if len(parent_errors)!=(1 if name=='TaskManager' else 0):raise RuntimeError('Additional watcher finding needs review: '+name)
        gate=candidate_gate(before,after);again=source_parent_watch_semantics(fixed,source,repair=True)
        if gate['should_stop'] or again.get('error') or again['code']!=fixed or again['changes']:raise RuntimeError('Rejected or unstable candidate: '+name)
        if name!='TaskManager' and fixed!=code:raise RuntimeError('Additional rewrite needs review: '+name)
        if sample['final_passed'] and (fixed!=state['final_code'] or not after['validation_passed']):raise RuntimeError('Original passed raw artifact changed or failed: '+name)
        compact=lambda d:{k:v for k,v in d.items() if k not in {'generated_code','ssm','validate_result'}}
        row={'id':name,'raw_original_automatic_passed':sample['final_passed'],'input_path':path.relative_to(ROOT).as_posix(),
            'input_sha256':digest(path),'vue_path':vue.relative_to(ROOT).as_posix(),'vue_sha256':digest(vue),
            'before':compact(before),'after':compact(after),'gate':gate,
            **{k:result[k] for k in ['changes','proofs','reviews','mapped_contracts']}}
        if name=='TaskManager':
            if {e['code'] for e in before['validation_errors']}!={'source_parent_watch_not_landed'} or not after['validation_passed']:raise RuntimeError('Unexpected TaskManager validation')
            plan,steps=RepairStage._deterministic_repair_plan(code,before['validation_errors'],[],state['ssm'],str(vue),enable_residual_v2=True)
            if plan!=fixed:raise RuntimeError('Prepass differs from independent rule')
            reverse=candidate_gate(after,before)
            if not reverse['should_stop']:raise RuntimeError('Missing async group regression was accepted')
            rb,ra=oracle_runtime(code,source),oracle_runtime(fixed,source)
            if rb['matched'] or not ra['matched'] or len(ra['pairs'])!=90:raise RuntimeError('Source business effect/state oracle failed')
            row.update(prepass_steps=steps,reverse_gate=reverse,landed_parent_watch_proofs=again['proofs'],
                oracle_before=rb,oracle_after=ra,offline_scheduler=offline_scheduler(code,vue,state['ssm'],fixed))
            artifacts['TaskManager_parent_async_watch_offline.san']=fixed
        if name=='trip_itinerary_planner' and (after['validation_passed'] or fixed!=code or not any(e['code']=='source_render_dependency_not_landed' for e in after['validation_errors'])):
            raise RuntimeError('Do not waive retained external render dependency')
        rows.append(row)
    return artifacts,{'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'offline_bounded_parent_watch_closure_reused_development_not_new_batch','source_verified_files':verified,
        'model_requests':0,'original_aggregate':raw['aggregate'],'original_score_modified':False,
        'canonical_san_or_manual_pages_modified':False,'manual_acceptance_inherited':False,'full_browser_interaction_executed':False,
        'runtime_inventory_count':len(inventory()),'original_passed_raw_artifacts_static_checked_unchanged':24,
        'initial_dom_reexecuted_ids':['TaskManager'],'retained_prior_derivative_risk_ids':['trip_itinerary_planner'],
        'parent_watch_normal_flow_oracle_matched':True,'exception_semantics_proven':False,'unknown_dynamic_keys_proven':False,
        'retained_artifact_replays':rows}


def report(data):
    tests=data['unit_tests']
    return f'''# 父异步监听有界闭环 v1（2026-11-11）

原批次仍24/30、6失败、0执行异常、1,821,544 tokens。0模型请求；复用开发冻结件，不是新生成/独立测试。不改canonical San、测试页、旧证据，不commit/push。

新增source_parent_watch_semantics.py/.cjs：只支持纯初始数据、默认async且deep=true的根字段监听（无handler参数），完整源回调、mounted/beforeDestroy、传递效果方法逐一AST对应；拒绝未知阶段/外部依赖/mixins/同步或immediate选项/递归/handler写回被监听根字段。字段和组件名不特判。限定源调用/条件回调；保守规范化Data API、只读别名、相邻临时赋值，不跨越可改变状态的效果猜测等价。

每实例闭包队列，按源注册次序去重，Promise微任务执行时读最新状态，清理pending后调用，销毁取消未运行任务；try/finally复位队列，不吞异常。不声称跨框架错误捕获/抛错策略等价，只覆盖正常完成回调；非原生Promise/异常存储/任意raw对象突变/未知动态键仍未证明，不能据此宣布全组件通过。

对照暴露额外的同值克隆入口：源已有键同值赋值无通知，而目标克隆整个settings触发监听。只在完整源动态属性赋值与目标四段clone写回/后续效果精确匹配时，加Object.is同值保护，保留后续通知。只证明已声明的现有设置键；未知动态键、原型键、新增键的Vue2非响应式语义未证明。绝不改回调业务效果来凑队列通过。

residual_v2前处理/返回后处理、共享repair Prompt、验证器、候选保护同步；新增source_parent_watch_not_landed/analysis_unavailable与lost_source_parent_watch_contracts。generation/服务器Prompt和legacy前处理不改。旧错误/断言保留并补新诊断/组合规则，旧冻结分数不回写。

最终独立完整测试{tests['passed']}/{tests['passed']}、0失败/跳过，{tests['elapsed_seconds']}秒。累计30项静态/编译回放仅TaskManager改写，原24通过件原字节仍静态通过；Trip外部依赖仍保留。TaskManager当前1→0错误、migration_hints_not_landed警告保留；仅它重做轻量初始DOM。真实调度器冻结输入1确定性步/0 LLM、现行自动门通过，不等于业务/浏览器通过。

源Vue2.7.16对照装置保持业务操作，只去掉已不适用的naive反事实版本（两处显式版本列表），另去除框架hook/注册/低级通知的记录差异，保留全部业务方法、存储、timer事件。修前不匹配；修后5场景×18阶段=90对，完整业务效果序列与状态均匹配，包括autoSave=false不误写、同轮多改合并、声明顺序、同值设置、dispose前取消、原生销毁后不触发。不是只比较最终画面。San attached应用钩子直接调用，无DOM attach；源空根render不测子组件/原模板，应用存储/timer模拟，真实框架Promise队列，San3.15.6并非人工页3.15.3。

实现过程的失配保留：最初装置构造了未使用的非法AST片段、后对数组直接调用节点生成比较报错，均已改正；首次别名规范化不对称/误把延迟箭头当即时效果，先拒绝了updateStatistics/updateSyncInterval，后加双端与即时范围证明；初次仅队列版在autoSave已false场景多重启timer，促成同值入口修复。未应用这些失败候选到canonical，不计为已实施生产回归。完整稳定验证独立重跑，不拼接散测。

冻结清单{data['runtime_inventory_count']}项。下一步在不扩大证明范围的前提下处理异常策略与未知动态键边界，再决定是否人工整页验收；本轮不付费重生成、不放宽规则使未证明分支通过。
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-evidence',action='store_true');args=parser.parse_args()
    if args.write_evidence and OUTPUT.exists():raise FileExistsError('Never overwrite frozen evidence')
    hashes=inventory();log=''
    if args.write_evidence:
        print('Running complete tests, no model requests.',flush=True)
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
        if proc.wait():raise RuntimeError('Full tests failed:\n'+log)
    artifacts,data=replay()
    if inventory()!=hashes:raise RuntimeError('Runtime changed during verification')
    if args.write_evidence:
        match=re.search(r'Ran (\d+) tests in ([\d.]+)s',log)
        if not match or '\nOK' not in log or re.search(r'OK\s*\(skipped=',log):raise RuntimeError('Missing complete non-skipped test success')
        data['unit_tests']={'passed':int(match[1]),'failed':0,'elapsed_seconds':float(match[2])};OUTPUT.mkdir(parents=True)
        for name in sorted(CHANGED|ADDED):
            dest=OUTPUT/'code'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
        for name,code in artifacts.items():(OUTPUT/name).write_text(code,encoding='utf-8')
        data['derived_artifact_sha256']={name:digest(OUTPUT/name) for name in artifacts}
        for name,value in [('replay.json',data),('live_inventory.json',hashes)]:
            (OUTPUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (OUTPUT/'REPORT.md').write_text(report(data),encoding='utf-8');(OUTPUT/'unit_tests.txt').write_text(log,encoding='utf-8')
        files=sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        (OUTPUT/'SHA256SUMS.txt').write_text('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files)+'\n',encoding='utf-8');verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'model_requests':0,'original_passed':24,'parent_watch_normal_flow_oracle_matched':True,
        'exception_semantics_proven':False,'unknown_dynamic_keys_proven':False,'unit_tests':data.get('unit_tests'),'evidence_written':args.write_evidence}))


if __name__=='__main__':main()
