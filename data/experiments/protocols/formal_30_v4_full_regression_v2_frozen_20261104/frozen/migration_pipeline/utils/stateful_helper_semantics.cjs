// Explicit readonly data dependencies for private inline-child calculations.
// Update the method, every instance call and every template call as one edit.
const fs=require('fs'), parser=require('@babel/parser'), traverse=require('@babel/traverse').default;
const {parse,ErrorCodes}=require('@vue/compiler-dom');
const {selfContained}=require('./residual_semantics.cjs');
const {component,key,parentOf}=require('./inline_identifier_recovery.cjs');
const ownMember=n=>n?.type==='MemberExpression' && n.object.type==='ThisExpression';
const namePattern=name=>new RegExp('(?<![\\w$])'+name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'(?![\\w$])','g');
function templateExpressions(node) {
  if (node?.type!=='TemplateLiteral' || node.expressions.length || node.quasis[0].value.raw.includes('\\')) return null;
  const text=node.quasis[0].value.raw, errors=[], expressions=[];
  const ast=parse(text,{onError:e=>errors.push(e)});
  if (errors.some(e=>e.code!==ErrorCodes.DUPLICATE_ATTRIBUTE)) return null;
  const add=(text,start)=>{
    for (const match of text.matchAll(/\{\{([\s\S]*?)\}\}/g)) {
      const value=match[1], at=start+match.index+2;
      expressions.push({text:value,start:at,ast:parser.parseExpression(value)});
    }
  };
  const visit=n=>{
    if (n.type===1) for (const p of n.props) if (p.type===6 && p.value) {
      const raw=p.value.loc.source;
      if (!['"',"'"].includes(raw[0]) || raw.at(-1)!==raw[0]) throw Error('Unquoted attribute');
      add(raw.slice(1,-1),p.value.loc.start.offset+1);
    }
    if (n.type===5) add(text.slice(n.loc.start.offset,n.loc.end.offset),n.loc.start.offset);
    for (const c of n.children||[]) visit(c);
  };
  visit(ast);
  return {text,expressions,offset:node.quasis[0].start};
}
function run(input) {
  const code=input.code, block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code);
  if (!block) return {code,changes:[]};
  const script=block[1], offset=block.index+block[0].indexOf('>')+1;
  const ast=parser.parse(script,{sourceType:'unambiguous'}), edits=[], changes=[], proofs=[];
  const parent=parentOf(ast), registries=parent?.properties.filter(p=>key(p)==='components')||[];
  if (registries.length!==1 || registries[0].value?.type!=='ObjectExpression'
      || registries[0].value.properties.some(p=>!key(p))) return {code,changes:[],proofs:[]};
  const registered=new Set(registries[0].value.properties.filter(p=>p.type==='ObjectProperty'
    && p.value.type==='Identifier').map(p=>p.value));
  traverse(ast,{VariableDeclarator(path) {
    if (!component(path.node.init) || path.node.id.type!=='Identifier') return;
    const binding=path.scope.getBinding(path.node.id.name);
    if (!binding?.constant || binding.referencePaths.length!==1
        || !registered.has(binding.referencePaths[0].node)) return;
    const object=path.get('init.arguments.0'), template=object.get('properties').find(p=>key(p.node)==='template');
    if (!template || object.node.properties.filter(p=>key(p)==='template').length!==1) return;
    let rendered;
    try {rendered=templateExpressions(template.node.value);} catch(_) {return;}
    if (!rendered) return;
    const computed=object.node.properties.find(p=>key(p)==='computed')?.value;
    for (const method of object.get('properties')) {
      const n=method.node, name=key(n);
      if (!name || n.type!=='ObjectMethod' || n.kind!=='method' || n.async || n.generator
          || n.params.some(p=>p.type!=='Identifier') || object.node.properties.filter(p=>key(p)===name).length!==1) continue;
      const reads=[], fields=[];
      let safe=true;
      method.traverse({ThisExpression(p) {
        const call=p.parentPath.parentPath.parentPath;
        if (!call?.isCallExpression()) {safe=false;return;}
        const x=call.node;
        if (x.callee.type!=='MemberExpression' || x.callee.computed || x.callee.property.name!=='get'
            || !ownMember(x.callee.object) || x.callee.object.computed || x.callee.object.property.name!=='data'
            || x.arguments.length!==1 || x.arguments[0].type!=='StringLiteral'
            || !/^[A-Za-z_$][\w$]*$/.test(x.arguments[0].value)) {safe=false;return;}
        for (let a=p.parentPath; a && a!==method; a=a.parentPath)
          if (a.isFunction() && !a.isArrowFunctionExpression()) safe=false;
        const field=x.arguments[0].value;
        reads.push({start:x.start,end:x.end,field});
        if (!fields.includes(field)) fields.push(field);
      }});
      if (!safe || !reads.length) continue;
      const params=fields.map(field=>{
        let candidate='__dep_'+field;
        while (namePattern(candidate).test(script)) candidate+='_';
        return candidate;
      });
      let body=script.slice(n.body.start,n.body.end);
      for (const r of [...reads].sort((a,b)=>b.start-a.start)) body=body.slice(0,r.start-n.body.start)
        +params[fields.indexOf(r.field)]+body.slice(r.end-n.body.start);
      const hypothetical=parser.parse(`({${name}(${n.params.map(p=>p.name).concat(params).join(',')}) ${body}})`);
      let pure=false;
      traverse(hypothetical,{ObjectMethod(p){pure=selfContained(p);p.stop();}});
      if (!pure) continue;
      const pending=[], covered=[], templateCalls=[];
      const walk=(value,base)=>{
        if (!value || typeof value!=='object') return;
        if (value.type==='CallExpression' && value.callee.type==='Identifier' && value.callee.name===name) {
          if (value.arguments.length!==n.params.length || value.arguments.some(a=>a.type==='SpreadElement')) safe=false;
          pending.push({start:rendered.offset+base+value.end-1,end:rendered.offset+base+value.end-1,
            text:(value.arguments.length?', ':'')+fields.join(', ')});
          covered.push(base+value.callee.start);
          templateCalls.push(fields);
        }
        for (const [k,v] of Object.entries(value)) if (!['loc','extra'].includes(k) && v && typeof v==='object')
          if (Array.isArray(v)) v.forEach(x=>walk(x,base)); else walk(v,base);
      };
      for (const expr of rendered.expressions) walk(expr.ast,expr.start);
      for (const m of rendered.text.matchAll(namePattern(name)))
        if (!covered.includes(m.index)) safe=false; // bare references, events or comments: refuse.
      let callCount=templateCalls.length;
      object.traverse({MemberExpression(p) {
        if (!ownMember(p.node)) return;
        const matches=p.node.computed ? p.node.property.value===name : p.node.property.name===name;
        if (!matches) return;
        const call=p.parentPath;
        if (p.node.computed || !call.isCallExpression() || call.node.callee!==p.node
            || call.node.arguments.length!==n.params.length || call.node.arguments.some(a=>a.type==='SpreadElement')) {safe=false;return;}
        for (let a=call.parentPath; a && a!==object; a=a.parentPath) if (a.isFunction() && !a.isArrowFunctionExpression()
            && !(a.isObjectMethod() && [object.node,computed].includes(a.parentPath.node))) safe=false;
        pending.push({start:call.node.end-1,end:call.node.end-1,
          text:(call.node.arguments.length?', ':'')+fields.map(f=>`this.data.get('${f}')`).join(', ')});
        callCount++;
      }});
      if (!safe || !callCount) continue;
      pending.push(...reads.map(r=>({start:r.start,end:r.end,text:params[fields.indexOf(r.field)]})));
      const at=n.params.length ? n.params.at(-1).end : script.indexOf('(',n.start)+1;
      pending.push({start:at,end:at,text:(n.params.length?', ':'')+params.join(', ')});
      edits.push(...pending);
      proofs.push({component:path.node.id.name,method:name,fields,call_sites:callCount});
      changes.push('explicit_readonly_inline_helper_dependencies');
    }
  }});
  edits.sort((a,b)=>b.start-a.start);
  for (let i=1;i<edits.length;i++) if (edits[i].end>edits[i-1].start || edits[i].start===edits[i-1].start) throw Error('Overlapping dependency edits');
  let next=script;
  for (const e of edits) next=next.slice(0,e.start)+e.text+next.slice(e.end);
  if (edits.length) parser.parse(next,{sourceType:'unambiguous'});
  return {code:code.slice(0,offset)+next+code.slice(offset+script.length),changes:[...new Set(changes)],proofs};
}
try {process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
catch(e) {process.stdout.write(JSON.stringify({error:e.message}));}
