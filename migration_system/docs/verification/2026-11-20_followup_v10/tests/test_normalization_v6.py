"""Rules compose without extra model calls or bypassing final acceptance."""
from types import SimpleNamespace
import unittest
from test_modular_system import PROJECT
from card_migration_system.stages.normalization import normalize_proposal, MAX_PASSES


class Syntax:
    def __init__(self): self.calls=[]
    def syntax(self, source, code, normalize=False):
        self.calls.append(code)
        return {'code':code.replace('BAD_ATTR','GOOD_ATTR'), 'changes':[],
                'after':{'status':'fail' if 'BAD_SCRIPT' in code else 'pass'}}


class NormalizationTests(unittest.TestCase):
    def run_rules(self, code, checks):
        return normalize_proposal(SimpleNamespace(repository_root=PROJECT/'engine'),checks,Syntax(),
                                  'source',code,{}, {'diagnostics':[]})

    def test_revalidates_every_intermediate_instead_of_using_old_diagnostics(self):
        seen=[]
        def checks(_,action,**kw):
            seen.append((action,kw['code']))
            if action=='validate':return {'validation_errors':[{'code':kw['code']}]}
            self.assertEqual(kw['errors'],[{'code':kw['code']}])
            return {'code':{'raw':'shape','shape':'defaults'}.get(kw['code'],kw['code']), 'changes':[]}
        result=self.run_rules('raw',checks)
        self.assertEqual(result['code'],'defaults');self.assertEqual(result['stop'],'fixed_point')
        self.assertEqual(result['model_calls'],0)
        self.assertEqual([c for a,c in seen if a=='validate'],['raw','shape','defaults'])

    def test_valid_but_semantically_wrong_template_getter_is_still_normalized(self):
        def checks(_,action,**kw):
            if action=='validate':
                self.assertNotIn('BAD_ATTR',kw['code']);return {'validation_errors':[]}
            return {'code':kw['code'],'changes':[]}
        self.assertEqual(self.run_rules('BAD_ATTR',checks)['code'],'GOOD_ATTR')

    def test_unparsed_script_never_enters_semantic_rules(self):
        def checks(*a,**kw):self.fail('semantic rules ran on malformed JavaScript')
        self.assertEqual(self.run_rules('BAD_SCRIPT',checks)['code'],'BAD_SCRIPT')

    def test_cycle_keeps_original_and_records_all_attempts(self):
        def checks(_,action,**kw):
            return {'validation_errors':[]} if action=='validate' else {'code':{'a':'b','b':'a'}[kw['code']],'changes':['cycle']}
        result=self.run_rules('a',checks)
        self.assertEqual(result['code'],'a');self.assertEqual(result['stop'],'rule_cycle_original_retained')
        self.assertEqual(len(result['passes']),2)

    def test_pass_limit_is_explicit_not_an_unbounded_rule_loop(self):
        def checks(_,action,**kw):
            return {'validation_errors':[]} if action=='validate' else {'code':kw['code']+'x','changes':[]}
        result=self.run_rules('a',checks)
        self.assertEqual(len(result['passes']),MAX_PASSES)
        self.assertEqual(result['stop'],'bounded_pass_limit')


if __name__=='__main__':unittest.main()
