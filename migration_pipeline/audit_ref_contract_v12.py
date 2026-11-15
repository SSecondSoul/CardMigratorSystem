"""Isolated Ref contract experiment; original production admission remains blocked."""
import argparse
import json
import re
import shutil
import subprocess

from migration_pipeline.audit_v7_source_queue_contract import ROOT, NB, sha, seal, verify, write
from migration_pipeline.audit_source_path_assignment_v11 import OUT as V11, regressions
from migration_pipeline.audit_v7_dynamic_shape import payload, node, RUNTIME
from migration_pipeline.audit_shape_input_expansion import RUNTIME as EXPANDED_RUNTIME
from migration_pipeline.audit_shape_observer_v10 import SUPPLEMENT as DESCRIPTOR_RUNTIME
from migration_pipeline.audit_source_path_assignment_v11 import PATH_RUNTIME

BASE = ROOT / 'data/experiments/analysis/formal_30_v4_ref_contract_v12_input_20261114'
OUT = ROOT / 'data/experiments/analysis/formal_30_v4_ref_contract_v12_20261114'
ADAPTER = 'migration_pipeline/probe_ref_contract_adapter_v12.cjs'
REF_RUNTIME = 'migration_pipeline/audit_ref_contract_v12_runtime.cjs'
FILES = ['migration_pipeline/probe_ref_contract_v12.cjs', ADAPTER, REF_RUNTIME,
         'migration_pipeline/audit_ref_contract_v12.py', 'tests/test_ref_contract_v12.py',
         'migration_pipeline/audit_ref_contract_v12_controls.cjs']


def freeze():
    verify(V11)
    a = json.loads((V11 / 'audit.json').read_text(encoding='utf-8'))
    assert a['stats']['expanded']['mismatches'] == 4 and a['cleanup_mismatch_count'] == 1
    protected = {**a['protected_files_sha256'], **a['code_sha256']}
    for name, expected in protected.items(): assert sha(ROOT / name) == expected, name
    BASE.mkdir(exist_ok=False)
    shutil.copy2(NB, BASE / 'notebook_before.ipynb')
    shutil.copy2(V11 / 'expanded_observations.json', BASE / 'v11_expanded_observations.json')
    write(BASE / 'protected_files.json', protected)
    seal(BASE); verify(BASE)
    print('Frozen V11 remaining marker counterexamples and 94-cell Notebook before Ref changes.')


def candidates(data):
    return {name: node(ROOT / ADAPTER, {'code': data[name], 'vue': data['vue' if name == 'san' else 'genericVue'],
                                      'experimental': True}) for name in ['san', 'genericSan']}


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
    verify(BASE)
    folder = OUT.with_name(OUT.name + '_preflight'); folder.mkdir(exist_ok=False)
    data = payload(); adapted = candidates(data)
    assert all(a['changes'] for a in adapted.values())
    request = {**data, **{n: a['code'] for n, a in adapted.items()}}
    counts = {}
    for name, runtime in [('expanded', EXPANDED_RUNTIME), ('refs', REF_RUNTIME)]:
        observed = node(ROOT / runtime, request); write(folder / (name + '_observations.json'), observed)
        counts[name] = {'pairs': len(observed['pairs']), 'mismatches': [p for p in observed['pairs'] if not p['equal']]}
    for name in FILES:
        if not (ROOT / name).exists(): continue
        dest = folder / 'code' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
    seal(folder); verify(folder); print(json.dumps(counts))


