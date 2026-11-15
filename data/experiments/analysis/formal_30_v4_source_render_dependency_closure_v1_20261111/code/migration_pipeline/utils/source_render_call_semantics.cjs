// Lift only the exact source render call, never globally replace JS strings.
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types');
const traverse=require('@babel/traverse').default,generate=require('@babel/generator').default;
const dom=require('@vue/compiler-dom'),{parse:parseSFC}=require('@vue/compiler-sfc');
const {key,parentOf,component}=require('./inline_identifier_recovery.cjs');
const one=(o,k)=>{const xs=o?.properties?.filter(p=>key(p)===k)||[];return xs.length===1?xs[0]:null;};
const safe=o=>t.isObjectExpression(o)&&o.properties.every(p=>key(p))&&new Set(o.properties.map(key)).size===o.properties.length;
const ident=s=>typeof s==='string'&&/^[A-Za-z_$][\w$]*$/.test(s)&&!['__proto__','constructor','prototype','Math','$event'].includes(s);
const print=n=>generate(n,{compact:true,comments:false}).code;
const clean=n=>Array.isArray(n)?n.map(clean):n&&typeof n==='object'?Object.fromEntries(Object.entries(n)
 .filter(([k])=>!['start','end','loc','extra','comments','leadingComments','trailingComments','innerComments'].includes(k))
 .map(([k,v])=>[k,clean(v)])):n;
const same=(a,b)=>print(clean(a))===print(clean(b));
const expr=s=>parser.parseExpression(s);
const own=(n,k)=>t.isMemberExpression(n)&&!n.computed&&t.isThisExpression(n.object)&&t.isIdentifier(n.property,{name:k});
const normalizeTag=s=>s.replace(/([a-z0-9])([A-Z])/g,'$1-$2').toLowerCase();
function walk(n,fn){if(!n||typeof n!=='object')return;if(Array.isArray(n)){n.forEach(v=>walk(v,fn));return;}
 fn(n);for(const [k,v] of Object.entries(n))if(!['loc','extra','comments'].includes(k))walk(v,fn);}
function sourceParent(ast){const xs=ast.program.body.filter(s=>t.isExportDefaultDeclaration(s)).map(s=>s.declaration)
 .concat(ast.program.body.filter(s=>t.isExpressionStatement(s)&&t.isAssignmentExpression(s.expression,{operator:'='})
 &&t.isMemberExpression(s.expression.left)&&!s.expression.left.computed&&s.expression.left.object.name==='module'
 &&s.expression.left.property.name==='exports').map(s=>s.expression.right));return xs.length===1&&safe(xs[0])?xs[0]:null;}
function registered(ast,parent,tag,san){const registry=one(parent,'components')?.value;if(!safe(registry))return null;
 const registrations=registry.properties.filter(p=>normalizeTag(key(p))===tag);
 if(!registrations.length||registrations.some(p=>!t.isIdentifier(p.value))||new Set(registrations.map(p=>p.value.name)).size!==1)return null;
 const name=registrations[0].value.name,paths=[];
 traverse(ast,{VariableDeclarator(p){if(t.isIdentifier(p.node.id,{name}))paths.push(p);}});
 if(paths.length!==1)return null;
 const path=paths[0],binding=path.scope.getBinding(name),object=san?(component(path.node.init)?path.node.init.arguments[0]:null):path.node.init;
 if(!safe(object)||one(object,'mixins')||one(object,'extends')||!binding?.constant
  ||!binding.referencePaths.length||binding.referencePaths.some(p=>!registry.properties.some(r=>r.value===p.node))
  ||registry.properties.some(p=>t.isIdentifier(p.value,{name})&&normalizeTag(key(p))!==tag))return null;
 return {name,object,path};}
function inline(o){const n=one(o,'template')?.value;if(!t.isTemplateLiteral(n)||n.expressions.length||n.quasis[0].value.raw.includes('\\'))return null;
 const text=n.quasis[0].value.raw,errors=[],ast=dom.parse(text,{onError:e=>errors.push(e)});return errors.length?null:{text,ast,node:n};}
