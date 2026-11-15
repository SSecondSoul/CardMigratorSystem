"""Bounded native Ref structural dependency experiment; private property deps remain open."""
import argparse
import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

from migration_pipeline.audit_v7_source_queue_contract import ROOT, NB, sha, seal, verify, write
from migration_pipeline.audit_ref_contract_v12 import OUT as V12, REF_RUNTIME
from migration_pipeline.audit_v7_dynamic_shape import payload, node, RUNTIME
from migration_pipeline.audit_source_path_assignment_v11 import regressions, PATH_RUNTIME
from migration_pipeline.audit_shape_input_expansion import RUNTIME as EXPANDED_RUNTIME
from migration_pipeline.audit_shape_observer_v10 import SUPPLEMENT as DESCRIPTOR_RUNTIME

BASE = ROOT / 'data/experiments/analysis/formal_30_v4_native_ref_structure_v13_input_20261114'
OUT = ROOT / 'data/experiments/analysis/formal_30_v4_native_ref_structure_v13_20261114'
ADAPTER = 'migration_pipeline/probe_native_ref_structure_adapter_v13.cjs'
STRUCTURE_RUNTIME = 'migration_pipeline/audit_native_ref_structure_v13_runtime.cjs'
FILES = ['migration_pipeline/probe_native_ref_structure_v13.cjs', ADAPTER, STRUCTURE_RUNTIME,
         'migration_pipeline/audit_native_ref_structure_v13.py', 'tests/test_native_ref_structure_v13.py',
         'migration_pipeline/audit_native_ref_structure_v13_controls.cjs']


def freeze():
    verify(V12)
    a = json.loads((V12 / 'audit.json').read_text(encoding='utf-8'))
    assert a['stats']['refs']['mismatches'] == 6 and a['stats']['expanded']['mismatches'] == 0
    protected = {**a['protected_files_sha256'], **a['code_sha256']}
    for name, expected in protected.items(): assert sha(ROOT / name) == expected, name
    BASE.mkdir(exist_ok=False)
    shutil.copy2(NB, BASE / 'notebook_before.ipynb')
    shutil.copy2(V12 / 'refs_observations.json', BASE / 'v12_ref_observations.json')
    write(BASE / 'protected_files.json', protected)
    seal(BASE); verify(BASE)
    print('Frozen six native deep Ref mismatches and 96-cell Notebook before V13.')


def candidates(data):
    return {n: node(ROOT / ADAPTER, {'code': data[n], 'vue': data['vue' if n == 'san' else 'genericVue'],
                                   'experimental': True}) for n in ['san', 'genericSan']}


def broad_replay():
    prior = ROOT / 'data/experiments/analysis/formal_30_v4_parent_alias_child_audit_v1_20261112'
    verify(prior)
    old = json.loads((prior / 'audit.json').read_text(encoding='utf-8')); fixture = old['fixture']
    composed = node(ROOT / 'migration_pipeline/probe_async_watcher_scope_adapter_v7.cjs',
                    {'code': fixture['normal'], 'vue': fixture['vue'], 'experimental': True,
                     'error_context_policy': 'private-async-parent-watch-source-context'})
    assert composed['changes'], composed['reviews']
    candidate = node(ROOT / ADAPTER, {'code': composed['code'], 'vue': fixture['vue'], 'experimental': True})
    assert candidate['changes'], candidate['reviews']
    common = {name: (ROOT / next(p for p in old['source_inputs'] if p.endswith(end))).read_text(encoding='utf-8')
              for name, end in [('vueRuntime', 'vue.runtime.common.dev.js'), ('sanRuntime', 'san.dev.js')]}
    return (node(prior / 'code/migration_pipeline/audit_parent_alias_child_runtime.cjs',
                 {**fixture, **common, 'v3': candidate['code']}),
            node(ROOT / 'migration_pipeline/audit_parent_alias_observer_v4_runtime.cjs',
                 {'vue': fixture['vue'], 'v4': candidate['code'], **common}))


