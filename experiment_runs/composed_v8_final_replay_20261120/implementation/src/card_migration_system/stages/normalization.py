"""Bounded composition of existing source-proven rules. No model or acceptance.

The raw model response remains immutable. The graph's normal candidate retest
and regression gate still decide whether the composed proposal can replace its
accepted parent. A malformed script never enters semantic analyzers.
"""
from hashlib import sha256

MAX_PASSES = 3


def normalize_proposal(settings, checks, browser, source, code, ssm, evaluation, *, prefer_runtime_recovery=True):
    original = code
    trace = []
    seen = {sha256(code.encode()).hexdigest()}
    # Do not conflate a proven startup recovery with unrelated template edits.
    # The graph retests this exact existing rule proposal first; its ordinary
    # gate still retains structure failures and rejects other new diagnostics.
    if (prefer_runtime_recovery and evaluation.get('dimensions',{}).get('compile_runtime')=='fail'
            and evaluation.get('syntax',{}).get('status')!='fail'
            and any(d.get('code')=='missing_prop_defaults' for d in evaluation.get('diagnostics',[]))):
        recovered=checks(settings.repository_root,'prop_defaults',source=source,code=code,ssm=ssm)
        allowed={'restored_source_parent_prop_schema','restored_source_parent_prop_defaults'}
        if (recovered and not recovered.get('error') and isinstance(recovered.get('code'),str)
                and recovered['code']!=code and 'restored_source_parent_prop_defaults' in recovered.get('changes',[])
                and not set(recovered['changes'])-allowed):
            return {'code':recovered['code'],'changes':recovered['changes'],'model_calls':0,
                    'stop':'source_defaults_runtime_recovery_first','passes':[{'pass':1,
                        'before_sha256':sha256(code.encode()).hexdigest(),
                        'after_sha256':sha256(recovered['code'].encode()).hexdigest(),
                        'semantic_checks_ran':True,'analysis':'source_parent_prop_ast',
                        'changes':recovered['changes']}]}
    observations = [d for d in evaluation.get('diagnostics', [])
                    if d.get('code', '').startswith(('rendered_', 'template_structure', 'dom_'))]
    visual = [] if evaluation.get('dimensions', {}).get('visual') in (None, 'pass', 'not_run') else [
        {'code': 'visual_mismatch', 'details': {k: evaluation[k] for k in
         ('ui_restoration', 'different_pixel_ratio', 'styles', 'interaction') if k in evaluation}}]
    for number in range(MAX_PASSES):
        before = code
        changes = []
        if hasattr(browser, 'syntax'):
            syntax = browser.syntax(source, code, normalize=True)
            code = syntax['code']
            changes.extend(syntax['changes'])
            inspected = syntax.get('after') or browser.syntax(source, code)
            parsed = inspected['status'] == 'pass'
        else:
            parsed = evaluation.get('syntax', {}).get('status') != 'fail'
        if parsed:
            static = checks(settings.repository_root, 'validate', source=source, code=code, ssm=ssm)
            rule = checks(settings.repository_root, 'rules', source=source, code=code, ssm=ssm,
                          errors=static['validation_errors'] + observations, visual_errors=visual)
            code = rule['code']
            changes.extend(rule['changes'])
        before_sha, after_sha = (sha256(text.encode()).hexdigest() for text in (before, code))
        trace.append({'pass': number + 1, 'before_sha256': before_sha, 'after_sha256': after_sha,
                      'semantic_checks_ran': parsed, 'changes': changes})
        if code == before:
            return {'code': code, 'changes': [c for p in trace for c in p['changes']],
                    'passes': trace, 'stop': 'fixed_point', 'model_calls': 0}
        if after_sha in seen:
            # An incompatible rule cycle is evidence, never an accepted repair.
            return {'code': original, 'changes': [], 'passes': trace,
                    'stop': 'rule_cycle_original_retained', 'model_calls': 0}
        seen.add(after_sha)
    return {'code': code, 'changes': [c for p in trace for c in p['changes']],
            'passes': trace, 'stop': 'bounded_pass_limit', 'model_calls': 0}
