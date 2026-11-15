"""Native V7 dynamic-key/shape counterexample audit; no production waiver."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import re

from migration_pipeline.audit_v7_source_queue_contract import ROOT, NB, sha, seal, verify, write

BASE = ROOT / 'data/experiments/analysis/formal_30_v4_v7_dynamic_shape_input_20261114'
OUT = ROOT / 'data/experiments/analysis/formal_30_v4_v7_dynamic_shape_audit_20261114'
QUEUE = ROOT / 'data/experiments/analysis/formal_30_v4_v7_queue_contract_v1_retry_20261114'
PRIOR = ROOT / 'data/experiments/analysis/formal_30_v4_parent_alias_child_audit_v1_20261112'
RUNTIME = 'migration_pipeline/audit_v7_dynamic_shape_runtime.cjs'
FILES = [RUNTIME, 'migration_pipeline/audit_v7_dynamic_shape.py', 'tests/test_v7_dynamic_shape.py',
         'migration_pipeline/probe_parent_alias_observer_v4.cjs',
         'migration_pipeline/probe_async_watcher_scope_v7.cjs',
         'migration_pipeline/probe_source_error_context_v6.cjs',
         'migration_pipeline/audit_parent_alias_child_runtime.cjs']
HARNESS_EVIDENCE = [ROOT / 'data/experiments/analysis/formal_30_v4_v7_dynamic_shape_first_observation_20261114',
                    ROOT / 'data/experiments/analysis/formal_30_v4_v7_dynamic_shape_encoder_control_failed_20261114']


def node(path, payload):
    run = subprocess.run(['node', str(path)], input=json.dumps(payload), text=True,
                         encoding='utf-8', capture_output=True, cwd=ROOT, timeout=120)
    if run.returncode or run.stderr.strip(): raise RuntimeError(run.stderr or str(run.returncode))
    return json.loads(run.stdout)


def freeze():
    verify(QUEUE)
    earlier = json.loads((QUEUE / 'audit.json').read_text(encoding='utf-8'))
    for path, expected in earlier['code_sha256'].items(): assert sha(ROOT / path) == expected, path
    BASE.mkdir(exist_ok=False)
    assets = {
        'task.vue': ROOT / 'data/experiments/analysis/formal_30_v4_v7_queue_contract_input_20261114/input.vue',
        'task.san': ROOT / 'data/experiments/analysis/formal_30_v4_v7_queue_contract_input_20261114/input.san',
        'vue.js': ROOT / 'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js',
        'san.js': ROOT / 'node_modules/san/dist/san.dev.js',
        'observer_before.cjs': ROOT / 'migration_pipeline/probe_parent_alias_observer_v4.cjs',
    }
    for name, path in assets.items(): shutil.copy2(path, BASE / name)
    old = json.loads((PRIOR / 'audit.json').read_text(encoding='utf-8'))['fixture']
    candidate = node(ROOT / 'migration_pipeline/probe_async_watcher_scope_adapter_v7.cjs',
                     {'code': old['normal'], 'vue': old['vue'], 'experimental': True,
                      'error_context_policy': 'private-async-parent-watch-source-context'})
    assert candidate['changes'] and not candidate['production_eligible']
    with (BASE / 'generic.vue').open('x', encoding='utf-8') as stream: stream.write(old['vue'])
    with (BASE / 'generic.san').open('x', encoding='utf-8') as stream: stream.write(candidate['code'])
    shutil.copy2(NB, BASE / 'notebook_before.ipynb')
    write(BASE / 'provenance.json', {'source_assets': {n: {'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)} for n, p in assets.items()},
          'generic_source_bundle': PRIOR.relative_to(ROOT).as_posix(),
          'generic_adaptation_changes': candidate['changes'], 'production_eligible': False, 'model_calls': 0,
          'scope': 'native browser-detected runtimes on limited DOM; minimal root render, stubbed storage/timers; not full UI acceptance'})
    seal(BASE); verify(BASE)
    print('Frozen dynamic-key inputs, runtimes, observer and prior Notebook.')


def payload():
    verify(BASE)
    return {name: (BASE / file).read_text(encoding='utf-8') for name, file in [
        ('vueRuntime', 'vue.js'), ('sanRuntime', 'san.js'), ('vue', 'task.vue'), ('san', 'task.san'),
        ('genericVue', 'generic.vue'), ('genericSan', 'generic.san')]}


def replay():
    from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
    from migration_pipeline.utils.repair_scheduler import candidate_gate
    old = json.loads((BASE / 'notebook_before.ipynb').read_text(encoding='utf-8'))
    for folder in HARNESS_EVIDENCE: verify(folder)
    provenance = json.loads((BASE / 'provenance.json').read_text(encoding='utf-8'))
    for entry in provenance['source_assets'].values(): assert sha(ROOT / entry['path']) == entry['sha256']
    assert json.loads(NB.read_text(encoding='utf-8')) == old, 'Notebook changed, do not overwrite'
    hashes = {n: sha(ROOT / n) for n in FILES}
    OUT.mkdir(exist_ok=False)
    data = payload(); observed = node(ROOT / RUNTIME, data)
    write(OUT / 'observations.json', observed)
    diagnostics = source_parent_watch_semantics(data['san'], data['vue'])
    before = {'generated_code': data['san'], 'vue_source': data['vue'], 'validation_errors': diagnostics['findings']}
    forged = candidate_gate(before, {**before, 'validation_errors': [], 'validation_passed': True})
    write(OUT / 'production_diagnostics.json', {k: v for k, v in diagnostics.items() if k != 'code'})
    write(OUT / 'forged_pass_gate.json', forged)
    suites = ['test_v7_dynamic_shape.py', 'test_v7_source_queue_contract.py',
              'test_v7_integration_contract.py', 'test_parent_alias_observer_v4.py']
    tests = []
    for suite in suites:
        print('Testing ' + suite, flush=True)
        proc = subprocess.run(['python', '-m', 'unittest', 'discover', '-s', 'tests', '-p', suite, '-v'],
                              capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
        log = proc.stdout + proc.stderr
        with (OUT / (suite + '.log')).open('x', encoding='utf-8') as stream: stream.write(log)
        match = re.search(r'Ran (\d+) tests?', log)
        tests.append({'suite': suite, 'count': int(match[1]) if match else 0, 'returncode': proc.returncode})
        print(tests[-1], flush=True)
    assert hashes == {n: sha(ROOT / n) for n in FILES}, 'Code changed during audit'
    for name in FILES:
        target = OUT / 'code' / name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, target)
    mismatches = [p for p in observed['pairs'] if not p['equal']]
    scenarios = sorted({p['scenario'] for p in mismatches})
    audit = {'test_results': tests, 'source_assets_unchanged': True, 'code_sha256': hashes,
             'scenario_count': len(observed['scenarios']), 'subject_count': 2, 'pair_count': len(observed['pairs']),
             'mismatch_pair_count': len(mismatches), 'mismatch_scenarios': scenarios,
             'production_eligible': False, 'model_calls': 0, 'original_scores_modified': False,
             'prior_notebook_cells': len(old['cells']), 'scope': observed['scope'],
             'harness_evidence': [p.relative_to(ROOT).as_posix() for p in HARNESS_EVIDENCE],
             'runtime_prototype_pollution': not observed['host_prototype_clean'],
             'classification': 'remaining_risk_experimental_adapter_counterexamples_not_new_sample_defect_rate'}
    write(OUT / 'audit.json', audit)
    write(OUT / 'repair_obligations.json', [
        {'id': 'DYNKEY-01', 'category': 'remaining_risk', 'phase': 'experimental_observer',
         'root_cause': 'write() rejects non-string keys before native ToPropertyKey conversion; source raw property assignment accepts/coerces them and preserves coercion throws.',
         'scenarios': ['numeric_key', 'symbol_key', 'coerced_existing_key', 'coerced_new_key', 'throwing_key_coercion'],
         'source_reference': 'input.vue updateSettings: raw this.settings[key] assignment; ECMAScript evaluation order must remain intact.',
         'repair_requirement': 'Preserve native source LHS/RHS conversion, assignment and synchronous notification order; no UI-key whitelist or silent catch.', 'status': 'unresolved'},
        {'id': 'DYNVALUE-02', 'category': 'remaining_risk', 'phase': 'experimental_observer',
         'root_cause': 'requireValue/allowed rejects Date, frozen values, sparse arrays and Symbols that the source assignment accepts; Vue observe can skip unsupported observation without rejecting assignment.',
         'scenarios': ['date_value', 'frozen_value', 'sparse_array_value', 'new_symbol_value'],
         'source_reference': 'vue.js observe/defineReactive; source does not declare the adapter value guard.',
         'repair_requirement': 'Separate native assignment acceptance from observer eligibility. Do not clone/coerce/drop values to satisfy observer constraints.', 'status': 'unresolved'},
        {'id': 'DYNSUB-03', 'category': 'remaining_risk', 'phase': 'experimental_observer',
         'root_cause': 'children()/ancestors() follows stale meta.values after raw deletion, descriptor replacement or enumerability change. Unlike Vue watcher traverse/cleanupDeps, subscriptions are not recollected after a flush.',
         'scenarios': ['delete_then_mutate_detached_alias', 'redefine_then_mutate_detached_alias', 'nonenumerable_then_mutate_alias'],
         'source_reference': 'vue.js _traverse uses current Object.keys; Watcher.get finally cleanupDeps removes stale subscriptions.',
         'repair_requirement': 'Match subscription timing as well as current shape. Preserve first-tick pending notification and remove obsolete dependencies after recollection; simply skipping deleted children would lose the first valid notification.', 'status': 'unresolved'}])
    report = f'''## 2026-11-14：V7 动态键／属性形状的原生反例审计

本步先验证观察器是否真的等价，未改生产规则、Prompt、组件或验收配置，也未放行。

- 两个开发对象：冻结 TaskManager（24场景）和通用 assign fixture（23场景；没有 TaskManager 特有的 syncInterval 分支），合计 {len(observed['pairs'])} 个同步／tick 比较点。不是新增独立样本或人工验收。
- 当前 V7 实验适配器出现 {len(mismatches)} 个不一致比较点，涉及 {len(scenarios)} 种场景：{', '.join(scenarios)}。
- 比较键转换／赋值结果、可枚举属性形状、原型、旧对象别名、watcher 及业务副作用、异常类别和下一 tick；保留双方原始消息。框架内部元数据及所有反射等价不在通过声明内。
- Vue 使用冻结 2.7.16 原生观察器；San 使用 3.15.6 和冻结 V7。限于有限 DOM、最小根渲染、桩存储／定时器，不是完整浏览器视觉复核。源码 ES module 以严格模式执行，San CommonJS 保持产物原模式。
- Vue 完整构建启动时有两个换行属性序列化探测，测试 DOM 仅支持这两个确切字符串；不模拟通用HTML解析。初次启动失败代码和日志保留。首次编码器把Vue增强数组原型与标准数组原型算作业务状态差异，导致普通控制场景误报；原观察值保留，当前显式排除数组原型／内部元数据的反射等价声明，双方原始own names与数组反射事实另存，根对象原型仍比较。
- 三条待修复义务在 `repair_obligations.json`：属性键转换、赋值输入类型、flush后过期订阅。删除／描述符变化场景的首次tick双方一致，而下一次旧别名变化在San产生多余副作用；不能简单在遍历时丢弃旧子对象，否则会丢失首次合法通知。
- 本轮 {sum(t['count'] for t in tests)} 项定向测试用于验证控制场景和反例可复现；“测试通过”不代表这39个不一致点被修复。
- 通过的普通场景不能外推为任意 key／value 的公开 API 等价。不能通过限制成 UI 已知键、删除属性、强制所有新键响应式或捕获后忽略错误来“修复”。
- 三项生产阻断保留，伪造通过仍拒绝；0 模型调用，原批24/30、6失败、1,821,544 tokens 不变。

反例及双方逐阶段数据：`{OUT.relative_to(ROOT).as_posix()}/observations.json`。
输入／运行时／旧观察器：`{BASE.relative_to(ROOT).as_posix()}`。
测试与代码副本：同证据目录的 `tests` 日志、`audit.json`、`code/`。

后续修复应由反例驱动：先处理公开方法原生属性键转换与赋值语义，再处理删除／描述符变化后的订阅更新；未知或不支持行为继续阻断，不能宣称动态键闭环已经完成。
'''
    with (OUT / 'REPORT.md').open('x', encoding='utf-8') as stream: stream.write(report)
    seal(OUT); verify(OUT)
    if not all(t['returncode'] == 0 for t in tests) or not forged['should_stop'] or not mismatches:
        raise RuntimeError('Audit preconditions/tests failed; evidence preserved, Notebook not appended')
    check = f'''from pathlib import Path
import json, hashlib
root=next(p for p in [Path.cwd(), *Path.cwd().parents] if (p/'migration_pipeline').is_dir())
folder=root/'{OUT.relative_to(ROOT).as_posix()}'
base=root/'{BASE.relative_to(ROOT).as_posix()}'
for d in [folder,base,*[root/p for p in {audit['harness_evidence']!r}]]:
    for line in (d/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected,name=line.split('  ',1)
        assert hashlib.sha256((d/name).read_bytes()).hexdigest()==expected,name
a=json.loads((folder/'audit.json').read_text(encoding='utf-8'))
o=json.loads((folder/'observations.json').read_text(encoding='utf-8'))
assert not a['production_eligible'] and a['model_calls']==0
assert all(t['returncode']==0 for t in a['test_results'])
assert sum(not p['equal'] for p in o['pairs'])==a['mismatch_pair_count']>0
assert len(o['pairs'])==a['pair_count'] and o['host_prototype_clean'] and o['rejection_listener_restored']
assert json.loads((folder/'forged_pass_gate.json').read_text(encoding='utf-8'))['should_stop']
old=json.loads((base/'notebook_before.ipynb').read_text(encoding='utf-8'))
nb=json.loads((root/'{NB.relative_to(ROOT).as_posix()}').read_text(encoding='utf-8'))
assert nb['cells'][:len(old['cells'])]==old['cells'] and nb['metadata']==old['metadata']
print({{'dynamic_shape':'counterexamples retained; production blocked','pairs':len(o['pairs']),'mismatches':a['mismatch_pair_count']}})
'''
    assert json.loads(NB.read_text(encoding='utf-8')) == old
    old['cells'].extend([
        {'cell_type': 'markdown', 'id': 'v7-dynamic-shape-20261114', 'metadata': {}, 'source': report.splitlines(keepends=True)},
        {'cell_type': 'code', 'id': 'v7-dynamic-shape-check-20261114', 'metadata': {}, 'execution_count': None,
         'outputs': [], 'source': check.splitlines(keepends=True)}])
    NB.write_text(json.dumps(old, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    actual = json.loads(NB.read_text(encoding='utf-8'))
    assert len(actual['cells']) == len({c['id'] for c in actual['cells']})
    for cell in actual['cells']:
        if cell['cell_type'] == 'code': compile(''.join(cell['source']), cell['id'], 'exec')
    exec(compile(check, 'dynamic-shape-readonly', 'exec'), {})
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-input', action='store_true'); parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    if args.freeze_input == args.replay: parser.error('Choose exactly one action')
    freeze() if args.freeze_input else replay()
