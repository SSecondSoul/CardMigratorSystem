"""Freeze real headless-browser evidence for the unchanged isolated v7 candidate."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot

PRIOR = ROOT / 'data/experiments/analysis/formal_30_v4_async_watcher_scope_v7_20261113'
FAILURE = ROOT / 'data/experiments/analysis/formal_30_v4_async_browser_startup_failed_20261113'
OUTPUT = ROOT / 'data/experiments/analysis/formal_30_v4_async_watcher_browser_v1_20261113'
NOTEBOOK = ROOT / 'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
PREFIX_SHA = '6af0eb6674c33bb0a63090c91eae8e7790bea46d3ab79949d39d6ead0fa6faee'
METADATA_SHA = 'da8e8b42bb4344c317ccdf5038310d76529bda61666c53ff805bcc19dbede418'
NAMES = ['migration_pipeline/audit_async_watcher_browser_v1.js',
         'migration_pipeline/run_async_watcher_browser_v1.cjs',
         'migration_pipeline/audit_formal_30_v4_async_watcher_browser_v1.py',
         'tests/test_async_watcher_browser_v1.py']


def stable(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def inventory():
    old = json.loads((PRIOR / 'audit.json').read_text(encoding='utf-8'))
    previous = json.loads((PRIOR / 'live_inventory.json').read_text(encoding='utf-8'))
    for name, expected in {**previous, **old['source_inputs'], **old['application_files_sha256'],
                           **old['selected_application_files_sha256']}.items():
        if digest(ROOT / name) != expected:
            raise RuntimeError('Prior/source/application drift: ' + name)
    nb = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    if stable(nb['cells'][:72]) != PREFIX_SHA or stable(nb['metadata']) != METADATA_SHA:
        raise RuntimeError('Previous Notebook cells/metadata changed')
    return {**previous, **{name: digest(ROOT / name) for name in NAMES}}


def payload():
    old = json.loads((PRIOR / 'audit.json').read_text(encoding='utf-8'))
    paths = old['source_inputs']
    data = {key: (ROOT / next(n for n in paths if n.endswith(end))).read_bytes().decode('utf-8')
            for key, end in [('vueRuntime', 'vue.runtime.common.dev.js'), ('sanRuntime', 'san.dev.js')]}
    data['vue'] = (ROOT / next(n for n in paths if n.endswith('.vue'))).read_text(encoding='utf-8')
    data['san_v5'] = (ROOT / next(n for n in paths if n.endswith('TaskManager_error_router_v5_offline.san'))).read_text(encoding='utf-8')
    data['san_v7'] = old['candidate']['code']
    return data


def browser_run(data):
    proc = subprocess.run(['node', str(ROOT / NAMES[1])], cwd=ROOT, input=json.dumps(data),
                          text=True, encoding='utf-8', capture_output=True, timeout=140)
    if proc.returncode or proc.stderr.strip():
        failed = OUTPUT.parent / (OUTPUT.name + '_failed_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.txt')
        with failed.open('x', encoding='utf-8') as stream:
            stream.write('exit=' + str(proc.returncode) + '\n' + proc.stdout + '\n' + proc.stderr)
        raise RuntimeError('Browser attempt failed; raw log retained: ' + str(failed))
    return json.loads(proc.stdout)


def gather():
    hashes = inventory()
    if verify_snapshot(PRIOR.resolve()) != 10 or verify_snapshot(FAILURE.resolve()) != 3:
        raise RuntimeError('Frozen evidence scope drift')
    old = json.loads((PRIOR / 'audit.json').read_text(encoding='utf-8'))
    data = payload()
    print('Running isolated real Edge audit (first)...', flush=True)
    first = browser_run(data)
    print('Running isolated real Edge audit (repeat)...', flush=True)
    second = browser_run(data)
    observed = first['observations']
    if observed != second['observations']:
        failed = OUTPUT.parent / (OUTPUT.name + '_nondeterministic_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.json')
        with failed.open('x', encoding='utf-8') as stream:
            json.dump({'first': first, 'second': second}, stream, ensure_ascii=False, indent=2)
        raise RuntimeError('Browser observations differed; raw attempts saved: ' + str(failed))
    rows = [p for p in observed['pairs'] if p['variant'] == 'san_v7']
    keys = ['stateEqual', 'eventsEqual', 'rawConsoleEqual', 'unhandledRejectionsEqual']
    if len(rows) != 110 or not all(all(p[k] for k in keys) for p in rows):
        raise RuntimeError('Candidate mismatch: do not promote browser result')
    failures = []
    for spec in observed['scenarios']:
        pairs = [p for p in observed['pairs'] if p['scenario'] == spec['name'] and p['variant'] == 'san_v5']
        bad = [p['phase'] for p in pairs if not all(p[k] for k in keys)]
        if bad:
            failures.append({'scenario': spec['name'], 'mismatch_phases': bad})
    if len(failures) != 9:
        raise RuntimeError('Nine old negative route groups not reproduced')
    for run in observed['runs']:
        if not run['boundary']['realBrowser'] or run['boundary']['limitedDOM']:
            raise RuntimeError('This audit must run in real DOM')
        if run['variant'] == 'san_v7' and run['scopeControls'] != {
            'configureOnly': True, 'lateConfiguration': 'CONFIGURATION_LOCKED', 'disposedConfiguration': 'DISPOSED'}:
            raise RuntimeError('Real browser scope guard failed')
    for result in [first, second]:
        if result['transport']['blockedRequests'] or result['transport']['protocolErrors']:
            raise RuntimeError('Unexpected external request or protocol failure')
        if not result['browser']['executable_unchanged_during_run'] or result['observations']['realmCountAfter'] != 0:
            raise RuntimeError('Version/profile/realm isolation failure')
    if first['browser'] != second['browser']:
        raise RuntimeError('Browser identity changed between runs')
    if inventory() != hashes:
        raise RuntimeError('Files changed during browser validation')
    return {'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification': 'real_headless_browser_isolated_minimal_subject_not_full_UI_or_production',
        'previous_verified_payloads': 10, 'failed_startup_verified_payloads': 3,
        'previous_inventory_unchanged': 429, 'inventory_count': len(hashes), 'production_runtime_inventory_unchanged': 387,
        'source_inputs': old['source_inputs'], 'application_files_sha256': old['application_files_sha256'],
        'selected_application_files_sha256': old['selected_application_files_sha256'],
        'candidate_reference': (PRIOR / 'TaskManager_async_scope_v7_offline.san').relative_to(ROOT).as_posix(),
        'candidate_sha256': digest(PRIOR / 'TaskManager_async_scope_v7_offline.san'),
        'browser_run': first, 'repeat_browser_run': second, 'repeat_native_observations_equal': True,
        'v5_negative_control_scenarios': failures,
        'native_model_positive_pairs': 110, 'native_model_total_pairs': 220,
        'original_aggregate': old['original_aggregate'],
        'production_validation_reference': {'path': (PRIOR / 'audit.json').relative_to(ROOT).as_posix(),
            'san_compile_passed': old['actual_validation']['san_compile_result']['passed'],
            'production_validation_passed': old['actual_validation']['validation_passed'], 'new_compile_run_claimed': False},
        'production_diagnostics_reference': old['production_diagnostics'], 'forged_pass_gate_reference': old['forged_pass_gate'],
        'failed_startup': {'path': FAILURE.relative_to(ROOT).as_posix(), 'status': 'no_observations_returned',
            'cause': 'undetermined; sandboxed attempt disconnected, later isolated launches succeeded',
            'temporary_profile_remaining': False, 'not_a_canonical_component_defect': True},
        'evidence_boundary': {'browser_is_real_headless_Edge': True, 'miniDOM_used': False,
            'frameworks_pinned': {'vue': '2.7.16', 'san': '3.15.6'},
            'browser_binary_vendored': False, 'browser_version_and_executable_sha_recorded': True,
            'isolated_native_iframe_parent_chains': True, 'subject_business_bodies_changed': False,
            'subject_render_replaced_with_minimal_node': True, 'fault_storage_and_business_timers_injected': True,
            'real_localStorage_or_business_timer_execution_tested': False,
            'full_TaskManager_UI_or_CSS_tested': False, 'real_user_application_mapping_certified': False,
            'application_binding_supplied_by_isolated_harness': True, 'trusted_binding_not_purity_sandbox': True,
            'SSR_async_hooks_or_general_dependency_pause_proven': False, 'CDN_or_model_used': False},
        'production_integration_enabled': False, 'production_rules_or_prompt_modified': False,
        'existing_pages_or_candidate_modified': False, 'model_requests': 0, 'original_score_modified': False,
        'manual_acceptance_added': False, 'full_suite_reexecuted': False,
        'prior_notebook_cells': 72, 'prior_notebook_cells_sha256': PREFIX_SHA,
        'prior_notebook_metadata_sha256': METADATA_SHA}


def report(data):
    return f'''# 真实浏览器隔离接入验证 v1（2026-11-13）

**已从Node miniDOM前进到真实无头Edge，不是完整TaskManager界面/人工验收，也未接入生产。** 固定本地Vue2.7.16/San3.15.6，无CDN、无模型调用；不改v7候选、旧页面、Prompt/规则和原批成绩。验证报告技能用于分开记录浏览器事实、故障注入和remaining_risk。

## 浏览器与隔离方式

{data['browser_run']['browser']['product']}，可执行文件SHA256：{data['browser_run']['browser']['executable_sha256']}。记录运行版本及运行前后不变的可执行文件指纹，但不声称浏览器二进制已vendoring或将来自动更新后可直接复现。Node内置WebSocket连接本机临时CDP端口，Windows隐藏新建headless进程及临时profile；不复用日常资料。HTTP只监听127.0.0.1随机端口，白名单4路由，不提供目录浏览或任意仓库文件。测试页请求由CDP限制本地origin，无外部页面请求。无需安装Playwright或新依赖。

每场景/变体创建真正同源iframe，固定脚本在iframe的Function/global中执行，原生DOM及native组件父链真实运行；不是Node vm或模拟document。固定时钟、存储故障、业务timer仍为注入装置，调度用真实浏览器Promise和外层原生timer等待。测试结束移除iframe、关闭自己启动的浏览器和临时HTTP服务并清理新建profile。没有调用私有框架错误方法。

## 结果

两次独立浏览器运行的完整native observations相同。每次11场景×3变体×10阶段=33运行、330快照、220比较；v7的110/110阶段在状态、完整业务/捕获事件、原始console和拒绝记录上匹配。原v5九组负向在浏览器仍复现，共51个不匹配阶段，未替换为成功。CDP层异常也完整保留（对应旧v5反例的未处理拒绝），不只查看手工包装console。v7真实实例的配置锁/销毁拒绝与私有入口检查通过，原生San最近error钩子行为保持。

## 失败尝试与边界

首次受限环境尝试在返回观察前CDP连接断开，临时profile清理也失败；原runner、fixture和日志已封存3payload。后续独立启动成功，失败原因仍未定，不武断归为组件或框架错误。失败目录已按明确路径清理，不影响日常资料。

主体render仍替换为最小main节点，**本轮不包含完整模板、子组件UI、CSS、拖拽、设置/任务弹窗或真实存储/timer业务行为验收**。祖先hook/全局handler/logger来自显式隔离应用绑定，并非读取现有RuleBuilder页面配置；不认证真实用户应用映射，也不解决任意回调副作用、一般依赖暂停、SSR或异步钩子问题。原生产验证仍失败的已有证据只引用，不声称本轮重编译或放行。

## 测试与证据

定向测试：{json.dumps(data['scoped_tests'], ensure_ascii=False)}。不是完整703项重跑，也不是30样本新批次。旧429项清单（含387生产/既有运行文件）及Notebook旧72单元/元数据保留，新增4文件后433项；本轮8payload，另失败3payload。原批24/30、6失败、0执行异常、1,821,544 tokens不变；无commit/push。

下一步应准备固定版本、完整TaskManager模板和内联子组件的独立人工验收入口，再由用户确认真实界面交互；不应据最小渲染接入测试直接声称整个组件或生产闭环通过。
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-evidence', action='store_true')
    args = parser.parse_args()
    if args.write_evidence and OUTPUT.exists():
        raise FileExistsError('Never overwrite frozen browser evidence')
    hashes, data = inventory(), gather()
    if args.write_evidence:
        logs, suites = '', []
        with tempfile.TemporaryDirectory(prefix='cardmig-browser-evidence-') as temp:
            staged = Path(temp) / 'audit.json'
            with staged.open('x', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False)
            for suite in ['test_async_watcher_browser_v1.py', 'test_async_watcher_scope_v7.py', 'test_parent_watch_scope_guard.py']:
                print('Running ' + suite, flush=True)
                proc = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', suite, '-v'],
                    cwd=ROOT, capture_output=True, text=True, encoding='utf-8',
                    env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'CARDMIG_BROWSER_AUDIT_EVIDENCE': str(staged)})
                text = proc.stdout + proc.stderr; logs += '\n### ' + suite + '\n' + text
                match = re.search(r'Ran (\d+) tests in ([\d.]+)s', text)
                if proc.returncode or not match or '\nOK' not in text or re.search(r'OK\s*\(skipped=', text):
                    failed = OUTPUT.parent / (OUTPUT.name + '_tests_failed_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.txt')
                    with failed.open('x', encoding='utf-8') as stream: stream.write(logs)
                    raise RuntimeError('Scoped failure retained: ' + str(failed))
                suites.append({'suite': suite, 'passed': int(match[1]), 'elapsed_seconds': float(match[2])})
        if inventory() != hashes: raise RuntimeError('Files changed during tests')
        data['scoped_tests'] = {'passed': sum(s['passed'] for s in suites), 'failed': 0, 'skipped': 0, 'suites': suites,
            'elapsed_seconds': round(sum(s['elapsed_seconds'] for s in suites), 3), 'not_a_full_suite': True,
            'browser_tests_validate_recorded_live_run_not_launch_per_unit_test': True}
        OUTPUT.mkdir(parents=True, exist_ok=False)
        for name in NAMES:
            target = OUTPUT / 'code' / name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, target)
        for name, value in [('audit.json', json.dumps(data, ensure_ascii=False, indent=2) + '\n'),
                            ('live_inventory.json', json.dumps(hashes, ensure_ascii=False, indent=2) + '\n'),
                            ('REPORT.md', report(data)), ('scoped_tests.txt', logs)]:
            with (OUTPUT / name).open('x', encoding='utf-8') as stream: stream.write(value)
        files = sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        with (OUTPUT / 'SHA256SUMS.txt').open('x', encoding='utf-8') as stream:
            stream.write('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files) + '\n')
        data['verified_payloads'] = verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'written': args.write_evidence, 'payloads': data.get('verified_payloads'), 'tests': data.get('scoped_tests'),
        'browser': data['browser_run']['browser']['product'], 'candidate_matched_pairs': 110,
        'repeat_native_observations_equal': True, 'full_UI_or_production_claimed': False}, ensure_ascii=False))


if __name__ == '__main__': main()
