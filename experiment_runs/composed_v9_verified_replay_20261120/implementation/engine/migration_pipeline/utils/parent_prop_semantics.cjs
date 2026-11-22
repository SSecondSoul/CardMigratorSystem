// Add only absent parent prop declarations/defaults proven by complete Vue AST.
// Never execute source factories, replace existing values, or edit child options.
const fs = require('fs'), parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const generate = require('@babel/generator').default;
const t = require('@babel/types');
const {parse: parseSFC} = require('@vue/compiler-sfc');
const key = p => !p.computed && (p.key?.name || p.key?.value);
const one = (o, name) => o?.properties?.filter(p => key(p) === name).length === 1
  ? o.properties.find(p => key(p) === name) : null;
const forbidden = new Set(['__proto__', 'prototype', 'constructor']);
const safeName = s => typeof s === 'string' && /^[A-Za-z_][\w]*$/.test(s) && !forbidden.has(s);
const unambiguous = o => t.isObjectExpression(o) && o.properties.every(p => safeName(key(p)))
  && new Set(o.properties.map(key)).size === o.properties.length;
const member = (n, object, property) => t.isMemberExpression(n) && !n.computed
  && t.isIdentifier(n.object, {name: object}) && t.isIdentifier(n.property, {name: property});
const component = n => t.isCallExpression(n) && member(n.callee, 'san', 'defineComponent')
  && n.arguments.length === 1 && t.isObjectExpression(n.arguments[0]);
