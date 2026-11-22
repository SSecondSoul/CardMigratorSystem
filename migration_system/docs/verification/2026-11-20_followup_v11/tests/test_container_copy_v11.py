"""A fresh array container is not a fresh record; prove the complete use chain."""
import unittest
from test_modular_system import PROJECT
from card_migration_system.adapters.legacy_checks import legacy_stage

BODY='''if(index<1)return;const list=this.data.get('rows').slice();const item=list.splice(index,1)[0];list.splice(index-1,0,item);this.data.set('rows',list);this.fire('change',list.slice())'''


def inspect(body):
    code='''<template><div/></template><script>const san=require('san');module.exports=san.defineComponent({initData(){return {rows:[]}},reorder(index){'''+body+'''}})</script>'''
    return legacy_stage(PROJECT/'engine','validate',source='',code=code,ssm={})


class ContainerCopyTests(unittest.TestCase):
    def codes(self,body):return {r['code'] for r in inspect(body)['validation_errors']}

    def test_container_only_two_splice_reorder_is_not_shared_record_mutation(self):
        for name in ('list','queueCopy'):
            self.assertNotIn('nested_state_mutation',self.codes(BODY.replace('list',name)))
        self.assertNotIn('nested_state_mutation',self.codes(BODY.replace("this.data.get('rows').slice()","[...this.data.get('rows')]")))

    def test_missing_copy_or_shared_record_write_is_still_rejected(self):
        for body in (
            BODY.replace(".get('rows').slice()",".get('rows')"),
            BODY.replace("list.splice(index-1",'item.done=true;list.splice(index-1'),
            BODY.replace("list.splice(index-1",'item.notes.push(1);list.splice(index-1'),
            BODY.replace("list.splice(index-1",'list[0].done=true;list.splice(index-1'),
        ):
            with self.subTest(body=body):self.assertIn('nested_state_mutation',self.codes(body))

    def test_incomplete_wrong_conditional_or_early_commit_is_not_proven(self):
        commit="this.data.set('rows',list);"
        for body in (BODY.replace(commit,''),BODY.replace(commit,"this.data.set('other',list);"),
                     BODY.replace(commit,'if(index>1){'+commit+'}'),
                     BODY.replace('list.splice(index-1,0,item);'+commit,commit+'list.splice(index-1,0,item);'),
                     BODY.replace(commit,'if(index>1)return;'+commit)):
            with self.subTest(body=body):self.assertIn('nested_state_mutation',self.codes(body))

    def test_escape_capture_live_alias_shadow_and_unknown_effect_remain_blocked(self):
        for addition in ('consume(list);','consume(item);','item.child.flag=true;',
                         'setTimeout(()=>list.splice(0,1),0);','const other=list;other.push(1);',
                         'function mutate(list){list.push(1)}',"this.data.set('flag',true);"):
            body=BODY.replace('list.splice(index-1',addition+'list.splice(index-1')
            with self.subTest(addition=addition):self.assertIn('nested_state_mutation',self.codes(body))


if __name__=='__main__':unittest.main()
