"""Compare compiler representations without dropping or inventing branches."""
from hashlib import sha256
import unittest
from test_modular_evaluator_compatibility import parse_pair,PROJECT
from card_migration_system.adapters.ssm import SSMExtractor
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.structure import tree_distance,ssm_template_tree,target_template_tree


def source(body):
    return '<template>'+body+'</template><script>export default {data(){return {phase:1,inner:false}},methods:{next(){this.phase=this.phase===3?1:this.phase+1}}}</script>'


def target(body):
    return '<template>'+body+'</template><script>const san=require("san");module.exports=san.defineComponent({initData(){return {phase:1,inner:false}},next(){this.data.set("phase",this.data.get("phase")===3?1:this.data.get("phase")+1)}})</script>'


A='<main><p v-if="phase===1">one</p><section v-else-if="phase===2"><button>two</button></section><article v-else><i>other</i></article><footer>end</footer></main>'
B='<main><p s-if="phase===1">one</p><section s-elif="phase===2"><button>two</button></section><article s-else><i>other</i></article><footer>end</footer></main>'


class TemplateBranchProjectionTests(unittest.TestCase):
    def compare(self,a=A,b=B):
        vue=source(a);san=target(b);pair=parse_pair(vue,san)
        ssm=SSMExtractor(PROJECT/'engine').extract(vue.encode(),'GenericConditional.vue',sha256(vue.encode()).hexdigest())['ssm']
        return (tree_distance(pair['source']['tree'],pair['target']['tree']),
                tree_distance(ssm_template_tree(ssm,pair['source']['class_bindings']),target_template_tree(pair['target']['tree'])))
    def test_else_elif_and_following_sibling_project_once_in_order(self):
        for b in (B,B.replace('s-elif','s-else-if')):
            for result in self.compare(b=b):self.assertEqual(result['distance'],0,result)
    def test_nested_and_template_branches_are_not_lost_or_duplicated(self):
        a=A.replace('<i>other</i>','<template v-if="inner"><b>yes</b></template><template v-else><b>no</b></template>')
        b=B.replace('<i>other</i>','<template s-if="inner"><b>yes</b></template><template s-else><b>no</b></template>')
        for result in self.compare(a,b):self.assertEqual(result['distance'],0,result)
    def test_deleted_else_added_else_wrong_tag_text_and_order_still_differ(self):
        for b in (B.replace('<article s-else><i>other</i></article>',''),
                  B.replace('<i>other</i>','<i>wrong</i>'),
                  B.replace('<article s-else>','<aside s-else>').replace('</article>','</aside>'),
                  B.replace('<button>two</button>','<button>two</button><small>extra</small>'),
                  B.replace('<footer>end</footer>','<footer>wrong end</footer>')):
            with self.subTest(b=b):
                for result in self.compare(b=b):self.assertGreater(result['distance'],0,result)
        a='<div><p v-if="phase===1">one</p></div>'
        b='<div><p s-if="phase===1">one</p><p s-else>invented</p></div>'
        for result in self.compare(a,b):self.assertGreater(result['distance'],0,result)
    def test_initial_and_all_switched_branches_match_real_dom(self):
        a=A.replace('</main>','<button class="next" @click="next">next</button></main>')
        b=B.replace('</main>','<button class="next" on-click="next">next</button></main>')
        settings=load_settings(project_root=PROJECT,environ={})
        actions=[{'name':'phase_'+str(i),'type':'click','selector':'.next'} for i in range(2,5)]
        result=BrowserEvaluator(settings,profile(settings)).evaluate(source(a),target(b),{},actions)
        self.assertFalse(result['vue']['errors']);self.assertFalse(result['san']['errors'])
        for x,y in zip(result['vue']['snapshots'],result['san']['snapshots']):
            self.assertEqual(tree_distance(x['dom'],y['dom'])['distance'],0)
        self.assertEqual(tree_distance(result['source_ast']['tree'],result['target_ast']['tree'])['distance'],0)


if __name__=='__main__':unittest.main()
