"""Read-only evidence analysis across versioned runs, never a merged pass rate.

Reads local frozen reports only. No database, worker, model or migration engine
imports; all generated analysis lives in a separate immutable output directory.
"""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / 'experiment_runs'
BATCHES = (
    'real_system_experiment70_v1_20261118',
    'real_system_experiment70_v2_generation_probe_20261118',
    'real_system_experiment70_v2_remaining21_20261119',
)
OUTPUT = RUNS / 'analysis_70_v1_v2_20261119'
TERMINAL = {'finished', 'failed', 'blocked', 'review_required', 'cancelled'}


def read(path):
    return json.loads(path.read_bytes())


def hashed(path):
    return sha256(path.read_bytes()).hexdigest()


def inside(path, root):
    path = path.resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('evidence_path_escapes_root')
    return path


def write_once(path, value):
    data = value.encode('utf-8') if isinstance(value, str) else (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(data)
    except FileExistsError:
        if path.read_bytes() != data:
            raise ValueError('analysis_output_differs_create_new_analysis_version:' + path.name)


def diagnostic_family(code):
    if code.startswith('target_') and 'syntax' in code:
        return '语法与定位'
    if code in {'style_capacity_exceeded', 'dom_node_limit', 'source_baseline_blocked'}:
        return '评估容量或源页环境待审'
    if code.startswith('model_') or code.startswith('provider_'):
        return '模型响应或用量边界'
    if code.startswith('source_') and code.endswith(('unproven', 'not_landed')):
        return '源语义契约未证明'
    if any(word in code for word in ('dom_', 'control_', 'template_structure')):
        return '结构与控件'
    if code in {'target_browser_error', 'missing_prop_defaults', 'missing_prop_dependent_initialization'}:
        return '初始化与运行时'
    return '静态语义或响应式'


def dom_kind(diff):
    expected, actual = diff.get('expected'), diff.get('actual')
    if expected is None or actual is None:
        return '节点或文本缺失新增'
    if str(expected).startswith('#text:') or str(actual).startswith('#text:'):
        return '文本内容变化'
    if str(expected).split('|', 1)[0] != str(actual).split('|', 1)[0]:
        return '元素标签变化'
    return '属性或序列化变化_尚未获准忽略'


def same_v2_protocol(first, second):
    return all(first[k] == second[k] for k in (
        'binding', 'runtime_profile', 'strategy', 'max_repair_rounds', 'props', 'actions', 'thresholds'))


def analyze_record(batch_name, sample, report, artifacts):
    assessment = report.get('assessment') or {}
    evaluations = [(int(p.stem), read(p)) for p in sorted((artifacts / 'evaluations').glob('*.json'))]
    revisions = [read(p) for p in sorted((artifacts / 'revisions').glob('*.json'))]
    revisions.sort(key=lambda value: value['number'])
    latest = revisions[-1] if revisions else None
    calls = []
    for folder in sorted((artifacts / 'calls').glob('*')):
        if not (folder / 'receipt.json').is_file():
            continue
        receipt = read(folder / 'receipt.json')
        response = read(folder / 'response.json')
        choices = response.get('choices') or [{}]
        calls.append({'ordinal': int(folder.name), 'error': receipt.get('error'),
                      'finish_reason': choices[0].get('finish_reason'), 'usage': receipt.get('usage')})
    # An unknown transport outcome is NOT a zero-token successful response.
    # Only a durably declared unknown call can explain a missing receipt.
    missing_receipts = report['model_calls_started'] - len(calls)
    if missing_receipts != report.get('unknown_calls', 0) or missing_receipts < 0:
        raise ValueError('call_receipts_not_complete:' + sample['id'])
    if missing_receipts and report['usage']['complete']:
        raise ValueError('unknown_call_cannot_have_complete_usage:' + sample['id'])
    if sum((call['usage'] or {}).get('total_tokens', 0) for call in calls) != report['usage']['known_total_tokens']:
        raise ValueError('usage_total_differs:' + sample['id'])
    decisions = report.get('state', {}).get('decisions', [])
    noop = [rev for rev in revisions if rev.get('parent') and rev['parent'] == rev['file']['sha256']]
    final_codes = sorted({item['code'] for item in assessment.get('diagnostics', [])})
    all_codes = sorted({item['code'] for _, value in evaluations for item in value.get('diagnostics', [])})
    return {
        'run_key': batch_name + '/' + sample['id'], 'batch': batch_name,
        'sample_id': sample['id'], 'component': sample['component_name'], 'complexity': sample['complexity'],
        'source_sha256': sample['vue_sha256'], 'migration_id': report['migration_id'],
        'status': report['status'], 'stop_reason': report['stop_reason'],
        'passed': report['status'] == 'finished' and assessment.get('passed') is True,
        'model_calls': report['model_calls_started'], 'known_tokens': report['usage']['known_total_tokens'],
        'unknown_calls': report['unknown_calls'], 'usage_complete': report['usage']['complete'],
        'dimensions': assessment.get('dimensions', {}), 'final_diagnostic_codes': final_codes,
        'ever_evaluated_codes': all_codes, 'round': report.get('state', {}).get('round', 0),
        'initial_passed': dict(evaluations).get(0, {}).get('passed'), 'decisions': decisions,
        'no_op_candidates': [{'number': rev['number'], 'origin': rev['origin']} for rev in noop],
        'latest_revision': latest['number'] if latest else None,
        'latest_revision_evaluated': latest is not None and latest['number'] in dict(evaluations),
        'assessment_scope': 'last_accepted_parent_not_necessarily_latest_candidate',
        'assessment_revision_sha256': assessment.get('revision_sha256'),
        'latest_revision_sha256': latest['file']['sha256'] if latest else None,
        'calls': calls,
        'missing_receipts_unknown_outcome': missing_receipts,
        'report': f'{batch_name}/samples/{sample["slug"]}/report.json',
        'coverage_claim': 'configured_initial_checks_only_no_interaction_or_manual_acceptance',
    }


def collect(root=RUNS, batches=None):
    rows, details, snapshots, batch_stats, protocols = [], {}, {}, [], {}
    def verify(path, expected=None):
        actual = hashed(path)
        if expected is not None and actual != expected:
            raise ValueError('evidence_hash_mismatch:' + str(path))
        snapshots[path.relative_to(root).as_posix()] = actual
    for name in BATCHES if batches is None else batches:
        batch = root / name
        protocol, checkpoint, samples, summary = [read(batch / path) for path in (
            'protocol.json', 'checkpoint.json', 'samples.json', 'summary.json')]
        protocols[name] = protocol
        for path in ('protocol.json', 'checkpoint.json', 'samples.json', 'summary.json',
                     'dataset_manifest.json', 'implementation_sha256.json'):
            verify(batch / path)
        for relative, expected in read(batch / 'implementation_sha256.json').items():
            verify(inside(batch / relative, batch / 'implementation'), expected)
        current = []
        for sample in samples:
            verify(inside(batch / sample['frozen_vue'], batch / 'inputs'), sample['vue_sha256'])
            if sample['id'] not in checkpoint['results']:
                continue
            folder = batch / 'samples' / sample['slug']
            verify(folder / 'SHA256SUMS.txt')
            for line in (folder / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
                expected, relative = line.split('  ', 1)
                verify(inside(folder / relative, folder), expected)
            report = read(folder / 'report.json')
            if report['status'] not in TERMINAL:
                raise ValueError('non_terminal_export')
            row = analyze_record(name, sample, report, folder / 'artifacts')
            rows.append(row);current.append(row)
            details[row['run_key']] = {'report': report, 'folder': folder, 'sample': sample}
        if len(current) != summary['completed'] or sum(row['passed'] for row in current) != summary['passed']:
            raise ValueError('batch_summary_differs')
        if sum(row['model_calls'] for row in current) != summary['model_calls']:
            raise ValueError('batch_call_summary_differs')
        if sum(row['known_tokens'] for row in current) != summary['known_total_tokens']:
            raise ValueError('batch_usage_summary_differs')
        dimensions = defaultdict(Counter)
        for row in current:
            for dimension, status in row['dimensions'].items():
                dimensions[dimension][status] += 1
        batch_stats.append({
            'batch': name, 'configured': len(samples), 'completed': len(current),
            'pending': len(samples) - len(current), 'status': summary['run_status'],
            'passed': sum(row['passed'] for row in current),
            'not_passed': sum(not row['passed'] for row in current),
            'stop_reasons': dict(Counter(row['stop_reason'] for row in current)),
            'dimensions': {k: dict(v) for k, v in dimensions.items()},
        })
    return rows, details, snapshots, batch_stats, protocols


def aggregate(rows, details, batch_stats, protocols):
    components = defaultdict(list)
    groups, dom, contracts, baseline = {}, [], [], []
    for row in rows:
        components[row['sample_id']].append({key: row[key] for key in (
            'run_key', 'batch', 'component', 'complexity', 'source_sha256', 'migration_id',
            'passed', 'stop_reason', 'report')})
        report = details[row['run_key']]['report'];assessment = report.get('assessment') or {}
        for code in row['final_diagnostic_codes']:
            group = groups.setdefault(code, {'code': code, 'family': diagnostic_family(code), 'runs': []})
            group['runs'].append({'run_key': row['run_key'], 'sample_id': row['sample_id'], 'report': row['report']})
        for diagnostic in assessment.get('diagnostics', []):
            if diagnostic['code'] == 'rendered_dom_mismatch':
                for diff in diagnostic.get('differences', []):
                    dom.append({'run_key': row['run_key'], 'sample_id': row['sample_id'], 'kind': dom_kind(diff),
                                'difference': diff, 'policy': diagnostic.get('comparison_policy'),
                                'live_controls_equal': diagnostic.get('live_control_state', {}).get('equal'),
                                'report': row['report']})
            if diagnostic['code'] == 'source_dynamic_assignment_unproven':
                contracts.append({'run_key': row['run_key'], 'sample_id': row['sample_id'],
                                  'details': diagnostic.get('details', {}), 'report': row['report']})
        if row['stop_reason'] == 'source_baseline_blocked':
            folder = details[row['run_key']]['folder']
            for path in sorted((folder / 'artifacts/evaluations').glob('*/raw.json')):
                vue = read(path).get('browser', {}).get('vue', {})
                baseline.append({'run_key': row['run_key'], 'evidence': path.relative_to(RUNS).as_posix(),
                                 **{key: vue.get(key) for key in ('errors', 'warnings', 'blocked_requests', 'evidence_overflow')}})
    for sample_id, records in components.items():
        if len({item['source_sha256'] for item in records}) != 1:
            raise ValueError('repeated_component_source_drift:' + sample_id)
    for group in groups.values():
        group['affected_runs'] = len(group['runs'])
        group['affected_unique_components'] = len({row['sample_id'] for row in group['runs']})
        group['interpretation'] = 'overlapping_detector_findings_not_confirmed_independent_defect_counts'
    v2_match = same_v2_protocol(protocols[BATCHES[1]], protocols[BATCHES[2]])
    v2 = [row for row in rows if row['batch'] in BATCHES[1:]]
    v2_ids = {row['sample_id'] for row in v2}
    decisions = [decision for row in rows for decision in row['decisions']]
    summary = {
        'analysis_scope': 'cross_version_development_problem_coverage_not_single_version_pass_rate',
        'unique_components': len(components), 'terminal_run_records': len(rows),
        'repeated_components': {key: len(value) for key, value in components.items() if len(value) > 1},
        'combined_70_pass_rate': None,
        'model_calls': sum(row['model_calls'] for row in rows),
        'known_total_tokens': sum(row['known_tokens'] for row in rows),
        'unknown_calls': sum(row['unknown_calls'] for row in rows),
        'all_returned_usage_complete': all(row['usage_complete'] for row in rows),
        'batch_stats': batch_stats,
        'v2_complex_only': {'protocols_match': v2_match, 'distinct_components': len(v2_ids),
                            'records': len(v2), 'passed': sum(row['passed'] for row in v2),
                            'scope': 'v2_complex_23_development_checks_not_full_70_or_independent_test'},
        'initial_evaluations': sum(row['initial_passed'] is not None for row in rows),
        'initial_passed': sum(row['initial_passed'] is True for row in rows),
        'repair_decisions': len(decisions), 'accepted_candidates': sum(d['accepted'] for d in decisions),
        'decision_reasons': dict(Counter(d['reason'] for d in decisions)),
        'no_op_candidates': sum(len(row['no_op_candidates']) for row in rows),
        'dom_difference_rows': dict(Counter(item['kind'] for item in dom)),
        'interaction': 'not_run', 'manual_acceptance': 'not_run',
    }
    return summary, dict(components), sorted(groups.values(), key=lambda group: (-group['affected_runs'], group['code'])), dom, contracts, baseline


def backlog(groups, rows):
    by_code = {group['code']: group for group in groups}
    def item(priority, name, codes, tests, status='requires_source_bound_replay_not_a_blanket_waiver'):
        evidence = sorted({run['report'] for code in codes for run in by_code.get(code, {}).get('runs', [])})
        return {'priority': priority, 'name': name, 'detector_codes': codes, 'evidence_reports': evidence,
                'acceptance_tests': tests, 'status': status}
    return [
        item('P0', '模板属性级定位与源约束语法修复',
             ['target_sfc_syntax_error', 'target_template_syntax_error', 'target_script_syntax_error'],
             ['逐属性定位空事件和循环别名错误，不再只指向模板开头',
              '保留 dragover.prevent 与拖拽语义，不能靠删除事件通过',
              '重复 class 只在源匹配并保留全部条件时合并；反例必须拒绝',
              '共享关键生成／修复约束；冻结三轮候选重放；不只增加 Prompt']),
        item('P0', '评估容量与内嵌资源边界', [],
             ['超过300个元素的真实源页及San页均有完整或明确不完整的证据',
              '不能静默丢弃后续DOM／样式，也不能把超限改成通过',
              '审查 data:image/svg+xml 自包含资源误拦；外网／脚本／不可信内容仍阻断'],
             status='confirmed_style_limit_and_source_data_uri_observation_not_fixed'),
        item('P1', 'DOM差异按真实缺失与表示差异拆分',
             ['rendered_dom_mismatch', 'rendered_control_state_mismatch', 'template_structure_mismatch', 'dom_child_order_mismatch'],
             ['缺失节点、数字、默认数组、顺序变化仍失败',
              '空class、value属性先审查CSS／DOM观察及控件行为；未经证明不归一化',
              '优先恢复与源一致的目标表示，不能全局关闭DOM门']),
        item('P1', '默认值、内联子组件和初始化链',
             ['target_browser_error', 'missing_prop_defaults', 'missing_prop_dependent_initialization',
              'vue_methods_wrapper', 'missing_lifecycle_mapping', 'watch_registration_not_in_lifecycle'],
             ['初始数据、data prop、computed、生命周期与watch分别有正反例',
              '父组件与所有内联子组件共同验证，运行时错误不得由视觉分数抵消']),
        item('P1', '内部调用契约的证明与迁移缺陷分流',
             ['source_dynamic_assignment_unproven', 'source_computed_collection_not_landed',
              'source_filter_method_not_landed', 'source_record_update_not_landed'],
             ['28条动态赋值发现逐项核对拒绝原因，不按setValue名字放行',
              '验证内联setter／emit包装的有限等价识别与错误事件／时序反例',
              '保留用户已授权的内部普通data键范围，不扩展为任意公开键']),
        item('P2', '无效修复和预算反馈', [],
             ['无变化候选不算进步，下一轮必须反馈具体未解决属性与差异',
              'Tokens停止是边界，不因未修好直接扩大费用额度',
              '196次调用的实际收据核算；新版本完整70项另行冻结'],
             status='9_exact_no_op_candidates_observed_budget_stops_preserved'),
    ]


def render_report(summary, groups, rows, baseline):
    lines = ['# 70 个组件跨版本问题覆盖分析', '',
        '本报告保留三个批次及其重复任务，覆盖70个不同组件、72条终态记录。不是同一版本完整70项实验，不计算混合通过率；没有修改旧结论、重发模型调用或修改迁移实现。', '',
        '## 批次与范围', '', '| 批次 | 配置数 | 完成 | 通过 | 未通过／阻断 | 待运行 |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for stat in summary['batch_stats']:
        lines.append(f'| {stat["batch"]} | {stat["configured"]} | {stat["completed"]} | {stat["passed"]} | {stat["not_passed"]} | {stat["pending"]} |')
    lines += ['', 'v1 为未完成的49/70基线，后续21项没有补写到v1；MonitoringDashboard、TaskManager在v2重复运行，旧失败保留。两个v2批次的实现、模型、阈值、props及交互设置一致且样本不重复，合计23个复杂组件，1项通过；这一结果仍不是完整70项通过率。', '',
        f'实际模型调用 {summary["model_calls"]} 次；已知 Tokens {summary["known_total_tokens"]:,}。未知调用 {summary["unknown_calls"]} 次，返回用量完整。70次已执行初始评估均未直接通过；另两条v1输出截断任务没有初始评估。全部批次未配置代表性交互、未进行本轮人工验收。', '',
        '## 高频发现', '', '计数针对最后接受父版本的诊断，一个组件可涉及多类；不是独立缺陷数量，也不等于全部已确认误报。', '',
        '| 检测代码 | 涉及任务 | 不同组件 | 分流 |', '| --- | ---: | ---: | --- |']
    for group in groups[:12]:
        lines.append(f'| `{group["code"]}` | {group["affected_runs"]} | {group["affected_unique_components"]} | {group["family"]} |')
    lines += ['', '## 主要结论', '',
        '1. DOM差异49条任务：既有缺失节点、数值文本和错误子节点顺序，也有空class、value等属性差异。当前记录的差异行中，属性／序列化变化166行，缺失新增43行，文本变化12行，标签变化2行；这些是有界诊断行数，不是完整DOM编辑距离或独立缺陷数。不能把全部DOM失败当成评估误报，也不能只看视觉分数通过就放行。', '',
        '2. 动态赋值契约未证明28条：主要拒绝涉及完整caller不匹配、键调用次数不一致、非普通声明状态键和未知this归属。BookmarkToggleCard的toggle表面上是源setter／emit包装的内联版本，值得专门检查分析器的有限等价覆盖；但必须同时核对值、事件、调用顺序和初始化，不据此全局豁免，也不恢复任意公开键承诺。', '',
        '3. 初始化与运行时缺陷可独立解释部分失败：11条任务有target_browser_error，包含undefined.map、缺少initData、内联子组件保留Vue methods／props、data store被当数组等发现。它们与首次生成截断是不同问题，应按共同模式修复。', '',
        f'4. 修复并非完全没有效果：共{summary["repair_decisions"]}次候选门决策，接受{summary["accepted_candidates"]}次；严格改善不等于最终全维通过。检测到{summary["no_op_candidates"]}个与父版本哈希相同的候选，均应归入无效修复反馈；不能算作修复成功。', '',
        '5. MonitoringDashboard最新候选通过语法，但在浏览器样式采集的300元素记录上限中断，未产生该候选完整评估。报告仍显示旧接受父版本的重复class语法诊断，不能把它当作最新候选全部状态。第一次修复与原代码完全相同；第二次已解除语法错误，后续问题被评估容量遮挡。', '',
        '6. TaskManager三份候选都保留空 on-dragover 与括号式 s-for 别名错误。逐属性隔离可复现两个解析错误，原报告却定位到模板开头；两轮修复均无语法进展。最终142394 Tokens触发131072软停止线，是未修好之后的费用边界，不是首要缺陷。保持预算，不先增加额度。', '',
        '7. TripItineraryPlanner的源基准被阻断：冻结浏览器证据显示源页无errors／warnings，却被拦截一个data:image/svg+xml;base64资源。它不是远程URL；当前不能仅据source_baseline_blocked判定Vue业务源码有错。需要独立审查自包含资源与安全拦截策略，同时保留真实外网请求阻断。', '',
        '8. v2截断修正有效但不等于迁移成功：两个复跑的首次生成均正常stop，输出9130／9464 Tokens；输入Tokens分别从97198降到71385、89069降到64269（26.56%／27.84%）。这是同源不同输出预算与格式策略的观测，不能单独归因全部质量变化。', '',
        '## 修复顺序与验收', '',
        '先做P0属性级语法定位、源约束的通用修复以及评估容量／内嵌资源边界；再做P1 DOM分类、默认值与子组件初始化、语义契约证明；最后依据无效候选反馈调整调用策略。具体正反例与证据链接在prioritized_backlog.json。', '',
        '每组先对冻结产物离线重放；保留真实失败和不支持边界，不降低阈值、不删事件／节点来通过。随后新建小规模真实回归。确认通用修复后，另行冻结统一版本完整70项批次；validation／test继续不运行。LangSmith、训练及数据库部署不作为本轮缺陷的替代修复。', '',
        '## 可追溯文件', '',
        '- `runs.json`：72条任务，保留最后接受父版本、最新候选、诊断与停止原因。',
        '- `components.json`：70个组件到各版本任务的映射；不选最好结果替换旧结果。',
        '- `error_groups.json`、`dom_triage.json`、`contract_triage.json`：分组及原始证据定位。',
        '- `source_baseline_observations.json`：源页环境原始记录。',
        '- `source_integrity.json`：全部输入、实现快照、样本导出包与控制文件哈希；生成前后复核。',
        '- `analysis.ipynb`：仅加载上述真实数据，无伪造执行输出。', '']
    return '\n'.join(lines)


def notebook():
    def cell(kind, source):
        return {'cell_type': kind, 'metadata': {}, 'source': source.splitlines(True),
                **({'execution_count': None, 'outputs': []} if kind == 'code' else {})}
    return {'nbformat': 4, 'nbformat_minor': 5,
            'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}},
            'cells': [cell('markdown', '# 70个组件跨版本问题覆盖分析\n70个不同组件、72条任务；v1、v2分开，不计算混合通过率。全部数据来自冻结报告，本轮无新模型调用。\n'),
                      cell('code', "import json\nfrom pathlib import Path\nhere = Path.cwd().resolve()\nfor root in [here, *here.parents]:\n    folder = root / 'experiment_runs/analysis_70_v1_v2_20261119'\n    if (folder / 'summary.json').is_file():\n        break\nelse:\n    raise FileNotFoundError('Run inside this repository')\nload = lambda name: json.loads((folder / name).read_text(encoding='utf-8'))\nsummary = load('summary.json')\nsummary\n"),
                      cell('code', "groups = load('error_groups.json')\n[(g['code'], g['affected_runs'], g['affected_unique_components']) for g in groups]\n"),
                      cell('code', "backlog = load('prioritized_backlog.json')\n[(item['priority'], item['name'], item['acceptance_tests']) for item in backlog]\n"),
                      cell('markdown', '详细解释、边界与后续验收见 REPORT.md。发现数量有重叠；表示差异和契约未证明不自动认定为误报。旧原始结论不改写。\n')]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args();output = inside(args.output, RUNS)
    if output in [RUNS / name for name in BATCHES]:
        raise ValueError('cannot_overwrite_source_batch')
    rows, details, snapshots, batch_stats, protocols = collect()
    summary, components, groups, dom, contracts, baseline = aggregate(rows, details, batch_stats, protocols)
    expected = {item['id'] for item in read(ROOT / 'experiment_dataset/experiment/manifest.json')['samples']}
    if set(components) != expected or len(rows) != 72 or not summary['v2_complex_only']['protocols_match']:
        raise ValueError('coverage_or_v2_identity_differs')
    outputs = {'summary.json': summary, 'runs.json': rows, 'components.json': components,
               'error_groups.json': groups, 'dom_triage.json': dom, 'contract_triage.json': contracts,
               'source_baseline_observations.json': baseline, 'prioritized_backlog.json': backlog(groups, rows),
               'source_integrity.json': {'verified_file_count': len(snapshots), 'files': snapshots,
                                         'source_evidence_modified': False}, 'analysis.ipynb': notebook(),
               'REPORT.md': render_report(summary, groups, rows, baseline)}
    # Verify inputs did not change while analysis was computed.
    for relative, expected_hash in snapshots.items():
        if hashed(RUNS / relative) != expected_hash:
            raise ValueError('source_changed_during_analysis:' + relative)
    for name, value in outputs.items():
        write_once(output / name, value)
    write_once(output / 'SHA256SUMS.txt', ''.join(
        hashed(output / name) + '  ' + name + '\n' for name in sorted(outputs)))
    print(json.dumps({'output': str(output), 'unique_components': len(components), 'run_records': len(rows),
                      'verified_source_files': len(snapshots), 'model_calls_triggered': 0}, ensure_ascii=True))


if __name__ == '__main__':
    main()
