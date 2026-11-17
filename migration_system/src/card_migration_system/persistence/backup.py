"""Verified local backups; restore only to absent destinations, never overwrite history."""
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from tempfile import TemporaryDirectory
import time
from uuid import uuid4

from sqlalchemy import select

from ..application.service import implementation_binding, Service, ServiceError
from ..application.storage import Storage
from .database import HEAD, transaction
from .runtime_lock import execution_guard
from .schema_v1 import Run, WorkerLock
from .worker_health import WorkerHealth


MAX_BYTES = 256 * 1024 * 1024
MAX_FILES = 10000


def backup_directory(settings, backup_id):
    if type(backup_id) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", backup_id):
        raise ServiceError("invalid_backup_id", 400)
    root = (settings.project_root / "var/backups").resolve()
    if not root.is_relative_to((settings.project_root / "var").resolve()):
        raise ServiceError("backup_root_escapes_project")
    target = root / backup_id
    if target.is_symlink():
        raise ServiceError("backup_symlink_not_allowed")
    return target


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)


def copy_database(source, destination):
    # SQLite backup includes committed WAL pages; do not copy only the .sqlite3 file.
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(readonly(source)) as origin, closing(sqlite3.connect(destination)) as target:
        origin.backup(target)


def inspect_business(path):
    with closing(readonly(path)) as connection:
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ServiceError("backup_database_integrity_failed")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ServiceError("backup_database_foreign_keys_failed")
        if connection.execute("SELECT version_num FROM alembic_version").fetchall() != [(HEAD,)]:
            raise ServiceError("backup_schema_mismatch")
        if connection.execute("SELECT count(*) FROM worker_locks").fetchone()[0]:
            raise ServiceError("backup_requires_resolved_worker_leases")
        if connection.execute("SELECT count(*) FROM runs WHERE status='running'").fetchone()[0]:
            raise ServiceError("backup_requires_quiescent_runs")
        references = {}
        if connection.execute("SELECT count(*) FROM ssm_extractions WHERE status='started'").fetchone()[0]:
            raise ServiceError('backup_requires_resolved_ssm_attempts')
        if (connection.execute("SELECT count(*) FROM generation_jobs WHERE status='started'").fetchone()[0]
                or connection.execute("SELECT count(*) FROM generation_attempts WHERE status='started'").fetchone()[0]):
            raise ServiceError('backup_requires_resolved_generation_attempts')
        if (connection.execute("SELECT count(*) FROM provider_generation_jobs WHERE status='started'").fetchone()[0]
                or connection.execute("SELECT count(*) FROM provider_generation_attempts WHERE status='started'").fetchone()[0]):
            raise ServiceError('backup_requires_resolved_provider_attempts')
        if connection.execute("SELECT count(*) FROM migration_jobs WHERE status='running'").fetchone()[0]:
            raise ServiceError('backup_requires_quiescent_migrations')
        if connection.execute("SELECT count(*) FROM migration_model_calls WHERE status='started'").fetchone()[0]:
            raise ServiceError('backup_requires_resolved_migration_calls')
        for table in ("source_inputs", "artifact_revisions", "ssm_extraction_files", "generation_files", "provider_generation_files", "generation_approval_files", "migration_files"):
            for relative, fingerprint in connection.execute(f"SELECT relative_path, sha256 FROM {table}"):
                if relative in references and references[relative] != fingerprint:
                    raise ServiceError("backup_artifact_identity_conflict")
                references[relative] = fingerprint
        return references


def audit_ssm_archive(settings, folder):
    """Validate extraction ownership/receipts using the copied DB AND copied files."""
    from ..application.extractions import ExtractionService
    from ..persistence.ssm_extractions import SSMExtraction
    archived = Service(replace(settings, runtime_dir=folder / 'db', artifact_dir=folder / 'artifacts'))
    try:
        with transaction(archived.engine) as session:
            keys = list(session.scalars(select(SSMExtraction.id)))
        for key in keys:
            ExtractionService(archived).report(key)
        from ..application.generations import GenerationService
        from ..persistence.generations import GenerationJob
        with transaction(archived.engine) as session:
            generation_keys = list(session.scalars(select(GenerationJob.id)))
        for key in generation_keys:
            GenerationService(archived).report(key)
        from ..application.provider_generations import ProviderGenerationService
        from ..persistence.provider_generations import ProviderGenerationJob
        with transaction(archived.engine) as session:
            provider_keys = list(session.scalars(select(ProviderGenerationJob.id)))
        for key in provider_keys:
            ProviderGenerationService(archived).report(key)
        from ..application.generation_approvals import GenerationApprovalService
        from ..persistence.generation_approvals import GenerationApproval
        with transaction(archived.engine) as session:
            approval_keys = list(session.scalars(select(GenerationApproval.id)))
        for key in approval_keys:
            GenerationApprovalService(archived).report(key)
        from ..application.migrations import MigrationService
        from .migrations import MigrationJob
        with transaction(archived.engine) as session:
            migration_keys = list(session.scalars(select(MigrationJob.id)))
        for key in migration_keys:
            MigrationService(archived).report(key)
    finally:
        archived.close()


