"""Freeze and replay the V7 queue/lifecycle inspection, never production admission."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/experiments/analysis/formal_30_v4_v7_queue_contract_input_20261114'
FAILED_REPLAY = ROOT / 'data/experiments/analysis/formal_30_v4_v7_queue_contract_v1_20261114'
COMPATIBILITY = ROOT / 'data/experiments/analysis/formal_30_v4_v7_queue_compatibility_input_20261114'
OUT = ROOT / 'data/experiments/analysis/formal_30_v4_v7_queue_contract_v1_retry_20261114'
NB = ROOT / 'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
PRIOR = ROOT / 'data/experiments/analysis/formal_30_v4_v7_limited_integration_preflight_retry_20261114'
MATCHER = 'migration_pipeline/utils/source_parent_watch_semantics.cjs'
CODE = [MATCHER, 'migration_pipeline/utils/v7_source_queue_contract.cjs',
        'migration_pipeline/utils/v7_source_queue_contract.py',
        'migration_pipeline/audit_v7_source_queue_contract.py', 'tests/test_v7_source_queue_contract.py',
        'tests/test_source_parent_watch_closure.py',
        'migration_pipeline/utils/source_parent_watch_semantics.py',
        'migration_pipeline/utils/source_render_call_semantics.cjs',
        'migration_pipeline/utils/inline_identifier_recovery.cjs',
        'migration_pipeline/probe_async_watcher_scope_v7.cjs',
        'migration_pipeline/probe_source_error_context_v6.cjs',
        'migration_pipeline/probe_parent_alias_observer_v4.cjs',
        'migration_pipeline/stages/validate.py', 'migration_pipeline/stages/repair.py',
        'migration_pipeline/utils/repair_scheduler.py', 'migration_pipeline/utils/repair_prompt.py']
SUITES = ['test_v7_source_queue_contract.py', 'test_source_parent_watch_closure.py',
          'test_async_watcher_scope_v7.py', 'test_parent_watch_scope_guard.py',
          'test_v7_integration_contract.py', 'test_class_binding_closure_v1.py']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2); stream.write('\n')


def seal(folder):
    files = sorted(p for p in folder.rglob('*') if p.is_file())
    with (folder / 'SHA256SUMS.txt').open('x', encoding='utf-8') as stream:
        stream.write(''.join(sha(p) + '  ' + p.relative_to(folder).as_posix() + '\n' for p in files))


def verify(folder):
    for line in (folder / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected, name = line.split('  ', 1)
        path = (folder / name).resolve()
        assert path.is_relative_to(folder.resolve()) and sha(path) == expected, name


def freeze_input():
    from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
    verify(PRIOR)
    acceptance = json.loads((PRIOR / 'manual_acceptance.json').read_text(encoding='utf-8'))
    assets = acceptance['assets']
    paths = {f: ROOT / assets[f]['component']['path'] for f in ['vue', 'san']}
    for f, path in paths.items():
        assert sha(path) == assets[f]['component']['sha256']
    BASE.mkdir(parents=True, exist_ok=False)
    for f, path in paths.items(): shutil.copy2(path, BASE / ('input.' + f))
    shutil.copy2(ROOT / MATCHER, BASE / 'source_parent_watch_semantics_before.cjs')
    shutil.copy2(NB, BASE / 'notebook_before.ipynb')
    baseline = source_parent_watch_semantics(paths['san'].read_text(encoding='utf-8'), paths['vue'].read_text(encoding='utf-8'))
    write(BASE / 'baseline.json', {k: v for k, v in baseline.items() if k != 'code'})
    write(BASE / 'inputs.json', {f: {'path': str(p.relative_to(ROOT).as_posix()), 'sha256': sha(p)} for f, p in paths.items()})
    seal(BASE); verify(BASE)
    print('Frozen queue-contract input; no production edits or model calls.')


def replay():
    from migration_pipeline.utils.v7_source_queue_contract import inspect_v7_source_queue
    from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
    from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
    from migration_pipeline.utils.repair_scheduler import candidate_gate
    verify(BASE)
    failed = ROOT / 'data/experiments/analysis/formal_30_v4_v7_queue_test_fixture_failed_20261114'
    verify(failed)
    verify(FAILED_REPLAY); verify(COMPATIBILITY)
    fingerprints = {name: sha(ROOT / name) for name in CODE}
    code = (BASE / 'input.san').read_text(encoding='utf-8'); vue = (BASE / 'input.vue').read_text(encoding='utf-8')
    original = json.loads((BASE / 'notebook_before.ipynb').read_text(encoding='utf-8'))
    assert json.loads(NB.read_text(encoding='utf-8')) == original, 'Notebook changed; do not overwrite'
    OUT.mkdir(parents=True, exist_ok=False)
    inspected = inspect_v7_source_queue(code, vue)
    production = source_parent_watch_semantics(code, vue)
    baseline = json.loads((BASE / 'baseline.json').read_text(encoding='utf-8'))
    assert {k: v for k, v in production.items() if k != 'code'} == baseline
    validation = ValidateStage().run(ValidateStageInput(generated_code=code, vue_file_path=str(BASE / 'input.vue'))).to_state_update()
    before = {'generated_code': code, 'vue_source': vue, **validation}
    gate = candidate_gate(before, {**before, 'validation_passed': True, 'validation_errors': []})
    write(OUT / 'inspection.json', inspected)
    write(OUT / 'validation.json', validation)
    write(OUT / 'forged_pass_gate.json', gate)
    tests = []
    for suite in SUITES:
        print('Testing ' + suite, flush=True)
        proc = subprocess.run(['python', '-m', 'unittest', 'discover', '-s', 'tests', '-p', suite, '-v'],
                              cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        log = proc.stdout + proc.stderr
        with (OUT / (suite + '.log')).open('x', encoding='utf-8') as stream: stream.write(log)
        count = re.search(r'Ran (\d+) tests?', log)
        tests.append({'suite': suite, 'count': int(count[1]) if count else 0, 'returncode': proc.returncode})
        print(tests[-1], flush=True)
    write(OUT / 'tests.json', tests)
    hashes = {}
    for name in CODE:
        target = OUT / 'code' / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target); hashes[name] = sha(ROOT / name)
    assert hashes == fingerprints, 'Code changed during inspection/tests'
    passed = inspected['queue_lifecycle_structure_matched'] and all(t['returncode'] == 0 for t in tests)
    passed = passed and not validation['validation_passed'] and gate['should_stop']
    audit = {'passed': passed, 'production_eligible': False, 'model_calls': 0,
             'original_scores_modified': False, 'input_bundle': BASE.relative_to(ROOT).as_posix(),
             'code_sha256': hashes, 'tests': tests, 'prior_notebook_cells': len(original['cells']),
             'failed_fixture_bundle': failed.relative_to(ROOT).as_posix(),
             'failed_fixture_reason': 'Four mutation tests used non-matching whitespace in search strings; assert-mutation checks caught this. Fixed fixtures, not production gates.',
             'failed_replay_bundle': FAILED_REPLAY.relative_to(ROOT).as_posix(),
             'compatibility_input_bundle': COMPATIBILITY.relative_to(ROOT).as_posix(),
             'failed_replay_reason': 'One legacy test omitted newly detected class findings and expected zero normalization. Retain watcher blockers; assert only source-proven class change and byte-identical script/style.',
             'production_diagnostics_unchanged': True}
    write(OUT / 'audit.json', audit)
    report = f'''# V7 队列／生命周期源码结构匹配 — 2026-11-14

本次完成一个独立、只读的结构检查器，不接入生产放行。冻结输入来自已人工通过的候选。

- 完整比较源码派生的 handler 数组、声明顺序、去重／排序／最新读取、私有异步入口、finally 重置和销毁包装；不凭 marker 存在放行。
- 比较 source data、mounted／beforeDestroy 和传递方法图；精确核对实验工厂及其引用，未知包装／额外工作拒绝。
- 动态 writer 仅核对源赋值参数及尾部结构，观察器属性形状／别名语义仍未证明；错误桥只核对工厂结构，不证明应用回调纯度或祖先配置。
- 测试 {sum(t['count'] for t in tests)} 项；通过状态：{passed}。这是定向测试，不是全量／独立评估。
- 原生产 matcher 输出完全不变，完整 ValidateStage 仍阻断三项，伪造通过被独立门拒绝。未修改 Prompt／生产调度、组件或验收页。
- 旧 matcher 文件仅增加只读检查原语导出，run() 的接受条件、诊断和修复逻辑未改。初次测试有4个篡改 fixture 因空格不匹配未真正改变输入而失败，原代码／日志已单独冻结；修正 fixture 后重新验证，没有放宽检查。
- 首次扩大回放89项中1条旧测试失败：class闭环加入后，历史产物新增两条合法class诊断；旧断言仍假设仅有watcher问题且不允许独立class修复。原测试单独保留，本次更新为精确校验class诊断、唯一class修复及script/style字节不变，watcher阻断仍保持。失败回放目录未覆盖。
- 0 模型调用，未启动浏览器／服务器；原批24/30、6失败、1,821,544 tokens 不变。

这只证明受限模板的结构对应，不证明任意 JS 上下文、运行时全局猴子补丁或整个应用语义等价。
下一步是动态键／属性形状闭环及受限错误桥接；完成后才考虑生产集成与付费复跑。
'''
    with (OUT / 'REPORT.md').open('x', encoding='utf-8') as stream: stream.write(report)
    seal(OUT); verify(OUT)
    if not passed: raise RuntimeError('Failed evidence preserved; Notebook not appended')
    check = f'''from pathlib import Path
import hashlib, json
root = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'migration_pipeline').is_dir())
folder = root / '{OUT.relative_to(ROOT).as_posix()}'
for directory in [folder, root / '{BASE.relative_to(ROOT).as_posix()}', root / '{failed.relative_to(ROOT).as_posix()}', root / '{FAILED_REPLAY.relative_to(ROOT).as_posix()}', root / '{COMPATIBILITY.relative_to(ROOT).as_posix()}']:
    for line in (directory / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected, name = line.split('  ', 1)
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == expected, name
audit = json.loads((folder / 'audit.json').read_text(encoding='utf-8'))
assert audit['passed'] and not audit['production_eligible'] and audit['model_calls'] == 0
assert all(t['returncode'] == 0 for t in audit['tests'])
result = json.loads((folder / 'inspection.json').read_text(encoding='utf-8'))
assert result['queue_lifecycle_structure_matched'] and not result['source_equivalence_proven']
assert len(result['remaining_production_codes']) == 3
assert not json.loads((folder / 'validation.json').read_text(encoding='utf-8'))['validation_passed']
assert json.loads((folder / 'forged_pass_gate.json').read_text(encoding='utf-8'))['should_stop']
old = json.loads((root / audit['input_bundle'] / 'notebook_before.ipynb').read_text(encoding='utf-8'))
nb = json.loads((root / '{NB.relative_to(ROOT).as_posix()}').read_text(encoding='utf-8'))
assert nb['cells'][:len(old['cells'])] == old['cells'] and nb['metadata'] == old['metadata']
print({{'queue_structure': 'matched', 'production': 'blocked', 'tests': sum(t['count'] for t in audit['tests'])}})
'''
    assert json.loads(NB.read_text(encoding='utf-8')) == original
    original['cells'].extend([
        {'cell_type': 'markdown', 'id': 'v7-queue-contract-20261114', 'metadata': {}, 'source': report.splitlines(keepends=True)},
        {'cell_type': 'code', 'id': 'v7-queue-contract-check-20261114', 'metadata': {}, 'outputs': [],
         'execution_count': None, 'source': check.splitlines(keepends=True)}])
    NB.write_text(json.dumps(original, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    actual = json.loads(NB.read_text(encoding='utf-8'))
    assert len({c['id'] for c in actual['cells']}) == len(actual['cells'])
    for cell in actual['cells']:
        if cell['cell_type'] == 'code': compile(''.join(cell['source']), cell['id'], 'exec')
    exec(compile(check, 'v7-queue-contract-readonly', 'exec'), {})
    print('Appended Notebook; original prefix and metadata preserved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-input', action='store_true'); parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    if args.freeze_input == args.replay: parser.error('Choose one action')
    freeze_input() if args.freeze_input else replay()
