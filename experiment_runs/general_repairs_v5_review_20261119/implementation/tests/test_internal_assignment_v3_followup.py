"""Follow-up proofs found by all-record replay; no component-name exceptions."""
import unittest
from test_semantic_comparison_v1 import inspect,SOURCE,TARGET


def proof(source,code):
    result=inspect(source,code)
    entry=next(c for c in result['method_contracts'] if c.get('dynamic_assignment'))
    return result,entry['dynamic_assignment']['scoped_proof']


class InternalAssignmentFollowupTests(unittest.TestCase):
    def test_ordinary_data_key_may_share_a_noncallable_component_metadata_option(self):
        for field in ('name','label','businessText'):
            source=SOURCE.replace('value:0',field+':0').replace("'value'",repr(field))
            code=TARGET.replace('value:0',field+':0').replace("'value'",repr(field))
            if field!='name':code=code.replace("name:'GenericSetter',", "name:'GenericSetter',"+field+":'metadata',")
            self.assertEqual(proof(source,code)[1]['status'],'proven_for_source_internal_calls')

    def test_callable_and_runtime_namespace_collisions_remain_unproven(self):
        source=SOURCE.replace('value:0','label:0').replace("'value'","'label'")
        code=TARGET.replace('value:0','label:0').replace("'value'","'label'").replace("name:'GenericSetter',","name:'GenericSetter',label(){return 0},")
        self.assertEqual(proof(source,code)[1]['status'],'unproven')
        for field in ('data','watch','constructor','prototype'):
            source=SOURCE.replace('value:0',field+':0').replace("'value'",repr(field))
            code=TARGET.replace('value:0',field+':0').replace("'value'",repr(field))
            self.assertEqual(proof(source,code)[1]['status'],'unproven')

    def test_missing_known_write_is_restored_from_complete_source_caller_not_counts(self):
        source=SOURCE.replace("this.assignField('value',2)","this.assignField('value',2);this.assignField('other',3)")
        code=TARGET.replace("this.assignField('value',2)","if(false)this.data.set('value',99)")
        self.assertEqual(proof(source,code)[1]['status'],'unproven')
        repaired=inspect(source,code,True)
        self.assertIn('restored_source_internal_setter_caller_bodies',repaired['changes'])
        self.assertEqual(proof(source,repaired['code'])[1]['status'],'proven_for_source_internal_calls')
        self.assertIn("'other', 3",repaired['code'])

    def test_other_unproven_write_owners_unknown_keys_and_captures_are_not_auto_repaired(self):
        changed=TARGET.replace("'value',2","'value',99")
        for source,code in (
            (SOURCE,changed.replace('change(){',"unrelated(){this.data.set('value',8)},change(){")),
            (SOURCE.replace("'value',2","unknown,2"),changed),
            (SOURCE.replace("'value',2","'value',outside()"),changed),
            (SOURCE.replace("'value',2","'unsafe.key',2"),changed),
        ):
            with self.subTest(code=code):
                result=inspect(source,code,True)
                self.assertNotIn('restored_source_internal_setter_caller_bodies',result['changes'])
                self.assertEqual(proof(source,result['code'])[1]['status'],'unproven')


if __name__=='__main__':unittest.main()
