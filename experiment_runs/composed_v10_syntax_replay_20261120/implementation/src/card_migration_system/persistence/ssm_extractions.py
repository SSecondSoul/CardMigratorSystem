"""Registered source-extraction ledger, additive schema 0003; not San revisions."""
from sqlalchemy import (CheckConstraint, Column, Float, ForeignKey, JSON, MetaData,
                        String, Table, UniqueConstraint)
from sqlalchemy.orm import registry

from .schema_v1 import inputs, runs

metadata = MetaData()
mapper = registry(metadata=metadata)
extractions = Table('ssm_extractions', metadata,
    Column('id', String(32), primary_key=True),
    Column('input_id', ForeignKey(inputs.c.id), nullable=False),
    Column('referenced_run_id', ForeignKey(runs.c.id)),
    Column('status', String(24), nullable=False),
    Column('request_sha256', String(64), nullable=False),
    Column('request', JSON, nullable=False),
    Column('stop_reason', String(100), nullable=False),
    Column('created_at', Float, nullable=False),
    CheckConstraint("status IN ('prepared','started','received','completed','blocked','review_required')"))
files = Table('ssm_extraction_files', metadata,
    Column('relative_path', String(240), primary_key=True),
    Column('sha256', String(64), nullable=False),
    Column('extraction_id', ForeignKey(extractions.c.id), nullable=False),
    Column('kind', String(16), nullable=False),
    CheckConstraint("kind IN ('request','ssm','receipt')"),
    UniqueConstraint('extraction_id', 'kind'))


class SSMExtraction: pass
class SSMExtractionFile: pass


mapper.map_imperatively(SSMExtraction, extractions)
mapper.map_imperatively(SSMExtractionFile, files)
