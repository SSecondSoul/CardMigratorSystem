"""Immutable v9 engineering review. Never rewrites historical success rates."""
from collections import Counter
from pathlib import Path
import json
import shutil
from analyze_coverage import RUNS, read, write_once, hashed

PROJECT=RUNS.parent/'migration_system'
REPLAY=RUNS/'composed_v9_verified_replay_20261120'
OUTPUT=RUNS/'composed_v9_review_20261120'


def verify_files(root):
    entries=[line.split('  ',1) for line in (root/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()]
    for digest,relative in entries:
        if hashed(root/relative)!=digest:raise ValueError('frozen_payload_changed:'+relative)
    return len(entries)


def rule_labels(change):
    if isinstance(change,str):return [change]
    if isinstance(change,dict):return [change.get('rule','unnamed_structured_change')]
    if isinstance(change,(list,tuple)):return [label for item in change for label in rule_labels(item)]
    return []


def main():
    summary=read(REPLAY/'summary.json');rows=read(REPLAY/'results.json');protocol=read(REPLAY/'protocol.json')
    tests_path=PROJECT/'docs/verification/2026-11-20_followup_v9/export_verified/test-results.json'
    tests=read(tests_path)
    standalone_path=PROJECT/'var/refactor-verification/composed_v9_export_verified_20261120.json'
    standalone=read(standalone_path)
    owner_audit=RUNS/'composed_v9_call_owner_audit_20261120/audit.json'
    if len(rows)!=70 or summary['statuses'].get('replay_error'):raise ValueError('complete_replay_required')
    if not tests['successful'] or tests['implementation_sha256']!=protocol['implementation_sha256']:
        raise ValueError('passing_same_version_regressions_required')
    if standalone['status']!='standalone_verified' or standalone['actual_cloud_model_calls']!=0:
        raise ValueError('standalone_engineering_verification_required')
    payloads=verify_files(REPLAY)
    v8_payloads=verify_files(RUNS/'composed_v8_final_replay_20261120')
    v7_payloads=verify_files(RUNS/'composed_v7_verified_replay_20261119')
    pairs=read(RUNS/'analysis_v3_vs_first70_20261119/pairs.json')
    by_name={row['component']:row for row in rows}
    comparison=[];remaining=[];failures=[];new_passes=[];codes=Counter();gates=Counter();changes=Counter()
    for pair in pairs:
        row=by_name[pair['component']];folder=REPLAY/row['sample_id']
        assessment=read(folder/'effective-assessment.json') if (folder/'effective-assessment.json').exists() else {}
        comparison.append({'component':pair['component'],'first_mixed_70':pair['old'],'real_v3':pair['new'],
            'v8_offline_effective_passed':row.get('v8_effective_passed'),
            'v9_fresh_baseline_passed':row.get('fresh_baseline_passed'),
            'v9_offline_effective_passed':row['effective_passed'],
            'v9_evidence':folder.relative_to(RUNS).as_posix()})
        for step in row.get('steps',[]):
            gates.update([step['gate']['reason']])
            changes.update(set(label for c in step['changes'] for label in rule_labels(c)))
        if row['effective_passed']:
            if not row.get('v8_effective_passed'):
                prior=read(RUNS/'composed_v8_final_replay_20261120'/row['sample_id']/'result.json')
                new_passes.append({'component':row['component'],'v8_effective_codes':prior.get('effective_codes',[]),
                    'v9_fresh_baseline_codes':row.get('baseline_codes',[]),'dimensions':row['effective_dimensions'],
                    'rule_labels':sorted({label for step in row.get('steps',[]) for c in step['changes'] for label in rule_labels(c)}),
                    'candidate_decisions':[step['gate'] for step in row.get('steps',[])],
                    'evidence':folder.relative_to(RUNS).as_posix()})
            continue
        residual=row.get('effective_codes') or ['model_response_unknown_no_automatic_retry']
        codes.update(residual)
        remaining.append({'component':row['component'],'sample_id':row['sample_id'],
            'complexity':row.get('complexity'),'codes':residual,'dimensions':row.get('effective_dimensions',{}),
            'candidate_decisions':[step['gate'] for step in row.get('steps',[])],
            'stop':row.get('stop',row['status']),'evidence':folder.relative_to(RUNS).as_posix()})
        failures.append({'component':row['component'],'first_mixed_codes':pair['old'].get('final_diagnostic_codes',[]),
            'real_v3_codes':pair['new'].get('final_diagnostic_codes',[]),'v9_diagnostics':assessment.get('diagnostics',[]),
            'source_method_contracts':assessment.get('source_method_contracts',[]),
            'steps':row.get('steps',[]),'not_fixed':True})
    browser_count=sum((REPLAY/r['sample_id']/'baseline-browser.json').exists() for r in rows)
    syntax_failures=[r['component'] for r in rows if 'target_script_syntax_error' in r.get('baseline_codes',[])]
    result={**summary,'baseline_browser_captures':browser_count,'baseline_script_syntax_failures':syntax_failures,
        'test_count':tests['tests_run'],'real_v3_passed_unchanged':15,
        'first_mixed_70_passed':sum(bool(p['old']['passed']) for p in pairs),
        'remaining_count':len(remaining),'remaining_codes_by_components':dict(codes),
        'all_issues_resolved':not remaining,'proposal_rule_labels_by_steps_not_defects':dict(changes),
        'verified_payloads':{'v9':payloads,'v8':v8_payloads,'v7':v7_payloads},
        'standalone_report_sha256':hashed(standalone_path),
        'v8_residual_call_owner_audit':{'path':owner_audit.relative_to(RUNS).as_posix(),'sha256':hashed(owner_audit)},
        'interpretation':'frozen_artifact_development_NOT_new_model_or_independent_test_pass_rate'}
    lines=['# 通用修复 v9：父级生命周期 AST、最小初始化恢复及真实 DOM 修复','',
        '2026-11-20。源码、SSM 和生成产物来自原冻结批次；无真实模型调用、云数据库写入或用户服务重启。','',
        '## 同版结果','',
        f'- 首轮混合结果仍为 {result["first_mixed_70_passed"]}/70（v1 49 项＋v2 补充21项），v3 真实模型批次仍为15/70，不改写历史统计。',
        f'- v8 有效离线结果35/70；本轮重新评估69份有效代码，{browser_count}份完成基线真实浏览器捕获，{len(syntax_failures)}份脚本语法失败按语法优先门停止，另1份未知模型调用无完整代码不重试。',
        f'- v9 新鲜父版本基线 {summary["fresh_baseline_passed"]}/70；生产顺序规则与正常门禁后 {summary["effective_passed"]}/70，仍有{len(remaining)}项未闭合。',
        '- 相对v8新增离线通过：'+('、'.join(summary['newly_passed_vs_v8']) or '无')+'。',
        '- 原通过现未通过：'+('、'.join(summary['previously_passed_now_failed']) or '无')+'。',
        f'- 固定实现及测试源码下，{tests["tests_run"]}项关联回归通过；独立目录实际运行验证通过（记录响应替身，云模型调用0）。',
        f'- 历史{summary["historical_files_verified_unchanged"]}文件、v8的{v8_payloads}文件及v7的{v7_payloads}文件哈希核验不变。','',
        '## 根因与通用修复','',
        '1. 生命周期旧正则不能可靠定位导出父组件，既漏认合法引号方法／函数属性，也会误认子组件／字符串中的钩子。现在只用唯一、未遮蔽导出父对象的 AST 方法元数据检查存在及实际方法体；空钩子、重复键、箭头、未知别名和子组件钩子不构成证明。没有把“有同名方法”当作业务正确。',
        '2. 源纯初始化恢复与其他模板改动混在一起时，被原回退门拒绝。现在先提交最小初始化候选，绑定整份代码、源、props、动作及运行实现哈希；只有确切恢复运行、控件值与数量保持、DOM确有进展且没有其他新增缺陷，才允许控件诊断从状态缺失细化为位置差异。位置及结构仍失败；额外CSS/业务改动不能借用该证明。',
        '3. 原生 value 绑定合法空白未被旧规则识别。按简单绑定语法识别 {{ field }}／{= field =}，修复实际HTML属性并保留原双向／事件语义；复杂表达式、错字段、未知类型不猜。',
        '4. 生成代码多余文本 span、aria 标签、input type、遗漏 button type 及静态化 option 绑定形成真实DOM差异。只在源／目标原生标签及全部祖先作用域明确匹配、无未知组件覆盖或属性展开时做局部源码恢复。源自己拥有的span、有属性span、错文本／循环作用域均保留；不是对DOM TED添加忽略项。',
        '5. Vue对字符串动态class做trim，San字符串插值可能保留首尾空格。只对有限纯状态条件和精确源表达式修复目标真实class序列化，空class属性存在性也保留。CSS观察精确class的测试仍按严格比较执行，不降低观察策略。',
        '生成与修复共享约束升级v6，仍为完整SSM＋模型生成；没有整体AST规则生成、公开实例代理、组件名白名单或阈值／模型预算变化。','',
        '## 保留的失败与下一步','',
        '剩余诊断逐组件、逐原始证据记录在remaining.json和failure_analysis.json，包括实际业务差异、尚未证明的watch／timer／写回接口、损坏脚本与无完整产物。不能用“模型随机”统一解释，也不能因画面相同而删除静态和结构诊断。','',
        '对v8剩余6项动态赋值诊断另做了全量AST调用归属审计（../composed_v9_call_owner_audit_20261120/）：3份源码包含watch选项内的setter调用，另见定时器私有句柄／箭头体表示、局部只读缓存及完整调用体差异。审计只定位，不构成放行证明；未来需组合watch注册、完整调用及读写顺序证明，不能把未知owner简单忽略或把私有实例键当普通data。','',
        *[f'- {code}: {count}个组件' for code,count in codes.most_common()], '',
        '上述数量按组件内诊断去重，可重叠，不是人工独立缺陷数。拒绝候选及父版本均保存。新真实模型通过率只能由后续经用户确认的统一配置重跑给出。','',
        '## 证据','',
        '- ../composed_v9_verified_replay_20261120/：新协议、逐项基线、候选、门禁、有效代码、浏览器DOM/截图及实现快照。',
        '- test-results.json、verification_tests/：同版关联回归与完整测试源码快照。',
        '- standalone.json：独立目录运行，真实解析／图／API／浏览器；模型为记录替身。',
        '- migration_system/docs/verification/2026-11-20_followup_v9/：生命周期修复前RED用例及中止预检，未混入最终结果。',
        '- ../composed_v9_final_replay_20261120/STOPPED.md：18项中止预检暴露CommonJS源入口覆盖缺口，原实现及部分结果封存；最终版本补充顶层、未遮蔽、唯一CommonJS对象导出及相同实际DOM回归，不采用旧18项统计。','']
    write_once(OUTPUT/'summary.json',result);write_once(OUTPUT/'remaining.json',remaining)
    write_once(OUTPUT/'newly_passed.json',new_passes)
    write_once(OUTPUT/'comparison.json',comparison);write_once(OUTPUT/'failure_analysis.json',failures)
    write_once(OUTPUT/'REPORT.md','\n'.join(lines));write_once(OUTPUT/'test-results.json',tests)
    write_once(OUTPUT/'standalone.json',standalone)
    for name,digest in tests['modules'].items():
        source=PROJECT/'tests'/(name+'.py')
        if hashed(source)!=digest:raise ValueError('test_changed_before_freeze:'+name)
        path=OUTPUT/'verification_tests'/source.name;path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():raise ValueError('immutable_test_snapshot_exists')
        shutil.copyfile(source,path)
    write_once(OUTPUT/'analysis.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{},'cells':[
        {'cell_type':'markdown','metadata':{},'source':'\n'.join(lines)},
        {'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
         'source':"import json\nfrom pathlib import Path\nsummary=json.loads(Path('summary.json').read_text(encoding='utf-8'))\nsummary"},
        {'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
         'source':"remaining=json.loads(Path('remaining.json').read_text(encoding='utf-8'))\nremaining"}]})
    write_once(OUTPUT/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(OUTPUT).as_posix()+'\n'
        for p in sorted(OUTPUT.rglob('*')) if p.is_file()))
    print(json.dumps(result,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
