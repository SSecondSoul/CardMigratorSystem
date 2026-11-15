"""Isolated value/shape observer follow-up to frozen V8 counterexamples."""
import argparse
import json
import re
import shutil
import subprocess

from migration_pipeline.audit_v7_source_queue_contract import ROOT, NB, sha, seal, verify, write
from migration_pipeline.audit_v7_dynamic_shape import payload, node, RUNTIME
from migration_pipeline.audit_source_property_assignment_v8 import OUT as V8

BASE = ROOT / 'data/experiments/analysis/formal_30_v4_shape_observer_v9_input_20261114'
FAILED = ROOT / 'data/experiments/analysis/formal_30_v4_shape_observer_v9_20261114'
OUT = ROOT / 'data/experiments/analysis/formal_30_v4_shape_observer_v9_retry_20261114'
ADAPTER = 'migration_pipeline/probe_shape_observer_adapter_v9.cjs'
FILES = ['migration_pipeline/probe_shape_observer_v9.cjs', ADAPTER,
         'migration_pipeline/audit_shape_observer_v9.py', 'tests/test_shape_observer_v9.py']
PROTECTED = ['migration_pipeline/probe_parent_alias_observer_v4.cjs',
             'migration_pipeline/probe_source_property_assignment_v8.cjs', RUNTIME,
             'migration_pipeline/stages/validate.py', 'migration_pipeline/stages/repair.py',
             'migration_pipeline/utils/repair_scheduler.py', 'migration_pipeline/utils/repair_prompt.py',
             'tests/manual/v7-acceptance-config.json']


def freeze():
    verify(V8)
    audit = json.loads((V8 / 'audit.json').read_text(encoding='utf-8'))
    assert audit['remaining_mismatches'] == 18 and not audit['production_eligible']
    for name, expected in audit['code_sha256'].items(): assert sha(ROOT / name) == expected, name
    BASE.mkdir(exist_ok=False)
    shutil.copy2(NB, BASE / 'notebook_before.ipynb')
    shutil.copy2(V8 / 'observations.json', BASE / 'v8_observations.json')
    for name in ['san', 'genericSan']:
        shutil.copy2(V8 / (name + '_source_assignment.san'), BASE / (name + '.san'))
    write(BASE / 'protected_files.json', {n: sha(ROOT / n) for n in PROTECTED})
    seal(BASE); verify(BASE)
    print('Frozen V8 negatives and current production/acceptance fingerprints.')


def candidates(data):
    return {name: node(ROOT / ADAPTER, {'code': data[name], 'vue': data['vue' if name == 'san' else 'genericVue'],
                                      'experimental': True}) for name in ['san', 'genericSan']}


