"""Real migration records, independent of development fixture and G1-G3 experiments."""
from sqlalchemy import Column, Integer, Float, String, JSON, Boolean, ForeignKey, Table, UniqueConstraint, MetaData
from sqlalchemy.orm import registry
from .schema_v1 import inputs
metadata=MetaData()
mapper=registry(metadata=metadata)

jobs = Table('migration_jobs', metadata,
    Column('id', String(32), primary_key=True),
    Column('input_id', ForeignKey(inputs.c.id), nullable=False),
    Column('idempotency_key', String(80), unique=True, nullable=False),
    Column('request', JSON, nullable=False), Column('request_sha256', String(64), nullable=False),
    Column('binding', JSON, nullable=False), Column('status', String(32), nullable=False),
    Column('stage', String(40), nullable=False), Column('stop_reason', String(120), nullable=False),
    Column('state', JSON, nullable=False), Column('cancel_requested', Boolean, nullable=False),
    Column('created_at', Float, nullable=False), Column('updated_at', Float, nullable=False))
files = Table('migration_files', metadata,
    Column('relative_path', String(240), primary_key=True), Column('sha256', String(64), nullable=False),
    Column('job_id', ForeignKey('migration_jobs.id'), nullable=False), Column('kind', String(40), nullable=False))
calls = Table('migration_model_calls', metadata,
    Column('id', String(80), primary_key=True), Column('job_id', ForeignKey('migration_jobs.id'), nullable=False),
    Column('ordinal', Integer, nullable=False), Column('status', String(24), nullable=False),
    Column('request_sha256', String(64), nullable=False), Column('receipt', JSON),
    Column('started_at', Float, nullable=False), Column('finished_at', Float),
    UniqueConstraint('job_id', 'ordinal'))
feedback = Table('migration_feedback', metadata,
    Column('id', String(32), primary_key=True), Column('job_id', ForeignKey('migration_jobs.id'), nullable=False),
    Column('revision_sha256', String(64), nullable=False), Column('passed', Boolean, nullable=False),
    Column('changed_lines', Integer), Column('elapsed_seconds', Float), Column('notes', String(4000), nullable=False),
    Column('created_at', Float, nullable=False))

class MigrationJob: pass
class MigrationFile: pass
class ModelCall: pass
class ManualFeedback: pass
for cls, table in ((MigrationJob, jobs), (MigrationFile, files), (ModelCall, calls), (ManualFeedback, feedback)):
    mapper.map_imperatively(cls, table)