def preflight():
    folder = OUT.with_name(OUT.name + '_preflight'); folder.mkdir(exist_ok=False)
    verify(BASE)
    data = payload(); adapted = candidates(data)
    assert all(a['changes'] for a in adapted.values())
    request = {**data, **{n: a['code'] for n, a in adapted.items()}}
    summary = {}
    for name, runtime in [('refs', REF_RUNTIME), ('structure', STRUCTURE_RUNTIME)]:
        observed = node(ROOT / runtime, request); write(folder / (name + '_observations.json'), observed)
        summary[name] = {'pairs': len(observed['pairs']), 'mismatches': [p for p in observed['pairs'] if not p['equal']]}
    for name in FILES:
        if not (ROOT / name).exists(): continue
        dest = folder / 'code' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
    seal(folder); verify(folder); print(json.dumps(summary))


def execute():
    from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
    from migration_pipeline.utils.repair_scheduler import candidate_gate
    verify(BASE); verify(V12)
    pre = OUT.with_name(OUT.name + '_preflight'); verify(pre)
    old = json.loads((BASE / 'notebook_before.ipynb').read_text(encoding='utf-8'))
    assert json.loads(NB.read_text(encoding='utf-8')) == old, 'Notebook changed; never overwrite'
    hashes = {n: sha(ROOT / n) for n in FILES}
    protected = json.loads((BASE / 'protected_files.json').read_text(encoding='utf-8'))
    for name, expected in protected.items(): assert sha(ROOT / name) == expected, name
    OUT.mkdir(exist_ok=False)
    data = payload(); adapted = candidates(data)
    assert all(a['changes'] and not a['production_eligible'] for a in adapted.values())
    request = {**data, **{n: a['code'] for n, a in adapted.items()}}
    for name, a in adapted.items():
        with (OUT / (name + '_native_structure.san')).open('x', encoding='utf-8') as stream: stream.write(a['code'])
    write(OUT / 'adaptation.json', {n: {k: v for k, v in a.items() if k != 'code'} for n, a in adapted.items()})
    observed = {}
    print('Replaying native structure, Ref and all earlier input matrices.', flush=True)
    for name, runtime in [('structure', STRUCTURE_RUNTIME), ('refs', REF_RUNTIME), ('expanded', EXPANDED_RUNTIME),
                          ('original', RUNTIME), ('descriptors', DESCRIPTOR_RUNTIME), ('paths', PATH_RUNTIME),
                          ('structure_controls', 'migration_pipeline/audit_native_ref_structure_v13_controls.cjs')]:
        observed[name] = node(ROOT / runtime, request)
        write(OUT / (name + '_observations.json'), observed[name])
    v12_request = {**data, **{n: (V12 / (n + '_ref_contract.san')).read_text(encoding='utf-8') for n in ['san', 'genericSan']}}
    before_structure = node(ROOT / STRUCTURE_RUNTIME, v12_request)
    write(OUT / 'v12_structure_observations.json', before_structure)
    before_refs = json.loads((BASE / 'v12_ref_observations.json').read_text(encoding='utf-8'))
    regression_rows = {'refs': regressions(before_refs, observed['refs']),
                       'structure': regressions(before_structure, observed['structure'])}
    mounted, aliases = broad_replay()
    write(OUT / 'mounted_observations.json', mounted); write(OUT / 'aliases_observations.json', aliases)
    diagnostic = source_parent_watch_semantics(adapted['san']['code'], data['vue'])
    write(OUT / 'production_diagnostics.json', {k: v for k, v in diagnostic.items() if k != 'code'})
    state = {'generated_code': data['san'], 'vue_source': data['vue'], 'validation_errors': diagnostic['findings']}
    gate = candidate_gate(state, {**state, 'generated_code': adapted['san']['code'], 'validation_errors': [], 'validation_passed': True})
    write(OUT / 'forged_pass_gate.json', gate)
    suites = ['test_native_ref_structure_v13.py', 'test_ref_contract_v12.py', 'test_source_path_assignment_v11.py',
              'test_shape_observer_v10.py', 'test_shape_input_expansion.py', 'test_shape_observer_v9.py',
              'test_source_property_assignment_v8.py', 'test_v7_source_queue_contract.py', 'test_v7_integration_contract.py']

    def test_suite(suite):
        proc = subprocess.run(['python', '-m', 'unittest', 'discover', '-s', 'tests', '-p', suite, '-v'],
                              cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        log = proc.stdout + proc.stderr
        with (OUT / (suite + '.log')).open('x', encoding='utf-8') as stream: stream.write(log)
        match = re.search(r'Ran (\d+) tests?', log)
        result = {'suite': suite, 'count': int(match[1]) if match else 0, 'returncode': proc.returncode}
        print(result, flush=True); return result

    # These suites read immutable inputs and run independent Node subprocesses.
    # Only this driver writes distinct logs; Notebook append occurs after all join.
    print('Testing nine read-only suites (two workers).', flush=True)
    with ThreadPoolExecutor(max_workers=2) as executor: tests = list(executor.map(test_suite, suites))
    for name, expected in {**protected, **hashes}.items(): assert sha(ROOT / name) == expected, name
    for name in FILES:
        dest = OUT / 'code' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
    stats = {n: {'pairs': len(observed[n]['pairs']), 'mismatches': sum(not p['equal'] for p in observed[n]['pairs'])}
             for n in ['refs', 'structure', 'expanded', 'original', 'descriptors', 'paths']}
    cleanup_failures = [p for name in ['refs', 'structure'] for p in observed[name]['cleanup_pairs']
                        if not all(p[k] for k in ['errorsEqual', 'sourceSubscribersReleased', 'sanSubscribersReleased'])]
    native_cleanup_failures = [r for r in observed['structure']['nativeObserverCleanup'] if not r['allReleased']]
    audit = {'production_eligible': False, 'model_calls': 0, 'classification': 'remaining_risk_partial_native_structure',
             'stats': stats, 'baseline_ref_mismatches': 6,
             'baseline_structure_mismatches': sum(not p['equal'] for p in before_structure['pairs']),
             'regressions': regression_rows,
             'remaining_ref_scenarios': sorted({p['scenario'] for p in observed['refs']['pairs'] if not p['equal']}),
             'remaining_structure_scenarios': sorted({p['scenario'] for p in observed['structure']['pairs'] if not p['equal']}),
             'ref_cleanup_failures': cleanup_failures, 'native_observer_cleanup_failures': native_cleanup_failures,
             'expanded_cleanup_mismatches': sum(not p['equal'] for p in observed['expanded']['cleanup_pairs']),
             'tests': tests, 'test_workers': 2, 'code_sha256': hashes, 'protected_files_sha256': protected,
             'prior_notebook_cells': len(old['cells']), 'original_scores_modified': False, 'production_files_changed': False,
             'open_boundaries': ['Native private property dependencies (four original Ref points plus two newly added-property points)',
                                 'Native Ref value propagation to child computed/render caches not established by the structural-only tests',
                                 'Whole-root Ref, custom/computed Ref, arbitrary/spoofed dep providers and foreign observer interoperability',
                                 'Lifecycle error routing (one earlier mismatch)',
                                 'Arbitrary accessor effects, Proxy/reflection and production contract integration']}
    write(OUT / 'audit.json', audit)
    write(OUT / 'coverage_obligations.json', [
        {'id': 'NATIVE-STRUCTURE', 'category': 'remaining_risk', 'status': 'bounded_native_replay_matches',
         'scope': 'Pinned native Ref value child observer dep and native array dependArray structural tokens; exact raw-shallow-array exclusion, old-alias timing and disposal.'},
        {'id': 'NATIVE-PRIVATE-PROPERTY', 'category': 'remaining_risk', 'status': 'unresolved',
         'root_cause': 'Native Observer.dep is separate from per-property deps captured in defineReactive closures. Structural subscriptions cannot substitute for those property deps.',
         'repair_requirement': 'Review an explicit producer-owned dependency interoperability contract before implementing it. Preserve identity, notification timing, error routing and cleanup. Do not silently use global tracking patches, duplicate observation, polling or a Vue watch/effect as the San implementation.'},
        *[{'id': 'NATIVE-OPEN-' + str(i), 'category': 'remaining_risk', 'status': 'unresolved', 'scope': s}
          for i, s in enumerate(audit['open_boundaries'][1:], 1)]])
    report = f'''## 2026-11-14：原生 Ref 结构依赖 v13 部分闭环

本轮继续V12的6个深层反例，依据冻结Vue2.7.16的 `defineReactive`／`dependArray` 区分整体Ref、子观察器结构和私有属性依赖；不把其中一种订阅当作全部依赖。

- 新增独立通用实验规则：在固定原生Ref值getter对应边界收集其现有 `__ob__.dep`，仅当值本身已有观察器且为数组时，继续收集数组元素／嵌套数组的结构dep。shallowRef可能持有已观察数组，也可能持有未观察的原始数组，二者不得一概处理。
- 不改输入对象、Ref、观察器或属性getter／setter身份，不安装第二套观察器，不改全局 `Dep.target` 或框架原型，不使用Vue watch/effect、轮询或复制对象补通知。仍依赖固定版本私有dep能力，**仅为互操作实验，不是稳定公共API或生产规则**。
- 原Ref矩阵192点差异 **6→{stats['refs']['mismatches']}**，数组变更反例已匹配；剩余为对象属性写入、数组元素对象属性写入，各在两个开发对象出现tick差异。原已一致点回退{len(regression_rows['refs'])}。
- 新增11类结构场景、{stats['structure']['pairs']}点，**{stats['structure']['pairs'] - stats['structure']['mismatches']}/{stats['structure']['pairs']}一致，{stats['structure']['mismatches']}处差异**。同一场景矩阵旧V12差异{audit['baseline_structure_mismatches']}→{stats['structure']['mismatches']}，旧已一致点回退{len(regression_rows['structure'])}。
- 已匹配：push／pop／splice／reverse／sort、嵌套数组、数组元素或Ref对象的Vue.set／delete结构通知、旧别名首次flush前通知与后续清理、shallowRef已有观察数组、原始浅数组不得误订阅元素结构、原始数组下标不应擅自响应式化。这里的nativeSet明确是Vue.set输入API，不与上一轮raw赋值映射混淆。
- 新增失败来自 `Vue.set` 新属性后的再次普通属性写入，两开发对象各1点。它与旧4点均指向私有属性依赖未接入，分别保留原始观察，不合并成正式组件缺陷率。剩余问题不是再加结构订阅或Prompt就能保证修复。
- 原116、扩展152、描述符104、路径172点继续一致；另保存既有原生父子36点／共享别名56点回归。它们不等于已证明原生Ref传给子组件后的计算／渲染缓存传播，后者另列未覆盖风险。
- 新结构矩阵44次运行的原生观察器订阅在销毁后均清理，22个Ref清理对照以及旧Ref48个清理对照无新增异常／残余订阅；两个父实例共享Ref／数组／元素结构dep时各仅1个订阅，释放一个仍服务另一个，最后全部释放。属性访问器、观察器和对象身份、Data／Dep原型与全局target保持不变。
- {sum(t['count'] for t in tests)}项定向测试（两个独立进程工作线程运行只读suite）；包括移除结构收集重现旧数组失败，以及错误地遍历原始shallow数组重现误通知的反向保护。测试通过包含未解决反例的稳定复现，不表示全部迁移通过。
- 原扩展48个清理对照仍有 **{audit['expanded_cleanup_mismatches']}** 个生命周期错误通道差异。三项生产阻断与独立候选门保留，伪造validation_passed仍拒绝。0模型调用、未启动服务器／浏览器、无新增人工通过声明；原批 **24/30通过、6失败、0执行错误、1,821,544 tokens** 不变。

证据：`{OUT.relative_to(ROOT).as_posix()}`；修复前输入／Notebook96单元副本：`{BASE.relative_to(ROOT).as_posix()}`；预回放反例：`{pre.relative_to(ROOT).as_posix()}`。Notebook只追加，历史单元与metadata保留；验证JSON和代码单元，不声称Notebook UI渲染验收。

方法边界与下一步：两个开发对象、固定运行时、有限DOM／最小根渲染与桩存储／定时器；私有属性dep、子组件原生Ref缓存传播、custom／computed Ref、伪造dep、完整反射及错误桥仍未证明。**下一步先形成并审核显式的外来依赖互操作协议设计**（输入提供方职责、订阅范围、身份、时序、异常与清理），再决定实现；本轮未自行引入该协议，也不通过缩小公开值域、复制输入或换用隐含Vue watch放行生产。
'''
    with (OUT / 'REPORT.md').open('x', encoding='utf-8') as stream: stream.write(report)
    seal(OUT); verify(OUT)
    if any(regression_rows.values()) or any(stats[n]['mismatches'] for n in ['expanded', 'original', 'descriptors', 'paths']) or stats['refs']['mismatches'] != 4 or stats['structure']['mismatches'] != 2 or cleanup_failures or native_cleanup_failures or not all(t['returncode'] == 0 and t['count'] > 0 for t in tests) or not gate['should_stop']:
        raise RuntimeError('Unexpected failure preserved; Notebook not appended')
    append_notebook(old, report, pre)
    print(json.dumps({k: v for k, v in audit.items() if k not in {'code_sha256', 'protected_files_sha256'}}, ensure_ascii=False))


def append_notebook(old, report, pre):
    check = f'''from pathlib import Path
import json,hashlib
root=next(p for p in [Path.cwd(),*Path.cwd().parents] if (p/'migration_pipeline').is_dir())
folder=root/'{OUT.relative_to(ROOT).as_posix()}'
base=root/'{BASE.relative_to(ROOT).as_posix()}'
for d in [folder,base,root/'{pre.relative_to(ROOT).as_posix()}']:
    for line in (d/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected,name=line.split('  ',1)
        assert hashlib.sha256((d/name).read_bytes()).hexdigest()==expected,name
a=json.loads((folder/'audit.json').read_text(encoding='utf-8'))
assert not a['production_eligible'] and a['model_calls']==0 and not a['original_scores_modified']
assert all(not rows for rows in a['regressions'].values()) and all(t['returncode']==0 for t in a['tests'])
for name,stats in a['stats'].items():
    o=json.loads((folder/(name+'_observations.json')).read_text(encoding='utf-8'))
    assert len(o['pairs'])==stats['pairs'] and sum(not p['equal'] for p in o['pairs'])==stats['mismatches']
assert a['stats']['refs']=={{'pairs':192,'mismatches':4}} and a['stats']['structure']=={{'pairs':116,'mismatches':2}}
assert a['ref_cleanup_failures']==[] and a['native_observer_cleanup_failures']==[] and a['expanded_cleanup_mismatches']==1
assert json.loads((folder/'forged_pass_gate.json').read_text(encoding='utf-8'))['should_stop']
old=json.loads((base/'notebook_before.ipynb').read_text(encoding='utf-8'))
nb=json.loads((root/'{NB.relative_to(ROOT).as_posix()}').read_text(encoding='utf-8'))
assert nb['cells'][:len(old['cells'])]==old['cells'] and nb['metadata']==old['metadata']
print({{'original_ref_remaining':4,'new_structure_remaining':2,'production':'blocked'}})
'''
    assert json.loads(NB.read_text(encoding='utf-8')) == old
    old['cells'].extend([
        {'cell_type': 'markdown', 'id': 'v13-native-ref-structure-20261114', 'metadata': {}, 'source': report.splitlines(keepends=True)},
        {'cell_type': 'code', 'id': 'v13-native-ref-structure-check-20261114', 'metadata': {}, 'execution_count': None,
         'outputs': [], 'source': check.splitlines(keepends=True)}])
    assert old['nbformat'] == 4 and len({c['id'] for c in old['cells']}) == len(old['cells'])
    for c in old['cells']:
        if c['cell_type'] == 'code': compile(''.join(c['source']), c['id'], 'exec')
    NB.write_text(json.dumps(old, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    exec(compile(check, 'native-ref-structure-readonly', 'exec'), {})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-input', action='store_true'); parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if sum([args.freeze_input, args.preflight, args.execute]) != 1: parser.error('Choose exactly one action')
    if args.freeze_input: freeze()
    elif args.preflight: preflight()
    else: execute()
