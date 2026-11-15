"""Source-native writer experiment against frozen V7 dynamic-shape negatives."""
import argparse
import json
import re
import shutil
import subprocess

from migration_pipeline.audit_v7_dynamic_shape import ROOT, BASE, OUT as NEGATIVE, payload, node, RUNTIME
from migration_pipeline.audit_v7_source_queue_contract import NB, sha, seal, verify, write

FAILED = ROOT / 'data/experiments/analysis/formal_30_v4_source_property_assignment_v8_20261114'
OUT = ROOT / 'data/experiments/analysis/formal_30_v4_source_property_assignment_v8_retry_20261114'
ADAPTER = 'migration_pipeline/probe_source_property_assignment_v8.cjs'
FILES = [ADAPTER, 'migration_pipeline/audit_source_property_assignment_v8.py', 'tests/test_source_property_assignment_v8.py']
SUITES = ['test_source_property_assignment_v8.py', 'test_v7_dynamic_shape.py', 'test_v7_source_queue_contract.py']


def candidates(data):
    return {name: node(ROOT / ADAPTER, {'code': data[name], 'vue': data['vue' if name == 'san' else 'genericVue'],
                                      'experimental': True}) for name in ['san', 'genericSan']}


def execute():
    from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
    from migration_pipeline.utils.repair_scheduler import candidate_gate
    verify(BASE); verify(NEGATIVE); verify(FAILED)
    hashes = {name: sha(ROOT / name) for name in [*FILES, RUNTIME]}
    old = json.loads(NB.read_text(encoding='utf-8'))
    data = payload(); adapted = candidates(data)
    assert all(row['changes'] and not row['production_eligible'] for row in adapted.values())
    OUT.mkdir(exist_ok=False)
    shutil.copy2(NB, OUT / 'notebook_before.ipynb')
    for name, row in adapted.items():
        with (OUT / (name + '_source_assignment.san')).open('x', encoding='utf-8') as stream: stream.write(row['code'])
    write(OUT / 'adaptation.json', {name: {k: v for k, v in row.items() if k != 'code'} for name, row in adapted.items()})
    observed = node(ROOT / RUNTIME, {**data, **{n: r['code'] for n, r in adapted.items()}})
    # The reused oracle calls its candidate slot san_v7. Relabel only serialized
    # variant identifiers (no behavior/frames are transformed) for clear lineage.
    for run in observed['runs']:
        if run['variant'] == 'san_v7': run['variant'] = 'san_v8_source_assignment'
    observed['candidate_provenance'] = {'adapter': ADAPTER, 'base': BASE.relative_to(ROOT).as_posix(), 'experimental': True}
    write(OUT / 'observations.json', observed)
    baseline = json.loads((NEGATIVE / 'observations.json').read_text(encoding='utf-8'))
    regressions = [p for p, before in zip(observed['pairs'], baseline['pairs']) if before['equal'] and not p['equal']]
    assert len(observed['pairs']) == len(baseline['pairs'])
    diagnostics = source_parent_watch_semantics(adapted['san']['code'], data['vue'])
    write(OUT / 'diagnostics.json', {k: v for k, v in diagnostics.items() if k != 'code'})
    state = {'generated_code': data['san'], 'vue_source': data['vue'],
             'validation_errors': source_parent_watch_semantics(data['san'], data['vue'])['findings']}
    forged = candidate_gate(state, {**state, 'generated_code': adapted['san']['code'], 'validation_errors': [], 'validation_passed': True})
    write(OUT / 'forged_pass_gate.json', forged)
    tests = []
    for suite in SUITES:
        print('Testing ' + suite, flush=True)
        run = subprocess.run(['python', '-m', 'unittest', 'discover', '-s', 'tests', '-p', suite, '-v'],
                              cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        log = run.stdout + run.stderr
        with (OUT / (suite + '.log')).open('x', encoding='utf-8') as stream: stream.write(log)
        match = re.search(r'Ran (\d+) tests?', log)
        tests.append({'suite': suite, 'count': int(match[1]) if match else 0, 'returncode': run.returncode})
        print(tests[-1], flush=True)
    assert hashes == {name: sha(ROOT / name) for name in hashes}, 'Code drift during experiment'
    for name in hashes:
        target = OUT / 'code' / name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, target)
    mismatches = [p for p in observed['pairs'] if not p['equal']]
    audit = {'production_eligible': False, 'model_calls': 0, 'tests': tests,
             'baseline_mismatches': sum(not p['equal'] for p in baseline['pairs']), 'remaining_mismatches': len(mismatches),
             'remaining_scenarios': sorted({p['scenario'] for p in mismatches}), 'regressions': regressions,
             'pair_count': len(observed['pairs']), 'code_sha256': hashes, 'production_files_changed': False,
             'original_scores_modified': False, 'prior_notebook_cells': len(old['cells']),
             'failed_test_bundle': FAILED.relative_to(ROOT).as_posix(),
             'failed_test_reason': 'One unit test incorrectly assumed ToPropertyKey preceded RHS coercion. The unchanged native source expression is now executed as the oracle; source and candidate both produce rhs then key. Adapter implementation unchanged.',
             'open_obligations': ['DYNVALUE-02 observed-value acceptance', 'DYNSUB-03 subscription recollection', 'restricted error bridge and production composition matching']}
    write(OUT / 'audit.json', audit)
    report = f'''## 2026-11-14：源原生属性赋值 v8 实验修复（未生产放行）

在已冻结 V7 反例之后，新增通用、显式 opt-in 的源码匹配修复；仅接受完整匹配的 V7 composition，不按组件名硬编码，不修改生产 emitter／Prompt／验证器。

- 从 Vue 源码提取整个赋值表达式，将 `this.settings[key]` 接收对象映射为 `this.data.get("settings")[key]`，保留键转换、RHS顺序和通知尾部；显式保留ES module严格模式。不是简单删除诊断或缩小key接口。
- TaskManager 和重命名通用 fixture 共 {len(observed['pairs'])} 个比较点：不一致从 {audit['baseline_mismatches']} 降到 {len(mismatches)}；已一致控制点回退 {len(regressions)}。
- 剩余场景：{', '.join(audit['remaining_scenarios'])}。这是部分通用修复，**动态键／属性形状闭环仍未完成**，不宣称任意输入或反射等价。
- {sum(t['count'] for t in tests)} 项定向测试，包含新修复、冻结V7反例及V7结构匹配；反例测试通过仅表示稳定重现，不表示所有缺口已修复。
- 受限值观察器和flush后旧订阅仍需修改；当前生产三项阻断、独立候选门保留。0模型请求，原始24/30、6失败及token统计不变。
- 未改旧V7观察器、冻结候选、验收配置、组件或原有批次结果。新产物仅供离线实验，不切换人工页，不要求用户复跑。
- 首次75项测试中1条顺序断言失败：测试错误假定键转换先于RHS转换。已保留原代码／日志，修正为执行原生源赋值作对照；双方都得到 rhs→key，适配器实现未因此修改。没有削弱严格模式、源表达式匹配或未关闭阻断。

证据：`{OUT.relative_to(ROOT).as_posix()}`；原反例：`{NEGATIVE.relative_to(ROOT).as_posix()}`。
下一步针对已冻结的值接受与订阅时机反例改进观察器，再做受限错误桥和生产集成。
'''
    with (OUT / 'REPORT.md').open('x', encoding='utf-8') as stream: stream.write(report)
    seal(OUT); verify(OUT)
    if regressions or not all(t['returncode'] == 0 for t in tests) or not forged['should_stop']:
        raise RuntimeError('Failed experiment preserved; Notebook not appended')
    check = f'''from pathlib import Path
import json, hashlib
root=next(p for p in [Path.cwd(), *Path.cwd().parents] if (p/'migration_pipeline').is_dir())
folder=root/'{OUT.relative_to(ROOT).as_posix()}'
for directory in [folder,root/'{FAILED.relative_to(ROOT).as_posix()}']:
    for line in (directory/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected,name=line.split('  ',1)
        assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected,name
a=json.loads((folder/'audit.json').read_text(encoding='utf-8'))
assert not a['production_eligible'] and a['model_calls']==0 and a['regressions']==[]
assert a['remaining_mismatches']<a['baseline_mismatches'] and a['remaining_mismatches']>0
assert all(t['returncode']==0 for t in a['tests'])
assert json.loads((folder/'forged_pass_gate.json').read_text(encoding='utf-8'))['should_stop']
nb=json.loads((root/'{NB.relative_to(ROOT).as_posix()}').read_text(encoding='utf-8'))
old=json.loads((folder/'notebook_before.ipynb').read_text(encoding='utf-8'))
assert nb['cells'][:len(old['cells'])]==old['cells'] and nb['metadata']==old['metadata']
print({{'native_assignment':'partial experimental improvement','production':'blocked','mismatches':a['remaining_mismatches']}})
'''
    assert json.loads(NB.read_text(encoding='utf-8')) == old, 'Notebook changed; do not overwrite'
    old['cells'].extend([
        {'cell_type': 'markdown', 'id': 'v8-source-assignment-20261114', 'metadata': {}, 'source': report.splitlines(keepends=True)},
        {'cell_type': 'code', 'id': 'v8-source-assignment-check-20261114', 'metadata': {}, 'execution_count': None,
         'outputs': [], 'source': check.splitlines(keepends=True)}])
    NB.write_text(json.dumps(old, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for cell in old['cells']:
        if cell['cell_type'] == 'code': compile(''.join(cell['source']), cell['id'], 'exec')
    exec(compile(check, 'source-assignment-check', 'exec'), {})
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--execute', action='store_true')
    if not parser.parse_args().execute: parser.error('Use --execute for the local experiment (no model)')
    execute()
