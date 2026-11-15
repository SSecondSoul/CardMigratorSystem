"""Broaden V9 native input coverage without modifying frozen candidates."""
import argparse
import json
import re
import shutil
import subprocess

from migration_pipeline.audit_v7_source_queue_contract import ROOT, NB, sha, seal, verify, write
from migration_pipeline.audit_shape_observer_v9 import OUT as V9
from migration_pipeline.audit_v7_dynamic_shape import payload, node, RUNTIME as ORIGINAL_RUNTIME

BASE = ROOT / 'data/experiments/analysis/formal_30_v4_shape_input_expansion_input_20261114'
OUT = ROOT / 'data/experiments/analysis/formal_30_v4_shape_input_expansion_20261114'
RUNTIME = 'migration_pipeline/audit_shape_input_expansion_runtime.cjs'
FILES = [RUNTIME, 'migration_pipeline/audit_shape_input_expansion.py', 'tests/test_shape_input_expansion.py']


def freeze():
    verify(V9)
    prior = json.loads((V9 / 'audit.json').read_text(encoding='utf-8'))
    assert prior['remaining_mismatches'] == 0 and not prior['production_eligible']
    protected = {**prior['code_sha256'], **prior['protected_files_sha256']}
    for name, expected in protected.items(): assert sha(ROOT / name) == expected, name
    BASE.mkdir(exist_ok=False)
    for name in ['san', 'genericSan']:
        shutil.copy2(V9 / (name + '_shape_observer.san'), BASE / (name + '.san'))
    shutil.copy2(NB, BASE / 'notebook_before.ipynb')
    write(BASE / 'protected_files.json', protected)
    seal(BASE); verify(BASE)
    print('Frozen V9 candidates and pre-expansion Notebook/protected code.')


def inputs():
    verify(BASE)
    return {**payload(), **{name: (BASE / (name + '.san')).read_text(encoding='utf-8') for name in ['san', 'genericSan']}}


