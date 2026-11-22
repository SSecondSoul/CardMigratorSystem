"""Golden equivalence against the experiment checkout; not a runtime dependency."""
import ast
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest
from typing import Any

PROJECT=Path(__file__).resolve().parents[1];ORIGINAL=PROJECT.parent
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.adapters.engine import verify_engine
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.adapters.ssm import SSMExtractor
from card_migration_system.prompts.generation import build_generation_messages,SYSTEM

SOURCE='<template><button class="card" @click="increment">{{count}}</button></template><script>export default {name:"CounterCard",data(){return {count:0}},methods:{increment(){this.count++}}}</script><style>.card{color:rgb(20,40,60)}</style>'
TARGET='<template><button class="card" on-click="increment">{{count}}</button></template><script>const san=require("san");const DataTypes=san.DataTypes;module.exports=san.defineComponent({name:"CounterCard",dataTypes:{},initData(){return {count:0}},increment(){this.data.set("count",this.data.get("count")+1)}});</script><style>.card{color:rgb(20,40,60)}</style>'


@unittest.skipUnless((ORIGINAL/'local_server/api/evaluation_routes.py').is_file(),'Source comparison runs only in the experiment checkout')
class ReuseEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=SOURCE;cls.target=TARGET
        cls.ssm=SSMExtractor(PROJECT/'engine').extract(SOURCE.encode(),'CounterCard.vue',sha256(SOURCE.encode()).hexdigest())['ssm']

    def test_internal_bundle_source_bodies_are_unchanged_and_no_experiment_runner_is_imported(self):
        self.assertEqual(verify_engine(PROJECT/'engine')['files'],99)
        manifest=json.loads((PROJECT/'engine/MANIFEST.json').read_bytes())
        same=0
        for name,item in manifest['files'].items():
            if item['transformation']=='none':
                self.assertEqual((PROJECT/'engine'/name).read_bytes(),(ORIGINAL/item['source_path']).read_bytes(),name)
                same+=1
        self.assertEqual(same,89)
        authored=manifest['files']['migration_pipeline/utils/native_select_semantics.cjs']
        self.assertIsNone(authored['source_path']);self.assertIsNone(authored['source_sha256'])
        self.assertIn('new_shared_source_bound',authored['transformation'])
        # Seven explicitly versioned advances; all other reused bytes remain exact.
        modified={name:item for name,item in manifest['files'].items() if item['transformation'].startswith('2026-11-18_')}
        self.assertEqual(set(modified),{'migration_pipeline/stages/validate.py',
            'migration_pipeline/utils/method_interface_semantics.cjs','migration_pipeline/utils/repair_prompt.py',
            'migration_pipeline/utils/bounded_semantics.cjs','migration_pipeline/stages/repair.py',
            'migration_pipeline/utils/repair_scheduler.py','migration_pipeline/utils/residual_semantics.cjs'})
        for name,item in modified.items():
            self.assertEqual(sha256((ORIGINAL/item['source_path']).read_bytes()).hexdigest(),item['source_sha256'])
        self.assertFalse((PROJECT/'engine/migration_pipeline/orchestrator.py').exists())

    def test_generation_messages_are_byte_equal_to_original_pure_builder(self):
        route=(ORIGINAL/'local_server/api/evaluation_routes.py').read_text(encoding='utf-8')
        builder=next(n for n in ast.parse(route).body if isinstance(n,ast.FunctionDef) and n.name=='_build_generation_prompt')
        text=(ORIGINAL/'migration_pipeline/utils/class_binding_contract.py').read_text(encoding='utf-8')
        rule=next(n.value for n in ast.parse(text).body if isinstance(n,ast.Assign)
                  and any(isinstance(t,ast.Name) and t.id=='CLASS_BINDING_RULE' for t in n.targets))
        namespace={'json':json,'Any':Any,'CLASS_BINDING_RULE':ast.literal_eval(rule)}
        exec(compile(ast.Module(body=[builder],type_ignores=[]),'<original-pure-builder>','exec'),namespace)
        expected=[{'role':'system','content':SYSTEM},{'role':'user','content':namespace['_build_generation_prompt'](self.ssm)}]
        self.assertEqual(build_generation_messages(PROJECT/'engine',self.ssm)[0],expected)

    def test_SSM_matches_original_extractor_exactly(self):
        old=SSMExtractor(ORIGINAL).extract(SOURCE.encode(),'CounterCard.vue',sha256(SOURCE.encode()).hexdigest())['ssm']
        self.assertEqual(self.ssm,old)

    def test_static_rules_and_repair_prompt_match_original_except_versioned_computed_read_instruction(self):
        first=legacy_stage(ORIGINAL,'validate',source=self.source,code=self.target,ssm=self.ssm)
        second=legacy_stage(PROJECT/'engine','validate',source=self.source,code=self.target,ssm=self.ssm)
        for key in ('validation_passed','validation_errors','validation_warnings'):
            self.assertEqual(first[key],second[key],key)
        # Visual rule case also verifies that CSS restoration stays a real rule,
        # not a fake successful score or another model response.
        broken=self.target.replace('rgb(20,40,60)','rgb(200,0,0)')
        for action in ('rules','repair_prompt'):
            a=legacy_stage(ORIGINAL,action,source=self.source,code=broken,ssm=self.ssm,
                           errors=[],visual_errors=[{'code':'visual_mismatch'}])
            b=legacy_stage(PROJECT/'engine',action,source=self.source,code=broken,ssm=self.ssm,
                           errors=[],visual_errors=[{'code':'visual_mismatch'}])
            if action=='repair_prompt':
                # Assert the ONE declared prompt delta; no broad ignore/normalizer.
                old='"this.computed.foo()"'
                new='"this.computed.foo or this.computed.foo(); computed values live in this.data.get(\'foo\'), not an instance computed namespace"'
                self.assertEqual(a['prompt'].count(old),1)
                a={'prompt':a['prompt'].replace(old,new)}
            self.assertEqual(a,b,action)

    @unittest.skipUnless((ORIGINAL/'data/experiments/evaluator_calibration/2026-11-17_modular_product_filter_contract_replay_v4/implementation/migration_system/src/card_migration_system/application/migrations.py').is_file(), 'Historical pre-refactor implementation snapshot is unavailable')
    def test_repair_rules_syntax_and_candidate_call_gates_remain_original_after_evidence_projection(self):
        old=ORIGINAL/'data/experiments/evaluator_calibration/2026-11-17_modular_product_filter_contract_replay_v4/implementation/migration_system/src/card_migration_system/application/migrations.py'
        source=ast.parse(old.read_text(encoding='utf-8'))
        klass=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='MigrationService')
        before=next(n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name=='repair')
        new=ast.parse((PROJECT/'src/card_migration_system/stages/repair.py').read_text(encoding='utf-8'))
        after=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name=='propose_repair')
        saved=ast.parse((PROJECT/'docs/verification/2026-11-18_repair_context_v1/before/repair.py').read_text(encoding='utf-8'))
        archived=next(n for n in saved.body if isinstance(n,ast.FunctionDef) and n.name=='propose_repair')
        self.assertEqual([ast.dump(n) for n in before.body],[ast.dump(n) for n in archived.body])
        def branch(fn):
            return next(n for n in fn.body if isinstance(n,ast.If) and "rule['code']" in ast.unparse(n.test))
        old_branch,new_branch=branch(before),branch(after)
        # v3 narrows a previously overbroad rejection cache: only the exact
        # rejected rule candidate is suppressed, not every rule on that parent.
        # Pin this ONE AST delta; all other orchestration/gates stay compared.
        # v6 composes the SAME existing rules before/after a model proposal.
        # Project only these audited stage-boundary changes to compare the
        # original call budget, cache and acceptance orchestration underneath.
        projected=deepcopy(after)
        saved_current=ast.parse((ORIGINAL/'experiment_runs/general_repairs_v5_review_20261119/implementation/src/card_migration_system/stages/repair.py').read_text(encoding='utf-8'))
        prior_stage=next(n for n in saved_current.body if isinstance(n,ast.FunctionDef) and n.name=='propose_repair')
        # Verify the new protocol explicitly rather than pretending byte reuse.
        calls=[n for n in ast.walk(after) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='normalize_proposal']
        self.assertEqual(len(calls),2)
        self.assertEqual(ast.unparse(calls[0].args[5]),'ssm')
        self.assertEqual(ast.unparse(calls[1].args[4]),'raw_code')
        self.assertIn("model-outputs/{number}.san",ast.unparse(after))
        self.assertIn("normalizations/{number}.json",ast.unparse(after))
        # The frozen v3 body is the declared predecessor; compare its unchanged
        # orchestration to the pre-refactor reference after the v3 cache delta.
        after=prior_stage;projected=deepcopy(after);new_branch=branch(after)
        loop=next(n for n in projected.body if isinstance(n,ast.For))
        guard=loop.body[0].body[-1]
        self.assertIsInstance(guard,ast.If)
        self.assertEqual(ast.unparse(guard.test.values[-1]),"prior['code'] == rule['code']")
        guard.test.values.pop()
        self.assertEqual([ast.dump(n) for n in before.body[:before.body.index(old_branch)]],
                         [ast.dump(n) for n in projected.body[:projected.body.index(branch(projected))]])
        self.assertEqual([ast.dump(n) for n in old_branch.body],[ast.dump(n) for n in new_branch.body])
        for kind in (ast.For,):
            self.assertEqual(ast.dump(next(n for n in old_branch.orelse if isinstance(n,kind))),
                             ast.dump(next(n for n in new_branch.orelse if isinstance(n,kind))))
        self.assertEqual([ast.dump(n) for n in old_branch.orelse[-2:]],
                         [ast.dump(n) for n in new_branch.orelse[-2:]])
        self.assertEqual(ast.dump(next(n for n in old_branch.orelse if isinstance(n,ast.If)).body[0]),
                         ast.dump(next(n for n in new_branch.orelse if isinstance(n,ast.If)).body[0]))
        self.assertEqual([ast.dump(n) for n in before.body[before.body.index(old_branch)+1:]],
                         [ast.dump(n) for n in after.body[after.body.index(new_branch)+1:]])


if __name__=='__main__':unittest.main()
