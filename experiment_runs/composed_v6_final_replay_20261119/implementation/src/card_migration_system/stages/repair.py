"""One repair proposal using the existing rules and projected model evidence.

The graph, not this module, owns candidate retesting and acceptance.
Dependencies stay explicit so existing boundary and replay tests remain valid.
"""
import json
from ..application.service import ServiceError
from ..prompts.repair_context import model_evidence,project_prompt
from ..prompts.san_contract import CONSTRAINTS, POLICY, SHA256, repair_targets
from .normalization import normalize_proposal


def propose_repair(self,key,current,evaluation,number,*,BrowserEvaluator,syntax_repair_messages):
    cached=self.cached(key,f'revisions/{number}.json')
    if cached:return cached
    self.guard(key);source=self.source(key);ssm=self.extract(key)['ssm'];errors=evaluation['diagnostics']
    syntax_blocked=evaluation.get('syntax',{}).get('status')=='fail'
    browser=self.browser or BrowserEvaluator(self.settings,self.job(key).request['runtime'])
    rule=normalize_proposal(self.settings,self.checks,browser,source,current['code'],ssm,evaluation)
    model_output=None
    rejected_rule=False
    for decision in self.job(key).state.get('decisions',[]):
        if not decision['accepted'] and decision['previous']==current['file']['sha256']:
            prior=self.cached(key,f'revisions/{decision["round"]}.json')
            if prior and prior['origin']=='rule_repair' and prior['code']==rule['code']:rejected_rule=True
    if rule['code']!=current['code'] and not rejected_rule:
        code=rule['code'];origin='rule_repair'
    else:
        feedback=self.repair_feedback(key,current)
        if syntax_blocked:
            messages=syntax_repair_messages(source,current['code'],evaluation['syntax'],feedback)
        else:
            model_errors,model_visual=model_evidence(evaluation)
            prompt=self.checks(self.settings.repository_root,'repair_prompt',source=source,code=current['code'],ssm=ssm,errors=model_errors,visual_errors=model_visual)['prompt']
            prompt,context=project_prompt(prompt,ssm,evaluation)
            prompt+='\nCausal repair checklist (not a waiver):\n'+json.dumps(repair_targets(errors),ensure_ascii=False)
            if feedback:prompt+='\nRejected attempts from this accepted parent (do not repeat):\n'+json.dumps(feedback,ensure_ascii=False)
            context['model_prompt_chars']=len(prompt)
            context['shared_san_contract']={'policy':POLICY,'sha256':SHA256}
            self.put_json(key,f'calls/{number}/repair-context.json','repair_context',context)
            messages=[{'role':'system','content':'Repair the current San SFC with minimal changes. Preserve correct behavior. Output only complete San SFC.\n'+CONSTRAINTS},{'role':'user','content':prompt}]
        for prior_number in range(1,number):
            prior=self.cached(key,f'calls/{prior_number}/request.json')
            if prior and prior.get('messages')==messages:raise ServiceError('repeated_repair_request_blocked')
        raw_code=self.invoke(key,number,messages)['code'];origin='model_repair'
        model_output=self.put(key,f'model-outputs/{number}.san','raw_model_san',raw_code.encode())
        # Newly introduced, source-proven option/default/syntax defects are
        # corrected in the SAME proposal, not left to consume the next repair
        # round. Never reuse the parent's stale static findings as proof.
        rule=normalize_proposal(self.settings,self.checks,browser,source,raw_code,ssm,evaluation)
        code=rule['code']
    self.put_json(key,f'normalizations/{number}.json','normalization',
        {k:v for k,v in rule.items() if k!='code'})
    ref=self.put(key,f'revisions/{number}.san','san',code.encode())
    revision={'number':number,'parent':current['file']['sha256'],'origin':origin,'file':ref,'code':code,'rules':rule['changes'],
              'repair_focus':'syntax' if syntax_blocked else 'semantics_and_observations'}
    if model_output:revision['raw_model_output']=model_output
    self.put_json(key,f'revisions/{number}.json','revision',revision);return revision
