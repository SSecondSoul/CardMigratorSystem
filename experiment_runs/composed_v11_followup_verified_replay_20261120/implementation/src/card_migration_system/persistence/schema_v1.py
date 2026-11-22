"""Frozen initial schema. Evolve with a new Alembic revision, not edits here."""
from sqlalchemy import (Boolean, Column, Float, ForeignKey, ForeignKeyConstraint,
                        Integer, JSON, MetaData, String, Table, UniqueConstraint)
from sqlalchemy.orm import registry

metadata = MetaData()
mapper = registry(metadata=metadata)

inputs = Table("source_inputs", metadata,
    Column("id", String(32), primary_key=True), Column("filename", String(120), nullable=False),
    Column("relative_path", String(240), nullable=False), Column("sha256", String(64), nullable=False))
tasks = Table("tasks", metadata,
    Column("id", String(32), primary_key=True),
    Column("input_id", ForeignKey("source_inputs.id"), nullable=False),
    Column("name", String(120), nullable=False))
runs = Table("runs", metadata,
    Column("id", String(32), primary_key=True), Column("task_id", ForeignKey("tasks.id"), nullable=False),
    Column("idempotency_key", String(80), nullable=False), Column("request_sha256", String(64), nullable=False),
    Column("request", JSON, nullable=False), Column("binding", JSON, nullable=False),
    Column("status", String(32), nullable=False), Column("outcome", String(32), nullable=False),
    Column("final_revision_id", String(80)), Column("cancel_requested", Boolean, nullable=False),
    Column("stop_reason", String(120), nullable=False), Column("created_at", Float, nullable=False),
    UniqueConstraint("task_id", "idempotency_key"))
revisions = Table("artifact_revisions", metadata,
    Column("id", String(80), primary_key=True), Column("run_id", ForeignKey("runs.id"), nullable=False),
    Column("parent_id", String(80)), Column("relative_path", String(240), nullable=False),
    Column("sha256", String(64), nullable=False), Column("source_kind", String(40), nullable=False),
    Column("fixture_assertions", JSON, nullable=False),
    UniqueConstraint("id", "run_id"),
    ForeignKeyConstraint(["parent_id", "run_id"], ["artifact_revisions.id", "artifact_revisions.run_id"]))
attempts = Table("attempts", metadata,
    Column("id", String(100), primary_key=True), Column("run_id", ForeignKey("runs.id"), nullable=False),
    Column("kind", String(40), nullable=False), Column("status", String(24), nullable=False),
    Column("request_sha256", String(64), nullable=False), Column("result", JSON),
    Column("started_at", Float, nullable=False), Column("model_tokens", Integer))
evaluations = Table("evaluations", metadata,
    Column("id", String(100), primary_key=True), Column("run_id", ForeignKey("runs.id"), nullable=False),
    Column("revision_id", String(80), nullable=False), Column("status", String(32), nullable=False),
    Column("scope", String(80), nullable=False), Column("fixture_assertions", JSON, nullable=False),
    ForeignKeyConstraint(["revision_id", "run_id"], ["artifact_revisions.id", "artifact_revisions.run_id"]))
decisions = Table("candidate_decisions", metadata,
    Column("id", String(100), primary_key=True), Column("run_id", ForeignKey("runs.id"), nullable=False),
    Column("previous_id", String(80), nullable=False), Column("candidate_id", String(80), nullable=False),
    Column("action", String(24), nullable=False), Column("reason", String(120), nullable=False),
    ForeignKeyConstraint(["previous_id", "run_id"], ["artifact_revisions.id", "artifact_revisions.run_id"]),
    ForeignKeyConstraint(["candidate_id", "run_id"], ["artifact_revisions.id", "artifact_revisions.run_id"]))
events = Table("run_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", ForeignKey("runs.id"), nullable=False),
    Column("event_key", String(120), nullable=False), Column("kind", String(40), nullable=False),
    Column("details", JSON, nullable=False), UniqueConstraint("run_id", "event_key"))
locks = Table("worker_locks", metadata,
    Column("id", String(20), primary_key=True), Column("owner", String(32), nullable=False),
    Column("run_id", ForeignKey("runs.id"), nullable=False), Column("expires_at", Float, nullable=False))


class SourceInput: pass
class Task: pass
class Run: pass
class Revision: pass
class Attempt: pass
class Evaluation: pass
class CandidateDecision: pass
class RunEvent: pass
class WorkerLock: pass

for cls, table in ((SourceInput, inputs), (Task, tasks), (Run, runs), (Revision, revisions),
                   (Attempt, attempts), (Evaluation, evaluations), (CandidateDecision, decisions),
                   (RunEvent, events), (WorkerLock, locks)):
    mapper.map_imperatively(cls, table)
