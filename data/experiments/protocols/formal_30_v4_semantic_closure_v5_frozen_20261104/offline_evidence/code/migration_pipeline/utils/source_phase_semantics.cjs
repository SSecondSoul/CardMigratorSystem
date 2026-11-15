// Source-proven parent repairs only. This module parses code; it never runs it.
const parser = require('@babel/parser');
const generate = require('@babel/generator').default;
const {parse} = require('@vue/compiler-dom');
const {parse: parseSFC} = require('@vue/compiler-sfc');
const traverse = require('@babel/traverse').default;
const startupPhase = require('./startup_phase_semantics.cjs');
const preserveMethods = require('./method_interface_semantics.cjs');
const key = p => !p.computed && p.key && (p.key.name || p.key.value);
const one = (obj, name) => {
  const ps = obj?.properties?.filter(p => key(p) === name) || [];
  return ps.length === 1 ? ps[0] : null;
};
const method = n => n?.type === 'ObjectMethod' && !n.async && !n.generator && n.kind === 'method';
const clean = n => {
  if (Array.isArray(n)) return n.map(clean);
  if (!n || typeof n !== 'object') return n;
  return Object.fromEntries(Object.entries(n).filter(([k]) =>
    !['loc', 'start', 'end', 'extra', 'leadingComments', 'trailingComments', 'innerComments'].includes(k))
    .map(([k, v]) => [k, clean(v)]));
};
const canonical = n => generate(clean(n), {compact: true, comments: false, jsescOption: {minimal: true}}).code;
const same = (a, b) => canonical(a) === canonical(b);
const thisMember = (n, name) => n?.type === 'MemberExpression' && !n.computed
  && n.object.type === 'ThisExpression' && (!name || n.property.name === name);
const callName = stmt => stmt?.type === 'ExpressionStatement' && stmt.expression.type === 'CallExpression'
  && thisMember(stmt.expression.callee) && stmt.expression.callee.property.name;
const simpleCall = (stmt, parent) => {
  const name = callName(stmt), node = name && one(parent, name);
  return name && method(node) && !node.params.length && !stmt.expression.arguments.length;
};
function shadowsGlobals(ast) {
  let shadowed = false;
  traverse(ast, {Program(path) {
    shadowed = ['localStorage', 'JSON'].some(n => !!path.scope.getBinding(n));
    path.stop();
  }});
  return shadowed;
}

function sourceInfo(vue) {
  const {descriptor, errors} = parseSFC(vue);
  if (errors.length || !descriptor.script || !descriptor.template || descriptor.scriptSetup) return null;
  const ast = parser.parse(descriptor.script.content, {sourceType: 'unambiguous'});
  const exports = ast.program.body.flatMap(n => {
    if (n.type === 'ExportDefaultDeclaration') return [n.declaration];
    const e = n.type === 'ExpressionStatement' && n.expression;
    return e?.type === 'AssignmentExpression' && e.operator === '=' && e.left.type === 'MemberExpression'
      && !e.left.computed && e.left.object.name === 'module' && e.left.property.name === 'exports' ? [e.right] : [];
  });
  if (exports.length !== 1 || exports[0].type !== 'ObjectExpression') return null;
  const object = exports[0];
  // Spread/mixins/computed keys make the source options ambiguous.
  if (object.properties.some(p => !key(p)) || one(object, 'mixins') || one(object, 'extends')) return null;
  return {object, script: descriptor.script.content, template: descriptor.template.content, ast};
}

// Translate only this.<declared-state> reads. Method calls stay as calls.
function translated(node, names, methods) {
  const walk = (n, parent, field) => {
    if (!n || typeof n !== 'object') return n;
    if (Array.isArray(n)) return n.map(x => walk(x, parent, field));
    if (n.type === 'ThisExpression') throw new Error('Unsupported source this access');
    if (thisMember(n)) {
      const name = n.property.name;
      if (parent?.type === 'CallExpression' && field === 'callee' && methods.has(name)) return n;
      if (!names.has(name) || parent?.type === 'AssignmentExpression' || parent?.type === 'UpdateExpression')
        throw new Error('Unsupported state translation');
      return parser.parseExpression(`this.data.get(${JSON.stringify(name)})`);
    }
    const out = {...n};
    for (const [k, v] of Object.entries(n)) if (v && typeof v === 'object' && !['loc', 'extra', 'comments'].includes(k))
      out[k] = walk(v, n, k);
    return out;
  };
  return walk(node, null, '');
}

