// Opt-in residual-v2 rewrites. Parse only: never evaluate generated code.
const fs = require('fs');
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const key = p => !p.computed && p.key && (p.key.name || p.key.value);
const isComponent = n => n?.type === 'CallExpression' && n.callee.type === 'MemberExpression'
  && !n.callee.computed && n.callee.object.name === 'san' && n.callee.property.name === 'defineComponent'
  && n.arguments.length === 1 && n.arguments[0].type === 'ObjectExpression';

function selfContained(path) {
  const n = path.node;
  if (n.type !== 'ObjectMethod' || n.async || n.generator || n.kind !== 'method'
      || n.params.some(p => p.type !== 'Identifier')) return false;
  let safe = true;
  const globals = new Set(['Math', 'Date', 'undefined', 'Infinity', 'NaN']);
  const mathCalls = new Set(['abs', 'min', 'max', 'floor', 'ceil', 'round', 'pow', 'sqrt']);
  path.traverse({
    ThisExpression() { safe = false; },
    Super() { safe = false; },
    AwaitExpression() { safe = false; },
    YieldExpression() { safe = false; },
    ThrowStatement() { safe = false; },
    ReferencedIdentifier(p) {
      const binding = p.scope.getBinding(p.node.name);
      if (binding) { if (binding.identifier.start < n.start || binding.identifier.end > n.end) safe = false; }
      else if (!globals.has(p.node.name)) safe = false;
    },
    AssignmentExpression(p) {
      const left = p.node.left;
      const binding = left.type === 'Identifier' && p.scope.getBinding(left.name);
      if (!binding || binding.kind === 'param' || binding.identifier.start < n.start) safe = false;
    },
    UpdateExpression(p) {
      const arg = p.node.argument;
      const binding = arg.type === 'Identifier' && p.scope.getBinding(arg.name);
      if (!binding || binding.kind === 'param' || binding.identifier.start < n.start) safe = false;
    },
    UnaryExpression(p) { if (p.node.operator === 'delete') safe = false; },
    NewExpression(p) {
      if (p.node.callee.type !== 'Identifier' || p.node.callee.name !== 'Date' || p.scope.getBinding('Date')) safe = false;
    },
    CallExpression(p) {
      const callee = p.node.callee;
      if (callee.type !== 'MemberExpression' || callee.computed) { safe = false; return; }
      if (callee.object.name === 'Math' && !p.scope.getBinding('Math') && mathCalls.has(callee.property.name)) return;
      const binding = callee.object.type === 'Identifier' && p.scope.getBinding(callee.object.name);
      // Only local Date instances may be changed; never mutate an argument.
      if (binding?.path.isVariableDeclarator() && binding.path.node.init?.type === 'NewExpression'
          && binding.path.node.init.callee.name === 'Date' && binding.constant
          && binding.identifier.start > n.start && !p.scope.getBinding('Date')
          && ['setHours', 'getTime', 'getHours', 'getMinutes', 'getSeconds'].includes(callee.property.name)) return;
      safe = false;
    }
  });
  return safe;
}

function propSchema(source) {
  try {
    const ast = parser.parseExpression(source);
    if (ast.type !== 'ObjectExpression') return null;
    const props = ast.properties.filter(p => key(p) === 'props');
    if (props.length !== 1 || props[0].type !== 'ObjectProperty') return null;
    const node = props[0].value;
    const types = {String: 'string', Number: 'number', Boolean: 'bool', Array: 'array', Object: 'object', Function: 'func'};
    if (node.type === 'ArrayExpression' && node.elements.every(p => p?.type === 'StringLiteral'))
      return {source: source.slice(node.start, node.end), fields: node.elements.map(p => [p.value, 'any'])};
    if (node.type !== 'ObjectExpression') return null;
    const fields = [];
    for (const prop of node.properties) {
      if (prop.type !== 'ObjectProperty' || !key(prop)) return null;
      let type = prop.value, required = false;
      if (type.type === 'ObjectExpression') {
        const req = type.properties.find(p => key(p) === 'required');
        if (req && req.value.type !== 'BooleanLiteral') return null;
        required = !!req?.value.value;
        const specified = type.properties.filter(p => key(p) === 'type');
        if (specified.length !== 1) return null;
        type = specified[0].value;
      }
      if (type.type !== 'Identifier' || !types[type.name]) return null;
      fields.push([key(prop), types[type.name] + (required ? '.isRequired' : '')]);
    }
    return {source: source.slice(node.start, node.end), fields};
  } catch (_) { return null; }
}

