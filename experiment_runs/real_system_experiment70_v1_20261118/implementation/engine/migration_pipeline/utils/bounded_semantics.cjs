// AST-backed, deliberately narrow repairs. No generated code is executed here.
const fs = require('fs');
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const sourcePhaseRepairs = require('./source_phase_semantics.cjs');

const key = p => !p.computed && p.key && (p.key.name || p.key.value);
const escapeRE = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const member = (n, object, name) => n && n.type === 'MemberExpression' && !n.computed
  && n.object.type === object && n.property.name === name;
const isComponent = n => n && n.type === 'CallExpression' && n.callee.type === 'MemberExpression'
  && n.callee.object.name === 'san' && n.callee.property.name === 'defineComponent'
  && n.arguments.length === 1 && n.arguments[0].type === 'ObjectExpression';

function wrapperTarget(method) {
  if (method.type !== 'ObjectMethod' || method.async || method.generator || method.params.length !== 1
      || method.params[0].type !== 'Identifier' || method.body.body.length !== 1) return null;
  const param = method.params[0].name;
  const stmt = method.body.body[0];
  if (stmt.type !== 'IfStatement' || stmt.alternate) return null;
  let cond = stmt.test;
  if (cond.type === 'LogicalExpression' && cond.operator === '&&'
      && cond.left.type === 'Identifier' && cond.left.name === param) cond = cond.right;
  const field = (n, name) => n && n.type === 'MemberExpression' && !n.computed
    && n.object.type === 'Identifier' && n.object.name === param && n.property.name === name;
  if (cond.type !== 'BinaryExpression' || cond.operator !== '==='
      || !field(cond.left, 'target') || !field(cond.right, 'currentTarget')) return null;
  let consequent = stmt.consequent;
  if (consequent.type === 'BlockStatement' && consequent.body.length === 1) consequent = consequent.body[0];
  if (consequent.type !== 'ExpressionStatement') return null;
  const call = consequent.expression;
  if (call.type !== 'CallExpression' || call.arguments.length || call.callee.type !== 'MemberExpression'
      || call.callee.computed || call.callee.object.type !== 'ThisExpression') return null;
  return call.callee.property.name;
}

function pureArithmetic(n, params) {
  if (!n) return false;
  if (n.type === 'NumericLiteral') return true;
  if (n.type === 'Identifier') return params.includes(n.name);
  if (n.type === 'UnaryExpression' && ['+', '-'].includes(n.operator)) return pureArithmetic(n.argument, params);
  if (n.type === 'BinaryExpression' && ['+', '-', '*', '/', '%', '**'].includes(n.operator))
    return pureArithmetic(n.left, params) && pureArithmetic(n.right, params);
  return false;
}

// Copy only tiny source-backed handlers whose complete effects are understood:
// assigning a parameter to declared root state, and calls to existing methods
// with parameter/literal arguments. No loops, async, globals or nested mutation.
function sourceHandler(source, parent, dataNames) {
  if (!source || source.is_async || !Array.isArray(source.params) || source.params.length !== 1
      || !/^[A-Za-z_$][\w$]*$/.test(source.params[0])) return null;
  let method;
  try { method = parser.parseExpression(`({${source.name}(${source.params[0]}) ${source.body_full || source.body}})`).properties[0]; }
  catch (_) { return null; }
  const param = source.params[0], body = source.body_full || source.body;
  const safeArg = n => {
    if (!n) return false;
    if (['StringLiteral', 'NumericLiteral', 'BooleanLiteral', 'NullLiteral'].includes(n.type)) return true;
    if (n.type === 'Identifier') return n.name === param;
    if (n.type === 'MemberExpression' && !n.computed && n.object.type !== 'ThisExpression') return safeArg(n.object);
    if (n.type === 'TemplateLiteral') return n.expressions.every(safeArg);
    return false;
  };
  const statements = [];
  for (const stmt of method.body.body) {
    if (stmt.type !== 'ExpressionStatement') return null;
    const expr = stmt.expression;
    if (expr.type === 'AssignmentExpression' && expr.operator === '=' && expr.left.type === 'MemberExpression'
        && !expr.left.computed && expr.left.object.type === 'ThisExpression'
        && dataNames.has(expr.left.property.name) && safeArg(expr.right)) {
      const prefix = `({${source.name}(${param}) `;
      statements.push(`this.data.set('${expr.left.property.name}', ${(`${prefix}${body}})`).slice(expr.right.start, expr.right.end)});`);
    } else if (expr.type === 'CallExpression' && expr.callee.type === 'MemberExpression' && !expr.callee.computed
        && expr.callee.object.type === 'ThisExpression'
        && parent.properties.some(p => key(p) === expr.callee.property.name && p.type === 'ObjectMethod')
        && expr.arguments.every(safeArg)) {
      const sourceCode = `({${source.name}(${param}) ${body}})`;
      statements.push(sourceCode.slice(stmt.start, stmt.end));
    } else return null;
  }
  return statements.length ? `${source.name}(${param}) {\n    ${statements.join('\n    ')}\n  }` : null;
}