function loopNodes(template, source) {
  const root = parse(template); // Any template parse error refuses the repair.
  const rows = [];
  const visit = (n, loop) => {
    if (n.type === 1) {
      const attr = source ? n.props.find(p => p.type === 7 && p.name === 'for')
        : n.props.find(p => p.type === 6 && p.name === 's-for');
      if (attr) {
        const text = source ? attr.exp?.content : attr.value?.content;
        const match = /^\s*\(?\s*([\w$]+)(?:\s*,\s*[\w$]+)?\s*\)?\s+in\s+([\w$]+)(?:\s+trackby\s+[\w$.]+)?\s*$/.exec(text || '');
        loop = match ? {alias: match[1], collection: match[2]} : null;
      }
      for (const p of n.props) {
        if (source && p.type === 7 && p.name === 'on' && p.arg?.isStatic && !p.modifiers.length)
          rows.push({tag: n.tag, event: p.arg.content, expression: p.exp?.content, loop, attr: p});
        if (!source && p.type === 6 && p.name.startsWith('on-'))
          rows.push({tag: n.tag, event: p.name.slice(3), expression: p.value?.content, loop, attr: p});
      }
    }
    for (const child of n.children || []) visit(child, loop);
  };
  visit(root, null);
  return rows;
}

function repairPayload(ctx, src, methods, names) {
  const {input, parent, script, offset, edit, changes, sourceHandler} = ctx;
  const outer = /<template\b[^>]*>([\s\S]*?)<\/template\s*>/i.exec(input.code);
  if (!outer || methods?.type !== 'ObjectExpression') return;
  const sources = loopNodes(src.template, true), targets = loopNodes(outer[1], false);
  for (const source of sources) {
    const m = /^([\w$]+)\(([\w$]+)\)$/.exec(source.expression || '');
    if (!m || !source.loop || m[2] !== source.loop.alias) continue;
    const name = m[1], original = one(methods, name), current = one(parent, name);
    if (!method(original) || original.params.length !== 1 || original.params[0].name !== m[2]
        || !method(current) || current.params.length !== 1 || current.params[0].type !== 'Identifier') continue;
    const selected = targets.filter(b => b.tag === source.tag && b.event === source.event
      && b.expression === name && b.loop?.alias === source.loop.alias
      && b.loop?.collection === source.loop.collection);
    if (selected.length !== 1 || sources.filter(s => s.expression?.startsWith(name + '(')).length !== 1
        || targets.filter(s => s.expression === name || s.expression?.startsWith(name + '(')).length !== 1) continue;
    // Refuse handlers also referenced from script or uncertain dynamic source.
    if (new RegExp('\\bthis\\.' + name + '\\b').test(script.slice(parent.start, parent.end))) continue;
    const restored = sourceHandler({name, params: [m[2]], body_full: src.script.slice(original.body.start, original.body.end)}, parent, names);
    if (!restored) continue;
    const body = current.body.body, replacement = parser.parseExpression(`({${restored}})`).properties[0];
    if (same(current, replacement)) {
      if (input.repair) {
        const attr = selected[0].attr;
        const start = outer.index + outer[0].indexOf('>') + 1;
        edit(start + attr.loc.start.offset, start + attr.loc.end.offset, `on-${source.event}="${source.expression}"`);
        changes.push('restored_source_loop_argument_binding');
      }
      continue;
    }
    if (body.length !== replacement.body.body.length + 2) continue;
    const declaration = s => s?.type === 'VariableDeclaration' && s.kind === 'const' && s.declarations.length === 1
      && s.declarations[0].id.type === 'Identifier' && s.declarations[0];
    const array = declaration(body[0]), item = declaration(body[1]);
    if (!array || !item || !array.init || !same(array.init,
        parser.parseExpression(`this.data.get('${source.loop.collection}')`))) continue;
    const lookup = item.init;
    if (item.id.name !== m[2] || lookup?.type !== 'MemberExpression' || !lookup.computed
        || lookup.object.name !== array.id.name || lookup.property.type !== 'MemberExpression'
        || lookup.property.computed || lookup.property.object.name !== current.params[0].name
        || lookup.property.property.name !== 'index') continue;
    if (!body.slice(2).every((s, i) => same(s, replacement.body.body[i]))) continue;
    if (!input.repair) continue;
    const attr = selected[0].attr;
    const start = outer.index + outer[0].indexOf('>') + 1;
    edit(start + attr.loc.start.offset, start + attr.loc.end.offset, `on-${source.event}="${source.expression}"`);
    edit(offset + current.start, offset + current.end, restored);
    changes.push('restored_source_loop_payload_handler');
  }
}

