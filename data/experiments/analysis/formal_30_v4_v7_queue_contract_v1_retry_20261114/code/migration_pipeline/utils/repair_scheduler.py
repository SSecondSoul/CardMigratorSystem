"""Opt-in repair scheduling: bounded normalization, explicit LLM budget, rollback.

Legacy batches retain their mixed-attempt policy. This policy defines the cap as
LLM repair calls; deterministic operations are bounded and reported separately.
"""

from collections import Counter
from copy import deepcopy
from pathlib import Path

from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.utils.repair_regression_guard import assess_event_contract_regression
from migration_pipeline.utils.semantic_coverage import latent_semantic_findings
from migration_pipeline.utils.source_dom_semantics import source_dom_semantics
from migration_pipeline.utils.source_payload_semantics import source_payload_semantics
from migration_pipeline.utils.source_render_call_semantics import source_render_call_semantics
from migration_pipeline.utils.source_render_dependency_semantics import source_render_dependency_semantics
from migration_pipeline.utils.source_array_transaction_semantics import source_array_transaction_semantics
from migration_pipeline.utils.source_child_initialization_semantics import source_child_initialization_semantics
from migration_pipeline.utils.source_native_drag_semantics import source_native_drag_semantics
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.class_binding_semantics import class_binding_regression
from migration_pipeline.utils.class_binding_contract import CLASS_BINDING_CODES


MAX_NORMALIZATION_STEPS_PER_CALL = 4
PARENT_WATCH_REVIEW_CODES = frozenset({
    'source_parent_watch_exception_policy_unproven', 'source_parent_watch_dynamic_key_unproven',
})

# Deliberately enumerated: unknown diagnostics and warnings do not acquire
# rollback semantics merely because their total count changed. Compare findings
# rather than total error counts, so a new defect cannot hide behind other fixes.
SEMANTIC_REGRESSION_CODES = frozenset({
    *CLASS_BINDING_CODES,
    "hidden_template_reactive_dependency", "invalid_san_computed_instance_method_call",
    "invalid_san_inline_computed_method_invocation",
    "source_dom_event_not_landed", "source_dom_loop_not_landed", "source_dom_analysis_unavailable",
    "source_event_payload_not_landed", "source_event_payload_analysis_unavailable",
    "source_render_call_not_landed", "source_render_call_analysis_unavailable",
    "source_render_dependency_not_landed", "source_render_dependency_analysis_unavailable",
    "source_array_transaction_not_landed", "source_array_transaction_analysis_unavailable",
    "source_child_factory_not_landed", "source_child_watch_not_landed", "source_child_initialization_analysis_unavailable",
    "source_native_drag_not_landed", "source_native_drag_analysis_unavailable",
    "source_parent_watch_not_landed", "source_parent_watch_analysis_unavailable",
    *PARENT_WATCH_REVIEW_CODES,
    "lifecycle_behavior_not_landed", "missing_data_types", "missing_prop_defaults",
    "invalid_san_textarea_binding",
    "invalid_san_template_data_store_access",
    "template_binding_analysis_unavailable",
    "source_class_binding_not_landed",
    "source_watch_persistence_not_landed",
    "source_watch_persistence_unproven",
    "source_mounted_order_not_landed",
    "source_startup_phase_not_landed",
    "source_method_interface_not_landed", "source_method_trigger_added",
})


