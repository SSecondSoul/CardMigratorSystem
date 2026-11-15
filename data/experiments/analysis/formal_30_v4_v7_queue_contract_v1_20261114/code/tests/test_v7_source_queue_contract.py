"""Source-derived queue structure and adversarial refusals; never release V7."""
import re
import unittest
from unittest.mock import patch

from migration_pipeline.utils.v7_source_queue_contract import inspect_v7_source_queue
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from test_parent_dynamic_key_adapter_probe import generic_pair, node, ROOT

BASE = ROOT / 'data/experiments/analysis/formal_30_v4_v7_queue_contract_input_20261114'
ADAPTER = ROOT / 'migration_pipeline/probe_async_watcher_scope_adapter_v7.cjs'


class V7SourceQueueContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = (BASE / 'input.san').read_text(encoding='utf-8')
        cls.vue = (BASE / 'input.vue').read_text(encoding='utf-8')

    def inspect(self, code=None, vue=None):
        return inspect_v7_source_queue(self.code if code is None else code, self.vue if vue is None else vue)

    def reject_change(self, before, after, *, source=False):
        text = self.vue if source else self.code
        changed = text.replace(before, after)
        self.assertTrue(changed != text, 'Mutation fixture did not match: ' + before)
        result = self.inspect(vue=changed) if source else self.inspect(code=changed)
        self.assertFalse(result['queue_lifecycle_structure_matched'], result)
        self.assertFalse(result['production_eligible'])

    def test_frozen_candidate_complete_structure_matches_not_production(self):
        result = self.inspect()
        self.assertTrue(result['queue_lifecycle_structure_matched'], result)
        self.assertTrue(all(result['checks'].values()))
        self.assertFalse(result['source_equivalence_proven']); self.assertFalse(result['production_eligible'])
        self.assertEqual(result['changes'], [])
        self.assertEqual(result['fields'], ['tasks', 'settings'])
        self.assertEqual(len(result['remaining_production_codes']), 3)

    def test_generic_renamed_source_group_not_component_specific(self):
        code, vue = generic_pair()
        for old, new in [('tasks', 'records'), ('settings', 'options'), ('assign', 'applyOption'), ('save', 'persist')]:
            code, vue = code.replace(old, new), vue.replace(old, new)
        candidate = node(ADAPTER, {'code': code, 'vue': vue, 'experimental': True,
                                 'error_context_policy': 'private-async-parent-watch-source-context'})
        self.assertTrue(candidate['changes'], candidate['reviews'])
        result = inspect_v7_source_queue(candidate['code'], vue)
        self.assertTrue(result['queue_lifecycle_structure_matched'], result)

    def test_registration_index_mutation(self): self.reject_change('()=>enqueue(1)', '()=>enqueue(0)')
    def test_declaration_order_mutation(self): self.reject_change('queue.sort((a,b)=>a-b)', 'queue.sort((a,b)=>b-a)')
    def test_dedup_mutation(self): self.reject_change('!alive||pending[index]', '!alive')
    def test_reset_mutation(self): self.reject_change('pending.length=0;waiting=false;', 'pending.length=0;waiting=true;')
    def test_pending_cleared_before_callback(self): self.reject_change('pending[index]=false;', 'pending[index]=true;')
    def test_latest_source_read_mutation(self): self.reject_change('this.data.get("settings.autoSave")', 'false')
    def test_handler_body_mutation(self): self.reject_change('this.updateStatistics();if(', 'this.saveToLocalStorage();if(')
    def test_private_scope_bypassed(self): self.reject_change('__watcherScope_v7Local.schedule(flush)', 'Promise.resolve().then(flush)')
    def test_route_index_mutation(self): self.reject_change('.route(__parentWatchError_v5Error,index)', '.route(__parentWatchError_v5Error,0)')
    def test_dispose_scope_mutation(self): self.reject_change('__watcherScope_v7Local.dispose();', '')
    def test_missing_queue_disposal(self): self.reject_change('this.__sourceParentWatchDispose_v1();', '')
    def test_startup_order_mutation(self): self.reject_change('attached(){this.loadInitialData();', 'attached(){this.startAutoSync();this.loadInitialData();')
    def test_unknown_inited_work(self): self.reject_change('inited(){const __watcherScope_v7Local', 'inited(){this.extra();const __watcherScope_v7Local')
    def test_source_startup_drift(self): self.reject_change('this.loadInitialData();', 'this.startAutoSync();', source=True)
    def test_transitive_effect_drift(self): self.reject_change('localStorage.setItem(', 'localStorage.other(')
    def test_source_initial_data_drift(self): self.reject_change('isDarkMode: false', 'isDarkMode: true', source=True)
    def test_writer_rhs_must_preserve_number_conversion(self): self.reject_change("key==='syncInterval'?Number(value):value", 'value')
    def test_writer_tail_mutation(self): self.reject_change('`设置已更新：${key}`', '`已更新`')
    def test_factory_body_mutation(self): self.reject_change("fail('OUTSIDE_ASYNC_DISPATCH')", "fail('OTHER')")
    def test_extra_factory_reference_rejected(self): self.reject_change('module.exports = san.defineComponent', 'const stolen=__watcherScope_v7Create;module.exports = san.defineComponent')
    def test_unknown_hook_rejected(self): self.reject_change('module.exports = san.defineComponent({', 'module.exports = san.defineComponent({created(){},')
    def test_global_shadow_rejected(self): self.reject_change("const san = require('san');", "const Promise=other;const san = require('san');")
    def test_escaped_component_control_rejected(self): self.reject_change('module.exports = san.defineComponent({', 'module.exports = san.defineComponent({escape(){return this.__watcherScope_v7Configure;},')

    def test_duplicate_registration_rejected(self): self.reject_change('this.watch("tasks",()=>enqueue(0));', 'this.watch("tasks",()=>enqueue(0));this.watch("tasks",()=>enqueue(0));')

    def test_source_watch_options_not_weakened(self):
        self.assertIn('deep: true', self.vue)
        self.reject_change('deep: true', 'deep: true, immediate: true', source=True)

    def test_factory_temporal_dead_zone_rejected(self):
        pattern = r'const __watcherScope_v7Create=\(function createAsyncWatcherScope[\s\S]*?\n}\);'
        match = re.search(pattern, self.code)
        self.assertIsNotNone(match)
        moved = self.code[:match.start()] + self.code[match.end():]
        moved = moved.replace('</script>', match[0] + '\n</script>')
        self.assertFalse(self.inspect(code=moved)['queue_lifecycle_structure_matched'])

    def test_comments_and_whitespace_not_mistaken_for_semantic_drift(self):
        changed = self.code.replace('pending[index]=false;', '/*same AST*/ pending [ index ] = false ;')
        self.assertNotEqual(changed, self.code)
        self.assertTrue(self.inspect(code=changed)['queue_lifecycle_structure_matched'])

    def test_old_source_matcher_diagnostics_and_repairs_unchanged(self):
        before = source_parent_watch_semantics(self.code, self.vue)
        self.assertEqual(len(before['findings']), 3); self.assertEqual(before['proofs'], [])
        after = source_parent_watch_semantics(self.code, self.vue, repair=True)
        self.assertEqual(after['code'], self.code); self.assertEqual(after['findings'], before['findings'])

    def test_bad_input_and_analysis_failure_fail_closed(self):
        for code, vue in [('', self.vue), (self.code, ''), ('<script>bad(</script>', self.vue)]:
            self.assertFalse(inspect_v7_source_queue(code, vue)['queue_lifecycle_structure_matched'])
        with patch('migration_pipeline.utils.v7_source_queue_contract.subprocess.run', side_effect=OSError):
            self.assertFalse(self.inspect()['queue_lifecycle_structure_matched'])


if __name__ == '__main__': unittest.main()