function repairMounted(ctx, src, sourceMethods, names) {
  const {input, parent, script, offset, edit, changes, findings} = ctx;
  const mounted = one(src.object, 'mounted'), inited = one(parent, 'inited'), attached = one(parent, 'attached');
  if (!method(mounted) || mounted.params.length || !method(inited) || inited.params.length
      || !method(attached) || attached.params.length
      || ['created', 'beforeCreate', 'beforeMount'].some(n => one(src.object, n))
      || one(parent, 'compiled')) return;
  const methodNames = new Set(parent.properties.filter(method).map(key));
  const init = one(sourceMethods, 'initData');
  const expanded = [];
  for (const stmt of mounted.body.body) {
    if (callName(stmt) === 'initData') {
      if (stmt.expression.arguments.length || !method(init) || init.params.length
          || !init.body.body.length || !init.body.body.every(s => simpleCall(s, parent))) return;
      expanded.push(...init.body.body);
    } else expanded.push(stmt);
  }
  // Only no-result existing method calls, or one conditional wrapping such calls.
  const valid = s => {
    const n = callName(s);
    if (n) return methodNames.has(n) && s.expression.arguments.every(a =>
      ['StringLiteral', 'NumericLiteral', 'BooleanLiteral', 'NullLiteral'].includes(a.type));
    return s.type === 'IfStatement' && !s.alternate && s.consequent.type === 'BlockStatement'
      && s.consequent.body.every(x => callName(x) && simpleCall(x, parent))
      && s.test.type === 'MemberExpression' && !s.test.computed && thisMember(s.test.object)
      && names.has(s.test.object.property.name);
  };
  if (!expanded.length || !expanded.every(valid)) return;
  let expected;
  try { expected = expanded.map(s => translated(s, names, methodNames)); } catch (_) { return; }
  const early = inited.body.body, late = attached.body.body;
  const movedCount = expected.length - late.length;
  if (movedCount < 0 || movedCount > early.length) return;
  const prefixLength = early.length - movedCount;
  const prefix = early.slice(0, prefixLength), moved = early.slice(prefixLength);
  // Keep only source-named watcher registrations in inited. No unknown startup
  // effects may be moved across, or silently discarded from, either hook.
  const sourceWatch = one(src.object, 'watch')?.value;
  if (!prefix.every(s => callName(s) === 'watch' && s.expression.arguments.length === 2
      && s.expression.arguments[0].type === 'StringLiteral'
      && one(sourceWatch, s.expression.arguments[0].value)
      && ['ArrowFunctionExpression', 'FunctionExpression'].includes(s.expression.arguments[1].type))) return;
  const observed = [...moved, ...late];
  const sameBag = JSON.stringify(observed.map(canonical).sort()) === JSON.stringify(expected.map(canonical).sort());
  const ordered = observed.every((s, i) => same(s, expected[i]));
  if (sameBag && (moved.length || !ordered)) findings.push({code: 'source_mounted_order_not_landed',
    location: 'script.attached', message: 'Source mounted actions must run once in attached in source order, not in inited or reordered.'});
  if (!moved.length || !ordered || !moved.every(s => simpleCall(s, parent))) return;
  if (!input.repair) return;
  // Remove only the proven suffix; preserve watcher text verbatim.
  edit(offset + moved[0].start, offset + moved[moved.length - 1].end, '');
  edit(offset + attached.body.start + 1, offset + attached.body.start + 1,
    '\n' + moved.map(s => script.slice(s.start, s.end)).join('\n') + '\n');
  changes.push('restored_source_mounted_phase_order');
}

