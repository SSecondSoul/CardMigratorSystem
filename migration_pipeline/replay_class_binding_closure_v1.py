"""Offline class-binding closure evidence. No server, browser or model calls."""
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess

from migration_pipeline.audit_class_binding_closure_v1 import BASELINE, ROOT, TARGETS
from migration_pipeline.analyze_formal_30_v4_full_regression import digest, verify_snapshot

OUTPUT = BASELINE.with_name('formal_30_v4_class_binding_closure_v1_20261113')
LEGACY = BASELINE.with_name('formal_30_v4_class_binding_legacy_guard_pre_fix_20261113')
NOTEBOOK = ROOT / 'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
CHANGED = [*TARGETS, 'migration_pipeline/orchestrator.py']
NEW = ['migration_pipeline/utils/class_binding_contract.py',
       'migration_pipeline/utils/class_binding_semantics.py', 'migration_pipeline/utils/class_binding_semantics.cjs',
       'migration_pipeline/audit_class_binding_closure_v1.py',
       'migration_pipeline/replay_class_binding_closure_v1.py', 'tests/test_class_binding_closure_v1.py']
SUITES = ['tests.test_class_binding_closure_v1', 'tests.test_source_template_closure',
          'tests.test_migration_pipeline_regressions', 'tests.test_repair_prompt_and_loop',
          'tests.test_bounded_repair_scheduler', 'tests.test_repair_regression_guard',
          'tests.test_semantic_regression_gate']


def write_json(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2); stream.write('\n')


