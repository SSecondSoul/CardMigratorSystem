"""Strict not-run P1 projection plus a separately validated development fixture ledger.

P1 has no development_stub origin/evidence type. Never relabel those records as
generation/model/rule migration evidence just to satisfy the P1 dataclasses.
"""
import re

from .identity import digest
from .request_snapshot import DIMENSIONS, validate_snapshot


class ReportError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise ReportError(code)


def assertions(value):
    require(type(value) is dict and set(value) == {"preserved", "requested"}
            and all(type(item) is bool for item in value.values()), "report_invalid_fixture_assertions")
    return value


def validate_ledger(snapshot, storage):
    """Validate one transaction snapshot, without rewriting records or running components."""
    run, source = snapshot["run"], snapshot["source"]
    request, run_id = run["request"], run["id"]
    require(run["request_sha256"] == digest(request), "report_request_hash_mismatch")
    require(request.get("mode") == "development_stub" and run["outcome"] == "not_run",
            "report_unexpected_development_outcome")
    require(set(request) <= {"profile", "max_repair_rounds", "input_sha256", "mode", "contract_snapshot"},
            "report_unknown_request_fields")
    require(request.get("profile") in ("success", "repairable", "regression", "always_fail"),
            "report_unknown_development_profile")
    rounds = request.get("max_repair_rounds")
    require(type(rounds) is int and 0 <= rounds <= 3, "report_invalid_fixture_budget")
    require(source["sha256"] == request.get("input_sha256"), "report_source_identity_mismatch")
    storage.read(source["relative_path"], source["sha256"])
    require(run["status"] in ("queued", "running", "review_required", "finished", "cancelled", "execution_error"),
            "report_unknown_execution_status")
    revisions = {row["id"]: row for row in snapshot["revisions"]}
    require(len(revisions) == len(snapshot["revisions"]), "report_duplicate_revision")
    for row in (*snapshot["revisions"], *snapshot["attempts"], *snapshot["evaluations"], *snapshot["decisions"]):
        require(row["run_id"] == run_id, "report_cross_run_reference")
    # Parent-first ordering is computed, not inferred from a filename's lexical order.
    remaining, ordered = dict(revisions), []
    while remaining:
        ready = sorted(key for key, row in remaining.items()
                       if row["parent_id"] is None or row["parent_id"] in {item["id"] for item in ordered})
        require(bool(ready), "report_missing_parent_or_cycle")
        for key in ready:
            ordered.append(remaining.pop(key))
    by_round = {}
    for row in snapshot["attempts"]:
        require(row["kind"] == "development_stub" and row["model_tokens"] is None,
                "report_unsupported_attempt_kind_or_usage")
        match = re.fullmatch(re.escape(run_id) + r":stub:([0-3])", row["id"])
        require(match is not None, "report_invalid_attempt_id")
        number = int(match.group(1))
        require(number not in by_round and number <= rounds, "report_attempt_budget_or_identity_mismatch")
        by_round[number] = row
        require(row["status"] in ("started", "completed"), "report_unknown_attempt_status")
        parent = None if number == 0 else f"{run_id}_{number - 1}"
        # The current fixture protocol stops on rejection; completed candidates form a linear attempt chain.
        require(row["request_sha256"] == digest({"run_request": run["request_sha256"],
                                                "round": number, "parent": parent}),
                "report_attempt_request_mismatch")
        if row["status"] == "started":
            require(row["result"] is None and f"{run_id}_{number}" not in revisions,
                    "report_unresolved_attempt_has_result")
            continue
        result = row["result"]
        require(type(result) is dict and set(result) == {"revision_id", "assertions"}, "report_invalid_receipt")
        require(type(result["revision_id"]) is str, "report_invalid_receipt_revision_id")
        revision = revisions.get(result["revision_id"])
        require(revision is not None and revision["id"] == f"{run_id}_{number}", "report_receipt_revision_mismatch")
        require(revision["parent_id"] == parent, "report_receipt_parent_mismatch")
        require(revision["source_kind"] == "development_stub", "report_unsupported_revision_origin")
        require(revision["relative_path"] == f"runs/{run_id}/{revision['id']}.san", "report_revision_path_mismatch")
        expected = {"preserved": not (request["profile"] == "regression" and number > 0),
                    "requested": request["profile"] == "success" or
                    (request["profile"] in ("repairable", "regression") and number > 0)}
        require(assertions(result["assertions"]) == assertions(revision["fixture_assertions"]) == expected,
                "report_receipt_assertion_mismatch")
        storage.read(revision["relative_path"], revision["sha256"])
    require(sorted(by_round) == list(range(len(by_round))), "report_noncontiguous_attempts")
    completed = [row for row in by_round.values() if row["status"] == "completed"]
    require({row["result"]["revision_id"] for row in completed} == set(revisions), "report_unowned_revision")
    require(all(by_round[number]["status"] == "completed" for number in range(max(by_round, default=0))),
            "report_attempt_after_unresolved_attempt")
    evaluations = {}
    for row in snapshot["evaluations"]:
        revision = revisions.get(row["revision_id"])
        require(revision is not None, "report_evaluation_unknown_revision")
        require(row["id"] == f"{revision['id']}:fixture" and row["id"] not in evaluations,
                "report_evaluation_identity_mismatch")
        require(row["status"] == "not_run" and row["scope"] == "development_control_fixture_only",
                "report_fixture_cannot_be_quality_evidence")
        require(assertions(row["fixture_assertions"]) == revision["fixture_assertions"],
                "report_evaluation_assertion_mismatch")
        evaluations[row["id"]] = row
    accepted = f"{run_id}_0" if revisions else None
    rejected, seen_decisions, comparisons = False, set(), []
    for row in sorted(snapshot["decisions"], key=lambda item: item["candidate_id"]):
        require(not rejected, "report_decision_after_rejection")
        require(row["id"] not in seen_decisions, "report_duplicate_decision")
        seen_decisions.add(row["id"])
        previous, candidate = revisions.get(row["previous_id"]), revisions.get(row["candidate_id"])
        require(previous is not None and candidate is not None and previous != candidate,
                "report_decision_unknown_or_same_revision")
        require(row["id"] == f"{candidate['id']}:gate" and previous["id"] == accepted
                and candidate["parent_id"] == previous["id"], "report_decision_chain_mismatch")
        before_id, after_id = f"{previous['id']}:fixture", f"{candidate['id']}:fixture"
        require(before_id in evaluations and after_id in evaluations, "report_decision_missing_evaluations")
        before, after = evaluations[before_id]["fixture_assertions"], evaluations[after_id]["fixture_assertions"]
        action = "reject" if any(value and not after[key] for key, value in before.items()) else "accept"
        require(row["action"] == action and row["reason"] ==
                ("fixture_regression" if action == "reject" else "fixture_no_regression"),
                "report_candidate_policy_mismatch")
        comparisons.append({"decision_id": row["id"], "previous_revision_id": previous["id"],
                            "candidate_revision_id": candidate["id"], "action": action,
                            "before_evaluation_ids": [before_id], "after_evaluation_ids": [after_id],
                            "rollback_revision_id": previous["id"] if action == "reject" else None})
        if action == "reject":
            rejected = True
        else:
            accepted = candidate["id"]
    if run["status"] == "finished":
        require(accepted is not None and run["final_revision_id"] == accepted,
                "report_final_revision_not_accepted")
        require(len(comparisons) == max(0, len(revisions) - 1) and len(completed) == len(by_round)
                and f"{accepted}:fixture" in evaluations, "report_finished_with_unresolved_records")
        expected_reason = ("fixture_candidate_regression_rolled_back" if rejected else
                           "fixture_assertions_satisfied" if all(revisions[accepted]["fixture_assertions"].values())
                           else "fixture_repair_budget_exhausted")
        require(run["stop_reason"] == expected_reason, "report_stop_reason_mismatch")
        if expected_reason == "fixture_repair_budget_exhausted":
            require(len(by_round) == rounds + 1, "report_budget_not_exhausted")
    else:
        require(run["final_revision_id"] is None, "report_nonterminal_final_revision")
    return {"status": "verified_development_ledger_not_migration_evidence",
            "initial_revision_id": f"{run_id}_0" if revisions else None,
            "accepted_revision_id": accepted,
            "revision_order": [row["id"] for row in ordered], "comparisons": comparisons,
            "source_and_revision_hashes_checked": True}


