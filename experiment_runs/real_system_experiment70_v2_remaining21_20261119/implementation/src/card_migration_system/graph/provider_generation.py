"""Separate recorded-transport graph, offline execution only; no ambient tracing."""
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from ..application.provider_generations import ProviderGenerationService, RecordedOfflineTransport
from ..application.generations import require
from ..application.service import ServiceError
from ..persistence.runtime_lock import execution_guard
from .extraction import error_code


class RecordedState(TypedDict, total=False):
    generation_id: str
    request_sha256: str
    outcome: str


def build_recorded_graph(ledger, key, transport, saver, *, interrupt_after=None):
    request_hash = ledger.report(key)['request_sha256']

    def prepare(state):
        require(state.get('generation_id') == key and state.get('request_sha256') == request_hash, 'provider_checkpoint_binding_mismatch')
        ledger.verify_binding(key)
        return {}

    def exchange(_):
        ledger._invoke_locked(key, transport)
        return {}

    def register(_):
        return {'outcome': ledger._finish_locked(key)}

    graph = StateGraph(RecordedState)
    for name, node in (('prepare_transport', prepare), ('record_exchange', exchange), ('register_result', register)):
        graph.add_node(name, node)
    graph.add_edge(START, 'prepare_transport')
    graph.add_edge('prepare_transport', 'record_exchange')
    graph.add_edge('record_exchange', 'register_result')
    graph.add_edge('register_result', END)
    return graph.compile(checkpointer=saver, interrupt_after=interrupt_after)


def execute_recorded_generation(service, *, generation_id, transport, interrupt_after=None):
    require(isinstance(transport, RecordedOfflineTransport), 'provider_offline_transport_required')
    ledger, key = ProviderGenerationService(service), generation_id
    with execution_guard(service.settings.runtime_dir):
        try:
            result = ledger.verify_binding(key)
            if result['status'] in ('completed', 'blocked'):
                return summary(result)
            if result['attempt'] is not None and result['receipt'] is None:
                raise ServiceError('provider_unresolved_attempt_requires_review')
            config = {'configurable': {'thread_id': 'provider-generation:' + key}, 'callbacks': [], 'recursion_limit': 10}
            with tracing_context(enabled=False):
                with SqliteSaver.from_conn_string(str(service.settings.graph_database)) as saver:
                    graph = build_recorded_graph(ledger, key, transport, saver, interrupt_after=interrupt_after)
                    state = graph.get_state(config)
                    if state.values:
                        require(state.values.get('generation_id') == key and state.values.get('request_sha256') == result['request_sha256'],
                            'provider_checkpoint_binding_mismatch')
                        # A terminal review with a known receipt remains review; no dispatch.
                        if not state.next and result['receipt'] is not None:
                            return summary(result)
                        require(bool(state.next), 'provider_terminal_checkpoint_requires_review')
                        graph.invoke(None, config, durability='sync')
                    else:
                        graph.invoke({'generation_id': key, 'request_sha256': result['request_sha256']}, config, durability='sync')
                    pending = bool(graph.get_state(config).next)
            return {**summary(ledger.report(key)), 'graph_pending': pending}
        except Exception as error:
            code = error_code(error)
            try:
                ledger.review(key, code)
            except ServiceError as review_error:
                if review_error.code != 'not_found':
                    raise
            raise ServiceError(code) from None


def summary(result):
    return {name: result[name] for name in ('id', 'status', 'request_sha256', 'stop_reason', 'files', 'usage',
        'actual_model_calls', 'transport_invocations', 'slots_reserved', 'contract_revision', 'scope',
        'migration_quality_status', 'langsmith_uploaded', 'production_ready')}
