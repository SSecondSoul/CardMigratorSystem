"""Freeze/replay an explicit raw Vue assignment to no-option San path mapping."""
import argparse
import json
import re
import shutil
import subprocess

from migration_pipeline.audit_v7_source_queue_contract import ROOT, NB, sha, seal, verify, write
from migration_pipeline.audit_shape_observer_v10 import OUT as V10
from migration_pipeline.audit_v7_dynamic_shape import payload, node, RUNTIME
from migration_pipeline.audit_shape_input_expansion import RUNTIME as EXPANDED_RUNTIME
from migration_pipeline.audit_shape_observer_v10 import SUPPLEMENT as DESCRIPTOR_RUNTIME

BASE = ROOT / 'data/experiments/analysis/formal_30_v4_source_path_assignment_v11_input_20261114'
OUT = ROOT / 'data/experiments/analysis/formal_30_v4_source_path_assignment_v11_20261114'
ADAPTER = 'migration_pipeline/probe_source_path_assignment_adapter_v11.cjs'
PATH_RUNTIME = 'migration_pipeline/audit_source_path_assignment_v11_runtime.cjs'
FILES = ['migration_pipeline/probe_source_path_assignment_v11.cjs', ADAPTER, PATH_RUNTIME,
         'migration_pipeline/audit_source_path_assignment_v11.py', 'tests/test_source_path_assignment_v11.py',
         'migration_pipeline/audit_source_path_assignment_v11_controls.cjs']


def freeze():
    verify(V10)
    prior = json.loads((V10 / 'audit.json').read_text(encoding='utf-8'))
    assert prior['remaining_expanded_mismatches'] == 8 and prior['cleanup_mismatch_count'] == 1
    protected = {**prior['protected_files_sha256'], **prior['code_sha256']}
    for name in ['tests/manual/v7-acceptance.html', 'tests/manual/v7-acceptance.js',
                 'migration_pipeline/utils/source_parent_watch_semantics.cjs']:
        protected[name] = sha(ROOT / name)
    for name, expected in protected.items(): assert sha(ROOT / name) == expected, name
    BASE.mkdir(exist_ok=False)
    shutil.copy2(NB, BASE / 'notebook_before.ipynb')
    shutil.copy2(V10 / 'expanded_observations.json', BASE / 'v10_expanded_observations.json')
    write(BASE / 'protected_files.json', protected)
    seal(BASE); verify(BASE)
    print('Frozen V10 negatives, 92-cell Notebook, production and manual-page fingerprints.')


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
    mounted = node(prior / 'code/migration_pipeline/audit_parent_alias_child_runtime.cjs',
                   {**fixture, **common, 'v3': candidate['code']})
    aliases = node(ROOT / 'migration_pipeline/audit_parent_alias_observer_v4_runtime.cjs',
                   {'vue': fixture['vue'], 'v4': candidate['code'], **common})
    return mounted, aliases


def preflight():
    verify(BASE)
    folder = OUT.with_name(OUT.name + '_preflight'); folder.mkdir(exist_ok=False)
    data = payload(); adapted = candidates(data)
    assert all(a['changes'] for a in adapted.values())
    request = {**data, **{n: a['code'] for n, a in adapted.items()}}
    result = {}
    for name, runtime in [('expanded', EXPANDED_RUNTIME), ('paths', PATH_RUNTIME)]:
        observations = node(ROOT / runtime, request)
        write(folder / (name + '_observations.json'), observations)
        result[name] = {'pairs': len(observations['pairs']),
                        'mismatches': [(p['subject'], p['scenario'], p['phase']) for p in observations['pairs'] if not p['equal']]}
    for name in FILES:
        if not (ROOT / name).exists(): continue
        dest = folder / 'code' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
    seal(folder); verify(folder); print(json.dumps(result))


def regressions(before, after):
    assert len(before['pairs']) == len(after['pairs'])
    result = []
    for a, b in zip(before['pairs'], after['pairs']):
        assert tuple(a[k] for k in ['subject', 'scenario', 'phase']) == tuple(b[k] for k in ['subject', 'scenario', 'phase'])
        if a['equal'] and not b['equal']: result.append(b)
    return result


