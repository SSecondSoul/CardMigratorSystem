// Source-proven trailing watcher persistence. Parse only; never execute a SFC.
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const generate = require('@babel/generator').default;
const t = require('@babel/types');

function nodePath(ast, node) {
  let result;
  traverse(ast, {enter(path) {if (path.node === node) {result = path; path.stop();}}});
  return result;
}
function visit(node, fn) {
  if (!node || typeof node !== 'object') return;
  if (Array.isArray(node)) {node.forEach(n => visit(n, fn)); return;}
  fn(node);
  for (const [key, value] of Object.entries(node))
    if (!['loc', 'extra', 'comments', 'tokens'].includes(key)) visit(value, fn);
}
function normalized(body, params, bindingName, sentinel) {
  const fn = t.functionExpression(null, params.map(p => t.cloneNode(p, true)),
    t.blockStatement(body.map(s => t.cloneNode(s, true))));
  const ast = t.file(t.program([t.expressionStatement(fn)]));
  traverse(ast, {FunctionExpression(path) {
    if (path.node !== fn) return;
    const binding = path.scope.getBinding(bindingName);
    if (!binding) throw Error('Missing watcher value binding');
    binding.scope.rename(bindingName, sentinel);
    path.stop();
  }});
  return fn.body.body;
}
function freshName(source, target) {
  const names = new Set();
  for (const node of [source, target]) visit(node, n => {if (n.type === 'Identifier') names.add(n.name);});
  let name = '__sourceWatchValue';
  while (names.has(name)) name += '_';
  return name;
}
function globalsUnbound(path) {
  return path && !['JSON', 'localStorage'].some(name => path.scope.getBinding(name));
}
function hasRiskyFlow(nodes) {
  let risky = false;
  visit(nodes, n => {
    if (t.isFunction(n) || ['ReturnStatement', 'ThrowStatement', 'TryStatement', 'AwaitExpression',
      'YieldExpression', 'WithStatement', 'ForStatement', 'ForOfStatement', 'ForInStatement',
      'WhileStatement', 'DoWhileStatement', 'SwitchStatement', 'BreakStatement', 'ContinueStatement',
      'VariableDeclaration', 'ClassDeclaration', 'Super', 'MetaProperty'].includes(n.type)) risky = true;
    if (n.type === 'CallExpression' && n.callee.type === 'Identifier' && n.callee.name === 'eval') risky = true;
    if (n.type === 'Identifier' && n.name === 'arguments') risky = true;
  });
  return risky;
}

