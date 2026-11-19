// Complete bounded source dragstart contract; unknown handler bodies are never copied.
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types');
const traverse=require('@babel/traverse').default,{parse}=require('@vue/compiler-sfc');
const dom=require('@vue/compiler-dom'),{isHTMLTag}=require('@vue/shared');
const {parentOf,key}=require('./inline_identifier_recovery.cjs');
const {one,safe,declared,print,same,walk,sourceParent,registered}=require('./source_render_call_semantics.cjs');
const id=s=>typeof s==='string'&&/^[A-Za-z_$][\w$]*$/.test(s)&&!['__proto__','prototype','constructor'].includes(s);
const own=(n,name)=>t.isMemberExpression(n)&&!n.computed&&t.isThisExpression(n.object)&&(!name||t.isIdentifier(n.property,{name}));
const field=n=>own(n)&&id(n.property.name)?n.property.name:null;
const method=(o,name)=>{const m=one(o,name);return t.isObjectMethod(m)&&m.kind==='method'&&!m.async&&!m.generator
 &&m.params.length<=1&&m.params.every(p=>t.isIdentifier(p)&&id(p.name))?m:null;};
const get=n=>t.isCallExpression(n)&&!n.optional&&t.isMemberExpression(n.callee)&&!n.callee.computed
 &&own(n.callee.object,'data')&&t.isIdentifier(n.callee.property,{name:'get'})&&n.arguments.length===1
 &&t.isStringLiteral(n.arguments[0])&&id(n.arguments[0].value)?n.arguments[0].value:null;
function inline(o){const value=one(o,'template')?.value;
 if(!t.isTemplateLiteral(value)||value.expressions.length||value.quasis[0].value.raw.includes('\\'))return null;
 const errors=[],ast=dom.parse(value.quasis[0].value.raw,{onError:e=>errors.push(e)});return errors.length?null:ast;}
