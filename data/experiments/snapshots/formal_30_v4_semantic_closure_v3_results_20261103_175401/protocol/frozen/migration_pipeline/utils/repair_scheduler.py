"""Opt-in repair scheduling: bounded normalization, explicit LLM budget, rollback.

Legacy batches retain their mixed-attempt policy. This policy defines the cap as
LLM repair calls; deterministic operations are bounded and reported separately.
"""

from collections import Counter
from copy import deepcopy
from pathlib import Path

from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.utils.repair_regression_guard import assess_event_contract_regression


MAX_NORMALIZATION_STEPS_PER_CALL = 4

# Deliberately enumerated: unknown diagnostics and warnings do not acquire
# rollback semantics merely because their total count changed. Compare findings
# rather than total error counts, so a new defect cannot hide behind other fixes.
SEMANTIC_REGRESSION_CODES = frozenset({
    "hidden_template_reactive_dependency", "invalid_san_computed_instance_method_call",
    "lifecycle_behavior_not_landed", "missing_data_types", "missing_prop_defaults",
    "invalid_san_textarea_binding",
    "source_watch_persistence_not_landed",
    "source_mounted_order_not_landed",
})


def _semantic_findings(state):
    return Counter((issue["code"], issue.get("location", ""), issue.get("message", ""))
                   for issue in state.get("validation_errors", [])
                   if issue.get("code") in SEMANTIC_REGRESSION_CODES)


def _evaluate(orchestrator, state):
    state.update(orchestrator.validate_stage.run_from_state(state))
    state.update(orchestrator.visual_eval_stage.run_from_state(state))


def candidate_gate(before, after):
    vue_source = before.get("vue_source") or ""
    source_path = Path(before.get("vue_file_path") or "")
    if not vue_source and source_path.is_file():
        vue_source = source_path.read_text(encoding="utf-8")
    gate = assess_event_contract_regression(
        ssm=before.get("ssm") or {}, before_code=before["generated_code"],
        after_code=after["generated_code"],
        before_errors=before.get("validation_errors", []), after_errors=after.get("validation_errors", []),
        vue_source=vue_source,
    )
    before_codes = Counter(x["code"] for x in before.get("validation_errors", []))
    after_codes = Counter(x["code"] for x in after.get("validation_errors", []))
    critical = {"reserved_init_data_method_collision", "san_script_compile_error", "san_template_compile_error"}
    introduced = sorted(code for code in critical if after_codes[code] > before_codes[code])
    visual_regression = bool(before.get("visual_eval_passed") and not after.get("visual_eval_passed"))
    semantic = _semantic_findings(after) - _semantic_findings(before)
    gate["introduced_semantic_findings"] = [
        {"code": code, "location": location, "message": message, "count": count}
        for (code, location, message), count in sorted(semantic.items())
    ]
    gate["introduced_critical_errors"] = introduced
    gate["lost_visual_pass"] = visual_regression
    gate["should_stop"] = gate["should_stop"] or bool(introduced) or visual_regression or bool(semantic)
    if introduced or visual_regression or semantic:
        gate["decision"] = "reject"
    return gate


def _restore(state, before, *, history, normalizations, calls, gate, rejected_file):
    state.clear()
    state.update(before)
    state.update({
        "repair_history": history, "normalization_history": normalizations,
        "repair_rounds": calls, "repair_attempt": calls, "llm_repair_calls": calls,
        "deterministic_steps": len(normalizations), "repair_regression_gate": gate,
        "repair_regression_rejected": True, "retained_previous_candidate": True,
        "rejected_candidate_file": rejected_file,
    })