function method(o,k){const m=one(o,k);return t.isObjectMethod(m)&&m.kind==='method'&&!m.async&&!m.generator
 &&m.params.every(p=>t.isIdentifier(p)&&ident(p.name))&&new Set(m.params.map(p=>p.name)).size===m.params.length?m:null;}
function declared(o,source){const names=new Set();
 const p=one(o,source?'props':'dataTypes')?.value;
 if(t.isArrayExpression(p))p.elements.forEach(n=>{if(t.isStringLiteral(n))names.add(n.value);});
 if(safe(p))p.properties.forEach(p=>names.add(key(p)));
 const m=method(o,source?'data':'initData');
 for(const s of m?.body.body||[])if(t.isReturnStatement(s)&&t.isObjectExpression(s.argument))s.argument.properties.forEach(p=>{if(key(p))names.add(key(p));});
 return names;}
function pathOf(n){if(t.isIdentifier(n))return [n.name];
 if(t.isMemberExpression(n)&&!n.computed&&t.isIdentifier(n.property)){const path=pathOf(n.object);return path&&path.concat(n.property.name);}return null;}
function arrayPath(o,path){
 const field=(object,name)=>{if(!t.isObjectExpression(object))return null;let found=null;
  for(const p of object.properties){if(t.isSpreadElement(p)&&found)found=null;if(key(p)===name)found=p.value;}return found;};
 const project=(n,parts,seen=new Set())=>{
  if(t.isConditionalExpression(n))return project(n.consequent,parts,seen)&&project(n.alternate,parts,seen);
  if(t.isCallExpression(n)&&t.isMemberExpression(n.callee)&&!n.callee.computed&&t.isThisExpression(n.callee.object)){
   const name=n.callee.property.name,m=method(one(o,'methods')?.value,name);
   if(!m||seen.has(name)||m.body.body.length!==1||!t.isReturnStatement(m.body.body[0]))return false;
   return project(m.body.body[0].argument,parts,new Set([...seen,name]));
  }
  if(!parts.length)return t.isArrayExpression(n);
  return project(field(n,parts[0]),parts.slice(1),seen);
 };
 if(path.length===1){const props=one(o,'props')?.value,p=one(props,path[0])?.value;
  if(t.isIdentifier(p,{name:'Array'})||t.isIdentifier(one(p,'type')?.value,{name:'Array'}))return true;}
 const data=method(o,'data');return !!data&&data.body.body.length===1&&t.isReturnStatement(data.body.body[0])
  &&project(data.body.body[0].argument,path);
}
function entries(render,vue){const result=[];
 const nodes=n=>(n.children||[]).filter(c=>c.type===1);
 const go=(n,path,scopes=[],aliases=[],inherited=true)=>{
  if(n.type!==1)return;
  let valid=inherited,local=[...aliases],signature=[];
  for(const p of n.props){const name=vue&&p.type===7?p.name:!vue&&p.type===6&&p.name.startsWith('s-')?p.name.slice(2):null;
   if(name==='slot'||['slot-scope','scope'].includes(p.name))valid=false;
   if(!['for','if','else-if','else'].includes(name))continue;
   let value=(vue?p.exp?.content:p.value?.content)||'';
   if(name==='for'){
    const m=/^\s*\(?\s*([A-Za-z_$][\w$]*)(?:\s*,\s*([A-Za-z_$][\w$]*))?\s*\)?\s+in\s+([\w$.]+)(?:\s+trackby\s+[\w$.]+)?\s*$/.exec(value);
    if(!m||!ident(m[1])||(m[2]&&!ident(m[2]))||[m[1],m[2]].filter(Boolean).some(a=>local.includes(a)))valid=false;
    else{local.push(...[m[1],m[2]].filter(Boolean));value=[m[1],m[2]||'',m[3]].join(':');}
   }else if(value){try{value=print(expr(value));}catch(_){valid=false;}}
   signature.push([name,value]);
  }
  const context=scopes.concat([JSON.stringify(signature.sort())]);
  const classes=n.props.filter(p=>p.type===6&&p.name==='class');
  const staticClass=classes.length<=1?(classes[0]?.value?.content||'').replace(/\{\{[^{}]*\}\}/g,'').trim().split(/\s+/).filter(Boolean):null;
  const add=(value,start,role,adjacent=null)=>{try{let node=expr(value);
   if(vue&&role==='attr:class:0'&&t.isObjectExpression(node)&&node.properties.length===1){
    const p=node.properties[0],token=key(p);
    if(t.isObjectProperty(p)&&!p.computed&&/^[A-Za-z_][\w-]*$/.test(token||''))node=t.conditionalExpression(p.value,t.stringLiteral(token),t.stringLiteral(''));
   }
   result.push({node,start,role,path,scope:JSON.stringify(context),aliases:local,valid,staticClass,adjacent});}catch(_){}};
  for(const p of n.props){
   if(vue&&p.type===7&&p.name==='bind'&&p.arg?.isStatic&&!p.modifiers.length&&p.exp){
    add(p.exp.content,p.exp.loc.start.offset,'attr:'+p.arg.content+':0');
   }else if(!vue&&p.type===6&&p.value&&!p.name.startsWith('on-')&&!p.name.startsWith('s-')){
    const raw=p.value.loc.source;if(!['"',"'"].includes(raw[0])||raw.at(-1)!==raw[0]||/&(?:#|\w+;)/.test(raw)){valid=false;continue;}
    const inner=raw.slice(1,-1);let index=0;
    for(const m of inner.matchAll(/\{\{([^{}]*?)\}\}/g))add(m[1],p.value.loc.start.offset+1+m.index+2,'attr:'+p.name+':'+index++);
   }
  }
  let textIndex=0;
  for(const [i,c] of (n.children||[]).entries())if(c.type===5){const before=n.children[i-1],after=n.children[i+1];
   add(c.content.content,c.content.loc.start.offset,'text:'+textIndex++,
    [before?.type===2?before.content.trim():'',after?.type===2?after.content.trim():'']);}
  nodes(n).forEach((c,i)=>go(c,path+'/'+c.tag+'['+i+']',context,local,valid));
 };
 nodes(render.ast).forEach((n,i)=>go(n,'/'+n.tag+'['+i+']'));return result;}
const maths=new Set(['abs','min','max','floor','ceil','round','pow','sqrt']);
function kind(n,source,names,aliases){if(!t.isCallExpression(n)||n.optional||!t.isMemberExpression(n.callee)||n.callee.computed||n.arguments.some(a=>t.isSpreadElement(a)))return null;
 const member=n.callee.property.name,receiver=pathOf(n.callee.object);
 const operand=a=>{const path=pathOf(a);return path?ident(path[0])&&(names.has(path[0])||aliases.includes(path[0])):
  t.isStringLiteral(a)||t.isNumericLiteral(a)||t.isBooleanLiteral(a)||t.isNullLiteral(a)
  ||(t.isUnaryExpression(a)&&['+','-'].includes(a.operator)&&t.isNumericLiteral(a.argument));};
 if(t.isIdentifier(n.callee.object,{name:'Math'})&&maths.has(member)&&!names.has('Math')&&n.arguments.length>0&&n.arguments.every(operand))return 'math';
 if(member==='includes'&&receiver&&!aliases.includes(receiver[0])&&arrayPath(source,receiver)&&n.arguments.length>=1&&n.arguments.length<=2&&n.arguments.every(operand))return 'includes';
 return null;}
function expand(node,target){const clone=t.cloneNode(node,true),expanded=[];let bad=false;
 const visit=n=>{
  if(!n||typeof n!=='object')return n;if(Array.isArray(n))return n.map(visit);
  if(t.isCallExpression(n)&&t.isIdentifier(n.callee)&&!n.optional){
   const m=method(target,n.callee.name);
   if(m&&m.params.length===n.arguments.length&&m.body.body.length===1&&t.isReturnStatement(m.body.body[0])){
    const value=m.body.body[0].argument;
    if(t.isCallExpression(value)&&t.isMemberExpression(value.callee)&&!value.callee.computed&&value.arguments.every(a=>t.isIdentifier(a))){
     const refs=[...value.arguments];if(!t.isIdentifier(value.callee.object,{name:'Math'}))refs.unshift(value.callee.object);
     const names=m.params.map(p=>p.name);
     if(refs.length===names.length&&refs.every((r,i)=>t.isIdentifier(r,{name:names[i]}))){
      const result=t.cloneNode(value,true),args=n.arguments;
      if(t.isIdentifier(result.callee.object,{name:'Math'}))result.arguments=args.map(a=>t.cloneNode(a,true));
      else{result.callee.object=t.cloneNode(args[0],true);result.arguments=args.slice(1).map(a=>t.cloneNode(a,true));}
      expanded.push({helper:n.callee.name,original:n,call:result});return result;
     }
    }
   }
  }
  for(const k of Object.keys(n))if(!['loc','extra','comments'].includes(k))n[k]=visit(n[k]);return n;
 };return {node:visit(clone),expanded,bad};}
function analyze(input){
 const result={code:input.code,findings:[],changes:[],proofs:[],reviews:[],mapped_bindings:[]};
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(input.code),src=parseSFC(input.vue);
 if(!block||src.errors.length||!src.descriptor.script||src.descriptor.scriptSetup)return result;
 const script=block[1],offset=block.index+block[0].indexOf('>')+1,ast=parser.parse(script,{sourceType:'unambiguous'}),sourceAst=parser.parse(src.descriptor.script.content,{sourceType:'unambiguous'});
 let runtime;traverse(ast,{Program(p){runtime=p.scope.getBinding('san');p.stop();}});
 if(!runtime?.constant||!runtime.path.isVariableDeclarator()||!t.isCallExpression(runtime.path.node.init)
  ||!t.isIdentifier(runtime.path.node.init.callee,{name:'require'})||runtime.path.node.init.arguments.length!==1
  ||!t.isStringLiteral(runtime.path.node.init.arguments[0],{value:'san'}))return result;
 const parent=parentOf(ast),sp=sourceParent(sourceAst);if(!safe(parent)||!sp||one(sp,'mixins')||one(sp,'extends'))return result;
 const used=new Set([...script.matchAll(/[A-Za-z_$][\w$]*/g)].map(m=>m[0]));
 const fresh=()=>{let i=0,name;do{name='__sourceRenderCall_'+i++;}while(used.has(name));used.add(name);return name;};
 const edits=[],contracts=input.ssm?.script?.options?.components||[],visited=new Set();
 for(const c of contracts){const tag=c.registered_tag;if(contracts.filter(x=>x.registered_tag===tag).length!==1)continue;
  const a=registered(sourceAst,sp,tag,false),b=registered(ast,parent,tag,true);
  if(!a||!b||visited.has(b.name))continue;visited.add(b.name);
  let original;try{original=expr(c.inline_definition?.source_code||'');}catch(_){continue;}
  if(!safe(original)||!same(original,a.object))continue;
  const sa=inline(a.object),sb=inline(b.object);if(!sa||!sb)continue;
  // Reject lexical/global shadowing and explicit Math/Array prototype rewrites.
  let shadow=false;traverse(ast,{Scope(p){if(p.scope.hasOwnBinding('Math')||p.scope.hasOwnBinding('Array'))shadow=true;}});
  traverse(sourceAst,{Scope(p){if(p.scope.hasOwnBinding('Math')||p.scope.hasOwnBinding('Array'))shadow=true;}});
  for(const tree of [sourceAst,ast])walk(tree,n=>{if(t.isAssignmentExpression(n)&&t.isMemberExpression(n.left)&&/^(Math\.|Array\.prototype\.)/.test(print(n.left)))shadow=true;});
  if(shadow)continue;
  const names=declared(a.object,true),targetNames=declared(b.object,false),sourceEntries=entries(sa,true),targetEntries=entries(sb,false),additions=[];
  for(const s of sourceEntries){if(!s.valid)continue;
   const calls=[];walk(s.node,n=>{const k=kind(n,a.object,names,s.aliases);if(k)calls.push({node:n,kind:k});});
   if(!calls.length)continue;
   const matches=targetEntries.filter(x=>x.path===s.path&&x.role===s.role&&x.scope===s.scope&&x.valid);
   const id='script.'+tag+'.template'+s.path+'#'+s.role;
   if(matches.length!==1){result.reviews.push({binding:id,reason:'unmatched_render_element_or_scope'});continue;}
   result.mapped_bindings.push(id);
   const target=matches[0],restored=expand(target.node,b.object);
   if(!s.staticClass||!target.staticClass||JSON.stringify(s.staticClass)!==JSON.stringify(target.staticClass)
    ||JSON.stringify(s.adjacent)!==JSON.stringify(target.adjacent)){
    result.findings.push({code:'source_render_call_not_landed',location:id,message:'Source render call static class or adjacent literal text no longer matches.'});
    result.reviews.push({binding:id,reason:'conflicting_static_class_or_adjacent_literal'});continue;
   }
   if(!same(restored.node,s.node)){
    result.findings.push({code:'source_render_call_not_landed',location:id,message:'Source render call or its explicit operand helper no longer matches the source binding.'});
    result.reviews.push({binding:id,reason:'unknown_or_conflicting_target_expression'});continue;
   }
   const rawCalls=[];walk(target.node,n=>{const k=kind(n,a.object,names,target.aliases);if(k)rawCalls.push({node:n,kind:k});});
   if(!rawCalls.length){result.proofs.push({binding:id,proof:'exact_source_expression_via_explicit_operand_helpers',lifted:true});continue;}
   const roots=new Set();let valid=true;
   for(const call of rawCalls){const operands=call.kind==='math'?call.node.arguments:[call.node.callee.object,...call.node.arguments];
    operands.forEach(n=>{const p=pathOf(n);if(p&&!target.aliases.includes(p[0]))roots.add(p[0]);});
    if(operands.some(n=>{const p=pathOf(n);return p&&(!ident(p[0])||(!targetNames.has(p[0])&&!target.aliases.includes(p[0])));}))valid=false;
   }
   if(!valid){result.reviews.push({binding:id,reason:'undeclared_target_operands'});continue;}
   result.findings.push({code:'source_render_call_not_landed',location:id,message:'Source render member/global call requires a helper with every reactive operand passed explicitly.'});
   for(const call of rawCalls){const name=fresh(),operands=call.kind==='math'?call.node.arguments:[call.node.callee.object,...call.node.arguments];
    const params=operands.map((_,i)=>t.identifier('_operand'+i)),value=t.cloneNode(call.node,true);
    if(call.kind==='math')value.arguments=params.map(p=>t.cloneNode(p));
    else{value.callee.object=t.cloneNode(params[0]);value.arguments=params.slice(1).map(p=>t.cloneNode(p));}
    additions.push(t.objectMethod('method',t.identifier(name),params,t.blockStatement([t.returnStatement(value)])));
    const replacement=t.callExpression(t.identifier(name),operands.map(n=>t.cloneNode(n,true)));
    edits.push({start:offset+sb.node.quasis[0].start+target.start+call.node.start,
     end:offset+sb.node.quasis[0].start+target.start+call.node.end,text:print(replacement)});
    result.proofs.push({binding:id,helper:name,kind:call.kind,explicit_operands:operands.map(print),
     proof:'exact_source_call_and_declared_operand_scope',lifted:false});
   }
  }
  if(additions.length)edits.push({start:offset+b.object.start+1,end:offset+b.object.start+1,text:'\n'+additions.map(print).join(',\n')+',\n'});
 }
 edits.sort((a,b)=>b.start-a.start);for(let i=1;i<edits.length;i++)if(edits[i].end>edits[i-1].start)throw Error('Overlapping render-call edits');
 if(input.repair){for(const e of edits)result.code=result.code.slice(0,e.start)+e.text+result.code.slice(e.end);
  if(edits.length){parser.parse(/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(result.code)[1],{sourceType:'unambiguous'});result.changes=['lifted_source_render_calls_with_explicit_operands'];}}
 return result;
}
module.exports={one,safe,method,declared,arrayPath,print,same,clean,walk,sourceParent,entries,pathOf};
if(require.main===module){
 try{process.stdout.write(JSON.stringify(analyze(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(e){process.stdout.write(JSON.stringify({error:e.message}));}
}
