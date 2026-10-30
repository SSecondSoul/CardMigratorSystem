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
    if lost_bindings or introduced.get("invalid_san_event_handler_syntax"):
        decision = "reject"
    elif introduced or new_aliases:
        decision = "review"
    else:
        decision = "pass"
    return {
        "decision": decision,
        "should_stop": decision != "pass",
        "introduced_event_error_codes": introduced,
        "additional_unresolved_source_bindings": lost_bindings,
        "before": before,
        "after": after,
        "boundary": "Plausible handle-prefixed aliases are not proof of equivalent behavior; invalid syntax remains a separate validation failure.",
    }