module.exports = function watchPersistence(ctx, src, names, helpers) {
  const {one, key, method, same, callName, translated} = helpers;
  const {parent, input, offset, edit, changes, findings} = ctx;
  const contracts = ctx.watcher_contracts || [];
  const watch = one(src.object, 'watch')?.value, inited = one(parent, 'inited');
  if (watch?.type !== 'ObjectExpression' || !method(inited)) return;
  const methodNames = new Set(parent.properties.filter(method).map(key));
  for (const entry of watch.properties) {
    const path = key(entry), descriptor = entry.value, handler = one(descriptor, 'handler');
    if (!path || watch.properties.filter(p => key(p) === path).length !== 1
        || descriptor?.type !== 'ObjectExpression'
        || descriptor.properties.some(p => !['handler', 'deep'].includes(key(p)))
        || !method(handler) || handler.params.length !== 1 || handler.params[0].type !== 'Identifier') continue;
    const sourcePath = nodePath(src.ast, handler), sourceParam = handler.params[0].name;
    if (!globalsUnbound(sourcePath) || ['JSON', 'localStorage'].includes(sourceParam)) continue;
    const sourceBinding = sourcePath.scope.getBinding(sourceParam);
    if (!sourceBinding || sourceBinding.constantViolations.length) continue;
    const body = handler.body.body, last = body.at(-1), call = last?.type === 'ExpressionStatement' && last.expression;
    if (call?.type !== 'CallExpression' || call.callee.type !== 'MemberExpression' || call.callee.computed
        || call.callee.object.name !== 'localStorage' || call.callee.property.name !== 'setItem'
        || call.arguments.length !== 2 || call.arguments[0].type !== 'StringLiteral') continue;
    const expectedLast = parser.parse(`localStorage.setItem(${JSON.stringify(call.arguments[0].value)}, JSON.stringify(${sourceParam}));`).program.body[0];
    if (!same(last, expectedLast)) continue;
    const registrations = inited.body.body.filter(s => callName(s) === 'watch' && s.expression.arguments[0]?.value === path);
    // A missing/opaque registration has separate watcher diagnostics. This rule
    // does not guess which of multiple callbacks represents the source handler.
    if (registrations.length !== 1) continue;
    const args = registrations[0].expression.arguments, listener = args[1];
    if (!['ArrowFunctionExpression', 'FunctionExpression'].includes(listener?.type)
        || listener.body.type !== 'BlockStatement') continue;
    const record = {path, storage_key: call.arguments[0].value, source_parameter: sourceParam,
      source_handler: src.script.slice(handler.start, handler.end),
      target_parameters: listener.params.map(p => p.name || p.type), status: 'unproven',
      repairable: false, reason: 'unsupported_target_signature_or_scope'};
    contracts.push(record);
    const listenerPath = nodePath(ctx.ast, listener);
    let targetName, binding, actual = listener.body.body, prefix = [];
    const simpleParams = listener.params.length <= 2 && listener.params.every(p => p.type === 'Identifier');
    if (simpleParams && listener.params.length) {
      targetName = listener.params[0].name;
      binding = listenerPath?.scope.getBinding(targetName);
    } else if (!listener.params.length) {
      const first = actual[0], declaration = first?.type === 'VariableDeclaration' && first.kind === 'const'
        && first.declarations.length === 1 && first.declarations[0];
      if (declaration?.id.type === 'Identifier' && declaration.init
          && same(declaration.init, parser.parseExpression(`this.data.get(${JSON.stringify(path)})`))) {
        targetName = declaration.id.name;
        binding = listenerPath?.scope.getBinding(targetName);
        prefix = [first]; actual = actual.slice(1);
      }
    }
    const targetGlobals = globalsUnbound(listenerPath);
    let possibleWrites = 0;
    visit(listener.body, n => {
      if (n.type === 'CallExpression' && n.callee.type === 'MemberExpression'
          && !n.callee.computed && n.callee.object.name === 'localStorage'
          && n.callee.property.name === 'setItem'
          && (n.arguments[0]?.type !== 'StringLiteral' || n.arguments[0].value === call.arguments[0].value))
        possibleWrites++;
    });
    let existingLast;
    if (binding && targetGlobals && !binding.constantViolations.length) {
      // Binding-aware alpha conversion preserves property names, strings and
      // nested lexical bindings; never text-replace parameter spellings.
      const sentinel = freshName(handler, listener);
      try {
        const target = normalized(listener.body.body, listener.params, targetName, sentinel);
        const source = normalized(body, handler.params, sourceParam, sentinel);
        existingLast = target.at(-1) && same(target.at(-1), source.at(-1))
          && possibleWrites === 1 && !hasRiskyFlow(actual);
      } catch (_) { /* Unprovable is not a successful preservation check. */ }
    }
    if (existingLast) {record.status = 'trailing_write_present'; record.reason = null; continue;}
    // Detection is intentionally wider than automatic restoration. Changed
    // callback bodies, used old-value parameters and complex signatures remain
    // reported even when inserting source code cannot be proven safe.
    const possibleWrite = possibleWrites > 0;
    const code = possibleWrite ? 'source_watch_persistence_unproven' : 'source_watch_persistence_not_landed';
    findings.push({code, location: `script.watch.${path}`,
      message: possibleWrite
        ? `Source watcher ${path} has a possible storage write, but its trailing effect/exception behavior is unproven.`
        : `Source watcher ${path} is missing its trailing localStorage.setItem write.`});
    record.status = 'trailing_write_not_proven';
    record.write_presence = possibleWrite ? 'present_or_opaque' : 'absent';
    // An existing wrapped/conditional/opaque write needs behavioral review;
    // never append a duplicate or strip exception handling automatically.
    if (possibleWrite) {record.reason = 'existing_write_effect_or_exception_behavior_unproven'; continue;}
    if (args.length !== 2 || listener.async || listener.generator || !simpleParams
        || !targetName || !binding || binding.constantViolations.length || !targetGlobals) continue;
    if (listener.params.length === 2) {
      const old = listenerPath.scope.getBinding(listener.params[1].name);
      if (!old || old.referencePaths.length || old.constantViolations.length) {
        record.reason = 'old_value_parameter_used'; continue;
      }
    }
    if (body.length < 2 || hasRiskyFlow(body.slice(0, -1)) || hasRiskyFlow(actual)
        || body.slice(0, -1).some(s => s.type !== 'IfStatement' && !callName(s))) {
      record.reason = 'unsupported_callback_effects'; continue;
    }
    let expected, observed;
    const sentinel = freshName(handler, listener);
    try {
      const translatedBody = body.slice(0, -1).map(s => translated(s, names, methodNames));
      expected = normalized(translatedBody, handler.params, sourceParam, sentinel);
      observed = normalized(listener.body.body, listener.params, targetName, sentinel).slice(prefix.length);
    } catch (_) {record.reason = 'unproven_source_state_translation'; continue;}
    if (observed.length !== expected.length || !observed.every((s, i) => same(s, expected[i]))) {
      record.reason = 'callback_body_differs'; continue;
    }
    // Reuse the target's current-value binding. No new parameter, event,
    // lifecycle action, condition or callback body is introduced/replaced.
    const write = parser.parse(`localStorage.setItem(${JSON.stringify(call.arguments[0].value)}, JSON.stringify(${targetName}));`).program.body[0];
    record.repairable = true; record.reason = null;
    if (input.repair) {
      const original = targetName === sourceParam ? src.script.slice(last.start, last.end)
        : generate(write, {comments: false}).code;
      edit(offset + listener.body.end - 1, offset + listener.body.end - 1, '\n' + original + '\n');
      changes.push('restored_source_watch_persistence');
    }
  }
};
