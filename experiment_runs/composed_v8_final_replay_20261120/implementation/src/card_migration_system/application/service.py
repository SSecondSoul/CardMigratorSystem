"""Persistent development run lifecycle, separate from migration verdicts."""
from hashlib import sha256
from contextlib import closing
import base64
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
from uuid import uuid4

from sqlalchemy import select, or_, and_

from ..contracts import load_p1_contracts
from ..persistence.database import engine_for_settings, require_schema, transaction
from ..persistence.schema_v1 import (Attempt, CandidateDecision, Evaluation, Revision,
                                    Run, RunEvent, SourceInput, Task, WorkerLock)
from ..persistence.worker_health import WorkerHealth
from ..reporting.identity import digest
from .storage import Storage


class ServiceError(ValueError):
    def __init__(self, code, status=409):
        super().__init__(code)
        self.code, self.status = code, status


def identifier():
    return uuid4().hex


def fields(payload, allowed, required=()):
    if type(payload) is not dict or set(payload) - set(allowed) or not set(required) <= set(payload):
        raise ServiceError("invalid_request_fields", 400)


def implementation_binding(settings):
    package = Path(__file__).resolve().parents[1]
    sources = {str(path.relative_to(package)): sha256(path.read_bytes()).hexdigest()
               for path in sorted(package.rglob("*.py"))}
    lock = settings.project_root / "requirements.lock"
    if not lock.is_file():
        raise ServiceError("dependency_lock_missing", 503)
    return {"implementation_sha256": digest(sources),
            "dependency_lock_sha256": sha256(lock.read_bytes()).hexdigest(),
            "p1_sha256": load_p1_contracts(settings.repository_root).manifest_sha256,
            "mode": "development_stub", "fixture_protocol": "p2b-control-v1"}


