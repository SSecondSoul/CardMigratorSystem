"""Operational safety tests using disposable databases/files, never model calls."""
from contextlib import closing
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from threading import Event, Thread
import time
import unittest
from unittest.mock import patch

import test_vertical_slice as fixtures
from card_migration_system.application.service import Service, ServiceError, digest
from card_migration_system.application.storage import Storage, StorageError
from card_migration_system.persistence.backup import create_backup, verify_backup, restore_backup, backup_directory, copy_database
from card_migration_system.persistence.database import initialize, transaction, HEAD
from card_migration_system.persistence.runtime_lock import execution_guard, RuntimeBusyError
from card_migration_system.persistence.schema_v1 import Run, WorkerLock
from card_migration_system.persistence.worker_health import WorkerHealth
from card_migration_system.workers.heartbeat import WorkerHeartbeat
from card_migration_system.workers.runner import run_worker, work_once

PROJECT, BASE = fixtures.PROJECT, fixtures.BASE

class OperationsTests(unittest.TestCase):
    setUp = fixtures.VerticalSliceTests.setUp
    enqueue = fixtures.VerticalSliceTests.enqueue
    app = fixtures.VerticalSliceTests.app

    def restored_settings(self, name="restored"):
        return replace(self.settings, runtime_dir=self.project / "var" / name,
                       artifact_dir=self.settings.artifact_dir / name)

    def start_blocking_worker(self):
        entered, release = Event(), Event()
        original = self.service.evaluate_fixture

        def blocking(*args, **kwargs):
            entered.set()
            if not release.wait(10):
                raise AssertionError("Test failed to release controlled blocking stage")
            return original(*args, **kwargs)

        self.service.evaluate_fixture = blocking
        results = []
        thread = Thread(target=lambda: results.append(run_worker(self.service, once=True, interval=0.05)))
        thread.start()
        self.addCleanup(lambda: thread.join(timeout=15))
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(10))
        return release, thread, results

    def test_schema_upgrade_0001_preserves_existing_rows(self):
        run_id, _ = self.enqueue()
        work_once(self.service)
        before = self.service.report(run_id)
        self.service.close()
        # Construct the prior schema in this disposable DB only.
        with closing(sqlite3.connect(self.settings.business_database)) as connection:
            # 0007 is intentionally strict about unexpected pre-existing tables.
            # Remove future empty fixture tables before rewinding the version marker.
            for table in ('migration_feedback', 'migration_model_calls', 'migration_files', 'migration_jobs'):
                connection.execute('DROP TABLE ' + table)
            connection.execute("DROP TABLE worker_health")
            connection.execute("UPDATE alembic_version SET version_num='0001_development_slice'")
            connection.commit()
        with self.assertRaisesRegex(ValueError, "schema_mismatch"):
            Service(self.settings)
        initialize(self.settings)
        self.service = Service(self.settings)
        self.assertEqual(self.service.report(run_id), before)
        with closing(sqlite3.connect(self.settings.business_database)) as connection:
            self.assertEqual(connection.execute("SELECT version_num FROM alembic_version").fetchone()[0], HEAD)

    def test_live_and_development_ready_do_not_claim_production(self):
        client = self.app().test_client()
        self.assertEqual(client.get("/health/live", base_url=BASE).status_code, 200)
        self.assertEqual(client.get("/health/ready", base_url=BASE).status_code, 503)
        with WorkerHeartbeat(self.service, interval=0.05):
            response = client.get("/health/ready", base_url=BASE)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["status"], "development_ready")
            self.assertFalse(response.json["production_ready"])
        self.assertEqual(client.get("/health/ready", base_url=BASE).status_code, 503)

    def test_stale_or_incompatible_heartbeat_is_not_ready(self):
        self.service.heartbeat("test-owner", "idle", None, "a" * 64)
        self.assertEqual(self.service.readiness()[1], 503)
        with self.assertRaisesRegex(ServiceError, "binding_conflict"):
            self.service.heartbeat("test-owner", "idle", None, digest(self.service.implementation_binding()))
        self.service.heartbeat("test-compatible", "idle", None, digest(self.service.implementation_binding()))
        self.assertEqual(self.service.readiness()[1], 200)
        with transaction(self.service.engine) as session:
            session.get(WorkerHealth, "test-compatible").last_seen = time.time() - 100
        self.assertEqual(self.service.readiness()[1], 503)

    def test_database_unavailable_readiness_is_redacted(self):
        with patch.object(self.service.engine, "connect", side_effect=RuntimeError("secret-sentinel")):
            result, status = self.service.readiness()
        self.assertEqual(status, 503)
        self.assertNotIn("secret-sentinel", json.dumps(result))

    def test_corrupt_graph_is_not_development_ready(self):
        self.settings.graph_database.write_bytes(b"not a sqlite database")
        with WorkerHeartbeat(self.service, interval=0.05):
            self.assertEqual(self.service.readiness()[1], 503)

    def test_idle_loop_heartbeats_and_stops_cleanly(self):
        stop = Event()
        thread = Thread(target=lambda: run_worker(self.service, stop_event=stop, interval=0.05, poll_interval=0.02))
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while self.service.readiness()[1] != 200 and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertEqual(self.service.readiness()[1], 200)
        finally:
            stop.set()
            thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.service.readiness()[1], 503)

    def test_blocking_stage_keeps_lease_alive_independently(self):
        self.service.LEASE_SECONDS = 0.6
        run_id, _ = self.enqueue()
        release, thread, results = self.start_blocking_worker()
        time.sleep(1.0)  # Longer than the test lease, no node operation in this interval.
        with transaction(self.service.engine) as session:
            lock = session.get(WorkerLock, "singleton")
            self.assertGreater(lock.expires_at, time.time())
        self.assertIsNone(self.service.claim("another-worker"))
        self.assertEqual(self.service.readiness()[1], 200)
        release.set()
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0]["status"], "finished")
        self.assertEqual(self.service.run(run_id)["outcome"], "not_run")

    def test_heartbeat_failure_fences_next_stage_commit(self):
        run_id, _ = self.enqueue()
        release, thread, results = self.start_blocking_worker()
        with patch.object(self.service, "heartbeat", side_effect=RuntimeError("forced heartbeat failure")):
            deadline = time.monotonic() + 5
            while not any(flag.is_set() for flag in self.service.worker_failures.values()) and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(any(flag.is_set() for flag in self.service.worker_failures.values()))
            release.set()
            thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0]["status"], "execution_error")
        self.assertEqual(self.service.run(run_id)["stop_reason"], "worker_heartbeat_failed")
        self.assertIsNone(self.service.run(run_id)["final_revision_id"])

    def test_cancel_during_blocking_stage_preserves_completed_receipt(self):
        run_id, _ = self.enqueue()
        release, thread, results = self.start_blocking_worker()
        self.service.cancel(run_id)
        release.set()
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0]["status"], "cancelled")
        report = self.service.report(run_id)
        self.assertEqual(len(report["attempts"]), 1)
        self.assertEqual(report["attempts"][0]["status"], "completed")
        self.assertIsNone(report["final_revision_id"])

    def test_cancel_in_flight_generation_records_returned_response_then_stops(self):
        run_id, _ = self.enqueue()
        entered, release = Event(), Event()
        original = self.service.storage.put

        def blocking(relative, content):
            if relative.endswith(".san"):
                entered.set()
                if not release.wait(10):
                    raise AssertionError("Test failed to release fixture output")
            return original(relative, content)

        results = []
        with patch.object(self.service.storage, "put", blocking):
            thread = Thread(target=lambda: results.append(run_worker(self.service, once=True, interval=0.05)))
            thread.start()
            try:
                self.assertTrue(entered.wait(10))
                self.service.cancel(run_id)
            finally:
                release.set()
                thread.join(timeout=15)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0]["status"], "cancelled")
        report = self.service.report(run_id)
        self.assertEqual(report["attempts"][0]["status"], "completed")
        self.assertEqual(len(report["revisions"]), 1)
        self.assertIsNone(report["final_revision_id"])

    def test_expired_lease_cannot_be_resurrected_by_heartbeat(self):
        run_id, _ = self.enqueue()
        self.service.claim("owner")
        with transaction(self.service.engine) as session:
            session.get(WorkerLock, "singleton").expires_at = time.time() - 1
        with self.assertRaisesRegex(ServiceError, "lease_lost"):
            self.service.heartbeat("owner", "running", run_id, "a" * 64)

    def test_os_guard_blocks_another_worker_process_and_migration(self):
        run_id, _ = self.enqueue()
        with execution_guard(self.settings.runtime_dir):
            child = subprocess.run([sys.executable, str(PROJECT / "scripts/run_system.py"), "worker", "--once",
                                    "--project-root", str(self.project)], capture_output=True, timeout=30)
            self.assertEqual(child.returncode, 0, child.stderr.decode(errors="replace"))
            self.assertEqual(json.loads(child.stdout)["status"], "busy")
            with self.assertRaises(RuntimeBusyError):
                initialize(self.settings)
        self.assertEqual(self.service.run(run_id)["status"], "queued")

    def test_backup_restore_includes_rejected_versions_and_checkpoints(self):
        run_id, _ = self.enqueue("regression")
        work_once(self.service)
        before = self.service.report(run_id)
        content = self.service.download(run_id)
        created = create_backup(self.settings, backup_id="regression")
        self.assertGreaterEqual(created["files"], 5)
        self.assertEqual(verify_backup(self.settings, "regression")["status"], "backup_verified")
        destination = self.restored_settings()
        restore_backup(destination, "regression")
        restored = Service(destination)
        self.addCleanup(restored.close)
        self.assertEqual(restored.report(run_id), before)
        self.assertEqual(restored.download(run_id), content)
        self.assertTrue(destination.graph_database.is_file())
        self.assertEqual(restored.readiness()[1], 503)
        self.assertEqual(before["candidate_decisions"][0]["action"], "reject")
        self.assertEqual(self.service.report(run_id), before)

    def test_sqlite_backup_includes_committed_wal_not_just_main_file(self):
        source, target = self.project / "var/wal-source.sqlite3", self.project / "var/wal-copy.sqlite3"
        with closing(sqlite3.connect(source)) as connection:
            self.assertEqual(connection.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
            connection.execute("PRAGMA wal_autocheckpoint=0")
            connection.execute("CREATE TABLE fixture (value TEXT)")
            connection.execute("INSERT INTO fixture VALUES ('committed in WAL')")
            connection.commit()
            self.assertTrue(Path(str(source) + "-wal").exists())
            copy_database(source, target)
            with closing(sqlite3.connect(target)) as restored:
                self.assertEqual(restored.execute("SELECT value FROM fixture").fetchall(), [("committed in WAL",)])

    def test_backup_without_graph_and_queued_run_still_processes_after_restore(self):
        run_id, _ = self.enqueue()
        create_backup(self.settings, backup_id="queued")
        destination = self.restored_settings()
        restore_backup(destination, "queued")
        restored = Service(destination)
        self.addCleanup(restored.close)
        self.assertFalse(destination.graph_database.exists())
        self.assertEqual(work_once(restored)["status"], "finished")
        self.assertEqual(restored.run(run_id)["outcome"], "not_run")
        self.assertEqual(self.service.run(run_id)["status"], "queued")

    def test_backup_preserves_review_checkpoint_and_resume_receipts(self):
        run_id, _ = self.enqueue("repairable")
        work_once(self.service, interrupt_after=["generate"])
        create_backup(self.settings, backup_id="review")
        destination = self.restored_settings()
        restore_backup(destination, "review")
        restored = Service(destination)
        self.addCleanup(restored.close)
        restored.resume(run_id)
        self.assertEqual(work_once(restored)["status"], "finished")
        self.assertEqual(len(restored.report(run_id)["attempts"]), 2)
        self.assertEqual(self.service.run(run_id)["status"], "review_required")

    def test_backup_requires_worker_shutdown_and_no_unresolved_lease(self):
        with WorkerHeartbeat(self.service, interval=0.05):
            with self.assertRaisesRegex(ServiceError, "stop_workers"):
                create_backup(self.settings, backup_id="active")
        run_id, _ = self.enqueue()
        self.service.claim("dead-owner")
        with self.assertRaisesRegex(ServiceError, "resolved_worker_leases"):
            create_backup(self.settings, backup_id="lease")
        self.assertEqual(self.service.run(run_id)["status"], "running")

    def test_backup_refuses_executing_graph_even_if_business_lease_disappears(self):
        with execution_guard(self.settings.runtime_dir), self.assertRaises(RuntimeBusyError):
            create_backup(self.settings, backup_id="busy")

    def test_existing_backup_and_destinations_never_overwritten(self):
        self.enqueue()
        create_backup(self.settings, backup_id="one")
        manifest = (backup_directory(self.settings, "one") / "manifest.json").read_bytes()
        with self.assertRaisesRegex(ServiceError, "already_exists"):
            create_backup(self.settings, backup_id="one")
        with self.assertRaises(ServiceError):
            restore_backup(self.settings, "one")
        destination = self.restored_settings()
        destination.runtime_dir.mkdir()
        sentinel = destination.runtime_dir / "sentinel"
        sentinel.write_bytes(b"do not overwrite")
        with self.assertRaisesRegex(ServiceError, "destination_exists"):
            restore_backup(destination, "one")
        self.assertEqual(sentinel.read_bytes(), b"do not overwrite")
        self.assertEqual((backup_directory(self.settings, "one") / "manifest.json").read_bytes(), manifest)

    def test_corrupt_backup_blocks_before_any_restore_destination(self):
        self.enqueue()
        create_backup(self.settings, backup_id="corrupt")
        (backup_directory(self.settings, "corrupt") / "db/business.sqlite3").write_bytes(b"damaged")
        destination = self.restored_settings()
        with self.assertRaises((ServiceError, StorageError)):
            restore_backup(destination, "corrupt")
        self.assertFalse(destination.runtime_dir.exists())
        self.assertFalse(destination.artifact_dir.exists())

    def test_missing_or_corrupt_registered_file_prevents_completed_backup(self):
        run_id, _ = self.enqueue()
        work_once(self.service)
        artifact = self.settings.artifact_dir / f"runs/{run_id}/{run_id}_0.san"
        artifact.write_bytes(b"damaged")
        with self.assertRaises(StorageError):
            create_backup(self.settings, backup_id="missing")
        folder = backup_directory(self.settings, "missing")
        self.assertTrue((folder / ".incomplete").exists())
        with self.assertRaisesRegex(ServiceError, "incomplete"):
            verify_backup(self.settings, "missing")

    def test_backup_path_traversal_and_binding_drift_blocked(self):
        for name in ("../outside", "bad/name", "C:/outside", ""):
            with self.subTest(name=name), self.assertRaises(ServiceError):
                backup_directory(self.settings, name)
        with self.assertRaisesRegex(ServiceError, "manifest_unavailable"):
            verify_backup(self.settings, "does-not-exist")
        self.enqueue()
        create_backup(self.settings, backup_id="drift")
        with patch("card_migration_system.persistence.backup.implementation_binding", return_value={}):
            with self.assertRaisesRegex(ServiceError, "drift"):
                restore_backup(self.restored_settings(), "drift")

    def test_manifest_traversal_and_omitted_artifact_are_rejected(self):
        self.enqueue()
        create_backup(self.settings, backup_id="manifest")
        path = backup_directory(self.settings, "manifest") / "manifest.json"
        manifest = json.loads(path.read_bytes())
        original = json.loads(path.read_bytes())
        manifest["files"]["artifacts/../../../outside"] = {"size": 0, "sha256": sha256(b"").hexdigest()}
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises((ServiceError, StorageError)):
            verify_backup(self.settings, "manifest")
        key = next(key for key in original["files"] if key.startswith("artifacts/"))
        del original["files"][key]
        path.write_text(json.dumps(original), encoding="utf-8")
        with self.assertRaisesRegex(ServiceError, "registered_files"):
            verify_backup(self.settings, "manifest")

    def test_interrupted_restore_marker_blocks_startup_and_initialization(self):
        self.enqueue()
        create_backup(self.settings, backup_id="interrupt")
        destination = self.restored_settings()
        original = Storage.put

        def fail_install(storage, relative, content):
            if storage.root == destination.runtime_dir:
                raise OSError("simulated installation interruption")
            return original(storage, relative, content)

        with patch.object(Storage, "put", fail_install), self.assertRaises(OSError):
            restore_backup(destination, "interrupt")
        self.assertTrue((destination.runtime_dir / ".restore-in-progress").exists())
        with self.assertRaisesRegex(ServiceError, "restore_incomplete"):
            Service(destination)
        with self.assertRaisesRegex(ValueError, "restore_incomplete"):
            initialize(destination)
        with self.assertRaisesRegex(ServiceError, "destination_exists"):
            restore_backup(destination, "interrupt")

    def test_real_cli_backup_verify_restore_and_existing_target_block(self):
        self.enqueue()
        shutil.copyfile(PROJECT / "configs/restore-example.toml", self.project / "configs/restore-example.toml")

        def command(*args):
            return subprocess.run([sys.executable, str(PROJECT / "scripts/run_system.py"), *args,
                                   "--project-root", str(self.project)], capture_output=True, timeout=30)

        created = command("backup", "--backup-id", "cli")
        self.assertEqual(created.returncode, 0, created.stderr.decode(errors="replace"))
        self.assertEqual(json.loads(created.stdout)["status"], "backup_created")
        verified = command("verify-backup", "--backup-id", "cli")
        self.assertEqual(verified.returncode, 0, verified.stderr.decode(errors="replace"))
        restored = command("restore", "--backup-id", "cli", "--config", "configs/restore-example.toml")
        self.assertEqual(restored.returncode, 0, restored.stderr.decode(errors="replace"))
        self.assertEqual(json.loads(restored.stdout)["status"], "backup_restored")
        again = command("restore", "--backup-id", "cli", "--config", "configs/restore-example.toml")
        self.assertEqual(again.returncode, 2)
        self.assertIn("restore_destination_exists", json.loads(again.stderr)["error"])


if __name__ == "__main__":
    unittest.main()
