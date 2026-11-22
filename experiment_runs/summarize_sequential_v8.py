"""One-version v8 review, initial mixed batch comparison, complete residuals."""
from collections import Counter
from pathlib import Path
import json
import shutil

from analyze_coverage import read, write_once, hashed, RUNS

PROJECT=RUNS.parent/'migration_system'
REPLAY=RUNS/'composed_v8_final_replay_20261120'
OUTPUT=RUNS/'composed_v8_review_20261120'


def category(code):
    if code=='model_response_unknown_no_automatic_retry':return 'incomplete_model_output'
    if 'syntax' in code or 'duplicate_class' in code:return 'generation_syntax'
    if code in ('target_browser_error','source_data_initialization_phase_not_landed','missing_prop_defaults','vue_this_state','missing_init_data'):
        return 'generated_initialization_or_runtime'
    if any(s in code for s in ('dynamic_assignment','method_interface','event_arguments','lifecycle','watch','nested_state','reactive','render_dependency','record_','shared_record','computed','filter_method','event_handler','event_binding','custom_event','dom_event')):
        return 'generated_business_semantics_or_unproven_contract'
    if code.startswith(('rendered_','template_structure','dom_child','source_class')):return 'template_native_control_or_real_DOM'
    return 'other_preserved_diagnostic'


