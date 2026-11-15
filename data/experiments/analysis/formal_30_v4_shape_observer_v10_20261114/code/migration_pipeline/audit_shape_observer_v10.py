"""Frozen native replay of descriptor/opaque-value observer experiment (not production)."""
import argparse
import json
import re
import shutil
import subprocess

from migration_pipeline.audit_v7_source_queue_contract import ROOT, NB, sha, seal, verify, write
from migration_pipeline.audit_shape_input_expansion import OUT as EXPANDED, RUNTIME as EXPANSION_RUNTIME
from migration_pipeline.audit_v7_dynamic_shape import payload, node, RUNTIME

BASE = ROOT / 'data/experiments/analysis/formal_30_v4_shape_observer_v10_input_20261114'
OUT = ROOT / 'data/experiments/analysis/formal_30_v4_shape_observer_v10_20261114'
ADAPTER = 'migration_pipeline/probe_shape_observer_adapter_v10.cjs'
FILES = ['migration_pipeline/probe_shape_observer_v10.cjs', ADAPTER,
         'migration_pipeline/audit_shape_observer_v10.py', 'tests/test_shape_observer_v10.py',
         'migration_pipeline/audit_shape_descriptors_v10_runtime.cjs']
SUPPLEMENT = 'migration_pipeline/audit_shape_descriptors_v10_runtime.cjs'


def freeze():
    verify(EXPANDED)
    audit = json.loads((EXPANDED / 'audit.json').read_text(encoding='utf-8'))
    assert audit['mismatch_pair_count'] == 80 and audit['cleanup_mismatch_count'] == 1
    protected = {**audit['code_sha256'], **audit['protected_files_sha256']}
    for name, expected in protected.items(): assert sha(ROOT / name) == expected, name
    BASE.mkdir(exist_ok=False)
    shutil.copy2(NB, BASE / 'notebook_before.ipynb')
    shutil.copy2(EXPANDED / 'observations.json', BASE / 'v9_expanded_observations.json')
    write(BASE / 'protected_files.json', protected)
    seal(BASE); verify(BASE)
    print('Frozen 80 action differences, one cleanup difference and Notebook before V10 edits.')


def candidates(data):
    return {name: node(ROOT / ADAPTER, {'code': data[name], 'vue': data['vue' if name == 'san' else 'genericVue'],
                                      'experimental': True}) for name in ['san', 'genericSan']}


def preflight():
    verify(BASE)
    folder = OUT.with_name(OUT.name + '_preflight')
    folder.mkdir(exist_ok=False)
    data = payload(); adapted = candidates(data)
    assert all(a['changes'] for a in adapted.values())
    request = {**data, **{n: a['code'] for n, a in adapted.items()}}
    observations = node(ROOT / EXPANSION_RUNTIME, request)
    original = node(ROOT / RUNTIME, request)
    write(folder / 'observations.json', observations)
    write(folder / 'original_observations.json', original)
    for name in FILES:
        if not (ROOT / name).exists(): continue
        dest = folder / 'code' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
    seal(folder); verify(folder)
    print(json.dumps({'expanded_mismatches': sum(not p['equal'] for p in observations['pairs']),
                      'remaining_scenarios': sorted({p['scenario'] for p in observations['pairs'] if not p['equal']}),
                      'original_mismatches': sum(not p['equal'] for p in original['pairs']),
                      'cleanup_mismatches': sum(not p['equal'] for p in observations['cleanup_pairs'])}))


def descriptor_preflight():
    folder = OUT.with_name(OUT.name + '_descriptor_preflight_failed')
    folder.mkdir(exist_ok=False)
    data = payload(); adapted = candidates(data)
    request = {**data, **{n: a['code'] for n, a in adapted.items()}}
    observed = node(ROOT / 'migration_pipeline/audit_shape_descriptors_v10_runtime.cjs', request)
    write(folder / 'observations.json', observed)
    for name in FILES:
        if not (ROOT / name).exists(): continue
        dest = folder / 'code' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
    seal(folder); verify(folder)
    print('Frozen supplemental mismatch pairs:', sum(not p['equal'] for p in observed['pairs']))


def broad_replay(data):
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


