"""Prepare a review-only dependency interoperability proposal, never an implementation."""
import argparse
import json
import re
import shutil

from migration_pipeline.audit_v7_source_queue_contract import ROOT, NB, sha, seal, verify, write
from migration_pipeline.audit_native_ref_structure_v13 import OUT as V13

BASE = ROOT / 'data/experiments/analysis/formal_30_v4_dependency_protocol_draft_v1_input_20261114'
OUT = ROOT / 'data/experiments/analysis/formal_30_v4_dependency_protocol_draft_v1_20261114'
DOC = ROOT / 'docs/ir-design/native-ref-dependency-interop-v1-draft.md'
PLAN = ROOT / 'docs/ir-design/native-ref-dependency-interop-v1-review.json'


def freeze():
    verify(V13)
    prior = json.loads((V13 / 'audit.json').read_text(encoding='utf-8'))
    assert prior['stats']['refs']['mismatches'] == 4 and prior['stats']['structure']['mismatches'] == 2
    protected = {**prior['protected_files_sha256'], **prior['code_sha256']}
    for n in ['migration_pipeline/utils/v7_integration_contract.py', 'local_server/api/evaluation_routes.py']:
        protected[n] = sha(ROOT / n)
    for n, expected in protected.items(): assert sha(ROOT / n) == expected, n
    BASE.mkdir(exist_ok=False)
    shutil.copy2(NB, BASE / 'notebook_before.ipynb')
    write(BASE / 'protected_files.json', protected)
    write(BASE / 'baseline.json', {'source_bundle': V13.relative_to(ROOT).as_posix(),
                                 'stats': prior['stats'], 'expanded_cleanup_mismatches': 1,
                                 'production_eligible': False, 'design_approval': 'pending'})
    seal(BASE); verify(BASE)
    print('Frozen V13 evidence pointers, 98-cell Notebook and production/manual fingerprints.')


