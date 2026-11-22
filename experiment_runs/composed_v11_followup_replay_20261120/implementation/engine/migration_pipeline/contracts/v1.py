"""Strict, JSON-compatible value contracts. No I/O, execution or admission authority.

Constructors check types; from_dict also rejects unknown fields/schema versions.
Nested JSON is copied at construction/export, not advertised as deeply immutable.
Hashes describe identities, not proof that files or evaluation claims were verified.
"""
from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields, is_dataclass
from enum import Enum
import math
import re
from types import UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints


class ContractError(ValueError):
    """Malformed or internally inconsistent contract value."""


class Status(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"
    NOT_RUN = "not_run"
    UNSUPPORTED = "unsupported"
    EXECUTION_ERROR = "execution_error"
    UNKNOWN = "unknown"


class DiagnosticOrigin(str, Enum):
    SOURCE = "source"
    TARGET = "target"
    INFRASTRUCTURE = "infrastructure"
    EVIDENCE = "evidence"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    UNKNOWN = "unknown"


class Repairability(str, Enum):
    RULE = "rule"
    MODEL = "model"
    NOT_REPAIRABLE = "not_repairable"
    UNKNOWN = "unknown"


class EvidenceLevel(str, Enum):
    LEGACY_DECLARATION = "legacy_declaration"
    STATIC = "static"
    LIGHTWEIGHT_DOM = "lightweight_dom"
    METHOD_PROJECTION = "method_projection"
    NATIVE_INSTANCE = "native_instance"
    BROWSER = "browser"
    MANUAL = "manual"


class ArtifactOrigin(str, Enum):
    GENERATION = "generation"
    RULE = "rule"
    MODEL = "model"
    MANUAL = "manual"


class RepairAction(str, Enum):
    RULE = "rule"
    MODEL = "model"
    BLOCK = "block"
    STOP = "stop"


class CandidateAction(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    NOT_EVALUATED = "not_evaluated"


def json_copy(value: Any, path: str = "value") -> Any:
    """Copy strictly JSON data; reject NaN, coercible keys and arbitrary objects."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is list:
        return [json_copy(item, f"{path}[{i}]") for i, item in enumerate(value)]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: json_copy(item, f"{path}.{key}") for key, item in value.items()}
    raise ContractError(f"{path}: expected finite JSON data")


def _typed(value, expected, path, *, decode=False):
    if expected is Any:
        return json_copy(value, path)
    origin, args = get_origin(expected), get_args(expected)
    if origin in (Union, UnionType):
        for option in args:
            try:
                return _typed(value, option, path, decode=decode)
            except ContractError:
                pass
        raise ContractError(f"{path}: wrong union value")
    if expected is type(None):
        if value is None:
            return None
    elif isinstance(expected, type) and issubclass(expected, Enum):
        if type(value) is expected:
            return value
        if decode and type(value) is str:
            try:
                return expected(value)
            except ValueError:
                pass
    elif isinstance(expected, type) and is_dataclass(expected):
        if decode:
            return _decode_fields(expected, value, path)
        if type(value) is expected:
            value._validate()
            return value
    elif origin is tuple and len(args) == 2 and args[1] is Ellipsis:
        if type(value) is (list if decode else tuple):
            return tuple(_typed(item, args[0], f"{path}[{i}]", decode=decode)
                         for i, item in enumerate(value))
    elif origin is dict and args == (str, Any):
        if type(value) is dict:
            return json_copy(value, path)
    elif expected in (str, bool, int) and type(value) is expected:
        return value
    elif expected is float and (type(value) is int or
                               (type(value) is float and math.isfinite(value))):
        return value
    raise ContractError(f"{path}: expected {expected}")


def _decode_fields(cls, payload, path):
    if type(payload) is not dict:
        raise ContractError(f"{path}: expected object")
    declared = {item.name: item for item in fields(cls)}
    if set(payload) - declared.keys():
        raise ContractError(f"{path}: unknown fields {set(payload) - declared.keys()}")
    hints = get_type_hints(cls)
    values = {}
    for key, item in declared.items():
        if key in payload:
            values[key] = _typed(payload[key], hints[key], f"{path}.{key}", decode=True)
        elif item.default is MISSING and item.default_factory is MISSING:
            raise ContractError(f"{path}.{key}: required")
    return cls(**values)


def _encode(value):
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {item.name: _encode(getattr(value, item.name)) for item in fields(value)}
    if type(value) is tuple:
        return [_encode(item) for item in value]
    return json_copy(value)


def _text(value, name):
    if not value.strip():
        raise ContractError(f"{name}: must not be blank")


def _sha(value, name):
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ContractError(f"{name}: expected lowercase SHA-256")


def _count(value, name):
    if value is not None and value < 0:
        raise ContractError(f"{name}: must be nonnegative")


class Contract:
    def __post_init__(self):
        hints = get_type_hints(type(self))
        for item in fields(self):
            checked = _typed(getattr(self, item.name), hints[item.name], item.name)
            object.__setattr__(self, item.name, checked)
        self._invariants()

    def _validate(self):
        hints = get_type_hints(type(self))
        for item in fields(self):
            _typed(getattr(self, item.name), hints[item.name], item.name)
        self._invariants()

    def _invariants(self):
        pass

    def to_dict(self):
        self._validate()
        return {"contract_version": 1, "contract_type": type(self).__name__,
                **_encode(self)}

    @classmethod
    def from_dict(cls, payload):
        data = json_copy(payload)
        if (type(data) is not dict or type(data.get("contract_version")) is not int
                or data.get("contract_version") != 1
                or data.get("contract_type") != cls.__name__):
            raise ContractError("Unsupported contract type/version")
        data.pop("contract_version")
        data.pop("contract_type")
        return _decode_fields(cls, data, cls.__name__)


@dataclass(frozen=True, kw_only=True)
class FileFingerprint(Contract):
    path: str
    sha256: str

    def _invariants(self):
        _text(self.path, "path")
        _sha(self.sha256, "sha256")


@dataclass(frozen=True, kw_only=True)
class Budget(Contract):
    max_model_repair_calls: int
    max_rule_steps: int
    max_total_tokens: int | None = None
    max_elapsed_seconds: float | None = None

    def _invariants(self):
        for item in fields(self):
            _count(getattr(self, item.name), item.name)


@dataclass(frozen=True, kw_only=True)
class MigrationRequest(Contract):
    run_id: str
    sample_id: str
    source: FileFingerprint
    protocol_sha256: str
    implementation_sha256: str
    prompt_set_sha256: str
    evaluation_policy_sha256: str
    model_config_sha256: str
    ssm_schema_version: str
    budget: Budget
    dependencies: tuple[FileFingerprint, ...] = ()
    scene_configs: tuple[FileFingerprint, ...] = ()
    props: dict[str, Any] = field(default_factory=dict)

    def _invariants(self):
        for key in ("run_id", "sample_id", "ssm_schema_version"):
            _text(getattr(self, key), key)
        for key in ("protocol_sha256", "implementation_sha256", "prompt_set_sha256",
                    "evaluation_policy_sha256", "model_config_sha256"):
            _sha(getattr(self, key), key)
        paths = [item.path for item in (self.source, *self.dependencies)]
        if len(paths) != len(set(paths)):
            raise ContractError("Duplicate source/dependency paths")


@dataclass(frozen=True, kw_only=True)
class ArtifactRevision(Contract):
    revision_id: str
    artifact: FileFingerprint
    origin: ArtifactOrigin
    parent_revision_id: str | None = None
    dependency_fingerprints: tuple[FileFingerprint, ...] = ()
    request_ref: str | None = None
    evidence_refs: tuple[str, ...] = ()

    def _invariants(self):
        _text(self.revision_id, "revision_id")
        if self.parent_revision_id == self.revision_id:
            raise ContractError("Revision cannot be its own parent")
        if self.origin in (ArtifactOrigin.RULE, ArtifactOrigin.MODEL) and not self.parent_revision_id:
            raise ContractError("Repair revision requires a parent")
        if self.origin is ArtifactOrigin.GENERATION and self.parent_revision_id is not None:
            raise ContractError("Generation revision must not inherit a previous candidate")


@dataclass(frozen=True, kw_only=True)
class Diagnostic(Contract):
    diagnostic_id: str
    code: str
    stage: str
    message: str = ""
    origin: DiagnosticOrigin = DiagnosticOrigin.UNKNOWN
    severity: Severity = Severity.UNKNOWN
    blocking: bool = True
    repairability: Repairability = Repairability.UNKNOWN
    location: str = ""
    evidence_refs: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def _invariants(self):
        for key in ("diagnostic_id", "code", "stage"):
            _text(getattr(self, key), key)
        if (self.repairability in (Repairability.RULE, Repairability.MODEL)
                and self.origin is not DiagnosticOrigin.TARGET):
            raise ContractError("Only attributed target diagnostics may declare a repair route")
        if self.origin is DiagnosticOrigin.UNKNOWN and not self.blocking:
            raise ContractError("Unknown diagnostic origin must remain blocking")


@dataclass(frozen=True, kw_only=True)
class EvaluationResult(Contract):
    evaluation_id: str
    dimension: str
    status: Status
    evidence_level: EvidenceLevel
    revision_id: str | None = None
    evaluator_version: str | None = None
    environment_sha256: str | None = None
    diagnostics: tuple[Diagnostic, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)
    thresholds: dict[str, Any] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    coverage: tuple[str, ...] = ()
    reason: str = ""

    def _invariants(self):
        for key in ("evaluation_id", "dimension"):
            _text(getattr(self, key), key)
        if self.environment_sha256 is not None:
            _sha(self.environment_sha256, "environment_sha256")
        if self.status is Status.PASS and any(item.blocking for item in self.diagnostics):
            raise ContractError("Pass conflicts with blocking diagnostics")
        if self.status in (Status.BLOCKED, Status.NOT_RUN, Status.UNSUPPORTED,
                           Status.EXECUTION_ERROR, Status.UNKNOWN) and not self.reason:
            raise ContractError("Non-conclusive evaluation requires a reason")


@dataclass(frozen=True, kw_only=True)
class CostRecord(Contract):
    generation_calls: int | None = None
    model_repair_calls: int | None = None
    rule_steps: int | None = None
    candidate_rechecks: int | None = None
    generation_tokens: int | None = None
    repair_tokens: int | None = None
    elapsed_seconds: float | None = None
    manual_lines: int | None = None
    manual_seconds: float | None = None

    def _invariants(self):
        for item in fields(self):
            _count(getattr(self, item.name), item.name)


@dataclass(frozen=True, kw_only=True)
class RepairDecision(Contract):
    decision_id: str
    input_revision_id: str
    action: RepairAction
    reason: str
    diagnostic_ids: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()
    preconditions: tuple[str, ...] = ()
    model_request_ref: str | None = None
    candidate_revision_id: str | None = None
    cost: CostRecord = field(default_factory=CostRecord)

    def _invariants(self):
        for key in ("decision_id", "input_revision_id", "reason"):
            _text(getattr(self, key), key)
        if self.action in (RepairAction.RULE, RepairAction.MODEL) and not self.diagnostic_ids:
            raise ContractError("Repair requires diagnostic references")
        if self.action is RepairAction.RULE and not (self.rule_ids and self.preconditions):
            raise ContractError("Rule repair requires rule IDs and preconditions")
        if self.action is RepairAction.MODEL and not self.model_request_ref:
            raise ContractError("Model repair requires an actual request reference")
        if self.action in (RepairAction.BLOCK, RepairAction.STOP) and self.candidate_revision_id:
            raise ContractError("Blocked/stopped decision cannot declare a produced candidate")


@dataclass(frozen=True, kw_only=True)
class CandidateDecision(Contract):
    decision_id: str
    previous_revision_id: str
    candidate_revision_id: str
    action: CandidateAction
    reason: str
    comparison_policy_sha256: str | None = None
    before_evaluation_ids: tuple[str, ...] = ()
    after_evaluation_ids: tuple[str, ...] = ()
    rollback_revision_id: str | None = None

    def _invariants(self):
        for key in ("decision_id", "previous_revision_id", "candidate_revision_id", "reason"):
            _text(getattr(self, key), key)
        if self.previous_revision_id == self.candidate_revision_id:
            raise ContractError("Candidate and previous revision IDs must differ")
        if self.comparison_policy_sha256 is not None:
            _sha(self.comparison_policy_sha256, "comparison_policy_sha256")
        if self.action is CandidateAction.ACCEPT:
            if not (self.comparison_policy_sha256 and self.before_evaluation_ids and self.after_evaluation_ids):
                raise ContractError("Acceptance requires policy and before/after evaluations")
            if self.rollback_revision_id is not None:
                raise ContractError("Accepted candidate cannot also be rolled back")
        if (self.action is CandidateAction.REJECT
                and self.rollback_revision_id != self.previous_revision_id):
            raise ContractError("Rejection must point back to the previous accepted revision")


@dataclass(frozen=True, kw_only=True)
class RunReport(Contract):
    request: MigrationRequest
    status: Status
    stop_reason: str
    required_dimensions: tuple[str, ...]
    revisions: tuple[ArtifactRevision, ...] = ()
    final_revision_id: str | None = None
    initial_results: tuple[EvaluationResult, ...] = ()
    attempt_results: tuple[EvaluationResult, ...] = ()
    final_results: tuple[EvaluationResult, ...] = ()
    repair_decisions: tuple[RepairDecision, ...] = ()
    candidate_decisions: tuple[CandidateDecision, ...] = ()
    cost: CostRecord = field(default_factory=CostRecord)
    evidence_refs: tuple[str, ...] = ()

    def _invariants(self):
        _text(self.stop_reason, "stop_reason")
        by_revision = {item.revision_id: item for item in self.revisions}
        if len(by_revision) != len(self.revisions):
            raise ContractError("Duplicate revision IDs")
        seen = set()
        for item in self.revisions:
            if item.parent_revision_id is not None and item.parent_revision_id not in seen:
                raise ContractError("Revisions must be parent-first and reference known parents")
            seen.add(item.revision_id)
        if self.final_revision_id is not None and self.final_revision_id not in seen:
            raise ContractError("Unknown final revision")
        results = (*self.initial_results, *self.attempt_results, *self.final_results)
        eval_ids = [item.evaluation_id for item in results]
        if len(eval_ids) != len(set(eval_ids)):
            raise ContractError("Duplicate evaluation IDs")
        for item in results:
            if item.revision_id is not None and item.revision_id not in seen:
                raise ContractError("Evaluation references unknown revision")
        for item in self.final_results:
            if item.revision_id is not None and item.revision_id != self.final_revision_id:
                raise ContractError("Final evaluation must describe the final revision")
        final_dimensions = [item.dimension for item in self.final_results]
        if len(final_dimensions) != len(set(final_dimensions)):
            raise ContractError("Duplicate final dimensions; use one aggregate per dimension")
        if len(self.required_dimensions) != len(set(self.required_dimensions)):
            raise ContractError("Duplicate required dimensions")
        known_diagnostics = {issue.diagnostic_id for result in results for issue in result.diagnostics}
        for item in self.repair_decisions:
            if item.input_revision_id not in seen:
                raise ContractError("Repair references unknown input revision")
            if item.candidate_revision_id is not None and item.candidate_revision_id not in seen:
                raise ContractError("Repair references unknown candidate revision")
            if not set(item.diagnostic_ids) <= known_diagnostics:
                raise ContractError("Repair references unknown diagnostics")
        for item in self.candidate_decisions:
            if item.previous_revision_id not in seen or item.candidate_revision_id not in seen:
                raise ContractError("Candidate decision references unknown revision")
            if not set((*item.before_evaluation_ids, *item.after_evaluation_ids)) <= set(eval_ids):
                raise ContractError("Candidate decision references unknown evaluations")
            by_evaluation = {result.evaluation_id: result for result in results}
            for ids, revision in ((item.before_evaluation_ids, item.previous_revision_id),
                                  (item.after_evaluation_ids, item.candidate_revision_id)):
                if any(by_evaluation[identifier].revision_id != revision for identifier in ids):
                    raise ContractError("Candidate comparison evaluation/revision mismatch")
            if item.action is CandidateAction.REJECT and self.final_revision_id == item.candidate_revision_id:
                raise ContractError("Rejected candidate cannot be reported as the final revision")
        if self.status is Status.PASS:
            by_dimension = {item.dimension: item for item in self.final_results}
            if not self.required_dimensions or self.final_revision_id is None:
                raise ContractError("Pass requires a final revision and explicit required dimensions")
            for dimension in self.required_dimensions:
                item = by_dimension.get(dimension)
                if (item is None or item.status is not Status.PASS
                        or item.revision_id != self.final_revision_id
                        or item.evidence_level is EvidenceLevel.LEGACY_DECLARATION
                        or not item.evaluator_version or not item.evidence_refs):
                    raise ContractError("Missing, unbound or legacy-only required evaluation")
            if any(item.status is not Status.PASS for item in self.final_results):
                raise ContractError("Final non-pass results cannot be hidden by the required subset")


_TYPES = {cls.__name__: cls for cls in (
    FileFingerprint, Budget, MigrationRequest, ArtifactRevision, Diagnostic,
    EvaluationResult, CostRecord, RepairDecision, CandidateDecision, RunReport,
)}


def load_contract(payload):
    """Decode a v1 contract object, never a legacy/browser record implicitly."""
    if (type(payload) is not dict or type(payload.get("contract_type")) is not str
            or payload["contract_type"] not in _TYPES):
        raise ContractError("Unknown contract type")
    return _TYPES[payload["contract_type"]].from_dict(payload)
