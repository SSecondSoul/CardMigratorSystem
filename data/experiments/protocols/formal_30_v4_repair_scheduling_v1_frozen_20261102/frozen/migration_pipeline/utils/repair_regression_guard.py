"""Conservative source-event traceability guard for focused San repairs.

An alias is evidence for review, not proof of behavioral equivalence. In
particular, this module never upgrades a failed validator result to a pass.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any


EVENT_CONTRACT_CODES = frozenset({
    "invalid_san_event_handler_syntax",
    "missing_event_handlers",
    "missing_event_bindings",
    "event_arguments_not_landed",
})
EVENT_ATTRIBUTE = re.compile(r"\bon-([\w:-]+)\s*=\s*([\"'])(.*?)\2", re.DOTALL)
CALLABLE_EXPRESSION = re.compile(r"^([A-Za-z_$][\w$]*)(\s*\(.*\))?$", re.DOTALL)
OUTER_TEMPLATE = re.compile(r"<template\b[^>]*>(.*?)</template\s*>", re.DOTALL | re.IGNORECASE)
SAN_VALUE_MODIFIERS = re.compile(r"^(?:(?:stop|prevent):)+")


def _mounted_loaded_inited_writes(
    before_code: str, after_code: str, ssm: dict[str, Any]
) -> tuple[list[str], list[str]]:
    """Find parent inited writes to fields loaded only by Vue mounted.

    This is intentionally narrower than a general state-diff: source created
    hooks, unknown SSM shapes, and nested callbacks are not assessed.
    """
    if not isinstance(ssm, dict):
        return [], []
    options = (ssm.get("script") or {}).get("options") or {}
    if not isinstance(options, dict):
        return [], []
    hooks = options.get("lifecycle_hooks") or []
    if not isinstance(hooks, list) or any(
        isinstance(hook, dict) and hook.get("vue_hook") == "created" for hook in hooks
    ):
        return [], []
    mounted = [
        hook for hook in hooks if isinstance(hook, dict)
        and hook.get("vue_hook") == "mounted" and hook.get("san_hook") == "attached"
    ]
    if len(mounted) != 1:
        return [], []
    source_data = {
        item.get("name") for item in options.get("data", [])
        if isinstance(item, dict) and item.get("name")
    }
    source_methods = {
        item.get("name"): item for item in options.get("methods", [])
        if isinstance(item, dict) and item.get("name")
    }
    mounted_body = mounted[0].get("body") or ""
    loaded_fields: set[str] = set()
    for method_name in re.findall(r"\bthis\.([A-Za-z_$][\w$]*)\s*\(", mounted_body):
        method = source_methods.get(method_name)
        if method:
            loaded_fields.update(method.get("writes_inferred") or [])
    loaded_fields &= source_data
    if not loaded_fields:
        return [], []

    from migration_pipeline.stages.repair import RepairStage

    def parent_inited_writes(code: str) -> set[str] | None:
        parent = re.search(r"\bmodule\.exports\s*=\s*san\.defineComponent\s*\(\s*\{", code)
        if not parent:
            return None
        parent_open = code.find("{", parent.start(), parent.end())
        parent_close = RepairStage._find_matching_js_brace(code, parent_open)
        if parent_close < 0:
            return None
        hook_matches = []
        hook_pattern = re.compile(r"(?m)^[ \t]*inited\s*\(\s*\)\s*\{")
        for match in hook_pattern.finditer(code, parent_open, parent_close):
            if RepairStage._js_brace_depth_at(code, parent_open + 1, match.start()) == 1:
                hook_matches.append(match)
        if len(hook_matches) != 1:
            return None
        opening = hook_matches[0].end() - 1
        closing = RepairStage._find_matching_js_brace(code, opening)
        if closing < 0 or closing > parent_close:
            return None
        body = code[opening + 1:closing]
        writes = set()
        for match in re.finditer(
            r"(?m)^[ \t]*this\.data\.set\s*\(\s*(['\"])([A-Za-z_$][\w$]*)\1\s*,",
            body,
        ):
            if RepairStage._js_brace_depth_at(body, 0, match.start()) == 1:
                writes.add(match.group(2))
        return writes

    before = parent_inited_writes(before_code)
    after = parent_inited_writes(after_code)
    if before is None or after is None:
        return [], []
    return sorted((after - before) & loaded_fields), sorted(after & loaded_fields)


def _issue_counts(issues: list[dict[str, Any]]) -> Counter[str]:
    return Counter(
        str(issue.get("code"))
        for issue in issues
        if isinstance(issue, dict) and issue.get("code") in EVENT_CONTRACT_CODES
    )


def _aliases(name: str) -> list[str]:
    aliases = ["handle" + name[:1].upper() + name[1:]]
    if name.startswith("on") and len(name) > 2 and name[2].isupper():
        aliases.append("handle" + name[2:])
    return list(dict.fromkeys(alias for alias in aliases if alias != name))


def _binding_coverage(code: str, ssm: dict[str, Any]) -> dict[str, Any]:
    match = OUTER_TEMPLATE.search(code)
    template = match.group(1) if match else ""
    script = code.split("<script", 1)[-1] if "<script" in code else ""
    available = Counter(
        (event_name, SAN_VALUE_MODIFIERS.sub("", expression.strip()))
        for event_name, _, expression in EVENT_ATTRIBUTE.findall(template)
    )
    template_model = ssm.get("template", {}) if isinstance(ssm, dict) else {}
    bindings = template_model.get("event_bindings", []) if isinstance(template_model, dict) else []
    exact: list[str] = []
    aliases: list[str] = []
    unresolved: list[str] = []
    unassessed: list[str] = []
    for item in bindings if isinstance(bindings, list) else []:
        if not isinstance(item, dict):
            continue
        event_name = str(item.get("event_name") or "").strip()
        source_expression = str(item.get("handler_expression") or "").strip()
        if not event_name or not source_expression:
            continue
        parsed = CALLABLE_EXPRESSION.fullmatch(source_expression)
        label = f"{event_name}:{source_expression}"
        if not parsed:
            unassessed.append(label)
            continue
        key = (event_name, source_expression)
        if available[key]:
            available[key] -= 1
            exact.append(label)
            continue
        name, arguments = parsed.group(1), parsed.group(2) or ""
        for alias in _aliases(name):
            alias_key = (event_name, alias + arguments)
            method_declared = re.search(
                rf"^\s*{re.escape(alias)}\s*\(", script, re.MULTILINE
            )
            if available[alias_key] and method_declared:
                available[alias_key] -= 1
                aliases.append(f"{label} -> {alias_key[1]}")
                break
        else:
            unresolved.append(label)
    return {
        "exact": exact,
        "plausible_aliases": aliases,
        "unresolved": unresolved,
        "unassessed_source_expressions": unassessed,
    }


def assess_event_contract_regression(
    *,
    ssm: dict[str, Any],
    before_code: str,
    after_code: str,
    before_errors: list[dict[str, Any]],
    after_errors: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return pass/review/reject; review and reject must never auto-pass."""
    before = _binding_coverage(before_code, ssm)
    after = _binding_coverage(after_code, ssm)
    before_counts = _issue_counts(before_errors)
    after_counts = _issue_counts(after_errors)
    introduced = {
        code: after_counts[code] - before_counts[code]
        for code in sorted(EVENT_CONTRACT_CODES)
        if after_counts[code] > before_counts[code]
    }
    lost_bindings = max(0, len(after["unresolved"]) - len(before["unresolved"]))
    new_aliases = max(0, len(after["plausible_aliases"]) - len(before["plausible_aliases"]))
    new_pre_mount_writes, unjustified_pre_mount_writes = _mounted_loaded_inited_writes(
        before_code, after_code, ssm
    )
    if lost_bindings or introduced.get("invalid_san_event_handler_syntax"):
        decision = "reject"
    elif introduced or new_aliases or unjustified_pre_mount_writes:
        decision = "review"
    else:
        decision = "pass"
    return {
        "decision": decision,
        "should_stop": decision != "pass",
        "introduced_event_error_codes": introduced,
        "additional_unresolved_source_bindings": lost_bindings,
        "new_pre_mount_state_writes": new_pre_mount_writes,
        "unjustified_pre_mount_state_writes": unjustified_pre_mount_writes,
        "before": before,
        "after": after,
        "boundary": "Plausible aliases are not proof of equivalent behavior. New parent inited writes to fields loaded by source mounted methods require review; source created hooks and nested writes are not assessed.",
    }
