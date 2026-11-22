"""Final v9 review, preserving all main-version and follow-up denominators."""
from collections import Counter
import json
import shutil
from analyze_coverage import RUNS,read,write_once,hashed

PROJECT=RUNS.parent/'migration_system'
REPLAY=RUNS/'composed_v9_scope_reassessment_20261120'
OUTPUT=RUNS/'composed_v9_scope_review_20261120'


def verify(root):
    entries=[line.split('  ',1) for line in (root/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()]
    for digest,relative in entries:
        if hashed(root/relative)!=digest:raise ValueError('frozen_file_changed:'+relative)
    return len(entries)


def main():
    rows=read(REPLAY/'results.json');summary=read(REPLAY/'summary.json');protocol=read(REPLAY/'protocol.json')
    targeted_path=PROJECT/'docs/verification/2026-11-20_followup_v9/scope_verified/test-results.json'
    targeted=read(targeted_path)
    main_path=PROJECT/'docs/verification/2026-11-20_followup_v9/export_verified/test-results.json'
    main_tests=read(main_path)
    standalone_path=PROJECT/'var/refactor-verification/composed_v9_scope_20261120.json'
    standalone=read(standalone_path)
    if len(rows)!=70 or summary['statuses'].get('reassessment_error'):raise ValueError('complete_reassessment_required')
    if not targeted['successful'] or targeted['tests_run']!=9 or targeted['implementation_sha256']!=protocol['implementation_sha256']:
        raise ValueError('current_fixed_version_targeted_tests_required')
    if not main_tests['successful'] or main_tests['tests_run']!=249:raise ValueError('main_verification_required')
    if standalone['status']!='standalone_verified' or standalone['actual_cloud_model_calls']!=0:
        raise ValueError('actual_standalone_fixture_required')
    payloads=verify(REPLAY);main_payloads=verify(RUNS/'composed_v9_verified_replay_20261120')
    pairs=read(RUNS/'analysis_v3_vs_first70_20261119/pairs.json');by_name={row['component']:row for row in rows}
    comparison=[];remaining=[];details=[];codes=Counter()
    for pair in pairs:
        row=by_name[pair['component']];folder=REPLAY/row['sample_id']
        assessment=read(folder/'effective-assessment.json') if (folder/'effective-assessment.json').exists() else {}
        comparison.append({'component':row['component'],'first_mixed_70':pair['old'],'real_v3':pair['new'],
            'v8_offline_passed':row.get('v8_effective_passed'),'v9_before_scope_fix_passed':row.get('v9_recorded_effective_passed'),
            'current_offline_passed':row['effective_passed'],'code_changed_in_scope_followup':False,
            'capture_provenance':row.get('capture_provenance'),'evidence':folder.relative_to(RUNS).as_posix()})
        if row['effective_passed']:continue
        residual=row.get('effective_codes') or ['model_response_unknown_no_automatic_retry'];codes.update(residual)
        remaining.append({'component':row['component'],'complexity':row.get('complexity'),'codes':residual,
            'dimensions':row.get('effective_dimensions',{}),'evidence':folder.relative_to(RUNS).as_posix(),
            'v9_rule_evidence':row.get('v9_rule_evidence')})
        details.append({'component':row['component'],'first_mixed_codes':pair['old'].get('final_diagnostic_codes',[]),
            'real_v3_codes':pair['new'].get('final_diagnostic_codes',[]),'current_diagnostics':assessment.get('diagnostics',[]),
            'source_method_contracts':assessment.get('source_method_contracts',[]),
            'v9_rule_evidence':row.get('v9_rule_evidence'),'not_fixed':True})
    result={**summary,'remaining_count':len(remaining),'remaining_codes_including_unknown':dict(codes),
        'all_issues_resolved':not remaining,'first_mixed_70_passed':12,'real_v3_passed_unchanged':15,
        'v8_recorded_offline_passed':35,'main_version_regressions':{'tests':249,'successful':True,'same_implementation_as_final':False,'sha256':hashed(main_path)},
        'current_metadata_targeted_regressions':{'tests':9,'successful':True,'sha256':hashed(targeted_path)},
        'do_not_sum_two_version_test_counts':True,
        'payload_hashes_verified':{'current_reassessment':payloads,'v9_main_replay':main_payloads},
        'standalone_sha256':hashed(standalone_path),'metadata_difference_proof':protocol['metadata_AST_difference_proof']}
    lines=['# 通用修复v9最终复核：明确区分规则效果与作用域校验修正','',
        '2026-11-20。只使用冻结实验源码／SSM／有效San产物；真实模型调用0、云库访问0、用户服务未重启。','',
        '## 结果','',
        '- 首轮混合70项仍12/70（v1的49项＋v2补充21项），真实模型v3仍15/70；不改写历史结果。',
        f'- v8有效离线35/70；v9主规则版本完成70项登记、69份有效代码重新评估（66份基线真实浏览器、3份脚本语法失败），为42/70，新增8项，但CourseModuleAccordion被局部module计数误报错误判失败。该完整42/70结果及原实现已冻结。',
        f'- 最后只修正父方法元数据的词法归属：最终有效离线 **{summary["effective_passed"]}/70**，原通过现未通过：'+('、'.join(summary['previously_passed_now_failed']) or '无')+'。',
        '- 相对v8新增通过：'+('、'.join(summary['newly_passed_vs_v8']) or '无')+'。',
        f'- 仍有{len(remaining)}项未闭合；其中1项未知模型调用无完整产物不重试。不是新的生成通过率、独立测试或全部功能等价。','',
        '## 修复链与验证','',
        '主版本已接入导出父组件生命周期AST识别、最小纯初始化恢复及整份代码绑定的窄门、合法value绑定空白、原生属性／文本span恢复、class真实序列化。支持明确的export default和顶层唯一未遮蔽module.exports对象，未知组件覆盖／祖先展开／循环作用域等继续拒绝。生成与修复共享约束v6；仍是完整SSM＋模型，未恢复整组件规则生成／公开实例代理，预算及质量阈值不变。',
        '主规则版本249项同版关联回归通过；实际回放后发现CourseModuleAccordion误报，再修正仅1个元数据函数：只计未被词法绑定遮蔽的module/exports引用，局部循环／回调变量不算导出逃逸，真正全局别名／San命名空间修改仍拒绝。保留2项修复前RED（1失败、1通过），修正后既有7项＋新增2项共9项AST专项在当前版本通过。249与9属于不同实现版本，明确分列，不虚报为258项同版通过。',
        '最后一轮无任何组件代码修改或新规则提案。完整重新进行语法及静态检查：仅引擎元数据函数及其清单两文件变化，AST差异证明其余程序节点不变。源／目标代码、props、动作、阈值及全部渲染实现相同，才显式复用原真实浏览器捕获；不把旧恢复门证据重新授权。',
        f'- 当前新增真实浏览器捕获：{summary["fresh_browser_captures"]}；明确复用v9相同代码捕获：{summary["reused_browser_captures"]}；3份脚本语法失败仍按语法优先停止，1项无产物。',
        '- CourseModuleAccordion在当前版本额外做真实浏览器确认；独立目录系统再次实际运行通过（真实AST／LangGraph／API／下载／浏览器，模型为记录响应替身、云调用0）。',
        f'- 历史{summary["historical_files_verified_unchanged"]}文件、v9主回放{main_payloads}文件前后哈希不变；旧失败、拒绝候选、中止预检、249项验证及42/70均保留。','',
        '## 剩余问题','',
        '见remaining.json、failure_analysis.json：6项动态赋值契约仍需watch／timer／调用体闭环，4项嵌套写回、3份损坏脚本、控件／DOM／SVG真实差异及尚未证明的渲染依赖等继续保留。源代码合法但证明不足，与生成代码真实缺陷分开分析，不以删除诊断或提高额度代替修复。','',
        *[f'- {code}: {count}个组件' for code,count in codes.most_common()], '',
        '计数按组件内诊断去重，可重叠，不是人工独立缺陷数。下一步仍应在冻结失败产物上继续通用修复；本报告不建议立即启动另一次70项付费试跑来代替规则闭环。','',
        '## 证据入口','',
        '- ../composed_v9_scope_reassessment_20261120/：最终逐项静态检查、代码哈希、明确的捕获来源、当前额外浏览器确认及实现快照。',
        '- ../composed_v9_verified_replay_20261120/、../composed_v9_review_20261120/：主规则版本完整原始42/70及249项同版回归。',
        '- migration_system/docs/verification/2026-11-20_followup_v9/scope_red/与scope_verified/：同断言的RED／GREEN；tests_main_249.json与tests_current_9.json分别保留版本。',
        '- ../composed_v9_final_replay_20261120/STOPPED.md：18项中止预检及CommonJS覆盖修正前实现，未混入最终统计。','']
    write_once(OUTPUT/'summary.json',result);write_once(OUTPUT/'remaining.json',remaining)
    write_once(OUTPUT/'comparison.json',comparison);write_once(OUTPUT/'failure_analysis.json',details)
    write_once(OUTPUT/'REPORT.md','\n'.join(lines));write_once(OUTPUT/'tests_main_249.json',main_tests)
    write_once(OUTPUT/'tests_current_9.json',targeted);write_once(OUTPUT/'standalone.json',standalone)
    for name,digest in targeted['modules'].items():
        source=PROJECT/'tests'/(name+'.py')
        if hashed(source)!=digest:raise ValueError('test_changed_before_archive')
        target=OUTPUT/'verification_tests'/source.name;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():raise ValueError('immutable_snapshot_exists')
        shutil.copyfile(source,target)
    write_once(OUTPUT/'analysis.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{},'cells':[
        {'id':'v9scope-summary','cell_type':'markdown','metadata':{},'source':'\n'.join(lines)},
        {'id':'v9scope-results','cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
         'source':"import json\nfrom pathlib import Path\nname='composed_v9_scope_review_20261120'\nbase=next(p for root in [Path.cwd(), *Path.cwd().parents] for p in [root, root/'experiment_runs'/name] if p.name==name and (p/'summary.json').exists())\nsummary=json.loads((base/'summary.json').read_text(encoding='utf-8'))\nsummary"},
        {'id':'v9scope-remaining','cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
         'source':"remaining=json.loads((base/'remaining.json').read_text(encoding='utf-8'))\nremaining"}]})
    write_once(OUTPUT/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(OUTPUT).as_posix()+'\n'
        for p in sorted(OUTPUT.rglob('*')) if p.is_file()))
    print(json.dumps({key:result[key] for key in ('effective_passed','remaining_count','previously_passed_now_failed','fresh_browser_captures','reused_browser_captures')},ensure_ascii=True))


if __name__=='__main__':main()
