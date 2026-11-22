// A complete registered child startup contract, never a global computed/watch rewrite.
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types');
const traverse=require('@babel/traverse').default,{parse}=require('@vue/compiler-sfc');
const {parentOf,key}=require('./inline_identifier_recovery.cjs');
const {one,safe,method,declared,print,same,walk,sourceParent,registered}=require('./source_render_call_semantics.cjs');
const id=s=>typeof s==='string'&&/^[A-Za-z_$][\w$]*$/.test(s)&&!['__proto__','constructor','prototype','watch','initData','inited'].includes(s);
const own=(n,name)=>t.isMemberExpression(n)&&!n.computed&&t.isThisExpression(n.object)&&(!name||t.isIdentifier(n.property,{name}));
const store=(n,op)=>t.isCallExpression(n)&&!n.optional&&t.isMemberExpression(n.callee)&&!n.callee.computed
 &&own(n.callee.object,'data')&&t.isIdentifier(n.callee.property,{name:op});
function bodyReturn(m){
 const body=m?.body?.body;if(body?.length!==1)return null;const s=body[0];
 if(t.isReturnStatement(s))return s.argument;
 const get=n=>t.isBlockStatement(n)&&n.body.length===1&&t.isReturnStatement(n.body[0])?n.body[0].argument:null;
 if(t.isIfStatement(s)&&get(s.consequent)&&get(s.alternate))return t.conditionalExpression(s.test,get(s.consequent),get(s.alternate));
 return null;
}
function factory(m){
 if(!t.isObjectMethod(m)||m.kind!=='method'||m.async||m.generator||m.params.length!==1||!t.isIdentifier(m.params[0])||!id(m.params[0].name))return null;
 const arg=m.params[0].name,expr=bodyReturn(m);if(!expr)return null;
 const literal=n=>t.isStringLiteral(n)||t.isNumericLiteral(n)||t.isBooleanLiteral(n)||t.isNullLiteral(n);
 const path=n=>t.isIdentifier(n,{name:arg})||(t.isMemberExpression(n)&&!n.computed&&id(n.property.name)&&path(n.object));
 const value=n=>literal(n)||path(n)
  ||(t.isLogicalExpression(n)&&['||','&&','??'].includes(n.operator)&&value(n.left)&&value(n.right))
  ||(t.isUnaryExpression(n)&&['!','+','-'].includes(n.operator)&&value(n.argument))
  ||(t.isConditionalExpression(n)&&value(n.test)&&value(n.consequent)&&value(n.alternate))
  ||(t.isArrayExpression(n)&&n.elements.every(e=>e&&(t.isSpreadElement(e)?value(e.argument):value(e))))
  ||(t.isObjectExpression(n)&&n.properties.every(p=>t.isSpreadElement(p)?path(p.argument)
    :t.isObjectProperty(p)&&!p.computed&&id(key(p))&&value(p.value)));
 const fresh=n=>t.isObjectExpression(n)||(t.isConditionalExpression(n)&&fresh(n.consequent)&&fresh(n.alternate));
 if(!fresh(expr)||!value(expr))return null;
 const result=t.cloneNode(m,true);result.body=t.blockStatement([t.returnStatement(t.cloneNode(expr,true))]);return result;
}
function returnedObject(m){return m&&m.body.body.length===1&&t.isReturnStatement(m.body.body[0])&&safe(m.body.body[0].argument)?m.body.body[0].argument:null;}
function contract(o){
 const data=returnedObject(method(o,'data')),props=one(o,'props')?.value,methods=one(o,'methods')?.value,watch=one(o,'watch')?.value;
 if(!data||!safe(methods)||!safe(watch)||watch.properties.length!==1)return null;
 const propNames=t.isArrayExpression(props)?props.elements.filter(t.isStringLiteral).map(n=>n.value):safe(props)?props.properties.map(key):[];
 const found=[];
 for(const p of data.properties){const call=p.value;
  if(!id(key(p))||!t.isCallExpression(call)||call.optional||!own(call.callee)||!id(call.callee.property.name)
   ||call.arguments.length!==1||!own(call.arguments[0])||!propNames.includes(call.arguments[0].property.name))continue;
  const name=call.callee.property.name,prop=call.arguments[0].property.name,original=factory(method(methods,name));
  if(!original||!id(prop)||!propNames.every(id)||propNames.includes(name)||one(data,name))continue;
  const w=one(watch,prop);let handler;
  if(t.isObjectMethod(w))handler=w;
  else if(t.isObjectProperty(w)&&safe(w.value)&&w.value.properties.every(p=>key(p)==='handler'))handler=one(w.value,'handler');
  if(!t.isObjectMethod(handler)||handler.async||handler.generator||handler.kind!=='method'||handler.params.length!==1
   ||!t.isIdentifier(handler.params[0])||!id(handler.params[0].name)||handler.body.body.length!==1)continue;
  const expected=t.expressionStatement(t.assignmentExpression('=',t.memberExpression(t.thisExpression(),t.identifier(key(p))),
   t.callExpression(t.memberExpression(t.thisExpression(),t.identifier(name)),[t.identifier(handler.params[0].name)])));
  if(!same(handler.body.body[0],expected))continue;
  found.push({name,prop,field:key(p),factory:original,handler,initial:t.expressionStatement(t.assignmentExpression('=',
   t.memberExpression(t.thisExpression(),t.identifier(key(p))),t.cloneNode(call,true))),props:propNames});
 }
 return found.length===1?found[0]:null;
}
function normalizeHook(m,spec,rename){
 const ast=t.file(t.program([t.expressionStatement(t.objectExpression([t.cloneNode(m,true)]))]));let path;
 traverse(ast,{ObjectMethod(p){path=p;p.stop();}});
 if(rename)path.scope.rename(path.node.params[0].name,rename);
 const fields=new Set([...spec.props,spec.field]);
 path.traverse({CallExpression(p){const n=p.node;
  if(store(n,'get')&&n.arguments.length===1&&t.isStringLiteral(n.arguments[0])&&fields.has(n.arguments[0].value))
   p.replaceWith(t.memberExpression(t.thisExpression(),t.identifier(n.arguments[0].value)));
  else if(store(n,'set')&&n.arguments.length===2&&t.isStringLiteral(n.arguments[0])&&fields.has(n.arguments[0].value))
   p.replaceWith(t.assignmentExpression('=',t.memberExpression(t.thisExpression(),t.identifier(n.arguments[0].value)),n.arguments[1]));
 },MemberExpression(p){if(!p.node.computed&&own(p.node.object,'computed')&&t.isIdentifier(p.node.property,{name:spec.name}))
   p.replaceWith(t.memberExpression(t.thisExpression(),t.identifier(spec.name)));}});
 let changed=true;while(changed){changed=false;path.scope.crawl();
  for(const statement of path.get('body.body')){const s=statement.node;if(!t.isVariableDeclaration(s,{kind:'const'})||s.declarations.length!==1)continue;
   const d=s.declarations[0];if(!t.isIdentifier(d.id)||!own(d.init)||!fields.has(d.init.property.name))continue;
   const b=path.scope.getBinding(d.id.name);if(!b?.constant)continue;
   b.referencePaths.forEach(p=>p.replaceWith(t.cloneNode(d.init,true)));statement.remove();changed=true;break;
  }
 }
 return path.node;
}
function watchCall(n,spec){
 if(!t.isExpressionStatement(n)||!t.isCallExpression(n.expression)||n.expression.optional||!own(n.expression.callee,'watch'))return false;
 const args=n.expression.arguments;if(args.length!==2||!t.isStringLiteral(args[0],{value:spec.prop}))return false;
 const fn=args[1];if(!t.isArrowFunctionExpression(fn)||fn.async||![1,2].includes(fn.params.length)||fn.params.some(p=>!t.isIdentifier(p))||!t.isBlockStatement(fn.body))return false;
 let body=fn.body,guarded=false;
 if(fn.params.length===2){
  const guard=t.binaryExpression('===',['change','expr','paths','length'].reduce((o,k)=>t.memberExpression(o,t.identifier(k)),t.cloneNode(fn.params[1],true)),t.numericLiteral(1));
  const statement=body.body[0];
  if(body.body.length!==1||!t.isIfStatement(statement)||statement.alternate||!t.isBlockStatement(statement.consequent)||!same(statement.test,guard))return false;
  body=statement.consequent;guarded=true;
 }
 const fake=t.objectMethod('method',t.identifier('__callback'),[fn.params[0]],t.cloneNode(body,true));
 const actual=normalizeHook(fake,spec,spec.handler.params[0].name);
 return same(actual.body,spec.handler.body)?{guarded}:false;
}
function run(input){
 const result={code:input.code,findings:[],changes:[],proofs:[],reviews:[],mapped_contracts:[]};
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(input.code),src=parse(input.vue);
 if(!block||src.errors.length||!src.descriptor.script||src.descriptor.scriptSetup)return result;
 const script=block[1],offset=block.index+block[0].indexOf('>')+1;
 const ast=parser.parse(script,{sourceType:'unambiguous'}),srcAst=parser.parse(src.descriptor.script.content,{sourceType:'unambiguous'});
 const parent=parentOf(ast),original=sourceParent(srcAst),registry=one(original,'components')?.value;
 if(!safe(parent)||!safe(registry)||!safe(original))return result;
 let binding;traverse(ast,{Program(p){binding=p.scope.getBinding('san');}});
 if(!binding?.constant||!binding.path.isVariableDeclarator()||!t.isCallExpression(binding.path.node.init)
  ||!t.isIdentifier(binding.path.node.init.callee,{name:'require'})||binding.path.node.init.arguments.length!==1
  ||!t.isStringLiteral(binding.path.node.init.arguments[0],{value:'san'})||binding.path.scope.getBinding('require'))return result;
 let changedRuntime=false;walk(ast,n=>{if(!t.isAssignmentExpression(n))return;let root=n.left;
  while(t.isMemberExpression(root))root=root.object;if(t.isIdentifier(root,{name:'san'}))changedRuntime=true;});
 if(changedRuntime)return result;
 const normalizeTag=s=>s.replace(/([a-z0-9])([A-Z])/g,'$1-$2').toLowerCase();
 const edits=[],visited=new Set();
 for(const reg of registry.properties){const tag=normalizeTag(key(reg));if(visited.has(tag))continue;visited.add(tag);
  const a=registered(srcAst,original,tag,false);if(!a||['mixins','extends'].some(k=>one(a.object,k)))continue;
  const spec=contract(a.object);if(!spec)continue;
  const identity='script.'+tag+'.'+spec.field+'@'+spec.prop;
  const b=registered(ast,parent,tag,true);result.mapped_contracts.push(identity);
  const finding=(kind,message)=>result.findings.push({code:'source_child_'+kind+'_not_landed',location:identity,message});
  if(!b||!safe(b.object)||['mixins','extends'].some(k=>one(b.object,k))){
   finding('factory','Registered source child factory/initialization is not mapped.');
   finding('watch','Registered source prop watcher is not mapped.');continue;
  }
  const object=b.object,computed=one(object,'computed')?.value,computedFactory=one(computed,spec.name),direct=one(object,spec.name);
  let candidate,kind;
  if(direct&&!computedFactory){candidate=factory(direct);kind='method';}
  if(!direct&&t.isObjectMethod(computedFactory)&&!computedFactory.params.length&&!computedFactory.async&&!computedFactory.generator
   &&computedFactory.body.body.length===1&&t.isReturnStatement(computedFactory.body.body[0])){
   const fn=computedFactory.body.body[0].argument;
   if(t.isArrowFunctionExpression(fn)&&!fn.async&&t.isBlockStatement(fn.body)){
    candidate=factory(t.objectMethod('method',t.identifier(spec.name),fn.params,fn.body));kind='computed_wrapper';
   }
  }
  const factoryMatches=!!candidate&&same(candidate,spec.factory);
  const init=one(object,'inited'),watch=one(object,'watch');
  let initBody=[],initRecognized=true,initial=false,hookWatch=false,hookWatchInfo=false,overrideWatch=false;
  if(init){if(!t.isObjectMethod(init)||init.params.length||init.async||init.generator)initRecognized=false;
   else{const normalized=normalizeHook(init,spec);initBody=normalized.body.body;
    initial=initBody.length>=1&&same(initBody[0],spec.initial);
    hookWatchInfo=initBody.length>=1&&watchCall(initBody.at(-1),spec);hookWatch=!!hookWatchInfo;
    if(initBody.length!==(initial?1:0)+(hookWatch?1:0))initRecognized=false;
   }
  }
  let overrideRecognized=!watch;
  if(watch){overrideRecognized=t.isObjectMethod(watch)&&!watch.params.length&&!watch.async&&!watch.generator&&watch.body.body.length===1&&watchCall(watch.body.body[0],spec);
   overrideWatch=overrideRecognized;
  }
  // Changing a computed contract is allowed only for these exact startup callers.
  const allowed=[direct,computedFactory,init,watch].filter(Boolean);let outside=false;
  for(const prop of object.properties.filter(p=>!allowed.includes(p))){
   walk(prop,n=>{if((t.isMemberExpression(n)&&!n.computed&&t.isIdentifier(n.property,{name:spec.name}))
    ||(t.isStringLiteral(n)&&n.value===spec.name)||own(n,'watch')
    ||(t.isMemberExpression(n)&&n.computed&&(t.isThisExpression(n.object)||own(n.object,'computed')))
    ||(store(n,'get')&&(n.arguments.length!==1||!t.isStringLiteral(n.arguments[0]))))outside=true;});
   const escaped=spec.name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
   if(t.isTemplateLiteral(prop.value)&&prop.value.quasis.some(q=>new RegExp('(?<![\\w$])'+escaped+'(?![\\w$])').test(q.value.raw)
    ||/\bthis\s*\[|\bcomputed\s*\[/.test(q.value.raw)))outside=true;
  }
  const parentFactory=returnedObject(method(object,'initData'));
  const declaredFields=declared(object,false),targetProp=declaredFields.has(spec.prop),targetField=!!one(parentFactory,spec.field);
  const recoverable=factoryMatches&&initRecognized&&overrideRecognized&&!(overrideWatch&&hookWatch)&&!outside&&targetProp&&targetField
   &&(!computedFactory||safe(computed));
  // A direct source method must be called directly in the original target hook too.
  const hasWrongReceiver=node=>{let found=false;if(node)walk(node,n=>{if(t.isMemberExpression(n)&&!n.computed&&own(n.object,'computed')
   &&t.isIdentifier(n.property,{name:spec.name}))found=true;});return found;};
  const factoryLanded=factoryMatches&&kind==='method'&&initial&&initRecognized&&!hasWrongReceiver(init);
  const watchLanded=!watch&&hookWatch&&hookWatchInfo.guarded&&initRecognized&&!hasWrongReceiver(init);
  if(!factoryLanded)finding('factory','Source pure factory and first prop-derived object initialization are not proven as direct methods.');
  if(!watchLanded)finding('watch','Source root-prop watcher must be registered once after initialization without overriding San watch.');
  if(!recoverable){result.reviews.push({contract:identity,reason:'unknown_factory_hook_watcher_or_external_use'});continue;}
  result.proofs.push({contract:identity,registered_tag:tag,component:b.name,factory:spec.name,prop:spec.prop,field:spec.field,
   original_kind:kind,factory_landed:factoryLanded,watch_landed:watchLanded,shallow_root_change_guard:!!hookWatchInfo.guarded,
   proof:'exact_pure_source_factory_initial_value_and_shallow_root_watcher'});
  if(factoryLanded&&watchLanded)continue;
  if(kind==='computed_wrapper'){
   const kept=computed.properties.filter(p=>p!==computedFactory).map(p=>script.slice(p.start,p.end));
   edits.push({start:computed.start,end:computed.end,text:'{'+kept.join(',\n')+'}'});
   edits.push({start:object.start+1,end:object.start+1,text:'\n'+print(spec.factory)+',\n'});
  }
  const read=t.callExpression(t.memberExpression(t.memberExpression(t.thisExpression(),t.identifier('data')),t.identifier('get')),[t.stringLiteral(spec.prop)]);
  const assign=value=>t.expressionStatement(t.callExpression(t.memberExpression(t.memberExpression(t.thisExpression(),t.identifier('data')),t.identifier('set')),
   [t.stringLiteral(spec.field),t.callExpression(t.memberExpression(t.thisExpression(),t.identifier(spec.name)),[value])]));
  const param=t.cloneNode(spec.handler.params[0],true);
  let meta='__sourceChildChange';while(meta===param.name)meta+='_';
  const change=t.identifier(meta),guard=t.binaryExpression('===',['change','expr','paths','length'].reduce((o,k)=>t.memberExpression(o,t.identifier(k)),t.cloneNode(change)),t.numericLiteral(1));
  const hook=t.objectMethod('method',t.identifier('inited'),[],t.blockStatement([assign(read),t.expressionStatement(t.callExpression(
   t.memberExpression(t.thisExpression(),t.identifier('watch')),[t.stringLiteral(spec.prop),t.arrowFunctionExpression([param,change],
    t.blockStatement([t.ifStatement(guard,t.blockStatement([assign(t.cloneNode(param,true))]))]))]))]));
  if(init)edits.push({start:init.start,end:init.end,text:print(hook)});
  else edits.push({start:object.start+1,end:object.start+1,text:'\n'+print(hook)+',\n'});
  if(watch){let start=watch.start,end=watch.end;while(/\s/.test(script[end]||'')&&end<script.length)end++;
   if(script[end]===',')end++;else{let p=start-1;while(/\s/.test(script[p]||'')&&p>object.start)p--;if(script[p]===',')start=p;}
   edits.push({start,end,text:''});
  }
 }
 edits.sort((a,b)=>b.start-a.start);for(let i=1;i<edits.length;i++)if(edits[i].end>edits[i-1].start)throw Error('Overlapping child startup edits');
 if(input.repair&&edits.length){let next=script;for(const e of edits)next=next.slice(0,e.start)+e.text+next.slice(e.end);
  parser.parse(next,{sourceType:'unambiguous'});result.code=input.code.slice(0,offset)+next+input.code.slice(offset+script.length);
  result.changes=['restored_source_child_factory_initialization_and_watch'];}
 return result;
}
try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
catch(e){process.stdout.write(JSON.stringify({error:e.message}));}
