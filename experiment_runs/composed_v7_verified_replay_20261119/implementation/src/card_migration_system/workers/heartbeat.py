"""Independent heartbeat during idle and blocking stages, with fail-closed ownership."""
from threading import Event, RLock, Thread
from uuid import uuid4

from ..application.service import digest, ServiceError


class WorkerHeartbeat:
    def __init__(self, service, *, interval=10):
        if not 0 < interval < min(service.LEASE_SECONDS, service.HEALTH_SECONDS) / 2:
            raise ValueError("heartbeat_interval_must_be_below_half_timeout")
        self.service, self.interval = service, interval
        self.owner = uuid4().hex
        self.binding = digest(service.implementation_binding())
        self.lock = RLock()
        self.state, self.run_id = "idle", None
        self.stop, self.failed = Event(), Event()
        self.thread = Thread(target=self._loop, name="cardmig-heartbeat", daemon=True)

    def tick(self):
        with self.lock:
            self.service.heartbeat(self.owner, self.state, self.run_id, self.binding)

    def _loop(self):
        while not self.stop.wait(self.interval):
            try:
                self.tick()
            except Exception:
                self.failed.set()
                return

    def require_healthy(self):
        if self.failed.is_set():
            raise ServiceError("worker_heartbeat_failed")

    def __enter__(self):
        self.service.worker_failures[self.owner] = self.failed
        try:
            self.tick()
            self.thread.start()
        except BaseException:
            self.service.worker_failures.pop(self.owner, None)
            raise
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join()  # At most the configured DB timeout; no detached renewing thread.
        try:
            with self.lock:
                self.state, self.run_id = "stopped", None
                self.tick()
        except Exception:
            pass  # Stale presence expires; do not mask the original failure.
        finally:
            self.service.worker_failures.pop(self.owner, None)
