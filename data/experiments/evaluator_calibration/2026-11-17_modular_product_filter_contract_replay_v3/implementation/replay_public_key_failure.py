"""Replay frozen contract failure and bounded UI observations; never claim arbitrary-key success."""
import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import sys

PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT.parent
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.adapters.browser import BrowserEvaluator,SourceContractError
from card_migration_system.adapters.legacy_checks import legacy_stage,legacy_binding
from card_migration_system.stages.evaluation import assess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen-evidence',required=True)
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args()
    frozen=Path(args.frozen_evidence).resolve();output=Path(args.output_dir).resolve()
    settings=load_settings(project_root=PROJECT,environ={})
    if not frozen.is_relative_to(ROOT) or not output.is_relative_to(ROOT) or output.is_relative_to(settings.artifact_dir.resolve()) or output.exists():
        raise ValueError('Require frozen workspace evidence and a new separate output directory')
    manifest=json.loads((frozen/'SHA256SUMS.json').read_bytes())
    for name,expected in manifest.items():
        path=(frozen/name).resolve()
        if not path.is_relative_to(frozen) or sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Frozen evidence mismatch')
    original=json.loads((frozen/'frozen/report.json').read_bytes());request=original['request']
    source=(frozen/'frozen/source.vue').read_text(encoding='utf-8')
    code=(frozen/'frozen/revisions/2.san').read_text(encoding='utf-8')
    if request['filename']!='ProductFilterPanel.vue' or sha256(source.encode()).hexdigest()!=request['source_sha256']:
        raise ValueError('This diagnostic scenario requires the frozen ProductFilterPanel source')
    if sha256(code.encode()).hexdigest()!=original['final_artifact']['sha256']:raise ValueError('Accepted revision mismatch')
    ssm=json.loads((frozen/'frozen/ssm.json').read_bytes())['ssm']
    actions=[
        {'name':'search_audio','type':'input','selector':'input[placeholder]','value':'耳机'},
        {'name':'clear_search','type':'click','selector':'.filters button'},
        {'name':'office','type':'select','selector':'.filters > select:first-of-type','value':'办公'},
        {'name':'price_200','type':'input','selector':'input[type=range]','value':'200'},
        {'name':'stock','type':'click','selector':'input[type=checkbox]'},
        {'name':'clear_filters','type':'click','selector':'.filters button'},
        {'name':'price_sort','type':'select','selector':'.filters > select:last-of-type','value':'price'},
        {'name':'select_first','type':'click','selector':'.products button:first-child'},
        {'name':'audio_category','type':'select','selector':'.filters > select:first-of-type','value':'音频'},
        {'name':'no_results','type':'input','selector':'input[type=range]','value':'500'},
        {'name':'clear_empty','type':'click','selector':'.filters button'},
    ]
    output.mkdir(parents=True)
    def dump(name,value):
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    dump('FROZEN_INPUT_SHA256SUMS.json',manifest);dump('diagnostic-actions.json',actions)
    implementation=legacy_binding(ROOT)
    for directory in ('src/card_migration_system','browser'):
        for path in (PROJECT/directory).rglob('*'):
            if path.is_file() and path.suffix in ('.py','.mjs') and 'node_modules' not in path.parts:
                implementation['migration_system/'+str(path.relative_to(PROJECT)).replace('\\','/')]=sha256(path.read_bytes()).hexdigest()
    for name in ('migration_pipeline/utils/method_interface_semantics.cjs','migration_system/browser/source-contracts.mjs',
                 'migration_system/browser/empty-class-policy.mjs','migration_system/browser/evaluate.mjs',
                 'migration_system/src/card_migration_system/adapters/browser.py',
                 'migration_system/src/card_migration_system/application/migrations.py',
                 'migration_system/src/card_migration_system/graph/migration.py',
                 'migration_system/src/card_migration_system/stages/dom_comparison.py',
                 'migration_system/src/card_migration_system/stages/evaluation.py',
                 'migration_system/frontend/src/components/MigrationWorkbench.vue',
                 'migration_system/tests/test_modular_public_key_contract.py'):
        path=output/'implementation'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((ROOT/name).read_bytes())
    (output/'implementation/replay_public_key_failure.py').write_bytes(Path(__file__).read_bytes())
    browser=BrowserEvaluator(settings,profile(settings))
    parsed=browser.preflight(source)
    try:
        browser.source_contracts(source)
        raise AssertionError('Retained arbitrary-key contract must remain unsupported')
    except SourceContractError as error:capability={'status':'blocked','code':error.code,'diagnostics':error.diagnostics}
    dump('source-contract.json',capability)
    static=legacy_stage(ROOT,'validate',source=source,code=code,ssm=ssm)
    data=browser.evaluate(source,code,request['props'],actions)
    assessment=assess(static,data,actions,request['thresholds'],ssm)
    # Explicit expected product ordering, not merely source/target agreement.
    names=['机械键盘','显示器支架','降噪耳机','桌面灯']
    expected=[names,['降噪耳机'],names,['显示器支架','桌面灯'],['桌面灯'],['桌面灯'],names,
              ['桌面灯','显示器支架','机械键盘','降噪耳机'],['桌面灯','显示器支架','机械键盘','降噪耳机'],
              ['降噪耳机'],[],names]
    observations=[]
    for side in ('vue','san'):
        for snapshot,wanted in zip(data[side]['snapshots'],expected):
            rows=[item['text'] for item in snapshot['styles'] if item['tag']=='strong' and item['path'].startswith('root.0.2.')]
            observations.append({'side':side,'step':snapshot['name'],'expected_products':wanted,'observed_products':rows,
                                 'expected_products_match':rows==wanted})
    explicit_passed=len(observations)==24 and all(i['expected_products_match'] for i in observations)
    for side in ('vue','san'):
        (output/(side+'.png')).write_bytes(base64.b64decode(data[side].pop('png'),validate=True))
    (output/'heatmap.png').write_bytes(base64.b64decode(data['image'].pop('heatmap'),validate=True))
    dump('raw.json',{'static':static,'browser':data});dump('assessment.json',assessment)
    for name,expected_hash in manifest.items():
        if sha256((frozen/name).read_bytes()).hexdigest()!=expected_hash:raise ValueError('Frozen evidence changed')
    for name,expected_hash in implementation.items():
        if sha256((ROOT/name).read_bytes()).hexdigest()!=expected_hash:raise ValueError('Implementation drift')
    for name,expected_hash in manifest.items():
        if not name.startswith('frozen/'):continue
        relative=name[len('frozen/'):]
        path=settings.artifact_dir/('inputs/'+request['input_id']+'/'+request['filename'] if relative=='source.vue'
                                   else 'migrations/'+original['migration_id']+'/'+relative)
        if sha256(path.read_bytes()).hexdigest()!=expected_hash:raise ValueError('Live historical file changed')
    result={'scope':'frozen_development_capability_and_UI_diagnostic_not_new_migration_success',
        'historical_job':original['migration_id'],'historical_usage':original['usage'],
        'source_sha256':request['source_sha256'],'candidate_sha256':original['final_artifact']['sha256'],
        'syntax_preflight':parsed['status'],'capability_preflight':capability,'implementation_sha256':implementation,
        'actual_model_calls':0,'original_task_updated':False,'langsmith_uploaded':False,
        'assessment':assessment,'explicit_product_observations':observations,'explicit_expected_products_passed':explicit_passed,
        'limitations':['Arbitrary public key equivalence remains unsupported; production now blocks before generation.',
                       'Live control equality does not waive raw value or class attribute presence.',
                       'Configured UI actions are not arbitrary public method equivalence; historical not_run is unchanged.']}
    dump('replay.json',result)
    dump('SHA256SUMS.json',{str(p.relative_to(output)).replace('\\','/'):sha256(p.read_bytes()).hexdigest()
                          for p in output.rglob('*') if p.is_file()})
    print(json.dumps({'actual_model_calls':0,'capability':capability['code'],'dimensions':assessment['dimensions'],
        'initial_controls':assessment['initial_control_state']['equal'],
        'action_controls_equal':all(i['control_state_equal'] for i in assessment['interaction']),
        'product_observations':len(observations),'explicit_expected_products_passed':explicit_passed,
        'passed':assessment['passed']},indent=2))


if __name__=='__main__':main()
