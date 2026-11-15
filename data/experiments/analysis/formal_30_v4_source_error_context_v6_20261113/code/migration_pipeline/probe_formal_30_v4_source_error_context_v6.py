"""Freeze an isolated, explicitly mapped browser error-context candidate."""
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

PRIOR = ROOT / 'data/experiments/analysis/formal_30_v4_browser_error_chain_audit_v1_20261113'
V5 = ROOT / 'data/experiments/analysis/formal_30_v4_watch_error_router_v5_20261113'
V4 = ROOT / 'data/experiments/analysis/formal_30_v4_parent_alias_observer_v4_20261112'
ALIAS = ROOT / 'data/experiments/analysis/formal_30_v4_parent_alias_child_audit_v1_20261112'
SCOPE = ROOT / 'data/experiments/analysis/formal_30_v4_parent_watch_scope_guard_v1_20261111'
OUTPUT = ROOT / 'data/experiments/analysis/formal_30_v4_source_error_context_v6_20261113'
NOTEBOOK = ROOT / 'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
PREFIX_SHA = '44170a0dc04f9b12faed8ea168b2b67de06607822c9a5a9566d599ecfcafb3a4'
METADATA_SHA = 'da8e8b42bb4344c317ccdf5038310d76529bda61666c53ff805bcc19dbede418'
NAMES = ['migration_pipeline/probe_source_error_context_v6.cjs',
         'migration_pipeline/probe_source_error_context_adapter_v6.cjs',
         'migration_pipeline/audit_source_error_context_v6_runtime.cjs',
         'migration_pipeline/probe_formal_30_v4_source_error_context_v6.py',
         'tests/test_source_error_context_v6.py']


