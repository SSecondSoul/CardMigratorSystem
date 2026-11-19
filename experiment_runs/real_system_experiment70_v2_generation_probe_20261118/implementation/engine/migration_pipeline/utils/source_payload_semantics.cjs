// A bounded two-ended event adapter, not an arbitrary emit/fire rewriter.
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types');
const traverse=require('@babel/traverse').default,generate=require('@babel/generator').default;
const dom=require('@vue/compiler-dom'),{parse:parseSFC}=require('@vue/compiler-sfc');
const {key,component,parentOf}=require('./inline_identifier_recovery.cjs');
const one=(o,k)=>{const xs=o?.properties?.filter(p=>key(p)===k)||[];return xs.length===1?xs[0]:null;};
const safe=o=>t.isObjectExpression(o)&&o.properties.every(p=>key(p))&&new Set(o.properties.map(key)).size===o.properties.length;
const ident=s=>typeof s==='string'&&/^[A-Za-z_$][\w$]*$/.test(s)&&!['__proto__','constructor','prototype','$event'].includes(s);
const print=n=>generate(n,{compact:true,comments:false}).code;
const expr=s=>parser.parseExpression(s);
const method=(o,k)=>{const m=one(o,k);return t.isObjectMethod(m)&&m.kind==='method'&&!m.async&&!m.generator
 &&m.params.every(p=>t.isIdentifier(p)&&ident(p.name))&&new Set(m.params.map(p=>p.name)).size===m.params.length?m:null;};
const own=(n,k)=>t.isMemberExpression(n)&&!n.computed&&t.isThisExpression(n.object)&&t.isIdentifier(n.property,{name:k});
const children=n=>(n.children||[]).filter(c=>c.type===1);
const shape=(a,b)=>children(a).length===children(b).length&&children(a).every((n,i)=>n.tag===children(b)[i].tag&&shape(n,children(b)[i]));
function template(text){const errors=[];const ast=dom.parse(text,{onError:e=>errors.push(e)});return errors.length?null:{ast,text};}
function walk(node,fn){if(!node||typeof node!=='object')return;if(Array.isArray(node)){node.forEach(n=>walk(n,fn));return;}
 fn(node);for(const [k,v] of Object.entries(node))if(!['loc','extra','comments'].includes(k))walk(v,fn);}
function sourceParent(ast){const xs=ast.program.body.filter(s=>t.isExportDefaultDeclaration(s)).map(s=>s.declaration)
 .concat(ast.program.body.filter(s=>t.isExpressionStatement(s)&&t.isAssignmentExpression(s.expression,{operator:'='})
 &&t.isMemberExpression(s.expression.left)&&!s.expression.left.computed
 &&s.expression.left.object.name==='module'&&s.expression.left.property.name==='exports').map(s=>s.expression.right));
 return xs.length===1&&safe(xs[0])?xs[0]:null;}
