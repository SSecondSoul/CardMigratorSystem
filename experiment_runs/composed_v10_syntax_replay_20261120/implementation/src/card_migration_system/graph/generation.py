"""Durable offline generation graph. Explicit injected test client only."""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver
from langsmith import tracing_context

from ..adapters.generation import OfflineGenerationClient
from ..application.generations import GenerationService, require
from ..application.service import ServiceError
from ..persistence.runtime_lock import execution_guard
from .extraction import error_code


class GenerationState(TypedDict, total=False):
    generation_id: str
    request_sha256: str
    outcome: str


def build_generation_graph(ledger, key, client, saver, *, interrupt_after=None):
    request_hash = ledger.report(key)['request_sha256']

    def prepare(state):
        require(state.get('generation_id') == key and state.get('request_sha256') == request_hash,
                'generation_checkpoint_binding_mismatch')
        ledger.verify_binding(key)
        return {}

    def generate(_):
        return {'outcome': ledger.invoke(key, client)['status']}

    def register(_):
        return {'outcome': ledger.finish(key)}

    graph = StateGraph(GenerationState)
    graph.add_node('prepare_generation', prepare)
    graph.add_node('invoke_offline_client', generate)
    graph.add_node('register_candidate', register)
    graph.add_edge(START, 'prepare_generation')
    graph.add_edge('prepare_generation', 'invoke_offline_client')
    graph.add_edge('invoke_offline_client', 'register_candidate')
    graph.add_edge('register_candidate', END)
    return graph.compile(checkpointer=saver, interrupt_after=interrupt_after)


def execute_generation(service, *, client, generation_id=None, extraction_id=None,
                       idempotency_key=None, interrupt_after=None, **model_options):
    require(isinstance(client, OfflineGenerationClient), 'generation_offline_client_required')
    ledger = GenerationService(service)
    with execution_guard(service.settings.runtime_dir):
        if generation_id is None:
            key = ledger.create(extraction_id, idempotency_key, **model_options)
        else:
            require(extraction_id is None and idempotency_key is None and not model_options,
                    'generation_resume_input_not_allowed')
            key = generation_id
        try:
            result = ledger.verify_binding(key)
            if result['status'] in ('completed', 'blocked'):
                return summary(result)
            # Known registered receipts may finish without a second call. Unknown
            # started attempts never become prepared again, even on graph replay.
            if result['attempt'] is not None and result['receipt'] is None:
                raise ServiceError('generation_unresolved_attempt_requires_review')
            config = {'configurable': {'thread_id': 'generation:' + key}, 'recursion_limit': 10, 'callbacks': []}
            with tracing_context(enabled=False):
                with SqliteSaver.from_conn_string(str(service.settings.graph_database)) as saver:
                    graph = build_generation_graph(ledger, key, client, saver, interrupt_after=interrupt_after)
                    state = graph.get_state(config)
                    if state.values:
                        require(state.values.get('generation_id') == key and state.values.get('request_sha256') == result['request_sha256'],
                                'generation_checkpoint_binding_mismatch')
                        require(bool(state.next), 'generation_terminal_checkpoint_requires_review')
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
    return {name: result[name] for name in ('generation_id', 'status', 'request_sha256', 'stop_reason',
        'files', 'candidate', 'actual_model_calls', 'offline_client_invocations', 'client_outcome',
        'scope', 'migration_quality_status', 'langsmith_uploaded', 'production_ready')}
