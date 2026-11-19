"""Read-only, versioned 70-component issue coverage and stage reconciliation."""
from collections import Counter
import json
from pathlib import Path
from analyze_coverage import collect,read,write_once,hashed,dom_kind
from summarize_general_repairs_v3 import family,dimension
from reproject_conditional_branches_v4 import verify

ROOT=Path(__file__).resolve().parent
REPLAY=ROOT/'general_repairs_v5_computed_options_complete_20261119'
OUT=ROOT/'general_repairs_v5_review_20261119'
PROJECT=ROOT.parent/'migration_system'


def repair_route(code):
    group=family(code)
    if group=='语法／外层与内联模板':route='真实属性级解析；仅源匹配的 class／循环／修饰符／模板路径修复'
    elif code.startswith('source_dynamic'):route='普通声明状态键＋完整内部 caller 证明；保留未知键、捕获、owner 和时序拒绝'
    elif group=='响应式／computed／数据访问':route='源 getter／读取依赖及写回校验；完整源匹配和已有纯 helper 的有界规则'
    elif group=='默认值／初始化／组件选项':route='源默认值／内联注册／选项形状与启动顺序校验；不覆盖未知工厂或副作用'
    elif group=='事件／参数／原生行为':route='源参数、payload、self／stop／prevent、原生拖拽及 owner 映射校验'
    elif group=='模板／渲染 DOM／控件':route='真实 AST／DOM／live 控件分开取证；只纠正有证明的表示误报，不删除真实差异'
    else:route='按源语义／首个运行异常的可定位证据进入紧凑模型修复，不按类别名直接放行'
    return {'bounded_rule_route':route,'when_proof_missing':'保留失败；当前接受代码＋定位差异＋相关 SSM 交给模型；本次离线未调用模型',
            'acceptance':'语法、静态、真实浏览器及原候选回退门全部复测；不降低阈值'}


