"""P2a offline tests. Mutable fixtures stay in TemporaryDirectory, not old inputs."""
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
import io
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import tomllib
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
REPOSITORY = PROJECT / 'engine'
sys.path.insert(0, str(PROJECT / "src"))

from card_migration_system.config import ConfigurationError, load_settings
from card_migration_system.contracts import ContractBindingError, load_p1_contracts
from card_migration_system.interfaces.cli import check_scaffold, main


def copy_fixture(root):
    project = root / "migration_system"
    (project / "configs").mkdir(parents=True)
    shutil.copyfile(PROJECT / "configs/development.toml", project / "configs/development.toml")
    shutil.copytree(PROJECT/'engine',project/'engine',ignore=shutil.ignore_patterns('node_modules','__pycache__','*.pyc'))
    return project


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = copy_fixture(Path(self.temp.name))

    def load(self, *, env=None, text=None):
        if text is not None:
            (self.project / "configs/development.toml").write_text(text, encoding="utf-8")
        return load_settings(project_root=self.project, environ={} if env is None else env)

    def original_text(self):
        return (PROJECT / "configs/development.toml").read_text(encoding="utf-8")

    def test_defaults_have_separate_runtime_and_evidence_paths(self):
        value = self.load()
        self.assertEqual(value.mode, "development_stub")
        self.assertEqual(value.port, 8790)
        self.assertEqual(value.business_database, self.project / "var/runtime/business.sqlite3")
        self.assertNotEqual(value.business_database, value.graph_database)
        self.assertEqual(value.artifact_dir, self.project / "var/artifacts")
        self.assertEqual(value.engine_root,self.project/'engine')

    def test_load_is_read_only_and_creates_no_databases_or_output(self):
        before = sorted(str(path.relative_to(self.project.parent)) for path in self.project.parent.rglob("*"))
        self.load()
        after = sorted(str(path.relative_to(self.project.parent)) for path in self.project.parent.rglob("*"))
        self.assertEqual(before, after)
        self.assertFalse((self.project / "var").exists())

    def test_only_namespaced_environment_is_read(self):
        settings = self.load(env={"LLM_API_KEY": "secret-sentinel", "LLM_MODEL": "ignore",
                                  "CARDMIG_SYSTEM_PORT": "8791"})
        self.assertEqual(settings.port, 8791)
        self.assertNotIn("secret-sentinel", json.dumps(settings.public_summary()))
        self.assertNotIn("LLM_MODEL", json.dumps(settings.public_summary()))

    def test_namespaced_environment_overrides_config(self):
        value = self.load(env={"CARDMIG_SYSTEM_HOST": "::1", "CARDMIG_SYSTEM_PORT": "8792"})
        self.assertEqual(value.host, "::1")
        self.assertEqual(value.port, 8792)

    def test_non_loopback_hosts_rejected(self):
        for value in ("0.0.0.0", "example.com", "localhost", "192.168.1.1"):
            with self.subTest(value=value), self.assertRaises(ConfigurationError):
                self.load(env={"CARDMIG_SYSTEM_HOST": value})

    def test_invalid_ports_rejected_without_printing_input(self):
        for value in ("0", "65536", "true", "secret-sentinel", "-1", "1.5", " 8790"):
            with self.subTest(value=value), self.assertRaises(ConfigurationError) as caught:
                self.load(env={"CARDMIG_SYSTEM_PORT": value})
            self.assertNotIn("secret-sentinel", str(caught.exception))

    def test_bool_and_string_config_port_not_coerced(self):
        for value in ("true", '"8790"'):
            with self.subTest(value=value), self.assertRaises(ConfigurationError):
                self.load(text=self.original_text().replace("port = 8790", f"port = {value}"))

    def test_real_execution_mode_not_available_in_scaffold(self):
        for value in ("real", "production", "fake-ready"):
            with self.subTest(value=value), self.assertRaises(ConfigurationError):
                self.load(env={"CARDMIG_SYSTEM_MODE": value})

    def test_unknown_secret_fields_and_schema_rejected(self):
        for text in (self.original_text().replace("schema_version = 1", "schema_version = 2"),
                     self.original_text().replace("schema_version = 1", "schema_version = true"),
                     self.original_text().replace("[app]", '[app]\napi_key = "secret-sentinel"')):
            with self.subTest(text=text[:40]), self.assertRaises(ConfigurationError):
                self.load(text=text)

    def test_missing_tables_or_path_rejected(self):
        for text in ('schema_version = 1\n', self.original_text().replace('runtime_dir = "var/runtime"', "")):
            with self.subTest(text=text), self.assertRaises(ConfigurationError):
                self.load(text=text)

    def test_runtime_cannot_escape_var(self):
        for path in ("..", "../data", "configs", "var/../../outside"):
            with self.subTest(path=path), self.assertRaises(ConfigurationError):
                self.load(text=self.original_text().replace('runtime_dir = "var/runtime"', f'runtime_dir = "{path}"'))

    def test_evidence_cannot_target_old_batch_or_snapshot(self):
        for path in ("../data/experiments/snapshots", "../data/experiments/pipeline/batches/old",
                     "../data/experiments/migration_system/../snapshots"):
            with self.subTest(path=path), self.assertRaises(ConfigurationError):
                self.load(text=self.original_text().replace(
                    'artifact_dir = "var/artifacts"', f'artifact_dir = "{path}"'))

    def test_config_cannot_be_read_outside_project(self):
        outside = self.project.parent / "outside.toml"
        outside.write_text(self.original_text(), encoding="utf-8")
        with self.assertRaises(ConfigurationError):
            load_settings(project_root=self.project, config_file=outside, environ={})

    def test_invalid_utf8_malformed_or_oversized_toml_rejected(self):
        for content in (b"\xff", b"[invalid", b"#" * 65537):
            (self.project / "configs/development.toml").write_bytes(content)
            with self.subTest(size=len(content)), self.assertRaises(ConfigurationError):
                self.load()


class ContractBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = copy_fixture(Path(self.temp.name))
        self.root = self.project/'engine'

    def test_pinned_api_supports_roundtrip_and_unknown_status(self):
        binding = load_p1_contracts(self.root)
        api = binding.contracts
        diagnostic = api.Diagnostic(diagnostic_id="d", code="kept", stage="s")
        self.assertEqual(api.load_contract(diagnostic.to_dict()), diagnostic)
        self.assertEqual(api.Status.UNKNOWN.value, "unknown")
        self.assertEqual(len(binding.source_sha256), 3)

    def test_pin_loader_does_not_import_old_pipeline(self):
        (self.root / "migration_pipeline/__init__.py").write_text(
            'raise AssertionError("old pipeline imported")', encoding="utf-8")
        import builtins
        normal_import = builtins.__import__

        def guarded(name, *args, **kwargs):
            if name == "migration_pipeline" or name.startswith("migration_pipeline."):
                raise AssertionError("old parent import")
            return normal_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=guarded):
            self.assertEqual(load_p1_contracts(self.root).contracts.Status.NOT_RUN.value, "not_run")

    def test_any_source_drift_blocks_before_execution(self):
        for name in ("__init__.py", "v1.py", "legacy.py"):
            path = self.root / "migration_pipeline/contracts" / name
            original = path.read_bytes()
            path.write_bytes(original + b'\nraise AssertionError("must not run")\n')
            with self.subTest(name=name), self.assertRaises(ContractBindingError):
                load_p1_contracts(self.root)
            path.write_bytes(original)

    def test_missing_source_blocks(self):
        (self.root / "migration_pipeline/contracts/v1.py").unlink()
        with self.assertRaises(ContractBindingError):
            load_p1_contracts(self.root)

    def test_cache_does_not_hide_later_source_drift(self):
        load_p1_contracts(self.root)
        path = self.root / "migration_pipeline/contracts/legacy.py"
        path.write_bytes(path.read_bytes() + b"\n# changed\n")
        with self.assertRaises(ContractBindingError):
            load_p1_contracts(self.root)

    def test_crlf_only_change_uses_documented_normalization(self):
        for path in (self.root / "migration_pipeline/contracts").glob("*.py"):
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.assertEqual(load_p1_contracts(self.root).contracts.Status.PASS.value, "pass")

    def test_legacy_projection_preserves_input_and_never_creates_browser_proof(self):
        api = load_p1_contracts(self.root).contracts
        old = {"final_passed": True, "future": {"n": [1]},
               "final_visual_eval_result": {"visual_eval_passed": True}}
        view = api.project_legacy(old, legacy_format=api.LegacyFormat.STATE)
        self.assertEqual(view.to_legacy(), old)
        self.assertEqual(next(item.status.value for item in view.evaluations
                              if item.dimension == "browser_visual"), "not_run")

    def test_relocated_roots_get_isolated_class_namespaces(self):
        other = Path(self.temp.name) / "second"
        other_project=copy_fixture(other)
        a, b = load_p1_contracts(self.root), load_p1_contracts(other_project/'engine')
        self.assertIsNot(a.contracts.Status, b.contracts.Status)
        self.assertEqual(a.manifest_sha256, b.manifest_sha256)
        self.assertIs(a.contracts.Status, load_p1_contracts(self.root).contracts.Status)

    def test_serialized_values_match_original_p1_binding(self):
        api = load_p1_contracts(self.root).contracts
        original = load_p1_contracts(REPOSITORY).contracts
        self.assertEqual(api.Budget(max_model_repair_calls=3, max_rule_steps=8).to_dict(),
                         original.Budget(max_model_repair_calls=3, max_rule_steps=8).to_dict())
        with self.assertRaises(api.ContractError):
            api.Budget.from_dict({**api.Budget(max_model_repair_calls=3, max_rule_steps=8).to_dict(),
                                  "future_field": 1})


