"""Freeze private async-watcher capability guards without production promotion."""
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
from migration_pipeline.audit_formal_30_v4_parent_watch_boundaries_v1 import RAW
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate, PARENT_WATCH_REVIEW_CODES

PRIOR = ROOT / 'data/experiments/analysis/formal_30_v4_error_context_reactivity_audit_v1_20261113'
V6 = ROOT / 'data/experiments/analysis/formal_30_v4_source_error_context_v6_20261113'
FAILURE = ROOT / 'data/experiments/analysis/formal_30_v4_async_scope_v7_adapter_preflight_failed_20261113'
SCOPE = ROOT / 'data/experiments/analysis/formal_30_v4_parent_watch_scope_guard_v1_20261111'
OUTPUT = ROOT / 'data/experiments/analysis/formal_30_v4_async_watcher_scope_v7_20261113'
NOTEBOOK = ROOT / 'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
PREFIX_SHA = '33ab75e3ff311b922f5580d3b69a4338b610a06a44c11307f3076c9a9df79085'
METADATA_SHA = 'da8e8b42bb4344c317ccdf5038310d76529bda61666c53ff805bcc19dbede418'
NAMES = ['migration_pipeline/probe_async_watcher_scope_v7.cjs',
         'migration_pipeline/probe_async_watcher_scope_adapter_v7.cjs',
         'migration_pipeline/audit_async_watcher_scope_v7_runtime.cjs',
         'migration_pipeline/probe_formal_30_v4_async_watcher_scope_v7.py',
         'tests/test_async_watcher_scope_v7.py']