function repairWatchPersistence(ctx, src, names) {
  const {input, parent, offset, edit, changes, findings} = ctx;
  const watch = one(src.object, 'watch')?.value, inited = one(parent, 'inited');
  if (watch?.type !== 'ObjectExpression' || !method(inited)) return;
  const methodNames = new Set(parent.properties.filter(method).map(key));
  // A locally shadowed storage/JSON is not the browser persistence contract.
  if (shadowsGlobals(src.ast) || shadowsGlobals(parser.parse(ctx.script, {sourceType: 'unambiguous'}))) return;
  for (const entry of watch.properties) {
    const path = key(entry), descriptor = entry.value;
    const handler = one(descriptor, 'handler');
    if (!path || descriptor?.type !== 'ObjectExpression'
        || descriptor.properties.some(p => !['handler', 'deep'].includes(key(p)))
        || !method(handler) || handler.params.length !== 1 || handler.params[0].type !== 'Identifier') continue;
    const param = handler.params[0].name, sourceBody = handler.body.body, last = sourceBody.at(-1);
    if (['localStorage', 'JSON'].includes(param) || sourceBody.length < 2) continue;
    const call = last.type === 'ExpressionStatement' && last.expression;
    if (call?.type !== 'CallExpression' || call.callee.type !== 'MemberExpression' || call.callee.computed
        || call.callee.object.name !== 'localStorage' || call.callee.property.name !== 'setItem'
        || call.arguments.length !== 2 || call.arguments[0].type !== 'StringLiteral') continue;
    const expectedLast = parser.parse(`localStorage.setItem(${JSON.stringify(call.arguments[0].value)}, JSON.stringify(${param}));`).program.body[0];
    if (!same(last, expectedLast)) continue;
    // No declaration or unrelated effect may be copied, only a missing trailing
    // write after an otherwise AST-identical, translated watcher body.
    if (sourceBody.slice(0, -1).some(s => s.type !== 'IfStatement' && !callName(s))) continue;
    let expected;
    try { expected = sourceBody.slice(0, -1).map(s => translated(s, names, methodNames)); } catch (_) { continue; }
    const registrations = inited.body.body.filter(s => callName(s) === 'watch'
      && s.expression.arguments[0]?.value === path);
    if (registrations.length !== 1) continue;
    const args = registrations[0].expression.arguments, listener = args[1];
    if (args.length !== 2 || !['ArrowFunctionExpression', 'FunctionExpression'].includes(listener?.type)
        || listener.async || listener.generator || listener.body.type !== 'BlockStatement') continue;
    let actual = listener.body.body;
    if (!listener.params.length) {
      const first = actual[0];
      if (first?.type !== 'VariableDeclaration' || first.kind !== 'const' || first.declarations.length !== 1
          || first.declarations[0].id.type !== 'Identifier' || first.declarations[0].id.name !== param
          || !first.declarations[0].init
          || !same(first.declarations[0].init, parser.parseExpression(`this.data.get(${JSON.stringify(path)})`))) continue;
      actual = actual.slice(1);
    } else if (listener.params.length !== 1 || listener.params[0].name !== param) continue;
    if (actual.length !== expected.length || !actual.every((s, i) => same(s, expected[i]))) continue;
    findings.push({code: 'source_watch_persistence_not_landed', location: `script.watch.${path}`,
      message: `Source watcher ${path} is missing its trailing localStorage.setItem write.`});
    if (input.repair) {
      edit(offset + listener.body.end - 1, offset + listener.body.end - 1,
        '\n' + src.script.slice(last.start, last.end) + '\n');
      changes.push('restored_source_watch_persistence');
    }
  }
}

