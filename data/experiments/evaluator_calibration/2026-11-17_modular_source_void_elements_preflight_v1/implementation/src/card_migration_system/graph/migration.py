"""The real migration graph: explicit evaluation, diagnosis, repair and candidate gate."""
from typing import TypedDict
from langgraph.graph import StateGraph,START,END
from langgraph.checkpoint.sqlite import SqliteSaver
from langsmith import tracing_context

from ..application.service import ServiceError
from ..observability.traces import Tracer


class MigrationState(TypedDict,total=False):
    migration_id:str
    request_sha256:str
    current:dict
    candidate:dict
    evaluation:dict
    candidate_evaluation:dict
    round:int
    stop_reason:str
    decisions:list


def build_migration_graph(service,key,saver,tracer,*,interrupt_after=None):
    job=service.job(key)
    def node(name,action):
        def execute(state):
            service.guard(key)
            if state['migration_id']!=key or state['request_sha256']!=job.request_sha256:raise ServiceError('migration_checkpoint_mismatch')
            service.update(key,stage=name)
            result=tracer.stage(name,job.request_sha256,lambda:action(state))
            service.update(key,state={**state,**result})
            return result
        return execute
    def generate(state):return {'current':service.generate(key),'round':0,'decisions':[]}
    def evaluate(state):return {'evaluation':service.evaluate(key,state['current'])}
    def diagnose(state):
        current=state['evaluation']
        if current['source_blocked']:reason='source_baseline_blocked'
        elif current['passed']:reason='passed_configured_checks'
        elif state['round']>=job.request['max_repair_rounds']:reason='repair_budget_exhausted'
        else:reason='repair'
        return {'stop_reason':reason}
    def repair(state):
        number=state['round']+1
        return {'candidate':service.repair(key,state['current'],state['evaluation'],number),'round':number}
    def retest(state):return {'candidate_evaluation':service.evaluate(key,state['candidate'])}
    def gate(state):
        decision=service.decide(key,state['current'],state['candidate'],state['evaluation'],state['candidate_evaluation'])
        result={'decisions':[*state['decisions'],decision]}
        if decision['accepted']:result.update(current=state['candidate'],evaluation=state['candidate_evaluation'])
        return result
    def report(state):
        result={'stop_reason':state['stop_reason']}
        status='finished' if state['evaluation']['passed'] else ('blocked' if state['evaluation']['source_blocked'] else 'failed')
        # Metadata-only trace export cannot alter the migration verdict or retry a model call.
        trace=service.cached(key,'trace.json') or tracer.finish({'status':status,'stop_reason':state['stop_reason']})
        service.put_json(key,'trace.json','trace',trace)
        service.update(key,status=status,stage='report',stop_reason=state['stop_reason'],state={**state,**result})
        if not service.cached(key,'report.json'):
            service.put_json(key,'report.json','report',service.report(key))
        return result
    graph=StateGraph(MigrationState)
    for name,action in [('preflight',lambda _: service.preflight(key)),('extract_ssm',lambda _: (service.extract(key) and {})),
        ('generate',generate),('evaluate',evaluate),('diagnose',diagnose),('repair',repair),
        ('candidate_retest',retest),('candidate_gate',gate)]:graph.add_node(name,node(name,action))
    graph.add_node('report',report)
    graph.add_edge(START,'preflight');graph.add_edge('preflight','extract_ssm');graph.add_edge('extract_ssm','generate')
    graph.add_edge('generate','evaluate');graph.add_edge('evaluate','diagnose')
    graph.add_conditional_edges('diagnose',lambda state:'repair' if state['stop_reason']=='repair' else 'report',{'repair':'repair','report':'report'})
    graph.add_edge('repair','candidate_retest');graph.add_edge('candidate_retest','candidate_gate')
    graph.add_edge('candidate_gate','diagnose');graph.add_edge('report',END)
    return graph.compile(checkpointer=saver,interrupt_after=interrupt_after)


def execute_migration(service,key,*,interrupt_after=None):
    row=service.guard(key)
    if row.status not in ('queued','running','review_required'):return service.report(key)
    tracer=Tracer(row.request['runtime'],key)
    service.tracer=tracer
    config={'configurable':{'thread_id':'migration:'+key},'recursion_limit':50,'callbacks':[]}
    service.update(key,status='running')
    try:
        # Disable ambient automatic tracing; the explicit summary-only exporter above owns disclosure.
        with tracing_context(enabled=False),SqliteSaver.from_conn_string(str(service.settings.graph_database)) as saver:
            graph=build_migration_graph(service,key,saver,tracer,interrupt_after=interrupt_after)
            checkpoint=graph.get_state(config)
            if checkpoint.values:
                if checkpoint.values.get('request_sha256')!=row.request_sha256:raise ServiceError('migration_checkpoint_mismatch')
                if checkpoint.next:graph.invoke(None,config,durability='sync')
                elif service.job(key).status=='running':raise ServiceError('migration_terminal_checkpoint_requires_review')
            else:graph.invoke({'migration_id':key,'request_sha256':row.request_sha256},config,durability='sync')
            if graph.get_state(config).next:service.update(key,status='review_required',stop_reason='controlled_graph_interrupt')
    except Exception as error:
        code=error.code if isinstance(error,ServiceError) else type(error).__name__
        status='cancelled' if code=='migration_cancel_requested' else ('review_required' if 'unknown' in code else 'blocked')
        service.update(key,status=status,stop_reason=code)
        service.put_json(key,'failure-'+__import__('uuid').uuid4().hex+'.json','failure',{'error_code':code,'trace':tracer.finish({'status':status,'error_code':code})})
    return service.report(key)
