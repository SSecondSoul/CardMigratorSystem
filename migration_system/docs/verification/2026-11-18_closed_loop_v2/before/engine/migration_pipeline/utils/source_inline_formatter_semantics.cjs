// Recover callable inline formatters only when the resulting method exactly
// matches its registered Vue source method. Never evaluate source code.
const parser = require('@babel/parser'), t = require('@babel/types');
const traverse = require('@babel/traverse').default, generate = require('@babel/generator').default;
const {parse} = require('@vue/compiler-dom');
const {component, parentOf, key} = require('./inline_identifier_recovery.cjs');
const one = (o, name) => {
  const xs = o?.properties?.filter(p => key(p) === name) || [];
  return xs.length === 1 ? xs[0] : null;
};
const canonical = n => generate(n, {compact:true, comments:false}).code;
const mentions = name => new RegExp('(?<![\\w$])'+name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'(?![\\w$])','g');
const literal = n => t.isStringLiteral(n) || t.isNumericLiteral(n) || t.isBooleanLiteral(n)
  || t.isNullLiteral(n) || (t.isArrayExpression(n) && n.elements.every(literal))
  || (t.isObjectExpression(n) && n.properties.every(p => t.isObjectProperty(p)
    && key(p) && !['__proto__','constructor','prototype'].includes(key(p)) && literal(p.value)));

function readonly(method) {
  const ast = t.file(t.program([t.expressionStatement(t.objectExpression([t.cloneNode(method, true)]))]));
  let safe = true;
  traverse(ast, {
    ThisExpression() {safe=false;}, Super() {safe=false;},
    AssignmentExpression() {safe=false;}, UpdateExpression() {safe=false;},
    AwaitExpression() {safe=false;}, YieldExpression() {safe=false;}, ThrowStatement() {safe=false;},
    UnaryExpression(p) {if (p.node.operator === 'delete') safe=false;},
    ReferencedIdentifier(p) {
      if (!p.scope.getBinding(p.node.name) && !['Date','undefined'].includes(p.node.name)) safe=false;
    },
    NewExpression(p) {
      if (!t.isIdentifier(p.node.callee, {name:'Date'}) || p.scope.getBinding('Date')) safe=false;
    },
    CallExpression(p) {
      const c=p.node.callee;
      const b=t.isMemberExpression(c) && !c.computed && t.isIdentifier(c.object)
        && p.scope.getBinding(c.object.name);
      if (!b?.constant || !b.path.isVariableDeclarator() || !t.isNewExpression(b.path.node.init)
        || !t.isIdentifier(b.path.node.init.callee,{name:'Date'}) || p.scope.getBinding('Date')
        || !['getMonth','getDate','getFullYear','getTime','getHours','getMinutes','getSeconds',
          'toLocaleTimeString','toLocaleDateString'].includes(c.property.name)) safe=false;
    }
  });
  return safe;
}

function templateCalls(node, name, arity) {
  if (!t.isTemplateLiteral(node) || node.expressions.length
    || node.quasis[0].value.raw.includes('\\')) return false;
  const text=node.quasis[0].value.raw, errors=[], calls=[];
  const ast=parse(text,{onError:e=>errors.push(e)});
  if (errors.length) return false;
  let safe=true;
  const expression=(value,base)=>{
    for (const m of value.matchAll(/\{\{([\s\S]*?)\}\}/g)) {
      let expr;
      try {expr=parser.parseExpression(m[1]);} catch (_) {safe=false;continue;}
      const visit=n=>{
        if (!n || typeof n!=='object') return;
        if (Array.isArray(n)) {n.forEach(visit);return;}
        if (t.isCallExpression(n) && t.isIdentifier(n.callee,{name})) {
          if (n.optional || n.arguments.length!==arity || n.arguments.some(a=>t.isSpreadElement(a))) safe=false;
          calls.push(base+m.index+2+n.callee.start);
        }
        for (const [k,v] of Object.entries(n)) if (!['loc','extra','comments'].includes(k)) visit(v);
      };
      visit(expr);
    }
  };
  const visit=n=>{
    if (n.type===1) for (const p of n.props) if (p.type===6 && p.value) {
      const raw=p.value.loc.source;
      if (!['"',"'"].includes(raw[0])) {safe=false;continue;}
      expression(raw.slice(1,-1),p.value.loc.start.offset+1);
    }
    if (n.type===5) expression(text.slice(n.loc.start.offset,n.loc.end.offset),n.loc.start.offset);
    (n.children||[]).forEach(visit);
  };
  visit(ast);
  const tokens=[...text.matchAll(mentions(name))];
  return safe && calls.length>0 && tokens.length===calls.length && tokens.every(m=>calls.includes(m.index));
}