def stable(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def inventory():
    old = json.loads((PRIOR / 'live_inventory.json').read_text(encoding='utf-8'))
    drift = [n for n, s in old.items() if digest(ROOT / n) != s]
    if drift:
        raise RuntimeError('Prior 416 files changed: ' + str(drift))
    data = json.loads((PRIOR / 'audit.json').read_text(encoding='utf-8'))
    if any(digest(ROOT / n) != s for n, s in data['application_files_sha256'].items()):
        raise RuntimeError('Application pages/scripts changed')
    nb = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    if stable(nb['cells'][:66]) != PREFIX_SHA or stable(nb['metadata']) != METADATA_SHA:
        raise RuntimeError('Old Notebook cells/metadata changed')
    return {**old, **{n: digest(ROOT / n) for n in NAMES}}


def fixtures():
    sys.path.insert(0, str(ROOT / 'tests'))
    spec = importlib.util.spec_from_file_location('source_context_v6_fixture', ROOT / NAMES[-1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def gather():
    hashes = inventory()
    p = fixtures()
    old, v5, base, common, candidate, payload = p.payloads()
    verified = {k: verify_snapshot(v.resolve()) for k, v in [
        ('browser_counterexamples', PRIOR), ('v5_candidate', V5),
        ('v4_observer', V4), ('frozen_dom_adapter', ALIAS), ('scope_guard', SCOPE)]}
    if verified != {'browser_counterexamples': 7, 'v5_candidate': 9,
                    'v4_observer': 10, 'frozen_dom_adapter': 7, 'scope_guard': 25}:
        raise RuntimeError('Evidence scope drift')
    inputs = old['source_inputs']
    for n, s in inputs.items():
        if digest(ROOT / n) != s:
            raise RuntimeError('Source/runtime drift: ' + n)
    retained = json.loads((SCOPE / 'replay.json').read_text(encoding='utf-8'))['retained_artifact_replays']
    if len(retained) != 30:
        raise RuntimeError('Expected 30 retained inputs')
    for row in retained:
        for key in ['input', 'vue']:
            if digest(ROOT / row[key + '_path']) != row[key + '_sha256']:
                raise RuntimeError('Retained input drift: ' + row['id'])
    observed = p.node(p.RUNTIME, payload)
    if observed != p.node(p.RUNTIME, payload):
        raise RuntimeError('Nondeterministic native context audit')
    rows = [r for r in observed['pairs'] if r['variant'] == 'san_v6']
    keys = ['stateEqual', 'eventsEqual', 'rawConsoleEqual', 'unhandledRejectionsEqual']
    if len(observed['runs']) != 33 or sum(len(r['phases']) for r in observed['runs']) != 330 or len(observed['pairs']) != 220:
        raise RuntimeError('Audit dimensions drift')
    if len(rows) != 110 or not all(all(r[k] for k in keys) for r in rows):
        raise RuntimeError('Explicit context candidate mismatch')
    if [r for r in observed['runs'] if r['variant'] != 'san_v6'] != old['native_observations']['runs']:
        raise RuntimeError('Frozen source/v5 control runs changed')
    controls = [{k: v for k, v in r.items() if k != 'variant'} for r in observed['pairs'] if r['variant'] == 'san_v5']
    if controls != old['native_observations']['pairs'] or len(old['negative_route_scenarios']) != 9:
        raise RuntimeError('Old nine negative route groups lost')
    for run in observed['runs']:
        if not run['nativeAncestorChain']:
            raise RuntimeError('Missing native ancestor chain')
        if run['variant'] != 'vue_source':
            c = run['nativeSanControl']
            if not c['nativeChildParentLink'] or not c['nearReturnedTrue'] or c['received'] != [
                {'ancestor': 'near', 'originalError': True, 'subjectIsChild': True, 'info': 'watch:value'}]:
                raise RuntimeError('Native San semantics patched or control failed')
    structure = p.node(p.STRUCTURE, {'before': v5['candidate']['code'], 'after': candidate['code']})
    if structure != {'factory': 1, 'configure': 1, 'dispatch': 1, 'rest_of_script_unchanged': True}:
        raise RuntimeError('Candidate AST scope expanded')
    unit = p.node(p.HELPER_UNIT, {})
    unconfigured_browser = p.node(PRIOR / 'code/migration_pipeline/audit_browser_error_chain_v1_runtime.cjs',
                                  {**payload, 'san_v5': candidate['code']})
    if unconfigured_browser != old['native_observations']:
        raise RuntimeError('Unconfigured candidate changed old browser failures')
    v4 = json.loads((V4 / 'audit.json').read_text(encoding='utf-8'))
    unconfigured_headless = p.node(V5 / 'code/migration_pipeline/audit_parent_watch_error_router_v5_runtime.cjs',
        {**common, 'vue': base['vue'], 'san_v4': v4['candidate']['code'], 'san_v5': candidate['code']})
    if unconfigured_headless != v5['explicit_policy_observations']:
        raise RuntimeError('Unconfigured candidate changed old headless failures')
    fixture = v4['mounted_fixture']
    generic = p.adapt(fixture['normal'], fixture['vue'])
    mounted = p.node(ALIAS / 'code/migration_pipeline/audit_parent_alias_child_runtime.cjs',
                     {**common, **fixture, 'v3': generic['code']})
    if mounted != v4['mounted_observations']:
        raise RuntimeError('Native observer/child behavior changed')
    ssm = json.loads((RAW / 'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']['ssm']
    vue_path = ROOT / next(n for n in inputs if n.endswith('.vue'))
    validation = ValidateStage().run(ValidateStageInput(
        generated_code=candidate['code'], ssm=ssm, vue_file_path=str(vue_path))).to_state_update()
    if validation['validation_passed'] or not validation['san_compile_result']['passed']:
        raise RuntimeError('Expected compilable but production-blocked candidate')
    diagnostics = source_parent_watch_semantics(candidate['code'], base['vue'])
    if {r['code'] for r in diagnostics['blocked_boundaries']} != PARENT_WATCH_REVIEW_CODES:
        raise RuntimeError('Production boundary lost')
    before = {'generated_code': base['code'], 'vue_source': base['vue'],
              'validation_errors': source_parent_watch_semantics(base['code'], base['vue'])['findings']}
    gate = candidate_gate(before, {**before, 'generated_code': candidate['code'],
                                   'validation_errors': [], 'validation_passed': True})
    if not gate['should_stop'] or len(gate['waived_source_parent_watch_boundaries']) != 2:
        raise RuntimeError('Forged pass was not refused')
    if inventory() != hashes:
        raise RuntimeError('Files changed during audit')
    return {
        'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification': 'isolated_explicit_mapped_browser_source_error_context_not_production_closure',
        'source_verified_payloads': verified, 'source_inputs': inputs,
        'previous_inventory_unchanged': 416, 'production_runtime_inventory_unchanged': 387,
        'inventory_count': len(hashes), 'application_files_sha256': old['application_files_sha256'],
        'retained_30_inputs_unchanged': True, 'original_aggregate': old['original_aggregate'],
        'candidate': candidate, 'generic_candidate': generic, 'native_observations': observed,
        'v5_negative_control_scenarios': old['negative_route_scenarios'],
        'exact_scope_structure_check': structure, 'helper_only_unit_observations': unit,
        'unconfigured_browser_observations': unconfigured_browser,
        'unconfigured_headless_observations': unconfigured_headless, 'mounted_observations': mounted,
        'actual_validation': validation, 'production_diagnostics': diagnostics, 'forged_pass_gate': gate,
        'mapped_reporting_only_browser_contract_matched': True,
        'application_bindings': {
            'parent_mapping': 'Native San parentComponent chain supplied explicitly by harness',
            'capture_mapping': 'Scenario hook lists explicitly attached to native Near/Far options',
            'global_handler': 'Fresh application getter; reporting-only synchronous handlers',
            'diagnostic_sink': 'Harness-only bounded Vue 2.7.16 trace formatter using explicit source names',
            'tracking_policy': 'no-reactive-reads-or-writes',
            'automatic_source_context_migration_implemented': False,
            'general_Vue_diagnostic_renderer_implemented': False,
            'runtime_enforces_hook_purity': False,
            'existing_application_binding_identified_or_deployed': False},
        'evidence_boundary': {
            'runtime_versions': {'vue': '2.7.16', 'san': '3.15.6'},
            'vue_inBrowser_branch_executed': True, 'limited_dom_adapter': True,
            'native_ancestor_components_mounted': True, 'subject_render_replaced': True,
            'subject_business_bodies_changed': False, 'actual_canonical_TaskManager_UI_tested': False,
            'real_browser_opened': False, 'real_storage_or_business_timers': False,
            'private_error_functions_called_by_harness': False,
            'twenty_two_native_San_controls_outside_main_phase_comparisons': True},
        'finding': {'category': 'remaining_risk', 'status': 'partially_addressed_in_explicit_fixture_only',
                    'nine_scenarios_are_not_nine_production_defects': True,
                    'unproven': ['arbitrary application mapping', 'dependency suspension/reactive hooks',
                                 'async/reentrant hooks', 'SSR/Node fallback', 'throwing diagnostic sinks',
                                 'general diagnostic formatting', 'real browser application integration']},
        'source_default_exception_contract_closed': False, 'production_integration_enabled': False,
        'canonical_san_or_manual_pages_modified': False, 'prior_probe_or_failure_evidence_modified': False,
        'production_rules_or_prompt_modified': False, 'source_api_or_storage_schema_restricted': False,
        'model_requests': 0, 'original_score_modified': False, 'full_suite_reexecuted': False,
        'manual_or_browser_rechecked': False, 'prior_full_suite_reference': v5['prior_full_suite_reference'],
        'prior_notebook_cells': 66, 'prior_notebook_cells_sha256': PREFIX_SHA,
        'prior_notebook_metadata_sha256': METADATA_SHA}


def report(data):
    return f'''# 源错误上下文桥：隔离候选 v6（2026-11-13）

**实现了显式映射、同步只报告、不读写响应式状态的浏览器错误上下文协议；不等于生产异常闭环。**
formal_30_v4 开发探针，非独立正式测试。原批仍为24/30、6失败、0执行异常、1,821,544 tokens；0模型请求，无新增人工验收。

## 根因与修改位置

v5合并Promise队列的异常缺少Vue祖先捕获/全局回退上下文；San原生最近error钩子语义也不能直接替代Vue errorCaptured。新增独立helper及AST探针，仅在v5之上插入helper工厂、实例配置方法及dispatch分支。源赋值右侧、队列、观察桥、业务方法、事件和生命周期其余脚本通过AST反向还原确认未改。不是生成/修复阶段生产Prompt改动，也未接入生产repair.py。

应用必须明确提供原生父链、钩子列表、全局处理器getter和终端日志sink；从近祖先到远祖先、同祖先声明顺序调用，仅严格false短路。捕获钩子抛错后将次生错误归属该祖先，按errorCaptured hook进入全局，再继续原错误。全局抛不同错误先记录次生再原错误；重抛原错误不重复记录。无handler时交给显式终端sink，继续队列，不重试失败回调内部语句。不猜测San.error映射、不安装全局补丁。

## 受控原生证据

固定Vue2.7.16/San3.15.6和冻结miniDOM；11场景×3变体×10阶段=33运行、330快照、220源/目标比较。显式映射v6的110/110阶段在状态、完整事件、原始console、Promise拒绝记录上匹配。旧source/v5的22运行和110比较完整不变，九组负向仍在；没有把历史失败覆盖成成功。另22个独立原生San watch控制证实最近error返回true仍不冒泡，未改全局San语义。

**传播协议与诊断文字分开负责。** 核心helper不实现Vue通用组件trace；本次应用装置显式映射subject/near/far源名称，并提供有界、非递归的诊断格式适配器，因而这些fixture的raw console能相等。该适配器是冻结runtime harness源码，不是生产日志实现，更未证明任意组件栈/重复栈/递归格式。真实native parentComponent关系已检查，但源应用映射由装置显式给出，不是自动迁移成果。

主体渲染替换为最小节点，业务/生命周期方法体不改。故障存储与应用timer为注入装置；原生框架、Promise和祖先挂载真实执行，但未打开真实浏览器，不是TaskManager UI/CSS或真实存储验收。纯helper无效映射单测另存，不冒充native框架证据。

## 保护与残余风险

未配置v6时，旧浏览器全量观察及旧headless显式报告器审计均原样保留（含失败）；旧native子组件观察保持。候选San本轮编译通过，生产验证仍失败；独立动态键/异常策略诊断和伪造通过保护仍阻止放行。

受控profile声明不读写响应式状态，**未实现也未证明依赖收集暂停，运行时不强制hook纯度**。任意应用祖先/config映射、异步/可重入hook、SSR/Node回退、抛错日志sink及通用trace仍未闭合；不能以调用者声明代替这些证明。缺少context时仍走原v5行为，不默认吞错。九种场景是同一剩余风险的展开，不计为九条生产缺陷，也不增加人工通过数。

## 测试与封存

定向测试：{json.dumps(data['scoped_tests'], ensure_ascii=False)}。不是完整703项重跑。旧416项清单（含387生产/既有运行文件）、30保留输入/Vue、测试页/验收脚本、Notebook旧66单元和元数据未变；新增5文件后421项，10个payload封存。candidate .san仅为分析目录中的离线证据，不替换canonical产物。

下一步应先证明真实应用上下文映射与响应式依赖边界，再决定能否接入；不能直接启动付费模型复跑或宣布完整闭环。不修改生产Prompt/规则、页面、原成绩，不commit/push。
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-evidence', action='store_true')
    args = parser.parse_args()
    if args.write_evidence and OUTPUT.exists():
        raise FileExistsError('Never overwrite frozen v6 evidence')
    hashes = inventory()
    data = gather()
    logs, counts = '', []
    if args.write_evidence:
        for suite in ['test_source_error_context_v6.py', 'test_browser_error_chain_audit_v1.py',
                      'test_parent_watch_error_router_v5.py', 'test_parent_watch_scope_guard.py']:
            print('Running scoped suite: ' + suite, flush=True)
            proc = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', suite, '-v'],
                cwd=ROOT, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                capture_output=True, text=True, encoding='utf-8')
            part = proc.stdout + proc.stderr
            logs += '\n### ' + suite + '\n' + part
            match = re.search(r'Ran (\d+) tests in ([\d.]+)s', part)
            if proc.returncode or not match or '\nOK' not in part or re.search(r'OK\s*\(skipped=', part):
                failed = OUTPUT.parent / (OUTPUT.name + '_failed_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.txt')
                with failed.open('x', encoding='utf-8') as stream:
                    stream.write(logs)
                raise RuntimeError('Scoped failure log saved: ' + str(failed))
            counts.append({'suite': suite, 'passed': int(match[1]), 'elapsed_seconds': float(match[2])})
        if inventory() != hashes:
            raise RuntimeError('Files changed during verification')
        data['scoped_tests'] = {'passed': sum(r['passed'] for r in counts), 'failed': 0, 'skipped': 0,
            'elapsed_seconds': round(sum(r['elapsed_seconds'] for r in counts), 3), 'suites': counts, 'not_a_full_suite': True}
        OUTPUT.mkdir(parents=True, exist_ok=False)
        for name in NAMES:
            target = OUTPUT / 'code' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        for name, value in [('audit.json', data), ('live_inventory.json', hashes)]:
            with (OUTPUT / name).open('x', encoding='utf-8') as stream:
                stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        for name, value in [('REPORT.md', report(data)), ('scoped_tests.txt', logs),
                            ('TaskManager_source_error_context_v6_offline.san', data['candidate']['code'])]:
            with (OUTPUT / name).open('x', encoding='utf-8') as stream:
                stream.write(value)
        files = sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        with (OUTPUT / 'SHA256SUMS.txt').open('x', encoding='utf-8') as stream:
            stream.write('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files) + '\n')
        data['verified_payloads'] = verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'written': args.write_evidence, 'tests': data.get('scoped_tests'),
        'verified_payloads': data.get('verified_payloads'), 'matched_candidate_pairs': 110,
        'production_integration_enabled': False, 'model_requests': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