def execute():
    from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
    from migration_pipeline.utils.repair_scheduler import candidate_gate
    verify(BASE); verify(V10)
    preflight_folder = OUT.with_name(OUT.name + '_preflight'); verify(preflight_folder)
    old = json.loads((BASE / 'notebook_before.ipynb').read_text(encoding='utf-8'))
    assert json.loads(NB.read_text(encoding='utf-8')) == old, 'Notebook changed; never overwrite'
    protected = json.loads((BASE / 'protected_files.json').read_text(encoding='utf-8'))
    hashes = {name: sha(ROOT / name) for name in FILES}
    for name, expected in protected.items(): assert sha(ROOT / name) == expected, name
    OUT.mkdir(exist_ok=False)
    data = payload(); adapted = candidates(data)
    assert all(a['changes'] and not a['production_eligible'] for a in adapted.values())
    request = {**data, **{n: a['code'] for n, a in adapted.items()}}
    for name, value in adapted.items():
        with (OUT / (name + '_path_assignment.san')).open('x', encoding='utf-8') as stream: stream.write(value['code'])
    write(OUT / 'adaptation.json', {n: {k: v for k, v in a.items() if k != 'code'} for n, a in adapted.items()})
    print('Replaying original, expanded, descriptor and native path matrices.', flush=True)
    observed = {}
    for name, runtime in [('original', RUNTIME), ('expanded', EXPANDED_RUNTIME),
                          ('descriptors', DESCRIPTOR_RUNTIME), ('paths', PATH_RUNTIME),
                          ('delegation', 'migration_pipeline/audit_source_path_assignment_v11_controls.cjs')]:
        observed[name] = node(ROOT / runtime, request)
        write(OUT / (name + '_observations.json'), observed[name])
    frozen_v10 = {**data, **{name: (V10 / (name + '_shape_observer.san')).read_text(encoding='utf-8') for name in ['san', 'genericSan']}}
    before_paths = node(ROOT / PATH_RUNTIME, frozen_v10)
    write(OUT / 'v10_path_observations.json', before_paths)
    before = json.loads((BASE / 'v10_expanded_observations.json').read_text(encoding='utf-8'))
    expanded_regressions = regressions(before, observed['expanded'])
    path_regressions = regressions(before_paths, observed['paths'])
    mounted, aliases = broad_replay()
    write(OUT / 'mounted_observations.json', mounted); write(OUT / 'aliases_observations.json', aliases)
    diagnosis = source_parent_watch_semantics(adapted['san']['code'], data['vue'])
    write(OUT / 'production_diagnostics.json', {k: v for k, v in diagnosis.items() if k != 'code'})
    state = {'generated_code': data['san'], 'vue_source': data['vue'], 'validation_errors': diagnosis['findings']}
    gate = candidate_gate(state, {**state, 'generated_code': adapted['san']['code'], 'validation_errors': [], 'validation_passed': True})
    write(OUT / 'forged_pass_gate.json', gate)
    tests = []
    for suite in ['test_source_path_assignment_v11.py', 'test_shape_observer_v10.py', 'test_shape_input_expansion.py',
                  'test_shape_observer_v9.py', 'test_source_property_assignment_v8.py',
                  'test_v7_source_queue_contract.py', 'test_v7_integration_contract.py']:
        print('Testing ' + suite, flush=True)
        proc = subprocess.run(['python', '-m', 'unittest', 'discover', '-s', 'tests', '-p', suite, '-v'],
                              cwd=ROOT, text=True, encoding='utf-8', capture_output=True)
        log = proc.stdout + proc.stderr
        with (OUT / (suite + '.log')).open('x', encoding='utf-8') as stream: stream.write(log)
        match = re.search(r'Ran (\d+) tests?', log)
        tests.append({'suite': suite, 'count': int(match[1]) if match else 0, 'returncode': proc.returncode})
        print(tests[-1], flush=True)
    for name, expected in {**protected, **hashes}.items(): assert sha(ROOT / name) == expected, name
    for name in FILES:
        dest = OUT / 'code' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
    stats = {name: {'pairs': len(observed[name]['pairs']), 'mismatches': sum(not p['equal'] for p in observed[name]['pairs'])}
             for name in ['original', 'expanded', 'descriptors', 'paths']}
    cleanup = observed['expanded']['cleanup_pairs']
    audit = {'production_eligible': False, 'model_calls': 0, 'classification': 'remaining_risk_bounded_rule_closure',
             'stats': stats, 'baseline_expanded_mismatches': 8,
             'baseline_path_mismatches': sum(not p['equal'] for p in before_paths['pairs']),
             'remaining_scenarios': sorted({p['scenario'] for p in observed['expanded']['pairs'] if not p['equal']}),
             'expanded_regressions': expanded_regressions, 'path_regressions': path_regressions,
             'cleanup_comparison_count': len(cleanup), 'cleanup_mismatch_count': sum(not p['equal'] for p in cleanup),
             'tests': tests, 'code_sha256': hashes, 'protected_files_sha256': protected,
             'prior_notebook_cells': len(old['cells']), 'original_scores_modified': False, 'production_files_changed': False,
             'preflight_bundle': preflight_folder.relative_to(ROOT).as_posix(),
             'preflight_failure': 'Six native error comparisons differed because the serialized wrapper lost its module strict context. Added a local strict directive, with a deletion mutation test reproducing all six failures.',
             'open_boundaries': ['actual Ref unwrapping and foreign observers', 'source lifecycle/error reporting bridge',
                                 'arbitrary accessor effects, Proxy and reflection',
                                 'dynamic expressions / explicit San options have no claimed raw-source equivalent',
                                 'production emitter/validator/candidate gate integration']}
    write(OUT / 'audit.json', audit)
    write(OUT / 'coverage_obligations.json', [
        {'id': 'PATH-V11', 'category': 'remaining_risk', 'status': 'bounded_native_replay_matches',
         'scope': 'Static string/number property paths, no options, explicit source raw assignment mapping.',
         'behavior': 'Preserve root/child identity, raw new properties and array-index/length behavior, inherited/accessor descriptors, strict assignment errors; do not clone, auto-create intermediates or force new-key observation.',
         'not_proven': 'Vue.set/reactive additions, arbitrary native San API equivalence, explicit force/silent/dynamic paths. These are delegated, not certified.'},
        *[{'id': 'PATH-OPEN-' + str(i), 'category': 'remaining_risk', 'status': 'unresolved', 'scope': s}
          for i, s in enumerate(audit['open_boundaries'], 1)]])
    report = f'''## 2026-11-14：外部静态路径原生赋值 v11 离线闭环

本轮继续 V10 未闭合的 `external_new_path`，只新增独立实验规则，不改生产 Prompt／生成器／校验器／修复器／门禁或人工验收页。

- 源语义范围明确为 Vue 严格模式原生属性赋值，映射到 San 无选项的静态字符串／数字路径；不是 Vue.set，也不是声称任意 San Data.set 都应保持此语义。
- 根因：V10 对已知观察属性才走原生 setter，新属性转回 San 的 immutableSet，克隆父链并通知。V11 对上述明确映射执行原生路径遍历和最终赋值，保留根／子对象身份；新键、数组下标、length保持源生的非响应式行为，不补观察／通知，不自动创建缺失中间对象。原有响应式 setter 仍照常通知。
- 扩展152点差异 **8→{stats['expanded']['mismatches']}**，已一致点回退 **{len(expanded_regressions)}**，剩余仅 `true_ref_marker_value`。实际Ref的4个差异点仍作为未解决反例保留，不按“拒绝输入”认定等价。
- 新增28类路径场景、{stats['paths']['pairs']}个同步／tick点，旧V10差异{audit['baseline_path_mismatches']}→**{stats['paths']['mismatches']}**，旧已一致点回退{len(path_regressions)}。覆盖新键／重复赋值、别名、Data.get先读后写、删除后重建、数组索引／长度／孔洞、负数／小数／前导零键、缺失中间对象、null／原始值、冻结／密封对象、访问器、继承setter、特殊键和新加原始Ref标记对象。
- 原116点、描述符104点、原生父子组件36点、共享别名56点继续回归。所有原始观察均保存，不只保存成功计数。
- 初次新增路径测试有6个严格模式错误差异，先冻结源码与观察，再在被序列化的路径包装函数内补 `use strict`。反向移除该指令会重现6个差异；模块文件顶层strict不能替代生成代码内部strict，此项保护不能只依赖Prompt。
- force／silent／null或空options、动态路径及无关根仍交回原San接口，测试保留原表达式和options对象；根替换保持原行为，dispose恢复包装前接口、框架原型不改。这些委托测试不证明它们与Vue原生赋值等价。
- 48个扩展清理对照仍有 **{audit['cleanup_mismatch_count']}** 个生命周期错误报告通道差异。实际Ref、错误桥、任意访问器副作用、Proxy／完整反射、生产契约接入仍未解决；不把本轮剩余风险计为新正式样本缺陷率。
- {sum(t['count'] for t in tests)}项定向测试（包含旧反例持续可复现及新闭环保护）。三项生产阻断不变，伪造validation_passed并清空错误仍被独立候选门拒绝。
- 0模型调用、未启动服务器／浏览器、无新增人工通过声明、未改验收配置。原批 **24/30通过、6失败、0执行错误、1,821,544 tokens** 不变。

证据：`{OUT.relative_to(ROOT).as_posix()}`；修复前输入／Notebook92单元副本：`{BASE.relative_to(ROOT).as_posix()}`；失败预回放：`{preflight_folder.relative_to(ROOT).as_posix()}`。Notebook只追加，原单元和metadata保留；验证JSON与代码单元，不是Notebook UI渲染。

有效性边界：两个开发对象、固定Vue2.7.16／San3.15.6、有限DOM与最小根渲染、桩存储和定时器；旧设备的V7／V9名称仅是历史标签，本轮实际候选为V11；编码不证明框架私有标记、数组方法放置或完整反射等价。下一步处理真正Ref的解包／写回契约，再验证受限错误桥，仍不能据此直接放行生产或称为独立正式测试通过。
'''
    with (OUT / 'REPORT.md').open('x', encoding='utf-8') as stream: stream.write(report)
    seal(OUT); verify(OUT)
    if expanded_regressions or path_regressions or any(stats[n]['mismatches'] for n in ['original', 'descriptors', 'paths']) or not all(t['returncode'] == 0 for t in tests) or not gate['should_stop']:
        raise RuntimeError('Failed evidence preserved; Notebook not appended')
    append_notebook(old, report, preflight_folder)
    print(json.dumps({k: v for k, v in audit.items() if k not in {'code_sha256', 'protected_files_sha256'}}, ensure_ascii=False))