def execute():
    from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
    from migration_pipeline.utils.repair_scheduler import candidate_gate
    verify(BASE); verify(EXPANDED)
    failed = OUT.with_name(OUT.name + '_descriptor_preflight_failed'); verify(failed)
    old = json.loads((BASE / 'notebook_before.ipynb').read_text(encoding='utf-8'))
    assert json.loads(NB.read_text(encoding='utf-8')) == old, 'Notebook changed; never overwrite'
    protected = json.loads((BASE / 'protected_files.json').read_text(encoding='utf-8'))
    hashes = {n: sha(ROOT / n) for n in FILES}
    for name, expected in protected.items(): assert sha(ROOT / name) == expected, name
    OUT.mkdir(exist_ok=False)
    data = payload(); adapted = candidates(data)
    assert all(a['changes'] and not a['production_eligible'] for a in adapted.values())
    request = {**data, **{n: a['code'] for n, a in adapted.items()}}
    for name, value in adapted.items():
        with (OUT / (name + '_shape_observer.san')).open('x', encoding='utf-8') as stream: stream.write(value['code'])
    write(OUT / 'adaptation.json', {n: {k: v for k, v in a.items() if k != 'code'} for n, a in adapted.items()})
    print('Replaying original, expanded and supplemental native matrices.', flush=True)
    original = node(ROOT / RUNTIME, request)
    expanded = node(ROOT / EXPANSION_RUNTIME, request)
    supplement = node(ROOT / SUPPLEMENT, request)
    mounted, aliases = broad_replay(data)
    for name, value in [('original', original), ('expanded', expanded), ('supplement', supplement),
                        ('mounted', mounted), ('aliases', aliases)]: write(OUT / (name + '_observations.json'), value)
    before = json.loads((BASE / 'v9_expanded_observations.json').read_text(encoding='utf-8'))
    regressions = []
    assert len(before['pairs']) == len(expanded['pairs'])
    for a, b in zip(before['pairs'], expanded['pairs']):
        assert tuple(a[k] for k in ['subject', 'scenario', 'phase']) == tuple(b[k] for k in ['subject', 'scenario', 'phase'])
        if a['equal'] and not b['equal']: regressions.append(b)
    diagnosis = source_parent_watch_semantics(adapted['san']['code'], data['vue'])
    write(OUT / 'production_diagnostics.json', {k: v for k, v in diagnosis.items() if k != 'code'})
    state = {'generated_code': data['san'], 'vue_source': data['vue'], 'validation_errors': diagnosis['findings']}
    gate = candidate_gate(state, {**state, 'generated_code': adapted['san']['code'], 'validation_errors': [], 'validation_passed': True})
    write(OUT / 'forged_pass_gate.json', gate)
    tests = []
    for suite in ['test_shape_observer_v10.py', 'test_shape_input_expansion.py', 'test_shape_observer_v9.py',
                  'test_source_property_assignment_v8.py', 'test_v7_source_queue_contract.py', 'test_v7_integration_contract.py']:
        print('Testing ' + suite, flush=True)
        result = subprocess.run(['python', '-m', 'unittest', 'discover', '-s', 'tests', '-p', suite, '-v'],
                                cwd=ROOT, text=True, encoding='utf-8', capture_output=True)
        log = result.stdout + result.stderr
        with (OUT / (suite + '.log')).open('x', encoding='utf-8') as stream: stream.write(log)
        match = re.search(r'Ran (\d+) tests?', log)
        tests.append({'suite': suite, 'count': int(match[1]) if match else 0, 'returncode': result.returncode})
        print(tests[-1], flush=True)
    for name, expected in {**protected, **hashes}.items(): assert sha(ROOT / name) == expected, name
    for name in FILES:
        dest = OUT / 'code' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
    remaining = [p for p in expanded['pairs'] if not p['equal']]
    audit = {'production_eligible': False, 'model_calls': 0, 'classification': 'remaining_risk_experimental_rule_closure',
             'baseline_expanded_mismatches': 80, 'expanded_pair_count': len(expanded['pairs']),
             'remaining_expanded_mismatches': len(remaining), 'remaining_scenarios': sorted({p['scenario'] for p in remaining}),
             'original_pair_count': len(original['pairs']), 'original_mismatches': sum(not p['equal'] for p in original['pairs']),
             'supplemental_pair_count': len(supplement['pairs']), 'supplemental_mismatches': sum(not p['equal'] for p in supplement['pairs']),
             'cleanup_comparison_count': len(expanded['cleanup_pairs']),
             'cleanup_mismatch_count': sum(not p['equal'] for p in expanded['cleanup_pairs']),
             'regressions': regressions, 'tests': tests, 'code_sha256': hashes, 'protected_files_sha256': protected,
             'prior_notebook_cells': len(old['cells']), 'original_scores_modified': False, 'production_files_changed': False,
             'failed_preflight': failed.relative_to(ROOT).as_posix(),
             'failed_preflight_reason': 'Two supplemental action/tick pairs disagreed after changing __v_skip on an already observed object. Source _traverse reads the flag before walking. Added the same early exit; preserved failed code and all observations.',
             'open_boundaries': ['actual Ref unwrapping and foreign observers', 'external new-path Data.set mapping',
                                 'lifecycle error routing', 'arbitrary accessor effects, Proxy and full reflection',
                                 'restricted production emitter/validator/gate integration']}
    write(OUT / 'audit.json', audit)
    obligations = [
        {'id': 'V10-DESCRIPTOR', 'category': 'remaining_risk', 'status': 'bounded_native_replay_matches',
         'scope': 'Pure/stable accessors, original setter receiver/throw/transform, configurable readonly conversion, nonconfigurable skipping, array-inserted accessor.',
         'not_proven': 'Arbitrary accessor side effects or getter-call-count equivalence; audit snapshots themselves read values.'},
        {'id': 'V10-VALUES', 'category': 'remaining_risk', 'status': 'bounded_native_replay_matches',
         'scope': 'Map/Set/RegExp assignment identity and raw mutations; Symbol properties, null/custom plain-object prototypes, false Ref marker, true/false skip flag.'},
        *[{'id': 'V10-OPEN-' + str(i), 'category': 'remaining_risk', 'status': 'unresolved', 'scope': scope}
          for i, scope in enumerate(audit['open_boundaries'], 1)]]
    write(OUT / 'coverage_obligations.json', obligations)
    report = f'''## 2026-11-14：描述符与特殊值观察器 v10 离线修复

本轮针对冻结 V9 的公开输入反例修复独立通用实验规则，不改生产 Prompt、生成器、校验器、修复器、候选门或验收配置。不是 TaskManager 专用手改，也未重新生产正式样本。

- 根因：V9 把观察资格与赋值资格合并，以描述符／原型白名单拒绝原生 Vue 可接受的值。对照冻结 Vue 2.7.16 的 `observe`、`defineReactive`、`_traverse`，将二者分离。Map／Set／RegExp 保留对象身份但不观察；普通对象按自有可枚举字符串键处理，保留符号键与原型。
- 不可配置属性跳过，不再拒绝整个对象；可配置访问器保留原 getter／setter 和对象接收者；getter-only 写入无操作，原 setter 异常不发通知；可配置但只读的数据属性依源实现转为响应式。假 Ref 标记不按真 Ref 拒绝，skip 标记按源策略处理。实际 Ref 仍未修复，不以拒绝它作为等价证明。
- 冻结扩展矩阵 24 类、152 个同步／tick点，不一致 **80→{len(remaining)}**，剩余为 `true_ref_marker_value` 与 `external_new_path`；原已一致点回退 **{len(regressions)}**。原116点仍有 **{audit['original_mismatches']}** 个差异。
- 新增13类、{len(supplement['pairs'])}点，差异 **{audit['supplemental_mismatches']}**；包含传入对象身份、setter接收者、异常、转换、getter-only、只读描述符、符号子对象、数组插入及观察后修改skip标记。另保留原生父子组件36点、共享别名／数组56点回归（原始观察输出均保存）。
- 补充测试先发现2个差异点：已观察对象开启skip后仍收集深度属性；失败源码／原始观察已先冻结，再对照 `_traverse` 补充早退。不是放宽断言或丢弃失败场景。初始预回放与失败补充预回放都保留。
- 48个清理阶段对照仍有 **{audit['cleanup_mismatch_count']}** 个差异：循环值销毁序列化错误的框架报告通道不同；没有隐藏到动作比较指标中。实际Ref、外部新路径身份／通知、生命周期错误桥及任意访问器副作用仍是 `remaining_risk`，不计为新正式样本缺陷率。
- {sum(t['count'] for t in tests)}项定向单元／回归测试，原始日志见证据目录。测试通过同时要求已知剩余反例持续可复现，不能解读为所有输入均已修复。
- 三项生产阻断保留，伪造 `validation_passed` 并清空错误仍被独立候选门拒绝。0模型调用、无服务器／浏览器启动、无新增人工通过声明；原批 **24/30通过、6失败、0执行错误、1,821,544 tokens** 不变。

证据：`{OUT.relative_to(ROOT).as_posix()}`；修复前输入与原90单元Notebook副本：`{BASE.relative_to(ROOT).as_posix()}`；失败反例：`{failed.relative_to(ROOT).as_posix()}`。本节仅追加，历史单元和metadata不改；JSON／代码校验不代表Notebook UI可视化验收。

方法边界：两个开发对象、固定运行时、有限DOM与最小根渲染、桩存储／定时器；扩展设备沿用V9标签只是历史标签，不代表本轮执行了旧候选。语义编码不比较Vue的 `__ob__` 与WeakMap、数组方法放置位置，也不证明完整反射等价。下一步先解决外部新路径映射与实际Ref契约，再完成受限错误桥和生产接入；不能直接启动新独立测试以替代这些闭环。
'''
    with (OUT / 'REPORT.md').open('x', encoding='utf-8') as stream: stream.write(report)
    seal(OUT); verify(OUT)
    if regressions or audit['original_mismatches'] or audit['supplemental_mismatches'] or not all(t['returncode'] == 0 for t in tests) or not gate['should_stop']:
        raise RuntimeError('Failed evidence preserved; Notebook not appended')
    check = f'''from pathlib import Path
import json,hashlib
root=next(p for p in [Path.cwd(),*Path.cwd().parents] if (p/'migration_pipeline').is_dir())
folder=root/'{OUT.relative_to(ROOT).as_posix()}'
base=root/'{BASE.relative_to(ROOT).as_posix()}'
for d in [folder,base,root/'{failed.relative_to(ROOT).as_posix()}']:
    for line in (d/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected,name=line.split('  ',1)
        assert hashlib.sha256((d/name).read_bytes()).hexdigest()==expected,name
a=json.loads((folder/'audit.json').read_text(encoding='utf-8'))
assert not a['production_eligible'] and a['model_calls']==0 and a['regressions']==[]
assert a['original_mismatches']==0 and a['supplemental_mismatches']==0
assert all(t['returncode']==0 for t in a['tests'])
o=json.loads((folder/'expanded_observations.json').read_text(encoding='utf-8'))
assert len(o['pairs'])==a['expanded_pair_count'] and sum(not p['equal'] for p in o['pairs'])==a['remaining_expanded_mismatches']
assert len(o['cleanup_pairs'])==48 and sum(not p['equal'] for p in o['cleanup_pairs'])==a['cleanup_mismatch_count']
assert a['remaining_scenarios']==['external_new_path','true_ref_marker_value']
assert json.loads((folder/'forged_pass_gate.json').read_text(encoding='utf-8'))['should_stop']
old=json.loads((base/'notebook_before.ipynb').read_text(encoding='utf-8'))
nb=json.loads((root/'{NB.relative_to(ROOT).as_posix()}').read_text(encoding='utf-8'))
assert nb['cells'][:len(old['cells'])]==old['cells'] and nb['metadata']==old['metadata']
print({{'original_pairs':a['original_pair_count'],'expanded_remaining':a['remaining_expanded_mismatches'],'supplemental_pairs':a['supplemental_pair_count'],'production':'blocked'}})
'''
    assert json.loads(NB.read_text(encoding='utf-8')) == old
    old['cells'].extend([
        {'cell_type': 'markdown', 'id': 'v10-shape-descriptors-20261114', 'metadata': {}, 'source': report.splitlines(keepends=True)},
        {'cell_type': 'code', 'id': 'v10-shape-descriptors-check-20261114', 'metadata': {}, 'execution_count': None,
         'outputs': [], 'source': check.splitlines(keepends=True)}])
    assert len({c['id'] for c in old['cells']}) == len(old['cells']) and old['nbformat'] == 4
    for cell in old['cells']:
        if cell['cell_type'] == 'code': compile(''.join(cell['source']), cell['id'], 'exec')
    NB.write_text(json.dumps(old, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    exec(compile(check, 'shape-descriptors-readonly', 'exec'), {})
    print(json.dumps({k: v for k, v in audit.items() if k not in {'code_sha256', 'protected_files_sha256'}}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-input', action='store_true')
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--descriptor-preflight', action='store_true')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if sum([args.freeze_input, args.preflight, args.descriptor_preflight, args.execute]) != 1: parser.error('Choose exactly one action')
    if args.freeze_input: freeze()
    elif args.preflight: preflight()
    elif args.descriptor_preflight: descriptor_preflight()
    else: execute()
