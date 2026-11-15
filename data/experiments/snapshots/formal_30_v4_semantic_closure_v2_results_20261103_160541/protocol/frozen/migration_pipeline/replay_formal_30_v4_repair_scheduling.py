"""Offline scheduling/rollback checks on frozen failures; never calls an LLM."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from migration_pipeline.analyze_formal_30_v4_full_regression import verify_snapshot, digest
from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.stages.generate import GenerateStageInput, GenerateStageResult
from migration_pipeline.stages.repair import RepairStage, RepairStageResult
from migration_pipeline.stages.validate import ValidateStage
from migration_pipeline.stages.visual_eval import VisualEvalStage


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / "data/experiments/snapshots/formal_30_v4_timeout_diagnostic_v1_results_20261102_173627"
FULL = ROOT / "data/experiments/snapshots/formal_30_v4_full_regression_results_20261030_215511"
OUTPUT = ROOT / "data/experiments/analysis/formal_30_v4_repair_scheduling_v1_20261102"


class ReplayGenerate:
    def __init__(self, state, code, path):
        self.state, self.code, self.path = state, code, path

    def run(self, _):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.code, encoding="utf-8")
        return GenerateStageResult(source_file=self.state["source_file"], ssm=self.state["ssm"],
                                   generation_code=self.code, saved_file_path=str(self.path),
                                   provider="offline_replay", model="frozen_bytes", usage={}, raw_response={})


class LLMReached(Exception):
    pass


class CaptureRepair(RepairStage):
    def __init__(self):
        self.captured = None

    def run_from_state(self, state):
        self.captured = deepcopy(state)
        raise LLMReached("No network call: captured input to LLM-only phase")


class ReplayCandidate(RepairStage):
    def __init__(self, code, output):
        self.code, self.output = code, output

    def run_from_state(self, state):
        if not state["repair_metadata"]["skip_deterministic_prepass"]:
            raise AssertionError("Expected LLM-only phase")
        self._ensure_repaired_file(str(self.output), self.code)
        return RepairStageResult(
            repaired_code=self.code, repaired_file_path=str(self.output), repair_prompt="offline frozen candidate",
            repair_attempt=state.get("repair_attempt", 0) + 1, provider="offline_replay", model="frozen_bytes",
        ).to_state_update()


def run_replay(state, code, name, repair):
    generate = ReplayGenerate(state, code, OUTPUT / name / "before.san")
    orchestrator = MigrationPipelineOrchestrator(generate, ValidateStage(), VisualEvalStage(), repair)
    return orchestrator.run_generate_validate_visual_eval_and_repair_loop(
        GenerateStageInput(vue_file_path=state["vue_file_path"], metadata={"repair_policy": "bounded_prepass_v1"}),
        max_repair_rounds=3,
    )


def main():
    verified = {"diagnostic": verify_snapshot(DIAGNOSTIC), "full": verify_snapshot(FULL)}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = {"verified_snapshot_files": verified, "llm_requests": 0, "checks": {}}
    task = json.loads((DIAGNOSTIC / "repair_reports/complex/TaskManager_repair_history.json").read_text(encoding="utf-8"))["state"]
    capture = CaptureRepair()
    try:
        run_replay(task, (DIAGNOSTIC / "pipeline/complex/TaskManager.san").read_text(encoding="utf-8"), "task_prepass", capture)
    except LLMReached:
        pass
    else:
        raise AssertionError("Frozen TaskManager must reach the LLM-only phase with residual errors")
    prepared = capture.captured
    assert prepared and prepared["repair_metadata"]["skip_deterministic_prepass"]
    assert prepared["llm_repair_calls"] == 0  # No request actually executed in replay.
    assert 0 < prepared["deterministic_steps"] <= 4
    results["checks"]["task_reaches_llm"] = {
        "deterministic_steps": prepared["deterministic_steps"],
        "stop_reasons": prepared["normalization_stop_reasons"],
        "remaining_errors": [x["code"] for x in prepared["validation_errors"]],
        "normalization_history": prepared["normalization_history"],
        "prepared_file": str(Path(prepared["generated_file_path"]).relative_to(ROOT)),
        "prepared_sha256": digest(Path(prepared["generated_file_path"])),
    }
    cases = (
        ("monitoring_rollback", DIAGNOSTIC, "complex", "MonitoringDashboard", "_repaired_repaired", "_repaired_repaired_repaired"),
        ("budget_rollback", FULL, "simple", "BudgetThreshold", "", "_repaired"),
    )
    for name, snapshot, level, component, before_suffix, rejected_suffix in cases:
        state = json.loads((snapshot / f"repair_reports/{level}/{component}_repair_history.json").read_text(encoding="utf-8"))["state"]
        code = (snapshot / f"pipeline/{level}/{component}{before_suffix}.san").read_text(encoding="utf-8")
        bad = (snapshot / f"pipeline/{level}/{component}{rejected_suffix}.san").read_text(encoding="utf-8")
        repair = ReplayCandidate(bad, OUTPUT / name / "rejected.san")
        # Isolate the acceptance gate from normalization; this is not a model rerun.
        with patch.object(RepairStage, "_deterministic_repair_plan", side_effect=lambda candidate, *_: (candidate, [])):
            result = run_replay(state, code, name, repair).state
        assert result["retained_previous_candidate"] and result["final_code"] == code
        assert Path(result["rejected_candidate_file"]).read_text(encoding="utf-8") == bad
        assert not result["final_passed"]
        results["checks"][name] = {
            "previous_candidate_retained": True, "final_passed": result["final_passed"],
            "stop_reason": result["stop_reason"], "gate": result["repair_regression_gate"],
            "final_file": str(Path(result["final_file_path"]).relative_to(ROOT)),
            "final_sha256": digest(Path(result["final_file_path"])),
            "rejected_file": str(Path(result["rejected_candidate_file"]).relative_to(ROOT)),
        }
    (OUTPUT / "replay.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"llm_requests": 0, "checks": list(results["checks"]), "output": str(OUTPUT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
