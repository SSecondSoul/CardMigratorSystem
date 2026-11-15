"""Read-only review must not confuse automatic pass with persistence equivalence."""

import unittest

from migration_pipeline.analyze_formal_30_v4_semantic_closure_v5 import (
    ROOT, audit, inspect_startup_and_storage,
)


VUE = '''<script>export default {
  watch:{settings:{handler(newVal){this.tick();localStorage.setItem('dashboard_settings',JSON.stringify(newVal));},deep:true}},
  methods:{initData(){this.boot();},boot(){},tick(){}}
};</script>'''
SAN = '''<script>const san=require('san');
module.exports=san.defineComponent({
  inited(){this.watch('settings',(newValue,oldValue)=>{this.tick();});},
  attached(){this.boot();},boot(){},tick(){}
});</script>'''


class SemanticClosureV5AnalysisTests(unittest.TestCase):
    def test_frozen_automatic_pass_still_has_independent_persistence_omission(self):
        snapshot = ROOT / 'data/experiments/snapshots/formal_30_v4_semantic_closure_v5_results_20261104_150846'
        result = audit(snapshot)
        self.assertTrue(result['sample']['final_passed'])
        self.assertEqual(result['verified_files'], 364)
        self.assertEqual(result['sample']['total_tokens'], 242231)
        self.assertEqual(result['recorded_final_validation_errors'], [])
        self.assertIn('source_watch_persistence_not_landed',
                      [f['code'] for f in result['source_semantics']['findings']])
        self.assertTrue(result['independent_ast_review']['watcher']['trailing_settings_write_missing'])
        self.assertFalse(result['original_automatic_score_modified'])
        self.assertFalse(result['runtime_or_browser_test_performed'])

    def test_renamed_value_and_extra_old_value_do_not_hide_missing_write(self):
        result = inspect_startup_and_storage(VUE, SAN)
        self.assertEqual(result['watcher']['source_params'], ['newVal'])
        self.assertEqual(result['watcher']['target_params'], ['newValue', 'oldValue'])
        self.assertTrue(result['watcher']['trailing_settings_write_missing'])
        self.assertTrue(result['initializer']['expanded_source_prefix_once_in_attached'])

    def test_present_direct_write_is_not_marked_missing(self):
        code = SAN.replace('this.tick();', "this.tick();localStorage.setItem('dashboard_settings',JSON.stringify(newValue));")
        result = inspect_startup_and_storage(VUE, code)
        self.assertFalse(result['watcher']['trailing_settings_write_missing'])
        self.assertEqual(len(result['watcher']['target_listener_writes']), 1)

    def test_child_storage_write_does_not_replace_exported_parent_write(self):
        code = SAN.replace('module.exports=', "const child=san.defineComponent({save(){localStorage.setItem('dashboard_settings','child');}});module.exports=")
        result = inspect_startup_and_storage(VUE, code)
        self.assertTrue(result['watcher']['trailing_settings_write_missing'])
        self.assertEqual(result['watcher']['target_parent_writes'], [])

    def test_duplicate_or_early_initializer_is_not_reported_as_once(self):
        for code in (SAN.replace('attached(){this.boot();}', 'attached(){this.boot();this.boot();}'),
                     SAN.replace('inited(){', 'inited(){this.boot();')):
            with self.subTest(code=code):
                result = inspect_startup_and_storage(VUE, code)
                self.assertFalse(result['initializer']['expanded_source_prefix_once_in_attached'])

    def test_ambiguous_parent_is_an_error_not_a_clean_audit(self):
        with self.assertRaises(RuntimeError):
            inspect_startup_and_storage(VUE, SAN.replace('</script>', 'module.exports=san.defineComponent({});</script>'))


if __name__ == '__main__':
    unittest.main()