def inspect_graph(path):
    with closing(readonly(path)) as connection:
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ServiceError("backup_graph_integrity_failed")
        if not connection.execute("SELECT name FROM sqlite_master WHERE name='checkpoints'").fetchone():
            raise ServiceError("backup_graph_schema_missing")


def create_backup(settings, *, backup_id=None):
    backup_id = backup_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:8]
    folder = backup_directory(settings, backup_id)
    service = Service(settings)
    try:
        with execution_guard(settings.runtime_dir), transaction(service.engine) as session:
            # BEGIN IMMEDIATE fences API database writes. The OS guard separately
            # fences graph/checkpoint writers, even if their lease has expired.
            if session.get(WorkerLock, "singleton") is not None:
                raise ServiceError("backup_requires_resolved_worker_leases")
            if session.scalar(select(Run.id).where(Run.status == "running").limit(1)):
                raise ServiceError("backup_requires_quiescent_runs")
            if session.scalar(select(WorkerHealth.id).where(
                WorkerHealth.state.in_(("idle", "running")),
                WorkerHealth.last_seen > time.time() - service.HEALTH_SECONDS).limit(1)):
                raise ServiceError("stop_workers_before_backup")
            folder.parent.mkdir(parents=True, exist_ok=True)
            try:
                folder.mkdir()  # Never reuse/overwrite an earlier backup, including incomplete ones.
            except FileExistsError as error:
                raise ServiceError("backup_already_exists") from error
            (folder / ".incomplete").touch(exist_ok=False)
            files = {}

            def register(relative):
                content = (folder / relative).read_bytes()
                files[relative] = {"sha256": sha256(content).hexdigest(), "size": len(content)}
                if len(files) > MAX_FILES or sum(row["size"] for row in files.values()) > MAX_BYTES:
                    raise ServiceError("development_backup_limit_exceeded")

            copy_database(settings.business_database, folder / "db/business.sqlite3")
            references = inspect_business(folder / "db/business.sqlite3")
            register("db/business.sqlite3")
            if settings.graph_database.exists():
                copy_database(settings.graph_database, folder / "db/langgraph.sqlite3")
                inspect_graph(folder / "db/langgraph.sqlite3")
                register("db/langgraph.sqlite3")
            storage = Storage(folder)
            for relative, fingerprint in references.items():
                destination = "artifacts/" + relative
                storage.put(destination, service.storage.read(relative, fingerprint))
                register(destination)
            audit_ssm_archive(settings, folder)
            manifest = {"schema_version": 1, "database_schema": HEAD, "mode": "development_stub",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "binding": service.implementation_binding(), "files": files,
                        "scope": "registered_files_and_databases_not_orphans_or_credentials"}
            storage.put("manifest.json", json.dumps(manifest, sort_keys=True, indent=2).encode())
            (folder / ".incomplete").unlink()  # Only our own completion marker.
        return {"status": "backup_created", "backup_id": backup_id, "files": len(files),
                "manifest_sha256": sha256((folder / "manifest.json").read_bytes()).hexdigest(),
                "production_ready": False}
    finally:
        service.close()


