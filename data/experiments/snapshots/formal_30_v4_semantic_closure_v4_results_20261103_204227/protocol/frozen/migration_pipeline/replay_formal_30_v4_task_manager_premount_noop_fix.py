"""Bounded offline replay removing two inherited parent pre-mount no-op writes."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.utils.repair_regression_guard import assess_event_contract_regression


SOURCE = ROOT / "data/experiments/snapshots/formal_30_v4_task_manager_four_residual_probe_v1_result_20261029_224507"
FIELDS = ("settings", "notification")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(directory: Path) -> None:
    for line in (directory / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if sha256(directory / relative) != expected:
            raise RuntimeError(f"Frozen evidence mismatch: {directory / relative}")


def parent_inited_span(code: str) -> tuple[int, int]:
    parent = re.search(r"\bmodule\.exports\s*=\s*san\.defineComponent\s*\(\s*\{", code)
    if not parent:
        raise RuntimeError("Exported San parent not found")
    parent_open = code.find("{", parent.start(), parent.end())
    parent_close = RepairStage._find_matching_js_brace(code, parent_open)
    if parent_close < 0:
        raise RuntimeError("Exported San parent is unbalanced")
    hook_pattern = re.compile(r"(?m)^[ \t]*inited\s*\(\s*\)\s*\{")
    hooks = [match for match in hook_pattern.finditer(code, parent_open, parent_close)
             if RepairStage._js_brace_depth_at(code, parent_open + 1, match.start()) == 1]
    if len(hooks) != 1:
        raise RuntimeError("Expected exactly one top-level parent inited hook")
    opening = hooks[0].end() - 1
    closing = RepairStage._find_matching_js_brace(code, opening)
    if closing < 0 or closing > parent_close:
        raise RuntimeError("Parent inited hook is unbalanced")
    return opening + 1, closing


def remove_redundant_parent_writes(code: str) -> str:
    start, end = parent_inited_span(code)
    body = code[start:end]
    fixed = body
    for field in FIELDS:
        getter = re.compile(
            rf"(?m)^[ \t]*const {field} = this\.data\.get\('{field}'\);\r?\n"
        )
        setter = re.compile(
            rf"(?m)^[ \t]*this\.data\.set\('{field}', {field}\);\r?\n"
        )
        if len(getter.findall(fixed)) != 1 or len(setter.findall(fixed)) != 1:
            raise RuntimeError(f"Expected exactly one parent no-op get/set pair: {field}")
        fixed = getter.sub("", fixed, count=1)
        fixed = setter.sub("", fixed, count=1)
    if fixed == body:
        raise RuntimeError("No bounded normalization applied")
    return code[:start] + fixed + code[end:]


def main() -> None:
    verify(SOURCE)
    prior = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((SOURCE / "probe_report.json").read_text(encoding="utf-8"))
    if (prior.get("automatic_passed") is not False
            or report.get("regression_gate", {}).get("decision") != "review"
            or report.get("regression_gate", {}).get("unjustified_pre_mount_state_writes") != list(FIELDS[::-1])):
        raise RuntimeError("Expected frozen review-only pre-mount write baseline")
    original = (SOURCE / "candidate.san").read_text(encoding="utf-8")
    vue_path = SOURCE / "source.vue"
    vue = vue_path.read_text(encoding="utf-8")
    if ("mounted()" not in vue or "this.loadInitialData();" not in vue
            or "this.startAutoSync();" not in vue or "this.showNotification(" not in vue):
        raise RuntimeError("Frozen Vue mounted contract changed")
    history = json.loads((ROOT / "data/experiments/snapshots/formal_30_v4_task_manager_source_events_regression_v1_TaskManager_automatic_fail_20261029_222317/repair_history.json").read_text(encoding="utf-8"))
    ssm = history["state"]["ssm"]
    validator = ValidateStage()
    before = validator.run(ValidateStageInput(
        generated_code=original, ssm=ssm, vue_file_path=str(vue_path),
    ))
    if not before.validation_passed:
        raise RuntimeError("Frozen probe candidate no longer validates")
    candidate = remove_redundant_parent_writes(original)
    after = validator.run(ValidateStageInput(
        generated_code=candidate, ssm=ssm, vue_file_path=str(vue_path),
    ))
    visual = VisualEvalStage().run(VisualEvalStageInput(
        vue_file_path=str(vue_path), generated_code=candidate,
    ))
    gate = assess_event_contract_regression(
        ssm=ssm, before_code=original, after_code=candidate,
        before_errors=before.validation_errors, after_errors=after.validation_errors,
    )
    if (not after.validation_passed or not visual.visual_eval_passed
            or gate["decision"] != "pass" or gate["should_stop"]):
        raise RuntimeError("Bounded candidate failed static, visual, or event gate")
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / f"formal_30_v4_task_manager_premount_noop_candidate_{stamp}"
    target.mkdir(parents=True, exist_ok=False)
    files = {
        "source.vue": vue_path,
        "prepared_input.san": SOURCE / "candidate.san",
        "prior_probe_report.json": SOURCE / "probe_report.json",
    }
    for name, source in files.items():
        shutil.copy2(source, target / name)
    (target / "candidate.san").write_text(candidate, encoding="utf-8")
    result = {
        "classification": "reused_development_bounded_offline_candidate",
        "independent_holdout": False,
        "source_snapshot": SOURCE.name,
        "input_sha256": sha256(SOURCE / "candidate.san"),
        "candidate_sha256": sha256(target / "candidate.san"),
        "removed_parent_inited_noop_fields": list(FIELDS),
        "validation_passed": after.validation_passed,
        "validation_error_codes": [issue["code"] for issue in after.validation_errors],
        "san_compile_passed": bool(after.san_compile_result and after.san_compile_result.get("passed")),
        "visual_eval_passed": visual.visual_eval_passed,
        "structure_similarity": visual.structure_similarity,
        "event_gate_decision": gate["decision"],
        "event_gate_detail": gate,
        "automatic_pipeline_passed": False,
        "browser_manual_review": "pending",
    }
    (target / "replay_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    manifest = {
        "snapshot_id": target.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        **{key: result[key] for key in (
            "classification", "independent_holdout", "source_snapshot", "candidate_sha256",
            "automatic_pipeline_passed", "browser_manual_review",
        )},
        "integrity_file": "SHA256SUMS.txt",
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    payloads = sorted(path for path in target.iterdir() if path.is_file())
    (target / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.name}" for path in payloads) + "\n", encoding="utf-8",
    )
    verify(target)
    print(f"candidate: {target.relative_to(ROOT)} ({len(payloads)} verified payloads)")
    print(f"validation: {after.validation_passed}; compile: {result['san_compile_passed']}; visual: {visual.visual_eval_passed}")
    print(f"event_gate: {gate['decision']}; browser_manual_review: pending")


if __name__ == "__main__":
    main()
