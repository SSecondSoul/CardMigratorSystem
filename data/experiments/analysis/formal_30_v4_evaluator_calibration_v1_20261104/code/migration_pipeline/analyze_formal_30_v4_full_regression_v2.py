"""Audit immutable full-30 outcomes and gate/validator boundaries; no repairs or model calls."""
import argparse
import json
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot, outcome
from migration_pipeline.analyze_formal_30_v4_repair_scheduling import progress_code_hash
from migration_pipeline.utils.bounded_semantics import inspect_semantics

BATCH = 'formal_30_v4_full_regression_v2'

CLONE_AUDIT_JS = r'''
const fs=require('fs'),parser=require('@babel/parser');
const data=JSON.parse(fs.readFileSync(0,'utf8'));
const script=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(data.code)?.[1];
if(!script)throw Error('Missing script');
const ast=parser.parse(script,{sourceType:'unambiguous'});
const key=n=>!n.computed&&(n.key?.name||n.key?.value);
const roots=ast.program.body.flatMap(n=>{
 const a=n.type==='ExpressionStatement'&&n.expression;
 return a?.type==='AssignmentExpression'&&a.left.type==='MemberExpression'&&!a.left.computed
  &&a.left.object.name==='module'&&a.left.property.name==='exports'&&a.right.type==='CallExpression'
  &&a.right.callee.type==='MemberExpression'&&a.right.callee.object.name==='san'
  &&a.right.callee.property.name==='defineComponent'?[a.right.arguments[0]]:[];
});
if(roots.length!==1||roots[0]?.type!=='ObjectExpression')throw Error('Ambiguous exported parent');
const methods=roots[0].properties.filter(p=>key(p)==='simulateDataUpdate');
if(methods.length!==1||methods[0].type!=='ObjectMethod')throw Error('Ambiguous update method');
const fn=methods[0];
function walk(n,f){if(!n||typeof n!=='object')return;if(Array.isArray(n)){n.forEach(x=>walk(x,f));return;}
 f(n);for(const[k,v]of Object.entries(n))if(!['loc','extra','comments'].includes(k))walk(v,f);}
const fieldCall=(n,action,field)=>n?.type==='CallExpression'&&n.callee.type==='MemberExpression'
 &&!n.callee.computed&&n.callee.object.type==='MemberExpression'&&!n.callee.object.computed
 &&n.callee.object.object.type==='ThisExpression'&&n.callee.object.property.name==='data'
 &&n.callee.property.name===action&&n.arguments[0]?.value===field;
const declaration=fn.body.body.flatMap(s=>s.type==='VariableDeclaration'?s.declarations:[])
 .filter(n=>n.id.name==='kpiData');
const init=declaration.length===1&&declaration[0].init;
const map=init?.type==='CallExpression'&&init.callee.type==='MemberExpression'&&!init.callee.computed
 &&init.callee.property.name==='map'&&fieldCall(init.callee.object,'get','kpiData')&&init.arguments.length===1;
const cb=map&&init.arguments[0],obj=cb?.body;
const cloned=cb?.type==='ArrowFunctionExpression'&&!cb.async&&cb.params.length===1&&cb.params[0].type==='Identifier'
 &&obj.type==='ObjectExpression'&&obj.properties.length===1&&obj.properties[0].type==='SpreadElement'
 &&obj.properties[0].argument.type==='Identifier'&&obj.properties[0].argument.name===cb.params[0].name;
const assignments=[],commits=[];let unexpected=false;
walk(fn.body,n=>{
 if(n.type==='AssignmentExpression'){
  const a=n.left,b=a?.object;
  if(b?.type==='MemberExpression'&&b.object.name==='kpiData'){
   const scalar=n.operator==='='&&a.type==='MemberExpression'&&!a.computed&&a.property.name==='value'
    &&b.computed&&b.property.type==='NumericLiteral';
   assignments.push({text:script.slice(n.start,n.end),scalar,index:b.property.value,start:n.start});
   if(!scalar)unexpected=true;
  }else if(script.slice(a.start,a.end).includes('kpiData'))unexpected=true;
 }
 if(fieldCall(n,'set','kpiData'))commits.push({same_alias:n.arguments.length===2&&n.arguments[1].name==='kpiData',
  text:script.slice(n.start,n.end),start:n.start});
});
const ordered=commits.length===1&&assignments.length>0&&commits[0].same_alias
 &&assignments.every(a=>a.scalar&&a.start<commits[0].start)&&fn.body.body.some(s=>s.type==='ExpressionStatement'
 &&fieldCall(s.expression,'set','kpiData'));
assignments.forEach(a=>delete a.start);
process.stdout.write(JSON.stringify({element_object_clone:!!cloned,assignments,commits,
 local_scalar_writes_are_on_cloned_records:!!cloned&&ordered&&!unexpected,
 boundary:'Only these direct local numeric-index .value assignments on ordinary records and explicit commit; '
  +'not deep-clone, proxy/accessor or arbitrary helper-call equivalence.'}));
'''