function repairBooleanBindings(ctx, src, names) {
  const {input, parent, script, offset, edit, changes} = ctx;
  if (!input.repair) return;
  const sourceData = one(src.object, 'data'), targetData = one(parent, 'initData');
  const returned = m => method(m) && !m.params.length && m.body.body.length === 1
    && m.body.body[0].type === 'ReturnStatement' && m.body.body[0].argument?.type === 'ObjectExpression'
    ? m.body.body[0].argument : null;
  const a = returned(sourceData), b = returned(targetData);
  if (!a || !b) return;
  const outer = /<template\b[^>]*>([\s\S]*?)<\/template\s*>/i.exec(input.code);
  if (!outer) return;
  const sources = loopNodes(src.template, true), targets = loopNodes(outer[1], false), additions = new Map();
  for (const source of sources) {
    let expr;
    try {expr = parser.parseExpression(source.expression || '');} catch (_) {continue;}
    if (expr.type !== 'AssignmentExpression' || expr.operator !== '=' || expr.left.type !== 'Identifier'
        || expr.right.type !== 'BooleanLiteral' || !names.has(expr.left.name)) continue;
    const field = expr.left.name, literal = expr.right.value;
    if (one(a, field)?.value?.type !== 'BooleanLiteral' || one(b, field)?.value?.type !== 'BooleanLiteral') continue;
    const equivalent = x => {
      try {return x.tag === source.tag && x.event === source.event && same(parser.parseExpression(x.expression), expr);}
      catch (_) {return false;}
    };
    // Source .self events are deliberately absent from loopNodes: do not turn a
    // backdrop-only setter into an unconditional setter or count it as missing.
    if (sources.filter(equivalent).length !== 1) continue;
    const matches = targets.filter(equivalent);
    if (matches.length !== 1) continue;
    const contract = `${field}:${literal}`;
    let name = additions.get(contract)?.name;
    if (!name) {
      name = `__sourceSet_${field}_${literal}`;
      while (parent.properties.some(p=>key(p)===name)) name += '_';
      additions.set(contract, {name, text:`${name}() { this.data.set(${JSON.stringify(field)}, ${literal}); }`});
    }
    const attr = matches[0].attr, start = outer.index + outer[0].indexOf('>') + 1;
    edit(start + attr.loc.start.offset, start + attr.loc.end.offset, `on-${source.event}="${name}"`);
  }
  if (additions.size) {
    edit(offset + parent.start + 1, offset + parent.start + 1,
      '\n' + [...additions.values()].map(x=>x.text).join(',\n') + ',\n');
    changes.push('restored_unique_source_boolean_event_bindings');
  }
}

module.exports = function sourcePhaseRepairs(ctx) {
  if (!ctx.input.vue) return;
  const src = sourceInfo(ctx.input.vue);
  if (!src) return;
  const methods = one(src.object, 'methods')?.value;
  const names = new Set((ctx.input.ssm?.script?.options?.data || []).map(x => x.name));
  // Invalid/ambiguous template syntax must not hide independently provable
  // script lifecycle/watch findings. Template edits commit atomically only.
  const templateTransaction = fn => {
    const pending = [], changes = [], findings = [];
    const local = {...ctx, edit:(...args)=>pending.push(args), changes, findings};
    try {fn(local);} catch (_) {return;}
    pending.forEach(args=>ctx.edit(...args));
    ctx.changes.push(...changes);
    ctx.findings.push(...findings);
  };
  templateTransaction(local=>repairPayload(local, src, methods, names));
  // Avoid applying the expanded-sequence mover to a wrapper already assessed
  // here; both must not edit the same hook suffix in one transaction.
  startupPhase(ctx, src, methods, {one, method, same, callName});
  if (!ctx.changes.some(n => ['removed_source_proven_duplicate_startup',
      'relocated_source_proven_startup_wrapper'].includes(n))) repairMounted(ctx, src, methods, names);
  repairWatchPersistence(ctx, src, names);
  templateTransaction(local=>repairBooleanBindings(local, src, names));
  preserveMethods(ctx, src, methods);
};
