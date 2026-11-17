"""Initial San stage. The supplied message builder is the pinned existing builder."""


def generate_initial(service,key,message_builder):
    cached=service.cached(key,'revisions/0.json')
    if cached:return cached
    plan=service.cached(key,'business-plan.json')
    if plan:
        from .business import generate
        return generate(service,key,plan)
    row=service.guard(key);ssm=service.extract(key)['ssm']
    messages,selection=message_builder(service.settings,ssm,row.request['few_shot_examples'],
        strategy=row.request['strategy'],source=service.source(key))
    service.put_json(key,'prompt-selection.json','prompt_selection',selection)
    result=service.invoke(key,0,messages)
    ref=service.put(key,'revisions/0.san','san',result['code'].encode())
    revision={'number':0,'parent':None,'origin':'generation','file':ref,'code':result['code']}
    service.put_json(key,'revisions/0.json','revision',revision)
    return revision
