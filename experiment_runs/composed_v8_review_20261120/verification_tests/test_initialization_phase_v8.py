"""Full source initialization, pure eager bootstrap and strict refusal cases."""
import unittest
import json
import subprocess
import sys
from test_semantic_comparison_v1 import inspect
from test_modular_system import PROJECT
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.structure import tree_distance
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.prompts.repair_context import relevant_ssm
from card_migration_system.prompts.san_contract import CONSTRAINTS, POLICY

SOURCE='''<template><main><b>{{chosen.name}}</b><i>{{rows.length}}</i><button @click="pick">pick</button></main></template><script>export default {
props:{entries:{type:Array,default:()=>[{id:1,name:'A'},{id:2,name:'B'}]}},data(){const copy=JSON.parse(JSON.stringify(this.entries));return {rows:copy,chosenId:copy.length?copy[0].id:0}},
computed:{chosen(){return this.rows.find(row=>row.id===this.chosenId)||{name:'empty'}}},methods:{pick(){this.chosenId=this.rows.length>1?this.rows[1].id:0}}}</script>'''
TARGET='''<template><main><b>{{chosen.name}}</b><i>{{rows.length}}</i><button on-click="pick">pick</button></main></template><script>const san=require('san');module.exports=san.defineComponent({
initData(){return {entries:[{id:1,name:'A'},{id:2,name:'B'}],rows:null,chosenId:null}},inited(){const entries=this.data.get('entries');let rows;if(typeof entries==='function'){rows=entries()}else{rows=entries||[]}this.data.set('rows',rows);this.data.set('chosenId',rows.length?rows[0].id:0)},
computed:{chosen(){const rows=this.data.get('rows');const chosenId=this.data.get('chosenId');return rows.find(row=>row.id===chosenId)||{name:'empty'}}},pick(){this.data.set('chosenId',this.data.get('rows').length>1?this.data.get('rows')[1].id:0)}})</script>'''


class InitializationPhaseTests(unittest.TestCase):
    def test_source_clone_and_order_restored_not_just_a_null_guard(self):
        result=inspect(SOURCE,TARGET,True)
        self.assertIn('restored_source_pure_prop_data_initialization_phase',result['changes'])
        self.assertIn('rows:[]',result['code'])
        self.assertIn('JSON.parse(JSON.stringify(this.data.get("entries")))',result['code'].replace(' ',''))
        self.assertNotIn("typeof entries",result['code'])
        self.assertEqual(inspect(SOURCE,result['code'],True)['code'],result['code'])
        self.assertNotIn('source_data_initialization_phase_not_landed',[f['code'] for f in inspect(SOURCE,result['code'])['findings']])

    def test_real_browser_default_empty_and_nondefault_props_then_interaction(self):
        code=inspect(SOURCE,TARGET,True)['code'];settings=load_settings(project_root=PROJECT,environ={})
        for props in ({},{'entries':[]},{'entries':[{'id':9,'name':'X'},{'id':4,'name':'Y'}]}):
            raw=BrowserEvaluator(settings,profile(settings)).evaluate(SOURCE,code,props,[{'name':'pick','type':'click','selector':'button'}])
            self.assertEqual(raw['vue']['errors'],[]);self.assertEqual(raw['san']['errors'],[])
            for a,b in zip(raw['vue']['snapshots'],raw['san']['snapshots']):self.assertEqual(tree_distance(a['dom'],b['dom'])['distance'],0,props)

    def test_impure_getter_init_hook_observers_unknown_calls_and_capture_refuse(self):
        for source,target in (
            (SOURCE.replace('return this.rows.find',"this.rows.push({});return this.rows.find"),TARGET),
            (SOURCE,TARGET.replace("inited(){","inited(){this.watch('entries',()=>{});")),
            (SOURCE,TARGET.replace("const entries=this.data.get('entries')","const entries=outside()")),
            (SOURCE.replace("const copy=JSON.parse(JSON.stringify(this.entries))","const copy=external(this.entries)"),TARGET),
            (SOURCE.replace('methods:{',"created(){this.pick()},methods:{"),TARGET),
            (SOURCE,TARGET.replace('rows.find(row=>row.id===chosenId)',"rows.find(row=>row.id!==chosenId)")),
            (SOURCE,TARGET.replace("this.data.set('rows',rows)","this.fire('loaded');this.data.set('rows',rows)")),
            (SOURCE,TARGET.replace("const san=", "const JSON={parse(v){return []},stringify(v){return ''}};const san=")),
            (SOURCE,TARGET.replace("inited(){", "inited(){const JSON={parse(v){return []}};")),
        ):
            self.assertNotIn('restored_source_pure_prop_data_initialization_phase',inspect(source,target,True)['changes'])

    def test_validator_rule_activation_and_focused_repair_context_share_the_same_cause(self):
        code='source_data_initialization_phase_not_landed'
        before=legacy_stage(PROJECT/'engine','validate',source=SOURCE,code=TARGET,ssm={})
        self.assertIn(code,[e['code'] for e in before['validation_errors']])
        result=legacy_stage(PROJECT/'engine','rules',source=SOURCE,code=TARGET,ssm={},errors=[{'code':code}])
        self.assertIn('restored_source_pure_prop_data_initialization_phase',str(result['changes']))
        after=legacy_stage(PROJECT/'engine','validate',source=SOURCE,code=result['code'],ssm={})
        self.assertNotIn(code,[e['code'] for e in after['validation_errors']])
        selected,audit=relevant_ssm({'script':{'data':'full'},'binding_graph':{'nodes':[]},'styles':{'css':'full'}},
            {'diagnostics':[{'code':code}],'dimensions':{'visual':'pass'}})
        self.assertEqual(audit['selection'],'error_related_sections')
        self.assertIn('script',selected);self.assertIn('binding_graph',selected);self.assertNotIn('styles',selected)

    def test_shared_generation_and_repair_contract_explains_eager_order_not_empty_final_state(self):
        self.assertEqual(POLICY,'san-shared-generation-repair-v5')
        self.assertIn('computed BEFORE inited',CONSTRAINTS)
        self.assertIn('not the final source initialization',CONSTRAINTS)

    def test_unavailable_source_analyzer_is_failure_not_silent_empty_findings(self):
        script='''import json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
from migration_pipeline.stages.validate import ValidateStage,ValidateStageInput
value=json.loads(sys.stdin.read())
with tempfile.TemporaryDirectory() as folder:
 p=Path(folder)/'Source.vue';p.write_text(value['source'],encoding='utf-8')
 with patch('migration_pipeline.stages.validate.inspect_semantics',return_value={'error':'injected_parser_failure','findings':[]}):
  result=ValidateStage().run(ValidateStageInput(generated_code=value['code'],vue_file_path=str(p),ssm={},compile_check=False))
 print(json.dumps({'passed':result.validation_passed,'codes':[e['code'] for e in result.validation_errors]}))
'''
        run=subprocess.run([sys.executable,'-c',script,str(PROJECT/'engine')],
            input=json.dumps({'source':SOURCE,'code':TARGET}).encode(),capture_output=True,timeout=30)
        self.assertEqual(run.returncode,0,run.stderr.decode(errors='replace'))
        result=json.loads(run.stdout)
        self.assertFalse(result['passed']);self.assertIn('source_semantic_analysis_unavailable',result['codes'])


if __name__=='__main__':unittest.main()
