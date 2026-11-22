"""Accounts, quotas and ownership; no model client or source execution here."""
import base64
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
from hmac import compare_digest
import re
import secrets
import time
from uuid import uuid4

from sqlalchemy import select, func
from werkzeug.security import generate_password_hash, check_password_hash
from .service import ServiceError, fields
from ..persistence.database import transaction
from ..persistence.accounts import User, AuthSession, UserLimit, DailyUsage, InputOwner, JobOwner, AuditLog, AuthThrottle
from ..persistence.migrations import MigrationJob, ModelCall

PASSWORD_METHOD = 'scrypt:32768:8:3'
DEFAULT_LIMITS = dict(max_active_jobs=3,daily_jobs=20,daily_model_calls=50,daily_tokens_soft=500000,storage_bytes=20*1024*1024)
LIMIT_MAX = dict(max_active_jobs=20,daily_jobs=1000,daily_model_calls=10000,daily_tokens_soft=100000000,storage_bytes=1000000000)

def digest_token(value): return sha256(value.encode()).hexdigest()
def csrf_for(token): return base64.urlsafe_b64encode(sha256(('cardmig-csrf-v1:'+token).encode()).digest()).decode().rstrip('=')
def day_key(): return datetime.now(timezone.utc).strftime('%Y-%m-%d')
def public_user(user):
    return {key:getattr(user,key) for key in ('id','username','display_name','role','is_active','must_change_password','created_at')}
def audit_event(s,actor,action,target=None,details=None):
    s.add(AuditLog(id=uuid4().hex,actor_id=actor,action=action,target_id=target,created_at=time.time(),details=details or {}))
def require_active(s,user_id):
    user=s.get(User,user_id)
    if not user or not user.is_active: raise ServiceError('account_disabled',403)
    return user
def usage_row(s,user_id):
    row=s.get(DailyUsage,(user_id,day_key()))
    if not row:
        row=DailyUsage(user_id=user_id,day=day_key(),jobs_count=0,calls_count=0,known_tokens=0);s.add(row);s.flush()
    return row
def password_hash(password):
    if type(password) is not str or not 12<=len(password)<=128: raise ServiceError('password_length_12_to_128',400)
    return generate_password_hash(password,method=PASSWORD_METHOD)
@lru_cache(maxsize=1)
def dummy_hash(): return password_hash(secrets.token_urlsafe(32))

def reserve_job(s,user_id,input_id):
    require_active(s,user_id)
    owner=s.get(InputOwner,input_id)
    if not owner or owner.user_id!=user_id: raise ServiceError('not_found',404)
    limit=s.get(UserLimit,user_id);usage=usage_row(s,user_id)
    active=s.scalar(select(func.count()).select_from(MigrationJob).join(JobOwner,JobOwner.job_id==MigrationJob.id)
                    .where(JobOwner.user_id==user_id,MigrationJob.status.in_(('queued','running'))))
    if active>=limit.max_active_jobs: raise ServiceError('active_job_limit_reached',429)
    if usage.jobs_count>=limit.daily_jobs: raise ServiceError('daily_job_limit_reached',429)
    usage.jobs_count+=1

def reserve_call(s,job_id):
    owner=s.get(JobOwner,job_id)
    if not owner: return  # Local CLI/archived experiment paths retain their original budget contract.
    require_active(s,owner.user_id);limit=s.get(UserLimit,owner.user_id);usage=usage_row(s,owner.user_id)
    previous=s.scalars(select(ModelCall).join(JobOwner,JobOwner.job_id==ModelCall.job_id).where(JobOwner.user_id==owner.user_id)).all()
    if any(c.status!='returned' or not c.receipt or c.receipt.get('usage') is None for c in previous):
        raise ServiceError('user_model_usage_unknown_requires_review')
    if usage.calls_count>=limit.daily_model_calls: raise ServiceError('daily_model_call_limit_reached')
    if usage.known_tokens>=limit.daily_tokens_soft: raise ServiceError('daily_token_stop_reached')
    usage.calls_count+=1

def check_resume_limit(s,job_id):
    owner=s.get(JobOwner,job_id)
    if not owner:return
    require_active(s,owner.user_id);limit=s.get(UserLimit,owner.user_id)
    active=s.scalar(select(func.count()).select_from(MigrationJob).join(JobOwner,JobOwner.job_id==MigrationJob.id)
                    .where(JobOwner.user_id==owner.user_id,MigrationJob.status.in_(('queued','running'))))
    if active>=limit.max_active_jobs:raise ServiceError('active_job_limit_reached',429)

def settle_call(s,job_id,started_at,usage):
    owner=s.get(JobOwner,job_id)
    if owner and usage:
        # Charge to reservation day even when the response crosses midnight.
        key=datetime.fromtimestamp(started_at,timezone.utc).strftime('%Y-%m-%d')
        row=s.get(DailyUsage,(owner.user_id,key))
        if row: row.known_tokens+=usage['total_tokens']