def main():
    verify(REPLAY)
    rows,details,frozen,_,_=collect();results=read(REPLAY/'results.json');by_key={r['run_key']:r for r in results}
    if len(results)!=72 or len(by_key)!=72:raise ValueError('incomplete_or_duplicate_result')
    final_groups=read(ROOT/'analysis_70_v1_v2_20261119/error_groups.json')
    # Include intermediate/rejected attempts too, not only final-parent errors.
    ever_codes=sorted({c for row in rows for c in row['ever_evaluated_codes']})
    groups=[{'code':code,'runs':[{'run_key':r['run_key'],'historical_final_presence':code in r['final_diagnostic_codes']}
             for r in rows if code in r['ever_evaluated_codes']]} for code in ever_codes];coverage=[]
    for group in groups:
        code=group['code'];observations=[]
        for item in group['runs']:
            r=by_key[item['run_key']];a=r.get('effective_assessment',{});codes={d['code'] for d in a.get('diagnostics',[])}
            blocked=not a or a.get('blocked') or a.get('syntax',{}).get('status')=='fail' and 'syntax' not in code
            status='not_observed_due_to_prior_block' if blocked else 'still_reported' if code in codes else 'not_reported_under_current_checks'
            observations.append({'run_key':r['run_key'],'status':status,'historical_final_presence':item['historical_final_presence'],
                                 'relevant_dimension':a.get('dimensions',{}).get(dimension(code)),
                                 'whole_record_passed':r.get('passed') is True})
        coverage.append({'code':code,'family':family(code),'historical_records':len(observations),'generic_handling':repair_route(code),
                         'counts':dict(Counter(x['status'] for x in observations)),'observations':observations})
    remaining=[]
    for r in results:
        if r.get('passed'):continue
        a=r.get('effective_assessment',{});codes=sorted({d['code'] for d in a.get('diagnostics',[])})
        remaining.append({'run_key':r['run_key'],'component':r['component'],'batch':r['batch'],'status':r['status'],
            'dimensions':a.get('dimensions',{}),'codes':codes,'source_hash':details[r['run_key']]['sample']['vue_sha256'],
            'dom_difference_classes':dict(Counter(dom_kind(d) for d in a.get('dom_differences',[]))),
            'gate_decisions':r['rule_decisions'],'assessment_reference':(REPLAY/r['batch']/details[r['run_key']]['sample']['slug']/'result.json').relative_to(ROOT).as_posix(),
            'next_action':'new_complete_model_generation_required' if not a else 'retain_failure_target_the_reported_source_bound_contract'})
    stages={}
    for stage in ('compile_runtime','static','structure','visual','source_baseline','interaction'):
        stages[stage]={'historical':dict(Counter((details[r['run_key']]['report'].get('assessment') or {}).get('dimensions',{}).get(stage,'no_accepted_assessment') for r in results)),
                       'current':dict(Counter(r.get('effective_assessment',{}).get('dimensions',{}).get(stage,'no_accepted_assessment') for r in results))}
    batches={batch:{'records':sum(r['batch']==batch for r in results),
                    'historical_passed':sum(r['historical_passed'] for r in results if r['batch']==batch),
                    'offline_current_passed':sum(r.get('passed',False) for r in results if r['batch']==batch)} for batch in sorted({r['batch'] for r in results})}
    tests=read(PROJECT/'docs/verification/2026-11-19_general_repairs_v1/test-results-computed_v5.json')
    if not tests['successful']:raise ValueError('tests_not_successful')
    standalone=read(PROJECT/'var/refactor-verification/general_repairs_v5_20261119.json')
    protocol=read(REPLAY/'protocol.json')
    if standalone['status']!='standalone_verified' or any(standalone['implementation_sha256'].get(k)!=v for k,v in protocol['implementation_sha256'].items()):
        raise ValueError('standalone_or_runtime_version_not_matched')
    if tests['implementation_sha256']!=protocol['implementation_sha256']:raise ValueError('tests_do_not_match_replay_implementation')
    write_once(PROJECT/'docs/verification/2026-11-19_general_repairs_v1/standalone-v5.json',standalone)
    # Retain the exact implementation, not hashes alone. No credentials,
    # runtime database settings, environment files or private keys are copied.
    for name,expected in protocol['implementation_sha256'].items():
        file=PROJECT/name
        if hashed(file)!=expected:raise ValueError('current_implementation_changed:'+name)
        write_once(OUT/'implementation'/name,file.read_bytes().decode('utf-8'))
    for name,expected in tests['modules'].items():
        file=PROJECT/'tests'/(name+'.py')
        if hashed(file)!=expected:raise ValueError('test_implementation_changed:'+name)
        write_once(OUT/'implementation/tests'/(name+'.py'),file.read_bytes().decode('utf-8'))
    report={**read(REPLAY/'summary.json'),'new_generation_pass_rate':None,'historical_diagnostic_categories':len(coverage),
            'historical_final_parent_categories':len(final_groups),
            'historical_stop_reasons':dict(Counter(r['stop_reason'] for r in rows)),
            'historical_exact_noop_candidates':sum(len(r['no_op_candidates']) for r in rows),
            'remaining_records':len(remaining),'stage_counts_records_not_homogeneous_pass_rates':stages,'batches':batches,
            'regression_tests':tests['tests_run'],'regression_tests_passed':tests['successful'],
            'standalone_verified':True,
            'new_diagnostic_categories':sorted({d['code'] for r in results for d in r.get('effective_assessment',{}).get('diagnostics',[])}-{g['code'] for g in groups}),
            'historical_pass_now_failed':[r['run_key'] for r in results if r['historical_passed'] and not r.get('passed')],
            'validation20_and_test10_run':False,'runtime_and_frozen_evidence_unchanged_during_replay':True}
    write_once(OUT/'summary.json',report);write_once(OUT/'coverage.json',coverage);write_once(OUT/'remaining.json',remaining)
    lines=['# 70 组件通用修复：最新工程与冻结产物复核','',
        '本报告核对全部 70 个不同组件的 72 条历史记录。两个重复组件保留各版本，不拼成统一的新实验通过率。',
        '这是已有模型产物的开发复核；新的真实模型调用为 0。源码、模型响应、旧报告和数据库记录未被改写。','',
        '## 当前已验证结果','',
        f'- 当前冻结产物通过 {report["effective_passed"]} 条，历史通过 {report["historical_passed"]} 条；仍有 {len(remaining)} 条未通过／无完整产物。',
        f'- 本次追加规则候选 {report["changed"]} 条，接受 {report["accepted"]} 条、拒绝 {report["rejected"]} 条；退步候选仍回退。',
        f'- {tests["tests_run"]} 项关联回归通过，真实模型调用 0。工程测试使用的注入模型客户端不是迁移成功证据。',
        '- **尚未全部修复，不能据此保证下一轮新生成通过率。** 交互未配置仍是 not_run；验证集 20 项、测试集 10 项未运行。','',
        '## 各阶段记录数量','',
        '以下按 72 条记录计数；历史模型预算／版本并不统一，因此不是同协议通过率比较。','',
        '| 阶段 | 历史记录状态 | 当前离线状态 |','| --- | --- | --- |']
    for stage,v in stages.items():lines.append('| '+stage+' | '+json.dumps(v['historical'],ensure_ascii=False)+' | '+json.dumps(v['current'],ensure_ascii=False)+' |')
    lines+=['','## 保留的批次边界','','| 批次 | 条数 | 历史通过 | 当前离线通过 |','| --- | ---: | ---: | ---: |']
    for batch,v in batches.items():lines.append(f'| {batch} | {v["records"]} | {v["historical_passed"]} | {v["offline_current_passed"]} |')
    lines+=['','## 全部历史问题类别覆盖','',
        f'涵盖所有修复轮次／拒绝候选中的 {len(coverage)} 类诊断，而不只是最终父版本的 {len(final_groups)} 类。',
        '“当前未报告”可能是历史已经解决，不都归功于本轮修复；逐条保留历史最终是否仍报告。它也不等于记录整体通过。前置阻断不可观测的检查单列。','',
        '| 诊断 | 原记录 | 仍出现 | 当前未报告 | 前置阻断未观测 |','| --- | ---: | ---: | ---: | ---: |']
    for c in coverage:
        n=c['counts'];lines.append(f'| `{c["code"]}` | {c["historical_records"]} | {n.get("still_reported",0)} | {n.get("not_reported_under_current_checks",0)} | {n.get("not_observed_due_to_prior_block",0)} |')
    lines+=['','## 通用性与仍未完成的闭环','',
        '规则按源码 AST 形状、注册关系、完整调用体和字段证明匹配，不以组件名或业务方法名分支。生成仍为完整 SSM＋模型；有界规则只修复当前生成代码。',
        '模板条件分支投影纠正、工厂字符串误报纠正属于评估器修复；真实缺失文本／节点、控件值／属性、事件参数／初始化与 computed 遗漏仍保留失败。',
        '新增 source_computed_option_not_landed 检查会揭示以前漏报的普通方法／字段误映射；只对完整函数体与源 getter 翻译相同、无未知捕获／写入／方法调用者的候选自动搬迁。未证明的行为进入模型修复，不能直接放行。',
        '内联数组 props 和纯字面量 data 工厂必须与源定义匹配才改写；已有 initData、默认值冲突、未知代码和歧义注册不覆盖。',
        'DOM value／checked 属性差异仍严格保留；未将同一时刻 live value 相同当作属性契约等价，也未接入失败的 attr-value 候选。',
        '复杂子组件、未知动态键／捕获、source/target caller 不一致、真实结构／控件缺失仍需后续有界规则与模型修复验证，详见 [逐记录遗留](remaining.json)。','',
        '## 原始证据与下一步','',
        '[本轮重放](../general_repairs_v5_computed_options_complete_20261119/summary.json) · [72 条详情](../general_repairs_v5_computed_options_complete_20261119/results.json) · [覆盖矩阵](coverage.json)',
        '重放协议固定实现指纹。改变代码的候选用真实浏览器重新捕获；未改变代码的 DOM／像素复用已核验的同源同目标捕获，并重新执行解析、静态检查，不伪称全新运行。',
        '需要 API／Worker 使用同一新代码重启后，另立不可变新批次再检验模型生成效果；旧失败和成本不得重写。无需再次初始化云数据库。','']
    write_once(OUT/'REPORT.md','\n'.join(lines))
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'python3','display_name':'Python 3'}},'cells':[
        {'cell_type':'markdown','metadata':{},'source':['# 70 组件通用修复 v5\n','读取不可变开发重放；不是新生成／独立测试通过率。所有原始失败和费用保留。\n']},
        {'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':[
            'import json\n','from pathlib import Path\n',
            'root = next(p for p in (Path.cwd(), *Path.cwd().parents) if (p / "experiment_runs").is_dir())\n',
            'folder = root / "experiment_runs/general_repairs_v5_review_20261119"\n',
            'summary = json.loads((folder / "summary.json").read_bytes())\n',
            'assert summary["model_calls"] == 0 and summary["new_generation_pass_rate"] is None\n',
            'print(json.dumps(summary, ensure_ascii=False, indent=2))\n']},
        {'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':[
            'for row in json.loads((folder / "coverage.json").read_bytes()):\n','    print(row["code"], row["counts"])\n']},
        {'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':[
            'for row in json.loads((folder / "remaining.json").read_bytes()):\n','    print(row["run_key"], row["dimensions"], row["codes"])\n']} ]}
    write_once(OUT/'analysis.ipynb',notebook)
    if frozen!=collect()[2]:raise ValueError('historical_evidence_changed')
    hashes={p.relative_to(OUT).as_posix():hashed(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    write_once(OUT/'SHA256SUMS.txt',''.join(v+'  '+k+'\n' for k,v in hashes.items()))
    print(json.dumps({k:v for k,v in report.items() if k not in ('stage_counts_records_not_homogeneous_pass_rates','batches')},ensure_ascii=True))


if __name__=='__main__':main()