def main():
    rows=read(REPLAY/'results.json');summary=read(REPLAY/'summary.json')
    tests=read(PROJECT/'docs/verification/2026-11-19_general_repairs_v1/test-results-composed_v8_verified.json')
    protocol=read(REPLAY/'protocol.json')
    if len(rows)!=70 or summary['statuses'].get('replay_error'):raise ValueError('complete_replay_required')
    if not tests['successful'] or tests['implementation_sha256']!=protocol['implementation_sha256']:
        raise ValueError('passing_same_version_tests_required')
    standalone=read(PROJECT/'var/refactor-verification/composed_v8_20261120.json')
    # Keep original pair evidence rather than relabeling a mixed run as uniform.
    pairs=read(RUNS/'analysis_v3_vs_first70_20261119/pairs.json')
    comparison=[];remaining=[];codes=Counter();causes=Counter();failure_analysis=[]
    by_name={r['component']:r for r in rows}
    for pair in pairs:
        current=by_name[pair['component']]
        comparison.append({'component':pair['component'],'first_mixed_70':pair['old'],
            'real_v3':pair['new'],'v7_offline_passed':current.get('v7_effective_passed'),
            'v8_fresh_baseline_passed':current.get('fresh_baseline_passed'),
            'v8_offline_effective_passed':current['effective_passed'],
            'v8_result':str((REPLAY/current['sample_id']/'result.json').relative_to(RUNS))})
        if current['effective_passed']:continue
        residual=current.get('effective_codes') or ['model_response_unknown_no_automatic_retry']
        groups=sorted({category(c) for c in residual});causes.update(groups);codes.update(residual)
        remaining.append({'component':current['component'],'complexity':current.get('complexity'),
            'codes':residual,'cause_groups':groups,'steps':current.get('steps',[]),
            'effective_dimensions':current.get('effective_dimensions',{}),
            'evidence':str((REPLAY/current['sample_id']).relative_to(RUNS))})
        current_folder=REPLAY/current['sample_id']
        assessment_path=current_folder/'effective-assessment.json'
        actual=read(assessment_path) if assessment_path.exists() else {}
        failure_analysis.append({'component':current['component'],
            'first_mixed_codes':pair['old'].get('final_diagnostic_codes',[]),
            'real_v3_codes':pair['new'].get('final_diagnostic_codes',[]),
            'v8_actual_diagnostics':actual.get('diagnostics',[]),
            'source_method_contracts':actual.get('source_method_contracts',[]),
            'first_to_v3_transition':pair['transition'],
            'source_generation_or_proof_categories':groups,
            'candidate_decisions':[s['gate'] for s in current.get('steps',[])],
            'candidate_rule_stops':[s['normalization_stop'] for s in current.get('steps',[])],
            'all_proposals_have_real_retest':True,
            'effective_source_bound_code':str((current_folder/'effective.san').relative_to(RUNS)) if assessment_path.exists() else None,
            'not_fixed':True})
    residual_audit=[
        {'component':'AccessMatrix','origin':'new_initialization_recovery_and_gate_not_yet_composed',
         'observation':'The v8 source-pure initialization proposal restores runtime and removes initialization findings, but also contains a class reflection edit and reveals rendered_control_position_mismatch. The existing exact default-only recovery proof correctly does not authorize that combined candidate, so the parent is retained.',
         'next_general_fix':'Propose pure source-data initialization alone, bind its exact whole-code/source/props/actions/runtime proof, and admit only the existing control-diagnostic refinement family after real runtime/value/count/DOM progress. Other new defects and structure failures remain. Then apply independent template rules in a later proposal.'},
        {'component':'VolumeControl','origin':'legacy_validator_format_recognition',
         'observation':'The accepted parent has a valid quoted ObjectMethod "inited"(){...}; target syntax passes and the scoped setter caller proof includes inited. The legacy lifecycle presence regex requires an unquoted name followed immediately by an opening parenthesis.',
         'next_general_fix':'Use unambiguous exported-parent AST hook metadata for presence/body extraction; preserve missing/duplicate/child-only/changed-body negatives, not a component-name waiver.'},
        {'component':'SearchClearField','origin':'native_value_rule_whitespace_coverage',
         'observation':'Source :value=query and target {= query =} bind the same field, but the existing value reflection condition accepts only {=query=} without inner whitespace. Live value matches while the real empty value attribute is absent.',
         'next_general_fix':'Parse/normalize the binding expression, reflect the actual HTML attribute, and verify empty/input/clear/reset; do not drop attribute comparison.'},
        {'component':'FileDropIndicator','origin':'framework_class_serialization_not_source_logic',
         'observation':'Vue trims the source string class result; San interpolation retains a trailing space. Strict class observer policy remains unapproved because of dynamic source instance writes.',
         'next_general_fix':'Source-bound actual class serialization lowering with reactive/DOM observer tests, not a blanket token-equivalence waiver.'},
        {'component':'StatusSwitch','origin':'generated_extra_observable_attribute',
         'observation':'The San section has a literal aria-label that the source section does not declare. Both template and actual DOM comparison correctly retain this extra attribute difference.',
         'next_general_fix':'Source-matched native attribute restoration under complete template ownership and no spread/dynamic attribute uncertainty; do not ignore aria attributes.'}
    ]
    result={**summary,'test_count':tests['tests_run'],'real_v3_passed_unchanged':15,
        'first_mixed_70_passed':sum(bool(p['old']['passed']) for p in pairs),
        'remaining_count':len(remaining),'all_issues_resolved':not remaining,
        'remaining_components_by_cause_group':dict(causes),'remaining_codes_by_components':dict(codes),
        'standalone_report_sha256':hashed(PROJECT/'var/refactor-verification/composed_v8_20261120.json'),
        'standalone_report':standalone,
        'interpretation':'additional_development_on_existing_artifacts_NOT_fresh_generation_or_independent_test'}
    lines=['# 通用修复 v8：生产规则的顺序、初始化及原生控件闭环','',
        '2026-11-20。本轮只使用已有冻结源码与 San 产物、真实解析器和浏览器；无真实模型调用、云数据库访问、服务重启或新任务提交。','',
        '## 版本与结果','',
        f'- 首轮混合 70 项：{result["first_mixed_70_passed"]}/70；由 v1 的 49 项和 v2 补充 21 项构成，配置不同，不包装成统一单版本基线。',
        '- v3 真实模型批次仍为 15/70，本轮没有改写这个结果。',
        f'- 上一轮 v7 的有效离线结果 33/70；本轮对 69 份有完整代码的有效父版本重新静态检查和真实浏览器捕获，当前基线 {summary["fresh_baseline_passed"]}/70，顺序规则后 {summary["effective_passed"]}/70。TaskManager 无完整产物，不重试未知调用。',
        f'- 相对 v7 新增离线通过：{"、".join(summary["newly_passed_vs_v7"]) or "无"}；原通过当前未通过：{"、".join(summary["previously_passed_now_failed"]) or "无"}。',
        f'- 仍有 {len(remaining)} 项未闭合，不声称所有问题已彻底解决。关联回归 {tests["tests_run"]} 项在固定版本下通过；初始并行运行有一模块超时，保留原失败日志，再在回放结束后单独复测并合并同版证据，不伪装成首次全绿。独立副本验证另存。',
        f'- {summary["historical_files_verified_unchanged"]} 个历史文件及 {summary["v7_files_verified_unchanged"]} 个 v7 引用文件哈希不变。原始报告、失败和被拒候选均保留。','',
        '## 原因定位及修复链','',
        '1. 生成代码确有初始化时序缺陷，不是 Vue 非法：San computed 比 inited 更早。源 data 克隆 props 再派生选择状态，不能用 null 集合延迟到 inited。新规则只在纯源 getter／helper、完整初始化表达式及顺序可证明时恢复；保留 JSON 深克隆／浅克隆语义。未知副作用、created 合并、内置对象被重定义时拒绝，不随意给 getter 加 ||[]。',
        '2. 已有规则和候选门没有形成执行顺序闭环：缺省值恢复夹杂模板改动时，不满足既有整份代码窄证明。现在先提出完全默认值规则产物、真实复测和正常门禁，再对接受的版本继续通用规则；被拒则保留父版本，不重复同一提案。恢复运行不等于结构通过。',
        '3. 动态赋值证明缺跨方法参数流：不识别方法名，而是递归追踪所有真实 this 调用及模板入口，要求有限普通 data 键、全部上游调用体和完整模板实参匹配。未知外部键、逃逸、循环、自定义实例命名空间仍不证明。',
        '4. 原生 select 的 value 设置阶段不同：San 在 option 挂载前设置，Vue 在其后。以源码一致的简单绑定，添加可审计的公共 ref＋attached/updated 同步，不增加 DOM 包装、不使用私有 API。语法、静态契约及评估共用同一精确 helper 证明；仅逻辑源比较识别内部前缀，真实 DOM／value／选项更新照常检查。',
        '5. 静态分析器异常不再返回空 findings 当成功：明确保留 source_semantic_analysis_unavailable。生成与修复共享 v5 初始化约束，相关新诊断进入定向修复及按错误选择 SSM 的路径。','',
        '本轮不是按组件名称补丁，也不是整体 Vue AST 规则生成。完整 SSM＋模型生成、质量阈值、修复预算及回退门继续保留。','',
        '## 进一步定位但尚未修复的校验／规则缺口','',
        'AccessMatrix 的纯初始化规则已恢复候选 runtime，但组合了 class 反射且出现控件位置诊断，不能套用只证明默认值规则的窄恢复门，因而仍回退；还需将初始化独立提案并绑定其完整源证明。VolumeControl 已有合法的字符串键生命周期方法，但旧生命周期正则不识别；SearchClearField 的合法双向绑定内部空格使原生 value 规则漏匹配；FileDropIndicator 是 Vue/San class 字符串 trim 差异；StatusSwitch 则确实多了源中没有的 aria-label。这些不能全部归为模型随机或 Vue 源码有错。详见 residual_root_cause_audit.json。这里只登记定位事实，不提前标记已经修好。','',
        '## 全部剩余问题','',
        '以下计数按组件内诊断去重，不是人工独立缺陷数；分类可重叠。所有剩余项、实际维度、候选门原因和文件路径在 remaining.json，首轮逐项配对在 comparison.json。','',
        *[f'- {code}: {count}' for code,count in codes.most_common()], '',
        '原生控件／模板真实缺失、未证明的业务语义、语法损坏和无完整模型产物必须分别继续处理，不能降低阈值或把一次模型重跑当作规则已闭合的证明。','',
        '## 证据','',
        '- ../composed_v8_final_replay_20261120/：不可变协议、每项基线／步骤／有效代码、真实 DOM 与截图、门禁和实现快照。',
        '- migration_system/docs/verification/2026-11-19_general_repairs_v1/test-results-composed_v8_verified.json：固定版本关联回归；final.json 保留初始并行超时，isolated 日志保留隔离复测。',
        '- migration_system/var/refactor-verification/composed_v8_20261120.json：仓库外独立运行；模型为明确记录响应替身，不是真实生产成功率。',
        '- ../composed_v8_sequential_replay_20261120/STOPPED.md：补充内置对象遮蔽反例前的中止预检，不纳入本次统计。','']
    write_once(OUTPUT/'summary.json',result);write_once(OUTPUT/'remaining.json',remaining)
    write_once(OUTPUT/'failure_analysis.json',failure_analysis)
    write_once(OUTPUT/'residual_root_cause_audit.json',residual_audit)
    write_once(OUTPUT/'comparison.json',comparison);write_once(OUTPUT/'REPORT.md','\n'.join(lines))
    write_once(OUTPUT/'test-results.json',tests)
    write_once(OUTPUT/'standalone.json',standalone)
    for name,digest in tests['modules'].items():
        source=PROJECT/'tests'/(name+'.py')
        if hashed(source)!=digest:raise ValueError('test_source_changed_before_freeze:'+name)
        target=OUTPUT/'verification_tests'/source.name
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():raise ValueError('immutable_test_snapshot_exists')
        shutil.copyfile(source,target)
    write_once(OUTPUT/'analysis.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{},'cells':[
        {'cell_type':'markdown','metadata':{},'source':'\n'.join(lines)},
        {'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
         'source':"import json\nfrom pathlib import Path\nsummary=json.loads(Path('summary.json').read_text(encoding='utf-8'))\nsummary"},
        {'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
         'source':"remaining=json.loads(Path('remaining.json').read_text(encoding='utf-8'))\nremaining"}]})
    write_once(OUTPUT/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(OUTPUT).as_posix()+'\n'
        for p in sorted(OUTPUT.rglob('*')) if p.is_file()))
    print(json.dumps({k:v for k,v in result.items() if k!='standalone_report'},ensure_ascii=True),flush=True)


if __name__=='__main__':main()
