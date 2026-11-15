// Closed parent watcher group; no arbitrary hook moves, no source-named component special cases.
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types');
const traverse=require('@babel/traverse').default,{parse}=require('@vue/compiler-sfc');
const {parentOf,key}=require('./inline_identifier_recovery.cjs');
const {one,safe,declared,print,same,walk,sourceParent}=require('./source_render_call_semantics.cjs');
const MARK='__sourceParentWatchDispose_v1';
const globals=new Set(['Date','JSON','Object','localStorage','setInterval','clearInterval','setTimeout','clearTimeout','Promise','Number','undefined']);
const own=(n,name)=>t.isMemberExpression(n)&&!n.computed&&t.isThisExpression(n.object)&&(!name||t.isIdentifier(n.property,{name}));
const meth=(o,name)=>{const m=one(o,name);return t.isObjectMethod(m)&&m.kind==='method'&&!m.generator?m:null;};
const path=n=>own(n)?[n.property.name]:t.isMemberExpression(n)&&!n.computed&&path(n.object)?[...path(n.object),n.property.name]:null;
const member=p=>p.reduce((o,k)=>t.memberExpression(o,t.identifier(k)),t.thisExpression());
const ident=s=>typeof s==='string'&&/^[A-Za-z_$][\w$]*$/.test(s)&&!['__proto__','constructor','prototype','data','watch',MARK].includes(s);
function tree(m){return t.file(t.program([t.expressionStatement(t.objectExpression([JSON.parse(JSON.stringify(m))]))]));}
function immediateWalk(node,fn,root=node){if(!node||typeof node!=='object')return;if(Array.isArray(node)){node.forEach(n=>immediateWalk(n,fn,root));return;}
 if(t.isFunction(node)&&node!==root)return;fn(node);
 for(const [name,value] of Object.entries(node))if(!['loc','extra','comments'].includes(name))immediateWalk(value,fn,root);}
function normalize(m,fields,readonly=new Set()){
 const ast=tree(m);let root;traverse(ast,{ObjectMethod(p){root=p;p.stop();}});
 root.traverse({CallExpression(p){const n=p.node;
  if(!t.isMemberExpression(n.callee)||n.callee.computed||!own(n.callee.object,'data'))return;
  const args=n.arguments;if(!t.isStringLiteral(args[0]))return;const parts=args[0].value.split('.');
  if(!parts.every(ident)||!fields.has(parts[0]))return;
  const located=v=>Object.assign(v,{start:n.start,end:n.end});
  if(n.callee.property.name==='get'&&args.length===1)p.replaceWith(located(member(parts)));
  if(n.callee.property.name==='set'&&args.length===2)p.replaceWith(located(t.assignmentExpression('=',member(parts),args[1])));
 }});
 // Remove only immutable field reads. Their normalized source use is later compared in full.
 let changed=true;while(changed){changed=false;root.scope.crawl();
  root.traverse({VariableDeclaration(p){if(changed||p.node.kind!=='const'||p.node.declarations.length!==1)return;
   const d=p.node.declarations[0],parts=path(d.init);if(!t.isIdentifier(d.id)||!parts||!fields.has(parts[0]))return;
   const binding=p.scope.getBinding(d.id.name);if(!binding?.constant)return;
   let unsafe=false;
   for(const ref of binding.referencePaths)immediateWalk(root.node,n=>{
    if(!(n.start>=p.node.end&&n.end<=ref.node.start))return;
    if((t.isAssignmentExpression(n)||t.isUpdateExpression(n))&&rootField(t.isAssignmentExpression(n)?n.left:n.argument)===parts[0])unsafe=true;
    if(t.isCallExpression(n)&&own(n.callee)&&!readonly.has(n.callee.property.name))unsafe=true;
   });
   if(unsafe)return;
   binding.referencePaths.forEach(r=>r.replaceWith(t.cloneNode(d.init,true)));p.remove();changed=true;
  }});
 }
 // Exact adjacent temporary result -> assignment, e.g. one setInterval result.
 root.scope.crawl();root.traverse({VariableDeclaration(p){if(p.node.kind!=='const'||p.node.declarations.length!==1||!p.inList)return;
  const d=p.node.declarations[0],b=t.isIdentifier(d.id)&&p.scope.getBinding(d.id.name),next=p.getSibling(p.key+1);
  if(!b?.constant||b.referencePaths.length!==1||!next?.isExpressionStatement())return;
  const a=next.node.expression;if(!t.isAssignmentExpression(a,{operator:'='})||!path(a.left)||!t.isIdentifier(a.right,{name:d.id.name})
   ||b.referencePaths[0].node!==a.right)return;
  a.right=d.init;p.remove();
 }});
 return root.node;
}
function rootField(n){if(!t.isMemberExpression(n))return null;let current=n;
 while(t.isMemberExpression(current.object))current=current.object;
 return t.isThisExpression(current.object)&&!current.computed?current.property.name:null;}
