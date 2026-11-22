"""Closure-local names are not CommonJS namespace references. Follow-up RED."""
import unittest
import test_parent_hook_metadata_v9 as fixture
from test_semantic_comparison_v1 import inspect


class ParentHookScopeTests(unittest.TestCase):
    def test_local_module_and_exports_names_do_not_hide_the_real_parent_hook(self):
        base=fixture.TARGET.replace('HOOK','inited(){'+fixture.BODY+'},')
        for extra in (
            'total(items){return items.reduce((sum,module)=>sum+module.n,0)},',
            'read(exports){return exports.name},',
            'read(module){module={name:1};return module.name},',
        ):
            code=base.replace('HOOK','').replace('assignField(k,v)',extra+'assignField(k,v)')
            metadata=inspect(fixture.SOURCE,code)['parent_methods']
            self.assertEqual(metadata['status'],'complete',extra)
            self.assertIn('inited',metadata['methods'])

    def test_real_global_namespace_escapes_and_san_mutation_still_refuse(self):
        base=fixture.TARGET.replace('HOOK','inited(){'+fixture.BODY+'},')
        for prefix in ('const alias=module;','const alias=exports;','san.defineComponent=unknownConstructor;'):
            code=base.replace('module.exports=',prefix+'module.exports=')
            self.assertEqual(inspect(fixture.SOURCE,code)['parent_methods']['status'],'unproven')


if __name__=='__main__':unittest.main()
