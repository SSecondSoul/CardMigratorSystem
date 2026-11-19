"""Summarize verified OFFLINE replays; never manufacture a new model pass rate."""
from collections import Counter
import json
from pathlib import Path

from analyze_coverage import read,write_once,hashed

ROOT=Path(__file__).resolve().parent
REPLAY=ROOT/'general_repairs_v3_final_replay_20261119'
OUT=ROOT/'general_repairs_v3_review_20261119'


def family(code):
    if 'syntax' in code or code=='duplicate_class_attribute':return '语法／外层与内联模板'
    if any(p in code for p in ('rendered_','dom_','template_structure')):return '模板／渲染 DOM／控件'
    if code.startswith('source_dynamic'):return '内部动态赋值契约'
    if any(p in code for p in ('prop','initial','lifecycle','watch','vue_methods','vue_props','init_data')):return '默认值／初始化／组件选项'
    if any(p in code for p in ('computed','reactive','mutation','render_dependency','vue_this','array_access','data_store','template_math')):return '响应式／computed／数据访问'
    if any(p in code for p in ('event','handler','binding')):return '事件／参数／原生行为'
    return '样式或其他源语义契约'


def dimension(code):
    if family(code)=='模板／渲染 DOM／控件':return 'structure'
    if code=='target_browser_error':return 'compile_runtime'
    return 'static'


