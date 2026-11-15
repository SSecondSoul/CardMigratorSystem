"""Source-grounded checks and narrow repairs for DOM event semantics.

These rules deliberately do not infer behavior from component names.  They only
run when the Vue source contains the corresponding native event contract.
"""

import re


TAG = re.compile(r"<(?P<tag>[A-Za-z][\w-]*)\b(?P<attrs>[^>]*)>", re.DOTALL)
SELF = re.compile(r"@click\.self(?:\.[\w-]+)*\s*=\s*(['\"])[^'\"]+\1")
CLASS = re.compile(r"\bclass\s*=\s*(['\"])(.*?)\1", re.DOTALL)
CLICK = re.compile(r"\bon-click\s*=\s*(['\"])(.*?)\1", re.DOTALL)
IDENT = re.compile(r"^[A-Za-z_$][\w$]*$")
NATIVE_DRAG = ("dragstart", "dragend")


def _classes(attrs: str) -> set[str]:
    match = CLASS.search(attrs)
    return set(match.group(2).split()) if match else set()


def _method_is_self_guarded(script: str, expression: str) -> bool:
    # San's parser gives a bare handler the default $event argument; explicit
    # handler() has no args. Never confuse these two valid syntactic forms.
    if not re.fullmatch(r"[A-Za-z_$][\w$]*(?:\s*\(\s*\$event\s*\))?", expression.strip()):
        return False
    name = expression.strip().split("(", 1)[0]
    if not IDENT.fullmatch(name):
        return False
    match = re.search(rf"\b{re.escape(name)}\s*\([^)]*\)\s*\{{", script)
    if not match:
        return False
    # The guard is expected immediately at the start of a short wrapper.  A
    # broad search across the script would accept an unrelated method's guard.
    prefix = script[match.end():match.end() + 180]
    return bool(re.search(r"\b(?:event|e)\.target\s*===\s*(?:event|e)\.currentTarget\b", prefix))


def source_self_classes(vue: str) -> list[set[str]]:
    return [_classes(match.group("attrs")) for match in TAG.finditer(vue)
            if SELF.search(match.group("attrs")) and _classes(match.group("attrs"))]


def unguarded_self_clicks(vue: str, san_template: str, san_script: str) -> list[tuple[str, int]]:
    """Return source-matched class and occurrence for unguarded San clicks."""
    findings = []
    san_tags = list(TAG.finditer(san_template))
    seen: dict[str, int] = {}
    for source_classes in source_self_classes(vue):
        # An ambiguous class is intentionally not auto-repaired.  Pair the
        # repeated overlay tags in source order by their shared class.
        candidates = [(i, tag) for i, tag in enumerate(san_tags)
                      if source_classes & _classes(tag.group("attrs"))]
        source_class = sorted(source_classes)[0]
        source_index = seen.get(source_class, 0)
        seen[source_class] = source_index + 1
        if source_index >= len(candidates):
            continue
        index, tag = candidates[source_index]
        click = CLICK.search(tag.group("attrs"))
        if click and not _method_is_self_guarded(san_script, click.group(2)):
            findings.append((source_class, index))
    return findings


def native_drag_misbindings(vue: str, san_script: str, native_tags: set[str]) -> list[str]:
    expected = {name for name in NATIVE_DRAG
                if re.search(rf"@{name}(?:\.[\w-]+)*\s*=", vue)}
    if not expected:
        return []
    findings = []
    for tag in TAG.finditer(san_script):
        if tag.group("tag").lower() not in native_tags:
            continue
        for name in expected:
            if re.search(rf"\bon-{name[:4]}-{name[4:]}\s*=", tag.group("attrs")):
                findings.append(name)
    return sorted(set(findings))


def repair_source_events(code: str, error_codes: set[str], native_tags: set[str], vue: str = "") -> str:
    """Repair only diagnosed event shapes; never touch custom-component events."""
    result = code
    if "native_drag_event_misbound" in error_codes and vue:
        def fix_tag(match: re.Match) -> str:
            if match.group("tag").lower() not in native_tags:
                return match.group(0)
            return (match.group(0).replace("on-drag-start=", "on-dragstart=")
                    .replace("on-drag-end=", "on-dragend="))
        result = TAG.sub(fix_tag, result)

    if "missing_self_click_guard" in error_codes and vue:
        template_match = re.search(r"(<template\b[^>]*>)(.*?)(</template>)", result,
                                   re.IGNORECASE | re.DOTALL)
        script_match = re.search(r"(<script\b[^>]*>)(.*?)(</script>)", result,
                                 re.IGNORECASE | re.DOTALL)
        if not template_match or not script_match:
            return result
        script = script_match.group(2)
        unguarded = {index for _, index in unguarded_self_clicks(
            vue, template_match.group(2), script
        )}
        wrappers = []
        tag_index = 0
        def fix_overlay(match: re.Match) -> str:
            nonlocal tag_index
            current_index = tag_index
            tag_index += 1
            if current_index not in unguarded:
                return match.group(0)
            attrs = match.group("attrs")
            click = CLICK.search(attrs)
            if not click or not IDENT.fullmatch(click.group(2).strip()):
                return match.group(0)
            original = click.group(2).strip()
            # A handler requiring event/arguments cannot safely be wrapped as
            # a zero-argument call by a deterministic rewrite.
            if not re.search(rf"\b{re.escape(original)}\s*\(\s*\)\s*\{{", script):
                return match.group(0)
            if _method_is_self_guarded(script, original):
                return match.group(0)
            wrapper = "onSelfClick" + original[0].upper() + original[1:]
            if re.search(rf"\b{re.escape(wrapper)}\s*\(", script):
                return match.group(0)
            if (wrapper, original) not in wrappers:
                wrappers.append((wrapper, original))
            fixed_attrs = attrs[:click.start(2)] + f"{wrapper}($event)" + attrs[click.end(2):]
            return match.group(0).replace(attrs, fixed_attrs, 1)
        fixed_template = TAG.sub(fix_overlay, template_match.group(2))
        if wrappers:
            parent = re.search(r"module\.exports\s*=\s*san\.defineComponent\s*\(\s*\{", script)
            if not parent:
                return result
            additions = "".join(
                f"\n  {wrapper}(event) {{\n"
                f"    if (event && event.target === event.currentTarget) this.{original}();\n"
                f"  }}," for wrapper, original in wrappers
            )
            fixed_script = script[:parent.end()] + additions + script[parent.end():]
            result = (result[:template_match.start(2)] + fixed_template
                      + result[template_match.end(2):])
            shifted = re.search(r"(<script\b[^>]*>)(.*?)(</script>)", result,
                                re.IGNORECASE | re.DOTALL)
            result = result[:shifted.start(2)] + fixed_script + result[shifted.end(2):]
    return result
