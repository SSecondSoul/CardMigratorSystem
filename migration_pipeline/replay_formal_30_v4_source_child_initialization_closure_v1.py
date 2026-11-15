"""Offline registered child factory/initialization/watch closure; zero model calls."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot
from migration_pipeline.replay_formal_30_v4_source_array_transaction_closure_v1 import OUTPUT as BASE, SOURCE, PROTOCOL, BATCH, offline_scheduler
from migration_pipeline.utils.source_child_initialization_semantics import source_child_initialization_semantics
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.utils.repair_scheduler import candidate_gate

OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_source_child_initialization_closure_v1_20261111'
CHANGED={'migration_pipeline/stages/repair.py','migration_pipeline/stages/validate.py',
 'migration_pipeline/utils/repair_prompt.py','migration_pipeline/utils/repair_scheduler.py',
 'migration_pipeline/utils/source_render_call_semantics.cjs','tests/test_monitoring_remaining_bounded_fix.py',
 'tests/test_repair_regression_guard.py','tests/test_source_array_transaction_closure.py',
 'tests/test_source_dom_closure.py','tests/test_source_inline_formatter_closure.py',
 'tests/test_source_payload_closure.py','tests/test_source_render_call_closure.py','tests/test_source_render_dependency_closure.py'}
ADDED={'migration_pipeline/utils/source_child_initialization_semantics.py',
 'migration_pipeline/utils/source_child_initialization_semantics.cjs','tests/test_source_child_initialization_closure.py',
 'migration_pipeline/replay_formal_30_v4_source_child_initialization_closure_v1.py'}


def inventory():
    verify_snapshot(BASE.resolve())
    previous=json.loads((BASE/'live_inventory.json').read_text(encoding='utf-8'))
    now={name:digest(ROOT/name) for name in sorted(set(previous)|ADDED)}
    changed={name for name,sha in previous.items() if now[name]!=sha}
    if changed!=CHANGED:raise RuntimeError('Unexpected runtime delta: '+str(changed^CHANGED))
    return now


def startup_runtime(code,vue):
    javascript=r'''const fs=require('fs'),san=require('san'),parser=require('@babel/parser'),generate=require('@babel/generator').default;
const x=JSON.parse(fs.readFileSync(0,'utf8')),m={exports:{}};
new Function('require','module',/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(x.code)[1])(require,m);
const ast=parser.parse(/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(x.vue)[1],{sourceType:'unambiguous'});
const declarations=ast.program.body.filter(n=>n.type==='VariableDeclaration').flatMap(n=>n.declarations);
const source=declarations.find(n=>n.id.name==='TaskForm').init.properties.find(n=>n.key.name==='methods').value;
const method=source.properties.find(n=>n.key.name==='createFormData');
const factory=new Function(...method.params.map(p=>generate(p).code),generate(method.body).code.slice(1,-1));
const F=m.exports.prototype.components['task-form'],original={title:'first',description:'description',tags:['a'],meta:{ok:true}},calls=[];
const base=F.prototype.createFormData;if(typeof base==='function')F.prototype.createFormData=function(value){calls.push(value);return base.call(this,value);};
const nativeWatch=san.Component.prototype.watch,registrations=[];
san.Component.prototype.watch=function(prop,fn){registrations.push({prop,initial_type:typeof this.data.get('formData')});return nativeWatch.call(this,prop,fn);};
const a=new F({data:{task:original,users:[],tags:['a']}}),b=new F({data:{task:original,users:[],tags:['a']}});
const first=a.data.get('formData'),other=b.data.get('formData');
const result={initial_type:typeof first,source_expected_type:typeof factory(original),initial_equals_source:JSON.stringify(first)===JSON.stringify(factory(original)),
 watch_is_builtin:a.watch===san.Component.prototype.watch,registration_count:registrations.length,
 instance_isolation:typeof first==='object'&&first!==other&&first.tags!==other.tags&&first.tags!==original.tags,
 root_guard_runtime_tested:false,full_parent_attached:false,browser_used:false};
if(typeof first==='object'&&first!==null){
 a.data.set('formData.title','draft edit');a.data.set('formData.tags',['b']);
 result.input_unchanged=original.title==='first'&&original.tags.join(',')==='a';
 a.data.set('task.title','nested');result.nested_preserves_draft=calls.length===2&&a.data.get('formData').title==='draft edit';
 const next={title:'replacement',tags:['z']};a.data.set('task',next);
 result.replacement_equals_source=JSON.stringify(a.data.get('formData'))===JSON.stringify(factory(next));
 result.tags_detached=a.data.get('formData').tags!==next.tags;
 a.data.set('task',null);result.empty_equals_source=JSON.stringify(a.data.get('formData'))===JSON.stringify(factory(null));
 result.factory_call_count=calls.length;result.registration_after_initial_object=registrations.every(r=>r.initial_type==='object');
 result.root_guard_runtime_tested=true;
}
san.Component.prototype.watch=nativeWatch;process.stdout.write(JSON.stringify(result));'''
    proc=subprocess.run(['node','-e',javascript],input=json.dumps({'code':code,'vue':vue}),cwd=ROOT,
        text=True,encoding='utf-8',capture_output=True,check=True,timeout=20)
    result=json.loads(proc.stdout);result['reserved_watch_warning']='reserved key' in proc.stderr and 'watch' in proc.stderr
    return result


def replay():
    verified={name:verify_snapshot(path.resolve()) for name,path in [
        ('raw',SOURCE),('protocol',PROTOCOL),('source_array_transaction_closure',BASE)]}
    old={r['id']:r for r in json.loads((BASE/'replay.json').read_text(encoding='utf-8'))['retained_artifact_replays']}
    raw=json.loads((SOURCE/f'{BATCH}_summary.json').read_text(encoding='utf-8'))
    rows,artifacts=[],{}
    if len(old)!=30 or len(raw['samples'])!=30:raise RuntimeError('Expected full-30 inputs')
    for sample in raw['samples']:
        name=sample['id'];print('Offline static check: '+name,flush=True);prior=old[name]
        path=BASE/'TaskManager_source_array_transaction_offline.san' if name=='TaskManager' else ROOT/prior['input_path']
        code=path.read_text(encoding='utf-8');vue=ROOT/prior['vue_path'];source=vue.read_text(encoding='utf-8')
        state=json.loads((SOURCE/'repair_reports'/sample['complexity']/sample['report_file'].replace('\\','/').split('/')[-1]).read_text(encoding='utf-8'))['state']
        result=source_child_initialization_semantics(code,source,repair=True)
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
        startup_findings=[e for e in before['validation_errors'] if e['code'].startswith('source_child_')]
        if len(startup_findings)!=(2 if name=='TaskManager' else 0):raise RuntimeError('Unexpected child startup finding: '+name)
        gate=candidate_gate(before,after)
        if gate['should_stop']:raise RuntimeError('Candidate rejected: '+name)
        again=source_child_initialization_semantics(fixed,source,repair=True)
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
            if {e['code'] for e in before['validation_errors']}!={'source_child_factory_not_landed','source_child_watch_not_landed'} or not after['validation_passed']:
                raise RuntimeError('Unexpected TaskManager diagnostic result')
            planned,steps=RepairStage._deterministic_repair_plan(code,before['validation_errors'],[],state['ssm'],str(vue),enable_residual_v2=True)
            if planned!=fixed:raise RuntimeError('Prepass differs from rule')
            reverse=candidate_gate(after,before)
            if not reverse['should_stop']:raise RuntimeError('Factory/watch regression not rejected')
            runtime_before=startup_runtime(code,source);runtime_after=startup_runtime(fixed,source)
            if runtime_before['initial_type']!='function' or runtime_before['watch_is_builtin'] or not runtime_before['reserved_watch_warning']:
                raise RuntimeError('Frozen first-prop failure did not reproduce')
            checks=['initial_equals_source','watch_is_builtin','instance_isolation','input_unchanged','nested_preserves_draft',
                'replacement_equals_source','tags_detached','empty_equals_source','registration_after_initial_object','root_guard_runtime_tested']
            if runtime_after['initial_type']!='object' or not all(runtime_after[k] for k in checks) or runtime_after['reserved_watch_warning']:
                raise RuntimeError('Native San runtime source parity checks failed')
            if runtime_after['registration_count']!=2 or runtime_after['factory_call_count']!=4:raise RuntimeError('Duplicate/missing initialization or prop watcher')
            row.update(prepass_steps=steps,reverse_gate=reverse,landed_startup_proofs=again['proofs'],
                startup_runtime_before=runtime_before,startup_runtime_after=runtime_after,
                offline_scheduler=offline_scheduler(code,vue,state['ssm'],fixed))
            artifacts['TaskManager_source_child_initialization_offline.san']=fixed
        if name=='trip_itinerary_planner' and (fixed!=code or after['validation_passed'] or not any(e['code']=='source_render_dependency_not_landed' for e in after['validation_errors'])):
            raise RuntimeError('Do not erase the previous unproven external render dependency')
        rows.append(row)
    verify_snapshot(SOURCE.resolve());verify_snapshot(BASE.resolve())
    return artifacts,{'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'offline_source_child_initialization_closure_reused_development_not_new_batch',
        'source_verified_files':verified,'original_aggregate':raw['aggregate'],'model_requests':0,
        'original_score_modified':False,'canonical_san_or_manual_pages_modified':False,
        'manual_acceptance_inherited':False,'full_browser_interaction_executed':False,
        'runtime_inventory_count':len(inventory()),'original_passed_raw_artifacts_static_checked_unchanged':24,
        'initial_dom_reexecuted_ids':['TaskManager'],'retained_prior_derivative_risk_ids':['trip_itinerary_planner'],
        'retained_artifact_replays':rows}


def report(data):
    tests=data['unit_tests']
    return f'''# 注册子组件工厂／首次 props／watch 闭环 v1（2026-11-11）

本轮从源数组事务冻结件继续，不重新生成、不改 canonical San 或测试页、不继承人工通过，不是独立测试。原始成绩仍为 24/30、6 失败、0 执行异常、1,821,544 tokens；模型请求 0，不回填分数。

旧初始化 regex 只看到读取 task 与写入 formData，未证明值的类型/工厂语义。既有 inline formatter 规则只允许模板调用而拒绝脚本提及，故未覆盖源 createFormData(task) 被生成成 computed 返回函数的分支；inited 调 this.computed.createFormData(task) 写入函数而非对象。watch() 又覆盖 San 框架方法且不是自动注册钩子。上述在前层冻结输入即可复现，并非移动修复引入的回归；原有静态零错误不能追认为完整通过。

新增 source_child_initialization_semantics.py/.cjs。按完整 Vue 的真实父注册和唯一、不逃逸、同标签别名的子构造器映射；复用 registered AST 辅助函数，不靠组件名特判。只支持完整单参数纯新对象工厂、单个 prop→派生字段初始化、对应单个无 deep/immediate 的源 watcher。规范化单 return 条件表达式与唯一 if/else-return，并比较全部对象字段、spread/数组副本、默认值及参数。拒绝未知调用/闭包/突变、返回原对象、工厂体不符、未知生命周期/监听效果、重复注册、其他脚本/模板调用、构造器逃逸、mixins/extends 等不明确分支，不做全局 computed/watch 替换。

恢复工厂为顶层可调用方法；在 inited 先按首次 props 创建派生对象，再使用 San 内建 watch 注册一次，移除仅包含该源监听的 watch 方法。未知钩子内容保留原字节并拒绝自动修复，不强行移动。新对象与 tags 副本保留源浅拷贝语义，不声称深克隆。

本地已安装 San 源码 component.js 的 watch 会比较数据对象引用，data.js 的嵌套 set 会复制祖先对象；直接 watch('task') 可能因 task.title 更新而重置草稿。目标回调使用第二参数 change.change.expr.paths.length===1 保持本规则限定的浅根替换语义，不能靠无效第三参数 deep:false。真实 San 验证根替换触发、嵌套更新不触发、初始对象先于注册、无重复初始化；未扩展到深监听、路径监听或任意 watcher 语义。

前处理、stub 模型返回后处理、共享 repair Prompt、验证器与候选保护同步；新增 source_child_factory_not_landed、source_child_watch_not_landed、source_child_initialization_analysis_unavailable。注册/工厂/根路径守卫删除或改坏必须回退。generation/服务器 Prompt 和 legacy 非 residual_v2 前处理未改，不需要启动服务。新规则首轮 20/20（58.456 秒）；9 项受影响历史用例 9/9（89.050 秒）通过；无本轮测试失败被隐藏。历史精确断言只加初始化错误与组合步骤，不删旧诊断、不豁免旧失败；完整套件独立重跑，不将散测拼为全通过。

开发只读 30 项预检完成、不写证据；随后补强动态 this/this.computed 成员、动态 data.get 与模板未知工厂调用的拒绝边界，新规则再次单独 20/20（53.235 秒）通过。最终从稳定代码重新执行完整套件与全部回放，预检不冒充最终冻结结果。

完整测试 {tests['passed']}/{tests['passed']}、0 失败，{tests['elapsed_seconds']} 秒，输出 unit_tests.txt。冻结前后在真实 San 子组件上复现 function→object、内建 watch 恢复；以冻结 Vue 原纯工厂为运行 oracle，验证新建/编辑、根替换/嵌套不重置、空值默认、标签/跨实例隔离及源输入不被写坏。子组件从构造到 inited/watch 执行，不 attach 完整父组件、不启动 UI/定时器；因此不是完整浏览器/全业务通过。

30 个累计输入重做静态验证/编译，仅 TaskManager 改写，24 个原始通过件原字节且仍静态通过。TaskManager 当前两条 factory/watch 错误变为 0，保留 migration_hints_not_landed 警告；不是 splice 复发，也不是原始批次新跑分。仅它重做轻量初始 DOM，其余视觉标记沿用前层。真实 bounded 调度器读取冻结输入、禁止模型：1 个确定性步骤、0 次 LLM，自动门 final_passed=true。正向接受、反向拒绝、固定点、独立规则与组合前处理一致。

TripItineraryPlanner 上轮外部渲染辅助依赖风险仍失败、不豁免。完整父组件初始化/watch 时机、浏览器弹窗与原生拖放、持久化/计时器联动仍未完整运行；未知源工厂/watch 形态仍需人工审查。不宣布独立测试、整个迁移器普适正确或组件全交互通过。下一步审查父生命周期与整条拖拽事件链，再决定是否配置人工验收；暂不付费复跑。

运行清单 {data['runtime_inventory_count']} 项，SHA256SUMS 覆盖代码、派生 San、回放/运行观察、报告和完整日志；旧原始、协议和各层冻结包不改，未 commit/push。调度器 output_sha256 为规范化 UTF-8 文本身份，与文件字节 SHA 分开复算。
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