def main():
    for line in (REPLAY/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected,name=line.split('  ',1)
        if hashed(REPLAY/name)!=expected:raise ValueError('replay_hash_changed:'+name)
    results=read(REPLAY/'results.json');summary=read(REPLAY/'summary.json')
    if len(results)!=72 or summary['records']!=72:raise ValueError('incomplete_replay')
    groups=read(ROOT/'analysis_70_v1_v2_20261119/error_groups.json')
    by_key={r['run_key']:r for r in results};coverage=[]
    for group in groups:
        code=group['code'];entries=[]
        for item in group['runs']:
            r=by_key[item['run_key']];after=r.get('current_after',{});seen={d['code'] for d in after.get('diagnostics',[])}
            deferred=after.get('syntax',{}).get('status')=='fail' and 'syntax' not in code
            status=('unobserved_due_to_block_or_deferred_check' if deferred or after.get('blocked') or after.get('dimensions',{}).get(dimension(code),'not_run')=='not_run'
                    else 'still_reported' if code in seen else 'absent_after_retest')
            entries.append({'run_key':r['run_key'],'diagnostic_status':status,
                'relevant_dimension':after.get('dimensions',{}).get(dimension(code)),
                'whole_sample_passed':after.get('passed') is True})
        coverage.append({'code':code,'family':family(code),'historical_affected_runs':len(entries),
            'observations':dict(Counter(e['diagnostic_status'] for e in entries)),
            'interpretation':'diagnostic_presence_not_independent_defect_or_new_generation_success',
            'runs':entries})
    regressions=[r['run_key'] for r in results if r.get('historical_passed') and r.get('current_after',{}).get('passed') is not True]
    newly_passed=[r['run_key'] for r in results if r.get('historical_passed') is False and r.get('current_after',{}).get('passed') is True]
    unresolved=[]
    for r in results:
        a=r.get('current_after',{})
        if a.get('passed') is not True:
            unresolved.append({'run_key':r['run_key'],'source_sha256':r.get('source_sha256'),
                'replay_status':r['status'],'blocked':a.get('blocked'),
                'dimensions':a.get('dimensions'), 'codes':sorted({d['code'] for d in a.get('diagnostics',[])}),
                'repair_targets':r.get('repair_targets',[]),
                'action':'requires_new_generation' if r['status'].startswith('no_accepted') else 'keep_failure_and_use_source_bound_rules_or_focused_model_repair'})
    report={'scope':summary['scope'],'unique_components':70,'run_records':72,'real_model_calls':0,
        'historical_passed_records':sum(r.get('historical_passed') is True for r in results),
        'offline_passed_records':summary['current_after_pass'],'newly_passed_historical_records':newly_passed,
        'previous_pass_not_reproduced':regressions,'rules_changed_records':summary['changed'],
        'replay_errors':[r['run_key'] for r in results if r['status']=='replay_error'],
        'new_generation_pass_rate':None,'all_problem_categories_considered':len(coverage),
        'all_problem_instances_fixed':not unresolved,'remaining_records':len(unresolved),
        'source_integrity':summary['frozen_integrity_unchanged']}
    write_once(OUT/'summary.json',report);write_once(OUT/'coverage.json',coverage);write_once(OUT/'remaining.json',unresolved)
    lines=['# 通用修复 v3：冻结产物离线重放复核','',
        '这是已有产物的开发重放，不是 70 项新生成实验，不合并 v1／v2 的通过率。真实模型调用为 **0**。','',
        f'- 覆盖 70 个不同组件、72 条运行记录、{len(coverage)} 类历史诊断。',
        f'- 当前离线通过 {summary["current_after_pass"]} 条；规则实际修改 {summary["changed"]} 条；遗留 {len(unresolved)} 条。',
        f'- {len(newly_passed)} 条历史未通过记录在当前检查通过；{len(regressions)} 条历史通过记录未复现通过（逐项保留，不删样本）。',
        f'- 原始冻结文件完整性：{summary["frozen_integrity_unchanged"]}；实现重放期间未变动：{summary["implementation_unchanged"]}。','',
        '## 全部历史诊断类别覆盖','',
        '“未再出现”只描述这次重测中的该诊断，不表示其他维度／全部交互／任意输入等价。', '',
        '| 诊断 | 原记录 | 仍出现 | 未再出现 | 因前置阻断未观测 |',
        '| --- | ---: | ---: | ---: | ---: |']
    for g in coverage:
        c=g['observations'];lines.append(f'| `{g["code"]}` | {g["historical_affected_runs"]} | {c.get("still_reported",0)} | {c.get("absent_after_retest",0)} | {c.get("unobserved_due_to_block_or_deferred_check",0)} |')
    lines+=['','## 遗留项与下一步','',
        '详见 [逐记录遗留清单](remaining.json)。DOM value 属性、真实缺失节点／文字／控件、未知动态键，以及内联 Vue 语法等仍失败的情况不放行。',
        '先完成必要的通用规则／证明修订与反例验证；重启当前云库配置的 API／Worker 后，再冻结新批次做真实模型实验。不要恢复旧实现检查点或直接提高预算。','',
        '## 原始证据','',
        '[重放摘要](../general_repairs_v3_final_replay_20261119/summary.json) · [72 条原始重放记录](../general_repairs_v3_final_replay_20261119/results.json) · [覆盖矩阵](coverage.json)',
        '','自动通过仍只代表已配置 props／检查场景；本批未配置的交互和人工确认不能由离线结果代替。','']
    write_once(OUT/'REPORT.md','\n'.join(lines))
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'python3','display_name':'Python 3'}},'cells':[
        {'cell_type':'markdown','metadata':{},'source':['# 通用修复 v3 离线验证\n','只读报告分析，零模型调用；不代表全新生成通过率。\n']},
        {'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':[
            'import json\n','from pathlib import Path\n',
            'root = next(p for p in (Path.cwd(), *Path.cwd().parents) if (p / "experiment_runs").is_dir())\n',
            'folder = root / "experiment_runs/general_repairs_v3_review_20261119"\n',
            'summary = json.loads((folder / "summary.json").read_bytes())\n',
            'assert summary["real_model_calls"] == 0 and summary["new_generation_pass_rate"] is None\n',
            'print(json.dumps(summary, ensure_ascii=False, indent=2))\n']},
        {'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':[
            'coverage = json.loads((folder / "coverage.json").read_bytes())\n',
            'for row in coverage:\n','    print(row["code"], row["observations"])\n']},
        {'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':[
            'remaining = json.loads((folder / "remaining.json").read_bytes())\n',
            'for row in remaining:\n','    print(row["run_key"], row["blocked"], row["codes"])\n']} ]}
    write_once(OUT/'analysis.ipynb',notebook)
    hashes={p.relative_to(OUT).as_posix():hashed(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    write_once(OUT/'SHA256SUMS.txt',''.join(v+'  '+k+'\n' for k,v in hashes.items()))
    print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__':main()