class AccountService:
    lifetime=8*60*60
    def __init__(self,base): self.base=base;self.engine=base.engine

    def create_user(self,payload,actor_id=None,bootstrap=False):
        fields(payload,('username','display_name','password','role'),('username','password'))
        username=payload['username'];role=payload.get('role','user');display=payload.get('display_name',username)
        if type(username) is not str or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{2,63}',username): raise ServiceError('invalid_username',400)
        if role not in ('admin','user') or type(display) is not str or not 1<=len(display.strip())<=120: raise ServiceError('invalid_account_fields',400)
        encoded=password_hash(payload['password']);key=uuid4().hex;now=time.time()
        with transaction(self.engine) as s:
            if bootstrap:
                if s.scalar(select(func.count()).select_from(User)): raise ServiceError('admin_already_initialized')
                role='admin'
            else:
                actor=require_active(s,actor_id)
                if actor.role!='admin': raise ServiceError('admin_required',403)
            if s.scalar(select(User.id).where(User.username_normalized==username.lower())): raise ServiceError('username_unavailable',409)
            user=User(id=key,username=username,username_normalized=username.lower(),display_name=display.strip(),password_hash=encoded,
                      role=role,is_active=True,must_change_password=not bootstrap,created_at=now,password_changed_at=now)
            s.add(user);s.flush();s.add(UserLimit(user_id=key,**DEFAULT_LIMITS))
            audit_event(s,actor_id,'account_created',key,{'role':role,'bootstrap':bootstrap})
        return public_user(user)

    def login(self,username,password,remote,origin):
        if type(username) is not str or len(username)>64 or type(password) is not str or len(password)>128: raise ServiceError('invalid_credentials',401)
        normalized=username.lower();now=time.time()
        buckets=[(digest_token('account:'+normalized+':'+remote),5),(digest_token('ip:'+remote),30)]
        with transaction(self.engine) as s:
            for key,maximum in buckets:
                row=s.get(AuthThrottle,key)
                if row and row.window_start>now-900 and row.failures>=maximum: raise ServiceError('login_rate_limited',429)
                if not row: row=AuthThrottle(bucket=key,window_start=now,failures=0);s.add(row)
                if row.window_start<=now-900: row.window_start=now;row.failures=0
                row.failures+=1
            user=s.scalar(select(User).where(User.username_normalized==normalized))
        matched=check_password_hash(user.password_hash if user else dummy_hash(),password)
        if not user or not user.is_active or not matched:
            with transaction(self.engine) as s: audit_event(s,None,'login_failed',None,{'account_digest':digest_token(normalized)})
            raise ServiceError('invalid_credentials',401)
        token=secrets.token_urlsafe(32)
        with transaction(self.engine) as s:
            current=require_active(s,user.id)
            if current.password_hash!=user.password_hash: raise ServiceError('invalid_credentials',401)
            s.add(AuthSession(id=uuid4().hex,user_id=user.id,token_sha256=digest_token(token),origin=origin,
                              created_at=now,expires_at=now+self.lifetime,revoked_at=None))
            s.get(AuthThrottle,buckets[0][0]).failures=0
            # Bound live sessions per user; older sessions are revoked, not deleted.
            older=s.scalars(select(AuthSession).where(AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None)).order_by(AuthSession.created_at.desc())).all()
            for old in older[9:]: old.revoked_at=now
            audit_event(s,user.id,'login_succeeded',user.id)
        return token,public_user(current)

    def resolve(self,token,origin):
        if type(token) is not str or not re.fullmatch('[A-Za-z0-9_-]{43}',token): return None
        with transaction(self.engine) as s:
            row=s.scalar(select(AuthSession).where(AuthSession.token_sha256==digest_token(token),AuthSession.revoked_at.is_(None),AuthSession.expires_at>time.time()+60))
            if not row or row.origin!=origin: return None
            user=s.get(User,row.user_id)
            if not user or not user.is_active: return None
            return {'user':public_user(user),'csrf_token':csrf_for(token),'expires_in':max(1,int(row.expires_at-time.time())),'session_id':row.id}

    def logout(self,session_id,user_id):
        with transaction(self.engine) as s:
            row=s.get(AuthSession,session_id)
            if row and row.user_id==user_id: row.revoked_at=time.time()
            audit_event(s,user_id,'logout',user_id)

    def change_password(self,user_id,current_password,new_password):
        with transaction(self.engine) as s: user=require_active(s,user_id)
        if type(current_password) is not str or len(current_password)>128 or not check_password_hash(user.password_hash,current_password): raise ServiceError('current_password_incorrect',403)
        encoded=password_hash(new_password)
        if current_password==new_password: raise ServiceError('password_must_change',400)
        with transaction(self.engine) as s:
            current=require_active(s,user_id)
            if current.password_hash!=user.password_hash: raise ServiceError('auth_required',401)
            current.password_hash=encoded;current.password_changed_at=time.time();current.must_change_password=False
            self._revoke(s,user_id);audit_event(s,user_id,'password_changed',user_id)

    @staticmethod
    def _revoke(s,user_id):
        for row in s.scalars(select(AuthSession).where(AuthSession.user_id==user_id,AuthSession.revoked_at.is_(None))): row.revoked_at=time.time()

    def manage_user(self,actor_id,target_id,payload):
        fields(payload,('is_active','new_password','admin_password'))
        if not payload or not ('is_active' in payload or 'new_password' in payload): raise ServiceError('invalid_account_fields',400)
        with transaction(self.engine) as s: actor=require_active(s,actor_id)
        if actor.role!='admin': raise ServiceError('admin_required',403)
        secret=payload.get('admin_password')
        if type(secret) is not str or len(secret)>128 or not check_password_hash(actor.password_hash,secret): raise ServiceError('current_password_incorrect',403)
        encoded=password_hash(payload['new_password']) if 'new_password' in payload else None
        if 'is_active' in payload and type(payload['is_active']) is not bool: raise ServiceError('invalid_account_fields',400)
        with transaction(self.engine) as s:
            target=s.get(User,target_id)
            if not target: raise ServiceError('not_found',404)
            # Recheck administrator credentials inside the write transaction.
            current=require_active(s,actor_id)
            if current.role!='admin' or current.password_hash!=actor.password_hash: raise ServiceError('auth_required',401)
            if payload.get('is_active') is False:
                if target.id==actor_id: raise ServiceError('cannot_disable_self')
                if target.role=='admin' and target.is_active and s.scalar(select(func.count()).select_from(User).where(User.role=='admin',User.is_active.is_(True)))<=1: raise ServiceError('last_admin_required')
            if 'is_active' in payload: target.is_active=payload['is_active']
            if encoded: target.password_hash=encoded;target.password_changed_at=time.time();target.must_change_password=True
            self._revoke(s,target_id);audit_event(s,actor_id,'account_updated',target_id,{'disabled':not target.is_active,'password_reset':bool(encoded)})
            return public_user(target)

    def set_limits(self,actor_id,user_id,payload):
        fields(payload,tuple(DEFAULT_LIMITS),tuple(DEFAULT_LIMITS))
        if any(type(v) is not int or not 0<=v<=LIMIT_MAX[k] for k,v in payload.items()): raise ServiceError('invalid_user_limits',400)
        with transaction(self.engine) as s:
            if require_active(s,actor_id).role!='admin': raise ServiceError('admin_required',403)
            row=s.get(UserLimit,user_id)
            if not row: raise ServiceError('not_found',404)
            for key,value in payload.items(): setattr(row,key,value)
            audit_event(s,actor_id,'limits_updated',user_id,payload)

    def usage(self,user_id):
        with transaction(self.engine) as s:
            require_active(s,user_id);limit=s.get(UserLimit,user_id);row=s.get(DailyUsage,(user_id,day_key()))
            active=s.scalar(select(func.count()).select_from(MigrationJob).join(JobOwner,JobOwner.job_id==MigrationJob.id).where(JobOwner.user_id==user_id,MigrationJob.status.in_(('queued','running'))))
            stored=s.scalar(select(func.coalesce(func.sum(InputOwner.byte_size),0)).where(InputOwner.user_id==user_id))
            return {'day_utc':day_key(),'limits':{k:getattr(limit,k) for k in DEFAULT_LIMITS},
                    'used':{'jobs':row.jobs_count if row else 0,'calls':row.calls_count if row else 0,'known_tokens':row.known_tokens if row else 0,'active_jobs':active,'source_bytes':stored},
                    'token_limit_kind':'soft_stop_not_billing_cap','storage_scope':'registered_source_bytes_not_all_artifacts'}

    def authorize_job(self,user,key):
        with transaction(self.engine) as s:
            owner=s.get(JobOwner,key)
            if user['role']!='admin' and (not owner or owner.user_id!=user['id']): raise ServiceError('not_found',404)
            if not s.get(MigrationJob,key): raise ServiceError('not_found',404)

    def users(self):
        with transaction(self.engine) as s: rows=s.scalars(select(User).order_by(User.created_at).limit(200)).all()
        return [{'user':public_user(u),'usage':self.usage(u.id) if u.is_active else None} for u in rows]

    def audits(self):
        with transaction(self.engine) as s:
            return [{k:getattr(r,k) for k in ('id','actor_id','action','target_id','created_at','details')} for r in s.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100))]
