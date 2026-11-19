// A narrow source-proven startup wrapper contract, not a general call graph.
module.exports = function startupPhase(ctx, src, sourceMethods, tools) {
  const {one, method, same, callName} = tools;
  const {parent, offset, edit, changes, findings} = ctx;
  const hooks = new Set(['initData', 'inited', 'compiled', 'attached', 'updated', 'detached', 'disposed',
    'created', 'beforeCreate', 'beforeMount', 'mounted', 'beforeDestroy', 'destroyed']);
  const key = n => !n.computed && (n.key?.name || n.key?.value);
  const uniqueOptions = o => o?.type === 'ObjectExpression'
    && o.properties.every(p => key(p)) && new Set(o.properties.map(key)).size === o.properties.length;
  if (!uniqueOptions(src.object) || !uniqueOptions(sourceMethods) || !uniqueOptions(parent)
      || one(parent, 'mixins') || one(parent, 'extends')
      || ['created', 'beforeCreate', 'beforeMount'].some(n => one(src.object, n))) return;
  const mounted = one(src.object, 'mounted'), early = one(parent, 'inited'), late = one(parent, 'attached');
  if (!method(mounted) || mounted.params.length || !mounted.body.body.length
      || !method(early) || early.params.length || !method(late) || late.params.length) return;
  const sourceCall = mounted.body.body[0], name = callName(sourceCall), initializer = one(sourceMethods, name);
  if (!name || sourceCall.expression.arguments.length || !method(initializer) || initializer.params.length
      || !initializer.body.body.length) return;
  // A wrapper consists solely of source-declared, existing, no-argument calls.
  // No return values, writes, conditions, async work or guessing renamed callees.
  if (!initializer.body.body.every(s => {
    const n = callName(s), a = n && one(sourceMethods, n), b = n && one(parent, n);
    return n && n !== name && !hooks.has(n) && !s.expression.arguments.length
      && method(a) && !a.params.length && method(b) && !b.params.length;
  })) return;
  const aliases = parent.properties.filter(p => method(p) && !hooks.has(key(p)) && !p.params.length
    && same(p.body, initializer.body));
  if (aliases.length !== 1) return;
  const target = key(aliases[0]);
  const references = (node, wanted) => {
    const rows = []; let dynamic = false;
    const walk = n => {
      if (!n || typeof n !== 'object') return;
      if (Array.isArray(n)) {n.forEach(walk); return;}
      if (['MemberExpression', 'OptionalMemberExpression'].includes(n.type) && n.object.type === 'ThisExpression') {
        if (n.computed) dynamic = true;
        if ((!n.computed && n.property.name === wanted) || (n.computed && n.property.value === wanted)) rows.push(n);
      }
      for (const [k, v] of Object.entries(n)) if (!['loc', 'extra', 'comments'].includes(k)) walk(v);
    };
    walk(node); return {rows, dynamic};
  };
  const originalRefs = references(src.object, name);
  // The source method may not also be used by another lifecycle, event or alias.
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  if (originalRefs.dynamic || originalRefs.rows.length !== 1
      || new RegExp('(^|[^A-Za-z0-9_$])' + escaped + '(?![A-Za-z0-9_$])').test(src.template)) return;
  const calls = hook => hook.body.body.filter(s => callName(s) === target && !s.expression.arguments.length);
  const before = calls(early), after = calls(late), refs = references(parent, target);
  const contract = {source_method: name, target_method: target, expected_phase: 'attached', expected_count: 1,
    inited_direct_calls: before.length, attached_direct_calls: after.length,
    assessment: 'source_wrapper_body_and_unique_parent_alias', repairable: false};
  ctx.startup_contracts?.push(contract);
  if (!before.length && after.length === 1) return;
  // Only direct, no-argument parent hook calls are counted. Unknown calls are
  // not declared equivalent or removed; report the proven direct mismatch.
  if (!before.length && !after.length) return;
  findings.push({code: 'source_startup_phase_not_landed', location: `script.startup.${name}`,
    message: `Source mounted initializer ${name} (San ${target}) must run exactly once in attached; found inited=${before.length}, attached=${after.length}.`});
  const first = before[0];
  if (before.length !== 1 || after.length > 1 || refs.dynamic
      || refs.rows.length !== before.length + after.length
      || first !== early.body.body.at(-1) || (after.length && after[0] !== late.body.body[0])
      || one(parent, 'compiled')) return;
  // Leave only uniquely source-named watcher registrations before the suffix.
  // We do not erase their bodies or alter registration order/options.
  const watch = one(src.object, 'watch')?.value;
  const registrations = early.body.body.slice(0, -1);
  const watched = [];
  if (!registrations.every(s => {
    if (callName(s) !== 'watch' || s.expression.arguments.length !== 2) return false;
    const [field, listener] = s.expression.arguments;
    const descriptor = field.type === 'StringLiteral' && one(watch, field.value)?.value;
    if (!descriptor || descriptor.type !== 'ObjectExpression' || one(descriptor, 'immediate')
        || !['ArrowFunctionExpression', 'FunctionExpression'].includes(listener.type)
        || listener.async || listener.generator) return false;
    watched.push(field.value); return true;
  }) || new Set(watched).size !== watched.length) return;
  contract.repairable = true;
  if (!ctx.input.repair) return;
  edit(offset + first.start, offset + first.end, '');
  if (!after.length) edit(offset + late.body.start + 1, offset + late.body.start + 1,
    '\n' + ctx.script.slice(first.start, first.end) + '\n');
  changes.push(after.length ? 'removed_source_proven_duplicate_startup' : 'relocated_source_proven_startup_wrapper');
};