class Service:
    LEASE_SECONDS = 60
    HEALTH_SECONDS = 30

    def __init__(self, settings):
        if (settings.runtime_dir / ".restore-in-progress").exists():
            raise ServiceError("restore_incomplete_requires_review", 503)
        if settings.database_backend == 'sqlite' and not settings.business_database.is_file():
            raise ServiceError("database_not_initialized", 503)
        self.settings = settings
        self.binding = load_p1_contracts(settings.repository_root)
        self.storage = Storage(settings.artifact_dir)
        self.engine = engine_for_settings(settings)
        try:
            require_schema(self.engine)
        except Exception:
            self.engine.dispose()
            raise
        self.worker_failures = {}  # Per-process fences set by the heartbeat thread.

    def close(self):
        self.engine.dispose()

    def implementation_binding(self):
        return implementation_binding(self.settings)

    def heartbeat(self, owner, state, run_id, binding_sha256):
        with transaction(self.engine) as session:
            if run_id is not None:
                lock = session.get(WorkerLock, "singleton")
                if (lock is None or lock.owner != owner or lock.run_id != run_id
                        or lock.expires_at <= time.time()):
                    raise ServiceError("worker_lease_lost")
                # Cancellation does not drop ownership while a call is still returning.
                lock.expires_at = time.time() + self.LEASE_SECONDS
            row = session.get(WorkerHealth, owner)
            if row is None:
                row = WorkerHealth(id=owner, pid=os.getpid(), binding_sha256=binding_sha256)
                session.add(row)
            elif row.binding_sha256 != binding_sha256:
                raise ServiceError("worker_identity_binding_conflict")
            row.state, row.run_id, row.last_seen = state, run_id, time.time()

    def readiness(self):
        try:
            require_schema(self.engine)
            binding = digest(self.implementation_binding())
            graph_status = "not_created"
            if self.settings.graph_database.exists():
                uri = self.settings.graph_database.resolve().as_uri() + "?mode=ro"
                with closing(sqlite3.connect(uri, uri=True, timeout=5)) as graph:
                    if graph.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                        raise ServiceError("graph_database_unavailable")
                    if not graph.execute("SELECT name FROM sqlite_master WHERE name='checkpoints'").fetchone():
                        raise ServiceError("graph_database_unavailable")
                graph_status = "available"
            with transaction(self.engine) as session:
                workers = list(session.scalars(select(WorkerHealth).where(
                    WorkerHealth.state.in_(("idle", "running")),
                    WorkerHealth.last_seen > time.time() - self.HEALTH_SECONDS,
                    WorkerHealth.binding_sha256 == binding)))
                lock = session.get(WorkerLock, "singleton")
                lease_ok = lock is None or (lock.expires_at > time.time()
                    and any(row.id == lock.owner and row.run_id == lock.run_id for row in workers))
            available = bool(workers) and lease_ok
            return {"status": "development_ready" if available else "not_ready",
                    "database": "available", "worker_readiness": "healthy" if available else "missing_stale_or_incompatible",
                    "graph_database": graph_status,
                    "mode": "development_stub", "production_ready": False}, 200 if available else 503
        except Exception:
            return {"status": "not_ready", "database": "unavailable_or_binding_mismatch",
                    "worker_readiness": "unknown", "mode": "development_stub",
                    "production_ready": False}, 503

    @staticmethod
    def get(session, cls, key):
        row = session.get(cls, key)
        if row is None:
            raise ServiceError("not_found", 404)
        return row

    @staticmethod
    def event(session, run_id, key, kind, details=None):
        if session.scalar(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.event_key == key)) is None:
            session.add(RunEvent(run_id=run_id, event_key=key, kind=kind, details=details or {}))

    def create_input(self, payload, owner_id=None):
        fields(payload, ("filename", "source"), ("filename", "source"))
        name, source = payload["filename"], payload["source"]
        if type(name) is not str or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,100}\.vue", name):
            raise ServiceError("invalid_source_filename", 400)
        if type(source) is not str or not source.strip() or len(source.encode("utf-8")) > 262144:
            raise ServiceError("invalid_source_size", 400)
        key = identifier()
        relative = f"inputs/{key}/{name}"
        with transaction(self.engine) as session:
            if owner_id:
                from .accounts import require_active, audit_event
                from ..persistence.accounts import InputOwner, UserLimit
                from sqlalchemy import func
                require_active(session,owner_id)
                limit=session.get(UserLimit,owner_id)
                stored=session.scalar(select(func.coalesce(func.sum(InputOwner.byte_size),0)).where(InputOwner.user_id==owner_id))
                if stored+len(source.encode('utf-8'))>limit.storage_bytes:raise ServiceError('source_storage_limit_reached',429)
            fingerprint = self.storage.put(relative, source.encode("utf-8"))
            session.add(SourceInput(id=key, filename=name, relative_path=relative, sha256=fingerprint))
            session.flush()
            if owner_id:
                session.add(InputOwner(input_id=key,user_id=owner_id,byte_size=len(source.encode('utf-8'))))
                audit_event(session,owner_id,'source_uploaded',key)
        return {"input_id": key, "filename": name, "sha256": fingerprint}

    def create_task(self, payload):
        fields(payload, ("input_id", "name"), ("input_id",))
        if type(payload["input_id"]) is not str:
            raise ServiceError("invalid_input_id", 400)
        name = payload.get("name", "Development migration")
        if type(name) is not str or not 1 <= len(name.strip()) <= 120:
            raise ServiceError("invalid_task_name", 400)
        key = identifier()
        with transaction(self.engine) as session:
            self.get(session, SourceInput, payload["input_id"])
            session.add(Task(id=key, input_id=payload["input_id"], name=name))
        return {"task_id": key, "name": name}

    def enqueue(self, task_id, payload, idempotency_key):
        fields(payload, ("profile", "max_repair_rounds"))
        if type(idempotency_key) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", idempotency_key):
            raise ServiceError("idempotency_key_required", 400)
        profile = payload.get("profile", "success")
        if profile not in ("success", "repairable", "regression", "always_fail"):
            raise ServiceError("unknown_development_profile", 400)
        rounds = payload.get("max_repair_rounds", 3)
        if type(rounds) is not int or not 0 <= rounds <= 3:
            raise ServiceError("invalid_repair_budget", 400)
        binding = self.implementation_binding()
        with transaction(self.engine) as session:
            task = self.get(session, Task, task_id)
            source = self.get(session, SourceInput, task.input_id)
            request = {"profile": profile, "max_repair_rounds": rounds, "input_sha256": source.sha256,
                       "mode": "development_stub"}
            old = session.scalar(select(Run).where(Run.task_id == task_id, Run.idempotency_key == idempotency_key))
            if old:
                # Compare the submitted configuration, not a newly allocated run ID.
                # The full request hash below also binds the immutable contract snapshot.
                if {key: old.request.get(key) for key in request} != request:
                    raise ServiceError("idempotency_conflict")
                if old.request_sha256 != digest(old.request):
                    raise ServiceError("request_identity_drift")
                return {"run_id": old.id, "reused": True, "mode": "development_stub"}
            from ..reporting.request_snapshot import build_snapshot
            run_id = identifier()
            request["contract_snapshot"] = build_snapshot(
                self.binding.contracts, run_id=run_id, task_id=task_id,
                source={"relative_path": source.relative_path, "sha256": source.sha256}, request=request, binding=binding)
            run = Run(id=run_id, task_id=task_id, idempotency_key=idempotency_key,
                      request_sha256=digest(request), request=request, binding=binding, status="queued",
                      outcome="not_run", final_revision_id=None, cancel_requested=False,
                      stop_reason="", created_at=time.time())
            session.add(run)
            session.flush()
            self.event(session, run.id, "queued", "queued")
            return {"run_id": run.id, "reused": False, "mode": "development_stub"}

    def run(self, run_id):
        with transaction(self.engine) as session:
            row = self.get(session, Run, run_id)
            return {"run_id": row.id, "task_id": row.task_id, "status": row.status,
                    "request_sha256": row.request_sha256,
                    "outcome": row.outcome, "mode": "development_stub", "request": row.request,
                    "binding": row.binding, "stop_reason": row.stop_reason,
                    "final_revision_id": row.final_revision_id, "created_at": row.created_at,
                    "cancel_requested": row.cancel_requested, "production_ready": False}

    def list_runs(self, *, limit=10, before=None, status=None):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ServiceError("invalid_page_size", 400)
        if status not in (None, "queued", "running", "review_required", "finished", "cancelled", "execution_error"):
            raise ServiceError("invalid_run_status_filter", 400)
        statement = select(Run, Task.name, SourceInput.filename).join(Task, Run.task_id == Task.id).join(
            SourceInput, Task.input_id == SourceInput.id)
        if status is not None:
            statement = statement.where(Run.status == status)
        if before is not None:
            try:
                if type(before) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", before):
                    raise ValueError()
                stamp, key = json.loads(base64.urlsafe_b64decode(before + "=" * (-len(before) % 4)))
                if (type(stamp) not in (float, int) or not math.isfinite(stamp) or stamp < 0
                        or type(key) is not str or not re.fullmatch("[0-9a-f]{32}", key)):
                    raise ValueError()
            except (ValueError, TypeError, UnicodeError) as error:
                raise ServiceError("invalid_run_cursor", 400) from error
            statement = statement.where(or_(Run.created_at < stamp, and_(Run.created_at == stamp, Run.id < key)))
        with transaction(self.engine) as session:
            rows = session.execute(statement.order_by(Run.created_at.desc(), Run.id.desc()).limit(limit + 1)).all()
            page = rows[:limit]
            items = [{"run_id": row.id, "task_id": row.task_id, "task_name": name, "filename": filename,
                      "status": row.status, "outcome": row.outcome, "created_at": row.created_at,
                      "mode": "development_stub", "production_ready": False} for row, name, filename in page]
            cursor = None
            if len(rows) > limit:
                last = page[-1][0]
                cursor = base64.urlsafe_b64encode(json.dumps([last.created_at, last.id], separators=(",", ":")).encode()).decode().rstrip("=")
            return {"items": items, "next_cursor": cursor, "mode": "development_stub", "production_ready": False}

    def list_tasks(self, limit=50):
        with transaction(self.engine) as session:
            return [{"task_id": row.id, "input_id": row.input_id, "name": row.name}
                    for row in session.scalars(select(Task).order_by(Task.id).limit(limit))]

    def events(self, run_id, after=0):
        with transaction(self.engine) as session:
            self.get(session, Run, run_id)
            return [{"sequence": row.id, "kind": row.kind, "details": row.details}
                    for row in session.scalars(select(RunEvent).where(
                        RunEvent.run_id == run_id, RunEvent.id > after).order_by(RunEvent.id).limit(200))]

    def cancel(self, run_id):
        with transaction(self.engine) as session:
            run = self.get(session, Run, run_id)
            if run.status in ("finished", "cancelled"):
                return
            run.cancel_requested = True
            if run.status != "running":
                run.status, run.stop_reason = "cancelled", "cancelled_before_execution"
            self.event(session, run_id, "cancel", "cancel_requested")

    def verify_binding(self, run_id):
        row = self.run(run_id)
        if row["binding"] != self.implementation_binding():
            raise ServiceError("implementation_or_dependency_drift")
        if row["request_sha256"] != digest(row["request"]):
            raise ServiceError("request_identity_drift")
        with transaction(self.engine) as session:
            run = self.get(session, Run, run_id)
            source = self.get(session, SourceInput, self.get(session, Task, run.task_id).input_id)
            if source.sha256 != run.request["input_sha256"]:
                raise ServiceError("input_identity_drift")
            self.storage.read(source.relative_path, source.sha256)
            from ..reporting.request_snapshot import validate_snapshot
            try:
                validate_snapshot(self.binding.contracts, run_id=run.id, task_id=run.task_id,
                                  source={"relative_path": source.relative_path, "sha256": source.sha256},
                                  request=run.request, binding=run.binding)
            except (ValueError, KeyError, TypeError) as error:
                raise ServiceError("request_snapshot_missing_or_mismatched") from error

    def resume(self, run_id):
        self.verify_binding(run_id)
        with transaction(self.engine) as session:
            run = self.get(session, Run, run_id)
            if run.status == "queued":
                return
            if run.status not in ("review_required", "execution_error") or run.cancel_requested:
                raise ServiceError("run_not_resumable")
            if session.scalar(select(Attempt).where(Attempt.run_id == run_id, Attempt.status == "started")):
                raise ServiceError("ambiguous_attempt_requires_review")
            lock = session.get(WorkerLock, "singleton")
            if lock and lock.expires_at > time.time():
                raise ServiceError("worker_still_active")
            run.status, run.stop_reason = "queued", ""
            self.event(session, run_id, f"resume-{identifier()}", "resumed")

    def claim(self, owner):
        with transaction(self.engine) as session:
            lock = session.get(WorkerLock, "singleton")
            if lock:
                if lock.expires_at > time.time():
                    return None
                old = self.get(session, Run, lock.run_id)
                if old.status == "running":
                    old.status, old.stop_reason = "review_required", "worker_lease_expired"
                session.delete(lock)
                session.flush()
            run = session.scalar(select(Run).where(Run.status == "queued").order_by(Run.created_at).limit(1))
            if run is None:
                return None
            run.status = "running"
            session.add(WorkerLock(id="singleton", owner=owner, run_id=run.id, expires_at=time.time()+self.LEASE_SECONDS))
            self.event(session, run.id, f"claim-{identifier()}", "running")
            return run.id

    def owned(self, session, run_id, owner, *, allow_cancel=False):
        if owner in self.worker_failures and self.worker_failures[owner].is_set():
            raise ServiceError("worker_heartbeat_failed")
        lock = self.get(session, WorkerLock, "singleton")
        if lock.run_id != run_id or lock.owner != owner or lock.expires_at <= time.time():
            raise ServiceError("worker_lease_lost")
        lock.expires_at = time.time()+self.LEASE_SECONDS
        run = self.get(session, Run, run_id)
        if run.cancel_requested and not allow_cancel:
            raise ServiceError("cancel_requested")
        return run

    def release(self, run_id, owner, *, status=None, reason=""):
        with transaction(self.engine) as session:
            lock = session.get(WorkerLock, "singleton")
            if lock is None or lock.owner != owner or lock.run_id != run_id:
                return
            run = self.get(session, Run, run_id)
            if status:
                run.status, run.stop_reason = status, reason
                self.event(session, run_id, f"release-{identifier()}", status, {"reason": reason})
            session.delete(lock)

    def generate_stub(self, run_id, owner, round_number, parent=None):
        attempt_id = f"{run_id}:stub:{round_number}"
        with transaction(self.engine) as session:
            run = self.owned(session, run_id, owner)
            request_sha = digest({"run_request": run.request_sha256, "round": round_number, "parent": parent})
            old = session.get(Attempt, attempt_id)
            if old:
                if old.request_sha256 != request_sha:
                    raise ServiceError("attempt_identity_conflict")
                if old.status != "completed":
                    raise ServiceError("ambiguous_attempt_requires_review")
                revision = self.get(session, Revision, old.result["revision_id"])
                self.storage.read(revision.relative_path, revision.sha256)
                return old.result
            session.add(Attempt(id=attempt_id, run_id=run_id, kind="development_stub", status="started",
                                request_sha256=request_sha, started_at=time.time(), result=None, model_tokens=None))
            profile = run.request["profile"]
        # Only a deterministic control fixture. Never reads LLM credentials or executes source.
        assertions = {"preserved": not (profile == "regression" and round_number > 0),
                      "requested": profile == "success" or (profile in ("repairable", "regression") and round_number > 0)}
        revision_id = f"{run_id}_{round_number}"
        relative = f"runs/{run_id}/{revision_id}.san"
        content = (f"<!-- DEVELOPMENT STUB: NOT MIGRATED OR EVALUATED; round {round_number} -->\n"
                   "<template><div>Development control fixture</div></template>\n").encode()
        fingerprint = self.storage.put(relative, content)
        result = {"revision_id": revision_id, "assertions": assertions}
        with transaction(self.engine) as session:
            # A cancellation is not a claim that the in-flight operation never returned.
            # Persist its completed receipt while still owned; stop at the next safe node.
            self.owned(session, run_id, owner, allow_cancel=True)
            session.add(Revision(id=revision_id, run_id=run_id, parent_id=parent, relative_path=relative,
                                 sha256=fingerprint, source_kind="development_stub", fixture_assertions=assertions))
            attempt = self.get(session, Attempt, attempt_id)
            attempt.status, attempt.result = "completed", result
            self.event(session, run_id, attempt_id, "stub_response", {"revision_id": revision_id})
        return result

    def evaluate_fixture(self, run_id, owner, revision_id):
        with transaction(self.engine) as session:
            self.owned(session, run_id, owner)
            revision = self.get(session, Revision, revision_id)
            if revision.run_id != run_id:
                raise ServiceError("revision_run_mismatch")
            self.storage.read(revision.relative_path, revision.sha256)
            key = f"{revision_id}:fixture"
            if session.get(Evaluation, key) is None:
                session.add(Evaluation(id=key, run_id=run_id, revision_id=revision_id, status="not_run",
                                      scope="development_control_fixture_only", fixture_assertions=revision.fixture_assertions))
            return revision.fixture_assertions

    def candidate(self, run_id, owner, previous, candidate, before, after):
        action = "reject" if any(value and not after.get(key) for key, value in before.items()) else "accept"
        with transaction(self.engine) as session:
            self.owned(session, run_id, owner)
            key = f"{candidate}:gate"
            if session.get(CandidateDecision, key) is None:
                session.add(CandidateDecision(id=key, run_id=run_id, previous_id=previous, candidate_id=candidate,
                                               action=action, reason="fixture_regression" if action == "reject" else "fixture_no_regression"))
        return action

    def finish(self, run_id, owner, revision_id, reason):
        with transaction(self.engine) as session:
            run = self.owned(session, run_id, owner)
            revision = self.get(session, Revision, revision_id)
            if revision.run_id != run_id:
                raise ServiceError("revision_run_mismatch")
            run.status, run.stop_reason, run.final_revision_id = "finished", reason, revision_id
            run.outcome = "not_run"  # Fixture success NEVER means migrated successfully.
            self.event(session, run_id, "finished", "finished", {"reason": reason, "outcome": "not_run"})

    def report(self, run_id):
        # Capture state, references and facts in ONE short transaction. Do not join
        # a separately fetched terminal state to an earlier/later set of attempts.
        with transaction(self.engine) as session:
            row = self.get(session, Run, run_id)
            source = self.get(session, SourceInput, self.get(session, Task, row.task_id).input_id)

            def record(instance):
                return {column.name: getattr(instance, column.name) for column in instance.__table__.columns}

            snapshot = {"run": record(row), "source": record(source)}
            for name, cls in (("attempts", Attempt), ("revisions", Revision),
                              ("evaluations", Evaluation), ("decisions", CandidateDecision)):
                snapshot[name] = [record(item) for item in session.scalars(
                    select(cls).where(cls.run_id == run_id).order_by(cls.id))]
        row = snapshot["run"]
        result = {"run_id": row["id"], "task_id": row["task_id"], "status": row["status"],
                  "request_sha256": row["request_sha256"], "outcome": row["outcome"], "mode": "development_stub",
                  "request": row["request"], "binding": row["binding"], "stop_reason": row["stop_reason"],
                  "final_revision_id": row["final_revision_id"], "production_ready": False}
        result["attempts"] = [{"attempt_id": item["id"], "kind": item["kind"], "status": item["status"],
                                "model_tokens": item["model_tokens"]} for item in snapshot["attempts"]]
        result["revisions"] = [{"revision_id": item["id"], "parent_id": item["parent_id"],
                                 "sha256": item["sha256"], "source_kind": item["source_kind"]}
                                for item in snapshot["revisions"]]
        result["evaluations"] = [{"evaluation_id": item["id"], "revision_id": item["revision_id"],
                                   "status": item["status"], "scope": item["scope"],
                                   "fixture_assertions": item["fixture_assertions"]} for item in snapshot["evaluations"]]
        result["candidate_decisions"] = [{"decision_id": item["id"], "candidate_id": item["candidate_id"],
                                           "previous_id": item["previous_id"], "action": item["action"],
                                           "reason": item["reason"]} for item in snapshot["decisions"]]
        from ..reporting.projection import project_report, ReportError
        try:
            result.update(project_report(self.binding.contracts, snapshot, self.storage))
        except ReportError as error:
            raise ServiceError(str(error)) from error
        result.update(scope="development_stub_control_flow_not_migration_evaluation", actual_model_calls=0,
                      langsmith_uploaded=False, browser_evaluation="not_run")
        return result

    def download(self, run_id):
        report = self.report(run_id)
        with transaction(self.engine) as session:
            run = self.get(session, Run, run_id)
            if run.status != "finished" or not run.final_revision_id:
                raise ServiceError("final_artifact_unavailable")
            if report["status"] != "finished" or report["final_revision_id"] != run.final_revision_id:
                raise ServiceError("report_changed_before_download")
            revision = self.get(session, Revision, run.final_revision_id)
            if revision.run_id != run_id:
                raise ServiceError("revision_run_mismatch")
            return self.storage.read(revision.relative_path, revision.sha256)
