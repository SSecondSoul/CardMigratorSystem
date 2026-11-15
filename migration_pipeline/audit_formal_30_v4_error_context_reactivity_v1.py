"""Read-only application mapping and reachable async-dispatch reactivity audit."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot

PRIOR = ROOT / 'data/experiments/analysis/formal_30_v4_source_error_context_v6_20261113'
OUTPUT = ROOT / 'data/experiments/analysis/formal_30_v4_error_context_reactivity_audit_v1_20261113'
NOTEBOOK = ROOT / 'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
PREFIX_SHA = '9d27ac06dd0f908522a03291c913a76dfddcae7f6f8cc58c7a2fc63105c29eb6'
METADATA_SHA = 'da8e8b42bb4344c317ccdf5038310d76529bda61666c53ff805bcc19dbede418'
NAMES = ['migration_pipeline/audit_error_context_reactivity_v1_runtime.cjs',
         'migration_pipeline/audit_formal_30_v4_error_context_reactivity_v1.py',
         'tests/test_error_context_reactivity_audit_v1.py']

# This inspects executable syntax, not stale page comments or live CDN globals.
STATIC = r'''
const fs=require('fs'),parser=require('@babel/parser');
const i=JSON.parse(fs.readFileSync(0,'utf8'));
function ast(text,html){
 const scripts=[...text.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)];
 return parser.parse(scripts.filter(m=>!html||!(/\bsrc\s*=/.test(m[1]))).map(m=>m[2]).join('\n'),{sourceType:'unambiguous'});
}
const key=p=>p?.key?.name||p?.key?.value;
function summary(text,html){
 const root=ast(text,html),r={vueRoots:[],sanRoots:[],vueLoaderPaths:[],testConfig:null,
  errorCapturedKeys:0,mixinOrExtendsKeys:0,globalHandlerAssignments:0,v6ConfigureCalls:0};
 function walk(n){if(!n||typeof n!=='object')return;
  if(n.type==='NewExpression'&&n.callee?.name==='Vue')r.vueRoots.push((n.arguments[0]?.properties||[]).map(key));
  if(n.type==='CallExpression'){
   if(n.callee?.name==='httpVueLoader'&&n.arguments[0]?.type==='StringLiteral')r.vueLoaderPaths.push(n.arguments[0].value);
   if(n.callee?.object?.name==='san'&&n.callee?.property?.name==='defineComponent')r.sanRoots.push((n.arguments[0]?.properties||[]).map(key));
   if(n.callee?.property?.name==='__sourceErrorContext_v6Configure')r.v6ConfigureCalls++;
  }
  if(n.type==='VariableDeclarator'&&n.id.name==='TEST_CONFIG')r.testConfig=Object.fromEntries(n.init.properties.filter(p=>p.value?.type==='StringLiteral').map(p=>[key(p),p.value.value]));
  if(['ObjectMethod','ObjectProperty'].includes(n.type)){
   if(key(n)==='errorCaptured')r.errorCapturedKeys++;
   if(['mixins','extends'].includes(key(n)))r.mixinOrExtendsKeys++;
  }
  if(n.type==='AssignmentExpression'&&n.left?.property?.name==='errorHandler')r.globalHandlerAssignments++;
  for(const [k,v] of Object.entries(n))if(!['loc','start','end','extra'].includes(k))Array.isArray(v)?v.forEach(walk):walk(v);
 }walk(root);return r;
}
process.stdout.write(JSON.stringify(Object.fromEntries(Object.entries(i).map(([k,v])=>[k,summary(v.text,v.html)]))));
'''


def stable(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def inventory():
    previous = json.loads((PRIOR / 'live_inventory.json').read_text(encoding='utf-8'))
    for name, expected in previous.items():
        if digest(ROOT / name) != expected:
            raise RuntimeError('Prior file drift: ' + name)
    data = json.loads((PRIOR / 'audit.json').read_text(encoding='utf-8'))
    for name, expected in {**data['application_files_sha256'], **data['source_inputs']}.items():
        if digest(ROOT / name) != expected:
            raise RuntimeError('Source/application drift: ' + name)
    return {**previous, **{name: digest(ROOT / name) for name in NAMES}}


def fixture():
    sys.path.insert(0, str(ROOT / 'tests'))
    spec = importlib.util.spec_from_file_location('error_context_reactivity_fixture', ROOT / 'tests/test_source_error_context_v6.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def application_audit(p, base):
    vue_page = ROOT / 'tests/manual/vue-test-runner.html'
    san_page = ROOT / 'tests/manual/san-test-runner.html'
    texts = {'vue_page': {'text': vue_page.read_text(encoding='utf-8'), 'html': True},
             'san_page': {'text': san_page.read_text(encoding='utf-8'), 'html': True},
             'frozen_TaskManager_source': {'text': base['vue'], 'html': False}}
    result = p.node(STATIC, texts)
    if len(result['vue_page']['vueLoaderPaths']) != 1 or not result['san_page']['testConfig']:
        raise RuntimeError('Ambiguous current page component')
    selected = {'vue': (vue_page.parent / result['vue_page']['vueLoaderPaths'][0]).resolve(),
                'san': (san_page.parent / result['san_page']['testConfig']['componentPath']).resolve()}
    if any(not path.is_relative_to(ROOT) or not path.is_file() for path in selected.values()):
        raise RuntimeError('Selected component outside workspace or missing')
    return {'evidence_level': 'local_executable_script_static_only_not_live_browser_or_CDN',
            'syntax': result, 'selected_files_sha256': {v.relative_to(ROOT).as_posix(): digest(v) for v in selected.values()},
            'current_component': 'RuleBuilder', 'TaskManager_is_current_manual_subject': False,
            'source_root_capture_mapping': 'No local root errorCaptured/mixins/extends declarations in current runner',
            'v6_application_binding_deployed': False, 'remote_loader_or_global_config_proven': False,
            'runtime_versions_match_pinned_pair': False,
            'warning': 'Absent local declarations do not prove absent live plugins/global hooks. Current pages do not load TaskManager.'}


def summarize(observed):
    differences = []
    for name in [s['name'] for s in observed['scenarios']]:
        a, b = [r for r in observed['runs'] if r['scenario'] == name]
        for x, y in zip(a['phases'], b['phases']):
            fields = {k: {'vue': value, 'san': y['state'][k]}
                      for k, value in x['state'].items() if value != y['state'][k]}
            if fields:
                differences.append({'scenario': name, 'phase': x['name'], 'fields': fields})
    return differences


def gather():
    hashes = inventory()
    if verify_snapshot(PRIOR.resolve()) != 10:
        raise RuntimeError('Frozen v6 scope changed')
    previous = json.loads((PRIOR / 'audit.json').read_text(encoding='utf-8'))
    p = fixture()
    _old, _v5, base, _common, candidate, payload = p.payloads()
    if candidate != previous['candidate']:
        raise RuntimeError('v6 candidate changed')
    old_runtime = PRIOR / 'code/migration_pipeline/audit_source_error_context_v6_runtime.cjs'
    if p.node(old_runtime, payload) != previous['native_observations']:
        raise RuntimeError('Prior v6 frozen observations changed')
    observed = p.node(ROOT / NAMES[0], payload)
    if observed != p.node(ROOT / NAMES[0], payload):
        raise RuntimeError('Nondeterministic dependency audit')
    if len(observed['runs']) != 18 or sum(len(r['phases']) for r in observed['runs']) != 216 or len(observed['pairs']) != 108:
        raise RuntimeError('Expected 9 scenarios x 2 native variants x 12 phases')
    if not all(all(row[k] for k in ['eventsEqual', 'rawConsoleEqual', 'unhandledRejectionsEqual']) for row in observed['pairs']):
        raise RuntimeError('Business/error event mismatch; keep raw output before further investigation')
    differences = summarize(observed)
    if not differences or any(set(d['fields']) - {'auditComputedRuns', 'domText'} for d in differences):
        raise RuntimeError('Unexpected state difference, not the observed computed/teardown boundary')
    for run in observed['runs']:
        by = {f['name']: f for f in run['phases']}
        before = by['recovery_tick']['state']['auditComputedRuns']
        after = by['unrelated_tick']['state']['auditComputedRuns']
        expected = 1 if run['scenario'] == 'positive_computed_dependency' else 0
        if after - before != expected:
            raise RuntimeError('Unrelated dependency observation changed: ' + run['scenario'])
    app = application_audit(p, base)
    nb = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    if stable(nb['cells'][:68]) != PREFIX_SHA or stable(nb['metadata']) != METADATA_SHA:
        raise RuntimeError('Previous Notebook cells/metadata changed')
    if inventory() != hashes:
        raise RuntimeError('Prior files changed during audit')
    return {'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification': 'application_mapping_static_and_native_reactivity_audit_not_new_repair',
        'previous_verified_payloads': 10, 'previous_inventory_unchanged': 421, 'inventory_count': len(hashes),
        'production_runtime_inventory_unchanged': 387,
        'application_files_sha256': previous['application_files_sha256'], 'application_static_audit': app,
        'source_inputs': previous['source_inputs'], 'original_aggregate': previous['original_aggregate'],
        'native_observations': observed, 'raw_state_differences': differences,
        'unrelated_dependency_check': {'normal_and_six_error_scenarios_delta': 0,
            'two_updates_control_delta': 0, 'explicit_dependency_positive_control_delta': 1,
            'active_collector_during_error_not_forced': True,
            'scope': 'Actual v6 asynchronous dispatch in this fixture; not arbitrary active render/computed error context'},
        'findings': [
            {'id': 'APPLICATION_BINDING_NOT_DEPLOYED', 'category': 'remaining_risk', 'status': 'static_only_unresolved',
             'component': 'TaskManager', 'root_cause': 'Local pages select RuleBuilder and contain no v6 configuration; remote runtime globals remain unknown.',
             'resolution': 'No deployment or manual page change; mapping not certified.'},
            {'id': 'REACTIVITY_CONTRACT_NOT_GENERALIZED', 'category': 'remaining_risk', 'status': 'bounded_observation_only',
             'component': 'TaskManager', 'root_cause': 'Source has dependency target push/pop; v6 has no dependency suspension. Current dispatch is async, and this fixture did not show phantom reads.',
             'resolution': 'Keep v6 profile unchanged. Six reactive hook scenarios intentionally exceed its declaration; no production expansion.'},
            {'id': 'COMPUTED_TIMING_AND_TEARDOWN_BASELINE', 'category': 'expected_behavior', 'status': 'native_control_reproduced',
             'component': 'injected_audit_computed_only', 'root_cause': 'San eager computed evaluation differs from Vue lazy/coalesced evaluation; native teardown retains/removes DOM differently.',
             'resolution': 'Preserve all raw differences. Two synchronous no-error updates reproduce the extra target computed evaluation; do not call it a new bridge regression.'}],
        'production_diagnostics_reference': previous['production_diagnostics'],
        'forged_pass_gate_reference': previous['forged_pass_gate'],
        'evidence_boundary': {'real_browser_opened': False, 'manual_acceptance_added': False,
            'subject_render_and_one_computed_are_injected_fixture': True, 'storage_and_timers_are_fault_injection': True,
            'native_frameworks_and_component_parent_chain': True, 'private_error_functions_called': False,
            'reactive_hooks_violate_existing_v6_declared_profile': True, 'full_source_dependency_pause_proven': False},
        'production_integration_enabled': False, 'production_rules_or_prompt_modified': False,
        'existing_candidate_or_manual_pages_modified': False, 'model_requests': 0,
        'original_score_modified': False, 'full_suite_reexecuted': False,
        'prior_notebook_cells': 68, 'prior_notebook_cells_sha256': stable(nb['cells'][:68]),
        'prior_notebook_metadata_sha256': stable(nb['metadata'])}


def report(data):
    return f'''# 应用映射与响应式错误钩子审计 v1（2026-11-13）

这是验证边界的审计，不是新生产规则或已部署修复。v6 helper/adapter及原生装置原封不动，上一轮110阶段证据完整重放。0模型调用，无人工确认，无页面改动；原批24/30、6失败、0执行异常、1,821,544 tokens不变。

## 真实应用核对的证据等级

只读取本地可执行脚本AST，不据旧注释推断当前组件。当前两页实际加载RuleBuilder，不是TaskManager；Vue root没有本地errorCaptured/mixins/extends，页面无全局errorHandler赋值；San wrapper没有v6配置调用。冻结TaskManager源没有errorCaptured/mixins/extends声明。验收驱动的window监听不是桥接配置。CDN/loader/运行中插件或全局配置未访问，不能用“本地未声明”证明真实浏览器没有祖先钩子。页面版本与固定Vue2.7.16/San3.15.6也不等同。因此**应用映射仍未部署/认证**，不能把v6 fixture应用绑定当成真实应用结果。

## 原生依赖与重入审计

保留固定miniDOM和原TaskManager业务/生命周期体；仅注入auditSentinel、一项computed及最小渲染以观察依赖。9场景×2变体×12阶段=18运行、216快照、108比较。含正常、两次同步设置、显式依赖阳性对照，以及6个捕获/全局钩子读状态、写无关状态、重入settings/tasks场景。钩子通过实际v6异步dispatch到达，没有手工调用helper.handle或私有框架错误函数。

**不是108项完整状态全通过**。108比较的完整事件、raw console、拒绝相等；所有原始状态差异保留在audit.json。无关sentinel后续变更未使computed新增求值（8场景×2变体），显式依赖阳性对照则两框架均增加1次，证明装置可以观测依赖。这只支持当前异步队列中的有限观察，不证明活跃render/computed上下文中的暂停/恢复，也不改变v6原profile。6种响应式hook刻意越出“不读写响应式状态”的声明；匹配不等于合法扩展。

## 保留并解释的差异

San computed较早求值，Vue computed较晚/合并求值，故同步帧有计数差异；settings hook将30改15时，目标多算一次。**无异常的两次同步设置控制也出现同样计数差异**，因此不能归为v6新回归或错误依赖。后续无关数据变更不增加两者计数。Vue销毁保留节点/San dispose移除节点也在正常控制中复现；所有destroy帧DOM差异保留，不过滤成成功。原业务状态没有观察到差异，渲染稳定时内容一致，但不能据此承诺computed副作用可等价迁移。

## 结果与下一步

定向测试：{json.dumps(data['scoped_tests'], ensure_ascii=False)}；不声称完整703项重跑。旧421文件清单（含387生产/既有运行文件）、来源/页面/原v6证据未改；新增3审计/测试文件后424项，7个payload封存。旧Notebook68单元及元数据保留，追加审计节。

结论是缩小了未知范围，并非宣布完整闭环：应用映射仍需明确实际部署入口；当前async通道未观察到额外依赖，但通用依赖暂停、活跃收集器中的钩子、异步/无限重入、SSR与任意祖先映射仍未证明。下一步应先确定是否把生产方案限定为已证明的异步watcher通道，并设计可拒绝越界上下文的能力契约；不直接接入生产、不放宽诊断、不付费模型复跑。
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-evidence', action='store_true')
    args = parser.parse_args()
    if args.write_evidence and OUTPUT.exists():
        raise FileExistsError('Never overwrite frozen audit')
    hashes = inventory()
    data = gather()
    if args.write_evidence:
        logs, suites = '', []
        for suite in ['test_error_context_reactivity_audit_v1.py', 'test_source_error_context_v6.py', 'test_parent_watch_scope_guard.py']:
            print('Running ' + suite, flush=True)
            proc = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', suite, '-v'],
                cwd=ROOT, capture_output=True, text=True, encoding='utf-8', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
            text = proc.stdout + proc.stderr
            logs += '\n### ' + suite + '\n' + text
            match = re.search(r'Ran (\d+) tests in ([\d.]+)s', text)
            if proc.returncode or not match or '\nOK' not in text or re.search(r'OK\s*\(skipped=', text):
                failed = OUTPUT.parent / (OUTPUT.name + '_failed_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.txt')
                with failed.open('x', encoding='utf-8') as stream:
                    stream.write(logs)
                raise RuntimeError('Scoped failure recorded: ' + str(failed))
            suites.append({'suite': suite, 'passed': int(match[1]), 'elapsed_seconds': float(match[2])})
        if inventory() != hashes:
            raise RuntimeError('Prior/live audit files changed during tests')
        data['scoped_tests'] = {'passed': sum(s['passed'] for s in suites), 'failed': 0, 'skipped': 0,
            'suites': suites, 'elapsed_seconds': round(sum(s['elapsed_seconds'] for s in suites), 3), 'not_a_full_suite': True}
        OUTPUT.mkdir(parents=True, exist_ok=False)
        for name in NAMES:
            target = OUTPUT / 'code' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        for name, value in [('audit.json', json.dumps(data, ensure_ascii=False, indent=2) + '\n'),
                            ('live_inventory.json', json.dumps(hashes, ensure_ascii=False, indent=2) + '\n'),
                            ('REPORT.md', report(data)), ('scoped_tests.txt', logs)]:
            with (OUTPUT / name).open('x', encoding='utf-8') as stream:
                stream.write(value)
        files = sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        with (OUTPUT / 'SHA256SUMS.txt').open('x', encoding='utf-8') as stream:
            stream.write('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files) + '\n')
        data['verified_payloads'] = verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'written': args.write_evidence, 'tests': data.get('scoped_tests'),
        'payloads': data.get('verified_payloads'), 'pairs': 108, 'full_state_equality_claimed': False,
        'application_mapping_deployed': False, 'production_integration_enabled': False, 'model_requests': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
