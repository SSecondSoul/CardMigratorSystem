// Closed parent render DAGs only. Public methods and script callers are untouched.
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types');
const traverse=require('@babel/traverse').default,dom=require('@vue/compiler-dom');
const {parse:parseSFC}=require('@vue/compiler-sfc');
const {parentOf,key}=require('./inline_identifier_recovery.cjs');
const {one,safe,method,declared,arrayPath,print,same,walk,sourceParent,entries}=require('./source_render_call_semantics.cjs');
const {expandBridges}=require('./source_readonly_bridge_semantics.cjs');
const id=s=>typeof s==='string'&&/^[A-Za-z_$][\w$]*$/.test(s)&&!['__proto__','constructor','prototype'].includes(s);
const own=(n,name)=>t.isMemberExpression(n)&&!n.computed&&t.isThisExpression(n.object)&&(!name||t.isIdentifier(n.property,{name}));
const dataGet=n=>t.isCallExpression(n)&&!n.optional&&t.isMemberExpression(n.callee)&&!n.callee.computed
 &&t.isIdentifier(n.callee.property,{name:'get'})&&own(n.callee.object,'data')&&n.arguments.length===1&&t.isStringLiteral(n.arguments[0]);
function tree(m){return t.file(t.program([t.expressionStatement(t.objectExpression([t.cloneNode(m,true)]))]));}
function normalize(m,source,fields,ids,program){
 const ast=tree(m),reads=new Set();let path;
 traverse(ast,{ObjectMethod(p){path=p;p.stop();}});
 path.traverse({CallExpression(p){if(!source&&dataGet(p.node)){
  const f=p.node.arguments[0].value;if(!fields.has(f)||!id(f))return;
  reads.add(f);p.replaceWith(t.identifier(ids.get(f)));
 }},MemberExpression(p){if(source&&own(p.node)&&fields.has(p.node.property.name)){
  const f=p.node.property.name;reads.add(f);p.replaceWith(t.identifier(ids.get(f)));
 }}});
 // Only root immutable aliases of a proven data read; no arbitrary inlining.
 let changed=true;
 while(changed){changed=false;path.scope.crawl();
  for(const statement of path.get('body.body')){
   const s=statement.node;if(!t.isVariableDeclaration(s,{kind:'const'})||s.declarations.length!==1)continue;
   const d=s.declarations[0];if(!t.isIdentifier(d.id)||!t.isIdentifier(d.init)||![...ids.values()].includes(d.init.name))continue;
   const binding=path.scope.getBinding(d.id.name);if(!binding?.constant)continue;
   for(const reference of binding.referencePaths)reference.replaceWith(t.identifier(d.init.name));
   statement.remove();changed=true;break;
  }
 }
 const expanded=source?{node:path.node,corrections:[]}:expandBridges(path.node,program);
 return {node:expanded.node,reads:[...reads].sort(),corrections:expanded.corrections};
}
function arrayField(root,field){
 if(arrayPath(root,[field]))return true;
 const m=method(one(root,'computed')?.value,field),last=m?.body.body.at(-1);
 // A declared computed array is an explicit dependency boundary; its implementation
 // is not rewritten or certified as equivalent by this render-only rule.
 const n=t.isReturnStatement(last)&&last.argument;
 return !!m&&!m.params.length&&t.isCallExpression(n)&&t.isMemberExpression(n.callee)&&!n.callee.computed
  &&t.isIdentifier(n.callee.object,{name:'Array'})&&t.isIdentifier(n.callee.property,{name:'from'})
  &&n.arguments.length===1&&t.isNewExpression(n.arguments[0])&&t.isIdentifier(n.arguments[0].callee,{name:'Set'});
}
function readonly(n,fields,ids,sourceRoot){
 const test=t.cloneNode(n,true);test.params.push(...fields.map(f=>t.identifier(ids.get(f))));
 const ast=tree(test);let good=true;
 const math=new Set(['abs','min','max','floor','ceil','round','pow','sqrt']);
 traverse(ast,{
  Function(p){if(p.isObjectMethod()&&p.node===ast.program.body[0].expression.properties[0])return;
   if(!p.isArrowFunctionExpression()||p.node.async||p.node.generator)good=false;},
  ReferencedIdentifier(p){if(!p.scope.getBinding(p.node.name)&&!['Date','Math','undefined','Infinity','NaN'].includes(p.node.name))good=false;},
  ThisExpression(p){if(!own(p.parentPath.node)||!p.parentPath.parentPath.isCallExpression()
    ||p.parentPath.parentPath.node.callee!==p.parentPath.node)good=false;},
  AssignmentExpression(){good=false;},UpdateExpression(){good=false;},ThrowStatement(){good=false;},
  AwaitExpression(){good=false;},YieldExpression(){good=false;},Super(){good=false;},
  UnaryExpression(p){if(p.node.operator==='delete')good=false;},
  NewExpression(p){if(!t.isIdentifier(p.node.callee,{name:'Date'})||p.scope.getBinding('Date')||p.node.arguments.some(a=>t.isSpreadElement(a)))good=false;},
  CallExpression(p){const c=p.node.callee;if(p.node.optional||p.node.arguments.some(a=>t.isSpreadElement(a))){good=false;return;}
   if(own(c))return;
   if(!t.isMemberExpression(c)||c.computed){good=false;return;}
   if(t.isIdentifier(c.object,{name:'Math'})&&!p.scope.getBinding('Math')&&math.has(c.property.name))return;
   const field=t.isIdentifier(c.object)&&[...ids].find(([_,v])=>v===c.object.name)?.[0];
   if(field&&arrayField(sourceRoot,field)&&t.isIdentifier(c.property,{name:'indexOf'})
    &&p.node.arguments.length===1)return;
   if(field&&arrayField(sourceRoot,field)&&t.isIdentifier(c.property,{name:'filter'})
    &&p.node.arguments.length===1&&t.isArrowFunctionExpression(p.node.arguments[0]))return;
   const binding=t.isIdentifier(c.object)&&p.scope.getBinding(c.object.name);
   if(binding?.constant&&binding.path.isVariableDeclarator()&&t.isNewExpression(binding.path.node.init)
    &&t.isIdentifier(binding.path.node.init.callee,{name:'Date'})&&!p.scope.getBinding('Date')
    &&['setHours','getTime','getHours','getMinutes','getSeconds','getFullYear','getMonth','getDate'].includes(c.property.name))return;
   good=false;
  }
 });return good;
}
function graph(rootName,options,source,fields,ids,sourceRoot,program){
 const methods=source?one(options,'methods')?.value:options,memo=new Map(),active=new Set();
 const visit=name=>{
  if(active.has(name))throw Error('recursive_method_graph');if(memo.has(name))return memo.get(name);
  const m=method(methods,name);if(!m)throw Error('unknown_or_unsupported_method');active.add(name);
  const norm=normalize(m,source,fields,ids,program),calls=[];
  walk(norm.node.body,n=>{if(t.isCallExpression(n)&&own(n.callee))calls.push(n);});
  const deps=new Set(norm.reads),children=[];
  for(const call of calls){const name=call.callee.property.name,child=visit(name);
   if(call.arguments.length!==child.node.params.length||call.arguments.some(a=>t.isSpreadElement(a)))throw Error('ambiguous_method_arity');
   child.fields.forEach(f=>deps.add(f));children.push(name);
  }
  if(!readonly(norm.node,norm.reads,ids,sourceRoot))throw Error('unproven_readonly_method');
  const result={node:norm.node,fields:[...deps].sort(),direct:norm.reads,children,corrections:norm.corrections};memo.set(name,result);active.delete(name);return result;
 };
 visit(rootName);return memo;
}
function equivalent(a,b){return a.size===b.size&&[...a].every(([name,entry])=>{
 const other=b.get(name);return other&&same(entry.node,other.node)&&JSON.stringify(entry.fields)===JSON.stringify(other.fields);
});}
function privateGraphIsExact(root,privateName,expected,target,ids,program){
 const seen=new Map(),used=new Set();
 const verify=(name,candidate)=>{
  if(seen.has(name))return seen.get(name)===candidate;
  if(used.has(candidate))return false;used.add(candidate);seen.set(name,candidate);
  const spec=expected.get(name),m=method(target,candidate);if(!spec||!m||m.params.length!==spec.node.params.length+spec.fields.length)return false;
  const bridge=expandBridges(m,program);
  // A legacy loop may authorize correction but cannot certify an existing
  // explicit render graph as already native-equivalent (sparse arrays differ).
  if(bridge.corrections.length)return false;
  const ast=tree(bridge.node);let path;traverse(ast,{ObjectMethod(p){path=p;p.stop();}});
  const n=path.node;if(!same(t.arrayExpression(n.params.slice(0,spec.node.params.length)),t.arrayExpression(spec.node.params)))return false;
  for(let i=0;i<spec.fields.length;i++){
   const p=n.params[spec.node.params.length+i],canonical=ids.get(spec.fields[i]);
   if(n.params.some((other,j)=>j!==spec.node.params.length+i&&t.isIdentifier(other,{name:canonical})))return false;
   path.scope.rename(p.name,canonical);
  }
  n.params=n.params.slice(0,spec.node.params.length);n.key=t.identifier(name);
  const calls=[],sourceCalls=[];
  walk(n.body,x=>{if(t.isCallExpression(x)&&own(x.callee))calls.push(x);});
  walk(spec.node.body,x=>{if(t.isCallExpression(x)&&own(x.callee))sourceCalls.push(x);});
  if(calls.length!==sourceCalls.length)return false;
  for(let i=0;i<calls.length;i++){
   const actual=calls[i],original=sourceCalls[i],childName=original.callee.property.name,child=expected.get(childName);
   if(!child||actual.arguments.length!==original.arguments.length+child.fields.length)return false;
   if(!child.fields.every((f,j)=>t.isIdentifier(actual.arguments[original.arguments.length+j],{name:ids.get(f)})))return false;
   const candidateName=actual.callee.property.name;
   actual.callee.property=t.identifier(childName);actual.arguments=actual.arguments.slice(0,original.arguments.length);
   if(!verify(childName,candidateName))return false;
  }
  return same(n,spec.node);
 };
 return verify(root,privateName);
}
function run(input){
 const result={code:input.code,findings:[],changes:[],proofs:[],reviews:[],mapped_bindings:[],scope_conditions:[]};
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(input.code),outer=/<template\b[^>]*>([\s\S]*?)<\/template\s*>/i.exec(input.code);
 const source=parseSFC(input.vue);if(!block||!outer||source.errors.length||!source.descriptor.script||!source.descriptor.template||source.descriptor.scriptSetup)return result;
 const script=block[1],scriptOffset=block.index+block[0].indexOf('>')+1,templateOffset=outer.index+outer[0].indexOf('>')+1;
 const ast=parser.parse(script,{sourceType:'unambiguous'}),srcAst=parser.parse(source.descriptor.script.content,{sourceType:'unambiguous'});
 const parent=parentOf(ast),original=sourceParent(srcAst);
 if(!safe(parent)||!original||one(original,'mixins')||one(original,'extends')||one(parent,'mixins')||one(parent,'extends'))return result;
 let binding,shadow=false;const globals=['Date','Math','Array','Set'];
 traverse(ast,{Program(p){binding=p.scope.getBinding('san');},Scope(p){if(globals.some(n=>p.scope.hasOwnBinding(n)))shadow=true;}});
 traverse(srcAst,{Scope(p){if(globals.some(n=>p.scope.hasOwnBinding(n)))shadow=true;}});
 if(shadow||!binding?.constant||!binding.path.isVariableDeclarator()||!t.isCallExpression(binding.path.node.init)
  ||!t.isIdentifier(binding.path.node.init.callee,{name:'require'})||binding.path.node.init.arguments.length!==1
  ||!t.isStringLiteral(binding.path.node.init.arguments[0],{value:'san'}))return result;
 for(const tree of [ast,srcAst])walk(tree,n=>{if(t.isAssignmentExpression(n)&&t.isMemberExpression(n.left)&&/^(Math\.|Date\.|Array\.prototype\.)/.test(print(n.left)))shadow=true;});
 if(shadow)return result;
 const fields=declared(original,true),targetFields=declared(parent,false),sourceMethods=one(original,'methods')?.value;
 for(const [options,names] of [[original,fields],[parent,targetFields]]){
  const computed=one(options,'computed')?.value;
  if(computed&&!safe(computed))return result;
  for(const p of computed?.properties||[]){const name=key(p);if(names.has(name)||!method(computed,name)||p.params.length)return result;names.add(name);}
 }
 if(!safe(sourceMethods)||[...fields].some(f=>!id(f)||/^[_$]/.test(f)||one(sourceMethods,f)))return result;
 const used=new Set([script,source.descriptor.script.content,outer[1],source.descriptor.template.content]
  .flatMap(text=>[...text.matchAll(/[A-Za-z_$][\w$]*/g)].map(m=>m[0])));
 const fresh=prefix=>{let name=prefix;while(used.has(name))name+='_';used.add(name);return name;};
 const ids=new Map([...fields].sort().map(f=>[f,fresh('__sourceField_'+f)]));
 const parse=text=>{const errors=[];const ast=dom.parse(text,{onError:e=>errors.push(e)});return errors.length?null:{ast,text};};
 const a=parse(source.descriptor.template.content),b=parse(outer[1]);if(!a||!b)return result;
 const srcEntries=entries(a,true,true),dstEntries=entries(b,false,true),graphCache=new Map(),copies=new Map(),edits=[],additions=[];
 const get=name=>{
  if(graphCache.has(name))return graphCache.get(name);
  let sourceGraph;try{sourceGraph=graph(name,original,true,fields,ids,original,srcAst);}catch(e){
   result.reviews.push({root:name,reason:'source_graph_unproven:'+e.message});graphCache.set(name,null);return null;
  }
  const info={source:sourceGraph,target:null,error:null};
  try{info.target=graph(name,parent,false,fields,ids,original,ast);if(!equivalent(sourceGraph,info.target))info.error='source_target_method_body_mismatch';}
  catch(e){info.error=e.message;}
  graphCache.set(name,info);return info;
 };
 const restore=node=>{
  const clone=t.cloneNode(node,true);walk(clone,n=>{if(!t.isCallExpression(n)||!t.isIdentifier(n.callee))return;
   for(const p of sourceMethods.properties){const name=key(p),info=get(name),spec=info?.source.get(name);if(!spec?.fields.length)continue;
    if(n.arguments.length!==spec.node.params.length+spec.fields.length
     ||!spec.fields.every((f,i)=>t.isIdentifier(n.arguments[spec.node.params.length+i],{name:f}))
     ||!privateGraphIsExact(name,n.callee.name,info.source,parent,ids,ast))continue;
    n.callee=t.identifier(name);n.arguments=n.arguments.slice(0,spec.node.params.length);break;
   }
  });return clone;
 };
 const scopeSame=(left,right)=>{
  const x=JSON.parse(left),y=JSON.parse(right);if(x.length!==y.length)return false;
  return x.every((part,i)=>{const a=JSON.parse(part),b=JSON.parse(y[i]);return a.length===b.length&&a.every(([k,v],j)=>{
   if(k!==b[j][0])return false;if(v===b[j][1])return true;
   if(!['if','else-if'].includes(k))return false;
   try{return same(parser.parseExpression(v),restore(parser.parseExpression(b[j][1])));}catch(_){return false;}
  });});
 };
 for(const s of srcEntries){if(!s.valid)continue;
  const calls=[];walk(s.node,n=>{if(t.isCallExpression(n)&&!n.optional&&t.isIdentifier(n.callee)&&method(sourceMethods,n.callee.name))calls.push(n);});
  if(calls.length!==1)continue;
  const call=calls[0],name=call.callee.name,info=get(name),spec=info?.source.get(name);
  if(!spec?.fields.length||call.arguments.length!==spec.node.params.length||call.arguments.some(a=>t.isSpreadElement(a)))continue;
  const location='template'+s.path+'#'+s.role+'@'+name;
  const dst=dstEntries.filter(d=>d.valid&&d.path===s.path&&d.role===s.role&&scopeSame(s.scope,d.scope));
  if(dst.length!==1){result.reviews.push({binding:location,reason:'unmatched_source_render_scope'});continue;}
  result.mapped_bindings.push(location);const d=dst[0];
  const issue=message=>result.findings.push({code:'source_render_dependency_not_landed',location,message});
  if(!spec.fields.every(f=>targetFields.has(f))||spec.fields.some(f=>s.aliases.includes(f))){
   issue('Source readonly render dependency graph or target declared fields are unproven.');
   result.reviews.push({binding:location,reason:info.error||'undeclared_or_shadowed_dependency'});continue;
  }
  if(JSON.stringify(s.staticClass)!==JSON.stringify(d.staticClass)||JSON.stringify(s.adjacent)!==JSON.stringify(d.adjacent)){
   issue('Source render static class or adjacent literal context changed.');continue;
  }
  if(same(s.node,d.node)){
   if(info.error){issue('Source readonly render dependency graph or target declared fields are unproven.');
    result.reviews.push({binding:location,reason:info.error});continue;}
   issue('Source render method hides transitive reactive fields; preserve public methods and pass every field to a proven private render graph.');
   let names=copies.get(name);
   if(!names){names=new Map([...info.source].map(([n])=>[n,fresh('__sourceDependency_'+n)]));copies.set(name,names);
    for(const [n,e] of info.source){const copy=t.cloneNode(e.node,true);copy.key=t.identifier(names.get(n));
     copy.params.push(...e.fields.map(f=>t.identifier(ids.get(f))));
     walk(copy.body,x=>{if(t.isCallExpression(x)&&own(x.callee)){
      const child=info.source.get(x.callee.property.name);x.callee.property=t.identifier(names.get(x.callee.property.name));
      x.arguments.push(...child.fields.map(f=>t.identifier(ids.get(f))));
     }});additions.push(copy);
    }
   }
   const replacement=t.callExpression(t.identifier(names.get(name)),[...call.arguments.map(a=>t.cloneNode(a,true)),...spec.fields.map(f=>t.identifier(f))]);
   const targetCalls=[];walk(d.node,n=>{if(t.isCallExpression(n)&&t.isIdentifier(n.callee,{name}))targetCalls.push(n);});
   if(targetCalls.length!==1)throw Error('ambiguous_render_root');const targetCall=targetCalls[0];
   edits.push({start:templateOffset+d.start+targetCall.start,end:templateOffset+d.start+targetCall.end,text:print(replacement)});
   const bridges=[...new Set([...info.target.values()].flatMap(e=>e.corrections))].sort();
   result.proofs.push({binding:location,root:name,methods:[...info.source.keys()].sort(),fields:spec.fields,
    proof:bridges.length?'source_derived_private_graph_after_bounded_readonly_bridge_match':'exact_normalized_readonly_source_target_dag',
    corrected_legacy_array_bridges:bridges,computed_dependency_boundaries:spec.fields.filter(f=>one(one(original,'computed')?.value,f)),explicit:false});
  }else{
   const clone=t.cloneNode(d.node,true),candidates=[];walk(clone,n=>{if(t.isCallExpression(n)&&t.isIdentifier(n.callee))candidates.push(n);});
   if(candidates.length!==1){issue('Private render call shape is unproven.');continue;}
   const privateCall=candidates[0],args=privateCall.arguments;
   if(args.length!==call.arguments.length+spec.fields.length||!spec.fields.every((f,i)=>t.isIdentifier(args[call.arguments.length+i],{name:f}))
    ||!privateGraphIsExact(name,privateCall.callee.name,info.source,parent,ids,ast)){
    issue('Private render graph or explicit dependency arguments do not match the source graph.');continue;
   }
   const publicCall=privateCall.callee.name===name;
   privateCall.callee=t.identifier(name);privateCall.arguments=args.slice(0,call.arguments.length);
   if(!same(clone,s.node)){issue('Source render method arguments or expression changed.');continue;}
   if(s.role.startsWith('directive:'))result.scope_conditions.push({path:s.path,kind:s.role.slice(10),source:print(s.node),target:print(d.node)});
   result.proofs.push({binding:location,root:name,methods:[...info.source.keys()].sort(),fields:spec.fields,
    proof:'exact_explicit_graph_and_template_dependencies',explicit:true,preexisting_public_call:publicCall});
  }
 }
 if(additions.length)edits.push({start:scriptOffset+parent.start+1,end:scriptOffset+parent.start+1,text:'\n'+additions.map(print).join(',\n')+',\n'});
 edits.sort((a,b)=>b.start-a.start);for(let i=1;i<edits.length;i++)if(edits[i].end>edits[i-1].start)throw Error('Overlapping dependency edits');
 if(input.repair){for(const e of edits)result.code=result.code.slice(0,e.start)+e.text+result.code.slice(e.end);
  if(edits.length){parser.parse(/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(result.code)[1],{sourceType:'unambiguous'});result.changes=['explicit_source_readonly_render_dependency_graph'];}}
 return result;
}
module.exports={run};
if(require.main===module){
 try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(e){process.stdout.write(JSON.stringify({error:e.message}));}
}
