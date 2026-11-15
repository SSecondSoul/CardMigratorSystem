"""Audit frozen v3 rollback and diagnostic visibility; no runtime repair/model call."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import digest, verify_snapshot
from migration_pipeline.analyze_formal_30_v4_repair_scheduling import progress_code_hash
from migration_pipeline.run_formal_30_v4_semantic_closure_v3 import ROOT, BATCH_ID
from migration_pipeline.stages.validate import ValidateStage


def visibility_audit(before, after, introduced):
    """Isolate the existing checker on scopes it skipped due to illegal names.

    This does not rewrite a SFC, execute either artifact or alter the live gate.
    Locations are explicitly aligned for comparing corresponding child scopes.
    """
    validator = ValidateStage()
    proofs, rediscovered = [], []
    for old, new, methods in (
        ('real-time-chart', 'RealTimeChart', ('getX', 'getY')),
        ('request-chart', 'RequestChart', ('getX', 'getHeight')),
    ):
        scopes = []
        for code, name in ((before, old), (after, new)):
            matches = list(re.finditer(r'\bconst\s+' + re.escape(name) + r'\s*=\s*san\.defineComponent\s*\(\s*\{', code))
            if len(matches) != 1:
                raise RuntimeError('Child scope is ambiguous')
            scopes.append(validator._extract_braced_body(code, matches[0].end() - 1))
        left, right = scopes
        bodies = {}
        for name in methods:
            a, b = (validator._extract_function_body(code, name).strip() for code in scopes)
            if not a or a != b:
                raise RuntimeError(f'Method changed; cannot prove pre-existing defect: {old}/{name}')
            bodies[name] = hashlib.sha256(a.encode('utf-8')).hexdigest()
        template = re.search(r'\btemplate\s*:\s*`([\s\S]*?)`', left).group(1)
        target_template = re.search(r'\btemplate\s*:\s*`([\s\S]*?)`', right).group(1)
        # The actual render call expressions for the diagnosed methods remain
        # unchanged, even though loop directive spelling/class syntax improved.
        calls = lambda text: [m.group(0) for m in re.finditer(
            r'\{\{[^{}]*\b(?:' + '|'.join(methods) + r')\s*\([^{}]*\}\}', text)]
        if calls(template) != calls(target_template):
            raise RuntimeError('Diagnosed render expressions changed')
        issues, checks = [], []
        validator._validate_template_reactive_dependencies(template, left, issues, checks, component_name=new)
        findings = [i.to_dict() for i in issues]
        rediscovered.extend(findings)
        proofs.append({'before_declaration': old, 'after_declaration': new,
            'method_bodies_equal_after_outer_whitespace_trim': True, 'method_body_sha256': bodies,
            'diagnosed_render_expressions_equal': True, 'render_expressions': calls(template),
            'isolated_before_findings_with_aligned_scope_location': findings})
    identity = lambda x: (x['code'], x.get('location', ''), x.get('message', ''))
    if sorted(map(identity, rediscovered)) != sorted(map(identity, introduced)):
        raise RuntimeError('Isolated baseline does not explain all gate additions')
    return {'classification': 'newly_visible_preexisting_hidden_dependencies_not_proven_new_regressions',
        'explained_findings': len(rediscovered), 'proofs': proofs,
        'root_cause': 'Inline checker enumerates legal const identifiers; hyphenated const names in '
                      'the baseline hide those scopes. Fixing declarations makes unchanged method '
                      'dependencies visible; the gate compares diagnostic tuples without coverage state.',
        'boundary': 'Only these four findings are explained. Rejected candidate remains statically '
                    'invalid and is not reclassified as passed. This audit does not disable the gate.'}


def analyze(snapshot):
    snapshot = snapshot.resolve()
    verified = verify_snapshot(snapshot)
    summary_path = snapshot / f'{BATCH_ID}_summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    if summary['batch_id'] != BATCH_ID or [s['id'] for s in summary['samples']] != ['MonitoringDashboard']:
        raise RuntimeError('Unexpected batch')
    sample = summary['samples'][0]
    report = json.loads((snapshot / 'repair_reports/complex/MonitoringDashboard_repair_history.json').read_text(encoding='utf-8'))
    state = report['state']
    history, norms = state['repair_history'], state['normalization_history']
    if (sample['status'] != 'completed' or len(history) != sample['llm_repair_calls'] or len(history) != 1
            or len(norms) != sample['deterministic_steps'] or len(norms) != 1
            or not sample['retained_previous_candidate'] or not state['retained_previous_candidate']
            or sample['stop_reason'] != 'repair_candidate_regression_rolled_back'
            or sample['final_passed'] or not history[0]['repair_regression_rejected']
            or not norms[0]['accepted']):
        raise RuntimeError('Unexpected rollback history')
    entry = history[0]
    final = snapshot / 'pipeline/complex' / Path(sample['final_file_path']).name
    rejected = snapshot / 'pipeline/complex' / Path(entry['repair_result']['repaired_file_path']).name
    if (final.read_text(encoding='utf-8') != state['generated_code']
            or rejected.read_text(encoding='utf-8') != entry['repair_result']['repaired_code']
            or final.name != Path(norms[0]['candidate_file']).name
            or rejected.name != Path(state['rejected_candidate_file']).name
            or progress_code_hash(final) != norms[0]['progress_signature']['generated_code_sha256']
            or progress_code_hash(rejected) != entry['progress_signature']['generated_code_sha256']
            or state['final_validate_result'] != state['validate_result']
            or state['final_visual_eval_result'] != state['visual_eval_result']):
        raise RuntimeError('Retained/rejected artifact or evaluation mismatch')
    for key in ('final_passed', 'stop_reason', 'llm_repair_calls', 'deterministic_steps', 'retained_previous_candidate'):
        if report['summary'][key] != sample[key]:
            raise RuntimeError(f'Summary mismatch: {key}')
    if (state['final_validate_result']['validation_errors'] != state['validation_errors']
            or sample['final_validation_error_codes'] != [i['code'] for i in state['validation_errors']]
            or sample['final_structure_similarity'] != state['final_visual_eval_result']['structure_similarity']):
        raise RuntimeError('Final evaluation differs from retained state')
    generation = state['generation_usage']['total_tokens']
    repair = sum(h['repair_result']['usage']['total_tokens'] for h in history)
    aggregate = summary['aggregate']
    if (generation != sample['generation_tokens'] or repair != sample['repair_tokens']
            or generation != aggregate['generation_tokens'] or repair != aggregate['repair_tokens']
            or generation + repair != aggregate['total_tokens']
            or any(aggregate[k] != v for k, v in {'configured': 1, 'completed': 1,
                'passed': 0, 'failed': 1, 'execution_errors': 0, 'pending': 0}.items())):
        raise RuntimeError('Usage/aggregate mismatch')
    gate = entry['repair_regression_gate']
    introduced = gate['introduced_semantic_findings']
    if len(introduced) != 4 or any(x['code'] != 'hidden_template_reactive_dependency' for x in introduced):
        raise RuntimeError('Unexpected rejection reason')
    audit = visibility_audit(final.read_text(encoding='utf-8'), rejected.read_text(encoding='utf-8'), introduced)
    data = {'classification': 'frozen_single_sample_development_rollback_analysis',
        'snapshot': snapshot.relative_to(ROOT).as_posix(), 'verified_files': verified,
        'summary_sha256': digest(summary_path), 'independent_holdout': False,
        'model_requests_performed_by_analysis': 0, 'aggregate': aggregate,
        'sample': sample, 'retained': {'file': final.name, 'sha256': digest(final),
            'validation': state['final_validate_result'], 'visual': state['final_visual_eval_result']},
        'rejected': {'file': rejected.name, 'sha256': digest(rejected),
            'validation': entry['validate_result'], 'visual': entry['visual_eval_result']},
        'gate': gate, 'normalizations': norms, 'diagnostic_visibility_audit': audit,
        'repair_prompt_chars': len(entry['repair_result']['repair_prompt']),
        'repair_postprocessing': entry['repair_result']['raw_response'].get('pipeline_postprocessing', []),
        'new_source_phase_rules_recorded_in_run': [],
        'manual_verification': 'not_started_no_renderable_accepted_candidate'}
    labels = norms[0]['normalizations'] + data['repair_postprocessing']
    if any(name in labels for name in ('restored_source_loop_payload_handler',
                                       'restored_source_mounted_phase_order', 'restored_source_watch_persistence')):
        raise RuntimeError('Unexpected source-phase application; review narrative')
    output = ROOT / 'data/experiments/analysis' / snapshot.name.replace('_results_', '_')
    if output.exists():
        raise FileExistsError('Do not replace an existing analysis')
    output.mkdir(parents=True)
    (output / 'summary.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report_text = f'''# semantic closure v3：失败已冻结，发现诊断可见性与回退门不协调

日期：2026-11-03。运行 17:44:11–17:53:44（UTC+8），572.797 秒。
批次 {BATCH_ID}，仅 MonitoringDashboard；重复开发回归，不是独立测试。
快照 {snapshot.name}，{verified} 文件校验；冻结时协议 304 项 live 校验通过。

## 实际结果

1 完成、0 通过、1 失败、0 执行异常。一次确定性步骤被接受；一次 LLM repair 被拒收并回退，故未继续消耗上限内其余两次调用。保留文件为 {final.name}；拒收文件 {rejected.name} 单独保留。summary、history、候选签名、文件及用量已交叉核对。

生成 {generation:,}、修复 {repair:,}、合计 {generation + repair:,} tokens，拒收消耗计入，不丢弃。最终保留代码仍无法编译，初始 DOM 相似度 0。拒收候选可编译，初始 DOM 通过、相似度 {entry['structure_similarity']}，但仍有 7 条静态错误：事件语法、computed 调用实例方法、4 条隐藏依赖、KPI 绑定参数丢失。不能因为能渲染或诊断数量减少而宣布通过。

## 为什么只调用一次就回退

候选门报告 4 条新出现的 hidden_template_reactive_dependency：RealTimeChart 的 cx/getX、cy/getY，以及 RequestChart 的 x/getX、height/getHeight。源码对照与隔离检测证明，这四个方法主体及对应渲染调用表达式在修复前后没有变化（见 summary.json 中逐项摘要与诊断）。

原保留代码包含 const real-time-chart、const request-chart 等非法 JavaScript 声明。当前 inline 检查器只枚举合法 const 标识符，因而漏掉这些范围；LLM 修复了标识符后，相同的既有隐藏依赖才被报告。保护门把诊断差集直接认作语义新增，没有记录检测覆盖率／不可分析状态。这次不能解读为模型新引入四个错误；应认定存在诊断可见性转换导致的回退误判。审计只解释这四项，不证明候选行为正确，也不改变本轮失败计分。

## 上轮规则为何未闭合本次产物

本轮 generation 重新产生非法内联标识符等语法问题；依赖完整 JS AST 的源事件／挂载／watcher 规则无法解析此输入，失败关闭是预期边界。本轮预处理只记录 directive 解包、methods 展开及业务 initData 重命名，没有记录上一轮新增的三项源阶段修复，不能声称它们本轮已执行又失效。

LLM 候选的 onKPIClick 方法已经是源 kpi 参数，但模板仍只有裸绑定；这不是上一窄规则处理的 e.index 两变量绕行形状，因此没有成对修复。watcher 又改成零参数回调、在内部读取 settings，不满足上一轮的“同参数／其余主体完全一致”存储补回条件。初始化链也有 initDataImpl 调用形式和提前读取 localStorage，不可直接按此前展开序列搬移。上述超出边界不等于源行为已正确或检测已全面覆盖。

候选还有 computed 直接调用 this.getX/this.getY，这些方法读取 this.data；现有 residual helper 提取限定自包含方法，不能把有隐藏 this 依赖的方法直接移到模块级。生成阶段 Prompt 本轮未改，不应预期 repair 阶段有边界规则保证所有初次输出合法。

## 下一步建议（尚未实施）

暂停直接付费复跑，也不切人工测试页面到失败产物。先以本快照补齐“不可分析 → 可分析”的覆盖状态及候选门正反例：区分既有缺陷首次暴露与真实新缺陷，保留真的回归拒收，不能全局豁免隐藏依赖。

再审查非法内联标识符的有边界结构恢复、已正确方法但缺参数绑定的成对契约，以及有状态图表 helper 的显式依赖转换。所有改动先在冻结输入／拒收候选离线证明，记录遗留错误；新版本冻结后才安排下一次模型调用。本轮原分数、被拒产物与用量不得改写。TaskManager 已通过候选与当前人工页保持不变，完整 30 项回归未完成。

本分析未修改运行期规则／Prompt／验证器、生成产物或测试页，未启动模型、未执行浏览器交互、未 commit／push。服务器是否实际以声明超时运行，不能由文件哈希或 health 返回独立证明。
'''
    (output / 'REPORT.md').write_text(report_text, encoding='utf-8')
    verify_snapshot(snapshot)
    print(output.relative_to(ROOT))
    print(json.dumps({'verified_files': verified, 'passed': 0, 'failed': 1,
        'llm_repair_calls': len(history), 'total_tokens': generation + repair,
        'preexisting_findings_newly_visible': audit['explained_findings']}))
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    args = parser.parse_args()
    analyze(args.snapshot if args.snapshot.is_absolute() else ROOT / args.snapshot)
