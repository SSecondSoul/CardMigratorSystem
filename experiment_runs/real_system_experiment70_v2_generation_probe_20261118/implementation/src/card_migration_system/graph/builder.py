"""Real LangGraph, explicit conditional edges; model/evaluation are labelled fixtures."""
from typing import TypedDict
from langgraph.graph import END, START, StateGraph


class State(TypedDict, total=False):
    run_id: str
    request_sha256: str
    current: str
    candidate: str
    round: int
    assertions: dict[str, bool]
    candidate_assertions: dict[str, bool]
    decision: str
    stop_reason: str


def build_graph(service, run_id, owner, checkpointer, *, interrupt_after=None):
    run = service.run(run_id)

    def prepare(state):
        service.verify_binding(run_id)
        if state["run_id"] != run_id or state["request_sha256"] != run["request_sha256"]:
            raise ValueError("checkpoint_binding_mismatch")
        return {}

    def generate(_):
        result = service.generate_stub(run_id, owner, 0)
        return {"current": result["revision_id"], "round": 0}

    def evaluate(state):
        return {"assertions": service.evaluate_fixture(run_id, owner, state["current"])}

    def route(state):
        if all(state["assertions"].values()):
            return "report"
        return "repair" if state["round"] < run["request"]["max_repair_rounds"] else "report"

    def repair(state):
        number = state["round"] + 1
        result = service.generate_stub(run_id, owner, number, state["current"])
        return {"candidate": result["revision_id"], "round": number}

    def recheck(state):
        return {"candidate_assertions": service.evaluate_fixture(run_id, owner, state["candidate"])}

    def gate(state):
        decision = service.candidate(run_id, owner, state["current"], state["candidate"],
                                     state["assertions"], state["candidate_assertions"])
        if decision == "reject":
            return {"decision": "reject", "stop_reason": "fixture_candidate_regression_rolled_back"}
        return {"decision": "accept", "current": state["candidate"],
                "assertions": state["candidate_assertions"]}

    def after_gate(state):
        return "report" if state["decision"] == "reject" else route(state)

    def report(state):
        reason = state.get("stop_reason") or ("fixture_assertions_satisfied" if all(state["assertions"].values())
                                              else "fixture_repair_budget_exhausted")
        service.finish(run_id, owner, state["current"], reason)
        return {"stop_reason": reason}

    graph = StateGraph(State)
    for name, node in (("prepare", prepare), ("generate", generate), ("evaluate_fixture", evaluate),
                       ("repair_stub", repair), ("recheck_fixture", recheck), ("candidate_gate", gate),
                       ("report", report)):
        graph.add_node(name, node)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "generate")
    graph.add_edge("generate", "evaluate_fixture")
    graph.add_conditional_edges("evaluate_fixture", route, {"repair": "repair_stub", "report": "report"})
    graph.add_edge("repair_stub", "recheck_fixture")
    graph.add_edge("recheck_fixture", "candidate_gate")
    graph.add_conditional_edges("candidate_gate", after_gate, {"repair": "repair_stub", "report": "report"})
    graph.add_edge("report", END)
    return graph.compile(checkpointer=checkpointer, interrupt_after=interrupt_after)