def finalize():
    from migration_pipeline.audit_v7_dynamic_shape import BASE as FROZEN_INPUTS
    verify(BASE); verify(V13); verify(FROZEN_INPUTS)
    old = json.loads((BASE / 'notebook_before.ipynb').read_text(encoding='utf-8'))
    assert json.loads(NB.read_text(encoding='utf-8')) == old, 'Notebook changed; never overwrite'
    protected = json.loads((BASE / 'protected_files.json').read_text(encoding='utf-8'))
    for n, expected in protected.items(): assert sha(ROOT / n) == expected, n
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    assert plan['status'] == 'draft_awaiting_review' and plan['user_approval'] == 'pending'
    assert plan['implementation_status'] == 'not_implemented' and plan['production_eligible'] is False
    assert plan['source_equivalence_proven'] is False and plan['existing_application_scope_unchanged'] is True
    assert plan['scope'] == 'isolated_explicit_input_provider_public_api_feasibility_only'
    assert plan['feasibility_claim'] == 'unproven_for_vue_2_7_public_apis'
    assert [g['id'] for g in plan['gates']] == ['P0', 'P1', 'P2', 'P3', 'P4', 'P5']
    assert [g['status'] for g in plan['gates']] == ['pending', *(['not_run'] * 5)]
    vectors = plan['acceptance_vectors']
    assert len(vectors) == 14 and len({v['id'] for v in vectors}) == 14
    assert all(v['status'] == 'not_run' and v['gate'] in {'P1', 'P2', 'P3', 'P4', 'P5'} for v in vectors)
    required_cases = {'native_deep_ref_nested_property_dependency', 'native_deep_ref_array_element_dependency',
                      'native_new_property_dependency_still_private'}
    assert required_cases <= {v['case'] for v in vectors}
    for v in vectors:
        if 'prior_evidence' in v: assert (V13 / v['prior_evidence']).is_file(), v['id']
    prior = json.loads((V13 / 'audit.json').read_text(encoding='utf-8'))
    assert plan['baseline'] == {'ref_pairs': 192, 'ref_mismatches': prior['stats']['refs']['mismatches'],
                               'structure_pairs': 116, 'structure_mismatches': prior['stats']['structure']['mismatches'],
                               'lifecycle_cleanup_mismatches': prior['expanded_cleanup_mismatches']}
    assert json.loads((V13 / 'forged_pass_gate.json').read_text(encoding='utf-8'))['should_stop']
    doc = DOC.read_text(encoding='utf-8')
    for heading in range(1, 11): assert re.search(r'^## ' + str(heading) + r'\.', doc, re.M)
    assert 'DRAFT / 未批准 / 未实现 / 不可用于生产放行' in doc
    source = ROOT / 'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js'
    assert sha(source) == sha(FROZEN_INPUTS / 'vue.js')
    source_text = source.read_text(encoding='utf-8')
    anchors = {}
    for name, pattern in [('property_deps', r'function defineReactive\('), ('array_deps', r'function dependArray\('),
                          ('watch_api', r'function doWatch\('), ('watcher_get', r'Watcher.prototype.get ='),
                          ('watcher_cleanup', r'Watcher.prototype.cleanupDeps ='), ('internal_effect', r'function effect\(fn, scheduler\)')]:
        matches = list(re.finditer(pattern, source_text)); assert len(matches) == 1, name
        anchors[name] = {'line': source_text[:matches[0].start()].count('\n') + 1, 'pattern': pattern}
    assert "watcher.update = watcher.run;" in source_text
    position = source_text.index('function effect(fn, scheduler)')
    assert 'internal testing' in source_text[position - 220:position]
    OUT.mkdir(exist_ok=False)
    write(OUT / 'source_anchors.json', {'source': source.relative_to(ROOT).as_posix(), 'sha256': sha(source),
                                       'frozen_runtime_bundle': FROZEN_INPUTS.relative_to(ROOT).as_posix(), 'anchors': anchors,
                                       'evidence_level': 'static_source_inspection_not_runtime_feasibility'})
    files = [DOC, PLAN, ROOT / 'migration_pipeline/prepare_native_dependency_protocol_draft_v1.py']
    fingerprints = {p.relative_to(ROOT).as_posix(): sha(p) for p in files}
    for p in files:
        dest = OUT / 'code' / p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, dest)
    audit = {'recorded_at': '2026-11-14', 'status': 'draft_awaiting_review', 'approval': 'pending',
             'implementation_status': 'not_implemented', 'evidence_level': 'static_only', 'production_eligible': False,
             'model_calls': 0, 'new_runtime_experiments': 0, 'new_runtime_tests': 0,
             'gate_count': len(plan['gates']), 'acceptance_vector_count': len(vectors),
             'prior_runtime_test_count_referenced_not_rerun': sum(t['count'] for t in prior['tests']),
             'prior_notebook_cells': len(old['cells']), 'protected_files_sha256': protected, 'design_files_sha256': fingerprints,
             'original_scores_modified': False, 'production_files_changed': False, 'acceptance_ui_changed': False,
             'baseline_stats_unchanged': prior['stats'], 'lifecycle_mismatch_unchanged': 1}
    write(OUT / 'audit.json', audit)
    write(OUT / 'review_checklist.json', plan)
    report = f'''## 2026-11-14：显式原生依赖互操作协议 v1 草案（待审核，未实现）

本步按验证报告技能核对V13冻结证据、固定Vue源码与现有V7应用声明，形成可审核的设计与验收清单；没有新增运行时实验、没有实现provider，更没有放行生产。

- 设计：`{DOC.relative_to(ROOT).as_posix()}`；结构化清单：`{PLAN.relative_to(ROOT).as_posix()}`。状态均为draft／approval pending／not implemented。
- 明确输入提供方、San迁移端、宿主与独立门禁三方职责；概念接口为describe／open／capture／dispose，不是现成或已实现的Vue接口。
- 关键要求：保留Ref／value身份，旧别名依赖保留到源匹配重收集位置，provider只递交失效、不执行业务回调；生命周期代际与captureEpoch分开；异常部分收集状态、共享订阅与子组件同身份缓存传播必须有源对照。
- 受审公开Vue订阅API只作为输入端候选路线。静态源码显示sync会调用run/get重收集，pre/post使用另一队列，不能直接假定时序匹配。冻结构建导出的Vue.effect旁注明确仅内部测试，本稿不以此绕过公开API约束。
- 不改全局tracking／框架原型，不加重复观察器，不复制／代理／轮询，不暗用Vue watch/effect替San实现观察；现有V7错误profile不等于依赖provider批准，不缩小原公开值域。未知域依然是未履行契约，不是通过。
- 六个阶段门P0—P5、14个验收向量，全部待审核／待测；覆盖原Ref4点、新结构属性2点、旧别名时序、capture异常、真实父子缓存、多owner／晚到通知、未知provider、生命周期与伪造通过。清单校验通过仅为静态文档一致性，不代表这些向量已运行。
- 旧Ref192点仍有4差异，新结构116点仍有2差异，旧生命周期差异仍为1；上轮205项测试仅引用、未重跑。原批24/30通过、6失败、0执行错误、1,821,544 tokens不变。
- 生产、实验实现、人工验收配置指纹保持，0模型调用，未启动服务器／浏览器，无新增人工通过声明。仅新增设计／整理脚本及Notebook追加，旧98单元与metadata保留。

证据：`{OUT.relative_to(ROOT).as_posix()}`；设计前副本：`{BASE.relative_to(ROOT).as_posix()}`。当前证据等级为**static_only**，JSON与代码单元核对不代表Notebook UI渲染。请求的下一步授权仅为按草案开展输入端显式公开API隔离可行性原型，仍不接生产／不改部署依赖；在确认和可行性证据前不实施provider。若公开API不满足时序等条件则保留阻断、提交设计决策，不暗换内部接口。
'''
    with (OUT / 'REPORT.md').open('x', encoding='utf-8') as stream: stream.write(report)
    for n, expected in protected.items(): assert sha(ROOT / n) == expected, n
    for n, expected in fingerprints.items(): assert sha(ROOT / n) == expected, n
    seal(OUT); verify(OUT)
    append_notebook(old, report)
    print(json.dumps({k: v for k, v in audit.items() if k not in {'protected_files_sha256', 'design_files_sha256'}}, ensure_ascii=False))


