// Recover only source-registered hyphenated declaration/registry pairs.
// Babel recovery is used for token positions, never as proof of valid JS.
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const key = p => !p.computed && p.key && (p.key.name || p.key.value);
const component = n => n?.type === 'CallExpression' && n.callee.type === 'MemberExpression'
  && !n.callee.computed && n.callee.object.name === 'san' && n.callee.property.name === 'defineComponent'
  && n.arguments.length === 1 && n.arguments[0].type === 'ObjectExpression';
const parentOf = ast => {
  const xs = ast.program.body.filter(s => s.type === 'ExpressionStatement'
    && s.expression.type === 'AssignmentExpression' && s.expression.operator === '='
    && s.expression.left.type === 'MemberExpression' && !s.expression.left.computed
    && s.expression.left.object.name === 'module' && s.expression.left.property.name === 'exports'
    && component(s.expression.right));
  return xs.length === 1 ? xs[0].expression.right.arguments[0] : null;
};
const subtractName = n => n?.type === 'Identifier' ? n.name
  : n?.type === 'BinaryExpression' && n.operator === '-' && n.right.type === 'Identifier'
    && subtractName(n.left) ? subtractName(n.left) + '-' + n.right.name : null;

function recover(code, ssm) {
  const fallback = {code, changes: [], mappings: [], parse_status: 'not_recovered'};
  const block = /<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code);
  if (!block) return fallback;
  const script = block[1], offset = block.index + block[0].indexOf('>') + 1;
  try { parser.parse(script, {sourceType: 'unambiguous'}); return {...fallback, parse_status: 'parsed'}; }
  catch (_) {}
  let ast;
  try { ast = parser.parse(script, {sourceType: 'unambiguous', tokens: true, errorRecovery: true}); }
  catch (_) { return fallback; }
  const parent = parentOf(ast), registries = parent?.properties.filter(p => key(p) === 'components') || [];
  if (registries.length !== 1 || registries[0].value?.type !== 'ObjectExpression') return fallback;
  const registry = registries[0].value;
  if (registry.properties.some(p => !key(p))) return fallback;
  const tags = (ssm?.script?.options?.components || []).map(c => c.registered_tag);
  const tokens = ast.tokens.filter(t => t.type.label && !['CommentLine', 'CommentBlock'].includes(t.type));
  const candidates = [], edits = [];
  let braces = 0, parens = 0, brackets = 0;
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i], label = t.type.label;
    if (!braces && !parens && !brackets && t.value === 'const') {
      let j = i + 1;
      if (tokens[j]?.type.label !== 'name') continue;
      let name = tokens[j].value;
      while (tokens[j + 1]?.value === '-' && tokens[j + 2]?.type.label === 'name') {
        name += '-' + tokens[j + 2].value; j += 2;
      }
      if (name.includes('-') && tokens[j + 1]?.type.label === '='
          && tokens[j + 2]?.value === 'san' && tokens[j + 3]?.type.label === '.'
          && tokens[j + 4]?.value === 'defineComponent' && tokens[j + 5]?.type.label === '('
          && tokens[j + 6]?.type.label === '{') {
        if (tags.filter(x => x === name).length !== 1 || candidates.some(c => c.tag === name)) return fallback;
        const props = registry.properties.filter(p => key(p) === name);
        if (props.length !== 1 || subtractName(props[0].value) !== name) return fallback;
        let replacement = '__sanInline_' + name.replace(/-/g, '_');
        while (tokens.some(t => t.type.label === 'name' && t.value === replacement)) replacement += '_';
        const declaration = {start: tokens[i + 1].start, end: tokens[j].end, text: replacement};
        const value = {start: props[0].value.start, end: props[0].value.end, text: replacement};
        edits.push(declaration, value);
        candidates.push({tag: name, identifier: replacement, declaration, value});
      }
    }
    if (label === '{' || label === '${') braces++;
    if (label === '}') braces--;
    if (label === '(') parens++;
    if (label === ')') parens--;
    if (label === '[') brackets++;
    if (label === ']') brackets--;
  }
  if (!candidates.length) return fallback;
  // A third token-level use might be arithmetic or an intended component use;
  // neither is safe to guess. Strings, comments and template text stay untouched.
  for (const c of candidates) {
    const parts = c.tag.split('-');
    for (let i = 0; i < tokens.length; i++) {
      if (tokens[i].type.label !== 'name' || tokens[i].value !== parts[0]) continue;
      let j = i, found = true;
      for (const part of parts.slice(1)) {
        if (tokens[j + 1]?.value !== '-' || tokens[j + 2]?.type.label !== 'name' || tokens[j + 2]?.value !== part) { found = false; break; }
        j += 2;
      }
      if (found && ![c.declaration, c.value].some(e => e.start === tokens[i].start && e.end === tokens[j].end)) return fallback;
    }
  }
  let next = script;
  for (const e of edits.sort((a,b) => b.start - a.start)) next = next.slice(0,e.start) + e.text + next.slice(e.end);
  let parsed;
  try { parsed = parser.parse(next, {sourceType: 'unambiguous'}); } catch (_) { return fallback; }
  let safe = true;
  traverse(parsed, {Program(path) {
    for (const c of candidates) {
      const binding = path.scope.getBinding(c.identifier);
      if (!binding?.constant || !binding.path.isVariableDeclarator() || !component(binding.path.node.init)
          || binding.referencePaths.length !== 1 || !binding.referencePaths[0].parentPath.isObjectProperty()
          || key(binding.referencePaths[0].parentPath.node) !== c.tag) safe = false;
    }
    path.stop();
  }});
  if (!safe) return fallback;
  return {code: code.slice(0,offset) + next + code.slice(offset + script.length),
    changes: ['recovered_source_registered_inline_identifiers'],
    mappings: candidates.map(({tag, identifier}) => ({tag, identifier})), parse_status: 'source_registered_recovery'};
}

module.exports = {recover, parentOf, component, key};
if (require.main === module) {
  try { const input = JSON.parse(require('fs').readFileSync(0,'utf8')); process.stdout.write(JSON.stringify(recover(input.code, input.ssm))); }
  catch (e) { process.stdout.write(JSON.stringify({error: e.message})); }
}
