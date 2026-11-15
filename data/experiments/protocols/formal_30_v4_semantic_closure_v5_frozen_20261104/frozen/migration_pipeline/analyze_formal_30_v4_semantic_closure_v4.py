"""Read-only audit of frozen automatic pass; keep lifecycle review separate."""

import argparse
import json
import subprocess
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import digest, verify_snapshot
from migration_pipeline.analyze_formal_30_v4_repair_scheduling import progress_code_hash
from migration_pipeline.run_formal_30_v4_semantic_closure_v4 import ROOT, BATCH_ID


LIFECYCLE_AUDIT_JS = r'''
const fs = require('fs'), parser = require('@babel/parser');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const key = n => !n.computed && (n.key?.name || n.key?.value);
const one = (o, k) => {
  const found = o?.properties?.filter(p => key(p) === k) || [];
  if (found.length > 1) throw Error('Ambiguous option: ' + k);
  return found[0];
};
function root(code, source) {
  const match = /<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code);
  if (!match) throw Error('Script missing');
  const text = match[1], ast = parser.parse(text, {sourceType: 'unambiguous'});
  const nodes = ast.program.body.flatMap(n => {
    if (source && n.type === 'ExportDefaultDeclaration') return [n.declaration];
    const e = n.type === 'ExpressionStatement' && n.expression;
    if (e?.type === 'AssignmentExpression' && e.operator === '='
        && e.left.type === 'MemberExpression' && !e.left.computed
        && e.left.object.name === 'module' && e.left.property.name === 'exports') {
      if (source) return [e.right];
      if (e.right.type === 'CallExpression' && e.right.callee.type === 'MemberExpression'
        && e.right.callee.object.name === 'san' && e.right.callee.property.name === 'defineComponent')
        return e.right.arguments;
    }
    return [];
  });
  if (nodes.length !== 1 || nodes[0].type !== 'ObjectExpression') throw Error('Ambiguous parent');
  const lineOffset = code.slice(0, match.index + match[0].indexOf('>') + 1).split('\n').length - 1;
  return {parent: nodes[0], text, lineOffset};
}
function directCalls(ctx, hook) {
  const method = one(ctx.parent, hook);
  if (!method) return [];
  if (method.type !== 'ObjectMethod' || method.params.length) throw Error('Unsupported hook');
  return method.body.body.flatMap(s => {
    const c = s.type === 'ExpressionStatement' && s.expression, f = c?.callee;
    return c?.type === 'CallExpression' && f?.type === 'MemberExpression' && !f.computed
      && f.object.type === 'ThisExpression'
      ? [{method: f.property.name, args: c.arguments.length,
          line: s.loc.start.line + ctx.lineOffset, statement: ctx.text.slice(s.start, s.end)}] : [];
  });
}
const a = root(input.vue, true), b = root(input.code, false);
const source = Object.fromEntries(['created', 'beforeMount', 'mounted'].map(h => [h, directCalls(a, h)]));
const target = Object.fromEntries(['inited', 'attached'].map(h => [h, directCalls(b, h)]));
const count = (calls, name) => calls.filter(c => c.method === name && c.args === 0).length;
const sourceCount = Object.values(source).flat().filter(c => c.method === 'initData' && c.args === 0).length;
const targetCount = Object.values(target).flat().filter(c => c.method === 'initDataImpl' && c.args === 0).length;
const sourceMethods = one(a.parent, 'methods')?.value;
process.stdout.write(JSON.stringify({source, target, source_business_initializer: 'initData',
  target_business_initializer: 'initDataImpl', source_initializer_calls: sourceCount,
  target_initializer_calls: targetCount,
  duplicated_startup: sourceCount === 1 && count(source.mounted, 'initData') === 1
    && count(target.inited, 'initDataImpl') === 1 && count(target.attached, 'initDataImpl') === 1,
  source_notification_permission_method_exists: !!one(sourceMethods, 'requestNotificationPermission'),
  target_notification_permission_method_exists: !!one(b.parent, 'requestNotificationPermission'),
  boundary: 'Read-only AST inspection of direct parent calls, not execution or arbitrary call-graph equivalence.'}));
'''