function childObject(ast,parent,tag,san){
 const reg=one(parent,'components')?.value,r=one(reg,tag);
 if(!safe(reg)||!t.isIdentifier(r?.value))return null;
 const xs=[];traverse(ast,{VariableDeclarator(p){if(t.isIdentifier(p.node.id,{name:r.value.name}))xs.push(p);}});
 if(xs.length!==1)return null;
 const p=xs[0],binding=p.scope.getBinding(r.value.name),object=san?(component(p.node.init)?p.node.init.arguments[0]:null):p.node.init;
 if(!safe(object)||one(object,'mixins')||one(object,'extends')||!binding?.constant
  ||!binding.referencePaths.some(p=>p.node===r.value)
  ||binding.referencePaths.some(p=>!reg.properties.some(r=>r.value===p.node)))return null;
 return {object,name:r.value.name,aliases:reg.properties.filter(p=>t.isIdentifier(p.value,{name:r.value.name})).map(key)};
}
function quoted(p,text){const raw=p?.value?.loc.source;
 if(!raw||!['"',"'"].includes(raw[0])||raw.at(-1)!==raw[0]||/&(?:#|\w+;)/.test(raw))return null;
 const start=p.value.loc.start.offset+1;return text.slice(start,start+raw.length-2)===raw.slice(1,-1)?{start,end:start+raw.length-2,value:raw.slice(1,-1),quote:raw[0]}:null;
}
function events(n,vue){return n.props.filter(p=>vue?p.type===7&&p.name==='on'&&p.arg?.isStatic:p.type===6&&p.name.startsWith('on-'));}
function eventName(p,vue){return vue?p.arg.content:p.name.slice(3);}
function eventExpr(p,vue){try{return expr(vue?p.exp?.content:p.value?.content);}catch(_){return null;}}
function emit(n,source){return t.isCallExpression(n)&&!n.optional&&(source?(t.isIdentifier(n.callee,{name:'$emit'})||own(n.callee,'$emit'))
 :(t.isIdentifier(n.callee,{name:'fire'})||own(n.callee,'fire')));}
function inlineTemplate(o){const n=one(o,'template')?.value;return t.isTemplateLiteral(n)&&!n.expressions.length&&!n.quasis[0].value.raw.includes('\\')?{node:n,...template(n.quasis[0].value.raw)}:null;}
function scope(n,vue){return n.props.filter(p=>vue?p.type===7&&['for','if','else-if','else'].includes(p.name)
 :p.type===6&&['s-for','s-if','s-else-if','s-else'].includes(p.name)).map(p=>{
 let name=vue?p.name:p.name.slice(2),value=(vue?p.exp?.content:p.value?.content)||'';
 if(name==='for')value=value.replace(/^\s*\(([^()]*)\)\s+in\s+/,'$1 in ').replace(/\s+trackby\s+.*$/,'').replace(/\s+/g,'').trim();
 else if(value){try{value=print(expr(value));}catch(_){return null;}}
 return [name,value];}).sort((a,b)=>String(a).localeCompare(String(b)));}
function pairs(a,b){if(!a?.ast||!b?.ast||!shape(a.ast,b.ast))return null;const rows=[];
 const go=(s,n,path,valid=true)=>{valid=valid&&JSON.stringify(scope(s,true))===JSON.stringify(scope(n,false))
  &&!s.props.some(p=>(p.type===7&&p.name==='slot')||(p.type===6&&['slot-scope','scope'].includes(p.name)));
 rows.push({s,n,path,valid});children(s).forEach((c,i)=>go(c,children(n)[i],path+'/'+c.tag+'['+i+']',valid));};
 children(a.ast).forEach((s,i)=>go(s,children(b.ast)[i],'/'+s.tag+'['+i+']'));return rows;}
function packed(n,fields){return t.isObjectExpression(n)&&n.properties.length===fields.length&&fields.every((f,i)=>
 t.isObjectProperty(n.properties[i])&&!n.properties[i].computed&&key(n.properties[i])===f);}
function simple(n){if(t.isIdentifier(n))return true;if(t.isStringLiteral(n)||t.isBooleanLiteral(n)||t.isNumericLiteral(n)||t.isNullLiteral(n))return true;
 return t.isMemberExpression(n)&&!n.computed&&t.isIdentifier(n.property)&&simple(n.object);}
function substitute(n,params,args){if(t.isIdentifier(n)&&params.includes(n.name))return args[params.indexOf(n.name)];
 if(t.isMemberExpression(n)&&!n.computed)return t.memberExpression(substitute(n.object,params,args),t.cloneNode(n.property));return t.cloneNode(n,true);}
function analyze(input){
 const result={code:input.code,findings:[],changes:[],proofs:[],reviews:[],mapped_contracts:[],proven_bindings:[]};
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(input.code),outer=/<template\b[^>]*>([\s\S]*?)<\/template\s*>/i.exec(input.code);
 const parsed=parseSFC(input.vue);if(!block||!outer||parsed.errors.length||!parsed.descriptor.script||!parsed.descriptor.template||parsed.descriptor.scriptSetup)return result;
 const script=block[1],offset=block.index+block[0].indexOf('>')+1,outerOffset=outer.index+outer[0].indexOf('>')+1;
 const ast=parser.parse(script,{sourceType:'unambiguous'}),srcAst=parser.parse(parsed.descriptor.script.content,{sourceType:'unambiguous'});
 let runtimeBinding;
 traverse(ast,{Program(p){runtimeBinding=p.scope.getBinding('san');p.stop();}});
 if(!runtimeBinding?.constant||!runtimeBinding.path.isVariableDeclarator()
  ||!t.isCallExpression(runtimeBinding.path.node.init)||!t.isIdentifier(runtimeBinding.path.node.init.callee,{name:'require'})
  ||runtimeBinding.path.node.init.arguments.length!==1||!t.isStringLiteral(runtimeBinding.path.node.init.arguments[0],{value:'san'}))return result;
 const parent=parentOf(ast),srcParent=sourceParent(srcAst);
 if(!safe(parent)||!srcParent||one(srcParent,'mixins')||one(srcParent,'extends'))return result;
 const outerA=template(parsed.descriptor.template.content),outerB=template(outer[1]),outerPairs=pairs(outerA,outerB);
 const contracts=input.ssm?.script?.options?.components||[],edits=[],visited=new Set();
 for(const contract of contracts){
  const tag=contract.registered_tag;
  if(contracts.filter(c=>c.registered_tag===tag).length!==1)continue;
  const source=childObject(srcAst,srcParent,tag,false),target=childObject(ast,parent,tag,true);
  // Vue registry often uses PascalCase while SSM exposes kebab-case tags.
  const srcRegistry=one(srcParent,'components')?.value;
  const sourceNames=safe(srcRegistry)?srcRegistry.properties.map(key).filter(k=>k.replace(/([a-z0-9])([A-Z])/g,'$1-$2').toLowerCase()===tag):[];
  const src=source||(sourceNames.length===1?childObject(srcAst,srcParent,sourceNames[0],false):null);
  if(!src||!target||visited.has(target.name)||one(src.object,'$emit')||one(target.object,'fire'))continue;visited.add(target.name);
  let declared;try{declared=expr(contract.inline_definition?.source_code||'');}catch(_){continue;}
  if(!safe(declared)||print(declared)!==print(src.object)||target.aliases.some(alias=>
   alias.replace(/([a-z0-9])([A-Z])/g,'$1-$2').toLowerCase()!==tag||contracts.some(c=>c.registered_tag===alias
   &&c.inline_definition?.source_code!==contract.inline_definition?.source_code)))continue;
  const a=inlineTemplate(src.object),b=inlineTemplate(target.object);if(!a?.ast)continue;
  const sourceEmits=[];const visit=n=>{if(n.type===1)for(const p of events(n,true)){const call=eventExpr(p,true);
   if(emit(call,true)&&t.isStringLiteral(call.arguments[0])&&call.arguments.length>2)sourceEmits.push({node:n,attribute:p,call,event:call.arguments[0].value});}
   children(n).forEach(visit);};children(a.ast).forEach(visit);
  for(const event of new Set(sourceEmits.map(e=>e.event))){
   const id=tag+'@'+event,review=reason=>result.reviews.push({contract:id,reason});
   const entries=sourceEmits.filter(e=>e.event===event);
   let sourceAmbiguous=false;
   walk(src.object,n=>{if(emit(n,true)&&(!t.isStringLiteral(n.arguments[0])||n.arguments[0].value===event))sourceAmbiguous=true;});
   const sourceTV=n=>{if(n.type===1)for(const p of events(n,true)){const c=eventExpr(p,true);if(c)walk(c,x=>{
    if(emit(x,true)&&(!t.isStringLiteral(x.arguments[0])||x.arguments[0].value===event)&&!entries.some(e=>e.attribute===p&&print(e.call)===print(x)))sourceAmbiguous=true;
   });}children(n).forEach(sourceTV);};children(a.ast).forEach(sourceTV);
   if(sourceAmbiguous){review('unaccounted_source_emitter');continue;}
   if(!outerPairs||!b?.ast){review('unmatched_template_structure');continue;}
   const cp=pairs(a,b);if(!cp){review('unmatched_child_structure');continue;}
   const consumers=outerPairs.filter(p=>p.s.tag===tag);
   if(!consumers.length||consumers.some(p=>!p.valid||p.s.props.some(a=>a.name==='ref'||a.name==='is'
    ||(a.type===7&&((a.name==='bind'&&!a.arg)||(a.name==='on'&&!a.arg)))))){review('unmatched_consumer_scope');continue;}
   const receivers=[];let supported=true;
   for(const row of consumers){const srcEvents=events(row.s,true).filter(p=>eventName(p,true)===event),dstEvents=events(row.n,false).filter(p=>eventName(p,false)===event);
    if(srcEvents.length!==1||srcEvents[0].modifiers.length){supported=false;break;}
    const fn=eventExpr(srcEvents[0],true),sm=t.isIdentifier(fn)&&method(one(srcParent,'methods')?.value,fn.name),tm=t.isIdentifier(fn)&&method(parent,fn.name);
    if(!sm||!tm||sm.params.length<2||sm.params.length>4||print(t.arrayExpression(sm.params))!==print(t.arrayExpression(tm.params))){supported=false;break;}
    const fields=sm.params.map(p=>p.name),p=dstEvents.length===1?dstEvents[0]:null,q=quoted(p,outerB.text),n=p?eventExpr(p,false):null;
    const desired=fn.name+'('+fields.map(f=>'$event.'+f).join(',')+')';
    const state=n&&print(n)===desired?'packed':t.isIdentifier(n,{name:fn.name})?'legacy':'unknown';
    receivers.push({row,fields,handler:fn.name,p,q,state,desired});
   }
   if(!supported||new Set(receivers.map(r=>JSON.stringify([r.handler,r.fields]))).size!==1){review('unsupported_or_conflicting_receiver');continue;}
   const fields=receivers[0].fields,matched=[],scriptCalls=new Set();
   for(const entry of entries){const row=cp.find(p=>p.s===entry.node);if(!row?.valid||entry.attribute.modifiers.length||entry.call.arguments.length!==fields.length+1){supported=false;break;}
    const es=events(row.n,false).filter(p=>eventName(p,false)===entry.attribute.arg.content);
    const p=es.length===1?es[0]:null,q=quoted(p,b.text),call=p?eventExpr(p,false):null;
    if(!q||!call){supported=false;break;}
    let fire=call,params=[],args=[],scriptFire=false;
    if(!emit(call,false)){
     const name=t.isIdentifier(call)?call.name:t.isCallExpression(call)&&t.isIdentifier(call.callee)?call.callee.name:null;
     const m=name&&method(target.object,name);if(!m){supported=false;break;}
     params=m.params.map(p=>p.name);args=t.isIdentifier(call)?[t.identifier('$event')]:call.arguments;
     if(args.length!==params.length||!args.every(simple)){supported=false;break;}
     const statements=m.body.body,last=statements.at(-1);fire=t.isExpressionStatement(last)?last.expression:null;
     // Preserve harmless existing read prefixes verbatim; do not create effects.
     if(!statements.slice(0,-1).every(s=>t.isVariableDeclaration(s,{kind:'const'})&&s.declarations.every(d=>t.isIdentifier(d.id)
      &&t.isCallExpression(d.init)&&t.isMemberExpression(d.init.callee)&&!d.init.callee.computed&&own(d.init.callee.object,'data')
      &&t.isIdentifier(d.init.callee.property,{name:'get'})&&d.init.arguments.length===1&&t.isStringLiteral(d.init.arguments[0])
      &&!params.includes(d.id.name)))){supported=false;break;}
     scriptFire=true;
    }
    if(!emit(fire,false)||!t.isStringLiteral(fire.arguments[0],{value:event})){supported=false;break;}
    const state=fire.arguments.length===fields.length+1?'legacy':fire.arguments.length===2&&packed(fire.arguments[1],fields)?'packed':'unknown';
    const values=state==='legacy'?fire.arguments.slice(1):state==='packed'?fire.arguments[1].properties.map(p=>p.value):[];
    if(state==='unknown'||!values.every(simple)||values.some((v,i)=>print(substitute(v,params,args))!==print(entry.call.arguments[i+1]))){supported=false;break;}
    if(scriptFire)scriptCalls.add(fire);
    matched.push({row,p,q,fire,state,scriptFire});
   }
   // Refuse a second unaccounted emitter, including unknown/dynamic event names.
   const allScript=[],fireMembers=[],allFireCalls=[];let opaqueFire=false;
   walk(target.object,n=>{
    if(emit(n,false))allFireCalls.push(n);
    if(emit(n,false)&&(!t.isStringLiteral(n.arguments[0])||n.arguments[0].value===event))allScript.push(n);
    if(t.isMemberExpression(n)&&t.isThisExpression(n.object)&&n.computed)opaqueFire=true;
    if(own(n,'fire'))fireMembers.push(n);
    if(t.isVariableDeclarator(n)&&t.isThisExpression(n.init))opaqueFire=true;
   });
   if(fireMembers.some(n=>!allFireCalls.some(c=>c.callee===n)))opaqueFire=true;
   const allTemplate=[];const tv=n=>{if(n.type===1)for(const p of events(n,false)){const c=eventExpr(p,false);if(c)walk(c,x=>{if(emit(x,false)&&(!t.isStringLiteral(x.arguments[0])||x.arguments[0].value===event))allTemplate.push(p);});}children(n).forEach(tv);};children(b.ast).forEach(tv);
   if(!supported||opaqueFire||allScript.some(c=>!scriptCalls.has(c))||allTemplate.some(p=>!matched.some(m=>!m.scriptFire&&m.p===p))){review('unproven_emitter_route');continue;}
   // Every same-constructor alias/instance must be represented by this source route.
   const targetInstances=[];const ti=n=>{if(n.type===1&&target.aliases.includes(n.tag))targetInstances.push(n);children(n).forEach(ti);};children(outerB.ast).forEach(ti);
   if(targetInstances.length!==consumers.length||targetInstances.some(n=>!consumers.some(c=>c.n===n))){review('additional_consumer_or_alias');continue;}
   result.mapped_contracts.push(id);
   const correct=matched.every(m=>m.state==='packed')&&receivers.every(r=>r.state==='packed');
   if(!correct)result.findings.push({code:'source_event_payload_not_landed',location:'script.'+id,
    message:'Source multi-argument custom event requires a single object payload and explicit matching parent unpacking.'});
   if(correct)for(const r of receivers)result.proven_bindings.push({event,source_handler:r.handler,target_handler:r.q.value.trim()});
   const canRepair=receivers.every(r=>r.q&&r.state!=='unknown');
   if(!canRepair){review('unknown_parent_binding');continue;}
   const local=[];
   for(const m of matched)if(m.state==='legacy'){
    const object=t.objectExpression(fields.map((f,i)=>t.objectProperty(t.identifier(f),t.cloneNode(m.fire.arguments[i+1],true))));
    const replacement=t.callExpression(t.cloneNode(m.fire.callee,true),[t.cloneNode(m.fire.arguments[0],true),object]);
    if(m.scriptFire)local.push({start:offset+m.fire.start,end:offset+m.fire.end,text:print(replacement)});
    else{let value=print(replacement);if(value.includes(m.q.quote))value=value.replaceAll(m.q.quote,m.q.quote==='"'?'&quot;':'&#39;');
     local.push({start:offset+b.node.quasis[0].start+m.q.start,end:offset+b.node.quasis[0].start+m.q.end,text:value});}
   }
   for(const r of receivers)if(r.state==='legacy')local.push({start:outerOffset+r.q.start,end:outerOffset+r.q.end,text:r.desired});
   const unique=[...new Map(local.map(e=>[e.start+':'+e.end,e])).values()];
   edits.push(...unique);result.proofs.push({contract:id,fields,handler:receivers[0].handler,emissions:matched.length,consumers:receivers.length,
    proof:'source_inline_emit_arguments_and_parent_formals_match_both_target_routes',complete:correct});
  }
 }
 const unique=[...new Map(edits.map(e=>[e.start+':'+e.end,e])).values()].sort((a,b)=>b.start-a.start);
 for(let i=1;i<unique.length;i++)if(unique[i].end>unique[i-1].start)throw Error('Overlapping payload edits');
 if(input.repair){for(const e of unique)result.code=result.code.slice(0,e.start)+e.text+result.code.slice(e.end);
  if(unique.length){parser.parse(/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(result.code)[1],{sourceType:'unambiguous'});result.changes=['restored_source_single_payload_contract'];}}
 return result;
}
try{process.stdout.write(JSON.stringify(analyze(JSON.parse(fs.readFileSync(0,'utf8')))));}
catch(e){process.stdout.write(JSON.stringify({error:e.message}));}
