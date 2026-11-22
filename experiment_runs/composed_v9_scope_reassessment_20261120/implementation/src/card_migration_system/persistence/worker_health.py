"""Operational presence, not run ownership or migration evidence; schema revision 0002."""
from sqlalchemy import Column, Float, Integer, MetaData, String, Table
from sqlalchemy.orm import registry

metadata = MetaData()
mapper = registry(metadata=metadata)
workers = Table("worker_health", metadata,
    Column("id", String(32), primary_key=True),
    Column("pid", Integer, nullable=False),
    Column("state", String(24), nullable=False),
    Column("run_id", String(32)),  # Informational only. worker_locks owns the run.
    Column("last_seen", Float, nullable=False),
    Column("binding_sha256", String(64), nullable=False))


class WorkerHealth: pass


mapper.map_imperatively(WorkerHealth, workers)
