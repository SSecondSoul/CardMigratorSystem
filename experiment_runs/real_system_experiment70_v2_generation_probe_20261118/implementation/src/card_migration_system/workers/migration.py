"""Single-machine real worker; shared OS guard fences checkpoint and paid calls."""
from threading import Event,Thread
import time
from uuid import uuid4
from sqlalchemy import select

from ..application.migrations import MigrationService,binding
from ..persistence.database import transaction
from ..persistence.runtime_lock import execution_guard,RuntimeBusyError
from ..persistence.migrations import MigrationJob
from ..persistence.worker_health import WorkerHealth
from ..graph.migration import execute_migration
from ..reporting.identity import digest


def run_migration_worker(base,*,once=False,stop_event=None,interval=1):
    stop=stop_event or Event();owner=uuid4().hex;heartbeat_stop=Event();failures=[]
    identity=digest(binding(base.settings))
    def beat():
        while not heartbeat_stop.is_set():
            try:
                with transaction(base.engine) as s:
                    row=s.get(WorkerHealth,owner)
                    if not row:row=WorkerHealth(id=owner,pid=__import__('os').getpid(),binding_sha256=identity);s.add(row)
                    row.state='migration_worker';row.run_id=None;row.last_seen=time.time()
            except Exception:failures.append('migration_heartbeat_failed');return
            heartbeat_stop.wait(5)
    thread=Thread(target=beat,daemon=True);thread.start()
    try:
        while not stop.is_set():
            if failures:raise ValueError(failures[0])
            result=work_once(base)
            if once:return result
            stop.wait(interval)
    finally:
        heartbeat_stop.set();thread.join(timeout=10)
        with transaction(base.engine) as s:
            row=s.get(WorkerHealth,owner)
            if row:row.state='stopped';row.last_seen=time.time()
    return {'status':'stopped'}


def work_once(base,*,service=None,interrupt_after=None):
    try:
        with execution_guard(base.settings.runtime_dir):
            with transaction(base.engine) as s:
                # A crashed worker's 'running' row can replay committed receipts, never resend an unknown call.
                row=s.scalar(select(MigrationJob).where(MigrationJob.status.in_(('queued','running'))).order_by(MigrationJob.created_at).limit(1))
                key=row.id if row else None
            if not key:return {'status':'idle'}
            ledger=service or MigrationService(base)
            try:return execute_migration(ledger,key,interrupt_after=interrupt_after)
            except Exception as error:
                ledger.update(key,status='blocked',stop_reason=getattr(error,'code',type(error).__name__))
                return ledger.report(key)
    except RuntimeBusyError:return {'status':'busy'}