def execute():
    from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
    from migration_pipeline.utils.repair_scheduler import candidate_gate
    verify(BASE); verify(V9)
    old = json.loads((BASE / 'notebook_before.ipynb').read_text(encoding='utf-8'))
    assert json.loads(NB.read_text(encoding='utf-8')) == old, 'Notebook changed; do not overwrite'
    protected = json.loads((BASE / 'protected_files.json').read_text(encoding='utf-8'))
    hashes = {n: sha(ROOT / n) for n in FILES}
    for name, expected in protected.items(): assert sha(ROOT / name) == expected, name
    OUT.mkdir(exist_ok=False)
    data = inputs(); observed = node(ROOT / RUNTIME, data)
    write(OUT / 'observations.json', observed)
    diagnosis = source_parent_watch_semantics(data['san'], data['vue'])
    write(OUT / 'production_diagnostics.json', {k: v for k, v in diagnosis.items() if k != 'code'})
    state = {'generated_code': data['san'], 'vue_source': data['vue'], 'validation_errors': diagnosis['findings']}
    gate = candidate_gate(state, {**state, 'validation_errors': [], 'validation_passed': True})
    write(OUT / 'forged_pass_gate.json', gate)
    tests = []
    for suite in ['test_shape_input_expansion.py', 'test_shape_observer_v9.py', 'test_v7_integration_contract.py']:
        print('Testing ' + suite, flush=True)
        result = subprocess.run(['python', '-m', 'unittest', 'discover', '-s', 'tests', '-p', suite, '-v'],
                                cwd=ROOT, text=True, encoding='utf-8', capture_output=True)
        log = result.stdout + result.stderr
        with (OUT / (suite + '.log')).open('x', encoding='utf-8') as stream: stream.write(log)
        match = re.search(r'Ran (\d+) tests?', log)
        tests.append({'suite': suite, 'count': int(match[1]) if match else 0, 'returncode': result.returncode})
        print(tests[-1], flush=True)
    for name, expected in {**hashes, **protected}.items(): assert sha(ROOT / name) == expected, name
    for name in FILES:
        dest = OUT / 'code' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
    mismatches = [p for p in observed['pairs'] if not p['equal']]
    audit = {'production_eligible': False, 'model_calls': 0, 'candidate_code_changed': False,
             'scenario_count': len(observed['scenarios']), 'pair_count': len(observed['pairs']),
             'mismatch_pair_count': len(mismatches), 'mismatch_scenarios': sorted({p['scenario'] for p in mismatches}),
             'cleanup_comparison_count': len(observed['cleanup_pairs']),
             'cleanup_mismatch_count': sum(not p['equal'] for p in observed['cleanup_pairs']),
             'tests': tests, 'code_sha256': hashes, 'protected_files_sha256': protected,
             'prior_notebook_cells': len(old['cells']), 'original_scores_modified': False,
             'classification': 'remaining_risk_expanded_public_input_contract_not_new_sample_defect_rate'}
    write(OUT / 'audit.json', audit)
    write(OUT / 'coverage_obligations.json', observed['coverage_obligations'])
    report = f'''## 2026-11-14：V9 未覆盖输入扩展验证

本轮不修改V9候选、观察器、Prompt、验收页面或生产检查。沿用已冻结源码和运行时，通过两个开发对象的新增场景扩展覆盖。

- 新增 {len(observed['scenarios'])} 类场景，{len(observed['pairs'])} 个同步／tick比较点；其中 {len(mismatches)} 个不一致，涉及 {len(audit['mismatch_scenarios'])} 类场景。具体列表见 `audit.json` 与双方原始观察值。
- 另计 {audit['cleanup_comparison_count']} 个销毁错误对照，其中 {audit['cleanup_mismatch_count']} 个不一致：循环值导致销毁时JSON序列化失败，Vue经beforeDestroy错误通道报告，San直接dispose异常。没有因动作阶段一致就丢弃清理阶段差异；这是原异步watcher错误桥不覆盖生命周期错误的边界，不计入80个动作比较点。
- 上一轮116点矩阵一致仍成立，但不能据此宣称任意输入已等价。本轮反例作为 `remaining_risk` 保留，不回填为新正式测试样本缺陷率。
- 访问器、属性描述符、符号属性／特殊元数据、原型和外部路径更新的覆盖义务逐项存入 `coverage_obligations.json`，不因输入类型守卫拒绝就记作修复通过。
- 外部路径场景明确比较“Vue原生根／属性赋值”与对应San Data.set（无选项）的映射；不把San特有force/silent接口擅自认作原生Vue接口。未覆盖选项继续不作等价声明。
- 测试设备只增加root/path更新绑定和场景集合，组件业务源码未改；原设备指纹与对照复算见 `harness`。仍是有限DOM、最小根渲染、桩存储／定时器，不是完整浏览器验收。
- {sum(t['count'] for t in tests)} 项定向测试。测试通过表示反例稳定重现／控制场景保持，不表示这些不一致已修复。
- 三项生产阻断和独立候选门保留；0模型调用，无服务器／浏览器启动，原批24/30、6失败、1,821,544 tokens不变。

证据：`{OUT.relative_to(ROOT).as_posix()}`。Notebook仅追加，原有 {len(old['cells'])} 单元保留。
在这些公开输入边界尚未闭合前，不直接把V9作为生产修复放行；下一步依据冻结反例修正规则／明确输入契约，再推进受限错误桥与生产契约组合。
'''
    with (OUT / 'REPORT.md').open('x', encoding='utf-8') as stream: stream.write(report)
    seal(OUT); verify(OUT)
    if not all(t['returncode'] == 0 for t in tests) or not gate['should_stop']:
        raise RuntimeError('Failed audit preserved; Notebook not appended')
    check = f'''from pathlib import Path
import json,hashlib
root=next(p for p in [Path.cwd(),*Path.cwd().parents] if (p/'migration_pipeline').is_dir())
folder=root/'{OUT.relative_to(ROOT).as_posix()}'
base=root/'{BASE.relative_to(ROOT).as_posix()}'
for d in [folder,base]:
    for line in (d/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected,name=line.split('  ',1)
        assert hashlib.sha256((d/name).read_bytes()).hexdigest()==expected,name
a=json.loads((folder/'audit.json').read_text(encoding='utf-8'))
o=json.loads((folder/'observations.json').read_text(encoding='utf-8'))
assert not a['production_eligible'] and a['model_calls']==0 and not a['candidate_code_changed']
assert all(t['returncode']==0 for t in a['tests'])
assert len(o['pairs'])==a['pair_count'] and sum(not p['equal'] for p in o['pairs'])==a['mismatch_pair_count']
assert sum(not p['equal'] for p in o['cleanup_pairs'])==a['cleanup_mismatch_count']
assert o['host_prototype_clean'] and o['rejection_listener_restored']
assert json.loads((folder/'forged_pass_gate.json').read_text(encoding='utf-8'))['should_stop']
old=json.loads((base/'notebook_before.ipynb').read_text(encoding='utf-8'))
nb=json.loads((root/'{NB.relative_to(ROOT).as_posix()}').read_text(encoding='utf-8'))
assert nb['cells'][:len(old['cells'])]==old['cells'] and nb['metadata']==old['metadata']
print({{'expanded_pairs':a['pair_count'],'counterexamples':a['mismatch_pair_count'],'production':'blocked'}})
'''
    assert json.loads(NB.read_text(encoding='utf-8')) == old
    old['cells'].extend([
        {'cell_type': 'markdown', 'id': 'v9-input-expansion-20261114', 'metadata': {}, 'source': report.splitlines(keepends=True)},
        {'cell_type': 'code', 'id': 'v9-input-expansion-check-20261114', 'metadata': {}, 'execution_count': None,
         'outputs': [], 'source': check.splitlines(keepends=True)}])
    NB.write_text(json.dumps(old, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for cell in old['cells']:
        if cell['cell_type'] == 'code': compile(''.join(cell['source']), cell['id'], 'exec')
    exec(compile(check, 'input-expansion-readonly', 'exec'), {})
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-input', action='store_true'); parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.freeze_input == args.execute: parser.error('Choose one action')
    freeze() if args.freeze_input else execute()
