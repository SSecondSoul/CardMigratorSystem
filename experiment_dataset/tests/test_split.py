"""Read-only split regression; no cloud calls or changes to original datasets."""
import importlib.util
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('component_split',HERE/'prepare_split.py')
split=importlib.util.module_from_spec(spec);spec.loader.exec_module(split)


class SplitTests(unittest.TestCase):
    def test_exact_ratio_strata_and_known_development_membership(self):
        plan=split.build(HERE.parent);record=json.loads(plan['files']['manifest.json'])
        self.assertEqual(record['counts'],{'total':100,'experiment':70,'validation':20,'test':10})
        self.assertEqual(record['stratified_counts'],{'simple':{'experiment':24,'validation':7,'test':3},'medium':{'experiment':23,'validation':7,'test':3},'complex':{'experiment':23,'validation':6,'test':4}})
        self.assertEqual(record['known_prior_development_in_experiment'],69)
        self.assertEqual(len({s['id'] for s in record['samples']}),100)
        for sample in record['samples']:
            if split.known_development(sample['prior_usage']):self.assertEqual(sample['subset'],'experiment')
            self.assertFalse(sample['independent_holdout'])

    def test_deterministic_selection_ignores_manifest_order(self):
        source=json.loads((HERE.parent/'data/datasets/dataset_manifest.json').read_bytes())['components']
        history,_=split.histories(HERE.parent)
        self.assertEqual(split.assign(source,history),split.assign(list(reversed(source)),history))

    def test_exact_vue_hash_never_crosses_subsets(self):
        record=json.loads(split.build(HERE.parent)['files']['manifest.json']);groups={}
        for sample in record['samples']:groups.setdefault(sample['vue_sha256'],set()).add(sample['subset'])
        self.assertTrue(all(len(group)==1 for group in groups.values()))

    def test_complete_source_component_files_are_preserved(self):
        record=json.loads(split.build(HERE.parent)['files']['manifest.json'])
        for sample in record['samples']:
            source=HERE.parent/sample['source_component_root']
            actual={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
            copied={p['path'][len(sample['component_root'])+1:] for p in record['payload_files'] if p['path'].startswith(sample['component_root']+'/')}
            self.assertEqual(actual,copied,sample['id'])
            for kind in ('vue','reference_san'):
                payload=next(p for p in record['payload_files'] if p['path']==sample[kind+'_file'])
                self.assertEqual(payload['sha256'],sample[kind+'_sha256'])

    def test_frozen_artifacts_match_plan_and_originals(self):
        plan=split.build(HERE.parent)
        for path,text in plan['files'].items():self.assertEqual((HERE/path).read_bytes(),text.encode('utf-8'),path)
        result=split.check(HERE,HERE.parent)
        self.assertEqual(result['status'],'verified');self.assertEqual(result['model_calls'],0)

    def test_copy_can_be_verified_without_original_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            copied=Path(temporary)/'standalone';shutil.copytree(HERE,copied,ignore=shutil.ignore_patterns('__pycache__'))
            self.assertEqual(split.check(copied)['counts']['total'],100)

    def test_tampering_and_extra_files_are_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            copied=Path(temporary)/'copy';shutil.copytree(HERE,copied,ignore=shutil.ignore_patterns('__pycache__'))
            record=json.loads((copied/'manifest.json').read_bytes());payload=copied/record['payload_files'][0]['path']
            original=payload.read_bytes();payload.write_bytes(original+b' changed by test')
            with self.assertRaisesRegex(ValueError,'Payload hash mismatch'):split.check(copied)
            payload.write_bytes(original)
            (copied/'test/unexpected.txt').write_text('temporary test only',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Unexpected or missing'):split.check(copied)


if __name__=='__main__':unittest.main()
