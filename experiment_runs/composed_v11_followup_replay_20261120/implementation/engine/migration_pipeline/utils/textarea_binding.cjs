// Restrict edits to actual SFC/inline-component templates, never JS examples.
const fs = require('fs');
const babel = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const dom = require('@vue/compiler-dom');

function run(input) {
  const code = input.code, templates = [], findings = [], edits = [];
  const outer = /<template\b[^>]*>([\s\S]*?)<\/template\s*>/i.exec(code);
  if (outer) templates.push({text: outer[1], offset: outer.index + outer[0].indexOf('>') + 1, scope: 'template'});
  const script = /<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code);
  if (script) {
    const offset = script.index + script[0].indexOf('>') + 1;
    const ast = babel.parse(script[1], {sourceType: 'unambiguous'});
    traverse(ast, {CallExpression(path) {
      const n = path.node;
      if (n.callee.type !== 'MemberExpression' || n.callee.computed || n.callee.object.name !== 'san'
          || n.callee.property.name !== 'defineComponent' || n.arguments[0]?.type !== 'ObjectExpression') return;
      const component = path.parentPath.isVariableDeclarator() ? path.parentPath.node.id.name : 'parent';
      for (const prop of n.arguments[0].properties) {
        if (prop.type === 'ObjectProperty' && !prop.computed && (prop.key.name || prop.key.value) === 'template'
            && prop.value.type === 'TemplateLiteral' && prop.value.expressions.length === 0)
          templates.push({text: prop.value.quasis[0].value.raw, offset: offset + prop.value.start + 1,
                          scope: `script.${component}.template`});
      }
    }});
  }
  for (const template of templates) {
    // Recover unrelated template errors to inspect an independently well-formed
    // textarea. An error inside that textarea still forbids automatic repair.
    const errors = [];
    const ast = dom.parse(template.text, {onError(error) { errors.push(error); }});
    function visit(node) {
      if (node.type === 1 && node.tag.toLowerCase() === 'textarea') {
        const source = node.loc.source;
        const opening = /^<textarea\b(?:[^'">]|"[^"]*"|'[^']*')*>/i.exec(source);
        const closing = /<\/textarea\s*>$/i.exec(source);
        if (opening && closing) {
          const body = source.slice(opening[0].length, closing.index);
          if (/\{=[\s\S]*?=\}/.test(body)) {
            const binding = /^\s*\{=\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*|\[\d+\])*)\s*=\}\s*$/.exec(body);
            const hasValue = node.props.some(p => p.type === 6 && p.name.toLowerCase() === 'value'
              || p.type === 7 && p.arg?.content === 'value');
            const localError = errors.some(error => error.loc?.start.offset >= node.loc.start.offset
              && error.loc.start.offset < node.loc.end.offset);
            findings.push({scope: template.scope, path: binding?.[1] || null, repairable: !!binding && !hasValue && !localError});
            if (input.repair && binding && !hasValue && !localError) {
              const start = template.offset + node.loc.start.offset;
              edits.push({start: start + opening[0].length - 1, end: start + closing.index,
                          text: ` value="{= ${binding[1]} =}">`});
            }
          }
        }
      }
      for (const child of node.children || []) visit(child);
    }
    visit(ast);
  }
  edits.sort((a, b) => b.start - a.start);
  for (let i = 1; i < edits.length; i++) if (edits[i].end > edits[i - 1].start) throw new Error('Overlapping edits');
  let result = code;
  for (const edit of edits) result = result.slice(0, edit.start) + edit.text + result.slice(edit.end);
  if (edits.length && script) babel.parse(/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(result)[1], {sourceType: 'unambiguous'});
  return {code: result, findings, changes: edits.length ? ['normalized_textarea_value_binding'] : []};
}
try { process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8'))))); }
catch (error) { process.stdout.write(JSON.stringify({error: String(error.message)})); }