function readonlyMethods(spec){const result=new Set();let changed=true;
 while(changed){changed=false;for(const m of spec.methods.properties){if(!t.isObjectMethod(m)||result.has(key(m)))continue;let pure=true;
  walk(m.body,n=>{if((t.isAssignmentExpression(n)||t.isUpdateExpression(n))&&rootField(t.isAssignmentExpression(n)?n.left:n.argument))pure=false;
   if(t.isCallExpression(n)&&own(n.callee)&&!result.has(n.callee.property.name))pure=false;
   if(t.isCallExpression(n)&&t.isMemberExpression(n.callee)&&t.isIdentifier(n.callee.object,{name:'localStorage'}))pure=false;
  });if(pure){result.add(key(m));changed=true;}
 }}return result;}
function sourceSpec(o){
 const watch=one(o,'watch')?.value,fields=declared(o,true),methods=one(o,'methods')?.value;
 const mounted=meth(o,'mounted'),destroyed=meth(o,'beforeDestroy'),data=meth(o,'data');
 if(!safe(watch)||watch.properties.length<1||watch.properties.length>8||!safe(methods)||!mounted||!destroyed
  ||[mounted,destroyed,data].some(m=>!m||m.async||m.params.length)||data.body.body.length!==1
  ||!t.isReturnStatement(data.body.body[0])||!safe(data.body.body[0].argument))return null;
 let dynamic=false;walk(data.body,n=>{if(t.isThisExpression(n)||t.isCallExpression(n)||t.isNewExpression(n))dynamic=true;});
 if(dynamic||[...fields].some(f=>!ident(f)))return null;
 if(['mixins','extends','beforeCreate','created','beforeMount','activated','deactivated','errorCaptured'].some(k=>one(o,k)))return null;
 const rows=[];
 for(const p of watch.properties){const field=key(p),value=p.value,handler=one(value,'handler');
  if(!ident(field)||!fields.has(field)||!safe(value)||value.properties.some(p=>!['handler','deep'].includes(key(p)))
   ||!t.isBooleanLiteral(one(value,'deep')?.value,{value:true})||!t.isObjectMethod(handler)||handler.async||handler.generator||handler.params.length)return null;
  const condition=n=>!!path(n)&&fields.has(path(n)[0])||t.isBooleanLiteral(n)||t.isNumericLiteral(n)||t.isStringLiteral(n)
   ||t.isUnaryExpression(n)&&n.operator==='!'&&condition(n.argument)
   ||(t.isLogicalExpression(n)||t.isBinaryExpression(n))&&condition(n.left)&&condition(n.right);
  const action=s=>t.isBlockStatement(s)?s.body.every(action):t.isExpressionStatement(s)&&t.isCallExpression(s.expression)
   &&own(s.expression.callee)&&s.expression.arguments.length===0||t.isIfStatement(s)&&condition(s.test)&&action(s.consequent)&&(!s.alternate||action(s.alternate));
  if(!handler.body.body.length||!handler.body.body.every(action))return null;
  rows.push({field,handler});
 }
 return {rows,fields,methods,mounted,destroyed,data};
}
function graph(spec,roots,target){
 const visited=new Set(),visiting=new Set(),readonly=readonlyMethods(spec);let reason=null;
 const inspect=m=>{
  const ast=tree(m);let root;traverse(ast,{ObjectMethod(p){root=p;p.stop();}});
  root.traverse({ReferencedIdentifier(p){if(!p.scope.getBinding(p.node.name)&&!globals.has(p.node.name))reason='external_dependency';},
   Function(p){if(p!==root&&!p.isArrowFunctionExpression())reason='unknown_function_receiver';},
   MemberExpression(p){if(t.isThisExpression(p.node.object)&&p.node.computed)reason='dynamic_instance_member';},
   ThisExpression(p){if(!p.parentPath.isMemberExpression()||p.key!=='object')reason='escaped_instance';}
  });
  const calls=[];walk(m.body,n=>{if(t.isCallExpression(n)&&own(n.callee))calls.push(n.callee.property.name);});return calls;
 };
 const visit=name=>{if(visiting.has(name)){reason='recursive_effect_graph';return;}if(visited.has(name))return;
  const source=meth(spec.methods,name),candidate=meth(target,name);
  if(!source||!candidate||!same(normalize(candidate,spec.fields,readonly),normalize(source,spec.fields,readonly))){reason='source_effect_method_mismatch:'+name;return;}
  visiting.add(name);for(const dep of inspect(source))visit(dep);visiting.delete(name);visited.add(name);
 };
 for(const root of roots)for(const name of inspect(root))visit(name);
 return {ok:!reason,reason,methods:[...visited].sort()};
}
function callbacks(spec,target){
 // A closure per instance, stable declared order, native Promise microtask, no captured stale values.
 const body=`({inited(){
 let alive=true,waiting=false,flushing=false,cursor=0;
 const queue=[],pending=[],handlers=[];
 const reset=()=>{queue.length=0;pending.length=0;waiting=false;flushing=false;cursor=0;};
 const flush=()=>{if(!alive){reset();return;}flushing=true;queue.sort((a,b)=>a-b);
 try{for(cursor=0;cursor<queue.length;cursor++){if(!alive)break;const index=queue[cursor];pending[index]=false;handlers[index]();}}
 finally{reset();}};
 const enqueue=index=>{if(!alive||pending[index])return;pending[index]=true;
 if(!flushing)queue.push(index);else{let at=queue.length-1;while(at>cursor&&queue[at]>index)at--;queue.splice(at+1,0,index);}
 if(!waiting){waiting=true;Promise.resolve().then(flush);}};
 this.${MARK}=()=>{alive=false;queue.length=0;pending.length=0;};
 }})`;
 const result=parser.parseExpression(body).properties[0];
 const handlers=result.body.body.find(s=>t.isVariableDeclaration(s)&&s.declarations.some(d=>t.isIdentifier(d.id,{name:'queue'})))
  .declarations.find(d=>t.isIdentifier(d.id,{name:'handlers'}));
 handlers.init=t.arrayExpression(spec.rows.map(({handler})=>{
  const h=t.cloneNode(handler,true),ast=tree(h);let p;traverse(ast,{ObjectMethod(v){p=v;v.stop();}});
  p.traverse({MemberExpression(v){const parts=path(v.node);if(parts&&spec.fields.has(parts[0])){
   v.replaceWith(t.callExpression(t.memberExpression(t.memberExpression(t.thisExpression(),t.identifier('data')),t.identifier('get')),[t.stringLiteral(parts.join('.'))]));v.skip();}
  }});return t.arrowFunctionExpression([],p.node.body);
 }));
 for(let i=0;i<spec.rows.length;i++)result.body.body.push(parser.parse(`this.watch(${JSON.stringify(spec.rows[i].field)},()=>enqueue(${i}));`).program.body[0]);
 return result;
}
function cloneWriters(spec,parent){const rows=[];
 for(const source of spec.methods.properties){if(!t.isObjectMethod(source)||source.async||source.params.length!==2||source.params.some(p=>!t.isIdentifier(p)))continue;
  const assignment=source.body.body[0]?.expression,lhs=assignment?.left;
  if(!t.isAssignmentExpression(assignment,{operator:'='})||!t.isMemberExpression(lhs)||!lhs.computed||!own(lhs.object)
   ||!t.isIdentifier(lhs.property,{name:source.params[0].name})||!spec.rows.some(r=>r.field===lhs.object.property.name))continue;
  const field=lhs.object.property.name,target=meth(parent,key(source)),slot=rows.length;
  rows.push({name:key(source),field,target,landed:false,unsupported:true});if(!target)continue;
  const [read,value,copy,write,...tail]=target.body.body;
  const decl=s=>t.isVariableDeclaration(s,{kind:'const'})&&s.declarations.length===1?s.declarations[0]:null;
  const a=decl(read),b=decl(value),c=decl(copy),call=write?.expression;
  if(!a||!b||!c||![a.id,b.id,c.id].every(t.isIdentifier)||new Set([a.id.name,b.id.name,c.id.name]).size!==3)continue;
  const expectedRead=parser.parseExpression(`this.data.get(${JSON.stringify(field)})`);
  const expectedCopy=parser.parseExpression(`({...${a.id.name},[${source.params[0].name}]:${b.id.name}})`);
  const expectedWrite=parser.parse(`this.data.set(${JSON.stringify(field)},${c.id.name});`).program.body[0];
  const guard=parser.parseExpression(`!Object.is(${a.id.name}[${source.params[0].name}],${b.id.name})`);
  const guarded=t.isIfStatement(write)&&!write.alternate&&same(write.test,guard)&&t.isBlockStatement(write.consequent)
   &&write.consequent.body.length===1&&same(write.consequent.body[0],expectedWrite);
  if(!same(a.init,expectedRead)||!same(b.init,assignment.right)||!same(c.init,expectedCopy)||(!guarded&&!same(write,expectedWrite))
   ||target.params.length!==source.params.length||!target.params.every((p,i)=>same(p,source.params[i]))||!same(normalize(t.objectMethod('method',t.identifier('tail'),[],t.blockStatement(tail)),spec.fields).body,
    t.blockStatement(source.body.body.slice(1))))continue;
  const fixed=t.cloneNode(target,true);fixed.body.body[3]=t.ifStatement(guard,t.blockStatement([expectedWrite]));
  rows[slot]={name:key(source),field,target,fixed,landed:guarded,unsupported:false};
 }return rows;}
