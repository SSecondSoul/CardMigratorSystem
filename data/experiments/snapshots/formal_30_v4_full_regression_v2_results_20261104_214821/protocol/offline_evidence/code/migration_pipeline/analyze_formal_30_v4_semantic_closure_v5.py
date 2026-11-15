"""Read-only audit: preserve the recorded score and disclose persistence omission."""

import argparse
import json
import subprocess
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import digest, verify_snapshot
from migration_pipeline.analyze_formal_30_v4_repair_scheduling import progress_code_hash
from migration_pipeline.audit_formal_30_v4_notification_method import inspect_method
from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.run_formal_30_v4_semantic_closure_v5 import ROOT, BATCH_ID


AUDIT_JS = r'''
const fs=require('fs'),parser=require('@babel/parser');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const key=p=>!p.computed&&(p.key?.name||p.key?.value);
const one=(obj,name)=>{
 const rows=obj?.properties?.filter(p=>key(p)===name)||[];
 if(rows.length>1)throw Error('Ambiguous option: '+name);
 return rows[0];
};
function root(code,source){
 const match=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code);
 if(!match)throw Error('Missing script');
 const text=match[1],ast=parser.parse(text,{sourceType:'unambiguous'});
 const nodes=ast.program.body.flatMap(n=>{
  if(source&&n.type==='ExportDefaultDeclaration')return [n.declaration];
  const e=n.type==='ExpressionStatement'&&n.expression;
  if(e?.type==='AssignmentExpression'&&e.operator==='='&&e.left.type==='MemberExpression'
    &&!e.left.computed&&e.left.object.name==='module'&&e.left.property.name==='exports'){
   if(source)return [e.right];
   if(e.right.type==='CallExpression'&&e.right.callee.type==='MemberExpression'
     &&!e.right.callee.computed&&e.right.callee.object.name==='san'
     &&e.right.callee.property.name==='defineComponent')return e.right.arguments;
  }return [];
 });
 if(nodes.length!==1||nodes[0].type!=='ObjectExpression')throw Error('Ambiguous exported parent');
 return {parent:nodes[0],text,offset:code.slice(0,match.index+match[0].indexOf('>')+1).split('\n').length-1};
}
function walk(node,fn){
 if(!node||typeof node!=='object')return;
 if(Array.isArray(node)){node.forEach(n=>walk(n,fn));return;}
 fn(node);for(const [k,v]of Object.entries(node))if(!['loc','extra','comments','tokens'].includes(k))walk(v,fn);
}
function writes(ctx,node){
 const rows=[];walk(node,n=>{
  const c=n.type==='CallExpression'&&n.callee;
  if(c?.type==='MemberExpression'&&!c.computed&&c.object.name==='localStorage'&&c.property.name==='setItem')
   rows.push({key:n.arguments[0]?.value??null,expression:ctx.text.slice(n.start,n.end),line:n.loc.start.line+ctx.offset});
 });return rows;
}
function direct(ctx,method){
 if(!method)return [];
 if(method.type!=='ObjectMethod'||method.params.length)throw Error('Unsupported hook');
 return method.body.body.flatMap(s=>{
  const c=s.type==='ExpressionStatement'&&s.expression,f=c?.callee;
  return c?.type==='CallExpression'&&f?.type==='MemberExpression'&&!f.computed&&f.object.type==='ThisExpression'
   ?[{method:f.property.name,args:c.arguments.length,line:s.loc.start.line+ctx.offset}]:[];
 });
}
const src=root(input.vue,true),dst=root(input.code,false);
const methods=one(src.parent,'methods')?.value,init=one(methods,'initData');
if(!init||init.type!=='ObjectMethod')throw Error('Source initializer unavailable');
const initCalls=direct(src,init);
const initSequence=initCalls.map(c=>c.method);
const inited=one(dst.parent,'inited'),attached=one(dst.parent,'attached');
const early=direct(dst,inited),mounted=direct(dst,attached);
const expanded=initCalls.length===init.body.body.length&&initCalls.every(c=>c.args===0)
 &&initSequence.every((n,i)=>mounted[i]?.method===n&&mounted[i]?.args===0)
 &&initSequence.every(n=>!early.some(c=>c.method===n)&&mounted.filter(c=>c.method===n&&c.args===0).length===1);
const descriptor=one(one(src.parent,'watch')?.value,'settings')?.value;
const handler=one(descriptor,'handler');
if(handler?.type!=='ObjectMethod')throw Error('Source watcher unavailable');
const registrations=(inited?.body?.body||[]).flatMap(s=>{
 const c=s.type==='ExpressionStatement'&&s.expression,f=c?.callee;
 return c?.type==='CallExpression'&&f?.type==='MemberExpression'&&!f.computed
  &&f.object.type==='ThisExpression'&&f.property.name==='watch'&&c.arguments[0]?.value==='settings'?[c]:[];
});
if(registrations.length!==1)throw Error('Ambiguous target settings watcher');
const listener=registrations[0].arguments[1];
if(!['ArrowFunctionExpression','FunctionExpression'].includes(listener?.type)||listener.body.type!=='BlockStatement')
 throw Error('Unsupported target settings watcher');
const sourceWrites=writes(src,handler),targetWrites=writes(dst,listener),parentWrites=writes(dst,dst.parent);
const last=handler.body.body.at(-1),lastWrites=writes(src,last);
process.stdout.write(JSON.stringify({
 initializer:{source_sequence:initSequence,target_inited_calls:early,target_attached_calls:mounted,
  expanded_source_prefix_once_in_attached:expanded,
  boundary:'Direct exported-parent hook statements and source initializer expansion only, not arbitrary call-graph equivalence.'},
 watcher:{source_params:handler.params.map(p=>p.name||p.type),target_params:listener.params.map(p=>p.name||p.type),
  source_writes:sourceWrites,source_trailing_writes:lastWrites,target_listener_writes:targetWrites,
  target_parent_writes:parentWrites,
  trailing_settings_write_missing:sourceWrites.some(w=>w.key==='dashboard_settings')
   &&lastWrites.some(w=>w.key==='dashboard_settings')&&!parentWrites.some(w=>w.key==='dashboard_settings'),
  boundary:'Static direct localStorage.setItem sites; does not execute storage, trace aliases, or prove arbitrary persistence equivalence.'}
}));
'''