function bindings(o,name,source){const ast=inline(o);if(!ast)return null;const found=[];
 const visit=n=>{if(n.type===1&&isHTMLTag(n.tag))for(const p of n.props){
  if(source&&p.type===7&&p.name==='on'&&p.arg?.isStatic&&p.arg.content==='dragstart'
    &&p.exp?.content.trim()===name&&!p.modifiers.length)found.push(n.tag);
  if(!source&&p.type===6&&p.name==='on-dragstart'&&p.value){
   const value=p.value.content.trim();if(value===name||value===name+'($event)')found.push(n.tag);
  }
 }for(const c of n.children||[])visit(c);};visit(ast);return found;
}
function specOf(m,fields){
 if(!m||m.params.length!==1)return null;const event=m.params[0].name,body=m.body.body;
 if(body.length!==4)return null;const [guard,transfer,effect,emit]=body;
 if(!t.isIfStatement(guard)||guard.alternate||!t.isUnaryExpression(guard.test,{operator:'!'})
  ||!fields.has(field(guard.test.argument)))return null;
 const returned=t.isBlockStatement(guard.consequent)&&guard.consequent.body.length===1?guard.consequent.body[0]:guard.consequent;
 if(!t.isReturnStatement(returned)||returned.argument)return null;
 const dt=n=>t.isMemberExpression(n)&&!n.computed&&t.isIdentifier(n.object,{name:event})&&t.isIdentifier(n.property,{name:'dataTransfer'});
 const call=transfer.expression,assignment=effect.expression,fire=emit.expression;
 if(!t.isExpressionStatement(transfer)||!t.isCallExpression(call)||call.optional||!t.isMemberExpression(call.callee)||call.callee.computed
  ||!dt(call.callee.object)||!t.isIdentifier(call.callee.property,{name:'setData'})||call.arguments.length!==2
  ||!t.isStringLiteral(call.arguments[0])||!fields.has(field(call.arguments[1])))return null;
 if(!t.isExpressionStatement(effect)||!t.isAssignmentExpression(assignment,{operator:'='})||!t.isMemberExpression(assignment.left)
  ||assignment.left.computed||!dt(assignment.left.object)||!t.isIdentifier(assignment.left.property,{name:'effectAllowed'})
  ||!t.isStringLiteral(assignment.right))return null;
 if(!t.isExpressionStatement(emit)||!t.isCallExpression(fire)||fire.optional||!own(fire.callee,'$emit')||fire.arguments.length!==2
  ||!t.isStringLiteral(fire.arguments[0])||!fields.has(field(fire.arguments[1])))return null;
 return {event,fields:new Set([field(guard.test.argument),field(call.arguments[1]),field(fire.arguments[1])])};
}
function normalize(m,spec){
 const ast=t.file(t.program([t.expressionStatement(t.objectExpression([t.cloneNode(m,true)]))]));let path;
 traverse(ast,{ObjectMethod(p){path=p;p.stop();}});
 if(path.node.params.length){const name=path.node.params[0].name;
  if(name!==spec.event&&path.scope.hasOwnBinding(spec.event))return null;
  if(name!==spec.event)path.scope.rename(name,spec.event);
 }
 path.traverse({CallExpression(p){const f=get(p.node);
  if(f&&spec.fields.has(f))p.replaceWith(t.memberExpression(t.thisExpression(),t.identifier(f)));
  else if(own(p.node.callee,'fire'))p.node.callee=t.memberExpression(t.thisExpression(),t.identifier('$emit'));
 }});
 for(const statement of path.get('body.body')){const n=statement.node;
  if(!t.isVariableDeclaration(n,{kind:'const'})||n.declarations.length!==1)continue;
  const d=n.declarations[0];if(!t.isIdentifier(d.id)||!spec.fields.has(field(d.init)))continue;
  const b=path.scope.getBinding(d.id.name);if(!b?.constant)return null;
  b.referencePaths.forEach(p=>p.replaceWith(t.cloneNode(d.init,true)));statement.remove();
 }
 return path.node;
}
function outsideUse(o,name,source){let unsafe=false;
 for(const p of o.properties){if(p===one(o,source?'methods':name)||key(p)==='template')continue;
  if(key(p)===(source?'$emit':'fire'))unsafe=true;
  walk(p,n=>{if(own(n,name)||(t.isMemberExpression(n)&&n.computed&&t.isThisExpression(n.object))
   ||(t.isAssignmentExpression(n)&&own(n.left,source?'$emit':'fire')))unsafe=true;});
 }
 if(source){const methods=one(o,'methods')?.value;
  for(const p of methods?.properties||[])if(key(p)!==name)walk(p,n=>{
   if(key(p)==='$emit'||own(n,name)||(t.isMemberExpression(n)&&n.computed&&t.isThisExpression(n.object))
    ||(t.isAssignmentExpression(n)&&own(n.left,'$emit')))unsafe=true;
  });
 }
 const template=one(o,'template')?.value;
 if(t.isTemplateLiteral(template)){
  const text=template.quasis.map(q=>q.value.raw).join('');
  // Exactly one textual use, the previously proven native binding; no second event or interpolation caller.
  const re=new RegExp('(?<![\\w$])'+name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'(?![\\w$])','g');
  if((text.match(re)||[]).length!==1)unsafe=true;
 }
 return unsafe;
}
function run(input){
 const result={code:input.code,findings:[],changes:[],proofs:[],reviews:[],mapped_contracts:[]};
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(input.code),src=parse(input.vue);
 if(!block||src.errors.length||!src.descriptor.script||src.descriptor.scriptSetup)return result;
 const script=block[1],offset=block.index+block[0].indexOf('>')+1;
 const ast=parser.parse(script,{sourceType:'unambiguous'}),srcAst=parser.parse(src.descriptor.script.content,{sourceType:'unambiguous'});
 const parent=parentOf(ast),original=sourceParent(srcAst),registry=one(original,'components')?.value;
 if(!safe(parent)||!safe(original)||!safe(registry)||['mixins','extends'].some(k=>one(parent,k)||one(original,k)))return result;
 let binding;traverse(ast,{Program(p){binding=p.scope.getBinding('san');}});
 if(!binding?.constant||!binding.path.isVariableDeclarator()||!t.isCallExpression(binding.path.node.init)
  ||!t.isIdentifier(binding.path.node.init.callee,{name:'require'})||binding.path.node.init.arguments.length!==1
  ||!t.isStringLiteral(binding.path.node.init.arguments[0],{value:'san'})||binding.path.scope.getBinding('require'))return result;
 let mutated=false;walk(ast,n=>{if(!t.isAssignmentExpression(n)&&!t.isUpdateExpression(n))return;
  let root=t.isUpdateExpression(n)?n.argument:n.left;while(t.isMemberExpression(root))root=root.object;
  if(t.isIdentifier(root,{name:'san'}))mutated=true;});if(mutated)return result;
 const edits=[],seen=new Set();
 for(const reg of registry.properties){const tag=key(reg).replace(/([a-z0-9])([A-Z])/g,'$1-$2').toLowerCase();
  if(seen.has(tag))continue;seen.add(tag);const a=registered(srcAst,original,tag,false);if(!a)continue;
  const methods=one(a.object,'methods')?.value;if(!safe(methods))continue;
  for(const p of methods.properties){const name=key(p);if(!id(name)||['initData','inited','attached','disposed','watch','fire','data','computed'].includes(name))continue;
   const source=method(methods,name),spec=specOf(source,declared(a.object,true)),sourceBindings=bindings(a.object,name,true);
   if(!spec||!sourceBindings||sourceBindings.length!==1||outsideUse(a.object,name,true))continue;
   const contract='script.'+tag+'.'+name+'@native-dragstart';result.mapped_contracts.push(contract);
   const b=registered(ast,parent,tag,true),target=b&&method(b.object,name);
   const targetBindings=b&&bindings(b.object,name,false),fields=b&&declared(b.object,false);
   const normalized=target&&normalize(target,spec);
   const body=normalized?.body.body;
   const core=source.body.body,variants=[[core[0],core[3]],[core[0],core[1],core[3]],
    [core[0],core[2],core[3]],core];
   const matched=!!body&&variants.some(v=>same(t.blockStatement(body),t.blockStatement(v)));
   const bound=!!targetBindings&&targetBindings.length===1&&targetBindings[0]===sourceBindings[0];
   const recoverable=matched&&bound&&(target.params.length===1||body.length===2)
    &&[...spec.fields].every(f=>fields.has(f))&&!outsideUse(b.object,name,false);
   const landed=recoverable&&target.params.length===1&&same(t.blockStatement(body),source.body);
   if(!landed)result.findings.push({code:'source_native_drag_not_landed',location:contract,
    message:'Source native drag handler guard, dataTransfer side effects, event argument and emit order are not proven.'});
   if(!recoverable){result.reviews.push({contract,reason:'unknown_native_binding_handler_effects_or_external_use'});continue;}
   result.proofs.push({contract,registered_tag:tag,component:b.name,method:name,landed,
    proof:'complete_source_guard_transfer_effect_and_single_payload_emit_in_order'});
   if(landed)continue;
   const restored=t.cloneNode(source,true);
   const tree=t.file(t.program([t.expressionStatement(t.objectExpression([restored]))]));
   traverse(tree,{CallExpression(p){if(own(p.node.callee,'$emit'))p.node.callee=t.memberExpression(t.thisExpression(),t.identifier('fire'));},
    MemberExpression(p){const f=field(p.node);if(spec.fields.has(f))p.replaceWith(t.callExpression(
     t.memberExpression(t.memberExpression(t.thisExpression(),t.identifier('data')),t.identifier('get')),[t.stringLiteral(f)]));}});
   edits.push({start:target.start,end:target.end,text:print(restored)});
  }
 }
 edits.sort((a,b)=>b.start-a.start);for(let i=1;i<edits.length;i++)if(edits[i].end>edits[i-1].start)throw Error('Overlapping native drag edits');
 if(input.repair&&edits.length){let next=script;for(const e of edits)next=next.slice(0,e.start)+e.text+next.slice(e.end);
  parser.parse(next,{sourceType:'unambiguous'});result.code=input.code.slice(0,offset)+next+input.code.slice(offset+script.length);
  result.changes.push('restored_source_native_drag_transfer_contract');
 }return result;
}
if(require.main===module){try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(e){process.stdout.write(JSON.stringify({error:e.message}));}}
module.exports={run};
