"""Rebuild repair messages from frozen evidence. NO model calls or database writes."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))

from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.prompts.repair_context import model_evidence,project_prompt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir',type=Path,required=True)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    folder=args.evidence_dir.resolve();output=args.output_dir.resolve()
    if not output.is_relative_to(PROJECT/'var') or output.exists():
        raise ValueError('Choose a NEW directory below migration_system/var')
    names=('model-request.json','model-receipt.json','evaluation.json','ssm.json','current.san')
    snapshots={name:(folder/name).read_bytes() for name in names}
    source_bytes=args.source.read_bytes();source=source_bytes.decode('utf-8')
    ssm_payload=json.loads(snapshots['ssm.json']);ssm=ssm_payload['ssm']
    if sha256(source_bytes).hexdigest()!=ssm_payload['source_sha256']:
        raise ValueError('Original source does not match frozen SSM input')
    evaluation=json.loads(snapshots['evaluation.json'])
    current=snapshots['current.san'].decode('utf-8')
    old=json.loads(snapshots['model-request.json'])['messages']
    receipt=json.loads(snapshots['model-receipt.json'])
    errors,visual=model_evidence(evaluation)
    legacy=legacy_stage(PROJECT/'engine','repair_prompt',source=source,code=current,
        ssm=ssm,errors=errors,visual_errors=visual)['prompt']
    prompt,context=project_prompt(legacy,ssm,evaluation)
    messages=[{'role':'system','content':old[0]['content']},{'role':'user','content':prompt}]
    # Source code, original evaluation and expensive receipts are only read.
    for name,original in snapshots.items():
        if (folder/name).read_bytes()!=original:raise ValueError('Frozen evidence changed')
    def contract(text):
        if '--- Expected San Contract From SSM ---\n' not in text:return None
        body=text.split('--- Expected San Contract From SSM ---\n',1)[1]
        return json.JSONDecoder().raw_decode(body)[0]
    old_user=old[-1]['content']
    preserved=contract(old_user)==contract(prompt)
    if not preserved:raise ValueError('Expected source contract changed during context projection')
    if 'Actual target evaluation (do not change source or hide diagnostics):' in prompt:
        raise ValueError('Full evaluation accidentally appended')
    report={'scope':'offline_prompt_projection_not_migration_quality',
        'policy':context['policy'],'source_sha256':sha256(source_bytes).hexdigest(),
        'frozen_files_sha256':{name:sha256(value).hexdigest() for name,value in snapshots.items()},
        'before_user_prompt_chars':len(old_user),'after_user_prompt_chars':len(prompt),
        'character_reduction_ratio':1-len(prompt)/len(old_user),
        'historical_provider_input_tokens':receipt['usage']['prompt_tokens'],
        'after_provider_input_tokens':None,'token_claim':'character_counts_only_no_tokenizer_or_provider_estimate',
        'actual_model_calls':0,'database_updated':False,'frozen_evidence_changed':False,
        'expected_source_contract_unchanged':preserved,'full_evaluation_appended':False,
        'error_codes':sorted({i['code'] for i in evaluation['diagnostics']}),
        'recorded_style_differences':len(evaluation.get('styles',{}).get('differences',[])),
        'style_summary':visual[0]['details']['styles'] if visual else {},
        'ssm_selection':context['ssm_selection'],'quality_thresholds_changed':False}
    output.mkdir(parents=True)
    for name,value in [('messages.json',messages),('context.json',context),('report.json',report)]:
        (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('style_summary','frozen_files_sha256')},
        ensure_ascii=True,indent=2))


if __name__=='__main__':main()
