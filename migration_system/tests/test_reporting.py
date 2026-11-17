"""Strict contract projections and corrupt-reference rejection; no quality/model execution."""
import json
import unittest
from unittest.mock import patch

import test_vertical_slice as fixtures
from sqlalchemy.orm.attributes import flag_modified
from card_migration_system.application.service import ServiceError, digest
from card_migration_system.application.storage import StorageError
from card_migration_system.persistence.database import transaction
from card_migration_system.persistence.schema_v1 import Attempt, Evaluation, Revision, Run
from card_migration_system.reporting.projection import project_report
from card_migration_system.workers.runner import work_once


class ReportingTests(unittest.TestCase):
    setUp = fixtures.VerticalSliceTests.setUp
    enqueue = fixtures.VerticalSliceTests.enqueue
    app = fixtures.VerticalSliceTests.app

    def finished(self, profile="success", rounds=3):
        run_id, _ = self.enqueue(profile, rounds)
        self.assertEqual(work_once(self.service)["status"], "finished")
        return run_id

    def fault(self, run_id, mutate):
        def project(api, snapshot, storage):
            mutate(snapshot)
            return project_report(api, snapshot, storage)
        with patch("card_migration_system.reporting.projection.project_report", project):
            return self.service.report(run_id)

    def test_enqueue_freezes_real_disabled_descriptors_and_p1_request(self):
        run_id, task_id = self.enqueue("repairable")
        run = self.service.run(run_id)
        frozen = run["request"]["contract_snapshot"]
        request = self.service.binding.contracts.load_contract(frozen["request"])
        self.assertEqual(request.run_id, run_id)
        self.assertEqual(request.sample_id, "task:" + task_id)
        self.assertEqual(request.ssm_schema_version, "development_stub_not_extracted")
        self.assertEqual(request.budget.max_model_repair_calls, 0)
        self.assertEqual(request.budget.max_rule_steps, 0)
        self.assertEqual(run["request"]["max_repair_rounds"], 3)
        for field, descriptor in (("protocol_sha256", "protocol"), ("prompt_set_sha256", "prompt_set"),
                                  ("model_config_sha256", "model_config"), ("evaluation_policy_sha256", "evaluation_policy")):
            self.assertEqual(getattr(request, field), digest(frozen["descriptors"][descriptor]))
        self.assertFalse(frozen["descriptors"]["model_config"]["external_calls_permitted"])
        self.assertEqual(run["request_sha256"], digest(run["request"]))

    def test_idempotent_submission_reuses_original_snapshot(self):
        run_id, task_id = self.enqueue()
        before = self.service.run(run_id)
        with patch("card_migration_system.reporting.request_snapshot.build_snapshot", side_effect=AssertionError("must not rebuild")):
            result = self.service.enqueue(task_id, {"profile": "success", "max_repair_rounds": 3}, "first")
        self.assertTrue(result["reused"])
        self.assertEqual(result["run_id"], run_id)
        self.assertEqual(self.service.run(run_id), before)

    def test_queued_report_roundtrips_without_claiming_evidence(self):
        run_id, _ = self.enqueue()
        result = self.service.report(run_id)
        report = result["contract_report"]
        self.assertEqual(self.service.binding.contracts.load_contract(report).to_dict(), report)
        self.assertEqual(report["status"], "not_run")
        self.assertEqual(result["status"], "queued")
        self.assertIsNone(report["final_revision_id"])
        self.assertEqual(report["revisions"], [])
        self.assertEqual(len(report["required_dimensions"]), 6)
        self.assertTrue(all(item["status"] == "not_run" and item["revision_id"] is None
                            and not item["metrics"] and not item["evidence_refs"]
                            and item["evaluator_version"] is None for item in report["final_results"]))

    def test_finished_stub_never_becomes_p1_generation_or_pass(self):
        run_id = self.finished()
        result = self.service.report(run_id)
        report = result["contract_report"]
        self.assertEqual(result["status"], "finished")
        self.assertIsNotNone(result["final_revision_id"])
        self.assertEqual(report["status"], "not_run")
        self.assertIsNone(report["final_revision_id"])
        self.assertEqual(report["revisions"], [])
        self.assertEqual(report["cost"]["generation_calls"], 0)
        self.assertIsNone(report["cost"]["elapsed_seconds"])
        self.assertIsNone(report["cost"]["manual_seconds"])
        self.assertIn("fixture_revisions", result["contract_projection"]["omitted_from_p1"])

    def test_repair_chain_keeps_actual_comparison_refs_not_fake_model_repairs(self):
        run_id = self.finished("repairable")
        result = self.service.report(run_id)
        audit = result["fixture_audit"]
        self.assertEqual(audit["revision_order"], [run_id + "_0", run_id + "_1"])
        self.assertEqual(audit["accepted_revision_id"], run_id + "_1")
        comparison = audit["comparisons"][0]
        self.assertEqual(comparison["before_evaluation_ids"], [run_id + "_0:fixture"])
        self.assertEqual(comparison["after_evaluation_ids"], [run_id + "_1:fixture"])
        self.assertEqual(comparison["action"], "accept")
        self.assertEqual(result["contract_report"]["repair_decisions"], [])
        self.assertEqual(result["contract_report"]["candidate_decisions"], [])
        self.assertEqual(result["contract_report"]["cost"]["model_repair_calls"], 0)

    def test_rejection_retains_failed_candidate_and_explicit_rollback(self):
        run_id = self.finished("regression")
        result = self.service.report(run_id)
        self.assertEqual(len(result["revisions"]), 2)
        self.assertEqual(result["fixture_audit"]["accepted_revision_id"], run_id + "_0")
        self.assertEqual(result["fixture_audit"]["comparisons"][0]["rollback_revision_id"], run_id + "_0")
        self.assertIn(b"round 0", self.service.download(run_id))

    def test_budget_exhaustion_remains_not_run_with_all_attempts(self):
        run_id = self.finished("always_fail", 3)
        result = self.service.report(run_id)
        self.assertEqual(len(result["attempts"]), 4)
        self.assertEqual(len(result["fixture_audit"]["comparisons"]), 3)
        self.assertEqual(result["contract_report"]["status"], "not_run")
        self.assertEqual(result["stop_reason"], "fixture_repair_budget_exhausted")

    def test_review_projects_blocked_without_fabricating_quality_failure(self):
        run_id, _ = self.enqueue()
        work_once(self.service, interrupt_after=["generate"])
        result = self.service.report(run_id)
        self.assertEqual(result["status"], "review_required")
        self.assertEqual(result["contract_report"]["status"], "blocked")
        self.assertTrue(all(item["status"] == "not_run" for item in result["contract_report"]["final_results"]))

    def test_cancelled_run_preserves_execution_state_and_not_run_projection(self):
        run_id, _ = self.enqueue()
        self.service.cancel(run_id)
        result = self.service.report(run_id)
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(result["contract_report"]["status"], "not_run")
        self.assertEqual(result["contract_report"]["stop_reason"], "cancelled_before_execution")

    def test_infrastructure_error_is_not_target_failure(self):
        run_id, _ = self.enqueue()
        with patch.object(self.service, "verify_binding", side_effect=ServiceError("controlled_infrastructure_error")):
            self.assertEqual(work_once(self.service)["status"], "execution_error")
        result = self.service.report(run_id)
        self.assertEqual(result["contract_report"]["status"], "execution_error")
        self.assertEqual(result["contract_report"]["attempt_results"], [])
        self.assertEqual(result["contract_report"]["repair_decisions"], [])

    def test_legacy_missing_snapshot_is_unavailable_not_backfilled(self):
        run_id, _ = self.enqueue()
        with transaction(self.service.engine) as session:
            row = session.get(Run, run_id)
            request = dict(row.request)
            del request["contract_snapshot"]
            row.request, row.request_sha256 = request, digest(request)
        before = self.service.run(run_id)
        result = self.service.report(run_id)
        self.assertIsNone(result["contract_report"])
        self.assertEqual(result["contract_projection"]["reason"], "request_snapshot_missing_no_backfill")
        self.assertEqual(self.service.run(run_id), before)
        with self.assertRaisesRegex(ServiceError, "snapshot_missing"):
            self.service.verify_binding(run_id)

    def test_request_hash_drift_blocks_export_and_worker(self):
        run_id, _ = self.enqueue()
        with transaction(self.service.engine) as session:
            row = session.get(Run, run_id)
            row.request = {**row.request, "max_repair_rounds": 2}
        with self.assertRaisesRegex(ServiceError, "request_hash_mismatch"):
            self.service.report(run_id)
        self.assertEqual(work_once(self.service)["stop_reason"], "request_identity_drift")

    def test_snapshot_mutation_even_with_rehashed_outer_request_is_rejected(self):
        run_id, _ = self.enqueue()
        with transaction(self.service.engine) as session:
            row = session.get(Run, run_id)
            request = json.loads(json.dumps(row.request))
            request["contract_snapshot"]["descriptors"]["model_config"]["external_calls_permitted"] = True
            row.request, row.request_sha256 = request, digest(request)
        with self.assertRaisesRegex(ServiceError, "snapshot_mismatch"):
            self.service.report(run_id)
        self.assertEqual(work_once(self.service)["stop_reason"], "request_snapshot_missing_or_mismatched")

    def test_p1_request_unknown_field_is_not_silently_accepted(self):
        run_id, _ = self.enqueue()
        with transaction(self.service.engine) as session:
            row = session.get(Run, run_id)
            request = json.loads(json.dumps(row.request))
            request["contract_snapshot"]["request"]["extra"] = "secret-sentinel"
            row.request, row.request_sha256 = request, digest(request)
        client = self.app().test_client()
        response = client.get(f"/api/v1/runs/{run_id}/report", base_url=fixtures.BASE)
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("secret-sentinel", response.get_data(as_text=True))

    def test_snapshot_boolean_integer_equality_cannot_hide_descriptor_drift(self):
        run_id, _ = self.enqueue()
        with transaction(self.service.engine) as session:
            row = session.get(Run, run_id)
            request = json.loads(json.dumps(row.request))
            request["contract_snapshot"]["descriptors"]["model_config"]["external_calls_permitted"] = 0
            row.request, row.request_sha256 = request, digest(request)
            # SQLAlchemy JSON dirty comparison also treats False == 0. Force this
            # deliberate corruption into the disposable DB to exercise the inner guard.
            flag_modified(row, "request")
        with self.assertRaisesRegex(ServiceError, "snapshot_mismatch"):
            self.service.report(run_id)

    def test_unknown_real_origin_is_not_invented_as_stub_or_model_evidence(self):
        run_id = self.finished()
        with transaction(self.service.engine) as session:
            session.get(Revision, run_id + "_0").source_kind = "model"
        with self.assertRaisesRegex(ServiceError, "unsupported_revision_origin"):
            self.service.report(run_id)

    def test_missing_candidate_evaluation_blocks_projection(self):
        run_id = self.finished("repairable")
        with transaction(self.service.engine) as session:
            session.delete(session.get(Evaluation, run_id + "_1:fixture"))
        with self.assertRaisesRegex(ServiceError, "missing_evaluations"):
            self.service.report(run_id)

    def test_fake_quality_pass_in_fixture_evaluation_blocks_projection(self):
        run_id = self.finished()
        with transaction(self.service.engine) as session:
            session.get(Evaluation, run_id + "_0:fixture").status = "pass"
        with self.assertRaisesRegex(ServiceError, "cannot_be_quality_evidence"):
            self.service.report(run_id)

    def test_rejected_candidate_cannot_be_the_exported_final(self):
        run_id = self.finished("regression")
        with transaction(self.service.engine) as session:
            session.get(Run, run_id).final_revision_id = run_id + "_1"
        with self.assertRaisesRegex(ServiceError, "final_revision_not_accepted"):
            self.service.report(run_id)
        with self.assertRaisesRegex(ServiceError, "final_revision_not_accepted"):
            self.service.download(run_id)

    def test_cross_run_snapshot_reference_is_blocked(self):
        run_id = self.finished()
        with self.assertRaisesRegex(ServiceError, "cross_run_reference"):
            self.fault(run_id, lambda snap: snap["revisions"][0].update(run_id="other-run"))

    def test_parent_cycle_or_missing_parent_is_blocked(self):
        run_id = self.finished()
        with self.assertRaisesRegex(ServiceError, "missing_parent_or_cycle"):
            self.fault(run_id, lambda snap: snap["revisions"][0].update(parent_id=run_id + "_0"))

    def test_receipt_cannot_reference_an_unknown_revision(self):
        run_id = self.finished()
        with self.assertRaisesRegex(ServiceError, "receipt_revision_mismatch"):
            self.fault(run_id, lambda snap: snap["attempts"][0]["result"].update(revision_id="unknown"))

    def test_attempt_request_hash_mismatch_is_blocked(self):
        run_id = self.finished()
        with self.assertRaisesRegex(ServiceError, "attempt_request_mismatch"):
            self.fault(run_id, lambda snap: snap["attempts"][0].update(request_sha256="a" * 64))

    def test_corrupt_rejected_artifact_still_blocks_verified_export(self):
        run_id = self.finished("regression")
        target = self.settings.artifact_dir / f"runs/{run_id}/{run_id}_1.san"
        target.write_bytes(b"corrupted rejected candidate")
        with self.assertRaises(StorageError):
            self.service.report(run_id)

    def test_started_unresolved_attempt_is_preserved_not_credited_as_generation(self):
        run_id, _ = self.enqueue()
        with transaction(self.service.engine) as session:
            row = session.get(Run, run_id)
            row.status, row.stop_reason = "review_required", "ambiguous_attempt_requires_review"
            session.add(Attempt(id=run_id + ":stub:0", run_id=run_id, kind="development_stub", status="started",
                                request_sha256=digest({"run_request": row.request_sha256, "round": 0, "parent": None}),
                                started_at=0, result=None, model_tokens=None))
        result = self.service.report(run_id)
        self.assertEqual(result["attempts"][0]["status"], "started")
        self.assertEqual(result["fixture_audit"]["revision_order"], [])
        self.assertEqual(result["contract_report"]["status"], "blocked")
        self.assertEqual(result["contract_report"]["cost"]["generation_calls"], 0)

    def test_finished_run_cannot_claim_premature_budget_exhaustion(self):
        run_id = self.finished("always_fail", 3)
        with transaction(self.service.engine) as session:
            session.get(Run, run_id).stop_reason = "fixture_assertions_satisfied"
        with self.assertRaisesRegex(ServiceError, "stop_reason_mismatch"):
            self.service.report(run_id)

    def test_report_reads_one_database_snapshot_and_never_calls_run_separately(self):
        run_id = self.finished()
        with patch.object(self.service, "run", side_effect=AssertionError("must not read a second run snapshot")):
            self.assertEqual(self.service.report(run_id)["status"], "finished")

    def test_http_report_polling_is_read_only_and_does_not_expose_raw_source(self):
        run_id = self.finished("repairable")
        before = self.service.report(run_id)
        client = self.app().test_client()
        for _ in range(2):
            response = client.get(f"/api/v1/runs/{run_id}/report", base_url=fixtures.BASE)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json, before)
            self.assertNotIn("<template>", response.get_data(as_text=True))
        self.assertEqual(self.service.report(run_id), before)

    def test_readonly_historical_report_uses_frozen_binding_not_current_implementation(self):
        run_id = self.finished()
        before = self.service.report(run_id)
        with patch.object(self.service, "implementation_binding", return_value={"changed": True}):
            self.assertEqual(self.service.report(run_id), before)
            with self.assertRaisesRegex(ServiceError, "drift"):
                self.service.verify_binding(run_id)


if __name__ == "__main__":
    unittest.main()
