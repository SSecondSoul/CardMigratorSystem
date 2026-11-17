"""Real Node/Python AST extraction over synthetic text, never real model requests."""
from contextlib import redirect_stdout
from dataclasses import replace
from hashlib import sha256
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
REPOSITORY = PROJECT.parent
sys.path.insert(0, str(PROJECT / 'src'))
from test_scaffold import copy_fixture
from card_migration_system.adapters.ssm import ExtractionError, SSMExtractor, _environment, source_binding
from card_migration_system.application.service import Service
from card_migration_system.application.storage import StorageError
from card_migration_system.config import load_settings
from card_migration_system.interfaces.cli import main
from card_migration_system.persistence.database import initialize
from card_migration_system.stages.extract import extract_registered_input

SOURCE = b'''<template><button class="counter" @click="inc">{{ count }}</button></template>
<script>export default {name:'Counter',props:{label:{type:String,default:'ok'}},
data(){return {count:0}},computed:{doubled(){return this.count*2}},
methods:{inc(){this.count++}}}</script><style scoped>.counter {color:red}</style>'''


class AdapterTests(unittest.TestCase):
    def extract(self, source=SOURCE, filename='Counter.vue'):
        return SSMExtractor(REPOSITORY).extract(source, filename, sha256(source).hexdigest())

    def test_real_ast_extracts_template_script_styles_and_relations(self):
        result = self.extract()
        ssm = result['ssm']
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(ssm['schema_version'], '3.0')
        self.assertEqual(ssm['metadata']['component_name'], 'Counter')
        self.assertEqual(ssm['metadata']['source_file'], 'Counter.vue')
        self.assertEqual(ssm['template']['dom_tree']['source_tag'], 'button')
        self.assertIn('inc', json.dumps(ssm['event_model']))
        self.assertIn('count', json.dumps(ssm['binding_graph']))
        self.assertIn('red', json.dumps(ssm['styles']))
        self.assertIn('@vue/compiler-sfc', result['binding']['runtime']['packages'])
        self.assertTrue(result['binding']['runtime']['loaded_module_sha256'])
        self.assertEqual(result['actual_model_calls'], 0)
        self.assertFalse(result['langsmith_uploaded'])
        self.assertNotIn('SSM.extractors.factory', sys.modules)

    def test_repeated_extraction_is_deterministic(self):
        first, second = self.extract(), self.extract()
        self.assertEqual(first, second)

    def test_uploaded_imports_and_top_level_code_are_not_executed(self):
        source = b'''<template><div>parse only</div></template><script>
import Missing from './does-not-exist';
throw new Error('SOURCE_MUST_NOT_EXECUTE');
export default {name:'ParseOnly',components:{Missing}};</script>'''
        result = self.extract(source)
        self.assertEqual(result['status'], 'completed')
        self.assertIn('./does-not-exist', json.dumps(result['ssm']['script']))

    def test_sfc_errors_are_not_regex_fallback_success(self):
        with self.assertRaisesRegex(ExtractionError, '^ssm_sfc_syntax_error$'):
            self.extract(b'<template><div/></template><template><p/></template>')

    def test_invalid_script_is_blocked_without_source_excerpt(self):
        with self.assertRaisesRegex(ExtractionError, '^ssm_script_syntax_error$'):
            self.extract(b'<template><div/></template><script>const SECRET_SENTINEL = ;</script>')

    def test_unsupported_syntax_is_blocked_instead_of_silently_dropped(self):
        cases = [(b'<template><div/></template><script setup>const x=1</script>', 'ssm_script_setup_not_supported'),
                 (b'<template><div/><p/></template>', 'ssm_single_element_root_required'),
                 (b'<template src="./part.html"></template>', 'ssm_external_blocks_not_supported'),
                 (b'<script>export default {}</script>', 'ssm_template_required')]
        for source, code in cases:
            with self.subTest(code=code), self.assertRaisesRegex(ExtractionError, '^' + code + '$'):
                self.extract(source)

    def test_input_guards_run_before_starting_process(self):
        extractor = SSMExtractor(REPOSITORY)
        with patch('card_migration_system.adapters.ssm.subprocess.run', side_effect=AssertionError('no process')):
            for source, filename, fingerprint, code in [
                (SOURCE, '../Counter.vue', sha256(SOURCE).hexdigest(), 'ssm_invalid_input'),
                (SOURCE, 'Counter.vue', '0'*64, 'ssm_source_hash_mismatch'),
                (b'\xff', 'Counter.vue', sha256(b'\xff').hexdigest(), 'ssm_invalid_utf8'),
                (b'x'*262145, 'Counter.vue', '0'*64, 'ssm_invalid_input')]:
                with self.subTest(code=code), self.assertRaisesRegex(ExtractionError, '^' + code + '$'):
                    extractor.extract(source, filename, fingerprint)

    def test_missing_node_is_explicit(self):
        with patch('card_migration_system.adapters.ssm.shutil.which', return_value=None):
            with self.assertRaisesRegex(ExtractionError, '^ssm_node_missing$'):
                self.extract()

    def test_missing_lock_is_explicit(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(REPOSITORY / 'SSM', root / 'SSM', ignore=shutil.ignore_patterns('__pycache__'))
            with self.assertRaisesRegex(ExtractionError, '^ssm_extractor_or_lock_missing$'):
                source_binding(root)

    def test_missing_dependencies_do_not_fallback(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(REPOSITORY / 'SSM', root / 'SSM', ignore=shutil.ignore_patterns('__pycache__'))
            for name in ('package.json', 'package-lock.json'):
                shutil.copyfile(REPOSITORY / name, root / name)
            with self.assertRaisesRegex(ExtractionError, '^ssm_dependency_missing$'):
                SSMExtractor(root).extract(SOURCE, 'Counter.vue', sha256(SOURCE).hexdigest())

    def test_process_timeout_is_a_bounded_failure(self):
        with patch('card_migration_system.adapters.ssm.subprocess.run', side_effect=subprocess.TimeoutExpired('worker', 30)):
            with self.assertRaisesRegex(ExtractionError, '^ssm_extraction_timeout$'):
                self.extract()

    def test_invalid_output_is_not_accepted(self):
        for output in (b'not json', b'[]', b'{"status":"completed","ssm":{}}'):
            with self.subTest(output=output):
                with patch('card_migration_system.adapters.ssm.subprocess.run',
                           return_value=subprocess.CompletedProcess([], 0, output, b'SECRET_SENTINEL')):
                    with self.assertRaises(ExtractionError) as caught:
                        self.extract()
                    self.assertNotIn('SECRET_SENTINEL', str(caught.exception))

    def test_plausible_ssm_without_runtime_evidence_is_not_accepted(self):
        ssm = {key: {} for key in ('metadata', 'template', 'script', 'styles', 'binding_graph', 'event_model', 'style_model')}
        ssm.update(schema_version='3.0', metadata={'source_file': 'Counter.vue'})
        output = json.dumps({'status': 'completed', 'ssm': ssm}).encode()
        with patch('card_migration_system.adapters.ssm.subprocess.run',
                   return_value=subprocess.CompletedProcess([], 0, output, b'')):
            with self.assertRaisesRegex(ExtractionError, '^ssm_runtime_binding_invalid$'):
                self.extract()

    def test_extractor_change_during_run_blocks_commit(self):
        binding = source_binding(REPOSITORY)
        with patch('card_migration_system.adapters.ssm.source_binding', side_effect=[binding, {}]):
            with self.assertRaisesRegex(ExtractionError, '^ssm_implementation_drift$'):
                self.extract()

    def test_subprocess_environment_does_not_forward_credentials_or_injection(self):
        with patch.dict('os.environ', {'LLM_API_KEY': 'secret', 'LANGSMITH_API_KEY': 'secret',
                                     'NODE_OPTIONS': '--require=untrusted', 'PYTHONPATH': 'untrusted'}):
            env = _environment()
            self.assertNotIn('LLM_API_KEY', env)
            self.assertNotIn('LANGSMITH_API_KEY', env)
            self.assertNotIn('NODE_OPTIONS', env)
            self.assertNotIn('PYTHONPATH', env)
            self.assertEqual(env['PYTHONHASHSEED'], '0')


class RegisteredInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        project = copy_fixture(Path(self.temp.name))
        shutil.copyfile(PROJECT / 'requirements.lock', project / 'requirements.lock')
        shutil.copytree(PROJECT / 'migrations', project / 'migrations', ignore=shutil.ignore_patterns('__pycache__'))
        # Only the trusted extractor/contract checkout is read from the real repo.
        # Every database/input/output stays in this test's temporary tree.
        self.settings = replace(load_settings(project_root=project, environ={}), repository_root=REPOSITORY)
        initialize(self.settings)
        self.service = Service(self.settings)
        self.addCleanup(self.service.close)
        self.input = self.service.create_input({'filename': 'Counter.vue', 'source': SOURCE.decode()})
        task = self.service.create_task({'input_id': self.input['input_id']})
        self.run_id = self.service.enqueue(task['task_id'], {'profile': 'success', 'max_repair_rounds': 0}, 'extract-test')['run_id']

    def test_real_saved_input_produces_auditable_probe_without_mutating_run(self):
        before = self.service.report(self.run_id)
        result = extract_registered_input(self.settings, run_id=self.run_id)
        self.assertEqual(result['status'], 'completed')
        directory = Path(result['directory'])
        receipt_bytes = (directory / 'receipt.json').read_bytes()
        receipt = json.loads(receipt_bytes)
        self.assertEqual(sha256(receipt_bytes).hexdigest(), result['receipt_sha256'])
        self.assertEqual(sha256((directory / 'ssm.json').read_bytes()).hexdigest(), receipt['ssm']['sha256'])
        self.assertEqual(sha256((directory / 'source.vue').read_bytes()).hexdigest(), self.input['sha256'])
        self.assertEqual(receipt['source']['referenced_run_id'], self.run_id)
        self.assertEqual(receipt['migration_quality_status'], 'not_run')
        self.assertEqual(before, self.service.report(self.run_id))
        self.assertFalse(self.settings.graph_database.exists())

    def test_failure_receipt_has_no_ssm_or_fake_quality_pass(self):
        with patch('card_migration_system.stages.extract.SSMExtractor.extract', side_effect=ExtractionError('ssm_node_missing')):
            result = extract_registered_input(self.settings, input_id=self.input['input_id'])
        self.assertEqual(result['status'], 'blocked')
        receipt = json.loads((Path(result['directory']) / 'receipt.json').read_bytes())
        self.assertIsNone(receipt['ssm'])
        self.assertIsNone(receipt['binding'])
        self.assertFalse((Path(result['directory']) / 'ssm.json').exists())
        self.assertEqual(receipt['migration_quality_status'], 'not_run')

    def test_corrupt_registered_source_is_blocked_before_parser(self):
        path = self.settings.artifact_dir / 'inputs' / self.input['input_id'] / 'Counter.vue'
        path.write_bytes(b'corrupt')
        with patch('card_migration_system.stages.extract.SSMExtractor.extract', side_effect=AssertionError('no parse')):
            with self.assertRaisesRegex(StorageError, '^artifact_hash_mismatch$'):
                extract_registered_input(self.settings, run_id=self.run_id)

    def test_reference_guards(self):
        for arguments in ({}, {'input_id': '../bad'}, {'run_id': self.run_id, 'input_id': self.input['input_id']}):
            with self.subTest(arguments=arguments), self.assertRaises(ExtractionError):
                extract_registered_input(self.settings, **arguments)

    def test_cli_extracts_registered_source_and_prints_only_summary(self):
        output = io.StringIO()
        with patch('card_migration_system.interfaces.cli.load_settings', return_value=self.settings), redirect_stdout(output):
            code = main(['extract-ssm', '--run-id', self.run_id])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result['actual_model_calls'], 0)
        self.assertEqual(result['status'], 'completed')
        self.assertNotIn('<template>', output.getvalue())

    def test_cli_blocked_probe_exits_nonzero_with_receipt(self):
        output = io.StringIO()
        with patch('card_migration_system.interfaces.cli.load_settings', return_value=self.settings), redirect_stdout(output):
            with patch('card_migration_system.stages.extract.SSMExtractor.extract', side_effect=ExtractionError('ssm_node_missing')):
                code = main(['extract-ssm', '--input-id', self.input['input_id']])
        self.assertEqual(code, 2)
        result = json.loads(output.getvalue())
        self.assertTrue((Path(result['directory']) / 'receipt.json').is_file())
        self.assertEqual(result['error'], 'ssm_node_missing')


if __name__ == '__main__':
    unittest.main()
