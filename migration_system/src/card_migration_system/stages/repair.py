"""One repair proposal. Body preserved from the validated application stage.

The graph, not this module, owns candidate retesting and acceptance.
Dependencies stay explicit so existing boundary and replay tests remain valid.
"""
import json
from ..application.service import ServiceError


def propose_repair(self,key,current,evaluation,number,*,BrowserEvaluator,syntax_repair_messages):
    cached=self.cached(key,f'revisions/{number}.json')
    if cached:return cached
    self.guard(key);source=self.source(key);ssm=self.extract(key)['ssm'];errors=evaluation['diagnostics']
    syntax_blocked=evaluation.get('syntax',{}).get('status')=='fail'
    visual=[] if evaluation['dimensions']['visual'] in ('pass','not_run') else [{'code':'visual_mismatch','details':{
        k:evaluation[k] for k in ('ui_restoration','different_pixel_ratio','styles','interaction')}}]
    browser=self.browser or BrowserEvaluator(self.settings,self.job(key).request['runtime'])
    if syntax_blocked:
        normalized=browser.syntax(source,current['code'],normalize=True)
        rule={'code':normalized['code'],'changes':normalized['changes']}
    else:
        rule=self.checks(self.settings.repository_root,'rules',source=source,code=current['code'],ssm=ssm,errors=errors,visual_errors=visual)
    rejected_rule=False
    for decision in self.job(key).state.get('decisions',[]):
        if not decision['accepted'] and decision['previous']==current['file']['sha256']:
            prior=self.cached(key,f'revisions/{decision["round"]}.json')
            if prior and prior['origin']=='rule_repair':rejected_rule=True
    if rule['code']!=current['code'] and not rejected_rule:
        code=rule['code'];origin='rule_repair'
    else:
        feedback=self.repair_feedback(key,current)
        if syntax_blocked:
            messages=syntax_repair_messages(source,current['code'],evaluation['syntax'],feedback)
        else:
            prompt=self.checks(self.settings.repository_root,'repair_prompt',source=source,code=current['code'],ssm=ssm,errors=errors,visual_errors=visual)['prompt']
            prompt+='\nActual target evaluation (do not change source or hide diagnostics):\n'+json.dumps(evaluation,ensure_ascii=False)
            if feedback:prompt+='\nRejected attempts from this accepted parent (do not repeat):\n'+json.dumps(feedback,ensure_ascii=False)
            messages=[{'role':'system','content':'Repair the current San SFC with minimal changes. Preserve correct behavior. Output only complete San SFC.'},{'role':'user','content':prompt}]
        for prior_number in range(1,number):
            prior=self.cached(key,f'calls/{prior_number}/request.json')
            if prior and prior.get('messages')==messages:raise ServiceError('repeated_repair_request_blocked')
        code=self.invoke(key,number,messages)['code'];origin='model_repair'
    ref=self.put(key,f'revisions/{number}.san','san',code.encode())
    revision={'number':number,'parent':current['file']['sha256'],'origin':origin,'file':ref,'code':code,'rules':rule['changes'],
              'repair_focus':'syntax' if syntax_blocked else 'semantics_and_observations'}
    self.put_json(key,f'revisions/{number}.json','revision',revision);return revision