def clone_audit(code):
    p = subprocess.run(['node', '-e', CLONE_AUDIT_JS], cwd=ROOT, input=json.dumps({'code': code}),
        capture_output=True, text=True, encoding='utf-8', timeout=20)
    if p.returncode:
        raise RuntimeError(p.stderr)
    return json.loads(p.stdout)


def default_fields(issues):
    fields = set()
    for issue in issues:
        if issue['code'] != 'missing_prop_defaults':
            continue
        match = re.fullmatch(r'以下带默认值的 Vue props 未在 San initData 中落地：([^。]+)。', issue['message'])
        if not match:
            raise ValueError('Unsupported diagnostic shape; do not infer a field-subset proof')
        fields.update(s.strip() for s in match[1].split(','))
    return fields


def transition(before, after):
    return ('kept_pass' if before == after == 'pass' else 'regressed_to_fail' if before == 'pass'
            else 'improved_to_pass' if after == 'pass' else 'still_not_pass')


def audit(snapshot):
    snapshot = snapshot.resolve()
    checked = verify_snapshot(snapshot)
    summary_path = snapshot / f'{BATCH}_summary.json'
    current = json.loads(summary_path.read_text(encoding='utf-8'))
    config = json.loads((snapshot / f'{BATCH}.json').read_text(encoding='utf-8'))
    baselines = {name: json.loads((snapshot / f'protocol/baseline_{name}_summary.json').read_text(encoding='utf-8'))
                 for name in ('v3', 'v4')}
    if current['batch_id'] != BATCH or len(current['samples']) != 30 or [s['id'] for s in current['samples']] != [s['id'] for s in config['samples']]:
        raise RuntimeError('Expected the ordered full-30 batch')
    old = {k: {s['id']: s for s in b['samples']} for k, b in baselines.items()}
    rows, states = [], {}
    for sample in current['samples']:
        if sample['status'] != 'completed':
            raise RuntimeError('Execution errors require separate accounting')
        folder = snapshot / 'pipeline' / sample['complexity']
        report_path = snapshot / 'repair_reports' / sample['complexity'] / Path(sample['report_file']).name
        report = json.loads(report_path.read_text(encoding='utf-8'))
        state = report['state']; states[sample['id']] = state
        repairs, norms = state['repair_history'], state['normalization_history']
        for key in ('final_passed', 'repair_rounds', 'stop_reason', 'llm_repair_calls', 'deterministic_steps', 'retained_previous_candidate'):
            if sample[key] != state[key] or sample[key] != report['summary'][key]:
                raise RuntimeError(f'Summary/state mismatch: {sample["id"]}/{key}')
        if len(repairs) != sample['llm_repair_calls'] or len(norms) != sample['deterministic_steps']:
            raise RuntimeError('History counter mismatch')
        final = folder / Path(sample['final_file_path']).name
        code = final.read_text(encoding='utf-8')
        if code != state['generated_code'] or code != state['final_code']:
            raise RuntimeError('Final artifact mismatch')
        val, vis = state['final_validate_result'], state['final_visual_eval_result']
        for errors, expected in ((val['validation_errors'], sample['final_validation_error_codes']),
                                 (vis['visual_eval_errors'], sample['final_visual_error_codes'])):
            if Counter(i['code'] for i in errors) != Counter(expected):
                raise RuntimeError('Final issue accounting mismatch')
        if bool(val['validation_passed'] and vis['visual_eval_passed']) != sample['final_passed']:
            raise RuntimeError('Final pass mismatch')
        for entry in repairs:
            path = folder / Path(entry['repair_result']['repaired_file_path']).name
            if (path.read_text(encoding='utf-8') != entry['repair_result']['repaired_code']
                    or progress_code_hash(path) != entry['progress_signature']['generated_code_sha256']):
                raise RuntimeError('Repair candidate signature mismatch')
        for entry in norms:
            path = folder / Path(entry['candidate_file']).name
            if progress_code_hash(path) != entry['progress_signature']['generated_code_sha256']:
                raise RuntimeError('Normalization candidate signature mismatch')
        if sample['retained_previous_candidate']:
            rejected = folder / Path(state['rejected_candidate_file']).name
            if not repairs[-1]['repair_regression_rejected'] or not repairs[-1]['repair_regression_gate']['should_stop']:
                raise RuntimeError('Rollback gate not reproduced')
            if rejected.read_text(encoding='utf-8') != repairs[-1]['repair_result']['repaired_code']:
                raise RuntimeError('Rejected candidate mismatch')
            kept = next((n for n in reversed(norms) if n['accepted']), None)
            expected_code = (folder / Path(kept['candidate_file']).name).read_text(encoding='utf-8') if kept else state['generate_result']['generation_code']
            if len(repairs) != 1 or code != expected_code:
                raise RuntimeError('This audit expects first-call rollback to the retained prepass/initial artifact')
        else:
            candidates = [h['repair_result']['repaired_code'] for h in repairs if not h['repair_regression_rejected']]
            candidates += [(folder / Path(n['candidate_file']).name).read_text(encoding='utf-8') for n in norms if n['accepted']]
            candidates.append(state['generate_result']['generation_code'])
            if code not in candidates:
                raise RuntimeError('Final code not found among accepted/initial candidates')
        generation = state['generation_usage']['total_tokens']
        repair = sum(h['repair_result']['usage']['total_tokens'] for h in repairs)
        if (sample['generation_tokens'], sample['repair_tokens'], sample['total_tokens']) != (generation, repair, generation + repair):
            raise RuntimeError('Per-sample token mismatch')
        row = {k: sample.get(k) for k in ('id', 'component_name', 'complexity', 'final_passed', 'initial_validation_passed',
            'stop_reason', 'llm_repair_calls', 'deterministic_steps', 'retained_previous_candidate',
            'final_structure_similarity', 'generation_tokens', 'repair_tokens', 'total_tokens', 'elapsed_seconds',
            'interaction_eval_passed')}
        row.update({'final_file': final.name, 'final_sha256': digest(final), 'history_sha256': digest(report_path),
            'validation_issues': val['validation_errors'], 'visual_issues': vis['visual_eval_errors'],
            'final_warnings': val['validation_warnings'],
            'comparisons': {k: {'before': outcome(old[k][sample['id']]), 'after': outcome(sample),
                               'transition': transition(outcome(old[k][sample['id']]), outcome(sample))} for k in baselines},
            'normalizations': norms,
            'repairs': [{'attempt': h['repair_attempt'], 'passed': h['passed'], 'rejected': h['repair_regression_rejected'],
                'gate': h['repair_regression_gate'], 'issues': h['validate_result']['validation_errors'],
                'visual_passed': h['visual_eval_passed'], 'postprocessing': h['repair_result']['raw_response'].get('pipeline_postprocessing', [])} for h in repairs]})
        rows.append(row)
    agg = current['aggregate']
    if (sum(r['final_passed'] for r in rows), len(rows), agg['execution_errors']) != (agg['passed'], agg['completed'], 0):
        raise RuntimeError('Aggregate outcome mismatch')
    for key in ('generation_tokens', 'repair_tokens', 'total_tokens'):
        if sum(r[key] for r in rows) != agg[key]:
            raise RuntimeError('Aggregate token mismatch')
    for level in ('simple', 'medium', 'complex'):
        selected = [r for r in rows if r['complexity'] == level]
        if len(selected) != 10 or sum(r['final_passed'] for r in selected) != agg['by_complexity'][level]['passed']:
            raise RuntimeError('Stratum aggregate mismatch')
    rule = next(r for r in rows if r['id'] == 'rule_builder')
    before_fields, after_fields = default_fields(rule['validation_issues']), default_fields(rule['repairs'][0]['issues'])
    if not after_fields < before_fields:
        raise RuntimeError('Grouped default diagnostic did not shrink; narrative needs review')
    mon = states['MonitoringDashboard']
    source = snapshot / 'protocol/frozen/data/datasets/components/03_complex/MonitoringDashboard/vue/MonitoringDashboard.vue'
    semantics = inspect_semantics(mon['final_code'], source.read_text(encoding='utf-8'), ssm=mon['ssm'])
    clone = clone_audit(mon['final_code'])
    if not clone['local_scalar_writes_are_on_cloned_records']:
        raise RuntimeError('Clone finding not reproduced')
    transitions = {k: dict(Counter(r['comparisons'][k]['transition'] for r in rows)) for k in baselines}
    verify_snapshot(snapshot)
    return {'classification': 'paired_reused_development_full_regression_with_separate_evaluator_review',
        'source_snapshot': snapshot.relative_to(ROOT).as_posix(), 'verified_files': checked,
        'source_summary_sha256': digest(summary_path), 'aggregate': agg,
        'baseline_aggregates': {k: b['aggregate'] for k, b in baselines.items()}, 'transition_counts': transitions,
        'wall_elapsed_seconds': (datetime.fromisoformat(current['updated_at']) - datetime.fromisoformat(current['started_at'])).total_seconds(),
        'llm_calls_total': sum(r['llm_repair_calls'] for r in rows),
        'deterministic_steps_total': sum(r['deterministic_steps'] for r in rows),
        'deterministic_steps_accepted': sum(n['accepted'] for r in rows for n in r['normalizations']),
        'regression_rollbacks': sum(r['retained_previous_candidate'] for r in rows),
        'zero_llm_passes': sum(r['final_passed'] and not r['llm_repair_calls'] for r in rows),
        'model_requests_by_analysis': 0, 'browser_test_performed': False, 'original_score_modified': False,
        'production_code_modified': False, 'independent_holdout': False,
        'rule_builder_gate_review': {'before_missing_defaults': sorted(before_fields), 'after_missing_defaults': sorted(after_fields),
            'old_diagnostic_shrank_but_message_identity_was_new': True, 'candidate_still_has_validation_errors': True,
            'boundary': 'Review grouped diagnostic identity, not a blanket waiver for new missing defaults.'},
        'monitoring_review': {'source_semantics': {k: v for k, v in semantics.items() if k not in ('code', 'wrappers')},
            'clone_audit': clone,
            'persistence_note': 'The actual write is inside try/catch. Current bare-tail proof refuses that shape; '
               'not a missing-write observation. Exception propagation differs from the unguarded source and needs a separate equivalence policy.'},
        'samples': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    args = parser.parse_args()
    data = audit(args.snapshot)
    output = ROOT / 'data/experiments/analysis' / Path(data['source_snapshot']).name.replace('_results_', '_')
    if output.exists():
        raise FileExistsError('Do not replace a previous analysis')
    output.mkdir(parents=True)
    (output / 'summary.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'analysis': output.relative_to(ROOT).as_posix(), 'verified_files': data['verified_files'],
        'passed': data['aggregate']['passed'], 'failed': data['aggregate']['failed'],
        'transition_counts': data['transition_counts'], 'model_requests': 0}))


if __name__ == '__main__':
    main()
