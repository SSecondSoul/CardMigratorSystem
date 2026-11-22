"""Evidence transmission is smaller, never a repair/evaluation correctness waiver."""
from copy import deepcopy
import json
import unittest

from test_modular_system import ModularFixture,PROJECT,FakeBrowser,SAN,checks
from card_migration_system.prompts.repair_context import (
    encoded,style_summary,compact_issues,model_evidence,relevant_ssm,project_prompt)
from card_migration_system.application.service import ServiceError
from card_migration_system.adapters.legacy_checks import legacy_stage


def evaluation():
    rows=[{'path':f'root.{i}','property':'height','source':'100px','target':'50px'} for i in range(500)]
    return {'dimensions':{'visual':'fail','static':'fail'},'required':['visual','static'],
        'thresholds':{'ui':.95},'ui_restoration':80,'different_pixel_ratio':.2,'ssim':.8,
        'styles':{'differences':rows,'truncated':True,'similarity':.5,'compared_properties':900},
        'diagnostics':[{'code':'rendered_dom_mismatch','message':'Different DOM',
            'differences':[{'path':'root.2','expected':'button|class=','actual':'button|'}],
            'comparison_policy':{'approved':False,'reasons':['exact_attribute_presence_required']}},
            {'code':'missing_event_bindings','message':'Missing unassign','location':'template'}],
        'interaction':[]}


class RepairContextTests(unittest.TestCase):
    def test_style_aggregation_keeps_paths_values_counts_and_upstream_overflow(self):
        original=evaluation()['styles'];saved=deepcopy(original)
        summary=style_summary(original)
        self.assertEqual(original,saved)
        self.assertEqual(summary['recorded_difference_count'],500)
        self.assertTrue(summary['upstream_truncated'])
        self.assertEqual(summary['groups'][0]['count'],500)
        self.assertEqual(summary['groups'][0]['examples'][0],original['differences'][0])
        self.assertEqual(len(summary['groups'][0]['examples']),2)
        self.assertLess(len(encoded(summary)),1200)

    def test_every_property_has_a_group_not_only_first_n_raw_rows(self):
        rows=[{'path':'root','property':prop,'source':'x','target':None}
              for prop in ('height','width','color') for _ in range(30)]
        summary=style_summary({'differences':rows})
        self.assertEqual({g['property'] for g in summary['groups']},{'height','width','color'})
        self.assertTrue(all(g['kinds']['target_missing']==30 for g in summary['groups']))

    def test_duplicate_issues_collapse_but_different_locations_do_not(self):
        first={'code':'missing_event_bindings','message':'Missing handler','location':'template.a'}
        second={**first,'location':'template.b'}
        result=compact_issues([first,first,second])
        self.assertEqual(len(result),2)
        self.assertEqual(result[0]['details']['duplicate_count'],2)
        self.assertEqual(result[1]['location'],'template.b')

    def test_DOM_and_control_location_evidence_survives_old_builder_compaction(self):
        data=evaluation();before=deepcopy(data)
        errors,visual=model_evidence(data)
        prompt=legacy_stage(PROJECT/'engine','repair_prompt',source='',code=SAN,ssm={},
            errors=errors,visual_errors=visual)['prompt']
        self.assertIn('root.2',prompt)
        self.assertIn('button|class=',prompt)
        self.assertIn('exact_attribute_presence_required',prompt)
        self.assertNotIn('root.499',prompt)
        self.assertEqual(data,before)

    def test_known_errors_select_sections_and_keep_full_methods_and_defaults(self):
        ssm={'script':{'options':{'props':[{'name':'x','default':{'a':[1,2]}}],
                                  'methods':[{'name':'setValue','body_full':'this[key]=value;'}]}},
            'template':{'dom_tree':{}},'styles':{'style_blocks':[{'content':'.x{color:red}'}],
                                                'css_rules':['same CSS again']},
            'binding_graph':{'unrelated':'NEVER_SEND'},'event_model':{'unrelated':'NEVER_SEND'}}
        data=evaluation();before=deepcopy(ssm)
        result,selection=relevant_ssm(ssm,data)
        self.assertEqual(result['script'],ssm['script'])
        self.assertNotIn('binding_graph',result)
        self.assertNotIn('event_model',result)
        self.assertNotIn('css_rules',result['styles'])
        self.assertEqual(selection['selection'],'error_related_sections')
        self.assertEqual(ssm,before)

    def test_unknown_error_conservatively_retains_full_SSM(self):
        ssm={'unknown':{'critical_source_contract':'must retain'}}
        data=evaluation();data['diagnostics']=[{'code':'new_future_error'}]
        result,selection=relevant_ssm(ssm,data)
        self.assertEqual(result,ssm)
        self.assertEqual(selection['selection'],'full_ssm_fallback')

    def test_projection_replaces_exact_SSM_only_not_current_code_or_contract(self):
        ssm={'template':{},'script':{'options':{}},'irrelevant_graph':'not selected'}
        original='contract MUST_REMAIN\n--- SSM ---\n'+json.dumps(ssm,ensure_ascii=False,indent=2)+'\n\n--- Current San Code ---\n'+SAN
        prompt,audit=project_prompt(original,ssm,evaluation())
        self.assertTrue(audit['ssm_projection_applied'])
        self.assertNotIn('irrelevant_graph',prompt.split('--- Relevant SSM Evidence ---')[1])
        self.assertIn('contract MUST_REMAIN',prompt)
        self.assertTrue(prompt.endswith(SAN))
        self.assertEqual(audit['legacy_builder_chars'],len(original))
        self.assertFalse(audit['full_evaluation_appended'])

    def test_existing_focused_prompt_stays_focused_and_bad_full_marker_blocks(self):
        prompt,audit=project_prompt('existing focused prompt',{'anything':'x'},evaluation())
        self.assertFalse(audit['ssm_projection_applied'])
        self.assertNotIn('"anything"',prompt)
        with self.assertRaises(ServiceError):
            project_prompt('--- SSM ---\nMISMATCH',{'anything':'x'},evaluation())

    def test_large_observation_is_explicitly_marked_not_silently_truncated(self):
        issue={'code':'rendered_dom_mismatch','differences':[{'path':'root','actual':'x'*5000}]}
        data=compact_issues([issue])[0]['details']['differences']['examples'][0]['actual']
        self.assertEqual(data['original_chars'],5000)
        self.assertTrue(data['truncated'])


