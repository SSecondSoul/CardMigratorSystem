"""Frozen, paired diagnosis. Never imports model/DB or changes task evidence."""
from collections import Counter, defaultdict
from pathlib import Path
import json
from analyze_coverage import BATCHES, RUNS, collect, read, write_once, hashed

LATEST = 'real_system_experiment70_v3_general_repairs_20261119'
OUTPUT = RUNS / 'analysis_v3_vs_first70_20261119'


def trajectory(detail):
    artifacts = detail['folder'] / 'artifacts'
    revisions = {int(p.stem): read(p) for p in (artifacts / 'revisions').glob('*.json')}
    values = []
    for p in sorted((artifacts / 'evaluations').glob('*.json'), key=lambda p: int(p.stem)):
        a = read(p); n = int(p.stem)
        values.append({'revision': n, 'origin': revisions.get(n, {}).get('origin'),
                      'sha256': a.get('revision_sha256'), 'passed': a.get('passed'),
                      'dimensions': a.get('dimensions'),
                      'codes': dict(Counter(d['code'] for d in a.get('diagnostics', []))),
                      'dom_similarity': a.get('dom_ted', {}).get('similarity'),
                      'ui_restoration': a.get('ui_restoration')})
    return values


def main():
    rows, details, frozen, stats, protocols = collect(batches=(*BATCHES, LATEST))
    old = {r['sample_id']: r for r in rows if r['batch'] in (BATCHES[0], BATCHES[2])}
    new = [r for r in rows if r['batch'] == LATEST]
    assert len(old) == len(new) == 70
    pairs, diagnostics, dom, decisions = [], [], [], []
    for row in new:
        previous = old[row['sample_id']]
        if row['source_sha256'] != previous['source_sha256']:
            raise ValueError('paired_source_drift')
        a = details[row['run_key']]['report'].get('assessment') or {}
        pair = {'component': row['component'], 'complexity': row['complexity'],
                'old': previous, 'new': row,
                'transition': ('pass' if previous['passed'] else 'fail') + '_to_' + ('pass' if row['passed'] else 'fail'),
                'trajectory': trajectory(details[row['run_key']])}
        pairs.append(pair)
        for d in a.get('diagnostics', []):
            diagnostics.append({'component': row['component'], 'report': row['report'], **d})
        dom.extend({'component': row['component'], **d} for d in a.get('raw_dom_differences', []))
        decisions.extend({'component': row['component'], **d} for d in row['decisions'])
    counts = Counter(d['code'] for d in diagnostics)
    # Overlapping categories, not independent human defects or waiver decisions.
    attr_only = [p['component'] for p in pairs if p['new']['final_diagnostic_codes'] == ['rendered_dom_mismatch']]
    transition = Counter(p['transition'] for p in pairs)
    summary = {'scope': 'paired_development_runs_different_versions_not_independent_test',
               'historical_evidence_files_verified': len(frozen), 'components': 70,
               'latest_passed': sum(r['passed'] for r in new),
               'latest_unknown_calls': sum(r['unknown_calls'] for r in new),
               'latest_known_tokens': sum(r['known_tokens'] for r in new),
               'paired_transitions': dict(transition), 'batches': stats,
               'lost_passes': [p['component'] for p in pairs if p['transition'] == 'pass_to_fail'],
               'new_passes': [p['component'] for p in pairs if p['transition'] == 'fail_to_pass'],
               'only_dom_diagnostic': attr_only,
               'final_diagnostic_instances': dict(counts.most_common()),
               'candidate_decisions': dict(Counter(d['reason'] for d in decisions)),
               'candidate_regression_added_codes': dict(Counter(c for d in decisions for c in d.get('added_errors', []))),
               'candidate_regression_dimensions': dict(Counter(c for d in decisions for c in d.get('dimensions', []))),
               'no_op_candidates': sum(len(r['no_op_candidates']) for r in new),
               'initial_passes': sum(r['initial_passed'] is True for r in new),
               'fresh_model_calls_by_this_analysis': 0}
    lines = ['# v3 与首轮 70 项逐项对照', '',
             '同源配对；首轮由 v1 的 49 项与 v2 补充 21 项组成，配置不完全相同，不能称单版本基线。v2 两项复跑单独保留。', '',
             f'新一轮真实生成：{summary["latest_passed"]}/70；未知调用 {summary["latest_unknown_calls"]} 次，已知 Tokens 不包含未知用量。', '',
             '配对变化：' + json.dumps(dict(transition), ensure_ascii=False), '',
             '此前通过本轮未通过：' + '、'.join(summary['lost_passes']), '',
             '此前未通过本轮通过：' + '、'.join(summary['new_passes']), '',
             '以下为重叠检查发现，不能当成人工独立缺陷数；DOM 属性差异尚未因此获准忽略。', '',
             *[f'- {code}: {n}' for code, n in counts.most_common()], '',
             '原始失败、候选回退、全部轮次见 pairs.json / diagnostics.json / decisions.json。未调用模型或数据库；未改历史报告。']
    for name, value in {'summary.json': summary, 'pairs.json': pairs, 'diagnostics.json': diagnostics,
                        'dom_differences.json': dom, 'decisions.json': decisions,
                        'input_sha256.json': frozen, 'REPORT.md': '\n'.join(lines) + '\n'}.items():
        write_once(OUTPUT / name, value)
    write_once(OUTPUT / 'analysis.ipynb', {'nbformat': 4, 'nbformat_minor': 5, 'metadata': {}, 'cells': [
        {'cell_type': 'markdown', 'metadata': {}, 'source': lines},
        {'cell_type': 'code', 'execution_count': None, 'metadata': {}, 'outputs': [],
         'source': ['import json\n', 'from pathlib import Path\n', "summary = json.loads(Path('summary.json').read_text(encoding='utf-8'))\n", 'summary']}]})
    write_once(OUTPUT / 'SHA256SUMS.txt', ''.join(hashed(p)+'  '+p.relative_to(OUTPUT).as_posix()+'\n'
               for p in sorted(OUTPUT.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS.txt'))
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == '__main__': main()
