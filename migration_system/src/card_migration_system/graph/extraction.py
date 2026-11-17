"""Separate real SSM graph; never silently graft real evidence onto fixture runs."""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver
from langsmith import tracing_context

from ..application.extractions import ExtractionService
from ..application.service import ServiceError
from ..application.storage import StorageError
from ..persistence.runtime_lock import execution_guard


class ExtractionState(TypedDict, total=False):
    extraction_id: str
    request_sha256: str
    outcome: str
    stop_reason: str


def build_extraction_graph(service, key, saver, *, interrupt_after=None):
    request_hash = service.report(key)['request_sha256']

    def prepare(state):
        if state.get('extraction_id') != key or state.get('request_sha256') != request_hash:
            raise ServiceError('ssm_checkpoint_binding_mismatch')
        service.verify_binding(key)
        return {}

    def extract(_):
        return {'outcome': service.extract(key)['status']}

    def report(_):
        return {'outcome': service.finish(key)}

    graph = StateGraph(ExtractionState)
    graph.add_node('prepare_source', prepare)
    graph.add_node('extract_ssm', extract)
    graph.add_node('register_report', report)
    graph.add_edge(START, 'prepare_source')
    graph.add_edge('prepare_source', 'extract_ssm')
    graph.add_edge('extract_ssm', 'register_report')
    graph.add_edge('register_report', END)
    return graph.compile(checkpointer=saver, interrupt_after=interrupt_after)


def execute_extraction(base_service, *, input_id=None, run_id=None, extraction_id=None, interrupt_after=None):
    service = ExtractionService(base_service)
    with execution_guard(base_service.settings.runtime_dir):
        if extraction_id is None:
            key = service.create(input_id=input_id, run_id=run_id)
        else:
            if input_id is not None or run_id is not None:
                raise ServiceError('ssm_resume_source_not_allowed')
            key = extraction_id
        try:
            report = service.verify_binding(key)
        except Exception as error:
            code = error_code(error)
            # A stopped/ambiguous attempt must remain reviewable even after code
            # drift. No parser runs here; the OS guard rules out a live executor.
            try:
                service.review(key, code)
            except ServiceError as review_error:
                if review_error.code != 'not_found':
                    raise
            raise ServiceError(code) from None
        if report['status'] in ('completed', 'blocked'):
            return summary(report)
        config = {'configurable': {'thread_id': 'ssm:' + key}, 'recursion_limit': 10, 'callbacks': []}
        try:
            with tracing_context(enabled=False):
                with SqliteSaver.from_conn_string(str(base_service.settings.graph_database)) as saver:
                    graph = build_extraction_graph(service, key, saver, interrupt_after=interrupt_after)
                    state = graph.get_state(config)
                    if state.values:
                        if state.values.get('extraction_id') != key or state.values.get('request_sha256') != report['request_sha256']:
                            raise ServiceError('ssm_checkpoint_binding_mismatch')
                        if not state.next:
                            raise ServiceError('ssm_terminal_checkpoint_requires_review')
                        graph.invoke(None, config, durability='sync')
                    else:
                        graph.invoke({'extraction_id': key, 'request_sha256': report['request_sha256']}, config, durability='sync')
                    pending = bool(graph.get_state(config).next)
            result = service.report(key)
            return {**summary(result), 'graph_pending': pending}
        except Exception as error:
            code = error_code(error)
            service.review(key, code)
            raise ServiceError(code) from None


def error_code(error):
    if isinstance(error, ServiceError):
        return error.code
    if isinstance(error, StorageError):
        return str(error)
    return type(error).__name__  # No raw parser errors, source or stack in the ledger.


def summary(report):
    return {'status': report['status'], 'extraction_id': report['extraction_id'],
            'stop_reason': report['stop_reason'], 'request_sha256': report['request_sha256'],
            'files': report['files'], 'scope': report['scope'], 'migration_quality_status': 'not_run',
            'actual_model_calls': 0, 'langsmith_uploaded': False, 'production_ready': False}
