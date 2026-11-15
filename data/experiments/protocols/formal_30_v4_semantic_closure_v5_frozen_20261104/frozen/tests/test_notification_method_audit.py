"""Static review must distinguish an unused interface from equivalent behavior."""

import unittest

from migration_pipeline.audit_formal_30_v4_notification_method import inspect_method, audit


def fixture(body='',template='<div></div>',extra=''):
    source='''<template>__TEMPLATE__</template><script>
const Child={methods:{run(){this.ask();}}};
module.exports={methods:{ask(){if('Notification' in window)Notification.requestPermission();},run(){__BODY__}}};
</script>'''.replace('__TEMPLATE__',template).replace('__BODY__',body)
    target='''<template><div></div></template><script>const Child=san.defineComponent({ask(){}});
module.exports=san.defineComponent({run(){}, __EXTRA__});</script>'''.replace('__EXTRA__',extra)
    return source,target


class NotificationMethodAuditTests(unittest.TestCase):
    def test_no_internal_calls_does_not_prove_public_interface_equivalence(self):
        result=inspect_method(*fixture(),name='ask')
        self.assertFalse(result['internal_invocation_found'])
        self.assertEqual(result['conclusion'],'source_method_interface_removed')
        self.assertTrue(result['source']['method_exists'])
        self.assertFalse(result['target']['method_exists'])
        self.assertEqual(result['source']['uncertain_reference_sites'],[])

    def test_direct_script_call_and_template_handler_are_detected(self):
        for body,template in [('this.ask();','<div></div>'),('', '<button @click="ask">Ask</button>')]:
            result=inspect_method(*fixture(body,template),name='ask')
            self.assertTrue(result['internal_invocation_found'])

    def test_dynamic_access_or_this_alias_is_explicitly_uncertain(self):
        for body in ('this[method]();','const self=this;self.ask();'):
            result=inspect_method(*fixture(body),name='ask')
            self.assertTrue(result['source']['uncertain_reference_sites'])

    def test_inline_child_method_does_not_satisfy_exported_parent_interface(self):
        result=inspect_method(*fixture(),name='ask')
        self.assertFalse(result['target']['method_exists'])
        self.assertEqual(result['source']['parent_script_references'],[])

    def test_frozen_history_confirms_second_repair_deletion_not_extraction_loss(self):
        result=audit()
        self.assertEqual(result['method_lost_at'],'second_llm_repair')
        self.assertTrue(result['second_repair_prompt_contains_method'])
        self.assertFalse(result['external_interface_equivalence_proven'])
        self.assertEqual(result['model_requests'],0)


if __name__=='__main__':
    unittest.main()
