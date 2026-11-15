"""Ensure the diagnostic changes both timeout layers in fresh child processes."""

import os
import subprocess
import sys
import unittest

from migration_pipeline.prepare_formal_30_v4_timeout_diagnostic import build_config
from migration_pipeline.run_formal_30_v4_timeout_diagnostic import ROOT, child_environment, batch_command


class TimeoutDiagnosticTests(unittest.TestCase):
    def test_child_environment_overrides_both_layers_without_mutating_parent(self):
        parent = {"LLM_TIMEOUT": "240", "MIGRATION_GENERATION_TIMEOUT": "300", "MIGRATION_REPAIR_TIMEOUT": "300", "LLM_API_KEY": "test-only"}
        child = child_environment(parent)
        self.assertEqual((child["LLM_TIMEOUT"], child["MIGRATION_GENERATION_TIMEOUT"], child["MIGRATION_REPAIR_TIMEOUT"]), ("600", "660", "660"))
        self.assertEqual(child["LLM_API_KEY"], "test-only")
        self.assertEqual(parent["LLM_TIMEOUT"], "240")

    def test_new_process_imports_the_explicit_timeout_settings(self):
        command = [sys.executable, "-c", "from local_server.config import settings as s; from migration_pipeline.config import settings as p; print(s.llm_timeout,p.generation_timeout,p.repair_timeout)"]
        result = subprocess.run(command, cwd=ROOT, env=child_environment(dict(os.environ)), capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "600 660 660")

    def test_plan_reuses_only_the_two_sources_and_three_round_cap(self):
        config = build_config()
        self.assertEqual([s["id"] for s in config["samples"]], ["TaskManager", "MonitoringDashboard"])
        self.assertEqual(config["max_repair_rounds"], 3)
        self.assertFalse(config["independent_holdout"])
        self.assertIn("timeout_diagnostic", config["batch_id"])

    def test_batch_command_uses_separate_checkpoint_without_force(self):
        command = batch_command(dry_run=True)
        self.assertIn("--dry-run", command)
        self.assertIn("--include-state", command)
        self.assertNotIn("--force", command)
        self.assertIn("migration_pipeline/batch_configs/formal_30_v4_timeout_diagnostic_v1.json", command)


if __name__ == "__main__":
    unittest.main()