def _verified_manifest(settings, backup_id):
    folder = backup_directory(settings, backup_id)
    if (folder / ".incomplete").exists():
        raise ServiceError("backup_incomplete")
    try:
        with (folder / "manifest.json").open("rb") as stream:
            raw = stream.read(2 * 1024 * 1024 + 1)
    except OSError as error:
        raise ServiceError("backup_manifest_unavailable") from error
    if len(raw) > 2 * 1024 * 1024:
        raise ServiceError("backup_manifest_too_large")
    try:
        manifest = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise ServiceError("backup_manifest_invalid") from error
    if (type(manifest) is not dict or manifest.get("schema_version") != 1
            or manifest.get("database_schema") != HEAD or manifest.get("mode") != "development_stub"):
        raise ServiceError("backup_manifest_version_mismatch")
    if manifest.get("binding") != implementation_binding(settings):
        raise ServiceError("backup_implementation_or_dependency_drift")
    files = manifest.get("files")
    if type(files) is not dict or not 1 <= len(files) <= MAX_FILES or "db/business.sqlite3" not in files:
        raise ServiceError("backup_file_manifest_invalid")
    storage, total = Storage(folder), 0
    for relative, row in files.items():
        if (type(relative) is not str or (relative not in ("db/business.sqlite3", "db/langgraph.sqlite3")
                and not relative.startswith("artifacts/")) or type(row) is not dict
                or set(row) != {"size", "sha256"} or type(row["size"]) is not int or row["size"] < 0
                or type(row["sha256"]) is not str or not re.fullmatch("[0-9a-f]{64}", row["sha256"])):
            raise ServiceError("backup_file_manifest_invalid")
        total += row["size"]
        if total > MAX_BYTES:
            raise ServiceError("development_backup_limit_exceeded")
        path = storage.locate(relative)
        try:
            size = path.stat().st_size
        except OSError as error:
            raise ServiceError("backup_file_unavailable") from error
        if size != row["size"]:
            raise ServiceError("backup_file_size_mismatch")
        storage.read(relative, row["sha256"])
    references = inspect_business(folder / "db/business.sqlite3")
    expected = {"db/business.sqlite3"} | {"artifacts/" + key for key in references}
    if "db/langgraph.sqlite3" in files:
        inspect_graph(folder / "db/langgraph.sqlite3")
        expected.add("db/langgraph.sqlite3")
    if set(files) != expected or any(files["artifacts/" + key]["sha256"] != value for key, value in references.items()):
        raise ServiceError("backup_registered_files_mismatch")
    audit_ssm_archive(settings, folder)
    return manifest, {"status": "backup_verified", "backup_id": backup_id, "files": len(files),
                      "manifest_sha256": sha256(raw).hexdigest(), "production_ready": False}


def verify_backup(settings, backup_id):
    return _verified_manifest(settings, backup_id)[1]


def restore_backup(settings, backup_id):
    # Verify before creating any destination. Existing databases/artifacts are never replaced.
    manifest, _ = _verified_manifest(settings, backup_id)
    folder = backup_directory(settings, backup_id)
    for target, allowed in ((settings.runtime_dir, settings.project_root / "var"),
                            (settings.artifact_dir, settings.repository_root / "data/experiments/migration_system")):
        if target == allowed.resolve() or not target.is_relative_to(allowed.resolve()):
            raise ServiceError("restore_requires_fresh_child_directories")
        if target.exists() or target.is_symlink():
            raise ServiceError("restore_destination_exists")
    settings.runtime_dir.parent.mkdir(parents=True, exist_ok=True)
    # Temporary staging under the same parent/volume; no user trees are removed.
    with TemporaryDirectory(prefix=".restore-stage-", dir=settings.runtime_dir.parent) as temporary:
        staging = Storage(Path(temporary))
        origin = Storage(folder)
        for relative, row in manifest["files"].items():
            staging.put(relative, origin.read(relative, row["sha256"]))
        inspect_business(Path(temporary) / "db/business.sqlite3")
        # Presence is operational, not historical run evidence. Old workers must not look alive.
        with closing(sqlite3.connect(Path(temporary) / "db/business.sqlite3")) as connection:
            connection.execute("UPDATE worker_health SET state='stopped', run_id=NULL, last_seen=0")
            connection.commit()
        settings.runtime_dir.mkdir(exist_ok=False)
        marker = settings.runtime_dir / ".restore-in-progress"
        marker.touch(exist_ok=False)
        # On interrupted installation, retain the marker and partial new destination for
        # explicit review. Never overwrite it on retry or silently start the service.
        with execution_guard(settings.runtime_dir):
            settings.artifact_dir.mkdir(parents=True, exist_ok=False)
            artifacts = Storage(settings.artifact_dir)
            runtime = Storage(settings.runtime_dir)
            for relative, row in manifest["files"].items():
                if relative.startswith("artifacts/"):
                    artifacts.put(relative[len("artifacts/"):], staging.read(relative, row["sha256"]))
                else:
                    content = staging.locate(relative).read_bytes()
                    runtime.put(relative[len("db/"):], content)
            marker.unlink()  # Only clear after both destinations are installed.
    return {"status": "backup_restored", "backup_id": backup_id,
            "worker_restart_required": True, "production_ready": False}
