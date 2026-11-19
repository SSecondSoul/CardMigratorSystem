"""Generic source-computed mapping: real parsers, reactivity and refusal cases."""
import json
import subprocess
import unittest
from test_modular_system import PROJECT
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.structure import tree_distance


def source(body='return this.count*2',extra=''):
    return '<template><main><b>{{amount}}</b><button @click="add">add</button></main></template><script>export default {data(){return {count:2}},computed:{amount(){'+body+'}},methods:{add(){this.count++}}'+extra+'}</script>'


def target(body="return this.data.get('count')*2",extra='',getters=''):
    return '<template><main><b>{{amount}}</b><button on-click="add">add</button></main></template><script>const san=require("san");module.exports=san.defineComponent({initData(){return {count:2}},amount(){'+body+'},add(){this.data.set("count",this.data.get("count")+1)}'+extra+((',computed:{'+getters+'}') if getters else '')+'})</script>'


def analyze(src,code,repair=False):
    result=subprocess.run(['node',str(PROJECT/'engine/migration_pipeline/utils/bounded_semantics.cjs')],
        input=json.dumps({'vue':src,'code':code,'ssm':{},'repair':repair}),capture_output=True,encoding='utf-8',check=True)
    value=json.loads(result.stdout)
    if value.get('error'):raise AssertionError(value)
    return value


class ComputedOptionTests(unittest.TestCase):
    def test_exact_getter_is_relocated_without_replacing_body(self):
        a=analyze(source(),target());finding=next(d for d in a['findings'] if d['code']=='source_computed_option_not_landed')
        self.assertTrue(finding['details']['source_matched_relocation_eligible'])
        b=analyze(source(),target(),True)
        self.assertIn('restored_source_matched_computed_option_shape',b['changes'])
        self.assertIn("computed:{amount(){return this.data.get('count')*2}}",b['code'])
        self.assertFalse(any(d['code']=='source_computed_option_not_landed' for d in analyze(source(),b['code'])['findings']))
        self.assertEqual(analyze(source(),b['code'],True)['code'],b['code'])

    def test_function_valued_and_existing_other_getters_are_preserved(self):
        code=target(getters='other(){return 7}').replace('amount(){','amount:function(){')
        result=analyze(source(),code,True)
        self.assertIn('other(){return 7}',result['code']);self.assertIn('amount:function(){',result['code'])
        self.assertIn('restored_source_matched_computed_option_shape',result['changes'])

    def test_arbitrary_getter_names_are_not_hardcoded(self):
        for name in ('remainingBudget','doneCount','labelText'):
            a=analyze(source().replace('amount',name),target().replace('amount',name),True)
            self.assertIn('restored_source_matched_computed_option_shape',a['changes'])

    def test_wrong_body_missing_getter_or_unknown_capture_stays_failed(self):
        for src,code in ((source(),target('return 99')),
                         (source('return this.count*scale'),target("return this.data.get('count')*scale")),
                         (source(),target().replace("amount(){return this.data.get('count')*2},",'')),
                         (source('return this.unknown'),target("return this.data.get('unknown')"))):
            with self.subTest(code=code):
                result=analyze(src,code,True)
                self.assertNotIn('restored_source_matched_computed_option_shape',result['changes'])
                self.assertTrue(any(d['code']=='source_computed_option_not_landed' for d in result['findings']))

    def test_script_and_event_method_callers_prevent_a_breaking_relocation(self):
        for extra in (',attached(){this.amount()}',',other(){return this.amount}',',other(){return this["amount"]()}'):
            result=analyze(source(),target(extra=extra),True)
            self.assertNotIn('restored_source_matched_computed_option_shape',result['changes'])
        for text in ('{{amount()}}','<i on-click="amount">click</i>'):
            result=analyze(source(),target().replace('{{amount}}',text),True)
            self.assertNotIn('restored_source_matched_computed_option_shape',result['changes'])

    def test_side_effects_nested_this_and_runtime_extension_are_not_guessed(self):
        for src,code in ((source('return this.count++'),target("return this.data.get('count')++")),
                         (source('return (()=>unknown())()'),target('return (()=>unknown())()')),
                         (source('return function(){return this.count}'),target("return function(){return this.data.get('count')}")),
                         (source(),target(extra=',mixins:[{}]')),
                         (source(),target().replace('const san=require("san")','const san=untrusted'))):
            with self.subTest(code=code):
                result=analyze(src,code,True)
                self.assertNotIn('restored_source_matched_computed_option_shape',result['changes'])

    def test_production_validator_and_rules_share_the_diagnostic(self):
        result=legacy_stage(PROJECT/'engine','validate',source=source(),code=target(),ssm={})
        self.assertIn('source_computed_option_not_landed',[d['code'] for d in result['validation_errors']])
        result=legacy_stage(PROJECT/'engine','rules',source=source(),code=target(),ssm={},errors=result['validation_errors'])
        self.assertIn('restored_source_matched_computed_option_shape',str(result['changes']))

    def test_browser_displays_and_recomputes_instead_of_only_compiling(self):
        result=analyze(source(),target(),True);settings=load_settings(project_root=PROJECT,environ={})
        raw=BrowserEvaluator(settings,profile(settings)).evaluate(source(),result['code'],{},[{'name':'increment','type':'click','selector':'button'}])
        self.assertFalse(raw['vue']['errors']);self.assertFalse(raw['san']['errors'])
        self.assertEqual(len(raw['san']['snapshots']),2)
        for a,b in zip(raw['vue']['snapshots'],raw['san']['snapshots']):
            self.assertEqual(tree_distance(a['dom'],b['dom'])['distance'],0)
        self.assertNotEqual(raw['san']['snapshots'][0]['dom'],raw['san']['snapshots'][1]['dom'])


if __name__=='__main__':unittest.main()