def append_notebook(old, report, preflight_folder):
    check = f'''from pathlib import Path
import json,hashlib
root=next(p for p in [Path.cwd(),*Path.cwd().parents] if (p/'migration_pipeline').is_dir())
folder=root/'{OUT.relative_to(ROOT).as_posix()}'
base=root/'{BASE.relative_to(ROOT).as_posix()}'
for d in [folder,base,root/'{preflight_folder.relative_to(ROOT).as_posix()}']:
    for line in (d/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected,name=line.split('  ',1)
        assert hashlib.sha256((d/name).read_bytes()).hexdigest()==expected,name
a=json.loads((folder/'audit.json').read_text(encoding='utf-8'))
assert not a['production_eligible'] and a['model_calls']==0 and not a['original_scores_modified']
assert a['expanded_regressions']==[] and a['path_regressions']==[]
assert a['remaining_scenarios']==['true_ref_marker_value']
assert all(t['returncode']==0 for t in a['tests'])
for name,stats in a['stats'].items():
    o=json.loads((folder/(name+'_observations.json')).read_text(encoding='utf-8'))
    assert len(o['pairs'])==stats['pairs'] and sum(not p['equal'] for p in o['pairs'])==stats['mismatches']
assert a['stats']['paths']=={{'pairs':172,'mismatches':0}} and a['stats']['expanded']['mismatches']==4
o=json.loads((folder/'expanded_observations.json').read_text(encoding='utf-8'))
assert len(o['cleanup_pairs'])==48 and sum(not p['equal'] for p in o['cleanup_pairs'])==a['cleanup_mismatch_count']==1
assert json.loads((folder/'forged_pass_gate.json').read_text(encoding='utf-8'))['should_stop']
old=json.loads((base/'notebook_before.ipynb').read_text(encoding='utf-8'))
nb=json.loads((root/'{NB.relative_to(ROOT).as_posix()}').read_text(encoding='utf-8'))
assert nb['cells'][:len(old['cells'])]==old['cells'] and nb['metadata']==old['metadata']
print({{'path_pairs':a['stats']['paths']['pairs'],'remaining_ref_pairs':a['stats']['expanded']['mismatches'],'production':'blocked'}})
'''
    assert json.loads(NB.read_text(encoding='utf-8')) == old
    old['cells'].extend([
        {'cell_type': 'markdown', 'id': 'v11-source-path-assignment-20261114', 'metadata': {}, 'source': report.splitlines(keepends=True)},
        {'cell_type': 'code', 'id': 'v11-source-path-assignment-check-20261114', 'metadata': {}, 'execution_count': None,
         'outputs': [], 'source': check.splitlines(keepends=True)}])
    assert old['nbformat'] == 4 and len({c['id'] for c in old['cells']}) == len(old['cells'])
    for c in old['cells']:
        if c['cell_type'] == 'code': compile(''.join(c['source']), c['id'], 'exec')
    NB.write_text(json.dumps(old, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    exec(compile(check, 'path-assignment-readonly', 'exec'), {})


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
