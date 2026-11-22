"""Versioned v7 evidence, with v6 comparison and every unresolved item retained."""
from collections import Counter
from pathlib import Path
import json
import shutil
from analyze_coverage import read,write_once,hashed,RUNS

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'migration_system'
REPLAY=RUNS/'composed_v7_verified_replay_20261119'
OUTPUT=RUNS/'composed_v7_review_20261119'


def main():
    summary=read(REPLAY/'summary.json');rows=read(REPLAY/'results.json')
    if len(rows)!=70 or summary['statuses'].get('replay_error'):raise ValueError('complete_successful_replay_required')
    previous={r['component']:r for r in read(RUNS/'composed_v6_final_replay_20261119/results.json')}
    pairs={p['component']:p['new'] for p in read(RUNS/'analysis_v3_vs_first70_20261119/pairs.json')}
    gained=[r['component'] for r in rows if r['effective_passed'] and not previous[r['component']]['effective_passed']]
    lost=[r['component'] for r in rows if not r['effective_passed'] and previous[r['component']]['effective_passed']]
    remaining=[];codes=Counter()
    for row in rows:
        if row['effective_passed']:continue
        old=pairs[row['component']]
        report=(row['after'] if row['gate']['accepted'] else row['before']) if row.get('gate') else read(RUNS/old['report']).get('assessment') or {}
        diagnostics=sorted({d['code'] for d in report.get('diagnostics',[])}) or [old['stop_reason']]
        codes.update(diagnostics)
        remaining.append({'component':row['component'],'complexity':old['complexity'],'codes':diagnostics,
                          'gate':row.get('gate'),'offline_result':str((REPLAY/old['sample_id']/'result.json').relative_to(RUNS))})
    tests=read(PROJECT/'docs/verification/2026-11-19_general_repairs_v1/test-results-composed_v7_verified.json')
    if not tests['successful']:raise ValueError('tests_must_pass')
    protocol=read(REPLAY/'protocol.json')
    if tests['implementation_sha256']!=protocol['implementation_sha256']:raise ValueError('test_replay_versions_differ')
    reference=RUNS/'composed_v6_final_replay_20261119';old_protocol=read(reference/'protocol.json')
    if hashed(reference/'implementation/browser/evaluate.mjs')!=old_protocol['implementation_sha256']['browser/evaluate.mjs']:
        raise ValueError('reference_capture_source_hash_drift')
    recovery=read(RUNS/'default_recovery_v7_20261119/summary.json')
    result={**summary,'real_model_v3_passed':15,'v6_offline_passed':28,'v7_new_offline_passes':gained,
        'v6_passes_lost':lost,'remaining_count':len(remaining),'remaining_codes_by_components':dict(codes.most_common()),
        'test_count':tests['tests_run'],'isolated_default_recovery':recovery,'all_issues_resolved':not remaining,
        'reused_v6_capture_rows':sum('reused_result' in row for row in rows),
        'new_browser_evidence_rows':sum((REPLAY/pairs[row['component']]['sample_id']/'after-browser.json').exists() for row in rows),
        'interpretation':'existing_artifact_development_replay_NOT_new_generation_or_independent_test_rate'}
    lines=['# 通用修复 v7：原生属性、computed 值消费与默认值恢复门','',
        '## 结果','',
        f'真实模型 v3 批次仍为 15/70。本轮真实模型调用为 0；已有冻结代码的有效离线通过为 {summary["effective_passed"]}/70（v6 为 28/70）。',
        f'相对 v6 新增：{"、".join(gained) or "无"}；v6 通过回退：{"、".join(lost) or "无"}。',
        f'保留未解决 {len(remaining)} 项；未降低阈值，未重试 TaskManager 未知调用，未运行验证集／测试集。',
        f'关联回归 {tests["tests_run"]} 项通过；全部 {summary["frozen_files_verified_unchanged"]} 个历史输入文件哈希核验不变。','',
        '复用捕获仍是 v6 的历史观察，不是对所有组件重新拍摄或当前运行时全量重测的声明；新增候选的浏览器证据单独保存。','',
        '## 通用实现','',
        '- 原生 input／textarea：源 :value 与目标绑定为同一简单状态表达式时，使用 HTML VALUE 属性反射；空值移除属性，保留原有 value、双向绑定及事件。真实 DOM/live 值及表单重置均验证，不删除实际 DOM 差异。',
        '- computed 命名空间：已声明源 getter 的值可用于直接 readonly filter/map/find/slice 等消费，改为 this.data.get；直接调用 getter、写入、mutator、动态／optional 调用仍不自动修复。',
        '- 运行恢复候选：只允许整个候选精确等于现有源 prop 默认值规则产物的情况。源、props/actions、浏览器及运行时指纹必须相同。只有 runtime 从 fail 到 pass、控件值和数量相等但位置仍不同，才允许诊断谱系前进；结构继续 fail，其他新增错误及原通过维度回退仍拒绝。',
        '- 未改生成／修复 Prompt，未替换 SSM＋模型生成路线，未新增整组件规则生成器，没有组件名称判断。','',
        '## 明确保留的问题','',
        '- select 初始空选中和 checkbox/radio boolean 属性未纳入新规则；不能由 input/textarea 的校准直接推断通过。',
        '- 依赖 props 的 data 初始化（如 source data 先 clone 再派生选择值）仍有真实时序缺陷：San 先计算 computed、后执行 inited；不能直接读取 initData 的 this.data，也不能任意给 getter 加 ||[] 掩盖问题。本轮恢复门只解决已证明的缺省值，不声称解决这类时序。',
        '- 所有其他真实缺失节点、动态键跨方法流、响应式写入及语法/事件问题按 remaining.json 保留。',
        '- 这不是新的模型生成通过率或独立测试证据。用户 API／Worker 尚未重启，不应把旧服务的任务当作 v7 运行。','',
        '## 证据','',
        '- ../composed_v7_verified_replay_20261119/：70 项离线规则；相对 v6 相同代码复用经哈希核验的捕获（capture 函数逐字相同），不同候选重新启动真实浏览器，逐项标注。',
        '- ../default_recovery_v7_20261119/：真实失败产物隔离默认值规则验证，保持结构失败，不冒充迁移通过。',
        '- migration_system/tests/test_remaining_repairs_v7.py：真实 DOM/live 控件/重置、computed 响应式、恢复门以及负例。','']
    write_once(OUTPUT/'summary.json',result);write_once(OUTPUT/'remaining.json',remaining)
    write_once(OUTPUT/'REPORT.md','\n'.join(lines))
    write_once(OUTPUT/'analysis.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{},'cells':[
        {'cell_type':'markdown','metadata':{},'source':'\n'.join(lines)},
        {'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
         'source':"import json\nfrom pathlib import Path\nsummary=json.loads(Path('summary.json').read_text(encoding='utf-8'))\nsummary"},
        {'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
         'source':"remaining=json.loads(Path('remaining.json').read_text(encoding='utf-8'))\nremaining"}]})
    # Preserve exact implementation bytes to keep subsequent iterations auditable.
    for relative,digest in read(REPLAY/'protocol.json')['implementation_sha256'].items():
        source=PROJECT/relative
        if hashed(source)!=digest:raise ValueError('implementation_changed_before_archiving')
        target=REPLAY/'implementation'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            if hashed(target)!=digest:raise ValueError('immutable_implementation_differs')
        else:shutil.copyfile(source,target)
    write_once(REPLAY/'IMPLEMENTATION_SHA256SUMS.txt',''.join(digest+'  implementation/'+relative+'\n'
        for relative,digest in sorted(protocol['implementation_sha256'].items())))
    write_once(OUTPUT/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(OUTPUT).as_posix()+'\n' for p in sorted(OUTPUT.rglob('*')) if p.is_file()))
    print(json.dumps(result,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
