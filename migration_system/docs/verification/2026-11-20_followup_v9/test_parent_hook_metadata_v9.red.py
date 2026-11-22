"""Follow-up TDD: lifecycle ownership must be parsed, not guessed from text.

Not included in v8's fixed verification modules. These cases drive the next
explicit AST-recognition repair; they must turn green before v9 is promoted.
"""
from hashlib import sha256
import unittest

from test_modular_system import PROJECT
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.adapters.ssm import SSMExtractor

SOURCE='''<template><b>{{value}}</b></template><script>export default {
props:{seed:{type:Number,default:4}},data(){return {value:0}},
created(){this.assignField('value',this.seed)},methods:{assignField(k,v){this[k]=v}}}
</script><style>b{color:black}</style>'''
TARGET='''<template><b>{{value}}</b></template><script>const san=require('san');const DataTypes=san.DataTypes;
module.exports=san.defineComponent({dataTypes:{seed:DataTypes.number},initData(){return {seed:4,value:0}},
HOOK
assignField(k,v){this.data.set(k,v)}})</script><style>b{color:black}</style>'''
BODY="this.assignField('value',this.data.get('seed'))"


class ParentHookMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ssm=SSMExtractor(PROJECT/'engine').extract(SOURCE.encode(),'HookFixture.vue',sha256(SOURCE.encode()).hexdigest())['ssm']

    def validate(self,hook,code=None):
        return legacy_stage(PROJECT/'engine','validate',source=SOURCE,code=code or TARGET.replace('HOOK',hook),ssm=self.ssm)

    def test_ordinary_quoted_and_function_property_parent_hooks_are_found(self):
        for hook in ('inited(){'+BODY+'},', '"inited"(){'+BODY+'},', "'inited'(){"+BODY+'},',
                     'inited: function(){'+BODY+'},', '"inited": function(){'+BODY+'},'):
            result=self.validate(hook)
            codes=[d['code'] for d in result['validation_errors']]
            self.assertNotIn('missing_lifecycle_mapping',codes,hook)
            self.assertNotIn('lifecycle_behavior_not_landed',codes,hook)

    def test_child_hook_cannot_satisfy_missing_exported_parent_hook(self):
        code=TARGET.replace('HOOK','').replace('module.exports=',
            'const Child=san.defineComponent({inited(){'+BODY+'}});module.exports=')
        codes=[d['code'] for d in self.validate('',code)['validation_errors']]
        self.assertIn('missing_lifecycle_mapping',codes)

    def test_empty_hook_is_found_but_behavior_still_fails(self):
        for hook in ('"inited"(){},','inited:function(){},'):
            result=self.validate(hook);codes=[d['code'] for d in result['validation_errors']]
            self.assertNotIn('missing_lifecycle_mapping',codes)
            self.assertIn('lifecycle_behavior_not_landed',codes)

    def test_duplicated_opaque_and_arrow_hooks_are_not_proven_by_presence(self):
        for hook in ('inited(){'+BODY+'},inited(){},','inited:()=>{'+BODY+'},',
                     'inited:unknownHook,','...unknownOptions,'):
            result=self.validate(hook)
            self.assertFalse(result['validation_passed'],hook)
            self.assertIn('missing_lifecycle_mapping',[d['code'] for d in result['validation_errors']],hook)


if __name__=='__main__':unittest.main()