function run(input) {
  const code = input.code;
  const block = /<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code);
  const fallback = {code, changes: [], source_prop_contracts: []};
  if (!block) return fallback;
  const script = block[1], offset = block.index + block[0].indexOf('>') + 1;
  const ast = parser.parse(script, {sourceType: 'unambiguous'});
  const components = [], edits = [], helpers = [], changes = [], contracts = [];
  let parent;
  traverse(ast, {
    CallExpression(path) {
      if (!isComponent(path.node)) return;
      const item = {path: path.get('arguments.0'), object: path.node.arguments[0]};
      if (path.parentPath.isVariableDeclarator()) item.identifier = path.parentPath.node.id.name;
      if (path.parentPath.isAssignmentExpression() && path.parentPath.node.left.type === 'MemberExpression'
          && path.parentPath.node.left.object.name === 'module' && path.parentPath.node.left.property.name === 'exports') parent = item;
      components.push(item);
    }
  });
  if (input.repair) for (const component of components) {
    const computed = component.path.get('properties').find(p => key(p.node) === 'computed' && p.node.value?.type === 'ObjectExpression');
    if (!computed) continue;
    const selected = new Map();
    computed.traverse({CallExpression(path) {
      const callee = path.node.callee;
      if (callee.type !== 'MemberExpression' || callee.computed || callee.object.type !== 'ThisExpression') return;
      // A non-arrow inner function has a different this and is not assessed.
      let ancestor = path.parentPath;
      while (ancestor && ancestor !== computed) {
        if (ancestor.isFunction() && !ancestor.isArrowFunctionExpression() && ancestor.parentPath.node !== computed.node.value) return;
        ancestor = ancestor.parentPath;
      }
      const name = callee.property.name;
      const methods = component.path.get('properties').filter(p => key(p.node) === name);
      if (methods.length !== 1 || !selfContained(methods[0])) return;
      if (!selected.has(name)) {
        const method = methods[0].node;
        let helper = `__sanComputed_${name}_${helpers.length}`;
        while (new RegExp('\\b' + helper + '\\b').test(script)) helper += '_';
        selected.set(name, helper);
        helpers.push(`function ${helper}(${method.params.map(p => p.name).join(', ')}) ${script.slice(method.body.start, method.body.end)}`);
        changes.push('lifted_self_contained_computed_helper');
      }
      edits.push({start: callee.start, end: callee.end, text: selected.get(name)});
    }});
  }
  const registry = parent?.object.properties.find(p => key(p) === 'components' && p.value?.type === 'ObjectExpression');
  for (const source of input.ssm?.script?.options?.components || []) {
    const schema = propSchema(source.inline_definition?.source_code || '');
    if (!schema) continue;
    contracts.push({component: source.source_name, registered_tag: source.registered_tag, props: schema.source});
    if (!input.repair || !schema.fields.length || !registry) continue;
    const registrations = registry.value.properties.filter(p => key(p) === source.registered_tag && p.value?.type === 'Identifier');
    if (registrations.length !== 1) continue;
    const targets = components.filter(c => c.identifier === registrations[0].value.name);
    if (targets.length !== 1 || targets[0].object.properties.some(p => key(p) === 'dataTypes')) continue;
    // Do not overwrite unsupported propTypes or a Vue props option here.
    if (targets[0].object.properties.some(p => ['props', 'propTypes'].includes(key(p)))) continue;
    const text = '\n  dataTypes: {' + schema.fields.map(([name, type]) => `${JSON.stringify(name)}: san.DataTypes.${type}`).join(', ') + '},\n';
    edits.push({start: targets[0].object.start + 1, end: targets[0].object.start + 1, text});
    changes.push('restored_inline_source_prop_schema');
  }
  if (helpers.length) edits.push({start: 0, end: 0, text: '\n' + helpers.join('\n') + '\n'});
  edits.sort((a, b) => b.start - a.start);
  for (let i = 1; i < edits.length; i++) if (edits[i].end > edits[i - 1].start) throw new Error('Overlapping edits');
  let next = script;
  for (const e of edits) next = next.slice(0, e.start) + e.text + next.slice(e.end);
  if (edits.length) parser.parse(next, {sourceType: 'unambiguous'});
  return {code: code.slice(0, offset) + next + code.slice(offset + script.length),
          changes: [...new Set(changes)], source_prop_contracts: contracts};
}
try { process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0, 'utf8'))))); }
catch (error) { process.stdout.write(JSON.stringify({error: String(error.message)})); }
