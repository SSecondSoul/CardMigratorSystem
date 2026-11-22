"""Preserve a stopped precheck exactly before any implementation is edited."""
import shutil
from analyze_coverage import RUNS,read,write_once,hashed

PROJECT=RUNS.parent/'migration_system'
DEST=RUNS/'composed_v9_final_replay_20261120'
protocol=read(DEST/'protocol.json')
for relative,digest in protocol['implementation_sha256'].items():
    source=PROJECT/relative
    if hashed(source)!=digest:raise ValueError('original_precheck_implementation_unavailable:'+relative)
    target=DEST/'implementation'/relative;target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():raise ValueError('snapshot_already_exists')
    shutil.copyfile(source,target)
rows=[read(p) for p in DEST.glob('*/result.json')]
write_once(DEST/'interruption.json',{'scope':'stopped_incomplete_precheck_NOT_70_result',
    'completed_records':len(rows),'completed_passed':sum(bool(r['effective_passed']) for r in rows),
    'reason':'Native template fidelity ownership covered export-default but omitted valid top-level CommonJS Vue object exports. Preserve this version and add both export positive/ambiguity negative regressions before final replay.',
    'implementation_preserved':True,'model_calls':0,'cloud_database_access':False})
write_once(DEST/'partial-results.json',rows)
write_once(DEST/'STOPPED.md','# 中止的v9预检，不是完整70项结果\n\n通用模板归属识别漏掉顶层 `module.exports = {...}` 源组件，导致实际样本的新规则未触发。保留当前已完成结果、失败、截图及原实现快照；不纳入最终70项结果。后续在新目录以完整导出覆盖版本回归。\n')
write_once(DEST/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(DEST).as_posix()+'\n'
    for p in sorted(DEST.rglob('*')) if p.is_file()))
print({'completed_records':len(rows),'implementation_preserved':True,'complete':False})