function normalize(code, ssm) {
  const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code);
  const fallback={code,changes:[],formatter_proofs:[]};
  if (!block) return fallback;
  const script=block[1], offset=block.index+block[0].indexOf('>')+1;
  const ast=parser.parse(script,{sourceType:'unambiguous'}), parent=parentOf(ast);
  const registry=one(parent,'components')?.value;
  if (!t.isObjectExpression(registry) || registry.properties.some(p=>!key(p))) return fallback;
  const declarations=new Map();
  traverse(ast,{VariableDeclarator(p) {
    if (t.isIdentifier(p.node.id) && component(p.node.init)) {
      const xs=declarations.get(p.node.id.name)||[];
      xs.push(p);declarations.set(p.node.id.name,xs);
    }
  }});
  const contracts=ssm?.script?.options?.components || [];
  const edits=[], proofs=[], visited=new Set();
  for (const contract of contracts) {
    if (contracts.filter(c=>c.registered_tag===contract.registered_tag).length!==1) continue;
    const reg=one(registry,contract.registered_tag);
    if (!t.isIdentifier(reg?.value)) continue;
    const xs=declarations.get(reg.value.name)||[];
    if (xs.length!==1 || visited.has(reg.value.name)) continue;
    visited.add(reg.value.name);
    const path=xs[0], binding=path.scope.getBinding(reg.value.name);
    // All uses must be direct registrations on this exported parent's registry.
    if (!binding?.constant || !binding.referencePaths.some(p=>p.node===reg.value)
      || binding.referencePaths.some(p=>!registry.properties.some(r=>r.value===p.node))) continue;
    const related=contracts.filter(c=>{
      const r=one(registry,c.registered_tag);
      return t.isIdentifier(r?.value,{name:reg.value.name});
    });
    if (related.some(c=>c.inline_definition?.source_code!==contract.inline_definition?.source_code)) continue;
    const object=path.node.init.arguments[0];
    if (object.properties.some(p=>!key(p)) || new Set(object.properties.map(key)).size!==object.properties.length) continue;
    const computed=one(object,'computed')?.value, template=one(object,'template')?.value;
    if (!t.isObjectExpression(computed) || computed.properties.some(p=>!key(p))
      || new Set(computed.properties.map(key)).size!==computed.properties.length) continue;
    let source;
    try {source=parser.parseExpression(contract.inline_definition?.source_code || '');} catch (_) {continue;}
    if (!t.isObjectExpression(source) || source.properties.some(p=>!key(p))) continue;
    const methods=one(source,'methods')?.value;
    if (!t.isObjectExpression(methods)) continue;
    const selected=new Map();
    for (const method of computed.properties) {
      const name=key(method), original=one(methods,name);
      if (!/^[A-Za-z_$][\w$]*$/.test(name||'') || one(object,name)
        || !t.isObjectMethod(method) || method.kind!=='method' || method.async || method.generator
        || method.params.length || !t.isObjectMethod(original) || original.kind!=='method'
        || original.async || original.generator) continue;
      const statements=method.body.body, last=statements.at(-1), fn=t.isReturnStatement(last) && last.argument;
      if (!t.isArrowFunctionExpression(fn) || fn.async || !fn.params.length
        || fn.params.some(p=>!t.isIdentifier(p)) || !statements.slice(0,-1).every(s=>t.isVariableDeclaration(s,{kind:'const'})
          && s.declarations.every(d=>t.isIdentifier(d.id)&&literal(d.init)))) continue;
      const body=statements.slice(0,-1).concat(t.isBlockStatement(fn.body)?fn.body.body:[t.returnStatement(fn.body)]);
      const candidate=t.objectMethod('method',t.identifier(name),t.cloneNode(fn,true).params,t.blockStatement(body.map(s=>t.cloneNode(s,true))));
      if (canonical(candidate)!==canonical(original) || !readonly(candidate) || path.scope.getBinding('Date')
        || !templateCalls(template,name,fn.params.length)) continue;
      // Any other script-side mention (including data.get, cross-child and bare
      // references) makes changing the computed contract unsafe. Refuse it.
      const ranges=[template,method].sort((a,b)=>b.start-a.start);
      // The binding proof above forbids escaping component constructors. Sibling
      // definitions are separate scopes and may use identical formatter names.
      let other=script.slice(object.start,object.end);
      for (const r of ranges) other=other.slice(0,r.start-object.start)+other.slice(r.end-object.start);
      if (mentions(name).test(other)) continue;
      selected.set(method,generate(candidate,{comments:false}).code);
      proofs.push({registered_tag:contract.registered_tag,component:reg.value.name,method:name,
        proof:'literal_prefix_and_exact_readonly_source_method',arity:fn.params.length});
    }
    if (!selected.size) continue;
    // Replace the full computed member once to avoid overlapping comma removals.
    const kept=computed.properties.filter(p=>!selected.has(p)).map(p=>script.slice(p.start,p.end));
    edits.push({start:computed.start,end:computed.end,text:'{'+kept.join(',\n')+'}'});
    edits.push({start:object.start+1,end:object.start+1,text:'\n'+[...selected.values()].join(',\n')+',\n'});
  }
  if (!edits.length) return fallback;
  edits.sort((a,b)=>b.start-a.start);
  for (let i=1;i<edits.length;i++) if (edits[i].end>edits[i-1].start) throw Error('Overlapping formatter edits');
  let next=script;
  for (const e of edits) next=next.slice(0,e.start)+e.text+next.slice(e.end);
  parser.parse(next,{sourceType:'unambiguous'});
  return {code:code.slice(0,offset)+next+code.slice(offset+script.length),
    changes:['restored_source_inline_callable_formatters'],formatter_proofs:proofs};
}
module.exports={normalize};