def prefix_hash(nb):
    return hashlib.sha256(json.dumps(nb['cells'], ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def run_tests(retest=False):
    folder=OUTPUT/'verification_run_2' if retest else OUTPUT
    if folder.exists(): raise FileExistsError('Never overwrite earlier test evidence')
    verify_snapshot(BASELINE.resolve()); verify_snapshot(LEGACY.resolve())
    folder.mkdir(parents=True, exist_ok=False)
    if not retest: shutil.copy2(NOTEBOOK, OUTPUT / 'notebook_before.ipynb')
    results=[]
    for suite in SUITES:
        print('Testing ' + suite, flush=True)
        proc=subprocess.run(['python','-m','unittest',suite,'-v'],cwd=ROOT,
            text=True,encoding='utf-8',capture_output=True)
        log=proc.stdout+proc.stderr
        with (folder / (suite.rsplit('.',1)[1]+'.log')).open('x',encoding='utf-8') as stream: stream.write(log)
        count=re.search(r'Ran (\d+) tests? in ([\d.]+)s',log)
        result={'suite':suite,'returncode':proc.returncode,'tests':int(count[1]) if count else None,
                'seconds':float(count[2]) if count else None}
        results.append(result); print(json.dumps(result),flush=True)
    write_json(folder/'tests.json',results)
    if any(r['returncode'] for r in results): raise RuntimeError('Test failure retained; inspect logs before finalizing')


def verify_final():
    """One process, one exact code fingerprint; preserve all previous logs."""
    folder=OUTPUT/'verification_final';folder.mkdir(parents=True,exist_ok=False)
    hashes={name:digest(ROOT/name) for name in [*CHANGED,*NEW]}
    print('Final verification: '+str(len(SUITES))+' modules, no model calls',flush=True)
    proc=subprocess.run(['python','-m','unittest',*SUITES,'-v'],cwd=ROOT,
        text=True,encoding='utf-8',capture_output=True)
    log=proc.stdout+proc.stderr
    with (folder/'unittest.log').open('x',encoding='utf-8') as stream: stream.write(log)
    count=re.search(r'Ran (\d+) tests? in ([\d.]+)s',log)
    result={'suite':'combined_seven_modules','modules':SUITES,'returncode':proc.returncode,
            'tests':int(count[1]) if count else None,'seconds':float(count[2]) if count else None}
    write_json(folder/'tests.json',[result]);write_json(folder/'code_sha256.json',hashes)
    assert hashes=={name:digest(ROOT/name) for name in hashes}, 'Code changed while final tests ran'
    print(json.dumps(result),flush=True)
    if proc.returncode: raise RuntimeError('Final verification failed; evidence retained')


def finalize():
    from migration_pipeline.stages.validate import ValidateStage,ValidateStageInput
    from migration_pipeline.stages.repair import RepairStage
    from migration_pipeline.utils.class_binding_semantics import class_binding_semantics,class_binding_regression
    from tests.test_class_binding_closure_v1 import native_states
    if (OUTPUT/'audit.json').exists(): raise FileExistsError('Never overwrite finalized evidence')
    tests=json.loads((OUTPUT/'verification_final/tests.json').read_text(encoding='utf-8'))
    if any(t['returncode'] for t in tests): raise RuntimeError('Tests must pass before final evidence')
    hashes=json.loads((OUTPUT/'verification_final/code_sha256.json').read_text(encoding='utf-8'))
    assert hashes=={name:digest(ROOT/name) for name in hashes}, 'Final test/code drift'
    old=json.loads((BASELINE/'audit.json').read_text(encoding='utf-8'))
    verify_snapshot(BASELINE.resolve());verify_snapshot(LEGACY.resolve())
    drift=[n for n,h in old['old_inventory'].items() if digest(ROOT/n)!=h and n not in CHANGED]
    if drift: raise RuntimeError('Unexpected inventory drift: '+str(drift))
    source=ROOT/old['source_reference'];candidate=ROOT/old['candidate_reference']
    code=candidate.read_text(encoding='utf-8');vue=source.read_text(encoding='utf-8')
    before=ValidateStage().run(ValidateStageInput(generated_code=code,vue_file_path=str(source)))
    fixed,steps=RepairStage._deterministic_repair_plan(code,before.validation_errors,[],{},str(source))
    if fixed==code: raise RuntimeError('Real deterministic prepass did not repair the frozen candidate')
    after=ValidateStage().run(ValidateStageInput(generated_code=fixed,vue_file_path=str(source)))
    analysis=class_binding_semantics(fixed,vue)
    assert not analysis.get('error') and not analysis['findings']
    assert not after.validation_passed, 'Other source watcher boundaries must remain blocking'
    assert fixed.split('</template>')[1]==code.split('</template>')[1]
    assert class_binding_regression(fixed,code,vue,[])['should_stop']
    with (OUTPUT/'TaskManager_class_binding_offline.san').open('x',encoding='utf-8',newline='') as stream: stream.write(fixed)
    nb=json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    previous=json.loads((OUTPUT/'notebook_before.ipynb').read_text(encoding='utf-8'))
    assert nb==previous, 'Notebook changed while tests ran; do not overwrite editor changes'
    # Historical cells intentionally retain their exact live-code fingerprints.
    # Execute readonly cells without weakening old assertions, and record drift.
    history=[]
    for cell in previous['cells']:
        if cell['cell_type']!='code': continue
        text=''.join(cell['source']);compile(text,str(cell.get('id','historical')),'exec')
        try:
            with redirect_stdout(io.StringIO()): exec(compile(text,'historical','exec'),{'__name__':'__main__'})
            history.append({'id':cell.get('id'),'status':'passed'})
        except Exception as exc:
            history.append({'id':cell.get('id'),'status':'failed','exception':type(exc).__name__,'message':str(exc)})
    data={'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'development_offline_class_contract_closure_not_independent_test',
        'issue':{'id':'class-map-prefix-escape','category':'production_defect','component':'TaskManager','framework':'san',
                 'symptom':'Initial dark styling despite false data; multi-key raw map interpreted as literal prefix.',
                 'root_cause':'Narrow regex plus gated single-key source comparison and permissive San compile.',
                 'verification':{'status':'automated_offline_only','manual_status':'awaiting_user'}},
        'baseline':str(BASELINE.relative_to(ROOT)),'legacy_baseline':str(LEGACY.relative_to(ROOT)),
        'source_reference':old['source_reference'],'candidate_reference':old['candidate_reference'],
        'validation_before':before.to_state_update(),'validation_after':after.to_state_update(),
        'analysis_after':{k:v for k,v in analysis.items() if k!='code'},'normalizations':steps,
        'native_before':native_states(code,('isDarkMode','isCompactMode')),
        'native_after':native_states(fixed,('isDarkMode','isCompactMode')),
        'production_files_changed':CHANGED,'new_code_files':NEW,'test_results':tests,'test_modules':SUITES,
        'earlier_test_runs':[json.loads((OUTPUT/p/'tests.json').read_text(encoding='utf-8')) for p in (Path('.'),Path('verification_run_2'))],
        'verification_adjustments':'Preserved earlier failures: old prompt compatibility wording/examples restored, non-class invalid script excluded from class proof, unsupported JS conditions refused. Existing assertions unchanged.',
        'historical_notebook_cells':history,'notebook_before_cells':len(previous['cells']),
        'notebook_prefix_sha256':prefix_hash(previous),'notebook_metadata':previous['metadata'],
        'previous_inventory':old['old_inventory'],'allowed_previous_inventory_drift':CHANGED+[str(NOTEBOOK.relative_to(ROOT)).replace('\\','/')],
        'old_manual_pages':old['old_manual_pages'],'original_aggregate':old['original_aggregate'],
        'model_requests':0,'original_score_modified':False,'browser_render_verified':False,
        'manual_pages_updated':False,'unsupported_boundary':'Dynamic keys, spreads, arbitrary calls, ambiguous scopes/registries or escaped inline literals are not guessed; full TaskManager still has source watcher blockers.'}
    write_json(OUTPUT/'audit.json',data)
    for name in [*CHANGED,*NEW]:
        target=OUTPUT/'code'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    passed=sum(t['tests'] for t in tests)
    failures=[h for h in history if h['status']=='failed']
    report=f'''# Conditional class binding closure v1 — 2026-11-13 发现，2026-11-14 验证

开发回归中的通用闭环改进，不是独立测试或完整组件通过证明。

- 用户报告 TaskManager 默认暗黑；冻结产物四种布尔组合均产生 `task-manager dark-theme`。
- 旧规则仅抓完整属性中的外层对象花括号，遗漏静态前缀后的裸多键 map；源比较仅支持单键且依赖其他错误触发。San 编译只接受了字面量前缀，因此编译通过不是语义通过。
- 生成和修复共用完整 class 约束；校验无条件分析父/内联模板；修复前后均用同一条源码匹配规则，且不依赖 residual_v2；两个调度策略均独立阻止条件 class 退化或隐藏诊断。
- 确定性改写只接受完整源码对象、字面量键、相同 DOM/循环/条件作用域、已知字段、静态 class 和全部条件。无法证明的情况不猜测修改。
- {passed}/{passed} 项定向回归通过（{len(SUITES)} 个测试模块）；San 原生 parser/Data/evaluator 覆盖 false/false、false/true、true/false、true/true、回到 false/false。不是浏览器重绘验证。此前失败日志保留，未删除或放宽旧测试。
- 原冻结 `.san`、测试页面及人工 manifest 均未改动。离线候选为 `TaskManager_class_binding_offline.san`，当前手工页面仍加载旧冻结产物。
- 完整 ValidateStage 仍不通过：保留源 watcher 动态键与异常策略边界；未修改原 24/30 结果、未调用模型。
- Notebook 原 {len(previous['cells'])} 单元完整保留。历史代码单元重新执行：{len(history)-len(failures)}/{len(history)} 通过，{len(failures)} 个失败详见 audit；旧单元的 live-code 指纹不会为这次授权修改而放宽。新增单元按冻结副本和明确变更白名单校验。
- 服务器端生成 Prompt 需重启本地服务才生效；新启动的批处理进程直接加载新校验与修复代码。尚未重启、未复跑模型、未人工宣告通过。
'''
    with (OUTPUT/'REPORT.md').open('x',encoding='utf-8') as stream: stream.write(report)
    markdown='## 2026-11-14：条件 class 漏检与通用闭环 v1（11-13 发现）\n\n'+report.split('\n',1)[1]
    check='''from pathlib import Path
import json, hashlib
root = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'migration_pipeline').is_dir())
folder = root / 'data/experiments/analysis/formal_30_v4_class_binding_closure_v1_20261113'
audit = json.loads((folder / 'audit.json').read_text(encoding='utf-8'))
for line in (folder / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
    expected, name = line.split('  ', 1)
    assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == expected, name
for name, expected in audit['previous_inventory'].items():
    if name not in audit['allowed_previous_inventory_drift']:
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
assert audit['native_after'] == ['task-manager', 'task-manager compact-mode', 'task-manager dark-theme', 'task-manager dark-theme compact-mode', 'task-manager']
assert all(t['returncode'] == 0 for t in audit['test_results'])
assert audit['model_requests'] == 0 and audit['original_score_modified'] is False
assert audit['manual_pages_updated'] is False and audit['browser_render_verified'] is False
assert audit['validation_after']['validation_passed'] is False  # unresolved watcher boundaries remain
current = json.loads((root / 'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb').read_text(encoding='utf-8'))
prefix = current['cells'][:audit['notebook_before_cells']]
assert hashlib.sha256(json.dumps(prefix, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest() == audit['notebook_prefix_sha256']
assert current['metadata'] == audit['notebook_metadata']
print({'targeted_tests': sum(t['tests'] for t in audit['test_results']), 'manual_recheck': 'pending', 'original_scores': 'unchanged'})
'''
    nb['cells'].extend([{'cell_type':'markdown','id':'class-binding-closure-v1-20261113','metadata':{},'source':markdown.splitlines(keepends=True)},
                        {'cell_type':'code','id':'class-binding-closure-v1-check-20261113','metadata':{},'source':check.splitlines(keepends=True),'execution_count':None,'outputs':[]}])
    # Notebook append is a mechanical artifact update, preserving all old cells.
    NOTEBOOK.write_text(json.dumps(nb,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
    files=sorted(p for p in OUTPUT.rglob('*') if p.is_file())
    with (OUTPUT/'SHA256SUMS.txt').open('x',encoding='utf-8') as stream:
        stream.write('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files)+'\n')
    current=json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    assert len({c['id'] for c in current['cells']})==len(current['cells'])
    for c in current['cells']:
        if c['cell_type']=='code': compile(''.join(c['source']),c['id'],'exec')
    exec(compile(check,'new-class-binding-readonly-check','exec'),{'__name__':'__main__'})
    print(json.dumps({'payloads':verify_snapshot(OUTPUT.resolve()),'tests':passed,'historical_cell_failures':failures,
        'notebook_cells':len(current['cells']),'validation_after':after.validation_passed},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-tests',action='store_true');parser.add_argument('--finalize',action='store_true')
    parser.add_argument('--retest',action='store_true')
    parser.add_argument('--verify-final',action='store_true')
    args=parser.parse_args()
    if args.run_tests: run_tests()
    elif args.retest: run_tests(retest=True)
    elif args.verify_final: verify_final()
    elif args.finalize: finalize()
    else: parser.error('Choose --run-tests or --finalize')