const types = {String: 'string', Number: 'number', Boolean: 'bool', Array: 'array', Object: 'object', Function: 'func'};
function plainLiteral(n) {
  if (t.isStringLiteral(n) || t.isNumericLiteral(n) || t.isBooleanLiteral(n) || t.isNullLiteral(n)) return true;
  if (t.isUnaryExpression(n) && ['+', '-'].includes(n.operator) && t.isNumericLiteral(n.argument)) return true;
  if (t.isArrayExpression(n)) return n.elements.every(x => x && plainLiteral(x));
  return unambiguous(n) && n.properties.every(p => t.isObjectProperty(p) && !p.shorthand && plainLiteral(p.value));
}
function defaultExpression(p, type) {
  let n = p?.value || (t.isObjectMethod(p) ? p : null);
  if (!n) return null;
  // A direct object/array Vue default may be shared across instances. Only
  // literal-returning factories prove the fresh-per-instance contract here.
  if (plainLiteral(n) && !t.isArrayExpression(n) && !t.isObjectExpression(n)) return n;
  if (!['Array', 'Object'].includes(type) || !t.isFunction(n) || n.async || n.generator || n.params.length) return null;
  if (t.isBlockStatement(n.body)) {
    if (n.body.body.length !== 1 || !t.isReturnStatement(n.body.body[0])) return null;
    n = n.body.body[0].argument;
  } else n = n.body;
  return plainLiteral(n) && (type === 'Array' ? t.isArrayExpression(n) : t.isObjectExpression(n)) ? n : null;
}
function targetFactoryObject(factory, scope) {
  if (!t.isObjectMethod(factory) || factory.kind !== 'method' || factory.async || factory.generator
      || factory.params.length) return null;
  const statements = factory.body.body, last = statements.at(-1);
  if (!t.isReturnStatement(last) || !unambiguous(last.argument)) return null;
  const readonlyLiteral = n => {
    if (plainLiteral(n)) return true;
    if (!t.isCallExpression(n) || n.arguments.length || !t.isIdentifier(n.callee)) return false;
    const binding = scope.getBinding(n.callee.name), helper = binding?.path.node;
    return binding?.constant && t.isFunctionDeclaration(helper) && !helper.async && !helper.generator
      && !helper.params.length && helper.body.body.length === 1
      && t.isReturnStatement(helper.body.body[0]) && plainLiteral(helper.body.body[0].argument);
  };
  // A few local literal constants/pure literal-returning helpers may precede
  // the return; preserve their bytes/order, never execute or inline them.
  if (!statements.slice(0, -1).every(s => t.isVariableDeclaration(s, {kind:'const'})
      && s.declarations.every(d => t.isIdentifier(d.id) && readonlyLiteral(d.init)))) return null;
  return last.argument;
}
function sourceContracts(vue) {
  const {descriptor, errors} = parseSFC(vue);
  if (errors.length || !descriptor.script || descriptor.scriptSetup || !descriptor.template) return null;
  const ast = parser.parse(descriptor.script.content, {sourceType: 'unambiguous'});
  const exports = [];
  traverse(ast, {
    ExportDefaultDeclaration(p) {if (p.parentPath.isProgram()) exports.push(p.get('declaration'));},
    AssignmentExpression(p) {
      if (member(p.node.left, 'module', 'exports') && p.node.operator === '='
          && p.parentPath.isExpressionStatement() && p.parentPath.parentPath.isProgram()
          && !p.scope.getBinding('module')) exports.push(p.get('right'));
    }
  });
  if (exports.length !== 1 || !unambiguous(exports[0].node)
      || ['mixins', 'extends'].some(k => one(exports[0].node, k))) return null;
  const props = one(exports[0].node, 'props')?.value;
  if (!unambiguous(props)) return null;
  const contracts = [];
  for (const prop of props.properties) {
    if (!t.isObjectProperty(prop)) return null;
    const descriptor = prop.value;
    let type = descriptor, required = false, def;
    if (t.isObjectExpression(descriptor)) {
      if (!unambiguous(descriptor) || descriptor.properties.some(p => !['type', 'default', 'required'].includes(key(p)))) return null;
      type = one(descriptor, 'type')?.value;
      const req = one(descriptor, 'required')?.value;
      if (req && !t.isBooleanLiteral(req)) return null;
      required = !!req?.value;
      def = one(descriptor, 'default');
    }
    if (!t.isIdentifier(type) || !types[type.name] || exports[0].scope.getBinding(type.name)) return null;
    const expression = def && defaultExpression(def, type.name);
    if (def && !expression) return null;
    // Type/default conflicts are not silently repaired by guessing coercions.
    if (expression && !t.isNullLiteral(expression)) {
      const matches = type.name === 'Array' ? t.isArrayExpression(expression)
        : type.name === 'Object' ? t.isObjectExpression(expression)
        : type.name === 'String' ? t.isStringLiteral(expression)
        : type.name === 'Boolean' ? t.isBooleanLiteral(expression)
        : type.name === 'Number' ? (t.isNumericLiteral(expression) || t.isUnaryExpression(expression)) : false;
      if (!matches) return null;
    }
    contracts.push({name: key(prop), type: types[type.name], required,
      default_code: expression ? generate(expression, {comments: false}).code : null});
  }
  return contracts;
}
function run(input) {
  const block = /<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(input.code);
  const script = block ? block[1] : input.code;
  const offset = block ? block.index + block[0].indexOf('>') + 1 : 0;
  const ast = parser.parse(script, {sourceType: 'unambiguous'}), parents = [];
  let wrappers = 0, opaqueComponents = false, moduleReferences = 0, externalMutation = false;
  traverse(ast, {
    ReferencedIdentifier(p) {if (p.node.name === 'module' || p.node.name === 'exports') moduleReferences++;},
    AssignmentExpression(p) {
      let root = p.node.left;
      while (t.isMemberExpression(root)) root = root.object;
      if (t.isIdentifier(root) && ['san','DataTypes'].includes(root.name)) externalMutation = true;
    },
    CallExpression(p) {
    if (member(p.node.callee, 'san', 'defineComponent') && !component(p.node)) opaqueComponents = true;
    if (!component(p.node)) return;
    wrappers += p.node.arguments[0].properties.filter(x => key(x) === 'methods'
      && t.isObjectProperty(x) && t.isObjectExpression(x.value)).length;
    const a = p.parentPath;
    if (a.isAssignmentExpression({operator: '='}) && member(a.node.left, 'module', 'exports')
        && a.parentPath.isExpressionStatement() && a.parentPath.parentPath.isProgram()
        && !a.scope.getBinding('module')) parents.push(p);
  }});
  const result = {code: input.code, changes: [], contracts: [], methods_wrapper_count: wrappers,
    methods_structure_complete: !opaqueComponents};
  if (!input.vue) return result;
  const contracts = sourceContracts(input.vue);
  if (!contracts || parents.length !== 1) return {...result, reason: 'unsupported_source_or_parent_contract'};
  result.contracts = contracts;
  const path = parents[0], parent = path.node.arguments[0];
  const san = path.scope.getBinding('san');
  if (moduleReferences !== 1 || externalMutation || !unambiguous(parent) || !san?.constant || !san.path.isVariableDeclarator()
      || san.path.parentPath.node.kind !== 'const' || !t.isCallExpression(san.path.node.init)
      || !t.isIdentifier(san.path.node.init.callee, {name: 'require'}) || path.scope.getBinding('require')
      || san.path.node.init.arguments.length !== 1 || san.path.node.init.arguments[0].value !== 'san')
    return {...result, reason: 'ambiguous_target_options_or_san_binding'};
  const schema = one(parent, 'dataTypes');
  const schemaObject = schema?.value;
  const factory = one(parent, 'initData');
  const factoryPath = path.get('arguments.0.properties').find(p => p.node === factory);
  const factoryObject = targetFactoryObject(factory, factoryPath?.scope || path.scope);
  const schemaBlocked = ['statics','props','propTypes'].some(name => one(parent,name));
  const missingSchema = !schemaBlocked && (!schema || (t.isObjectProperty(schema) && unambiguous(schemaObject)))
    ? contracts.filter(c => !schema || !one(schemaObject, c.name)) : [];
  if (schemaBlocked) result.schema_review_reason = 'existing_alternative_schema_container_requires_review';
  const missingDefaults = unambiguous(factoryObject)
    ? contracts.filter(c => c.default_code !== null && !one(factoryObject, c.name)) : [];
  const alias = path.scope.getBinding('DataTypes');
  const aliasValid = !alias || (alias.constant && alias.path.isVariableDeclarator()
    && alias.path.parentPath.node.kind === 'const' && member(alias.path.node.init, 'san', 'DataTypes'));
  result.addable_schema_fields = aliasValid ? missingSchema.map(c => c.name) : [];
  result.addable_default_fields = missingDefaults.map(c => c.name);
  if (!input.repair) return result;
  const edits = [], parentOptions = [];
  const insert = (object, text) => edits.push({start: object.start + 1, end: object.start + 1,
    text: '\n' + text.join(',\n') + (object.properties.length ? ',' : '') + '\n'});
  if (missingSchema.length && aliasValid) {
    const fields = missingSchema.map(c => `${c.name}: DataTypes.${c.type}${c.required ? '.isRequired' : ''}`);
    if (schema) insert(schemaObject, fields);
    else parentOptions.push('dataTypes: {\n' + fields.join(',\n') + '\n}');
    if (!alias) edits.push({start: san.path.parentPath.node.end, end: san.path.parentPath.node.end,
      text: '\nconst DataTypes = san.DataTypes;\n'});
    result.changes.push('restored_source_parent_prop_schema');
  }
  if (missingDefaults.length) {
    insert(factoryObject, missingDefaults.map(c => `${c.name}: ${c.default_code}`));
    result.changes.push('restored_source_parent_prop_defaults');
  }
  if (parentOptions.length) insert(parent, parentOptions);
  edits.sort((a, b) => b.start - a.start);
  for (let i = 1; i < edits.length; i++) if (edits[i].end > edits[i - 1].start) throw Error('Overlapping edits');
  let next = script;
  for (const e of edits) next = next.slice(0, e.start) + e.text + next.slice(e.end);
  if (edits.length) parser.parse(next, {sourceType: 'unambiguous'});
  result.code = input.code.slice(0, offset) + next + input.code.slice(offset + script.length);
  return result;
}
try {process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0, 'utf8')))));}
catch (error) {process.stdout.write(JSON.stringify({error: error.message}));}
