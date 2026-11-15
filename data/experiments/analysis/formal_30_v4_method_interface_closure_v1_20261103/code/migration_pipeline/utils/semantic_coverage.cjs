// Proof for one coverage transition, not a blanket exemption for parse errors.
const fs = require('fs');
const parser = require('@babel/parser');
const generate = require('@babel/generator').default;
const {parse, ErrorCodes} = require('@vue/compiler-dom');
const {recover, parentOf, component, key} = require('./inline_identifier_recovery.cjs');
const clean = n => Array.isArray(n) ? n.map(clean) : !n || typeof n !== 'object' ? n
  : Object.fromEntries(Object.entries(n).filter(([k]) => !['start','end','loc','extra','leadingComments','innerComments','trailingComments'].includes(k)).map(([k,v]) => [k,clean(v)]));
const canonical = n => generate(clean(n), {compact:true, comments:false}).code;
const one = (o,n) => {const ps=o?.properties.filter(p=>key(p)===n)||[]; return ps.length===1 ? ps[0] : null;};
function scopes(code) {
  const script = /<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code)?.[1];
  if (!script) throw Error('Missing script');
  const ast=parser.parse(script,{sourceType:'unambiguous'}), parent=parentOf(ast);
  const reg=one(parent,'components')?.value;
  if (reg?.type!=='ObjectExpression' || reg.properties.some(p=>!key(p))) throw Error('Ambiguous registry');
  const declarations=ast.program.body.flatMap(n=>n.type==='VariableDeclaration' ? n.declarations : []);
  const result=new Map();
  for (const p of reg.properties) {
    if (p.value?.type!=='Identifier') continue;
    const ds=declarations.filter(d=>d.id.name===p.value.name && component(d.init));
    if (ds.length!==1 || result.has(key(p))) throw Error('Ambiguous component');
    result.set(key(p),{name:p.value.name, object:ds[0].init.arguments[0]});
  }
  return {result,script,parent};
}
function renderCalls(object, method) {
  const node=one(object,'template')?.value;
  if (node?.type!=='TemplateLiteral' || node.expressions.length || node.quasis[0].value.raw.includes('\\')) return null;
  const text=node.quasis[0].value.raw, errors=[];
  const ast=parse(text,{onError:e=>errors.push(e)});
  if (errors.some(e=>e.code!==ErrorCodes.DUPLICATE_ATTRIBUTE)) return null;
  const result=[];
  const hasCall=n=>{
    if (!n || typeof n!=='object') return false;
    if (n.type==='CallExpression' && n.callee.type==='Identifier' && n.callee.name===method) return true;
    return Object.values(n).some(v=>Array.isArray(v) ? v.some(hasCall) : v && typeof v==='object' && hasCall(v));
  };
  const visit=(n,path)=>{
    if (n.type===1) for (const p of n.props) if (p.type===6 && p.value) {
      for (const m of p.value.content.matchAll(/\{\{([\s\S]*?)\}\}/g)) {
        const expr=parser.parseExpression(m[1]);
        if (hasCall(expr)) result.push({binding:p.name,path,expression:canonical(expr)});
      }
    }
    (n.children||[]).forEach((c,i)=>visit(c,path+'/'+(c.tag||c.type)+':'+i));
  };
  visit(ast,'root');
  return result;
}
function assess(input) {
  const recovered=recover(input.before,input.ssm);
  const fallback={status:'unproven', pairs:[], before_parse_status:recovered.parse_status};
  if (recovered.parse_status!=='source_registered_recovery') return fallback;
  const a=scopes(recovered.code), b=scopes(input.after), pairs=[];
  for (const [tag,left] of a.result) {
    const right=b.result.get(tag); if (!right) continue;
    for (const m of left.object.properties) {
      const name=key(m), other=one(right.object,name);
      if (!name || m.type!=='ObjectMethod' || other?.type!=='ObjectMethod'
          || canonical(m)!==canonical(other) || left.object.properties.filter(p=>key(p)===name).length!==1) continue;
      const before=renderCalls(left.object,name), after=renderCalls(right.object,name);
      if (!before || !after) continue;
      for (const binding of new Set(after.map(x=>x.binding))) {
        const xs=before.filter(x=>x.binding===binding), ys=after.filter(x=>x.binding===binding);
        if (!ys.length || JSON.stringify(xs)!==JSON.stringify(ys)) continue;
        pairs.push({tag,before_name:left.name,after_name:right.name,method:name,binding,
          render_calls:ys,method_sha256:require('crypto').createHash('sha256').update(canonical(m)).digest('hex')});
      }
    }
  }
  const earlyA=one(a.parent,'inited'), earlyB=one(b.parent,'inited');
  const parentInitedUnchanged=!!earlyA && !!earlyB && canonical(earlyA)===canonical(earlyB);
  return {status:'source_recovery_and_identical_scoped_calls', before_parse_status:recovered.parse_status,
    parent_inited_unchanged:parentInitedUnchanged,
    before_code:recovered.code,pairs};
}
try {process.stdout.write(JSON.stringify(assess(JSON.parse(fs.readFileSync(0,'utf8')))));}
catch(e) {process.stdout.write(JSON.stringify({status:'unproven',pairs:[],error:e.message}));}
