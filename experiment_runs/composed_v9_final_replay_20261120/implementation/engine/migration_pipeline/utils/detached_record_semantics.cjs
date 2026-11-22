// Prove only fresh array + fresh shallow records, direct scalar writes, then
// one explicit commit. Unknown syntax, escape, depth or control flow fails closed.
// Parsing only: generated component code is never executed.
const fs = require('fs'), parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const t = require('@babel/types');
const forbiddenKeys = new Set(['__proto__', 'constructor', 'prototype']);
function fieldCall(n, action, field) {
  return t.isCallExpression(n) && !n.optional && n.arguments.length === (action === 'get' ? 1 : 2)
    && t.isMemberExpression(n.callee) && !n.callee.computed && n.callee.property.name === action
    && t.isMemberExpression(n.callee.object) && !n.callee.object.computed
    && t.isThisExpression(n.callee.object.object) && n.callee.object.property.name === 'data'
    && t.isStringLiteral(n.arguments[0]) && (!field || n.arguments[0].value === field);
}
function recordProperty(n, name) {
  return t.isMemberExpression(n) && !n.computed && t.isIdentifier(n.property)
    && !forbiddenKeys.has(n.property.name) && t.isMemberExpression(n.object)
    && n.object.computed && t.isNumericLiteral(n.object.property)
    && Number.isInteger(n.object.property.value) && n.object.property.value >= 0
    && t.isIdentifier(n.object.object, {name});
}
function scalar(n, name, scope) {
  if (t.isNumericLiteral(n) || t.isBooleanLiteral(n) || t.isStringLiteral(n) || t.isNullLiteral(n)) return true;
  if (recordProperty(n, name)) return true;
  if (t.isBinaryExpression(n) || t.isLogicalExpression(n)) return scalar(n.left, name, scope) && scalar(n.right, name, scope);
  if (t.isUnaryExpression(n) && ['+', '-', '!', '~'].includes(n.operator)) return scalar(n.argument, name, scope);
  if (t.isConditionalExpression(n)) return [n.test, n.consequent, n.alternate].every(x => scalar(x, name, scope));
  return t.isCallExpression(n) && t.isMemberExpression(n.callee) && !n.callee.computed
    && t.isIdentifier(n.callee.object, {name: 'Math'}) && !scope.getBinding('Math')
    && ['max', 'min', 'random', 'round', 'floor', 'ceil', 'abs'].includes(n.callee.property.name)
    && n.arguments.every(x => scalar(x, name, scope));
}
function prove({body, script}) {
  const ast = parser.parse(script, {sourceType: 'unambiguous'});
  const matches = [];
  traverse(ast, {Function(p) {
    if (t.isBlockStatement(p.node.body) && script.slice(p.node.body.start + 1, p.node.body.end - 1) === body)
      matches.push(p);
  }});
  if (matches.length !== 1 || matches[0].node.async || matches[0].node.generator) return {aliases: []};
  const fn = matches[0];
  const aliases = [];
  for (const statement of fn.get('body.body')) {
    if (!statement.isVariableDeclaration({kind: 'const'}) || statement.node.declarations.length !== 1) continue;
    const declaration = statement.get('declarations.0'), n = declaration.node, map = n.init;
    if (!t.isIdentifier(n.id) || !t.isCallExpression(map) || map.arguments.length !== 1
        || !t.isMemberExpression(map.callee) || map.callee.computed || map.callee.property.name !== 'map'
        || !fieldCall(map.callee.object, 'get')) continue;
    const cb = map.arguments[0], obj = cb?.body;
    if (!t.isArrowFunctionExpression(cb) || cb.async || cb.params.length !== 1 || !t.isIdentifier(cb.params[0])
        || !t.isObjectExpression(obj) || obj.properties.length !== 1 || !t.isSpreadElement(obj.properties[0])
        || !t.isIdentifier(obj.properties[0].argument, {name: cb.params[0].name})) continue;
    const name = n.id.name, field = map.callee.object.arguments[0].value;
    const binding = declaration.scope.getBinding(name);
    if (!binding || binding.constantViolations.length) continue;
    let unsafe = false, commit, writes = [];
    // Textual fallback validator cannot distinguish shadowed names: in that
    // situation retain its diagnostics rather than hiding an unrelated mutation.
    fn.traverse({Identifier(p) {
      if (p.node.name === name && p.scope.getBinding(name) !== binding) unsafe = true;
    }});
    for (const ref of binding.referencePaths) {
      if (ref.getFunctionParent() !== fn) {unsafe = true; break;}
      const parent = ref.parentPath;
      if (parent.isCallExpression() && fieldCall(parent.node, 'set', field)
          && parent.node.arguments[1] === ref.node && parent.parentPath.isExpressionStatement()
          && parent.parentPath.parentPath === fn.get('body')) {
        if (commit) unsafe = true;
        commit = parent.node; continue;
      }
      let root = ref;
      while (root.parentPath.isMemberExpression() && root.parentPath.node.object === root.node) root = root.parentPath;
      if (!recordProperty(root.node, name)) {unsafe = true; break;}
      if (root.parentPath.isAssignmentExpression() && root.parentPath.node.left === root.node) {
        const assignment = root.parentPath;
        if (assignment.node.operator !== '=' || !assignment.parentPath.isExpressionStatement()
            || assignment.parentPath.parentPath !== fn.get('body')
            || !scalar(assignment.node.right, name, assignment.scope)) unsafe = true;
        writes.push(assignment.node);
      } else {
        // A record read is allowed only inside an already bounded scalar write.
        const assignment = root.findParent(p => p.isAssignmentExpression());
        if (!assignment || !recordProperty(assignment.node.left, name)
            || !scalar(assignment.node.right, name, assignment.scope)) unsafe = true;
      }
    }
    if (!unsafe && commit && writes.length && writes.every(w => w.start > n.end && w.end < commit.start)) {
      // Abrupt flow can skip the commit. Unknown loops/try/closures in the
      // enclosing method are conservatively refused even without alias escape.
      fn.traverse({enter(p) {
        if (p.isReturnStatement() || p.isThrowStatement() || p.isTryStatement()
            || p.isAwaitExpression() || p.isYieldExpression() || p.isLoop()
            || p.isWithStatement() || p.isSwitchStatement()
            || (p.isCallExpression() && t.isIdentifier(p.node.callee, {name: 'eval'}))) unsafe = true;
      }});
      if (!unsafe) aliases.push(name);
    }
  }
  return {aliases, boundary: 'shallow fresh records; complete local use chain; direct scalar writes then commit'};
}
try {process.stdout.write(JSON.stringify(prove(JSON.parse(fs.readFileSync(0, 'utf8')))));}
catch (_) {process.stdout.write(JSON.stringify({aliases: [], status: 'unproven'}));}