function processInput(input) {
  const code = input.code;
  const block = /<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code);
  if (!block) return {code, changes: [], wrappers: {}};
  const script = block[1], offset = block.index + block[0].indexOf('>') + 1;
  const ast = parser.parse(script, {sourceType: 'unambiguous'});
  const edits = [], changes = [], wrappers = {}, findings = [], startup_contracts = [], method_contracts = [], watcher_contracts = [];
  const record_update_contracts = [];
  const shared_record_contracts = [];
  const parent_initialization_contracts = [];
  const computed_collection_contracts = [];
  const filter_method_contracts = [];
  let parent = null;
  const children = [];
  traverse(ast, {
    AssignmentExpression(path) {
      const n = path.node;
      if (member(n.left, 'Identifier', 'exports') && n.left.object.name === 'module' && isComponent(n.right)) {
        if (parent) throw new Error('Ambiguous exports');
        parent = n.right.arguments[0];
      }
    },
    VariableDeclarator(path) {
      if (path.node.id.type === 'Identifier' && isComponent(path.node.init)) children.push(path.node.init.arguments[0]);
    }
  });
  const edit = (start, end, text) => edits.push({start, end, text});
  // San computed callbacks are not an instance namespace. Diagnose all known
  // component scopes; repair only source-declared root computed VALUE reads.
  // No component/method names are hard-coded; no source or target is executed.
  let sourceRoot = null;
  try {
    const sourceScript=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(input.vue||'')?.[1];
    if(sourceScript)traverse(parser.parse(sourceScript,{sourceType:'unambiguous'}),{
      ExportDefaultDeclaration(p){if(p.node.declaration.type==='ObjectExpression')sourceRoot=p.node.declaration;},
      AssignmentExpression(p){const n=p.node;
        if(member(n.left,'Identifier','exports')&&n.left.object.name==='module'&&n.right.type==='ObjectExpression')sourceRoot=n.right;}
    });
  } catch (_) { /* No proof means no automatic repair. */ }
  const unique=(object,name)=>object?.properties.filter(p=>key(p)===name).length===1
    ?object.properties.find(p=>key(p)===name):null;
  const sourceComputed=unique(sourceRoot,'computed')?.value;
  const sourceNames=new Set(sourceComputed?.type==='ObjectExpression'?sourceComputed.properties.filter(p=>
    p.type==='ObjectMethod'&&p.kind==='method'&&!p.params.length&&!p.async&&!p.generator
    &&unique(sourceComputed,key(p))===p).map(key):[]);
  const components=[...new Set([parent,...children].filter(Boolean))];
  const unsafeStores=new Set();
  traverse(ast,{
    AssignmentExpression(p){let n=p.node.left;
      while(n?.type==='MemberExpression'&&n.object.type==='MemberExpression')n=n.object;
      if(member(n,'ThisExpression','data'))for(const c of components)
        if(c.start<p.node.start&&c.end>p.node.end)unsafeStores.add(c);},
    UpdateExpression(p){if(member(p.node.argument,'ThisExpression','data'))for(const c of components)
      if(c.start<p.node.start&&c.end>p.node.end)unsafeStores.add(c);}
  });
  traverse(ast,{
    MemberExpression(path){
      const n=path.node, namespace=n.object;
      if(!member(namespace,'ThisExpression','computed'))return;
      const component=components.filter(c=>c.start<n.start&&c.end>n.end).sort((a,b)=>(a.end-a.start)-(b.end-b.start))[0];
      const computed=unique(component,'computed')?.value;
      if(computed?.type!=='ObjectExpression')return;
      let owner=path.getFunctionParent();while(owner?.isArrowFunctionExpression())owner=owner.getFunctionParent();
      const direct=owner?.node.type==='ObjectMethod'?owner.parent:owner?.parentPath?.parent;
      if(direct!==component&&direct!==computed)return; // Nested ordinary function has a different this.
      const name=!n.computed&&n.property.type==='Identifier'?n.property.name:
        n.computed&&n.property.type==='StringLiteral'?n.property.value:null;
      let context=path;
      while(context.parentPath?.isMemberExpression()&&context.parent.object===context.node)context=context.parentPath;
      const use=context.parent;
      const unsafe=use?.type==='AssignmentExpression'&&use.left===context.node
        ||use?.type==='UpdateExpression'||use?.type==='UnaryExpression'&&use.operator==='delete'
        ||['CallExpression','NewExpression','OptionalCallExpression','TaggedTemplateExpression'].includes(use?.type);
      const entry=name&&unique(computed,name);
      const safe=component===parent&&sourceNames.has(name)&&entry?.type==='ObjectMethod'&&entry.kind==='method'
        &&!entry.params.length&&!entry.async&&!entry.generator&&!unsafe
        &&!['data','mixins','extends'].some(k=>component.properties.some(p=>key(p)===k))
        &&!unsafeStores.has(component)
        &&!component.properties.some(p=>key(p)===name);
      findings.push({code:'invalid_san_computed_namespace_access',location:'script',
        message:'Read San computed values through this.data.get(name), not this.computed: '+(name||'<dynamic>'),
        details:{contract:'computed_namespace_v1',component:component===parent?'root':'inline_child',
          name,line:n.loc.start.line,column:n.loc.start.column,source_declared_read_repairable:!!safe}});
      if(input.repair&&safe){edit(offset+n.start,offset+n.end,'this.data.get('+JSON.stringify(name)+')');
        changes.push('source_declared_computed_namespace_value_read');}
    }
  });
  if (parent) {
    for (const method of parent.properties) {
      const name = key(method), target = wrapperTarget(method);
      if (name && target && parent.properties.filter(p => key(p) === name).length === 1
          && parent.properties.some(p => key(p) === target && p.type === 'ObjectMethod' && !p.params.length))
        wrappers[name] = target;
    }
    sourcePhaseRepairs({input, parent, script, ast, offset, edit, changes, sourceHandler, findings, startup_contracts, method_contracts, watcher_contracts, record_update_contracts, shared_record_contracts, parent_initialization_contracts, computed_collection_contracts, filter_method_contracts});
    if (input.repair) {
      const outer = /<template\b[^>]*>([\s\S]*?)<\/template\s*>/i.exec(code);
      // A diagnosed source .self contract is required, not just a suggestive name.
      const selfTargets = new Set(Array.from((input.vue || '').matchAll(/@click\.self\s*=\s*(["'])([\w$]+)\1/g), m => m[2]));
      if (outer) {
        const start = outer.index + outer[0].indexOf('>') + 1;
        for (const [name, target] of Object.entries(wrappers)) {
          if (!selfTargets.has(target)) continue;
          const pattern = new RegExp('on-click\\s*=\\s*(["\'])' + escapeRE(name) + '\\1', 'g');
          for (const match of outer[1].matchAll(pattern)) {
            edit(start + match.index, start + match.index + match[0].length, `on-click=${match[1]}${name}($event)${match[1]}`);
            changes.push('explicit_self_wrapper_event');
          }
        }
      }
      const options = input.ssm?.script?.options || {};
      const bindings = input.ssm?.template?.event_bindings || [];
      const dataNames = new Set((options.data || []).map(p => p.name));
      for (const method of parent.properties) {
        const name = key(method);
        if (!name || method.type !== 'ObjectMethod' || method.params.length
            || parent.properties.filter(p => key(p) === name).length !== 1
            || !/\bthis\.event\b/.test(script.slice(method.body.start, method.body.end))) continue;
        const expected = bindings.filter(b => b.handler_name === name || b.handler_expression?.startsWith(name + '('));
        const expressions = [...new Set(expected.map(b => b.handler_expression))];
        if (expressions.length !== 1 || !new RegExp('^' + escapeRE(name) + '\\([A-Za-z_$][\\w$]*(?:\\.[A-Za-z_$][\\w$]*)*\\)$').test(expressions[0])) continue;
        const sources = (options.methods || []).filter(m => m.name === name);
        if (sources.length !== 1 || !outer) continue;
        const restored = sourceHandler(sources[0], parent, dataNames);
        if (!restored) continue;
        const currentCalls = Array.from(outer[1].matchAll(/\bon-[\w-]+\s*=\s*(["'])(.*?)\1/g), m => m[2]);
        if (currentCalls.some(expr => expr.startsWith(name + '(') && expr !== expressions[0])) continue;
        const start = outer.index + outer[0].indexOf('>') + 1;
        const bindingsToFix = [];
        for (const match of outer[1].matchAll(/<([A-Za-z][\w-]*)\b[^>]*>/g)) {
          for (const event of expected) {
            if (match[1] !== event.element_tag) continue;
            const pattern = new RegExp('\\bon-' + escapeRE(event.event_name) + '\\s*=\\s*(["\'])' + escapeRE(name) + '\\1', 'g');
            for (const attr of match[0].matchAll(pattern)) bindingsToFix.push({start: start + match.index + attr.index,
              end: start + match.index + attr.index + attr[0].length, text: `on-${event.event_name}=${attr[1]}${expressions[0]}${attr[1]}`});
          }
        }
        const unique = [...new Map(bindingsToFix.map(e => [e.start, e])).values()];
        if (!unique.length) continue;
        edits.push(...unique);
        edit(offset + method.start, offset + method.end, restored);
        changes.push('restored_source_parameterized_event_handler');
      }
    }
  }
  if (input.repair) for (const child of children) {
    const template = child.properties.find(p => key(p) === 'template');
    const computed = child.properties.find(p => key(p) === 'computed');
    if (!template || template.type !== 'ObjectProperty' || template.value.type !== 'TemplateLiteral'
        || template.value.expressions.length || !computed || computed.value?.type !== 'ObjectExpression') continue;
    const text = template.value.quasis[0].value.raw;
    const moved = [];
    for (const method of computed.value.properties) {
      const name = key(method);
      if (!name || method.type !== 'ObjectMethod' || method.params.length || method.body.body.length !== 1
          || method.async || method.generator || child.properties.some(p => key(p) === name)) continue;
      const ret = method.body.body[0];
      const fn = ret.type === 'ReturnStatement' && ret.argument;
      if (!fn || fn.type !== 'ArrowFunctionExpression' || fn.async || fn.params.length === 0
          || fn.params.some(p => p.type !== 'Identifier') || !pureArithmetic(fn.body, fn.params.map(p => p.name))) continue;
      // All template references must be calls, and there must be no script-side
      // reference (including computed dependencies or this.data.get('name')).
      if (template.end > method.start) continue;
      const refs = Array.from(text.matchAll(new RegExp('\\b' + escapeRE(name) + '\\b', 'g')));
      if (!refs.length || refs.some(m => !/^\s*\(/.test(text.slice(m.index + name.length)))) continue;
      const remainder = script.slice(child.start, template.start) + script.slice(template.end, method.start)
        + script.slice(method.end, child.end);
      if (new RegExp('\\b' + escapeRE(name) + '\\b').test(remainder)) continue;
      let end = method.end;
      while (/\s/.test(script[end] || '') && end < script.length) end++;
      // Leave an empty computed object if needed. Remove a following comma,
      // or the preceding separator when this is the last computed property.
      let start = method.start;
      if (script[end] === ',') end++;
      else { let pos = start - 1; while (/\s/.test(script[pos] || '') && pos > 0) pos--; if (script[pos] === ',') start = pos; }
      edit(offset + start, offset + end, '');
      moved.push(`${name}(${fn.params.map(p => p.name).join(', ')}) { return ${script.slice(fn.body.start, fn.body.end)}; }`);
      changes.push('parameterized_computed_to_pure_method');
    }
    if (moved.length) edit(offset + child.start + 1, offset + child.start + 1, '\n  ' + moved.join(',\n  ') + ',\n');
  }
  // Non-overlapping edits only; adjacent method removals are deliberately
  // rejected rather than risking an ambiguous rewrite.
  edits.sort((a, b) => b.start - a.start);
  for (let i = 1; i < edits.length; i++) if (edits[i].end > edits[i - 1].start) throw new Error('Overlapping edits');
  let result = code;
  for (const e of edits) result = result.slice(0, e.start) + e.text + result.slice(e.end);
  if (edits.length) {
    const next = /<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(result);
    parser.parse(next[1], {sourceType: 'unambiguous'});
  }
  return {code: result, changes: [...new Set(changes)], wrappers, findings, startup_contracts, method_contracts, watcher_contracts, record_update_contracts, shared_record_contracts, parent_initialization_contracts, computed_collection_contracts, filter_method_contracts};
}

try { process.stdout.write(JSON.stringify(processInput(JSON.parse(fs.readFileSync(0, 'utf8'))))); }
catch (error) { process.stdout.write(JSON.stringify({error: String(error.message)})); }