class RepairContextGraphTests(ModularFixture,unittest.TestCase):
    def test_rules_get_full_evidence_model_gets_summary_and_failed_output_is_retested(self):
        observed=[];messages=[];exchange=self.model.exchange
        def record(value):messages.append(value);return exchange(value)
        self.model.exchange=record;self.model.codes=[SAN.replace('Hello','BAD'),SAN]
        def wrapped(repository,action,**kwargs):
            observed.append((action,deepcopy(kwargs)))
            return checks(repository,action,**kwargs)
        self.service.checks=wrapped
        original=self.service.evaluate
        def changed(key,revision):
            result=original(key,revision)
            if revision['number']==0:
                data=evaluation()
                result.update(styles=data['styles'],ui_restoration=data['ui_restoration'],
                    different_pixel_ratio=data['different_pixel_ratio'],ssim=data['ssim'])
                result['dimensions']['visual']='fail'
            return result
        self.service.evaluate=changed
        key=self.enqueue(max_repair_rounds=1)
        report=self.run_graph(key)
        self.assertEqual(report['status'],'finished')
        self.assertEqual(self.model.calls,2)
        raw=next(kwargs for action,kwargs in observed if action=='rules')
        compact=next(kwargs for action,kwargs in observed if action=='repair_prompt')
        self.assertEqual(len(raw['visual_errors'][0]['details']['styles']['differences']),500)
        self.assertNotIn('differences',compact['visual_errors'][0]['details']['styles'])
        self.assertNotIn('Actual target evaluation',messages[1][1]['content'])
        self.assertNotIn('root.499',messages[1][1]['content'])
        context=self.service.cached(key,'calls/1/repair-context.json')
        self.assertEqual(context['policy'],'repair-evidence-projection-v1')
        self.assertFalse(context['full_evaluation_appended'])
        self.assertTrue(report['state']['decisions'][0]['accepted'])
        self.assertIsNotNone(self.service.cached(key,'evaluations/0.json'))


if __name__=='__main__':unittest.main()