def append_notebook(old, report):
    check = f'''from pathlib import Path
import json,hashlib
root=next(p for p in [Path.cwd(),*Path.cwd().parents] if (p/'migration_pipeline').is_dir())
folder=root/'{OUT.relative_to(ROOT).as_posix()}'
base=root/'{BASE.relative_to(ROOT).as_posix()}'
for d in [folder,base]:
    for line in (d/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected,name=line.split('  ',1)
        assert hashlib.sha256((d/name).read_bytes()).hexdigest()==expected,name
a=json.loads((folder/'audit.json').read_text(encoding='utf-8'))
p=json.loads((folder/'review_checklist.json').read_text(encoding='utf-8'))
assert a['evidence_level']=='static_only' and a['approval']=='pending' and not a['production_eligible']
assert a['implementation_status']=='not_implemented' and a['new_runtime_experiments']==a['new_runtime_tests']==a['model_calls']==0
assert p['user_approval']=='pending' and len(p['acceptance_vectors'])==14
assert all(v['status']=='not_run' for v in p['acceptance_vectors'])
assert a['baseline_stats_unchanged']['refs']['mismatches']==4 and a['baseline_stats_unchanged']['structure']['mismatches']==2
old=json.loads((base/'notebook_before.ipynb').read_text(encoding='utf-8'))
nb=json.loads((root/'{NB.relative_to(ROOT).as_posix()}').read_text(encoding='utf-8'))
assert nb['cells'][:len(old['cells'])]==old['cells'] and nb['metadata']==old['metadata']
print({{'design':'pending_review','implementation':'none','acceptance_vectors':14,'production':'blocked'}})
'''
    assert json.loads(NB.read_text(encoding='utf-8')) == old
    old['cells'].extend([
        {'cell_type': 'markdown', 'id': 'native-dependency-protocol-draft-v1-20261114', 'metadata': {}, 'source': report.splitlines(keepends=True)},
        {'cell_type': 'code', 'id': 'native-dependency-protocol-draft-v1-check-20261114', 'metadata': {}, 'execution_count': None,
         'outputs': [], 'source': check.splitlines(keepends=True)}])
    assert old['nbformat'] == 4 and len({c['id'] for c in old['cells']}) == len(old['cells'])
    for c in old['cells']:
        if c['cell_type'] == 'code': compile(''.join(c['source']), c['id'], 'exec')
    NB.write_text(json.dumps(old, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    exec(compile(check, 'draft-static-readonly', 'exec'), {})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-input', action='store_true'); parser.add_argument('--finalize', action='store_true')
    args = parser.parse_args()
    if args.freeze_input == args.finalize: parser.error('Choose exactly one action')
    freeze() if args.freeze_input else finalize()
