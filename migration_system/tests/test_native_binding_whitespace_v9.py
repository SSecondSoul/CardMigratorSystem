"""Native reflection accepts grammar whitespace, not unknown expressions."""
import unittest
import test_remaining_repairs_v7 as v7
from test_modular_system import PROJECT
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.adapters.syntax import target_syntax
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.structure import tree_distance
from card_migration_system.stages.dom_comparison import compare_control_state


class NativeBindingWhitespaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.settings=load_settings(project_root=PROJECT,environ={})

    def pair(self,expression):
        source,code=v7.NullableNativeValueTests().pair('input',True)
        return source,code.replace('{=value=}',expression)

    def test_one_way_and_two_way_grammar_whitespace_reflects_same_identifier(self):
        for expression in ('{= value =}','{=\nvalue\n=}','{{ value }}','{{\nvalue\n}}'):
            source,code=self.pair(expression)
            result=target_syntax(self.settings,source,code,normalize=True)
            self.assertIn(' VALUE="{{value}}"',result['code'],expression)
            self.assertEqual(result['after']['status'],'pass')
            self.assertEqual(target_syntax(self.settings,source,result['code'],normalize=True)['code'],result['code'])

    def test_real_spaced_two_way_input_clear_and_reset_preserve_dom_and_live_state(self):
        source,code=self.pair('{= value =}')
        code=target_syntax(self.settings,source,code,normalize=True)['code']
        raw=BrowserEvaluator(self.settings,profile(self.settings)).evaluate(source,code,{},[
            {'name':'input','type':'input','selector':'input','value':'changed'},
            {'name':'next','type':'click','selector':'button'},
            {'name':'clear','type':'click','selector':'button:nth-of-type(2)'},
            {'name':'reset','type':'click','selector':'button[type=reset]'}])
        self.assertEqual(raw['vue']['errors'],[]);self.assertEqual(raw['san']['errors'],[])
        self.assertEqual(tree_distance(raw['source_ast']['tree'],raw['target_ast']['tree'])['distance'],0)
        for a,b in zip(raw['vue']['snapshots'],raw['san']['snapshots']):
            self.assertEqual(tree_distance(a['dom'],b['dom'])['distance'],0,a['name'])
            self.assertTrue(compare_control_state(a['styles'],b['styles'])['equal'],a['name'])

    def test_unknown_expression_mismatched_identifier_and_vmodel_are_not_reflected(self):
        for expression in ('{= other =}','{{va lue}}','{{ value.x }}','{{ value + other }}','{= value.x =}'):
            source,code=self.pair(expression)
            self.assertNotIn(' VALUE=',target_syntax(self.settings,source,code,normalize=True)['code'],expression)
        source,code=self.pair('{= value =}')
        self.assertNotIn(' VALUE=',target_syntax(self.settings,source.replace(':value="value"','v-model="value"'),code,normalize=True)['code'])


if __name__=='__main__':unittest.main()