class ScaffoldCLITests(unittest.TestCase):
    def test_worker_alias_routes_to_real_migration_not_development_fixture(self):
        with patch('card_migration_system.interfaces.system_cli.main',return_value=0) as route:
            self.assertEqual(main(['worker','--once']),0)
        route.assert_called_once_with(['migration-worker','--once'])

    def test_check_has_no_execution_or_write_side_effects(self):
        with TemporaryDirectory() as directory:
            project = copy_fixture(Path(directory))
            before = sorted(str(path) for path in Path(directory).rglob("*"))
            with patch("socket.socket.connect", side_effect=AssertionError("network")), \
                    patch("subprocess.run", side_effect=AssertionError("subprocess")), \
                    patch("pathlib.Path.mkdir", side_effect=AssertionError("mkdir")):
                result = check_scaffold(project_root=project, environ={})
            self.assertEqual(before, sorted(str(path) for path in Path(directory).rglob("*")))
            self.assertFalse(result["production_ready"])
            self.assertEqual(result["model_calls"], 0)
            self.assertEqual(result["capabilities"]["langsmith_tracing"], "opt_in_metadata_only_export_implemented_live_credentials_pending")
            self.assertEqual(result["capabilities"]["langgraph_execution"],
                             "local_persistent_system_not_unrestricted_production")

    def test_cli_outputs_json_and_success_means_scaffold_only(self):
        output = io.StringIO()
        with patch.dict("os.environ", {}, clear=True), redirect_stdout(output):
            self.assertEqual(main(["check", "--project-root", str(PROJECT)]), 0)
        value = json.loads(output.getvalue())
        self.assertTrue(output.getvalue().isascii())
        self.assertEqual(value["configuration"]["project_root"], str(PROJECT))
        self.assertEqual(value["status"], "scaffold_verified")
        self.assertFalse(value["production_ready"])

    def test_cli_failure_is_nonzero_and_does_not_echo_credentials(self):
        output = io.StringIO()
        with patch.dict("os.environ", {"LLM_API_KEY": "secret-sentinel", "CARDMIG_SYSTEM_PORT": "bad"}), \
                redirect_stderr(output):
            self.assertEqual(main(["check", "--project-root", str(PROJECT)]), 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "blocked")
        self.assertNotIn("secret-sentinel", output.getvalue())

    def test_packaging_metadata_and_pin_resource_declared(self):
        metadata = tomllib.loads((PROJECT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(metadata["project"]["name"], "card-migration-system")
        self.assertTrue(any(value.startswith("langgraph>=") for value in metadata["project"]["dependencies"]))
        self.assertIn("p1_contracts_pin.json", metadata["tool"]["setuptools"]["package-data"]
                      ["card_migration_system.adapters"])

    def test_old_source_fingerprints_unchanged_after_checks(self):
        paths = [REPOSITORY / "migration_pipeline/contracts" / name
                 for name in ("__init__.py", "v1.py", "legacy.py")]
        before = [sha256(path.read_bytes()).hexdigest() for path in paths]
        check_scaffold(project_root=PROJECT, environ={})
        self.assertEqual(before, [sha256(path.read_bytes()).hexdigest() for path in paths])


if __name__ == "__main__":
    unittest.main()