def run_bounded_repair_loop(orchestrator, state, max_calls):
    state.update({
        "repair_policy": "bounded_prepass_v1", "repair_budget_unit": "llm_calls",
        "llm_repair_calls": 0, "deterministic_steps": 0, "normalization_history": [],
        "normalization_stop_reasons": [], "retained_previous_candidate": False,
        "semantic_rule_set": state.get("generation_metadata", {}).get("semantic_rule_set", "bounded_v1"),
    })
    calls = 0
    while calls < max_calls and not orchestrator._stage_passed(state):
        seen = {orchestrator._build_progress_signature(state)["generated_code_sha256"]}
        for step in range(MAX_NORMALIZATION_STEPS_PER_CALL):
            before = deepcopy(state)
            code, repairs = RepairStage._deterministic_repair_plan(
                state["generated_code"], state.get("validation_errors", []),
                state.get("visual_eval_errors", []), state.get("ssm"), state.get("vue_file_path", ""),
                **({"enable_residual_v2": True} if state["semantic_rule_set"] == "residual_v2" else {}),
            )
            if code == state["generated_code"]:
                state["normalization_stop_reasons"].append("fixed_point")
                break
            trial = {**state, "generated_code": code}
            signature = orchestrator._build_progress_signature(trial)["generated_code_sha256"]
            if signature in seen:
                state["normalization_stop_reasons"].append("cycle_detected")
                break
            number = len(state["normalization_history"]) + 1
            source = Path(state["generated_file_path"])
            output = str(source.with_name(f"{source.stem}_normalized_{number}{source.suffix}"))
            orchestrator.repair_stage._ensure_repaired_file(output, code)
            state.update({"generated_code": code, "generated_file_path": output})
            _evaluate(orchestrator, state)
            gate = candidate_gate(before, state)
            entry = {
                "step": number, "before_llm_call": calls + 1,
                "normalizations": [name for _, name in repairs], "candidate_file": output,
                "accepted": not gate["should_stop"], "gate": gate,
                "progress_signature": orchestrator._build_progress_signature(state),
            }
            state["normalization_history"].append(entry)
            state["deterministic_steps"] = len(state["normalization_history"])
            if gate["should_stop"]:
                # Keep the evidence but let LLM address the original candidate.
                log = state["normalization_history"]
                state.clear()
                state.update(before)
                state["normalization_history"] = log
                state["deterministic_steps"] = len(log)
                state["normalization_stop_reasons"].append("candidate_rejected")
                break
            seen.add(signature)
            if orchestrator._stage_passed(state):
                break
        else:
            state["normalization_stop_reasons"].append("step_cap_reached")
        if orchestrator._stage_passed(state):
            break

        before = deepcopy(state)
        calls += 1
        state["repair_metadata"] = {**state.get("repair_metadata", {}), "skip_deterministic_prepass": True,
                                    "semantic_rule_set": state["semantic_rule_set"]}
        state["repair_attempt"] = calls - 1
        update = orchestrator.repair_stage.run_from_state(state)
        if update.get("repair_provider") == "deterministic":
            raise RuntimeError("LLM-only phase unexpectedly returned deterministic output")
        state.update(update)
        state.update({"repair_rounds": calls, "llm_repair_calls": calls})
        _evaluate(orchestrator, state)
        gate = candidate_gate(before, state)
        state["repair_regression_gate"] = gate
        state["repair_regression_rejected"] = gate["should_stop"]
        state["repaired_validate_result"] = state["validate_result"]
        state["repaired_visual_eval_result"] = state["visual_eval_result"]
        signature = orchestrator._build_progress_signature(state)
        state["no_repair_progress"] = signature == orchestrator._build_progress_signature(before)
        state["progress_signature"] = signature
        state["repair_history"].append(orchestrator._build_repair_history_entry(state))
        if gate["should_stop"]:
            _restore(state, before, history=state["repair_history"],
                     normalizations=state["normalization_history"], calls=calls,
                     gate=gate, rejected_file=state["generated_file_path"])
            break
        if state["no_repair_progress"]:
            break
    orchestrator._finalize_state(state, max_calls)
    if state.get("retained_previous_candidate"):
        state["stop_reason"] = "repair_candidate_regression_rolled_back"