def lifecycle_audit(vue, code):
    result = subprocess.run(['node', '-e', LIFECYCLE_AUDIT_JS], cwd=ROOT,
        input=json.dumps({'vue': vue, 'code': code}), capture_output=True,
        text=True, encoding='utf-8', timeout=20)
    if result.returncode:
        raise RuntimeError(f'Lifecycle AST audit failed: {result.stderr}')
    return json.loads(result.stdout)


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
    history, norms = state['repair_history'], state['normalization_history']
    if (sample['status'] != 'completed' or not sample['final_passed'] or sample['stop_reason'] != 'passed'
            or len(history) != sample['llm_repair_calls'] or len(history) != 2
            or sample['repair_rounds'] != 2 or len(norms) != sample['deterministic_steps'] or len(norms) != 2
            or sample['retained_previous_candidate'] or state['retained_previous_candidate']
            or any(not n['accepted'] or n['gate']['should_stop'] for n in norms)
            or any(r['repair_regression_rejected'] or r['repair_regression_gate']['should_stop'] for r in history)):
        raise RuntimeError('Unexpected accepted-candidate history')
    for key in ('final_passed', 'stop_reason', 'repair_rounds', 'llm_repair_calls',
                'deterministic_steps', 'retained_previous_candidate'):
        if sample[key] != report['summary'][key] or sample[key] != state[key]:
            raise RuntimeError(f'Summary/history mismatch: {key}')
    final = snapshot / 'pipeline/complex' / Path(sample['final_file_path']).name
    code = final.read_text(encoding='utf-8')
    if (code != state['generated_code'] or code != state['final_code']
            or code != history[-1]['repair_result']['repaired_code']
            or state['final_validate_result'] != history[-1]['validate_result']
            or state['final_visual_eval_result'] != history[-1]['visual_eval_result']
            or not state['final_validate_result']['validation_passed']
            or state['final_validate_result']['validation_errors']
            or not state['final_visual_eval_result']['visual_eval_passed']
            or state['final_visual_eval_result']['visual_eval_errors']
            or sample['final_structure_similarity'] != state['final_visual_eval_result']['structure_similarity']
            or progress_code_hash(final) != history[-1]['progress_signature']['generated_code_sha256']):
        raise RuntimeError('Final artifact or evaluation mismatch')
    for entry in history:
        path = snapshot / 'pipeline/complex' / Path(entry['repair_result']['repaired_file_path']).name
        if (path.read_text(encoding='utf-8') != entry['repair_result']['repaired_code']
                or progress_code_hash(path) != entry['progress_signature']['generated_code_sha256']):
            raise RuntimeError('Repair artifact/signature mismatch')
    for entry in norms:
        path = snapshot / 'pipeline/complex' / Path(entry['candidate_file']).name
        if progress_code_hash(path) != entry['progress_signature']['generated_code_sha256']:
            raise RuntimeError('Normalization artifact/signature mismatch')
    generation = state['generation_usage']['total_tokens']
    repair = sum(r['repair_result']['usage']['total_tokens'] for r in history)
    for row in (sample, summary['aggregate']):
        if (row['generation_tokens'] != generation or row['repair_tokens'] != repair
                or row['total_tokens'] != generation + repair):
            raise RuntimeError('Token accounting mismatch')
    if any(summary['aggregate'][k] != v for k, v in {
            'configured': 1, 'completed': 1, 'passed': 1, 'failed': 0, 'execution_errors': 0, 'pending': 0}.items()):
        raise RuntimeError('Aggregate mismatch')
    source = snapshot / 'protocol/frozen' / sample['vue_file']
    inspection = lifecycle_audit(source.read_text(encoding='utf-8'), code)
    previous = lifecycle_audit(source.read_text(encoding='utf-8'), history[0]['repair_result']['repaired_code'])
    if not inspection['duplicated_startup'] or previous['target_initializer_calls'] != 1:
        raise RuntimeError('Duplicate-initialization finding no longer reproduced; review narrative')
    data = {
        'classification': 'frozen_automatic_pass_with_separate_lifecycle_review_defect',
        'snapshot': snapshot.relative_to(ROOT).as_posix(), 'verified_files': checked,
        'summary_sha256': digest(summary_path), 'history_sha256': digest(report_path),
        'final_file': final.name, 'final_sha256': digest(final), 'sample': sample,
        'aggregate': summary['aggregate'], 'model_requests_performed_by_analysis': 0,
        'runtime_or_browser_test_performed': False, 'manual_status': 'not_started_lifecycle_review_required',
        'original_automatic_score_modified': False, 'independent_holdout': False,
        'normalizations': [{'step': n['step'], 'before_llm_call': n['before_llm_call'],
            'rules': n['normalizations'], 'accepted': n['accepted'],
            'progress_signature': n['progress_signature']} for n in norms],
        'repairs': [{'attempt': r['repair_attempt'], 'passed': r['passed'],
            'validation_error_codes': [e['code'] for e in r['validate_result']['validation_errors']],
            'usage': r['repair_result']['usage'], 'gate': r['repair_regression_gate'],
            'postprocessing': r['repair_result']['raw_response'].get('pipeline_postprocessing', [])} for r in history],
        'final_warnings': state['final_validate_result']['validation_warnings'],
        'lifecycle_review': inspection, 'first_repair_lifecycle_review': previous,
        'next_step': 'Offline source-proven lifecycle multiplicity/phase detection and bounded repair; '
                     'counterexamples and candidate gate tests before any new model protocol or manual acceptance.',
    }
    verify_snapshot(snapshot)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    args = parser.parse_args()
    data = audit(args.snapshot if args.snapshot.is_absolute() else ROOT / args.snapshot)
    target = ROOT / 'data/experiments/analysis' / Path(data['snapshot']).name.replace('_results_', '_')
    if target.exists():
        raise FileExistsError('Do not replace an existing analysis')
    target.mkdir(parents=True)
    (target / 'summary.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(target.relative_to(ROOT))
    print(json.dumps({'verified_files': data['verified_files'], 'automatic_passed': True,
        'total_tokens': data['sample']['total_tokens'], 'duplicate_startup_found': True,
        'manual_passed': False}))


if __name__ == '__main__':
    main()
