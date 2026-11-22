"""Additive multi-user schema. Ownership is separate from frozen experiment rows."""
from sqlalchemy import Table, Column, String, Boolean, Float, Integer, JSON, ForeignKey, UniqueConstraint, CheckConstraint, MetaData
from sqlalchemy.orm import registry
from .schema_v1 import inputs
from .migrations import jobs

metadata = MetaData(); mapper = registry(metadata=metadata)
users = Table('users', metadata,
    Column('id', String(32), primary_key=True), Column('username', String(64), nullable=False),
    Column('username_normalized', String(64), nullable=False, unique=True), Column('display_name', String(120), nullable=False),
    Column('password_hash', String(255), nullable=False), Column('role', String(16), nullable=False),
    Column('is_active', Boolean, nullable=False), Column('must_change_password', Boolean, nullable=False),
    Column('created_at', Float, nullable=False), Column('password_changed_at', Float, nullable=False),
    CheckConstraint("role IN ('admin','user')"))
sessions = Table('auth_sessions', metadata,
    Column('id', String(32), primary_key=True), Column('user_id', ForeignKey(users.c.id), nullable=False),
    Column('token_sha256', String(64), nullable=False, unique=True), Column('origin', String(240), nullable=False),
    Column('created_at', Float, nullable=False), Column('expires_at', Float, nullable=False), Column('revoked_at', Float))
limits = Table('user_limits', metadata,
    Column('user_id', ForeignKey(users.c.id), primary_key=True),
    Column('max_active_jobs', Integer, nullable=False), Column('daily_jobs', Integer, nullable=False),
    Column('daily_model_calls', Integer, nullable=False), Column('daily_tokens_soft', Integer, nullable=False),
    Column('storage_bytes', Integer, nullable=False),
    CheckConstraint('max_active_jobs >= 0 AND daily_jobs >= 0 AND daily_model_calls >= 0 AND daily_tokens_soft >= 0 AND storage_bytes >= 0'))
daily = Table('user_usage_daily', metadata,
    Column('user_id', ForeignKey(users.c.id), primary_key=True), Column('day', String(10), primary_key=True),
    Column('jobs_count', Integer, nullable=False), Column('calls_count', Integer, nullable=False), Column('known_tokens', Integer, nullable=False))
input_owners = Table('input_owners', metadata,
    Column('input_id', ForeignKey(inputs.c.id), primary_key=True), Column('user_id', ForeignKey(users.c.id), nullable=False),
    Column('byte_size', Integer, nullable=False), UniqueConstraint('user_id', 'input_id'))
job_owners = Table('job_owners', metadata,
    Column('job_id', ForeignKey(jobs.c.id), primary_key=True), Column('user_id', ForeignKey(users.c.id), nullable=False))
audit = Table('audit_logs', metadata,
    Column('id', String(32), primary_key=True), Column('actor_id', ForeignKey(users.c.id)),
    Column('action', String(80), nullable=False), Column('target_id', String(100)),
    Column('created_at', Float, nullable=False), Column('details', JSON, nullable=False))
throttle = Table('auth_throttle', metadata,
    Column('bucket', String(64), primary_key=True), Column('window_start', Float, nullable=False), Column('failures', Integer, nullable=False))

class User: pass
class AuthSession: pass
class UserLimit: pass
class DailyUsage: pass
class InputOwner: pass
class JobOwner: pass
class AuditLog: pass
class AuthThrottle: pass
for cls, table in ((User,users),(AuthSession,sessions),(UserLimit,limits),(DailyUsage,daily),
                   (InputOwner,input_owners),(JobOwner,job_owners),(AuditLog,audit),(AuthThrottle,throttle)):
    mapper.map_imperatively(cls,table)
