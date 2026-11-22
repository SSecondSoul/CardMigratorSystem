"""Shared generation/repair constraint; the AST validator remains authoritative."""
CLASS_BINDING_RULE = (
    "Object-style Vue :class bindings must be converted to a San string expression. "
    "Each template element must have exactly one class attribute; merge static and dynamic classes. "
    "Class binding contract (parent AND every inline child): use one class attribute per element. "
    "Convert every literal-key Vue :class object entry to its complete conditional string, "
    "preserving all keys, conditions, dependencies and static classes. For example "
    "class=\"task-manager {{ isDarkMode ? 'dark-theme' : '' }} {{ isCompactMode ? 'compact-mode' : '' }}\". "
    "Never emit class=\"base {{ 'dark-theme': isDarkMode, 'compact-mode': isCompactMode }}\" "
    "or class=\"{{ { active: flag } }}\" or class=\"{{{ selected: condition }}}\" triple-brace object syntax. San may accept only a literal "
    "prefix without reporting a compile error; compile success is not full-expression or behavior proof. "
    "Do not replace conditions with always-on class tokens. Do not guess dynamic keys, spreads or "
    "unmapped source scopes; keep unsupported cases explicit for review.\n"
)
CLASS_BINDING_CODES = frozenset({
    'invalid_object_class_binding', 'source_class_binding_not_landed',
    'source_class_binding_unproven', 'class_binding_analysis_unavailable',
})