def execute():
    from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
    from migration_pipeline.utils.repair_scheduler import candidate_gate
    verify(BASE); verify(V11)
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
        with (OUT / (name + '_ref_contract.san')).open('x', encoding='utf-8') as stream: stream.write(a['code'])
    write(OUT / 'adaptation.json', {n: {k: v for k, v in a.items() if k != 'code'} for n, a in adapted.items()})
    observed = {}
    print('Replaying Ref inputs and all earlier native matrices.', flush=True)
    for name, runtime in [('refs', REF_RUNTIME), ('expanded', EXPANDED_RUNTIME), ('original', RUNTIME),
                          ('descriptors', DESCRIPTOR_RUNTIME), ('paths', PATH_RUNTIME),
                          ('ref_controls', 'migration_pipeline/audit_ref_contract_v12_controls.cjs')]:
        observed[name] = node(ROOT / runtime, request)
        write(OUT / (name + '_observations.json'), observed[name])
    before_request = {**data, **{name: (V11 / (name + '_path_assignment.san')).read_text(encoding='utf-8')
                               for name in ['san', 'genericSan']}}
    before_refs = node(ROOT / REF_RUNTIME, before_request)
    write(OUT / 'v11_ref_observations.json', before_refs)
    before_expanded = json.loads((BASE / 'v11_expanded_observations.json').read_text(encoding='utf-8'))
    regression_rows = {'expanded': regressions(before_expanded, observed['expanded']),
                       'refs': regressions(before_refs, observed['refs'])}
    mounted, aliases = broad_replay()
    write(OUT / 'mounted_observations.json', mounted); write(OUT / 'aliases_observations.json', aliases)
    diagnostic = source_parent_watch_semantics(adapted['san']['code'], data['vue'])
    write(OUT / 'production_diagnostics.json', {k: v for k, v in diagnostic.items() if k != 'code'})
    state = {'generated_code': data['san'], 'vue_source': data['vue'], 'validation_errors': diagnostic['findings']}
    gate = candidate_gate(state, {**state, 'generated_code': adapted['san']['code'], 'validation_errors': [], 'validation_passed': True})
    write(OUT / 'forged_pass_gate.json', gate)
    tests = []
    for suite in ['test_ref_contract_v12.py', 'test_source_path_assignment_v11.py', 'test_shape_observer_v10.py',
                  'test_shape_input_expansion.py', 'test_shape_observer_v9.py', 'test_source_property_assignment_v8.py',
                  'test_v7_source_queue_contract.py', 'test_v7_integration_contract.py']:
        print('Testing ' + suite, flush=True)
        proc = subprocess.run(['python', '-m', 'unittest', 'discover', '-s', 'tests', '-p', suite, '-v'],
                              cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        log = proc.stdout + proc.stderr
        with (OUT / (suite + '.log')).open('x', encoding='utf-8') as stream: stream.write(log)
        match = re.search(r'Ran (\d+) tests?', log)
        tests.append({'suite': suite, 'count': int(match[1]) if match else 0, 'returncode': proc.returncode})
        print(tests[-1], flush=True)
    for name, expected in {**protected, **hashes}.items(): assert sha(ROOT / name) == expected, name
    for name in FILES:
        dest = OUT / 'code' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
    stats = {n: {'pairs': len(observed[n]['pairs']), 'mismatches': sum(not p['equal'] for p in observed[n]['pairs'])}
             for n in ['refs', 'expanded', 'original', 'descriptors', 'paths']}
    ref_cleanup = observed['refs']['cleanup_pairs']
    old_cleanup = observed['expanded']['cleanup_pairs']
    gaps = sorted({p['scenario'] for p in observed['refs']['pairs'] if not p['equal']})
    audit = {'production_eligible': False, 'model_calls': 0, 'classification': 'remaining_risk_partial_ref_contract',
             'stats': stats, 'baseline_expanded_mismatches': 4,
             'baseline_ref_mismatches': sum(not p['equal'] for p in before_refs['pairs']),
             'remaining_ref_scenarios': gaps, 'regressions': regression_rows,
             'ref_cleanup_comparison_count': len(ref_cleanup),
             'ref_cleanup_failures': [p for p in ref_cleanup if not all(p[k] for k in ['errorsEqual', 'sourceSubscribersReleased', 'sanSubscribersReleased'])],
             'expanded_cleanup_comparison_count': len(old_cleanup), 'expanded_cleanup_mismatches': sum(not p['equal'] for p in old_cleanup),
             'tests': tests, 'code_sha256': hashes, 'protected_files_sha256': protected,
             'prior_notebook_cells': len(old['cells']), 'original_scores_modified': False, 'production_files_changed': False,
             'open_boundaries': ['Native deep Ref inner-property/array dependencies (six observed mismatches)',
                                 'Whole-root Ref replacement, customRef/computed Ref, arbitrary/spoofed dep providers and foreign observer interoperability',
                                 'Lifecycle error routing (one earlier cleanup mismatch)',
                                 'Arbitrary accessor effects, Proxy and complete reflection',
                                 'Production emitter/validator/candidate gate integration'],
             'native_ref_scope': 'Pinned Vue2.7.16 input ref/shallowRef; candidate directly subscribes exposed private dep capabilities only for bounded cases. No native Vue parent/watch/effect, Dep.target mutation or prototype patch. This is not a public stable production Ref implementation.'}
    write(OUT / 'audit.json', audit)
    write(OUT / 'coverage_obligations.json', [
        {'id': 'REF-BASE', 'category': 'remaining_risk', 'status': 'bounded_native_replay_matches',
         'scope': 'Strict boolean marker recognition, one-level object-property unwrapping, non-Ref writeback to old Ref, replacement, frozen/getter-only error behavior; no array-element auto-unwrapping.'},
        {'id': 'REF-NATIVE-SCALAR-SHALLOW', 'category': 'remaining_risk', 'status': 'bounded_native_replay_matches',
         'scope': 'Genuine pinned ref/scalar and shallowRef input, same-value/NaN/signed-zero, old-alias timing, per-owner cleanup.',
         'limits': audit['native_ref_scope']},
        {'id': 'REF-NATIVE-DEEP', 'category': 'remaining_risk', 'status': 'unresolved',
         'scenarios': gaps, 'mismatch_pairs': stats['refs']['mismatches'],
         'root_cause': 'Ref.dep notifies whole-value writes. Its inner Vue Observer/property deps are distinct and are not collected by the San bridge. Reading those native getters during a private token traversal does not subscribe to their deps.',
         'repair_requirement': 'Design and source-match a foreign-dependency interoperability contract without rewriting original Ref identity, adding duplicate observers, global tracking patches or secretly using a Vue watch/effect as the San implementation.'},
        *[{'id': 'REF-OPEN-' + str(i), 'category': 'remaining_risk', 'status': 'unresolved', 'scope': s}
          for i, s in enumerate(audit['open_boundaries'][1:], 1)]])
    report = f'''## 2026-11-14：Ref v12 部分契约修复与原生深层依赖反例

本轮按验证报告技能保存成功与失败，不将结构标记与真正Vue Ref混为一谈；不改变原30样本评分、生产Prompt／生成器／校验器／修复器／门禁或人工验收配置。

- **证据纠正**：上一轮剩余4点 `true_ref_marker_value` 使用 `{{__v_isRef:true,value:...}}`，仅证明结构标记反例，不等于原生Vue.ref全覆盖。本轮保留该旧反例，另用冻结Vue2.7.16的 `ref`／`shallowRef` 在两侧各自构造真实传入值。
- 修复独立通用实验规则：严格 `===true` 识别、普通响应式对象属性解包、旧Ref接收非Ref赋值时写回 `.value` 而非替换、Ref替换，以及原生冻结／只读错误。数组元素不自动解包，普通标记对象的原始 `.value` 也不擅自变为响应式。
- 原扩展152点差异 **4→{stats['expanded']['mismatches']}**，旧116、描述符104、路径172点继续保持一致；另保存原生父子36点、共享别名56点的原始回放。旧已一致点回退：扩展{len(regression_rows['expanded'])}、新增Ref矩阵对照旧V11为{len(regression_rows['refs'])}。
- 新增24类Ref场景、{stats['refs']['pairs']}个同步／tick点，其中 **{stats['refs']['pairs'] - stats['refs']['mismatches']}/{stats['refs']['pairs']}一致，{stats['refs']['mismatches']}处差异**。标量Ref、同值／NaN／正负零、替换与旧别名时序、数组Ref元素、shallowRef原始子值和整体替换匹配；原生深层Ref内属性写入、数组变更、数组元素属性写入三类各在两个开发对象出现tick差异。
- 对照旧V11，同一新增Ref矩阵的差异为{audit['baseline_ref_mismatches']}→{stats['refs']['mismatches']}；这是扩展值域后的部分改进，不是新正式样本缺陷率，也不是“Ref已全部通过”。六个深层失败在首次预回放即冻结，并在最终测试中要求持续可复现。
- 深层根因：整体 `.value` 与其内部Vue观察对象／属性有不同依赖。订阅Ref暴露的 `dep` 只覆盖整体值更新，私有token遍历并不会接入原生深层getter依赖。本轮不通过篡改全局 `Dep.target`、框架原型、重复观察器或暗用Vue watch/effect抹平差异。
- 原生标量／shallowRef部分直接订阅固定版本的私有dep能力，**仅为互操作实验，不是稳定公共API或可直接部署的生产Ref实现**。传入值的额外Vue运行时仅在测试设备中构造原生Ref，San组件仍由San执行，没有Vue父组件／watch／effect替它完成观察。
- 新Ref矩阵48个清理对照全部释放订阅并保持错误类别／通道一致；共享Ref的两个父实例共用一个订阅，释放一个后另一实例仍响应，最后释放后无残余回调。原扩展48个销毁对照仍有 **{audit['expanded_cleanup_mismatches']}** 个循环序列化生命周期错误通道差异，分别统计、不隐藏。
- {sum(t['count'] for t in tests)}项定向测试。包含反向破坏测试：关闭native dep通知会重现标量Ref失败；关闭写回分支会重现标记对象赋值失败。测试通过表示已匹配案例和未解决反例均按预期验证，不表示全部迁移通过。
- 三项生产阻断和独立候选门不变，伪造validation_passed并清空错误仍被拒绝。0模型调用、未启动服务器／浏览器、无新增人工通过声明；原批 **24/30通过、6失败、0执行错误、1,821,544 tokens** 不变。

证据：`{OUT.relative_to(ROOT).as_posix()}`；输入与Notebook94单元副本：`{BASE.relative_to(ROOT).as_posix()}`；初次深层失败：`{pre.relative_to(ROOT).as_posix()}`。Notebook仅追加、保留原单元和metadata，校验JSON／代码单元而非Notebook UI渲染。

范围与下一步：两个开发对象、固定运行时、有限DOM／最小根渲染、桩存储／定时器；旧设备V7／V9标签只是历史名称，不代表执行旧候选。whole-root Ref、customRef／computed Ref、伪造dep、副作用访问器、Proxy／完整反射未证明。**本步收尾不等于Ref完全闭环**：下一步先设计深层外来依赖的互操作方案，验证三类反例和清理／多实例边界；之后才进入受限错误桥与生产契约组合，不能据此提前启动或宣称独立正式测试通过。
'''
    with (OUT / 'REPORT.md').open('x', encoding='utf-8') as stream: stream.write(report)
    seal(OUT); verify(OUT)
    expected_gaps = sorted(['native_deep_ref_nested_property_dependency', 'native_deep_ref_array_mutator_dependency', 'native_deep_ref_array_element_dependency'])
    if any(regression_rows.values()) or any(stats[n]['mismatches'] for n in ['expanded', 'original', 'descriptors', 'paths']) or gaps != expected_gaps or stats['refs']['mismatches'] != 6 or audit['ref_cleanup_failures'] or not all(t['returncode'] == 0 for t in tests) or not gate['should_stop']:
        raise RuntimeError('Evidence preserved; unexpected failure, Notebook not appended')
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
assert a['stats']['refs']=={{'pairs':192,'mismatches':6}} and a['stats']['expanded']=={{'pairs':152,'mismatches':0}}
assert a['ref_cleanup_comparison_count']==48 and a['ref_cleanup_failures']==[]
assert a['expanded_cleanup_mismatches']==1
assert json.loads((folder/'forged_pass_gate.json').read_text(encoding='utf-8'))['should_stop']
old=json.loads((base/'notebook_before.ipynb').read_text(encoding='utf-8'))
nb=json.loads((root/'{NB.relative_to(ROOT).as_posix()}').read_text(encoding='utf-8'))
assert nb['cells'][:len(old['cells'])]==old['cells'] and nb['metadata']==old['metadata']
print({{'marker_matrix_mismatches':0,'native_ref_points':192,'unresolved_deep_ref_points':6,'production':'blocked'}})
'''
    assert json.loads(NB.read_text(encoding='utf-8')) == old
    old['cells'].extend([
        {'cell_type': 'markdown', 'id': 'v12-ref-partial-contract-20261114', 'metadata': {}, 'source': report.splitlines(keepends=True)},
        {'cell_type': 'code', 'id': 'v12-ref-partial-contract-check-20261114', 'metadata': {}, 'execution_count': None,
         'outputs': [], 'source': check.splitlines(keepends=True)}])
    assert old['nbformat'] == 4 and len({c['id'] for c in old['cells']}) == len(old['cells'])
    for c in old['cells']:
        if c['cell_type'] == 'code': compile(''.join(c['source']), c['id'], 'exec')
    NB.write_text(json.dumps(old, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    exec(compile(check, 'ref-contract-readonly', 'exec'), {})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-input', action='store_true')
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if sum([args.freeze_input, args.preflight, args.execute]) != 1: parser.error('Choose exactly one action')
    if args.freeze_input: freeze()
    elif args.preflight: preflight()
    else: execute()
