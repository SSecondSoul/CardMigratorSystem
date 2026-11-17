"""Offline graph/ledger tests plus a real Puppeteer calibration. No cloud calls."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PROJECT/'src'))
from test_scaffold import copy_fixture
from card_migration_system.config import load_settings
from card_migration_system.application.service import Service,ServiceError
from card_migration_system.application.migrations import MigrationService
from card_migration_system.adapters.model import ModelExchange,inspect_response
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.runtime import profile,browser_executable
from card_migration_system.persistence.database import initialize,transaction
from card_migration_system.persistence.migrations import ModelCall
from card_migration_system.workers.migration import work_once
from card_migration_system.stages.structure import tree_distance
from card_migration_system.stages.evaluation import candidate_decision
from card_migration_system.interfaces.api.app import create_app

PNG=base64.b64encode(bytes.fromhex('89504e470d0a1a0a')).decode() # Fake browser evidence; no image claim.
SOURCE='<template><div class="card">Hello</div></template><script>export default {}</script><style>.card { color: rgb(20, 40, 60); }</style>'
SAN='<template><div class="card">Hello</div></template><script>const san = require("san");module.exports = san.defineComponent({});</script><style>.card { color: rgb(20, 40, 60); }</style>'

class FakeModel:
    def __init__(self,codes=None,fail=False):self.calls=0;self.codes=codes or [SAN];self.fail=fail
    def preflight(self):pass
    def exchange(self,messages):
        self.calls+=1
        if self.fail:raise ServiceError('model_response_unknown_no_automatic_retry')
        code=self.codes[min(self.calls-1,len(self.codes)-1)]
        return ModelExchange(200,json.dumps({'model':'qwen-plus','choices':[{'finish_reason':'stop','message':{'role':'assistant','content':code}}],
            'usage':{'prompt_tokens':10,'completion_tokens':20,'total_tokens':30}}).encode())

class FakeExtractor:
    def extract(self,*args):return {'ssm':{'schema_version':'3.0'},'status':'completed'}

class FakeBrowser:
    def __init__(self,source_bad=False):self.source_bad=source_bad
    def evaluate(self,source,code,props,actions):
        tree={'label':'div|','children':[{'label':'#text:Hello','children':[]}]}
        snap={'name':'initial','dom':tree,'styles':[]}
        side={'snapshots':[snap]+[{**snap,'name':a['name']} for a in actions],'png':PNG,'errors':[],'warnings':[],
              'blocked_requests':[],'evidence_overflow':False,'render_ms':1}
        vue=deepcopy(side)
        if self.source_bad:vue['warnings']=['source warning']
        return {'status':'completed','source_ast':{'tree':tree},'target_ast':{'tree':tree},'vue':vue,'san':deepcopy(side),
            'image':{'ssim':1,'different_pixel_ratio':0,'heatmap':PNG}}

def checks(repository,action,**kwargs):
    if action=='validate':return {'validation_passed':'BAD' not in kwargs['code'],
        'validation_errors':[{'code':'bad_target','message':'bad'}] if 'BAD' in kwargs['code'] else []}
    if action=='rules':return {'code':kwargs['code'],'changes':[]}
    if action=='repair_prompt':return {'prompt':'Fix current target, do not modify source.'}


class ModularFixture:
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.project=copy_fixture(Path(self.temp.name))
        shutil.copy(PROJECT/'configs/system.toml',self.project/'configs/system.toml')
        config=self.project/'configs/system.toml'
        config.write_text(config.read_text(encoding='utf-8').replace('few_shot_count = 1','few_shot_count = 0')
            .replace('network_enabled = true','network_enabled = false'),encoding='utf-8')
        shutil.copy(PROJECT/'requirements.lock',self.project/'requirements.lock')
        shutil.copytree(PROJECT/'migrations',self.project/'migrations',ignore=shutil.ignore_patterns('__pycache__'))
        self.settings=load_settings(project_root=self.project,environ={});initialize(self.settings)
        self.base=Service(self.settings);self.addCleanup(self.base.close)
        self.patcher=patch('card_migration_system.application.migrations.binding',return_value={'system':'test','legacy':'test','ssm':'test','protocol':'test'})
        self.patcher.start();self.addCleanup(self.patcher.stop)
        self.model=FakeModel();self.service=MigrationService(self.base,model=self.model,browser=FakeBrowser(),extractor=FakeExtractor(),checks=checks)
        self.source=self.base.create_input({'filename':'Example.vue','source':SOURCE})
    def enqueue(self,**kwargs):return self.service.create({'input_id':self.source['input_id'],'trusted_source':True,**kwargs},'same')['migration_id']
    def run_graph(self,key,**kwargs):
        with patch('card_migration_system.application.migrations.generation_messages',return_value=([{'role':'user','content':'test'}],{})):
            return work_once(self.base,service=self.service,**kwargs)


class ModularTests(ModularFixture,unittest.TestCase):
    def test_real_graph_persists_all_dimensions_and_test_provenance(self):
        key=self.enqueue();result=self.run_graph(key)
        self.assertEqual(result['status'],'finished');self.assertEqual(result['assessment']['dimensions']['interaction'],'not_run')
        self.assertEqual(result['actual_cloud_model_calls'],0);self.assertEqual(result['model_calls_started'],1)
        self.assertEqual(result['state']['evaluation']['functional_equivalence'],'not_proven')
        self.assertGreater(len(result['files']),8)
    def test_rule_then_model_candidate_retested(self):
        self.model.codes=[SAN.replace('Hello','BAD'),SAN]
        key=self.enqueue();result=self.run_graph(key)
        self.assertEqual(result['status'],'finished');self.assertEqual(self.model.calls,2)
        self.assertEqual(result['state']['decisions'][0]['reason'],'strict_improvement')
    def test_unknown_response_never_resent(self):
        self.model.fail=True;key=self.enqueue();result=self.run_graph(key)
        self.assertEqual(result['status'],'review_required');self.assertEqual(self.model.calls,1)
        with self.assertRaises(ServiceError):self.service.invoke(key,0,[{'role':'user','content':'test'}])
        self.assertEqual(self.model.calls,1)
    def test_missing_key_does_not_reserve_model_slot(self):
        self.service.model=None;key=self.enqueue();result=self.run_graph(key)
        self.assertEqual(result['stop_reason'],'model_network_disabled');self.assertEqual(result['model_calls_started'],0)
    def test_source_warning_blocks_repair_and_is_not_target_bug(self):
        self.service.browser=FakeBrowser(source_bad=True);key=self.enqueue();result=self.run_graph(key)
        self.assertEqual(result['status'],'blocked');self.assertEqual(self.model.calls,1)
    def test_checkpoint_resume_uses_committed_generation(self):
        key=self.enqueue();result=self.run_graph(key,interrupt_after=['generate']);self.assertEqual(result['status'],'review_required')
        self.service.update(key,status='queued');result=self.run_graph(key)
        self.assertEqual(result['status'],'finished');self.assertEqual(self.model.calls,1)
    def test_idempotency_and_cancel(self):
        key=self.enqueue();self.assertEqual(key,self.enqueue())
        with self.assertRaises(ServiceError):self.enqueue(max_repair_rounds=0)
        self.service.cancel(key);self.assertEqual(self.service.job(key).status,'cancelled')
    def test_feedback_bound_to_artifact_keeps_auto_result(self):
        key=self.enqueue();result=self.run_graph(key)
        self.service.feedback(key,{'revision_sha256':result['final_artifact']['sha256'],'passed':False,'notes':'check','changed_lines':3})
        result=self.service.report(key);self.assertEqual(result['status'],'finished');self.assertFalse(result['manual_feedback'][0]['passed'])
    def test_api_auth_and_readonly_report(self):
        app=create_app(self.settings,write_token='local-test-token-at-least-24-chars');self.addCleanup(app.extensions['migration_service'].close)
        client=app.test_client();key=self.enqueue()
        self.assertEqual(client.post('/api/v1/migrations/'+key+'/cancel',base_url='http://127.0.0.1:8790',json={}).status_code,403)
        self.assertEqual(client.get('/api/v1/migrations/'+key+'/report',base_url='http://127.0.0.1:8790').status_code,200)
    def test_tampered_artifact_blocks_report(self):
        key=self.enqueue();result=self.run_graph(key);self.base.storage.locate(result['final_artifact']['relative_path']).write_bytes(b'tampered')
        with self.assertRaises(ValueError):self.service.report(key)


class AlgorithmTests(unittest.TestCase):
    def test_source_export_preflight_supports_both_forms_without_executing_source(self):
        import subprocess
        dataset_source=PROJECT.parent/'data/datasets/components/01_simple/DeliveryPhaseCard/vue/DeliveryPhaseCard.vue'
        sources=[SOURCE,SOURCE.replace('export default {}','module.exports = {}')]
        if dataset_source.is_file():
            sources.append(dataset_source.read_text(encoding='utf-8'))
        for source in sources:
            with self.subTest(source=source[:80]):
                value={'repository':str(PROJECT/'engine'),'project':str(PROJECT),'source':source,'action':'source-preflight'}
                process=subprocess.run(['node',str(PROJECT/'browser/evaluate.mjs')],input=json.dumps(value).encode(),capture_output=True,timeout=20)
                self.assertEqual(process.returncode,0,process.stdout.decode()[:500])
                self.assertEqual(json.loads(process.stdout)['status'],'completed')

    def test_source_preflight_keeps_ambiguous_exports_and_dependencies_blocked(self):
        import subprocess
        scripts=[('module.exports = {}; export default {}','unsupported_source_sfc'),
                 ('module.exports = {}; module.exports = {}','unsupported_source_sfc'),
                 ('module.exports = makeComponent()','unsupported_source_sfc'),
                 ('export const other = {}; module.exports = {}','unsupported_source_sfc'),
                 ('import Other from "./Other.vue"; module.exports = {}','external_source_dependencies_unsupported')]
        for script,error in scripts:
            with self.subTest(script=script):
                source=SOURCE.replace('export default {}',script)
                value={'repository':str(PROJECT/'engine'),'project':str(PROJECT),'source':source,'action':'source-preflight'}
                process=subprocess.run(['node',str(PROJECT/'browser/evaluate.mjs')],input=json.dumps(value).encode(),capture_output=True,timeout=20)
                self.assertEqual(json.loads(process.stdout),{'status':'blocked','error':error})
                self.assertNotEqual(process.returncode,0)

    def test_nested_san_template_does_not_truncate_sfc(self):
        import subprocess
        value={'repository':str(PROJECT/'engine'),'project':str(PROJECT),'source':SOURCE,
            'code':SAN.replace('Hello','<template s-if="true"><span>Nested</span></template><b>Tail</b>'),'action':'parse'}
        process=subprocess.run(['node',str(PROJECT/'browser/evaluate.mjs')],input=json.dumps(value).encode(),capture_output=True,timeout=20)
        self.assertEqual(process.returncode,0,process.stderr.decode()[:500])
        self.assertIn('Tail',json.dumps(json.loads(process.stdout)['target']))
    def test_tree_edit_rename_delete_and_order(self):
        node=lambda label,*children:{'label':label,'children':list(children)}
        self.assertEqual(tree_distance(node('a',node('b',node('c'))),node('a',node('c')))['distance'],1)
        self.assertEqual(tree_distance(node('a'),node('b'))['distance'],1)
        self.assertEqual(tree_distance(node('a',node('b'),node('c')),node('a',node('c'),node('b')))['distance'],2)
    def test_response_shape_and_usage_preserved_on_truncation(self):
        raw={'model':'qwen-plus','usage':{'prompt_tokens':2,'completion_tokens':3,'total_tokens':5},'choices':[{'finish_reason':'length','message':{'role':'assistant','content':SAN}}]}
        result=inspect_response(ModelExchange(200,json.dumps(raw).encode()),'qwen-plus')
        self.assertFalse(result['valid']);self.assertEqual(result['usage']['total_tokens'],5)
    def test_candidate_cannot_exchange_passing_dimension_for_visual_score(self):
        old={'dimensions':{'static':'pass'},'source_blocked':False,'diagnostics':[],'structure_ted':{'similarity':1},'ui_restoration':50}
        new={**old,'dimensions':{'static':'fail'},'ui_restoration':100}
        self.assertFalse(candidate_decision(old,new)['accepted'])


class BrowserCalibrationTests(unittest.TestCase):
    def test_commonjs_source_scope_and_click_updates_in_real_browser(self):
        settings=load_settings(project_root=PROJECT,environ={});conf=profile(settings)
        source='<template><button @click="increment">{{count}}</button></template><script>const initial=2; module.exports={data(){return {count:initial}},methods:{increment(){this.count++}}};</script>'
        actions=[{'name':'increment','type':'click','selector':'button'}]
        data=BrowserEvaluator(settings,conf).evaluate(source,SAN,{},actions)
        self.assertFalse(data['vue']['errors']);self.assertFalse(data['vue']['warnings'])
        self.assertIn('#text:2',json.dumps(data['vue']['snapshots'][0]))
        self.assertIn('#text:3',json.dumps(data['vue']['snapshots'][1]))

    def test_real_puppeteer_compilation_render_and_pixels(self):
        settings=load_settings(project_root=PROJECT,environ={});conf=profile(settings)
        if not browser_executable(conf['browser']):self.skipTest('Chromium not installed')
        result=BrowserEvaluator(settings,conf).evaluate(SOURCE,SAN,{},[])
        self.assertEqual(result['status'],'completed');self.assertFalse(result['vue']['errors']);self.assertFalse(result['san']['errors'])
        self.assertEqual(result['image']['different_pixel_ratio'],0)
        self.assertEqual(tree_distance(result['source_ast']['tree'],result['target_ast']['tree'])['distance'],0)

    def test_real_ssm_validator_and_interaction_are_not_test_double_scores(self):
        from hashlib import sha256
        from card_migration_system.adapters.ssm import SSMExtractor
        from card_migration_system.adapters.legacy_checks import legacy_stage
        from card_migration_system.stages.evaluation import assess
        settings=load_settings(project_root=PROJECT,environ={});conf=profile(settings)
        source='<template><button class="card" @click="increment">{{count}}</button></template><script>export default {name:"CounterCard",data(){return {count:0}},methods:{increment(){this.count++}}}</script><style>.card{color:rgb(20,40,60)}</style>'
        code='<template><button class="card" on-click="increment">{{count}}</button></template><script>const san=require("san");const DataTypes=san.DataTypes;module.exports=san.defineComponent({name:"CounterCard",dataTypes:{},initData(){return {count:0}},increment(){this.data.set("count",this.data.get("count")+1)}});</script><style>.card{color:rgb(20,40,60)}</style>'
        ssm=SSMExtractor(settings.repository_root).extract(source.encode(),'CounterCard.vue',sha256(source.encode()).hexdigest())['ssm']
        static=legacy_stage(settings.repository_root,'validate',source=source,code=code,ssm=ssm)
        actions=[{'name':'increment','type':'click','selector':'button'}]
        data=BrowserEvaluator(settings,conf).evaluate(source,code,{},actions)
        result=assess(static,data,actions,{'structure':.95,'ui':.95,'pixel_difference':.05},ssm)
        self.assertTrue(result['passed'],json.dumps(result,ensure_ascii=True)[:2500])
        self.assertEqual(result['dimensions']['interaction'],'pass')
        self.assertEqual(result['structure_ted']['distance'],0)

    def test_target_runtime_exception_is_target_failure_not_infrastructure(self):
        settings=load_settings(project_root=PROJECT,environ={});conf=profile(settings)
        broken=SAN.replace('san.defineComponent({})','san.defineComponent({inited(){throw Error("target-test-error")}})')
        data=BrowserEvaluator(settings,conf).evaluate(SOURCE,broken,{},[])
        self.assertEqual(data['status'],'completed');self.assertTrue(data['san']['errors']);self.assertFalse(data['vue']['errors'])

    def test_known_color_difference_is_not_masked_by_structure(self):
        settings=load_settings(project_root=PROJECT,environ={});conf=profile(settings)
        data=BrowserEvaluator(settings,conf).evaluate(SOURCE,SAN.replace('rgb(20, 40, 60)','rgb(255, 0, 0)'),{},[])
        self.assertGreater(data['image']['different_pixel_ratio'],0)
        self.assertLess(data['image']['ssim'],1)

if __name__=='__main__':unittest.main()
