"""Related offline regressions; fixtures use temporary DBs, not the user's queue."""
import argparse
import json
from pathlib import Path
import sys
import time
import unittest

PROJECT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve()
    if output.exists() or not output.is_relative_to(PROJECT/'var'):
        raise ValueError('Choose a NEW result file below project/var')
    sys.path.insert(0,str(PROJECT/'tests'));sys.path.insert(0,str(PROJECT/'src'))
    loader=unittest.TestLoader()
    suites=[loader.discover(str(PROJECT/'tests'),pattern='test_modular_*.py')]
    names=['test_semantic_comparison_v1','test_repair_context','test_dynamic_setter_production',
           'test_san_business_contract_policy','test_production_scope','test_refactor_reuse']
    suites.extend(loader.loadTestsFromName(name) for name in names)
    counts=[s.countTestCases() for s in suites]
    begin=time.perf_counter()
    result=unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(suites))
    report={'scope':'offline_engineering_tests_not_component_migration_rate',
        'patterns':['test_modular_*.py',*names],'suite_counts':counts,
        'tests_run':result.testsRun,'passed':result.wasSuccessful(),'skipped':len(result.skipped),
        'failures':[case.id() for case,_ in result.failures],'errors':[case.id() for case,_ in result.errors],
        'elapsed_seconds':time.perf_counter()-begin,'paid_model_execution_requested':False}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
    if not result.wasSuccessful():raise SystemExit(1)


if __name__=='__main__':main()