def execute():
    from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
    from migration_pipeline.utils.repair_scheduler import candidate_gate
    verify(BASE); verify(V8); verify(FAILED)
    old = json.loads((BASE / 'notebook_before.ipynb').read_text(encoding='utf-8'))
    assert json.loads(NB.read_text(encoding='utf-8')) == old, 'Notebook changed; never overwrite'
    hashes = {n: sha(ROOT / n) for n in FILES}
    protected = json.loads((BASE / 'protected_files.json').read_text(encoding='utf-8'))
    for name, expected in protected.items(): assert sha(ROOT / name) == expected, name
    data = payload(); adapted = candidates(data)
    assert all(a['changes'] and not a['production_eligible'] for a in adapted.values())
    OUT.mkdir(exist_ok=False)
    for name, value in adapted.items():
        with (OUT / (name + '_shape_observer.san')).open('x', encoding='utf-8') as stream: stream.write(value['code'])
    write(OUT / 'adaptation.json', {n: {k: v for k, v in a.items() if k != 'code'} for n, a in adapted.items()})
    observed = node(ROOT / RUNTIME, {**data, **{n: a['code'] for n, a in adapted.items()}})
    for run in observed['runs']:
        if run['variant'] == 'san_v7': run['variant'] = 'san_v9_shape_observer'
    write(OUT / 'observations.json', observed)
    baseline = json.loads((BASE / 'v8_observations.json').read_text(encoding='utf-8'))
    assert len(baseline['pairs']) == len(observed['pairs'])
    regressions = [after for before, after in zip(baseline['pairs'], observed['pairs']) if before['equal'] and not after['equal']]
    diagnostics = source_parent_watch_semantics(adapted['san']['code'], data['vue'])
    write(OUT / 'production_diagnostics.json', {k: v for k, v in diagnostics.items() if k != 'code'})
    state = {'generated_code': data['san'], 'vue_source': data['vue'],
             'validation_errors': source_parent_watch_semantics(data['san'], data['vue'])['findings']}
    forged = candidate_gate(state, {**state, 'generated_code': adapted['san']['code'], 'validation_errors': [], 'validation_passed': True})
    write(OUT / 'forged_pass_gate.json', forged)
    tests = []
    for suite in ['test_shape_observer_v9.py', 'test_source_property_assignment_v8.py',
                  'test_v7_dynamic_shape.py', 'test_v7_source_queue_contract.py']:
        print('Testing ' + suite, flush=True)
        proc = subprocess.run(['python', '-m', 'unittest', 'discover', '-s', 'tests', '-p', suite, '-v'],
                              cwd=ROOT, text=True, encoding='utf-8', capture_output=True)
        log = proc.stdout + proc.stderr
        with (OUT / (suite + '.log')).open('x', encoding='utf-8') as stream: stream.write(log)
        match = re.search(r'Ran (\d+) tests?', log)
        tests.append({'suite': suite, 'count': int(match[1]) if match else 0, 'returncode': proc.returncode})
        print(tests[-1], flush=True)
    for name, expected in {**hashes, **protected}.items(): assert sha(ROOT / name) == expected, name
    for name in FILES:
        dest = OUT / 'code' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
    mismatches = [p for p in observed['pairs'] if not p['equal']]
    audit = {'production_eligible': False, 'model_calls': 0, 'tests': tests, 'baseline_mismatches': 18,
             'remaining_mismatches': len(mismatches), 'regressions': regressions, 'pair_count': len(observed['pairs']),
             'code_sha256': hashes, 'protected_files_sha256': protected, 'prior_notebook_cells': len(old['cells']),
             'original_scores_modified': False, 'production_files_changed': False,
             'failed_test_bundle': FAILED.relative_to(ROOT).as_posix(),
             'failed_test_reason': 'Three harness tests failed: broad alias fixture supplied pre-V7 normal-flow code, correctly declined by the V7-only adapter and thus executed old clone writers; identity fixture omitted its explicit minimal root template. Compose V7 first, require nonempty changes, preserve all parity assertions. Observer/adapter implementation unchanged.',
             'open_boundaries': ['full source observation/reflection/public-API coverage',
                                 'source-matched restricted error bridge', 'production emitter/validator/gate composition']}
    write(OUT / 'audit.json', audit)
    report = f'''## 2026-11-14：特殊值与订阅重收集 v9 离线实验

在冻结 V8 的18个不一致点之后，新增独立的观察器实验，不覆盖旧V4/V7/V8或验收页面。

- Date、冻结对象作为不可观察值保留原对象；稀疏数组保留孔洞并观察现有元素，不再把“不能观察”变成“拒绝赋值”。
- 观察依赖与当前对象形状分离：初始化收集，实际队列运行前重收集；旧别名在首次tick前仍能通知，重收集后不再误通知。不是简单丢弃已删属性。
- 原冻结24类场景／两个开发对象共 {len(observed['pairs'])} 个同步／tick比较点，不一致18→{len(mismatches)}，已一致点回退 {len(regressions)}。
- {sum(t['count'] for t in tests)} 项定向测试。矩阵范围通过不等于任意对象、访问器、Ref、Proxy、反射、异步应用错误处理全部等价，生产三项阻断和独立伪造通过检查仍保留。
- 0模型调用、未启动浏览器／服务器，未新增人工通过声明；原24/30、6失败、1,821,544 tokens不变。
- 初次98项中3条测试配置失败，代码与日志保留：扩大回归把旧normal-flow产物误交给V7-only适配器，适配器正确拒绝后，测试实际仍执行旧clone writer；另一个最小测试未设置根模板。现补齐V7组合与转换成功断言、最小根模板，所有原生身份／计算值／副作用等价断言原样保留；观察器和适配器实现未为此修改。

证据：`{OUT.relative_to(ROOT).as_posix()}`；输入与Notebook旧副本：`{BASE.relative_to(ROOT).as_posix()}`。
这是研究性通用修复，不是新的正式样本批次或生产版本。后续先扩大别名／原生子组件与未覆盖值域回归，再做受限错误桥和生产契约接入。
'''
    with (OUT / 'REPORT.md').open('x', encoding='utf-8') as stream: stream.write(report)
    seal(OUT); verify(OUT)
    if mismatches or regressions or not all(t['returncode'] == 0 for t in tests) or not forged['should_stop']:
        raise RuntimeError('Failed evidence preserved; Notebook not appended')
    check = f'''from pathlib import Path
import json,hashlib
root=next(p for p in [Path.cwd(),*Path.cwd().parents] if (p/'migration_pipeline').is_dir())
folder=root/'{OUT.relative_to(ROOT).as_posix()}'
base=root/'{BASE.relative_to(ROOT).as_posix()}'
for d in [folder,base,root/'{FAILED.relative_to(ROOT).as_posix()}']:
    for line in (d/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected,name=line.split('  ',1)
        assert hashlib.sha256((d/name).read_bytes()).hexdigest()==expected,name
a=json.loads((folder/'audit.json').read_text(encoding='utf-8'))
assert a['remaining_mismatches']==0 and a['regressions']==[] and not a['production_eligible']
assert all(t['returncode']==0 for t in a['tests']) and a['model_calls']==0
assert json.loads((folder/'forged_pass_gate.json').read_text(encoding='utf-8'))['should_stop']
old=json.loads((base/'notebook_before.ipynb').read_text(encoding='utf-8'))
nb=json.loads((root/'{NB.relative_to(ROOT).as_posix()}').read_text(encoding='utf-8'))
assert nb['cells'][:len(old['cells'])]==old['cells'] and nb['metadata']==old['metadata']
print({{'observed_dynamic_shape_pairs':a['pair_count'],'mismatches':0,'production':'blocked'}})
'''
    assert json.loads(NB.read_text(encoding='utf-8')) == old
    old['cells'].extend([
        {'cell_type': 'markdown', 'id': 'v9-shape-observer-20261114', 'metadata': {}, 'source': report.splitlines(keepends=True)},
        {'cell_type': 'code', 'id': 'v9-shape-observer-check-20261114', 'metadata': {}, 'execution_count': None,
         'outputs': [], 'source': check.splitlines(keepends=True)}])
    NB.write_text(json.dumps(old, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for cell in old['cells']:
        if cell['cell_type'] == 'code': compile(''.join(cell['source']), cell['id'], 'exec')
    exec(compile(check, 'shape-observer-readonly', 'exec'), {})
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-input', action='store_true'); parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.freeze_input == args.execute: parser.error('Choose exactly one action')
    freeze() if args.freeze_input else execute()
