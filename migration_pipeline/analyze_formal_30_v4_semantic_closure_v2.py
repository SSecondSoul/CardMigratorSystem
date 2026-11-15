"""Verify and analyze the frozen v2 result; no runtime change or model call."""

import argparse
import json
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import digest, verify_snapshot
from migration_pipeline.analyze_formal_30_v4_repair_scheduling import progress_code_hash
from migration_pipeline.run_formal_30_v4_semantic_closure_v2 import ROOT, BATCH_ID


def analyze(snapshot):
    snapshot = snapshot.resolve()
    checked = verify_snapshot(snapshot)
    summary_file = snapshot / f'{BATCH_ID}_summary.json'
    summary = json.loads(summary_file.read_text(encoding='utf-8'))
    if summary['batch_id'] != BATCH_ID or [s['id'] for s in summary['samples']] != ['TaskManager', 'MonitoringDashboard']:
        raise RuntimeError('Unexpected batch or samples')
    rows = []
    for sample in summary['samples']:
        if sample['status'] != 'completed':
            raise RuntimeError('Execution errors require separate analysis')
        report = json.loads((snapshot / 'repair_reports/complex' / Path(sample['report_file']).name).read_text(encoding='utf-8'))
        state = report['state']
        history = state['repair_history']
        normalizations = state['normalization_history']
        if (state['semantic_rule_set'] != 'residual_v2' or sample['semantic_rule_set'] != 'residual_v2'
                or len(history) != sample['llm_repair_calls'] or len(history) != sample['repair_rounds']
                or len(normalizations) != sample['deterministic_steps'] or not 0 < len(history) <= 3
                or len(normalizations) > 4 * len(history) or sample['retained_previous_candidate']):
            raise RuntimeError(f"Unexpected counters/policy: {sample['id']}")
        for key in ('final_passed', 'stop_reason', 'llm_repair_calls', 'deterministic_steps', 'semantic_rule_set'):
            if report['summary'][key] != sample[key]:
                raise RuntimeError(f"Report/summary mismatch: {sample['id']}/{key}")
        final = snapshot / 'pipeline/complex' / Path(sample['final_file_path']).name
        if (final.read_text(encoding='utf-8') != state['generated_code']
                or final.read_text(encoding='utf-8') != history[-1]['repair_result']['repaired_code']
                or progress_code_hash(final) != history[-1]['progress_signature']['generated_code_sha256']
                or state['final_validate_result'] != history[-1]['validate_result']
                or state['final_visual_eval_result'] != history[-1]['visual_eval_result']):
            raise RuntimeError(f"Final file/evaluation mismatch: {sample['id']}")
        passed = bool(state['final_validate_result']['validation_passed'] and state['final_visual_eval_result']['visual_eval_passed'])
        if passed != sample['final_passed'] or state['final_passed'] != passed:
            raise RuntimeError('Final pass mismatch')
        rounds = []
        for entry in history:
            repair = entry['repair_result']
            if repair['provider'] == 'deterministic':
                raise RuntimeError('Wrong budget unit')
            gate = entry['repair_regression_gate']
            rounds.append({'attempt': entry['repair_attempt'], 'errors': entry['validate_result']['validation_errors'],
                'structure_similarity': entry['structure_similarity'], 'gate_should_stop': gate['should_stop'],
                'introduced_semantic_findings': gate['introduced_semantic_findings'],
                'postprocessing': repair.get('raw_response', {}).get('pipeline_postprocessing', []),
                'prompt_chars': len(repair['repair_prompt']),
                'focused_prompt': repair['repair_prompt'].startswith('You are repairing a standalone San'),
                'usage': repair.get('usage', {})})
        generation = state['generation_usage']['total_tokens']
        repair_tokens = sum(r['usage'].get('total_tokens', 0) for r in rounds)
        if generation != sample['generation_tokens'] or repair_tokens != sample['repair_tokens']:
            raise RuntimeError('Usage mismatch')
        rows.append({'id': sample['id'], 'passed': passed, 'stop_reason': sample['stop_reason'],
            'elapsed_seconds': sample['elapsed_seconds'], 'llm_repair_calls': len(history),
            'deterministic_steps': len(normalizations), 'normalization_history': normalizations,
            'rounds': rounds, 'final_errors': state['final_validate_result']['validation_errors'],
            'final_warnings': state['final_validate_result']['validation_warnings'],
            'final_structure_similarity': sample['final_structure_similarity'],
            'final_file': final.name, 'final_sha256': digest(final),
            'generation_tokens': generation, 'repair_tokens': repair_tokens,
            'automatic_interaction_evaluated': sample['interaction_eval_passed'] is not None,
            'manual_verification': 'pending'})
    a = summary['aggregate']
    if a['completed'] != len(rows) or a['passed'] != sum(r['passed'] for r in rows):
        raise RuntimeError('Aggregate status mismatch')
    for key in ('generation_tokens', 'repair_tokens'):
        if a[key] != sum(r[key] for r in rows):
            raise RuntimeError('Aggregate usage mismatch')
    if a['total_tokens'] != a['generation_tokens'] + a['repair_tokens']:
        raise RuntimeError('Total tokens mismatch')
    output = ROOT / 'data/experiments/analysis' / snapshot.name.replace('_results_', '_')
    output.mkdir(parents=True, exist_ok=True)
    data = {'snapshot': snapshot.relative_to(ROOT).as_posix(), 'verified_files': checked,
            'summary_sha256': digest(summary_file), 'classification': 'residual_v2_development_regression_analysis',
            'independent_holdout': False, 'model_requests_performed_by_analysis': 0,
            'aggregate': a, 'samples': rows}
    (output / 'summary.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    table = '\n'.join(f"| {r['id']} | {r['llm_repair_calls']} | {r['deterministic_steps']} | {r['final_structure_similarity']} | {'自动通过，人工待验' if r['passed'] else '未通过'} |" for r in rows)
    report = f'''# semantic closure v2 模型回归：TaskManager 自动通过，MonitoringDashboard 未通过

日期：2026-11-03。运行 15:32:26–16:03:55（UTC+8）。批次 `{BATCH_ID}`。先冻结后详细分析：`{snapshot.name}`，{checked} 个文件验证通过；冻结时协议 278 项 live 哈希通过。实际服务器超时环境未被文件哈希或健康检查独立证明。仅重复开发样本，不是独立测试，旧评分不变。

## 结果与用量

**2 完成、1 自动通过、1 失败、0 执行错误**。两项最终文件字节／进度签名、静态与视觉评估、repair history、计数及 token 均核对一致。

| 样本 | LLM repair 次数 | 确定性步骤（均接受） | 最终 DOM 相似度 | 结论 |
| --- | ---: | ---: | ---: | --- |
{table}

生成 {a['generation_tokens']:,}、repair {a['repair_tokens']:,}、总计 **{a['total_tokens']:,} tokens**。TaskManager 764.781 秒，MonitoringDashboard 1124.688 秒，均为样本总耗时而不是单次请求耗时。v1 使用 6 次 LLM repair、本次 5 次；上限相同、输入 Vue 相同，但新生成代码不同且规则／Prompt／保护门同时变更，不能把用量差异或通过变化当作单因素因果结论。

## TaskManager

两步确定性计划均被接受：源 inline props schema 补到子组件、source self／drag、methods／registry 修复，随后提取自包含 computed helper、规范空修饰符事件。第一次 LLM 的返回后处理也记录了 helper 提取；最终第二次 LLM 后静态与初始 DOM 通过，stop_reason=passed。

第 1 次 LLM 后剩事件语法与隐藏依赖，第 2 次已无静态错误；未触发保护门或回退。两次提示长度 444481／57136 字符，第二次进入语义聚焦。通过依据是当前冻结评估，不是择优引用历史人工修过的旧 San。

仍有 migration_hints_not_landed 警告，自动结果不等于零警告、交互全面等价。automatic interaction 未运行，**人工验证仍待执行**。设置、创建／编辑模态框、点击内部不关闭、关闭按钮、拖拽、筛选计数与完成状态联动应重点复查。

当前两个人工测试页仍引用 2026-10-29 的旧 TaskManager 源／San 快照，尚未切换到本轮产物。直接在当前页面点击不能证明新产物通过；本次没有改测试页或把旧人工通过结论移用到新产物。

## MonitoringDashboard

一次确定性计划补源 props schema、解包 directive／methods；第一次 LLM 返回后明确记录纯算术 formatter 和自包含 computed helper 修复。三次 LLM 后错误族分别为 4、3、2；最终还剩：

1. event_arguments_not_landed：源 `onKPIClick(kpi)` 改成裸 `onKPIClick`，父处理器变成 `onKPIClick(e)` 并访问 `kpiData[e.index]`；子组件实际 `this.fire('click')` 不携带 index。此链不能提供所需索引，需恢复源业务参数／一致 payload，不能只改绑定或函数名。当前窄规则只处理特定零形参 this.event 绕行，未覆盖此带参数且不一致的 payload 改写。
2. lifecycle_behavior_not_landed：源 mounted 的 initData 初始化链、startTimeUpdate、startDataSimulation 被搬到 inited，attached 只剩自动刷新和启动通知。动作不是全部消失，而是初始化／计时器启动时机与源契约不一致；需要基于源顺序修复，不能豁免验证器或再提前启动来消除报错。

最终 DOM 0.9825，前两次 0.9912；均在当前阈值内，通过状态没有丢失，因此保护门未因细微 DOM 相似度下降拒收。事件参数与生命周期错误持续存在而非本轮新出现，新增语义拒收也未触发。不能声称本次模型运行演示了回退；回退证据来自此前冻结第 2→3 次重放及正反例测试。

第 2 次 repair 仍为完整 Prompt（477646 字符），因为此前缺少 missing_lifecycle_mapping，不在当前语义聚焦集合；第 3 次才进入聚焦（63853 字符）。这是待审查路由边界，不足以单独解释失败。

## 下一步（尚未实施）

保留 TaskManager 本轮通过产物，切换两个人工测试页到它并由用户验证，不重生已通过样本。MonitoringDashboard 使用本次失败快照离线建立 KPI payload／绑定与生命周期阶段的正反例，审查聚焦边界；先改通用规则／Prompt、验证和冻结新版本，再只对失败项做新版本针对性运行。不要直接 --force 重抽本批。两项全部验证后仍需完整 30 项回归，原另外三个失败事项及 v5 仍等待。

本次只新增结果冻结／分析工具与 Notebook 记录，未改运行期 Prompt、规则、验证器、旧 San、人工测试页，未 commit／push。

复现：`python -m migration_pipeline.analyze_formal_30_v4_semantic_closure_v2 --snapshot {snapshot.relative_to(ROOT).as_posix()}`。
'''
    (output / 'REPORT.md').write_text(report, encoding='utf-8')
    print(output.relative_to(ROOT))
    print(json.dumps({'verified_files': checked, 'completed': a['completed'], 'passed': a['passed'],
                      'failed': a['failed'], 'total_tokens': a['total_tokens']}))
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    args = parser.parse_args()
    analyze(args.snapshot if args.snapshot.is_absolute() else ROOT / args.snapshot)
