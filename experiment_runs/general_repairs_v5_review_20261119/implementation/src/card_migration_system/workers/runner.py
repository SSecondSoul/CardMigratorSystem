"""One claimed run per invocation; the CLI can poll. No paid model or trace upload."""
from threading import Event

from langgraph.checkpoint.sqlite import SqliteSaver
from langsmith import tracing_context

from ..application.service import ServiceError
from ..graph.builder import build_graph
from ..persistence.runtime_lock import execution_guard, RuntimeBusyError
from .heartbeat import WorkerHeartbeat


def run_worker(service, *, once=False, stop_event=None, interval=10, poll_interval=1):
    stop = stop_event if stop_event is not None else Event()
    with WorkerHeartbeat(service, interval=interval) as heartbeat:
        while not stop.is_set():
            heartbeat.require_healthy()
            result = work_once(service, heartbeat=heartbeat)
            if once:
                return result
            if result["status"] in ("idle", "busy"):
                stop.wait(poll_interval)
    return {"status": "stopped"}


def work_once(service, *, interrupt_after=None, heartbeat=None):
    if heartbeat is None:
        with WorkerHeartbeat(service) as presence:
            return work_once(service, interrupt_after=interrupt_after, heartbeat=presence)
    heartbeat.require_healthy()
    try:
        with execution_guard(service.settings.runtime_dir):
            return _execute(service, heartbeat, interrupt_after)
    except RuntimeBusyError:
        return {"status": "busy"}


def _execute(service, heartbeat, interrupt_after):
    owner = heartbeat.owner
    with heartbeat.lock:
        run_id = service.claim(owner)
        if run_id is not None:
            heartbeat.state, heartbeat.run_id = "running", run_id
    if run_id is None:
        return {"status": "idle"}
    try:
        heartbeat.tick()
        service.verify_binding(run_id)
        run = service.run(run_id)
        config = {"configurable": {"thread_id": run_id}, "recursion_limit": 50, "callbacks": []}
        # Explicitly overrides ambient tracing environment. No data upload in P2b.
        with tracing_context(enabled=False):
            with SqliteSaver.from_conn_string(str(service.settings.graph_database)) as saver:
                graph = build_graph(service, run_id, owner, saver, interrupt_after=interrupt_after)
                snapshot = graph.get_state(config)
                if snapshot.values:
                    if snapshot.values.get("request_sha256") != run["request_sha256"]:
                        raise ServiceError("checkpoint_binding_mismatch")
                    if not snapshot.next:
                        # Business report and graph finalization may have different commit boundaries.
                        if service.run(run_id)["status"] != "finished":
                            raise ServiceError("terminal_checkpoint_requires_review")
                    else:
                        graph.invoke(None, config, durability="sync")
                else:
                    graph.invoke({"run_id": run_id, "request_sha256": run["request_sha256"]},
                                 config, durability="sync")
                pending = bool(graph.get_state(config).next)
        with heartbeat.lock:
            if pending:
                service.release(run_id, owner, status="review_required", reason="controlled_graph_interrupt")
            else:
                service.release(run_id, owner)
            heartbeat.state, heartbeat.run_id = "idle", None
            heartbeat.tick()
        return service.run(run_id)
    except Exception as error:
        code = error.code if isinstance(error, ServiceError) else type(error).__name__
        status = "cancelled" if code == "cancel_requested" else "execution_error"
        with heartbeat.lock:
            service.release(run_id, owner, status=status, reason=code)
            heartbeat.state, heartbeat.run_id = "idle", None
        return service.run(run_id)
    finally:
        # Also handles KeyboardInterrupt: preserve run/attempt facts for lease review,
        # but stop renewing a run that is no longer executing in this process.
        with heartbeat.lock:
            heartbeat.state, heartbeat.run_id = "idle", None
