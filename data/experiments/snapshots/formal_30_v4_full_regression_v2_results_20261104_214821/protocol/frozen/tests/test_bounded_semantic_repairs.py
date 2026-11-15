"""Positive and fail-closed cases for recurrence-prevention rules."""

import json
import subprocess
import unittest

from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.repair_regression_guard import assess_event_contract_regression
from migration_pipeline.utils.repair_prompt import RepairPromptBuilder, RepairPromptInput
from migration_pipeline.utils.san_compile import check_san_compile


VUE = '<template><div class="overlay" @click.self="close"></div></template>'
SSM = {"template": {"event_bindings": [{"event_name": "click", "handler_expression": "close"}]}}


def component(binding='close', method=''):
    return f'''<template><div class="overlay" on-click="{binding}"></div></template>
<script>const san = require('san');
module.exports = san.defineComponent({{
  close() {{}},
  {method}
}});</script><style></style>'''


WRAPPER = 'guard(event) { if (event && event.target === event.currentTarget) this.close(); },'


class BoundedSemanticRepairTests(unittest.TestCase):
    def gate(self, after, vue=VUE):
        return assess_event_contract_regression(ssm=SSM, before_code=component(), after_code=after,
                                                before_errors=[], after_errors=[], vue_source=vue)

    def test_ast_verified_source_self_wrapper_is_traced(self):
        result = self.gate(component('guard($event)', WRAPPER))
        self.assertFalse(result['should_stop'], result)
        self.assertEqual(result['after']['proven_self_wrappers'], ['click:close -> guard($event)'])

    def test_missing_event_is_repaired_only_with_source_self_contract(self):
        code = component('guard', WRAPPER)
        fixed = inspect_semantics(code, VUE, True)
        self.assertIn('on-click="guard($event)"', fixed['code'])
        self.assertEqual(fixed['changes'], ['explicit_self_wrapper_event'])
        self.assertEqual(inspect_semantics(code, '', True)['code'], code)
        self.assertFalse(self.gate(code)['should_stop'])
        self.assertTrue(self.gate(component('guard()', WRAPPER))['should_stop'])
        self.assertEqual(inspect_semantics(fixed['code'], VUE, True)['code'], fixed['code'])

    def test_guard_rejects_side_effect_wrong_target_missing_or_wrong_event(self):
        methods = [
            WRAPPER.replace('this.close();', 'this.deleteAll();'),
            WRAPPER.replace('===', '!=='),
            WRAPPER.replace('event.currentTarget', 'other.currentTarget'),
            WRAPPER.replace('if (event', 'this.erase(); if (event'),
            WRAPPER.replace('this.close();', '{ this.close(); this.erase(); }'),
            'guard(event) { if (event.target === event.currentTarget) {} this.close(); },',
        ]
        for method in methods:
            with self.subTest(method=method):
                self.assertTrue(self.gate(component('guard($event)', method))['should_stop'])
        self.assertTrue(self.gate(component('guard(other)', WRAPPER))['should_stop'])
        self.assertTrue(self.gate(component('guard($event)', WRAPPER), vue='')['should_stop'])

    def test_child_guard_cannot_prove_a_parent_binding(self):
        code = component('guard($event)').replace('module.exports',
            "const child = san.defineComponent({" + WRAPPER + " close() {} });\nmodule.exports")
        self.assertTrue(self.gate(code)['should_stop'])

    def test_event_argument_loss_remains_rejected(self):
        ssm = {'template': {'event_bindings': [{'event_name': 'click', 'handler_expression': 'choose(item)'}]}}
        result = assess_event_contract_regression(ssm=ssm,
            before_code=component('choose(item)'), after_code=component('choose'),
            before_errors=[], after_errors=[])
        self.assertTrue(result['should_stop'])

    def formatter(self, return_value='n => 800 / n - 4', extra='', binding='width(data.length)'):
        return f'''<template><div></div></template><script>const san = require('san');
const chart = san.defineComponent({{
  template: `<div>{{{{{binding}}}}}</div>`,
  initData() {{ return {{data: [1, 2, 3]}}; }},
  computed: {{
    width() {{ return {return_value}; }},
    count() {{ return this.data.get('data').length; }}
  }},
  {extra}
}});
module.exports = san.defineComponent({{components: {{chart}}}});</script><style></style>'''

    def test_pure_parameterized_computed_becomes_method_idempotently(self):
        fixed = inspect_semantics(self.formatter(), repair=True)
        self.assertEqual(fixed['changes'], ['parameterized_computed_to_pure_method'])
        self.assertIn('width(n) { return 800 / n - 4; }', fixed['code'])
        self.assertIn("count() { return this.data.get('data').length; }", fixed['code'])
        self.assertTrue(check_san_compile(fixed['code']).passed)
        self.assertEqual(inspect_semantics(fixed['code'], repair=True)['code'], fixed['code'])
        script = fixed['code'].split('<script>', 1)[1].split('</script>', 1)[0]
        js = r"""const fs=require('fs'); const script=fs.readFileSync(0,'utf8');
const m={exports:{}}; new Function('require','module',script+'\nmodule.exports=chart;')(require,m);
const c=new m.exports(); process.stdout.write(JSON.stringify([7,30,90].map(n=>c.width(n))));"""
        actual = subprocess.run(['node', '-e', js], input=script, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(actual.returncode, 0, actual.stderr)
        self.assertEqual(json.loads(actual.stdout), [800 / n - 4 for n in (7, 30, 90)])

    def test_formatter_refuses_hidden_dependencies_and_ambiguous_uses(self):
        cases = [self.formatter('n => n + this.data.get("offset")'),
                 self.formatter('n => n + external'),
                 self.formatter('n => Math.max(n, 1)'),
                 self.formatter('n => { this.erase(); return n; }'),
                 self.formatter(extra='width() { return 0; },'),
                 self.formatter(extra="other() { return this.data.get('width'); },"),
                 self.formatter(binding='width'),
                 self.formatter(binding='width(data.length) + width')]
        for code in cases:
            with self.subTest(code=code):
                self.assertEqual(inspect_semantics(code, repair=True)['code'], code)

    def test_parse_errors_never_rewrite(self):
        code = component().replace('close() {}', 'close( {')
        result = inspect_semantics(code, VUE, True)
        self.assertEqual(result['code'], code)
        self.assertIn('error', result)

    def event_case(self, body='{ this.selected = item; this.notify(`Selected ${item.title}`); }'):
        code = component('choose').replace('  close() {},', '''  close() {},
  initData() { return {selected: null}; },
  notify(message) {},
  choose() { const item = this.event.target.getAttribute('data-item'); this.data.set('selected', item); },''')
        ssm = {'template': {'event_bindings': [{'handler_name': 'choose', 'handler_expression': 'choose(item)',
                    'event_name': 'click', 'element_tag': 'div'}]},
               'script': {'options': {'data': [{'name': 'selected'}], 'methods': [
                   {'name': 'choose', 'params': ['item'], 'body_full': body}]}}}
        return code, ssm

    def test_restore_binding_and_method_together_from_bounded_source_body(self):
        code, ssm = self.event_case()
        fixed = inspect_semantics(code, repair=True, ssm=ssm)
        self.assertEqual(fixed['changes'], ['restored_source_parameterized_event_handler'])
        self.assertIn('on-click="choose(item)"', fixed['code'])
        self.assertIn("this.data.set('selected', item)", fixed['code'])
        self.assertIn('choose(item)', fixed['code'])
        self.assertNotIn('this.event', fixed['code'])
        self.assertIn('this.notify(`Selected ${item.title}`)', fixed['code'])
        self.assertEqual(inspect_semantics(fixed['code'], repair=True, ssm=ssm)['code'], fixed['code'])

    def test_unknown_or_complex_source_event_is_not_guessed(self):
        for body in ('{ this.selected.nested = item; }', '{ await save(item); }',
                     '{ this.selected = external; }', '{ this.missing(item); }',
                     '{ if (item) this.selected = item; }'):
            code, ssm = self.event_case(body)
            self.assertEqual(inspect_semantics(code, repair=True, ssm=ssm)['code'], code)
        code, ssm = self.event_case()
        self.assertEqual(inspect_semantics(code, repair=True)['code'], code)
        different_call = code.replace('on-click="choose"', 'on-click="choose(other)"')
        self.assertEqual(inspect_semantics(different_call, repair=True, ssm=ssm)['code'], different_call)

    def test_focused_prompt_has_source_method_and_explicit_argument_contract(self):
        ssm = {'template': {'event_bindings': [{'event_name': 'click', 'handler_name': 'choose',
                                              'handler_expression': 'choose(item)'}]},
               'script': {'options': {'methods': [{'name': 'choose', 'body_full': '{ this.current = item; }'}]}}}
        prompt = RepairPromptBuilder().build(RepairPromptInput(
            ssm=ssm, current_code=self.formatter(), validation_errors=[
                {'code': 'invalid_san_inline_computed_method_invocation'},
                {'code': 'event_arguments_not_landed'},
            ]))
        self.assertIn('this.current = item', prompt)
        self.assertIn('this.event', prompt)
        self.assertIn('wrapper($event)', prompt)
        self.assertIn('width(n)', prompt)

    def test_actual_san_listener_requires_explicit_event_and_preserves_self(self):
        # Exercise the installed San listener, not a reimplementation of dispatch.
        js = """const san = require('san');
const listener = require('san/src/view/get-event-listener');
const Data = require('san/src/runtime/data');
let calls=0;
const owner={guard(e){if(e && e.target===e.currentTarget) calls++;}};
const bind=expr=>listener(san.parseTemplate('<div on-click="'+expr+'"></div>').children[0].events[0],owner,new Data({}),false);
const target={};
bind('guard')({target,currentTarget:target});
const bare=calls;
bind('guard()')({target,currentTarget:target});
const emptyCall=calls;
bind('guard($event)')({target,currentTarget:{}});
const inner=calls;
bind('guard($event)')({target,currentTarget:target});
process.stdout.write(JSON.stringify({bare,emptyCall,inner,backdrop:calls}));"""
        result = subprocess.run(['node', '-e', js], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'bare': 1, 'emptyCall': 1, 'inner': 1, 'backdrop': 2})


if __name__ == '__main__':
    unittest.main()