def _semantic_findings(state):
    identities = []
    for issue in state.get("validation_errors", []):
        if issue.get("code") not in SEMANTIC_REGRESSION_CODES:
            continue
        details = issue.get("details") or {}
        fields = details.get("affected_fields") if isinstance(details, dict) else None
        if (issue["code"] == "missing_prop_defaults"
                and isinstance(details, dict)
                and details.get("contract") == "prop_defaults_v1"
                and isinstance(fields, list) and fields
                and all(isinstance(name, str) and name for name in fields)):
            identities.extend((issue["code"], issue.get("location", ""), f"prop.default:{name}")
                              for name in sorted(set(fields)))
        elif (issue["code"] == "invalid_san_inline_computed_method_invocation"
                and isinstance(details, dict) and details.get("contract") == "inline_computed_calls_v1"
                and isinstance(details.get("affected_methods"), list) and details["affected_methods"]
                and all(isinstance(name, str) and name for name in details["affected_methods"])):
            identities.extend((issue["code"], issue.get("location", ""), f"computed.call:{name}")
                              for name in sorted(set(details["affected_methods"])))
        else:
            # Legacy/unstructured diagnostics remain fail-closed; never parse
            # localized prose or waive every finding sharing an error code.
            identities.append((issue["code"], issue.get("location", ""), issue.get("message", "")))
    return Counter(identities)


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
    before_dom = source_dom_semantics(before['generated_code'], vue_source, before.get('ssm')) if vue_source else {}
    after_dom = source_dom_semantics(after['generated_code'], vue_source, before.get('ssm')) if vue_source else {}
    lost_dom_scopes = sorted(set(before_dom.get('mapped_scopes', [])) - set(after_dom.get('mapped_scopes', [])))
    lost_dom_nodes = sorted(set(before_dom.get('mapped_nodes', [])) - set(after_dom.get('mapped_nodes', [])))
    gate['lost_source_dom_scopes'] = lost_dom_scopes
    gate['lost_source_dom_nodes'] = lost_dom_nodes
    before_payload = source_payload_semantics(before['generated_code'], vue_source, before.get('ssm'))
    after_payload = source_payload_semantics(after['generated_code'], vue_source, before.get('ssm'))
    lost_payload = sorted(set(before_payload['mapped_contracts']) - set(after_payload['mapped_contracts']))
    gate['lost_source_payload_contracts'] = lost_payload
    before_render = source_render_call_semantics(before['generated_code'], vue_source, before.get('ssm'))
    after_render = source_render_call_semantics(after['generated_code'], vue_source, before.get('ssm'))
    lost_render = sorted(set(before_render['mapped_bindings']) - set(after_render['mapped_bindings']))
    gate['lost_source_render_bindings'] = lost_render
    before_deps = source_render_dependency_semantics(before['generated_code'], vue_source)
    after_deps = source_render_dependency_semantics(after['generated_code'], vue_source)
    lost_deps = sorted(set(before_deps['mapped_bindings']) - set(after_deps['mapped_bindings']))
    gate['lost_source_dependency_bindings'] = lost_deps
    before_array = source_array_transaction_semantics(before['generated_code'], vue_source)
    after_array = source_array_transaction_semantics(after['generated_code'], vue_source)
    lost_array = sorted(set(before_array['mapped_contracts']) - set(after_array['mapped_contracts']))
    gate['lost_source_array_contracts'] = lost_array
    before_child = source_child_initialization_semantics(before['generated_code'], vue_source)
    after_child = source_child_initialization_semantics(after['generated_code'], vue_source)
    lost_child = sorted(set(before_child['mapped_contracts']) - set(after_child['mapped_contracts']))
    gate['lost_source_child_startup_contracts'] = lost_child
    before_drag = source_native_drag_semantics(before['generated_code'], vue_source)
    after_drag = source_native_drag_semantics(after['generated_code'], vue_source)
    lost_drag = sorted(set(before_drag['mapped_contracts']) - set(after_drag['mapped_contracts']))
    gate['lost_source_native_drag_contracts'] = lost_drag
    before_watch = source_parent_watch_semantics(before['generated_code'], vue_source)
    after_watch = source_parent_watch_semantics(after['generated_code'], vue_source)
    lost_watch = sorted(set(before_watch['mapped_contracts']) - set(after_watch['mapped_contracts']))
    gate['lost_source_parent_watch_contracts'] = lost_watch
    reported = {(e.get('code'),e.get('location')) for e in after.get('validation_errors', [])}
    waived_watch = [b for b in after_watch['blocked_boundaries'] if (b['code'],b['location']) not in reported]
    gate['waived_source_parent_watch_boundaries'] = waived_watch
    class_gate = class_binding_regression(before['generated_code'], after['generated_code'],
                                          vue_source, after.get('validation_errors', []))
    gate.update({k: v for k, v in class_gate.items() if k not in {'decision', 'should_stop'}})
    before_codes = Counter(x["code"] for x in before.get("validation_errors", []))
    after_codes = Counter(x["code"] for x in after.get("validation_errors", []))
    critical = {"reserved_init_data_method_collision", "san_script_compile_error", "san_template_compile_error"}
    introduced = sorted(code for code in critical if after_codes[code] > before_codes[code])
    visual_regression = bool(before.get("visual_eval_passed") and not after.get("visual_eval_passed"))
    semantic = _semantic_findings(after) - _semantic_findings(before)
    latent, coverage = latent_semantic_findings(before, after, semantic, vue_source=vue_source)
    semantic -= latent
    gate['semantic_coverage_assessment'] = coverage
    gate['newly_visible_preexisting_semantic_findings'] = [
        {'code': code, 'location': location, 'message': message, 'count': count}
        for (code, location, message), count in sorted(latent.items())
    ]
    gate["introduced_semantic_findings"] = [
        {"code": code, "location": location, "message": message, "count": count}
        for (code, location, message), count in sorted(semantic.items())
    ]
    gate["introduced_critical_errors"] = introduced
    gate["lost_visual_pass"] = visual_regression
    gate["should_stop"] = gate["should_stop"] or bool(introduced) or visual_regression or bool(semantic) or bool(lost_dom_scopes) or bool(lost_dom_nodes) or bool(lost_payload) or bool(lost_render) or bool(lost_deps) or bool(lost_array) or bool(lost_child) or bool(lost_drag) or bool(lost_watch) or bool(waived_watch)
    if class_gate['should_stop']:
        gate['should_stop'] = True
    if introduced or visual_regression or semantic or lost_dom_scopes or lost_dom_nodes or lost_payload or lost_render or lost_deps or lost_array or lost_child or lost_drag or lost_watch or waived_watch or class_gate['should_stop']:
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

        boundary_review = sorted({e.get('code') for e in state.get('validation_errors', [])} & PARENT_WATCH_REVIEW_CODES)
        if boundary_review:
            state['source_parent_watch_review_required'] = True
            state['source_parent_watch_review_codes'] = boundary_review
            state['normalization_stop_reasons'].append('source_parent_watch_scope_requires_review')
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
    elif state.get('source_parent_watch_review_required'):
        state['stop_reason'] = 'source_parent_watch_scope_requires_review'
