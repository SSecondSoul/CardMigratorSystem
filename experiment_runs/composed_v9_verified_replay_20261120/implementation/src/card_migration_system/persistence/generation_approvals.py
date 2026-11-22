"""Additive, single-plan local approval ledger; no model invocation here."""
from sqlalchemy import CheckConstraint, Column, Float, ForeignKey, JSON, MetaData, String, Table, UniqueConstraint
from sqlalchemy.orm import registry

from .ssm_extractions import extractions

metadata = MetaData()
mapper = registry(metadata=metadata)
approvals = Table('generation_approvals', metadata,
    Column('id', String(32), primary_key=True),
    Column('extraction_id', ForeignKey(extractions.c.id), nullable=False),
    Column('idempotency_key', String(80), nullable=False),
    Column('request', JSON, nullable=False),
    Column('request_sha256', String(64), nullable=False),
    Column('status', String(16), nullable=False),
    Column('created_at', Float, nullable=False),
    Column('expires_at', Float, nullable=False),
    UniqueConstraint('extraction_id', 'idempotency_key'),
    CheckConstraint("status IN ('pending','approved','revoked','consumed')"))
files = Table('generation_approval_files', metadata,
    Column('relative_path', String(240), primary_key=True),
    Column('sha256', String(64), nullable=False),
    Column('approval_id', ForeignKey(approvals.c.id), nullable=False),
    Column('kind', String(16), nullable=False),
    UniqueConstraint('approval_id', 'kind'),
    CheckConstraint("kind IN ('request','approval','revocation','claim')"))


class GenerationApproval: pass
class GenerationApprovalFile: pass


mapper.map_imperatively(GenerationApproval, approvals)
mapper.map_imperatively(GenerationApprovalFile, files)
