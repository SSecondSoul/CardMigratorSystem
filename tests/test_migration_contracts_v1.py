"""Offline contract tests: no models, browser, subprocess or old-record writes."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from migration_pipeline.contracts import (
    ArtifactOrigin, ArtifactRevision, Budget, CandidateAction, CandidateDecision,
    ContractError, CostRecord, Diagnostic, DiagnosticOrigin, EvaluationResult,
    EvidenceLevel, FileFingerprint, LegacyFormat, MigrationRequest, RepairAction,
    RepairDecision, Repairability, RunReport, Severity, Status, load_contract,
    project_legacy,
)


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 64


def request():
    return MigrationRequest(
        run_id="offline-test", sample_id="example", source=FileFingerprint(path="Example.vue", sha256=SHA),
        protocol_sha256=SHA, implementation_sha256=SHA, prompt_set_sha256=SHA,
        evaluation_policy_sha256=SHA, model_config_sha256=SHA, ssm_schema_version="3",
        budget=Budget(max_model_repair_calls=3, max_rule_steps=8), props={"title": "示例"},
    )


def revision(name="r0", parent=None, origin=ArtifactOrigin.GENERATION):
    return ArtifactRevision(revision_id=name, parent_revision_id=parent, origin=origin,
                            artifact=FileFingerprint(path=f"{name}.san", sha256=SHA))


def evaluation(**changes):
    values = dict(evaluation_id="e0", dimension="static_validation", status=Status.PASS,
                  evidence_level=EvidenceLevel.STATIC, revision_id="r0",
                  evaluator_version="test-v1", evidence_refs=("test-result.json",))
    return EvaluationResult(**{**values, **changes})


def report(**changes):
    values = dict(request=request(), status=Status.PASS, stop_reason="passed",
                  required_dimensions=("static_validation",), revisions=(revision(),),
                  final_revision_id="r0", final_results=(evaluation(),))
    return RunReport(**{**values, **changes})


def dimension(projection, name):
    return next(item for item in projection.evaluations if item.dimension == name)


class ContractValueTests(unittest.TestCase):
    def test_all_contract_types_json_roundtrip(self):
        diagnostic = Diagnostic(diagnostic_id="d0", code="original_code", stage="validate",
                                details={"中文": [1, None, False]})
        values = [request(), request().source, request().budget, revision(), diagnostic,
                  evaluation(), CostRecord(),
                  RepairDecision(decision_id="repair0", input_revision_id="r0",
                                 action=RepairAction.BLOCK, reason="unproven"),
                  CandidateDecision(decision_id="gate0", previous_revision_id="r0",
                                    candidate_revision_id="r1", action=CandidateAction.NOT_EVALUATED,
                                    reason="pending"), report()]
        for value in values:
            with self.subTest(contract=type(value).__name__):
                encoded = json.loads(json.dumps(value.to_dict(), ensure_ascii=False, allow_nan=False))
                self.assertEqual(load_contract(encoded), value)

    def test_statuses_remain_distinct(self):
        self.assertEqual(len(Status), 7)
        for status in Status:
            value = evaluation(status=status, reason="explicit state")
            self.assertIs(load_contract(value.to_dict()).status, status)

    def test_unknown_fields_versions_and_types_rejected(self):
        for changes in ({"contract_version": 2}, {"contract_version": True},
                        {"contract_type": "browser"}, {"contract_type": []},
                        {"unexpected": "not silently dropped"}):
            with self.subTest(changes=changes):
                with self.assertRaises(ContractError):
                    load_contract({**request().to_dict(), **changes})

    def test_nested_missing_or_extra_fields_rejected(self):
        for change in (lambda v: v["budget"].update(extra=1),
                       lambda v: v["source"].pop("sha256"),
                       lambda v: v["budget"].update(max_rule_steps=True)):
            value = request().to_dict()
            change(value)
            with self.assertRaises(ContractError):
                MigrationRequest.from_dict(value)

    def test_no_boolean_or_string_numeric_coercion(self):
        for value in (True, "3", -1):
            with self.subTest(value=value), self.assertRaises(ContractError):
                Budget(max_model_repair_calls=value, max_rule_steps=8)

    def test_bad_hashes_and_duplicate_inputs_rejected(self):
        for value in ("", "unknown", "A" * 64, "a" * 63):
            with self.subTest(value=value), self.assertRaises(ContractError):
                FileFingerprint(path="Example.vue", sha256=value)
        with self.assertRaises(ContractError):
            replace(request(), dependencies=(request().source,))

    def test_json_rejects_nan_infinity_nonstring_keys_and_objects(self):
        for value in (float("nan"), float("inf"), {1: "key"}, object()):
            with self.subTest(value=repr(value)), self.assertRaises(ContractError):
                replace(request(), props={"bad": value})

    def test_input_and_export_json_are_detached(self):
        props = {"items": [{"n": 1}]}
        value = replace(request(), props=props)
        props["items"][0]["n"] = 8
        exported = value.to_dict()
        exported["props"]["items"][0]["n"] = 9
        self.assertEqual(value.props["items"][0]["n"], 1)

    def test_unknown_costs_are_not_zero(self):
        self.assertIsNone(CostRecord().model_repair_calls)
        self.assertEqual(CostRecord(model_repair_calls=0).model_repair_calls, 0)
        with self.assertRaises(ContractError):
            CostRecord(manual_lines=-1)

    def test_repair_requires_parent_and_generation_cannot_inherit(self):
        for kwargs in (dict(origin=ArtifactOrigin.MODEL), dict(origin=ArtifactOrigin.RULE),
                       dict(parent_revision_id="r1"), dict(parent_revision_id="r0")):
            with self.subTest(kwargs=kwargs), self.assertRaises(ContractError):
                replace(revision(), **kwargs)

    def test_origin_and_severity_are_separate_and_unknown_blocks(self):
        value = Diagnostic(diagnostic_id="d", code="source_warning", stage="browser",
                           origin=DiagnosticOrigin.SOURCE, severity=Severity.WARNING)
        self.assertTrue(value.blocking)
        with self.assertRaises(ContractError):
            replace(value, origin=DiagnosticOrigin.UNKNOWN, blocking=False)

    def test_unknown_source_and_infrastructure_cannot_declare_target_repair(self):
        for origin in DiagnosticOrigin:
            for route in (Repairability.MODEL, Repairability.RULE):
                if origin is not DiagnosticOrigin.TARGET:
                    with self.subTest(origin=origin, route=route), self.assertRaises(ContractError):
                        Diagnostic(diagnostic_id="d", code="c", stage="s", origin=origin,
                                   repairability=route)

    def test_nonconclusive_results_require_reason(self):
        for status in (Status.BLOCKED, Status.NOT_RUN, Status.UNSUPPORTED,
                       Status.EXECUTION_ERROR, Status.UNKNOWN):
            with self.subTest(status=status), self.assertRaises(ContractError):
                evaluation(status=status)

    def test_pass_cannot_contain_blocking_diagnostic(self):
        with self.assertRaises(ContractError):
            evaluation(diagnostics=(Diagnostic(diagnostic_id="d", code="c", stage="s"),))

    def test_rule_and_model_decisions_require_records(self):
        base = RepairDecision(decision_id="d", input_revision_id="r0",
                              action=RepairAction.BLOCK, reason="pending")
        for action in (RepairAction.MODEL, RepairAction.RULE):
            with self.subTest(action=action), self.assertRaises(ContractError):
                replace(base, action=action, diagnostic_ids=("issue",))
        self.assertIs(replace(base, action=RepairAction.MODEL, diagnostic_ids=("issue",),
                              model_request_ref="request.json").action, RepairAction.MODEL)

    def test_candidate_accept_requires_comparison_and_reject_requires_rollback(self):
        base = CandidateDecision(decision_id="d", previous_revision_id="r0",
                                 candidate_revision_id="r1", action=CandidateAction.NOT_EVALUATED,
                                 reason="pending")
        for change in (dict(action=CandidateAction.ACCEPT), dict(action=CandidateAction.REJECT),
                       dict(action=CandidateAction.REJECT, rollback_revision_id="r1")):
            with self.subTest(change=change), self.assertRaises(ContractError):
                replace(base, **change)
        self.assertEqual(replace(base, action=CandidateAction.REJECT,
                                 rollback_revision_id="r0").rollback_revision_id, "r0")

    def test_report_missing_unknown_or_legacy_checks_cannot_pass(self):
        for values in ((), (evaluation(status=Status.UNKNOWN, reason="missing"),),
                       (evaluation(evidence_level=EvidenceLevel.LEGACY_DECLARATION),),
                       (evaluation(revision_id=None),), (evaluation(evidence_refs=()),)):
            with self.subTest(values=values), self.assertRaises(ContractError):
                report(final_results=values)

    def test_report_cannot_hide_blocked_dimension_or_empty_required_list(self):
        blocked = evaluation(evaluation_id="e1", dimension="public_key_contract",
                             status=Status.UNSUPPORTED, reason="not waived")
        with self.assertRaises(ContractError):
            report(final_results=(evaluation(), blocked))
        with self.assertRaises(ContractError):
            report(required_dimensions=())

    def test_report_unknown_cyclic_or_duplicate_revision_references_rejected(self):
        for changes in (dict(final_revision_id="absent"),
                        dict(revisions=(revision(), revision())),
                        dict(revisions=(revision("r1", "r0", ArtifactOrigin.MODEL), revision())),
                        dict(final_results=(evaluation(revision_id="absent"),))):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                report(**changes)

    def test_failed_and_blocked_report_do_not_require_fake_final_artifact(self):
        for status in (Status.FAIL, Status.BLOCKED, Status.EXECUTION_ERROR, Status.UNSUPPORTED):
            value = report(status=status, final_revision_id=None, revisions=(), final_results=())
            self.assertIsNone(load_contract(value.to_dict()).final_revision_id)

    def test_attempt_evaluations_and_rejected_candidates_survive_roundtrip(self):
        issue = Diagnostic(diagnostic_id="d0", code="missing_event", stage="validate",
                           origin=DiagnosticOrigin.TARGET, repairability=Repairability.MODEL)
        before = evaluation(evaluation_id="before", status=Status.FAIL, diagnostics=(issue,))
        after = evaluation(evaluation_id="candidate", revision_id="r1", status=Status.FAIL)
        repair = RepairDecision(decision_id="repair", input_revision_id="r0", action=RepairAction.MODEL,
                                reason="actual attempt", diagnostic_ids=("d0",),
                                model_request_ref="request.json", candidate_revision_id="r1")
        gate = CandidateDecision(decision_id="gate", previous_revision_id="r0", candidate_revision_id="r1",
                                 action=CandidateAction.REJECT, reason="regression", rollback_revision_id="r0",
                                 before_evaluation_ids=("before",), after_evaluation_ids=("candidate",))
        value = report(status=Status.FAIL, stop_reason="candidate_rejected",
                       revisions=(revision(), revision("r1", "r0", ArtifactOrigin.MODEL)),
                       initial_results=(before,), attempt_results=(after,),
                       repair_decisions=(repair,), candidate_decisions=(gate,))
        loaded = load_contract(value.to_dict())
        self.assertEqual(loaded, value)
        self.assertEqual(loaded.final_revision_id, "r0")
        self.assertEqual(loaded.attempt_results[0].revision_id, "r1")

    def test_report_rejects_dangling_repair_and_candidate_links(self):
        bad_repair = RepairDecision(decision_id="d", input_revision_id="absent",
                                    action=RepairAction.BLOCK, reason="blocked")
        with self.assertRaises(ContractError):
            report(repair_decisions=(bad_repair,))
        gate = CandidateDecision(decision_id="g", previous_revision_id="r0", candidate_revision_id="r1",
                                 action=CandidateAction.ACCEPT, reason="claimed", comparison_policy_sha256=SHA,
                                 before_evaluation_ids=("missing",), after_evaluation_ids=("e0",))
        with self.assertRaises(ContractError):
            report(revisions=(revision(), revision("r1", "r0", ArtifactOrigin.MODEL)),
                   candidate_decisions=(gate,))

    def test_final_evaluation_and_candidate_comparison_must_bind_right_revision(self):
        with self.assertRaises(ContractError):
            report(revisions=(revision(), revision("r1", "r0", ArtifactOrigin.MODEL)),
                   final_results=(evaluation(revision_id="r1"),))
        gate = CandidateDecision(decision_id="g", previous_revision_id="r0", candidate_revision_id="r1",
                                 action=CandidateAction.REJECT, reason="regression", rollback_revision_id="r0",
                                 after_evaluation_ids=("e0",))
        with self.assertRaises(ContractError):
            report(revisions=(revision(), revision("r1", "r0", ArtifactOrigin.MODEL)),
                   candidate_decisions=(gate,))

    def test_export_does_not_replace_nested_object_identity(self):
        value = request()
        before_props, before_source = value.props, value.source
        value.to_dict()
        self.assertIs(value.props, before_props)
        self.assertIs(value.source, before_source)


class LegacyCompatibilityTests(unittest.TestCase):
    def project(self, value, fmt=LegacyFormat.STATE, **kwargs):
        return project_legacy(value, legacy_format=fmt, **kwargs)

    def test_absent_default_and_string_flags_never_become_pass(self):
        for payload in ({}, {"validation_passed": True, "final_passed": False},
                        {"final_validate_result": {"validation_passed": "true"}}):
            with self.subTest(payload=payload):
                view = self.project(payload)
                self.assertIsNot(dimension(view, "static_validation").status, Status.PASS)

    def test_current_phase_does_not_use_flat_defaults(self):
        view = self.project({"validation_passed": False}, phase="current")
        self.assertIs(dimension(view, "static_validation").status, Status.NOT_RUN)

    def test_state_initial_current_and_final_do_not_leak(self):
        data = {"initial_validate_result": {"validation_passed": False},
                "validate_result": {"validation_passed": True}}
        self.assertIs(dimension(self.project(data, phase="initial"), "static_validation").status, Status.FAIL)
        self.assertIs(dimension(self.project(data, phase="current"), "static_validation").status, Status.PASS)
        self.assertIs(dimension(self.project(data), "static_validation").status, Status.NOT_RUN)

    def test_legacy_dom_pass_never_creates_native_proof(self):
        data = {"final_visual_eval_result": {"visual_eval_passed": True, "structure_similarity": 1.0}}
        view = self.project(data)
        dom = dimension(view, "legacy_dom")
        self.assertIs(dom.status, Status.PASS)
        self.assertIs(dom.evidence_level, EvidenceLevel.LEGACY_DECLARATION)
        self.assertIsNone(dom.revision_id)
        for name in ("native_runtime", "browser_visual", "browser_interaction"):
            self.assertIs(dimension(view, name).status, Status.NOT_RUN)

    def test_skipped_compile_and_interaction_do_not_pass(self):
        data = {"final_validate_result": {"validation_passed": True, "san_compile_result": {
            "passed": True, "skipped": True, "reason": "node_not_found"}},
            "interaction_eval_result": {"passed": True, "skipped": True}}
        view = self.project(data)
        self.assertIs(dimension(view, "san_compile").status, Status.NOT_RUN)
        self.assertIs(dimension(view, "legacy_interaction").status, Status.NOT_RUN)

    def test_original_codes_details_history_and_unknown_fields_preserved(self):
        data = {"final_passed": False, "stop_reason": "repair_candidate_regression_rolled_back",
                "repair_history": [{"original": {"future": [1, 2]}}], "future_schema": {"v": 9},
                "final_validate_result": {"validation_passed": False, "validation_errors": [
                    {"code": "source_dynamic_assignment_unproven", "details": {"keys": ["a.b"]}}]}}
        original = deepcopy(data)
        view = self.project(data)
        data["future_schema"]["v"] = 0
        detached = view.to_legacy()
        self.assertEqual(detached, original)
        detached["repair_history"].clear()
        self.assertEqual(view.to_legacy(), original)
        issue = dimension(view, "static_validation").diagnostics[0]
        self.assertEqual(issue.code, "source_dynamic_assignment_unproven")
        self.assertIs(issue.origin, DiagnosticOrigin.UNKNOWN)
        self.assertIs(issue.repairability, Repairability.UNKNOWN)
        self.assertNotIn("repair_history", view.to_dict())

    def test_source_looking_warning_not_guessed_as_target_or_ignored(self):
        data = {"final_visual_eval_result": {"visual_eval_passed": True,
                "visual_eval_warnings": [{"code": "vue_warning", "message": "target stack"}]}}
        view = self.project(data)
        item = dimension(view, "legacy_dom")
        self.assertIs(item.status, Status.BLOCKED)
        self.assertIs(item.diagnostics[0].origin, DiagnosticOrigin.UNKNOWN)

    def test_compact_counts_preserved_without_inventing_issue_codes(self):
        data = {"summary": {"final_passed": True}, "final": {
            "validate": {"validation_passed": True, "error_count": 0, "warning_count": 2},
            "visual_eval": {"visual_eval_passed": True, "structure_similarity": 0.99}}}
        view = self.project(data, LegacyFormat.REPAIR_REPORT)
        self.assertTrue(view.legacy_declared_final_passed)
        item = dimension(view, "static_validation")
        self.assertIs(item.status, Status.BLOCKED)
        self.assertEqual(item.diagnostics[0].details["legacy_issue"]["count"], 2)
        self.assertIs(dimension(view, "san_compile").status, Status.NOT_RUN)

    def test_malformed_flags_lists_counts_and_conflicts_block(self):
        for result in ({"validation_passed": True, "passed": False},
                       {"validation_passed": True, "passed": 1},
                       {"validation_passed": True, "validation_errors": "bad"},
                       {"validation_passed": True, "skipped": True, "validation_errors": "bad"},
                       {"validation_passed": True, "error_count": -1},
                       {"validation_passed": True, "skipped": "false"}):
            with self.subTest(result=result):
                view = self.project({"final_validate_result": result})
                self.assertIs(dimension(view, "static_validation").status, Status.BLOCKED)

    def test_batch_completed_is_not_migration_pass_and_cost_not_fabricated(self):
        row = {"id": "example", "status": "completed", "repair_rounds": 2,
               "final_passed": False, "final_validation_passed": False,
               "final_validation_error_codes": ["original"], "total_tokens": 100}
        view = self.project(row, LegacyFormat.BATCH_SAMPLE)
        self.assertFalse(view.legacy_declared_final_passed)
        self.assertIs(dimension(view, "static_validation").status, Status.FAIL)
        self.assertNotIn("cost", view.to_dict())
        self.assertEqual(view.to_legacy(), row)

    def test_execution_error_not_target_failure(self):
        view = self.project({"id": "x", "status": "error", "error_message": "HTTP 400"},
                            LegacyFormat.BATCH_SAMPLE)
        self.assertIs(dimension(view, "pipeline_execution").status, Status.EXECUTION_ERROR)
        self.assertIs(dimension(view, "static_validation").status, Status.NOT_RUN)

    def test_explicit_formats_and_supported_phases_only(self):
        for kwargs in (dict(legacy_format="state"),
                       dict(legacy_format=LegacyFormat.STATE, phase="best"),
                       dict(legacy_format=LegacyFormat.REPAIR_REPORT, phase="current")):
            with self.subTest(kwargs=kwargs), self.assertRaises(ContractError):
                project_legacy({}, **kwargs)
        for fmt in (LegacyFormat.STATE, LegacyFormat.BATCH_SAMPLE):
            with self.subTest(fmt=fmt), self.assertRaises(ContractError):
                self.project({"samples": [], "aggregate": {}}, fmt)
        for payload in ({"schemaVersion": 5}, {"contract_type": "RunReport", "contract_version": 1}):
            with self.subTest(payload=payload), self.assertRaises(ContractError):
                self.project(payload)

    def test_real_state_and_compact_report_can_be_read_without_mutation(self):
        path = ROOT / ("data/experiments/repair_reports/batches/formal_30_v4_full_regression_v2/"
                       "simple/VolumeControl_repair_history.json")
        before = path.read_bytes()
        data = json.loads(before)
        for payload, fmt in ((data, LegacyFormat.REPAIR_REPORT), (data["state"], LegacyFormat.STATE)):
            for phase in ("initial", "final"):
                with self.subTest(format=fmt, phase=phase):
                    view = self.project(payload, fmt, phase=phase)
                    self.assertEqual(view.to_legacy(), payload)
                    self.assertIs(dimension(view, "browser_visual").status, Status.NOT_RUN)
        self.assertEqual(path.read_bytes(), before)

    def test_existing_generation_interface_with_fake_client_needs_no_new_material(self):
        from migration_pipeline.generation_client import GenerationResult
        from migration_pipeline.stages.generate import GenerateStage, GenerateStageInput

        class FakeClient:
            def generate(self, old_request):
                return GenerationResult(source_file=old_request.source_file, ssm=old_request.ssm,
                                        code="test-only", saved_file_path="not-written.san",
                                        provider="fake", model="fake")

        with patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            result = GenerateStage(FakeClient()).run(GenerateStageInput(ssm={"metadata": {}}, source_file="x"))
            old_state = result.to_state_update()
            view = self.project(old_state, phase="current")
        self.assertEqual(view.to_legacy()["generated_code"], "test-only")
        self.assertIs(dimension(view, "static_validation").status, Status.NOT_RUN)

    def test_adapter_calls_no_model_browser_or_subprocess_and_changes_no_input(self):
        original = {"final_passed": True, "generation_raw_response": {"private": "not exported"}}
        saved = deepcopy(original)
        with patch("urllib.request.urlopen", side_effect=AssertionError("network")), \
                patch("subprocess.run", side_effect=AssertionError("subprocess")):
            view = self.project(original)
            self.assertEqual(original, saved)
            self.assertNotIn("not exported", json.dumps(view.to_dict()))

    def test_real_30_sample_checkpoint_read_only_roundtrip(self):
        path = ROOT / "data/experiments/batch_reports/formal_30_v4_full_regression_v2_summary.json"
        before = path.read_bytes()
        checkpoint = json.loads(before)
        self.assertEqual(len(checkpoint["samples"]), 30)
        passed = 0
        for row in checkpoint["samples"]:
            with self.subTest(sample=row["id"]):
                view = self.project(row, LegacyFormat.BATCH_SAMPLE)
                self.assertEqual(view.to_legacy(), row)
                passed += view.legacy_declared_final_passed is True
                self.assertIs(dimension(view, "browser_visual").status, Status.NOT_RUN)
        self.assertEqual(passed, 24)  # Historical declarations, not new admission.
        self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), hashlib.sha256(before).digest())


if __name__ == "__main__":
    unittest.main()