def inspect_startup_and_storage(vue, code):
    proc = subprocess.run(['node', '-e', AUDIT_JS], cwd=ROOT,
        input=json.dumps({'vue': vue, 'code': code}), capture_output=True,
        text=True, encoding='utf-8', timeout=20)
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    return json.loads(proc.stdout)


def audit(snapshot):
    snapshot = snapshot.resolve()
    checked = verify_snapshot(snapshot)
    summary_path = snapshot / f'{BATCH_ID}_summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    if summary['batch_id'] != BATCH_ID or [s['id'] for s in summary['samples']] != ['MonitoringDashboard']:
        raise RuntimeError('Unexpected batch')
    sample = summary['samples'][0]
    report_path = snapshot / 'repair_reports/complex/MonitoringDashboard_repair_history.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    state = report['state']
    repairs, norms = state['repair_history'], state['normalization_history']
    if (checked != 364 or not sample['final_passed'] or len(repairs) != 1 or len(norms) != 2
            or [n['accepted'] for n in norms] != [False, True]
            or [n['gate']['should_stop'] for n in norms] != [True, False]
            or repairs[0]['repair_regression_rejected'] or repairs[0]['passed']
            or sample['retained_previous_candidate'] or sample['status'] != 'completed'):
        raise RuntimeError('Review narrative: candidate history differs')
    for key in ('final_passed', 'stop_reason', 'repair_rounds', 'llm_repair_calls',
                'deterministic_steps', 'retained_previous_candidate'):
        if sample[key] != state[key] or sample[key] != report['summary'][key]:
            raise RuntimeError(f'Summary/state mismatch: {key}')
    for entry in repairs:
        path = snapshot / 'pipeline/complex' / Path(entry['repair_result']['repaired_file_path']).name
        if (path.read_text(encoding='utf-8') != entry['repair_result']['repaired_code']
                or progress_code_hash(path) != entry['progress_signature']['generated_code_sha256']):
            raise RuntimeError('Repair candidate hash mismatch')
    for entry in norms:
        path = snapshot / 'pipeline/complex' / Path(entry['candidate_file']).name
        if progress_code_hash(path) != entry['progress_signature']['generated_code_sha256']:
            raise RuntimeError('Normalization candidate hash mismatch')
    final = snapshot / 'pipeline/complex' / Path(sample['final_file_path']).name
    code = final.read_text(encoding='utf-8')
    if (code != state['generated_code'] or code != state['final_code']
            or final.name != Path(norms[-1]['candidate_file']).name
            or not state['final_validate_result']['validation_passed']
            or state['final_validate_result']['validation_errors']
            or not state['final_visual_eval_result']['visual_eval_passed']
            or state['final_visual_eval_result']['visual_eval_errors']
            or sample['final_structure_similarity'] != state['final_visual_eval_result']['structure_similarity']):
        raise RuntimeError('Final artifact/evaluation mismatch')
    generation = state['generation_usage']['total_tokens']
    repair = sum(r['repair_result']['usage']['total_tokens'] for r in repairs)
    for row in (sample, summary['aggregate']):
        if (row['generation_tokens'], row['repair_tokens'], row['total_tokens']) != (generation, repair, generation + repair):
            raise RuntimeError('Token accounting mismatch')
    source = snapshot / 'protocol/frozen' / sample['vue_file']
    vue = source.read_text(encoding='utf-8')
    semantics = inspect_semantics(code, vue, ssm=state['ssm'])
    details = inspect_startup_and_storage(vue, code)
    notification = inspect_method(vue, code)
    method = next(c for c in semantics.get('method_contracts', []) if c.get('name') == 'requestNotificationPermission')
    if (semantics.get('error')
            or method['status'] != 'callable_present'
            or method['source_references']['count'] or method['target_references']['count']
            or not details['initializer']['expanded_source_prefix_once_in_attached']
            or not details['watcher']['trailing_settings_write_missing']):
        raise RuntimeError('Review narrative: source contract audit changed')
    data = {
        'classification': 'frozen_automatic_pass_with_separate_watch_persistence_defect',
        'snapshot': snapshot.relative_to(ROOT).as_posix(), 'verified_files': checked,
        'summary_sha256': digest(summary_path), 'history_sha256': digest(report_path),
        'final_file': final.name, 'final_sha256': digest(final),
        'sample': sample, 'aggregate': summary['aggregate'],
        'normalizations': norms,
        'repairs': [{'attempt': h['repair_attempt'], 'passed': h['passed'],
            'validation_error_codes': [e['code'] for e in h['validate_result']['validation_errors']],
            'gate': h['repair_regression_gate'], 'usage': h['repair_result']['usage'],
            'postprocessing': h['repair_result']['raw_response'].get('pipeline_postprocessing', [])} for h in repairs],
        'normalization_stop_reasons': state['normalization_stop_reasons'],
        'source_semantics': {k: v for k, v in semantics.items() if k not in ('code', 'wrappers')},
        'recorded_final_validation_errors': state['final_validate_result']['validation_errors'],
        'independent_ast_review': details, 'notification_review': notification,
        'final_warning_codes': [w['code'] for w in state['final_validate_result']['validation_warnings']],
        'model_requests_performed_by_analysis': 0, 'runtime_or_browser_test_performed': False,
        'manual_status': 'not_started_watch_persistence_review_required',
        'original_automatic_score_modified': False, 'production_rules_modified': False,
        'independent_holdout': False,
        'next_step': 'Source-proven watcher parameter alpha-mapping and unused second-parameter boundary: '
          'detection, bounded restoration and gate counterexamples on frozen artifacts before another model run. '
          'Do not patch canonical San, waive validation, or declare all 30 samples passed.',
    }
    verify_snapshot(snapshot)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    args = parser.parse_args()
    data = audit(args.snapshot)
    output = ROOT / 'data/experiments/analysis' / Path(data['snapshot']).name.replace('_results_', '_')
    if output.exists():
        raise FileExistsError('Never replace an existing analysis')
    output.mkdir(parents=True)
    (output / 'summary.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'analysis': output.relative_to(ROOT).as_posix(), 'verified_files': data['verified_files'],
        'automatic_passed': True, 'manual_passed': False, 'persistence_omission_found': True,
        'total_tokens': data['sample']['total_tokens'], 'final_sha256': data['final_sha256']}))


if __name__ == '__main__':
    main()
