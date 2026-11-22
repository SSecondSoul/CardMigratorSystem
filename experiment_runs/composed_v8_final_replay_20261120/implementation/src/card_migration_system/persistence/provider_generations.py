"""Additive recorded-transport ledger; never mixed with G2 candidate provenance."""
from sqlalchemy import CheckConstraint, Column, Float, ForeignKey, JSON, MetaData, String, Table, UniqueConstraint
from sqlalchemy.orm import registry

from .ssm_extractions import extractions

metadata = MetaData()
mapper = registry(metadata=metadata)
jobs = Table('provider_generation_jobs', metadata,
    Column('id', String(32), primary_key=True),
    Column('extraction_id', ForeignKey(extractions.c.id), nullable=False),
    Column('idempotency_key', String(80), nullable=False),
    Column('request', JSON, nullable=False),
    Column('request_sha256', String(64), nullable=False),
    Column('status', String(24), nullable=False),
    Column('stop_reason', String(100), nullable=False),
    Column('created_at', Float, nullable=False),
    UniqueConstraint('extraction_id', 'idempotency_key'),
    CheckConstraint("status IN ('prepared','started','received','completed','blocked','review_required')"))
attempts = Table('provider_generation_attempts', metadata,
    Column('id', String(80), primary_key=True),
    Column('job_id', ForeignKey(jobs.c.id), nullable=False, unique=True),
    Column('request_sha256', String(64), nullable=False),
    Column('status', String(24), nullable=False),
    Column('started_at', Float, nullable=False),
    CheckConstraint("status IN ('started','received','review_required')"))
files = Table('provider_generation_files', metadata,
    Column('relative_path', String(240), primary_key=True),
    Column('sha256', String(64), nullable=False),
    Column('job_id', ForeignKey(jobs.c.id), nullable=False),
    Column('kind', String(16), nullable=False),
    UniqueConstraint('job_id', 'kind'),
    CheckConstraint("kind IN ('plan','request','response','receipt','candidate')"))


class ProviderGenerationJob: pass
class ProviderGenerationAttempt: pass
class ProviderGenerationFile: pass


for cls, table in ((ProviderGenerationJob, jobs), (ProviderGenerationAttempt, attempts), (ProviderGenerationFile, files)):
    mapper.map_imperatively(cls, table)