function scopeBoundaries(spec,contract){
 const findings=[],seen=new Set(),storage=new Set(),dynamic=new Set();
 // Inspect source callbacks independently of target recognition. A malformed target
 // must not hide a pre-existing source boundary until a later normalization.
 const visit=(node,label)=>{if(!node||seen.has(node))return;seen.add(node);
  walk(node,n=>{
   if(t.isIdentifier(n,{name:'localStorage'}))storage.add(label);
   if(t.isCallExpression(n)&&own(n.callee))visit(meth(spec.methods,n.callee.property.name),n.callee.property.name);
  });
 };
 for(const {field,handler} of spec.rows)visit(handler,'watch.'+field);
 const initial=spec.data.body.body[0].argument;
 const objectRoots=new Set(spec.rows.filter(r=>t.isObjectExpression(one(initial,r.field)?.value)).map(r=>r.field));
 for(const method of spec.methods.properties)if(t.isObjectMethod(method))walk(method.body,n=>{
  const lhs=t.isAssignmentExpression(n)?n.left:t.isUpdateExpression(n)?n.argument:
   t.isUnaryExpression(n,{operator:'delete'})?n.argument:null;
  if(!lhs)return;
  walk(lhs,leaf=>{if(!t.isMemberExpression(leaf)||!objectRoots.has(rootField(leaf)))return;
   const parts=[];let part=leaf,unknown=t.isUnaryExpression(n,{operator:'delete'});
   while(t.isMemberExpression(part)){
    if(part.computed&&!t.isStringLiteral(part.property)&&!t.isNumericLiteral(part.property))unknown=true;
    parts.unshift(part.computed?part.property.value:part.property.name);part=part.object;
   }
   let value=one(initial,parts.shift())?.value;
   for(const property of parts){if(!t.isObjectExpression(value)||!one(value,String(property))){unknown=true;break;}
    value=one(value,String(property)).value;}
   if(unknown)dynamic.add(key(method)+':'+rootField(leaf));
  });
 });
 if(storage.size)findings.push({code:'source_parent_watch_exception_policy_unproven',location:contract+'/exception-policy',
  message:'Source watcher effects access localStorage ('+[...storage].sort().join(', ')+'); normal-flow matching does not prove storage-failure propagation or continuation policy. Automatic watcher rewriting requires review.'});
 if(dynamic.size)findings.push({code:'source_parent_watch_dynamic_key_unproven',location:contract+'/dynamic-keys',
  message:'Source watched-object writes have unproven key/shape or deletion semantics ('+[...dynamic].sort().join(', ')+'); cloning and same-value guards do not prove new, undefined, inherited or prototype-key semantics. Automatic watcher rewriting requires review.'});
 return findings;
}
function run(input){
 const result={code:input.code,findings:[],changes:[],proofs:[],reviews:[],mapped_contracts:[],blocked_boundaries:[]};
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(input.code),source=parse(input.vue);
 if(!block||source.errors.length||!source.descriptor.script||source.descriptor.scriptSetup)return result;
 const script=block[1],offset=block.index+block[0].indexOf('>')+1,ast=parser.parse(script,{sourceType:'unambiguous'}),srcAst=parser.parse(source.descriptor.script.content,{sourceType:'unambiguous'});
 const original=sourceParent(srcAst),parent=parentOf(ast),spec=sourceSpec(original);if(!spec||!safe(parent))return result;
 const contract='script.parent.watch@'+spec.rows.map(r=>r.field).join(',');result.mapped_contracts.push(contract);
 const boundaries=scopeBoundaries(spec,contract);
 result.findings.push(...boundaries);result.blocked_boundaries=boundaries.map(f=>({code:f.code,location:f.location}));
 const issue=()=>result.findings.push({code:'source_parent_watch_not_landed',location:contract,
  message:'Default-async source root deep watchers must register before startup, coalesce in declaration order, read latest state and cancel pending work on disposal.'});
 let binding,unsafe=false;traverse(ast,{Program(p){binding=p.scope.getBinding('san');},Scope(p){
  if([...globals].some(name=>p.scope.hasOwnBinding(name)))unsafe=true;
 }});
 traverse(srcAst,{Scope(p){if([...globals].some(name=>p.scope.hasOwnBinding(name)))unsafe=true;}});
 if(!binding?.constant||!binding.path.isVariableDeclarator()||!t.isCallExpression(binding.path.node.init)
  ||!t.isIdentifier(binding.path.node.init.callee,{name:'require'})||!t.isStringLiteral(binding.path.node.init.arguments[0],{value:'san'})
  ||binding.path.node.init.arguments.length!==1||binding.path.scope.getBinding('require'))unsafe=true;
 walk(ast,n=>{if(t.isAssignmentExpression(n)){let v=n.left;while(t.isMemberExpression(v))v=v.object;
  if(t.isIdentifier(v,{name:'san'}))unsafe=true;}});
 const init=meth(parent,'inited'),attach=meth(parent,'attached'),disposed=meth(parent,'disposed'),data=meth(parent,'initData');
 const expectedInit=callbacks(spec,parent);
 const cancel=parser.parse(`this.${MARK}();`).program.body[0];
 const already=!!init&&same(init,expectedInit);
 const disposeBody=disposed?.body.body||[],hasCancel=!!disposeBody.length&&same(disposeBody[0],cancel);
 const plainDispose=disposed&&t.cloneNode(disposed,true);if(hasCancel)plainDispose.body.body.shift();
 const registrations=[],otherWatch=[];let hookBody=attach?.body.body||[];
 for(const hook of [init,attach].filter(Boolean))for(const statement of hook.body.body){const call=statement.expression;
  if(t.isCallExpression(call)&&own(call.callee,'watch'))registrations.push({statement,call,hook});
 }
 const stripped=attach&&t.cloneNode(attach,true);if(stripped)stripped.body.body=stripped.body.body.filter((s,i)=>!registrations.some(r=>r.hook===attach&&attach.body.body[i]===r.statement));
 const renamed=(m,name)=>{if(!m)return m;const n=t.cloneNode(m,true);n.key=t.identifier(name);return n;};
 let phaseMatches=!!stripped&&!!plainDispose&&!!data&&same(renamed(normalize(stripped,spec.fields),'mounted'),spec.mounted)
  &&same(renamed(normalize(plainDispose,spec.fields),'beforeDestroy'),spec.destroyed)
  &&same(renamed(data,'data'),spec.data);
 const roots=[...spec.rows.map(r=>r.handler),spec.mounted,spec.destroyed],effects=graph(spec,roots,parent);
 const writers=cloneWriters(spec,parent);
 // This first bounded group excludes watcher-driven writes to watched roots;
 // queue re-insertion is defensive, not a proof for arbitrary reactive cycles.
 const watchEffects=graph(spec,spec.rows.map(r=>r.handler),parent),watched=new Set(spec.rows.map(r=>r.field));
 for(const node of [...spec.rows.map(r=>r.handler),...watchEffects.methods.map(name=>meth(spec.methods,name))])if(node)walk(normalize(node,spec.fields,readonlyMethods(spec)),n=>{
  if((t.isAssignmentExpression(n)||t.isUpdateExpression(n))&&watched.has(rootField(t.isAssignmentExpression(n)?n.left:n.argument)))unsafe=true;
  if(t.isCallExpression(n)&&t.isMemberExpression(n.callee)&&watched.has(rootField(n.callee))&&['push','pop','shift','unshift','splice','sort','reverse'].includes(n.callee.property.name))unsafe=true;
 });
 let targetCallbacks=registrations.length===spec.rows.length;
 for(let i=0;i<spec.rows.length;i++){const matching=registrations.filter(r=>t.isStringLiteral(r.call.arguments[0],{value:spec.rows[i].field}));
  if(matching.length!==1){targetCallbacks=false;continue;}const args=matching[0].call.arguments,fn=args[1];
  if(![2,3].includes(args.length)||!t.isArrowFunctionExpression(fn)||fn.async||fn.params.length||!t.isBlockStatement(fn.body))targetCallbacks=false;
  else{const fake=t.objectMethod('method',t.identifier('handler'),[],fn.body);
   if(!same(normalize(fake,spec.fields).body,spec.rows[i].handler.body))targetCallbacks=false;
  }
  if(args.length===3&&(!safe(args[2])||args[2].properties.some(p=>!['deep','immediate'].includes(key(p))
   ||!t.isBooleanLiteral(p.value,{value:key(p)==='deep'}))))targetCallbacks=false;
 }
 let outside=false;
 for(const prop of parent.properties){if([init,attach,disposed].includes(prop))continue;
  if(['watch','created','compiled','beforeCreate','beforeMount','mixins','extends',MARK].includes(key(prop)))outside=true;
  walk(prop,n=>{if(own(n,'watch')||own(n,MARK)||(t.isMemberExpression(n)&&n.computed&&t.isThisExpression(n.object)))outside=true;});
 }
 if(!already){if(init?.body.body.some(s=>!registrations.some(r=>r.hook===init&&r.statement===s)))outside=true;
  if(script.includes(MARK))outside=true;
 }
 const recoverable=!unsafe&&!outside&&phaseMatches&&effects.ok&&writers.every(w=>!w.unsupported)&&(already||targetCallbacks);
 const landed=recoverable&&already&&hasCancel&&registrations.filter(r=>r.hook===attach).length===0&&writers.every(w=>w.landed);
 if(!landed)issue();
 if(!recoverable){result.reviews.push({contract,reason:effects.reason||'unknown_phase_registration_scope_or_source_body'});return result;}
 result.proofs.push({contract,landed,fields:spec.rows.map(r=>r.field),effect_methods:effects.methods,
  proof_scope:'normal_flow_only',automatic_repair_eligible:boundaries.length===0,
  proof:'full_source_data_lifecycle_callback_and_transitive_method_match_default_async_root_group',
  source_nested_clone_writers:writers.map(w=>({method:w.name,field:w.field,same_value_guard:w.landed})),
  exception_boundary:'Normal completed callback effects; framework-specific thrown/error-handler behavior is not claimed equivalent.'});
 if(boundaries.length)result.reviews.push({contract,reason:'source_parent_watch_scope_requires_review',
  blocked_codes:boundaries.map(f=>f.code)});
 if(!input.repair||landed||boundaries.length)return result;
 const newDisposed=t.cloneNode(disposed,true);if(!hasCancel)newDisposed.body.body.unshift(cancel);
 const edits=[{start:init?init.start:parent.start+1,end:init?init.end:parent.start+1,text:print(expectedInit)+(init?'':',')},
  {start:attach.start,end:attach.end,text:print(stripped)},{start:disposed.start,end:disposed.end,text:print(newDisposed)}];
 for(const writer of writers)if(!writer.landed)edits.push({start:writer.target.start,end:writer.target.end,text:print(writer.fixed)});
 edits.sort((a,b)=>b.start-a.start);let next=script;for(const edit of edits)next=next.slice(0,edit.start)+edit.text+next.slice(edit.end);
 parser.parse(next,{sourceType:'unambiguous'});result.code=input.code.slice(0,offset)+next+input.code.slice(offset+script.length);
 result.changes.push('restored_source_parent_async_watch_group');return result;
}
if(require.main===module){try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}catch(e){process.stdout.write(JSON.stringify({error:e.message}));}}
module.exports={run,normalize};