def project_report(api, snapshot, storage):
    audit = validate_ledger(snapshot, storage)
    run, source = snapshot["run"], snapshot["source"]
    if "contract_snapshot" not in run["request"]:
        return {"contract_report": None, "fixture_audit": audit,
                "contract_projection": {"status": "unavailable", "reason": "request_snapshot_missing_no_backfill"}}
    try:
        request = validate_snapshot(api, run_id=run["id"], task_id=run["task_id"], source=source,
                                    request=run["request"], binding=run["binding"])
    except (ValueError, KeyError, TypeError) as error:
        raise ReportError("report_request_snapshot_mismatch") from error
    if run["status"] == "execution_error":
        status = api.Status.EXECUTION_ERROR
    elif run["status"] == "review_required":
        status = api.Status.BLOCKED
    else:
        status = api.Status.NOT_RUN
    unexecuted = tuple(api.EvaluationResult(
        evaluation_id=f"{run['id']}:not-run:{dimension}", dimension=dimension,
        status=api.Status.NOT_RUN, evidence_level=api.EvidenceLevel(level),
        reason="development_stub: quality evaluation not executed; level names the intended check, not observed evidence")
        for dimension, level in DIMENSIONS.items())
    report = api.RunReport(request=request, status=status,
        stop_reason=run["stop_reason"] or f"execution_{run['status']}; migration_evaluation_not_run",
        required_dimensions=tuple(DIMENSIONS), final_results=unexecuted,
        cost=api.CostRecord(generation_calls=0, model_repair_calls=0, rule_steps=0,
                            generation_tokens=0, repair_tokens=0))
    wire = report.to_dict()
    require(api.load_contract(wire).to_dict() == wire, "report_contract_roundtrip_mismatch")
    return {"contract_report": wire, "fixture_audit": audit,
            "contract_projection": {"status": "validated_not_run_projection", "schema_version": 1,
                "reason": "P1 has no development_stub origin; fixture records remain in the application ledger",
                "omitted_from_p1": ["fixture_revisions", "fixture_evaluations", "fixture_candidate_decisions"],
                "production_ready": False}}
