"""Read-only legacy SSM integration; no pipeline, regex-parser fallback or LLM."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from ..reporting.identity import digest


class ExtractionError(ValueError):
    pass


def source_binding(repository):
    root = Path(repository).resolve()
    files = sorted((root / 'SSM').rglob('*.py')) + [root / 'SSM/extractors/parse_sfc.cjs',
              root / 'package.json', root / 'package-lock.json']
    if not (root / 'SSM/extractors/factory.py').is_file():
        raise ExtractionError('ssm_extractor_missing')
    try:
        result = {}
        for path in files:
            if not path.resolve().is_relative_to(root):
                raise ExtractionError('ssm_extractor_path_invalid')
            result[path.relative_to(root).as_posix()] = sha256(path.read_bytes()).hexdigest()
        return result
    except OSError:
        raise ExtractionError('ssm_extractor_or_lock_missing') from None


def _environment():
    # NODE_OPTIONS/PYTHONPATH, model credentials and tracing variables are not inherited.
    allowed = {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH', 'PATHEXT', 'COMSPEC'}
    result = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    result.update(PYTHONHASHSEED='0', PYTHONIOENCODING='utf-8')
    return result


class SSMExtractor:
    def __init__(self, repository):
        self.repository = Path(repository).resolve()

    def extract(self, source, filename, expected_sha256):
        if (type(source) is not bytes or not source.strip() or len(source) > 262144
                or type(filename) is not str or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,100}\.vue', filename)):
            raise ExtractionError('ssm_invalid_input')
        if sha256(source).hexdigest() != expected_sha256:
            raise ExtractionError('ssm_source_hash_mismatch')
        try:
            text = source.decode('utf-8')
        except UnicodeError:
            raise ExtractionError('ssm_invalid_utf8') from None
        if '\x00' in text:
            raise ExtractionError('ssm_invalid_input')
        files = source_binding(self.repository)
        node = shutil.which('node')
        if not node:
            raise ExtractionError('ssm_node_missing')
        worker = Path(__file__).with_name('ssm_worker.py')
        own_files = {path.name: sha256(path.read_bytes()).hexdigest() for path in
                     (Path(__file__), worker, worker.with_name('ssm_bridge.cjs'))}
        node_hash = sha256(Path(node).read_bytes()).hexdigest()
        request = {'source': text, 'filename': filename, 'source_sha256': expected_sha256, 'files': files}
        try:
            # -S/-s avoid third-party site initialization. No shell or uploaded file is executed.
            proc = subprocess.run([sys.executable, '-S', '-s', str(worker), str(self.repository), node],
                                  input=json.dumps(request, ensure_ascii=True).encode(), capture_output=True,
                                  timeout=30, check=False, cwd=self.repository, env=_environment())
        except subprocess.TimeoutExpired:
            raise ExtractionError('ssm_extraction_timeout') from None
        except OSError:
            raise ExtractionError('ssm_process_unavailable') from None
        if proc.returncode or len(proc.stdout) > 8 * 1024 * 1024:
            raise ExtractionError('ssm_worker_failed')
        try:
            payload = json.loads(proc.stdout)
        except (ValueError, UnicodeError):
            raise ExtractionError('ssm_worker_invalid_response') from None
        if (type(payload) is not dict or payload.get('status') != 'completed'):
            code = payload.get('error') if type(payload) is dict else None
            raise ExtractionError(code if type(code) is str and re.fullmatch(r'ssm_[a-z_]{1,80}', code)
                                  else 'ssm_worker_invalid_response')
        ssm = payload.get('ssm')
        if (type(ssm) is not dict or ssm.get('schema_version') != '3.0'
                or any(type(ssm.get(key)) is not dict for key in
                       ('metadata', 'template', 'script', 'styles', 'binding_graph', 'event_model', 'style_model'))
                or ssm['metadata'].get('source_file') != filename):
            raise ExtractionError('ssm_output_shape_invalid')
        runtime = payload.get('runtime')
        if (type(runtime) is not dict or type(runtime.get('node')) is not str
                or type(runtime.get('python')) is not str or type(runtime.get('packages')) is not dict
                or set(runtime['packages']) != {'@vue/compiler-sfc', '@vue/compiler-dom', '@babel/parser', '@babel/traverse'}
                or any(type(value) is not str for value in runtime['packages'].values())
                or type(runtime.get('loaded_module_sha256')) is not dict or not runtime['loaded_module_sha256']):
            raise ExtractionError('ssm_runtime_binding_invalid')
        if source_binding(self.repository) != files:
            raise ExtractionError('ssm_implementation_drift')
        for name, expected in own_files.items():
            if sha256(worker.with_name(name).read_bytes()).hexdigest() != expected:
                raise ExtractionError('ssm_adapter_drift')
        if sha256(Path(node).read_bytes()).hexdigest() != node_hash:
            raise ExtractionError('ssm_node_drift')
        for name, expected in runtime['loaded_module_sha256'].items():
            if (type(name) is not str or not name.startswith('node_modules/') or '\\' in name
                    or '..' in Path(name).parts or type(expected) is not str or not re.fullmatch(r'[0-9a-f]{64}', expected)):
                raise ExtractionError('ssm_runtime_binding_invalid')
            path = (self.repository / name).resolve()
            try:
                matches = path.is_relative_to(self.repository) and sha256(path.read_bytes()).hexdigest() == expected
            except OSError:
                matches = False
            if not matches:
                raise ExtractionError('ssm_dependency_drift')
        binding = {'protocol': 'ssm-extraction-probe-v1', 'schema_version': '3.0', 'legacy_files_sha256': files,
                   'adapter_files_sha256': own_files, 'runtime': payload['runtime'],
                   'node_executable_sha256': node_hash,
                   'python_executable_sha256': sha256(Path(sys.executable).read_bytes()).hexdigest()}
        return {'status': 'completed', 'ssm': ssm, 'source_sha256': expected_sha256,
                'binding': binding, 'binding_sha256': digest(binding),
                'limitations': ['options_api_single_element_root_only', 'no_dependency_source_resolution',
                                'css_and_cross_block_relations_are_heuristic', 'not_semantic_equivalence_or_coverage_evidence'],
                'actual_model_calls': 0, 'langsmith_uploaded': False, 'production_ready': False}
