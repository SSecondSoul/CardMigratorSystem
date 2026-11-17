"""Explicit, detached projections of legacy records; no file reads or writes.

Old booleans are declarations, not native evaluation or production permission.
The original JSON can be returned losslessly, but is excluded from to_dict(): it
may contain source, prompts or sensitive metadata and is not a logging payload.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .v1 import (
    ContractError, Diagnostic, DiagnosticOrigin, EvaluationResult, EvidenceLevel,
    Severity, Status, json_copy,
)


class LegacyFormat(str, Enum):
    STATE = "state"
    REPAIR_REPORT = "repair_report"
    BATCH_SAMPLE = "batch_sample"


@dataclass(frozen=True, kw_only=True)
class LegacyProjection:
    legacy_format: LegacyFormat
    phase: str
    legacy_declared_final_passed: bool | None
    legacy_stop_reason: str | None
    legacy_execution_status: str | None
    evaluations: tuple[EvaluationResult, ...]
    notes: tuple[str, ...]
    _original: dict[str, Any] = field(repr=False, compare=False)

    def to_legacy(self):
        """Return a detached original, not a rewritten legacy judgement."""
        return deepcopy(self._original)

    def to_dict(self):
        return {
            "contract_version": 1, "contract_type": "LegacyProjection",
            "scope": "legacy_read_only_not_run_admission",
            "legacy_format": self.legacy_format.value, "phase": self.phase,
            "legacy_declared_final_passed": self.legacy_declared_final_passed,
            "legacy_stop_reason": self.legacy_stop_reason,
            "legacy_execution_status": self.legacy_execution_status,
            "evaluations": [item.to_dict() for item in self.evaluations],
            "notes": list(self.notes),
        }


_METRICS = ("tree_edit_distance", "structure_similarity",
            "tag_sequence_similarity", "text_similarity")


def _diagnostic(issue, *, path, index, severity):
    raw = issue if type(issue) is dict else {"legacy_value": issue}
    code = raw.get("code")
    code = code if type(code) is str and code.strip() else "legacy_issue_without_code"
    # Even a source-looking error code or stack is not trustworthy attribution.
    return Diagnostic(
        diagnostic_id=f"{path}/{index}", code=code, stage=path.split(".")[0],
        message=raw.get("message") if type(raw.get("message")) is str else "",
        location=raw.get("location") if type(raw.get("location")) is str else "",
        origin=DiagnosticOrigin.UNKNOWN, severity=severity,
        details={"legacy_issue": json_copy(issue)},
    )


def _evaluation(raw, *, dimension, path, flag, errors, warnings):
    status, reason, diagnostics, metrics = Status.NOT_RUN, "legacy_result_absent", [], {}
    if raw is not None:
        status, reason = Status.UNKNOWN, "legacy_boolean_missing_or_invalid"
        if type(raw) is not dict:
            status, reason = Status.BLOCKED, "legacy_result_malformed"
        else:
            for name in _METRICS:
                if name in raw:
                    metrics[name] = raw[name]
            declared = raw.get(flag, raw.get("passed"))
            if type(declared) is bool:
                status = Status.PASS if declared else Status.FAIL
                reason = "legacy_declaration_only_not_verified"
            if (flag != "passed" and flag in raw and "passed" in raw
                    and (type(raw[flag]) is not bool or type(raw["passed"]) is not bool
                         or raw[flag] != raw["passed"])):
                status, reason = Status.BLOCKED, "legacy_conflicting_flags"
            for key, severity in ((errors, Severity.ERROR), (warnings, Severity.WARNING)):
                issues = raw.get(key, [])
                if type(issues) is not list:
                    status, reason = Status.BLOCKED, "legacy_issue_list_malformed"
                    continue
                diagnostics.extend(_diagnostic(issue, path=f"{path}.{key}", index=i, severity=severity)
                                   for i, issue in enumerate(issues))
            # Compact reports retain counts instead of issue bodies.
            for key in ("error_count", "warning_count"):
                count = raw.get(key, 0)
                if type(count) is not int or count < 0:
                    status, reason = Status.BLOCKED, "legacy_issue_count_invalid"
                elif count > 0:
                    diagnostics.append(_diagnostic(
                        {"code": "legacy_issue_details_unavailable", "count": count},
                        path=f"{path}.{key}", index=0,
                        severity=Severity.ERROR if key == "error_count" else Severity.WARNING,
                    ))
            if raw.get("skipped") is True and status is not Status.BLOCKED:
                status, reason = Status.NOT_RUN, "legacy_skipped_not_passed"
            elif "skipped" in raw and type(raw["skipped"]) is not bool:
                status, reason = Status.BLOCKED, "legacy_skipped_flag_invalid"
            if status is Status.PASS and diagnostics:
                status, reason = Status.BLOCKED, "legacy_pass_has_unattributed_diagnostics"
    return EvaluationResult(
        evaluation_id=path, dimension=dimension, status=status,
        evidence_level=EvidenceLevel.LEGACY_DECLARATION,
        diagnostics=tuple(diagnostics), metrics=metrics, reason=reason,
        coverage=("legacy_declared_only",),
    )


def _batch_stage(row, phase, *, visual):
    prefix = f"{phase}_visual" if visual else f"{phase}_validation"
    flag = f"{phase}_visual_eval_passed" if visual else f"{prefix}_passed"
    keys = (flag, f"{prefix}_error_codes", f"{prefix}_warning_codes")
    if not any(key in row for key in keys):
        return None
    result = {"passed": row.get(flag)}
    for suffix, target in (("error_codes", "errors"), ("warning_codes", "warnings")):
        values = row.get(f"{prefix}_{suffix}", [])
        result[target] = ([{"code": value} for value in values]
                          if type(values) is list else values)
    if visual:
        for name in _METRICS:
            if f"{phase}_{name}" in row:
                result[name] = row[f"{phase}_{name}"]
    return result


def project_legacy(payload, *, legacy_format: LegacyFormat, phase="final"):
    """Project one state, repair report or batch sample. Never guess the format.

    Initial/final never fall back to flat state defaults or another phase.
    No revision lineage, source ownership, cost totals or evaluator versions are
    invented. Unknown fields/history remain in the detached original only.
    """
    if type(legacy_format) is not LegacyFormat:
        raise ContractError("legacy_format must be an explicit LegacyFormat")
    if phase not in ("initial", "current", "final"):
        raise ContractError("Unknown legacy phase")
    original = json_copy(payload)
    if type(original) is not dict:
        raise ContractError("Legacy record must be a JSON object")
    if "schemaVersion" in original or "contract_type" in original:
        raise ContractError("Browser/new contract records require their own explicit adapter")
    notes = ["read_only_declaration_not_production_admission",
             "no_origin_revision_or_dependency_binding_inferred"]
    flag, stop, interaction, compile_result = None, None, None, None
    if legacy_format is LegacyFormat.STATE:
        if any(key in original for key in ("samples", "aggregate", "inputs", "summary")):
            raise ContractError("Expected state, not a batch/report envelope")
        prefix = "" if phase == "current" else f"{phase}_"
        validation = original.get(f"{prefix}validate_result")
        visual = original.get(f"{prefix}visual_eval_result")
        if phase == "current":
            # Flat dataclass defaults do not establish that a stage executed.
            notes.append("flat_state_defaults_not_used_as_execution_evidence")
        flag, stop = original.get("final_passed"), original.get("stop_reason")
        if type(validation) is dict:
            compile_result = validation.get("san_compile_result")
        if phase == "final":
            interaction = original.get("interaction_eval_result")
        errors, warnings = "validation_errors", "validation_warnings"
        verrors, vwarnings, vflag = "visual_eval_errors", "visual_eval_warnings", "visual_eval_passed"
        validation_flag = "validation_passed"
    elif legacy_format is LegacyFormat.REPAIR_REPORT:
        if phase == "current":
            raise ContractError("Compact repair report has no current phase")
        if type(original.get("summary")) is not dict:
            raise ContractError("Expected repair report summary")
        section = original.get(phase)
        if section is not None and type(section) is not dict:
            raise ContractError("Malformed repair report phase")
        section = section or {}
        validation, visual = section.get("validate"), section.get("visual_eval")
        flag, stop = original["summary"].get("final_passed"), original["summary"].get("stop_reason")
        if phase == "final" and "interaction_eval_passed" in original["summary"]:
            interaction = {"passed": original["summary"]["interaction_eval_passed"]}
        errors, warnings = "validation_errors", "validation_warnings"
        verrors, vwarnings, vflag = "visual_eval_errors", "visual_eval_warnings", "visual_eval_passed"
        validation_flag = "validation_passed"
        notes.append("compact_report_not_enriched_from_optional_state_or_external_files")
    else:
        if phase == "current":
            raise ContractError("Batch sample has no current phase")
        if "id" not in original or any(key in original for key in ("samples", "aggregate")):
            raise ContractError("Expected one batch sample, not aggregate/checkpoint")
        validation = _batch_stage(original, phase, visual=False)
        visual = _batch_stage(original, phase, visual=True)
        flag, stop = original.get("final_passed"), original.get("stop_reason")
        if phase == "final" and "interaction_eval_passed" in original:
            interaction = {"passed": original["interaction_eval_passed"]}
        errors, warnings, validation_flag = "errors", "warnings", "passed"
        verrors, vwarnings, vflag = "errors", "warnings", "passed"
        notes.append("batch_completed_means_execution_finished_not_migration_passed")
    evaluations = [
        _evaluation(validation, dimension="static_validation", path=f"{phase}.validation",
                    flag=validation_flag, errors=errors, warnings=warnings),
        _evaluation(compile_result, dimension="san_compile", path=f"{phase}.compile",
                    flag="passed", errors="diagnostics", warnings="warnings"),
        _evaluation(visual, dimension="legacy_dom", path=f"{phase}.visual",
                    flag=vflag, errors=verrors, warnings=vwarnings),
        _evaluation(interaction, dimension="legacy_interaction", path=f"{phase}.interaction",
                    flag="passed", errors="errors", warnings="warnings"),
    ]
    for dimension in ("native_runtime", "browser_visual", "browser_interaction"):
        evaluations.append(_evaluation(None, dimension=dimension, path=f"{phase}.{dimension}",
                                       flag="passed", errors="errors", warnings="warnings"))
    execution_status = original.get("status") if legacy_format is LegacyFormat.BATCH_SAMPLE else None
    if execution_status == "error":
        evaluations.append(EvaluationResult(
            evaluation_id=f"{phase}.pipeline_execution", dimension="pipeline_execution",
            status=Status.EXECUTION_ERROR, evidence_level=EvidenceLevel.LEGACY_DECLARATION,
            reason="legacy_batch_execution_error_not_attributed_to_target",
        ))
    if type(flag) is not bool and flag is not None:
        notes.append("invalid_legacy_final_passed_preserved_in_original")
    return LegacyProjection(
        legacy_format=legacy_format, phase=phase,
        legacy_declared_final_passed=flag if type(flag) is bool else None,
        legacy_stop_reason=stop if type(stop) is str else None,
        legacy_execution_status=execution_status if type(execution_status) is str else None,
        evaluations=tuple(evaluations), notes=tuple(notes), _original=original,
    )
