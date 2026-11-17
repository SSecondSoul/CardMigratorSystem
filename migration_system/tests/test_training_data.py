"""Offline data isolation; no Torch/model downloads/training in engineering tests."""
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PROJECT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PROJECT/'src'))
from test_modular_system import ModularFixture,SOURCE,SAN
from card_migration_system.training.data import build_dataset
from card_migration_system.training.lora import train
from card_migration_system.application.service import ServiceError


class TrainingDataTests(ModularFixture,unittest.TestCase):
    def manifest(self,pairs):
        path=self.project/'pairs.json';path.write_text(json.dumps({'schema_version':1,'pairs':pairs}),encoding='utf-8');return path
    def pair(self,name,group,split):
        (self.project/(name+'.vue')).write_text(SOURCE.replace('Hello',name),encoding='utf-8')
        (self.project/(name+'.san')).write_text(SAN.replace('Hello',name),encoding='utf-8')
        return {'id':name,'vue':name+'.vue','san':name+'.san','group':group,'split':split}
    def test_group_leakage_rejected_before_training(self):
        manifest=self.manifest([self.pair('One','same','train'),self.pair('Two','same','test')])
        with patch('card_migration_system.training.data.SSMExtractor') as extractor:
            extractor.return_value.extract.return_value={'ssm':{}}
            with self.assertRaisesRegex(ServiceError,'training_group_leakage'):build_dataset(self.settings,manifest,self.project/'var/training/data')
    def test_distinct_groups_export_with_fingerprints(self):
        manifest=self.manifest([self.pair('One','one','train'),self.pair('Two','two','validation')])
        with patch('card_migration_system.training.data.SSMExtractor') as extractor:
            extractor.return_value.extract.return_value={'ssm':{}}
            result=build_dataset(self.settings,manifest,self.project/'var/training/data')
        self.assertEqual(result['counts'],{'train':1,'validation':1,'test':0})
        self.assertTrue((self.project/'var/training/data/few-shot.json').is_file())
    def test_training_requires_explicit_execution_and_license(self):
        with self.assertRaisesRegex(ServiceError,'training_requires_explicit_execute'):train(self.settings,'missing.json')
        config=self.project/'training.json';config.write_text('{"license_confirmed":false}',encoding='utf-8')
        with self.assertRaisesRegex(ServiceError,'base_model_license_confirmation_required'):train(self.settings,config,execute=True)

if __name__=='__main__':unittest.main()
