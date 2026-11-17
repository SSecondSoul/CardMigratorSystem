"""Source-proven San rule generation for eligible dynamic-instance setters.

Ordinary sources still use the pinned model/repair stages. This is a bounded
production profile, not admission of the unfinished universal Vue contract.
"""
from hashlib import sha256
import json
import subprocess

from ..adapters.ssm import _environment
from ..application.service import ServiceError
from ..reporting.identity import digest

MODE='dynamic-setter-single-component-v1'


def run_compiler(settings,payload):
    try:
        process=subprocess.run(['node',str(settings.project_root/'runtime/san_business_v1/cli.cjs')],
            input=json.dumps(payload).encode(),capture_output=True,cwd=settings.project_root,
            timeout=45,env=_environment())
        if len(process.stdout)>8*1024*1024:raise ServiceError('business_compiler_output_too_large')
        result=json.loads(process.stdout)
    except (OSError,ValueError,subprocess.TimeoutExpired):
        raise ServiceError('business_compiler_unavailable') from None
    if process.returncode or result.get('status')!='completed':
        error=ServiceError(str(result.get('error','business_compiler_failed'))[:120])
        error.details=str(result.get('details',''))[:160]
        raise error
    return result


def prepare(service,key):
    source=service.source(key)
    result=run_compiler(service.settings,{'action':'compile','source':source,'code':source,'mode':MODE})
    if result['manifest'].get('production_profile')!=MODE:raise ServiceError('business_profile_mismatch')
    run_compiler(service.settings,{'action':'verify','source':source,'code':result['code'],'manifest':result['manifest']})
    plan={'route':MODE,'source_sha256':sha256(source.encode()).hexdigest(),
          'code':result['code'],'manifest':result['manifest'],'model_calls_required':0,
          'semantic_policy':'canonical_source_options_and_verified_vue_to_san_template',
          'public_key_whitelist':None,'full_public_instance_compatibility':False}
    prior=service.cached(key,'business-plan.json')
    if prior and prior!=plan:raise ServiceError('business_plan_drift')
    if not prior:service.put_json(key,'business-plan.json','source_capability',plan)
    return plan


def generate(service,key,plan):
    source=service.source(key);ssm=service.extract(key)['ssm']
    run_compiler(service.settings,{'action':'verify','source':source,'code':plan['code'],'manifest':plan['manifest']})
    file=service.put(key,'revisions/0.san','san',plan['code'].encode())
    manifest=service.put_json(key,'revisions/0.business.json','compiler_manifest',
        {'compiler':plan['manifest'],'ssm_sha256':digest(ssm),'mode':MODE})
    revision={'number':0,'parent':None,'origin':'source_ast_rule_generation','file':file,
        'code':plan['code'],'business_manifest':manifest,'route':MODE}
    service.put_json(key,'revisions/0.json','revision',revision)
    return revision


def validate(service,key,revision,ssm):
    try:
        reference=revision['business_manifest']
        manifest=json.loads(service.read_file(key,reference['relative_path']))
        if sha256(service.read_file(key,reference['relative_path'])).hexdigest()!=reference['sha256']:
            raise ServiceError('business_manifest_reference_mismatch')
        if manifest['mode']!=MODE or manifest['ssm_sha256']!=digest(ssm):raise ServiceError('business_ssm_binding_mismatch')
        if not ssm.get('template'):raise ServiceError('business_ssm_template_missing')
        run_compiler(service.settings,{'action':'verify','source':service.source(key),
            'code':revision['code'],'manifest':manifest['compiler']})
        return {'validation_passed':True,'validation_errors':[],
            'policy':'canonical_source_options_and_verified_vue_to_san_template',
            'ssm_sha256':manifest['ssm_sha256'],'contract_id':MODE,
            'universal_equivalence_claim':False}
    except (KeyError,TypeError,ValueError) as error:
        return {'validation_passed':False,'validation_errors':[{
            'code':error.code if isinstance(error,ServiceError) else 'business_manifest_invalid',
            'message':'Source/SSM/template/runtime binding verification failed; no semantic waiver.'}],
            'policy':'canonical_source_options_and_verified_vue_to_san_template'}