def stable(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def inventory():
    previous = json.loads((PRIOR / 'live_inventory.json').read_text(encoding='utf-8'))
    old = json.loads((PRIOR / 'audit.json').read_text(encoding='utf-8'))
    for name, expected in {**previous, **old['source_inputs'], **old['application_files_sha256'],
                           **old['application_static_audit']['selected_files_sha256']}.items():
        if digest(ROOT / name) != expected:
            raise RuntimeError('Prior/source/application drift: ' + name)
    nb = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    if stable(nb['cells'][:70]) != PREFIX_SHA or stable(nb['metadata']) != METADATA_SHA:
        raise RuntimeError('Previous Notebook cells/metadata changed')
    return {**previous, **{name: digest(ROOT / name) for name in NAMES}}


def fixtures():
    sys.path.insert(0, str(ROOT / 'tests'))
    spec = importlib.util.spec_from_file_location('async_watcher_scope_v7_fixture', ROOT / NAMES[-1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def gather():
    hashes = inventory()
    verified = {name: verify_snapshot(path.resolve()) for name, path in [
        ('reactivity_audit', PRIOR), ('v6_candidate', V6), ('failed_adapter_preflight', FAILURE), ('scope_guard', SCOPE)]}
    if verified != {'reactivity_audit': 7, 'v6_candidate': 10, 'failed_adapter_preflight': 2, 'scope_guard': 25}:
        raise RuntimeError('Frozen evidence scope changed')
    old = json.loads((PRIOR / 'audit.json').read_text(encoding='utf-8'))
    v6 = json.loads((V6 / 'audit.json').read_text(encoding='utf-8'))
    p = fixtures()
    browser, v5, base, common, _v6, payload = p.payloads()
    candidate = p.adapt(**base)
    observed = p.node(p.RUNTIME, {**payload, 'san_v7': candidate['code']})
    if observed != p.node(p.RUNTIME, {**payload, 'san_v7': candidate['code']}):
        raise RuntimeError('Nondeterministic native audit')
    rows = [r for r in observed['pairs'] if r['variant'] == 'san_v7']
    if len(rows) != 110 or not all(all(r[k] for k in ['stateEqual', 'eventsEqual', 'rawConsoleEqual', 'unhandledRejectionsEqual']) for r in rows):
        raise RuntimeError('Legal mapped scope no longer matches')
    if [r for r in observed['runs'] if r['variant'] != 'san_v7'] != browser['native_observations']['runs']:
        raise RuntimeError('Source/v5 complete control changed')
    pairs = [{k: v for k, v in r.items() if k != 'variant'} for r in observed['pairs'] if r['variant'] == 'san_v5']
    if pairs != browser['native_observations']['pairs']:
        raise RuntimeError('Old nine failures changed')
    for run in observed['runs']:
        if run['variant'] == 'san_v7' and run['scopeControls'] != {
            'configureOnly': True, 'lateConfiguration': 'CONFIGURATION_LOCKED', 'disposedConfiguration': 'DISPOSED'}:
            raise RuntimeError('Native API guard failed')
    structure = p.node(p.STRUCTURE, {'before': v5['candidate']['code'], 'after': candidate['code']})
    if structure != {'factories': 2, 'catches': 1, 'schedules': 1, 'privateStatements': 4, 'rest_of_script_unchanged': True}:
        raise RuntimeError('Unexpected AST scope')
    unit = p.node(p.UNIT, {})
    unconfigured_browser = p.node(p.BROWSER / 'code/migration_pipeline/audit_browser_error_chain_v1_runtime.cjs',
                                  {**payload, 'san_v5': candidate['code']})
    if unconfigured_browser != v6['unconfigured_browser_observations']:
        raise RuntimeError('Unconfigured browser behavior changed')
    v4 = json.loads((ROOT / 'data/experiments/analysis/formal_30_v4_parent_alias_observer_v4_20261112/audit.json').read_text(encoding='utf-8'))
    headless = p.node(p.V5 / 'code/migration_pipeline/audit_parent_watch_error_router_v5_runtime.cjs',
        {**common, 'vue': base['vue'], 'san_v4': v4['candidate']['code'], 'san_v5': candidate['code']})
    if headless != v6['unconfigured_headless_observations']:
        raise RuntimeError('Unconfigured old explicit reporter behavior changed')
    f = v4['mounted_fixture']
    generic = p.adapt(f['normal'], f['vue'])
    mounted = p.node(p.ALIAS / 'code/migration_pipeline/audit_parent_alias_child_runtime.cjs', {**common, **f, 'v3': generic['code']})
    if mounted != v6['mounted_observations']:
        raise RuntimeError('Native child behavior changed')
    retained = json.loads((SCOPE / 'replay.json').read_text(encoding='utf-8'))['retained_artifact_replays']
    if len(retained) != 30:
        raise RuntimeError('Expected 30 retained inputs')
    for row in retained:
        for key in ['input', 'vue']:
            if digest(ROOT / row[key + '_path']) != row[key + '_sha256']:
                raise RuntimeError('Retained source/input drift: ' + row['id'])
    ssm = json.loads((RAW / 'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']['ssm']
    source = ROOT / next(name for name in old['source_inputs'] if name.endswith('.vue'))
    validation = ValidateStage().run(ValidateStageInput(generated_code=candidate['code'], ssm=ssm, vue_file_path=str(source))).to_state_update()
    if validation['validation_passed'] or not validation['san_compile_result']['passed']:
        raise RuntimeError('Expected compilable but production-blocked candidate')
    diagnostics = source_parent_watch_semantics(candidate['code'], base['vue'])
    if {r['code'] for r in diagnostics['blocked_boundaries']} != PARENT_WATCH_REVIEW_CODES:
        raise RuntimeError('Production boundaries lost')
    before = {'generated_code': base['code'], 'vue_source': base['vue'],
              'validation_errors': source_parent_watch_semantics(base['code'], base['vue'])['findings']}
    gate = candidate_gate(before, {**before, 'generated_code': candidate['code'], 'validation_errors': [], 'validation_passed': True})
    if not gate['should_stop'] or len(gate['waived_source_parent_watch_boundaries']) != 2:
        raise RuntimeError('Forged pass was not refused')
    if inventory() != hashes:
        raise RuntimeError('Files changed during verification')
    return {'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification': 'isolated_private_async_watcher_scope_not_purity_or_production_closure',
        'source_verified_payloads': verified, 'previous_inventory_unchanged': 424, 'inventory_count': len(hashes),
        'production_runtime_inventory_unchanged': 387, 'source_inputs': old['source_inputs'],
        'application_files_sha256': old['application_files_sha256'],
        'selected_application_files_sha256': old['application_static_audit']['selected_files_sha256'],
        'retained_30_inputs_unchanged': True, 'candidate': candidate, 'generic_candidate': generic,
        'native_observations': observed, 'exact_scope_structure_check': structure,
        'helper_only_guard_observations': unit,
        'unconfigured_browser_observations': unconfigured_browser, 'unconfigured_headless_observations': headless,
        'mounted_observations': mounted, 'actual_validation': validation,
        'production_diagnostics': diagnostics, 'forged_pass_gate': gate,
        'v5_negative_control_scenarios': browser['negative_route_scenarios'],
        'original_aggregate': old['original_aggregate'],
        'scope_guards': {'private_Promise_entry': True, 'no_public_v7_route_or_handle_on_component': True,
            'first_schedule_locks_configuration': True, 'disposed_scope_refused': True,
            'cross_scope_or_outside_route_refused': True, 'invalid_watcher_index_refused': True,
            'unsupported_declared_profiles_refused': True, 'arbitrary_callback_purity_enforced': False,
            'async_hook_effects_detected_or_sandboxed': False, 'general_dependency_pause_implemented': False},
        'remaining_risk': {'category': 'remaining_risk',
            'scope': 'Application capabilities remain trusted; entry guards do not certify reactive purity or source mapping.',
            'production_integration_enabled': False, 'application_mapping_deployed': False,
            'real_browser_or_canonical_TaskManager_UI_tested': False, 'SSR_or_async_hooks_proven': False,
            'unconfigured_legacy_failure_behavior_deliberately_retained': True},
        'failed_preflight': {'path': FAILURE.relative_to(ROOT).as_posix(), 'verified_payloads': 2,
            'cause': 'AST schedule comparison received Array; restricted comparison to CallExpression.',
            'native_run_or_model_request_started': False, 'not_a_canonical_component_defect': True},
        'production_rules_or_prompt_modified': False, 'prior_candidate_or_manual_pages_modified': False,
        'model_requests': 0, 'original_score_modified': False, 'full_suite_reexecuted': False,
        'prior_notebook_cells': 70, 'prior_notebook_cells_sha256': PREFIX_SHA,
        'prior_notebook_metadata_sha256': METADATA_SHA}


def report(data):
    return f'''# 私有异步 watcher 入口范围：隔离候选 v7（2026-11-13）

**新增可执行的入口范围保护，不是任意回调副作用检测，也不是生产放行。** 不改v6及旧证据、生产Prompt/repair.py、canonical San或页面。原批24/30、6失败、0执行异常、1,821,544 tokens不变；0模型调用、无新增人工验收。

## 范围与实际修改

v5基础上内联冻结v6源错误路由工厂及新增scope工厂。scope只存在于inited闭包，不挂在组件上；组件仅有配置委托，不暴露v7 route/run/handle。scope自身安排Promise进入，dispatch catch只在该入口有效期内调用route；watcher归属由冻结fields+合法索引生成，不接受任意info或subject。首次schedule即锁配置，早于实际tick；重复/重入schedule、跨scope/队列外route、非法索引、销毁后使用和不支持的声明profile均拒绝。能力函数引用和fields复制，避免调用者替换配置槽位；已排队后销毁仍走原队列取消/reset逻辑，异常finally撤销active状态。

AST反向还原只涉及2个factory、1个catch分支、1个schedule入口、4条私有配置/销毁语句，其余v5脚本及完整业务/生命周期方法体相同。未配置新context时仍走原v5显式报告器或抛错路径；兼容行为刻意保留，不是缺少映射也安全放行。

## 验证

11场景×3变体×10阶段=33运行、330快照、220源/目标比较；v7合法显式映射110/110阶段的状态、完整事件、raw console、拒绝匹配。原source/v5全量22运行和110比较完整保留，九组负向仍在。11个v7实例均只暴露配置入口；首次tick后重新配置为CONFIGURATION_LOCKED，销毁后为DISPOSED。原生San最近error控制语义不变。

helper guard单测另存：它证明实际Promise进入后才可route，以及异常恢复、pending取消、原错误身份和索引边界；不是TaskManager UI或真实浏览器证据。未配置v7时旧浏览器、旧headless报告器和native子组件装置观察原样保留。候选San本轮编译通过，生产验证仍失败；独立动态键/异常策略诊断和伪造通过保护保留。

## 不能夸大的边界

入口保护**不检测任意函数的响应式读写或Promise副作用**。parentOf/hooksOf/globalHandler/logError仍是受信任应用能力，profile检查只拒绝不支持的声明；调用者谎报纯度时不提供沙箱安全保证。一般依赖暂停、活跃收集器上下文、SSR、异步/无限重入、任意源祖先映射和通用diagnostic renderer都未证明。当前两页仍为RuleBuilder，未配置v7。故不接入生产、不放宽诊断或启动模型复跑。

## 中间失败与证据

首次适配器预检查在生成候选前失败：AST比较器收到Array，旧版本与日志已独立封存（2payload）；修正为仅比较CallExpression，新增AST范围回归覆盖。它不是canonical组件新缺陷，不能从论文过程记录中删除。

定向测试：{json.dumps(data['scoped_tests'], ensure_ascii=False)}。未重跑完整703项。旧424项清单（含387生产/既有运行文件）、30保留输入/Vue、应用文件及Notebook旧70单元/元数据保留；新增5文件后429项，10个payload封存（另有失败2payload）。验证报告技能用于区分入口保证与纯度/应用集成的remaining_risk。

下一步应做固定版本真实浏览器中的隔离应用接入验证，并明确应用能力的信任边界；在此之前不把scope保护当作完整异常闭环或正式30样本新成绩。
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-evidence', action='store_true')
    args = parser.parse_args()
    if args.write_evidence and OUTPUT.exists():
        raise FileExistsError('Never overwrite frozen v7 evidence')
    hashes, data = inventory(), gather()
    if args.write_evidence:
        logs, suites = '', []
        for suite in ['test_async_watcher_scope_v7.py', 'test_source_error_context_v6.py',
                      'test_error_context_reactivity_audit_v1.py', 'test_parent_watch_scope_guard.py']:
            print('Running ' + suite, flush=True)
            proc = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', suite, '-v'],
                cwd=ROOT, capture_output=True, text=True, encoding='utf-8', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
            text = proc.stdout + proc.stderr
            logs += '\n### ' + suite + '\n' + text
            match = re.search(r'Ran (\d+) tests in ([\d.]+)s', text)
            if proc.returncode or not match or '\nOK' not in text or re.search(r'OK\s*\(skipped=', text):
                failed = OUTPUT.parent / (OUTPUT.name + '_failed_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.txt')
                with failed.open('x', encoding='utf-8') as stream: stream.write(logs)
                raise RuntimeError('Scoped failure saved: ' + str(failed))
            suites.append({'suite': suite, 'passed': int(match[1]), 'elapsed_seconds': float(match[2])})
        if inventory() != hashes: raise RuntimeError('Files changed during tests')
        data['scoped_tests'] = {'passed': sum(s['passed'] for s in suites), 'failed': 0, 'skipped': 0,
            'suites': suites, 'elapsed_seconds': round(sum(s['elapsed_seconds'] for s in suites), 3), 'not_a_full_suite': True}
        OUTPUT.mkdir(parents=True, exist_ok=False)
        for name in NAMES:
            target = OUTPUT / 'code' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        for name, value in [('audit.json', json.dumps(data, ensure_ascii=False, indent=2) + '\n'),
                            ('live_inventory.json', json.dumps(hashes, ensure_ascii=False, indent=2) + '\n'),
                            ('REPORT.md', report(data)), ('scoped_tests.txt', logs),
                            ('TaskManager_async_scope_v7_offline.san', data['candidate']['code'])]:
            with (OUTPUT / name).open('x', encoding='utf-8') as stream: stream.write(value)
        files = sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        with (OUTPUT / 'SHA256SUMS.txt').open('x', encoding='utf-8') as stream:
            stream.write('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files) + '\n')
        data['verified_payloads'] = verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'written': args.write_evidence, 'tests': data.get('scoped_tests'), 'payloads': data.get('verified_payloads'),
        'matched_candidate_pairs': 110, 'purity_enforced': False, 'production_integration_enabled': False, 'model_requests': 0}, ensure_ascii=False))


if __name__ == '__main__': main()
