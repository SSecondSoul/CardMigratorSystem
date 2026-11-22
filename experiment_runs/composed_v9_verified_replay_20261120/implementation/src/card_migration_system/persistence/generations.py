"""Additive 0004 offline-generation ledger, isolated from fixture/San evidence."""
from sqlalchemy import (CheckConstraint, Column, Float, ForeignKey, JSON, MetaData,
                        String, Table, UniqueConstraint)
from sqlalchemy.orm import registry

from .schema_v1 import inputs
from .ssm_extractions import extractions

metadata = MetaData()
mapper = registry(metadata=metadata)
jobs = Table('generation_jobs', metadata,
    Column('id', String(32), primary_key=True),
    Column('extraction_id', ForeignKey(extractions.c.id), nullable=False),
    Column('input_id', ForeignKey(inputs.c.id), nullable=False),
    Column('idempotency_key', String(80), nullable=False),
    Column('status', String(24), nullable=False),
    Column('request_sha256', String(64), nullable=False),
    Column('request', JSON, nullable=False),
    Column('stop_reason', String(100), nullable=False),
    Column('created_at', Float, nullable=False),
    UniqueConstraint('extraction_id', 'idempotency_key'),
    CheckConstraint("status IN ('prepared','started','received','completed','blocked','review_required')"))
attempts = Table('generation_attempts', metadata,
    Column('id', String(80), primary_key=True),
    Column('job_id', ForeignKey(jobs.c.id), nullable=False, unique=True),
    Column('request_sha256', String(64), nullable=False),
    Column('status', String(24), nullable=False),
    Column('started_at', Float, nullable=False),
    CheckConstraint("status IN ('started','received','review_required')"))
files = Table('generation_files', metadata,
    Column('relative_path', String(240), primary_key=True),
    Column('sha256', String(64), nullable=False),
    Column('job_id', ForeignKey(jobs.c.id), nullable=False),
    Column('kind', String(16), nullable=False),
    UniqueConstraint('job_id', 'kind'),
    CheckConstraint("kind IN ('request','receipt','candidate')"))
candidates = Table('generation_candidates', metadata,
    Column('id', String(80), primary_key=True),
    Column('job_id', ForeignKey(jobs.c.id), nullable=False, unique=True),
    Column('relative_path', ForeignKey(files.c.relative_path), nullable=False, unique=True),
    Column('sha256', String(64), nullable=False),
    Column('parent_id', String(80)),
    Column('source_kind', String(32), nullable=False),
    CheckConstraint('parent_id IS NULL'),
    CheckConstraint("source_kind = 'offline_client_test'"))


class GenerationJob: pass
class GenerationAttempt: pass
class GenerationFile: pass
class GenerationCandidate: pass


for cls, table in ((GenerationJob, jobs), (GenerationAttempt, attempts),
                   (GenerationFile, files), (GenerationCandidate, candidates)):
    mapper.map_imperatively(cls, table)
