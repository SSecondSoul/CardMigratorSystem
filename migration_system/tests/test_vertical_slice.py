"""Real SQLite/Alembic/HTTP/LangGraph tests; fake model, no migration-quality claims."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import time
import unittest
from unittest.mock import patch
from urllib import request as http

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from test_scaffold import copy_fixture
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from werkzeug.serving import make_server, WSGIRequestHandler

from card_migration_system.config import load_settings
from card_migration_system.application.service import Service, ServiceError
from card_migration_system.application.storage import StorageError
from card_migration_system.interfaces.api.app import create_app
from card_migration_system.persistence.database import initialize, transaction
from card_migration_system.persistence.schema_v1 import Attempt, Evaluation, Run, WorkerLock
from card_migration_system.workers.runner import work_once

TOKEN = "test-only-token-not-for-deployment"
BASE = "http://127.0.0.1:8790"


class VerticalSliceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = copy_fixture(Path(self.temp.name))
        shutil.copyfile(PROJECT / "requirements.lock", self.project / "requirements.lock")
        shutil.copytree(PROJECT / "migrations", self.project / "migrations", ignore=shutil.ignore_patterns("__pycache__"))
        self.settings = load_settings(project_root=self.project, environ={})
        initialize(self.settings)
        self.service = Service(self.settings)
        self.addCleanup(lambda: self.service.close())

    def enqueue(self, profile="success", rounds=3, key="first"):
        source = self.service.create_input({"filename": "Example.vue", "source": "<template><div>Input</div></template>"})
        task = self.service.create_task({"input_id": source["input_id"]})
        row = self.service.enqueue(task["task_id"], {"profile": profile, "max_repair_rounds": rounds}, key)
        return row["run_id"], task["task_id"]

    def app(self):
        app = create_app(self.settings, write_token=TOKEN)
        self.addCleanup(app.extensions["migration_service"].close)
        return app

    def test_real_alembic_migration_idempotent_and_separate_graph_db(self):
        initialize(self.settings)
        self.assertIn("attempts", inspect(self.service.engine).get_table_names())
        self.assertIn("artifact_revisions", inspect(self.service.engine).get_table_names())
        self.assertFalse(self.settings.graph_database.exists())
        run_id, _ = self.enqueue()
        self.assertEqual(work_once(self.service)["status"], "finished")
        with closing(sqlite3.connect(self.settings.graph_database)) as connection:
            self.assertIn("checkpoints", [row[0] for row in connection.execute("SELECT name FROM sqlite_master")])
        self.assertEqual(self.service.run(run_id)["outcome"], "not_run")

    def test_success_fixture_never_becomes_migration_pass(self):
        run_id, _ = self.enqueue()
        work_once(self.service)
        report = self.service.report(run_id)
        self.assertEqual(report["status"], "finished")
        self.assertEqual(report["outcome"], "not_run")
        self.assertEqual(report["actual_model_calls"], 0)
        self.assertFalse(report["production_ready"])
        self.assertEqual(report["evaluations"][0]["status"], "not_run")
        self.assertIn(b"DEVELOPMENT STUB", self.service.download(run_id))

    def test_repairable_fixture_uses_conditional_repair_edge(self):
        run_id, _ = self.enqueue("repairable")
        work_once(self.service)
        report = self.service.report(run_id)
        self.assertEqual(len(report["attempts"]), 2)
        self.assertEqual(report["candidate_decisions"][0]["action"], "accept")
        self.assertTrue(report["final_revision_id"].endswith("_1"))

    def test_regression_rejected_keeps_both_artifacts_and_previous_final(self):
        run_id, _ = self.enqueue("regression")
        work_once(self.service)
        report = self.service.report(run_id)
        self.assertEqual(report["candidate_decisions"][0]["action"], "reject")
        self.assertEqual(len(report["revisions"]), 2)
        self.assertTrue(report["final_revision_id"].endswith("_0"))
        self.assertIn(b"round 0", self.service.download(run_id))
        self.assertEqual(report["stop_reason"], "fixture_candidate_regression_rolled_back")

    def test_zero_and_three_round_budgets_stop(self):
        for rounds in (0, 3):
            run_id, _ = self.enqueue("always_fail", rounds)
            work_once(self.service)
            report = self.service.report(run_id)
            self.assertEqual(len(report["attempts"]), 1+rounds)
            self.assertEqual(report["stop_reason"], "fixture_repair_budget_exhausted")

    def test_idempotency_conflicts_and_repeated_polls_do_not_regenerate(self):
        run_id, task_id = self.enqueue()
        self.assertEqual(self.service.enqueue(task_id, {"profile": "success", "max_repair_rounds": 3}, "first")["run_id"], run_id)
        with self.assertRaises(ServiceError):
            self.service.enqueue(task_id, {"profile": "repairable"}, "first")
        work_once(self.service)
        before = self.service.report(run_id)
        for _ in range(3):
            self.service.events(run_id)
            self.service.run(run_id)
        self.assertEqual(before, self.service.report(run_id))
        self.assertEqual(work_once(self.service)["status"], "idle")

    def test_concurrent_enqueue_serializes_unique_idempotency(self):
        _, task_id = self.enqueue()
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(lambda _: self.service.enqueue(task_id, {}, "concurrent"), range(2)))
        self.assertEqual(values[0]["run_id"], values[1]["run_id"])

    def test_checkpoint_resume_from_new_service_does_not_repeat_generation(self):
        run_id, _ = self.enqueue("repairable")
        self.assertEqual(work_once(self.service, interrupt_after=["generate"])["status"], "review_required")
        self.assertEqual(len(self.service.report(run_id)["attempts"]), 1)
        self.service.close()
        self.service = Service(self.settings)
        self.service.resume(run_id)
        work_once(self.service)
        self.assertEqual(self.service.run(run_id)["status"], "finished")
        self.assertEqual(len(self.service.report(run_id)["attempts"]), 2)

    def test_completed_receipt_reused_even_if_checkpoint_missing(self):
        run_id, _ = self.enqueue()
        work_once(self.service, interrupt_after=["generate"])
        # Only this test's temporary checkpoint DB, never a repository artifact.
        self.settings.graph_database.unlink()
        self.service.resume(run_id)
        work_once(self.service)
        self.assertEqual(len(self.service.report(run_id)["attempts"]), 1)
        self.assertEqual(self.service.run(run_id)["status"], "finished")

    def test_abrupt_worker_exit_reuses_committed_receipt_after_lease_review(self):
        run_id, _ = self.enqueue()
        crashed = subprocess.run([sys.executable, str(PROJECT / "tests/worker_crash_probe.py"), str(self.project)],
                                 capture_output=True, timeout=60)
        self.assertEqual(crashed.returncode, 37, crashed.stderr.decode(errors="replace"))
        self.assertEqual(self.service.run(run_id)["status"], "running")
        self.assertEqual(len(self.service.report(run_id)["attempts"]), 1)
        with transaction(self.service.engine) as session:
            session.get(WorkerLock, "singleton").expires_at = time.time()-1
        self.assertIsNone(self.service.claim("lease-auditor"))
        self.assertEqual(self.service.run(run_id)["status"], "review_required")
        self.service.resume(run_id)
        completed = subprocess.run([sys.executable, str(PROJECT / "scripts/run_system.py"), "worker", "--once",
                                     "--project-root", str(self.project)], capture_output=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))
        self.assertEqual(self.service.run(run_id)["status"], "finished")
        self.assertEqual(len(self.service.report(run_id)["attempts"]), 1)

    def test_ambiguous_attempt_not_automatically_retried(self):
        run_id, _ = self.enqueue()
        with transaction(self.service.engine) as session:
            row = session.get(Run, run_id)
            row.status = "review_required"
            session.add(Attempt(id=f"{run_id}:stub:0", run_id=run_id, kind="development_stub",
                                status="started", request_sha256="a"*64, started_at=time.time(), result=None))
        with self.assertRaisesRegex(ServiceError, "ambiguous_attempt"):
            self.service.resume(run_id)
        self.assertEqual(work_once(self.service)["status"], "idle")

    def test_version_drift_refuses_resume(self):
        run_id, _ = self.enqueue()
        work_once(self.service, interrupt_after=["generate"])
        with patch.object(self.service, "implementation_binding", return_value={"drift": True}):
            with self.assertRaisesRegex(ServiceError, "drift"):
                self.service.resume(run_id)
        self.assertEqual(self.service.run(run_id)["status"], "review_required")

    def test_cancel_before_execution_is_idempotent(self):
        run_id, _ = self.enqueue()
        self.service.cancel(run_id)
        before = self.service.events(run_id)
        self.service.cancel(run_id)
        self.assertEqual(self.service.events(run_id), before)
        self.assertEqual(work_once(self.service)["status"], "idle")
        self.assertEqual(self.service.run(run_id)["status"], "cancelled")

    def test_single_worker_lease_and_expiry_require_review(self):
        first, _ = self.enqueue()
        second, _ = self.enqueue()
        self.assertEqual(self.service.claim("owner-a"), first)
        self.assertIsNone(self.service.claim("owner-b"))
        with transaction(self.service.engine) as session:
            session.get(WorkerLock, "singleton").expires_at = time.time()-1
        self.assertEqual(self.service.claim("owner-b"), second)
        self.assertEqual(self.service.run(first)["status"], "review_required")
        self.service.release(first, "owner-a", status="finished")
        self.assertEqual(self.service.run(first)["status"], "review_required")
        self.service.release(second, "owner-b", status="review_required", reason="test")

    def test_corrupt_final_artifact_blocks_download_without_overwrite(self):
        run_id, _ = self.enqueue()
        work_once(self.service)
        target = self.settings.artifact_dir / f"runs/{run_id}/{run_id}_0.san"
        target.write_bytes(b"corrupt")
        with self.assertRaises(StorageError):
            self.service.download(run_id)
        self.assertEqual(target.read_bytes(), b"corrupt")

    def test_foreign_keys_reject_cross_run_evaluation(self):
        one, _ = self.enqueue()
        work_once(self.service)
        two, _ = self.enqueue()
        with self.assertRaises(IntegrityError):
            with transaction(self.service.engine) as session:
                session.add(Evaluation(id="bad", run_id=two, revision_id=f"{one}_0", status="not_run",
                                       scope="test", fixture_assertions={}))

    def test_storage_rejects_overwrite_and_traversal(self):
        self.service.storage.put("tests/one", b"first")
        with self.assertRaises(StorageError):
            self.service.storage.put("tests/one", b"replacement")
        for path in ("../outside", str(self.settings.artifact_dir / "tests/one"), "tests/../one"):
            with self.subTest(path=path), self.assertRaises(StorageError):
                self.service.storage.read(path, "a"*64)

    def test_unknown_database_not_overwritten(self):
        self.service.close()
        with closing(sqlite3.connect(self.settings.business_database)) as connection:
            connection.execute("DROP TABLE alembic_version")  # Only a disposable test DB.
        with self.assertRaisesRegex(ValueError, "refuse_unknown"):
            initialize(self.settings)

    def test_api_write_host_origin_and_token_guards(self):
        client = self.app().test_client()
        self.assertEqual(client.get("/health/live", base_url="http://evil.example:8790").status_code, 403)
        self.assertEqual(client.post("/api/v1/inputs", base_url=BASE, json={}).status_code, 403)
        self.assertEqual(client.post("/api/v1/inputs", base_url=BASE, json={},
                                    headers={"X-Cardmig-Token": TOKEN, "Origin": "https://evil.example"}).status_code, 403)
        self.assertEqual(client.get("/health/ready", base_url=BASE).status_code, 503)

    def test_api_invalid_fields_paths_and_error_redaction(self):
        client = self.app().test_client()
        for payload in ({"filename": "../Example.vue", "source": "x"},
                        {"filename": "Example.vue", "source": "x", "api_key": "secret-sentinel"}):
            response = client.post("/api/v1/inputs", base_url=BASE, json=payload,
                                   headers={"X-Cardmig-Token": TOKEN})
            self.assertEqual(response.status_code, 400)
            self.assertNotIn("secret-sentinel", response.get_data(as_text=True))

    def test_ambient_langsmith_environment_cannot_upload(self):
        run_id, _ = self.enqueue()
        with patch.dict("os.environ", {"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "not-a-real-key"}), \
                patch("socket.socket.connect", side_effect=AssertionError("network disallowed")):
            result = work_once(self.service)
        self.assertEqual(result["status"], "finished")
        self.assertFalse(self.service.report(run_id)["langsmith_uploaded"])

    def test_real_http_and_separate_worker_process(self):
        class QuietHandler(WSGIRequestHandler):
            def log_request(self, *args, **kwargs):
                pass

        app = self.app()
        server = make_server("127.0.0.1", 0, app, request_handler=QuietHandler)
        app.config["ALLOWED_PORT"] = server.server_port
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"

        def call(path, payload=None, key=None):
            headers = {"Content-Type": "application/json", "X-Cardmig-Token": TOKEN}
            if key:
                headers["Idempotency-Key"] = key
            with http.urlopen(http.Request(base+path, headers=headers,
                              data=None if payload is None else json.dumps(payload).encode()), timeout=10) as response:
                return json.load(response)
        try:
            source = call("/api/v1/inputs", {"filename": "Smoke.vue", "source": "<template><div>source</div></template>"})
            task = call("/api/v1/tasks", {"input_id": source["input_id"]})
            run = call(f"/api/v1/tasks/{task['task_id']}/runs", {"profile": "repairable"}, "network-smoke")
            completed = subprocess.run([sys.executable, str(PROJECT / "scripts/run_system.py"), "worker", "--once",
                                         "--project-root", str(self.project)], capture_output=True, timeout=60)
            self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))
            result = call(f"/api/v1/runs/{run['run_id']}/report")
            self.assertEqual(result["status"], "finished", result)
            self.assertEqual(result["outcome"], "not_run")
            self.assertEqual(len(result["attempts"]), 2)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
