// Source-faithful shared-record swaps. This is NOT record detachment proof:
// the separate nested-state validator deliberately retains its diagnostic.
const parser=require('@babel/parser'),t=require('@babel/types'),traverse=require('@babel/traverse').default;
const {one,safe,method,arrayPath,print,same,walk}=require('./source_render_call_semantics.cjs');
const own=(n,name)=>t.isMemberExpression(n)&&!n.computed&&t.isThisExpression(n.object)
 &&(!name||t.isIdentifier(n.property,{name}));
const namesafe=s=>typeof s==='string'&&/^[A-Za-z][\w$]*$/.test(s)
 &&!['data','fire','watch','initData','inited','attached','disposed','constructor','prototype','__proto__'].includes(s);
const variable=s=>t.isVariableDeclaration(s,{kind:'const'})&&s.declarations.length===1
 &&t.isIdentifier(s.declarations[0].id)?s.declarations[0]:null;
const parseMethod=text=>parser.parseExpression('({'+text+'})').properties[0];
function sourceSpec(fn,src,methods){
 if(!t.isObjectMethod(fn)||!namesafe(fn.key.name)||fn.async||fn.generator||fn.params.length!==2
  ||fn.params.some(p=>!t.isIdentifier(p))||fn.body.body.length!==12||fn.body.directives?.length)return null;
 const b=fn.body.body,rows=variable(b[0]),target=variable(b[1]),temp=variable(b[3]),mapped=variable(b[6]),next=variable(b[8]);
 if(!rows||!target||!temp||!mapped||!next)return null;
 const slice=rows.init,map=next.init;
 if(!t.isCallExpression(slice)||!t.isMemberExpression(slice.callee)||!own(slice.callee.object)
  ||!t.isCallExpression(map)||!t.isMemberExpression(map.callee)||!own(map.callee.object))return null;
 const derived=slice.callee.object.property.name,root=map.callee.object.property.name,computed=one(src.object,'computed')?.value;
 if(!namesafe(root)||!namesafe(derived)||!method(computed,derived)||method(computed,derived).params.length||!arrayPath(src.object,[root]))return null;
 const notify=t.isExpressionStatement(b[11])&&b[11].expression;
 const first=t.isExpressionStatement(b[9])&&b[9].expression,flag=t.isExpressionStatement(b[10])&&b[10].expression;
 if(!t.isCallExpression(first)||!own(first.callee)||!t.isCallExpression(flag)||!own(flag.callee)
  ||!t.isCallExpression(notify)||!own(notify.callee)||flag.arguments.length!==2
  ||!t.isStringLiteral(flag.arguments[0])||!namesafe(flag.arguments[0].value)||!t.isBooleanLiteral(flag.arguments[1]))return null;
 const setter=method(methods,first.callee.property.name),notification=method(methods,notify.callee.property.name);
 if(!setter||setter.params.length!==2||setter.params.some(p=>!t.isIdentifier(p))||!notification||notification.params.length!==1
  ||!t.isIdentifier(notification.params[0])||notification.body.body.length!==1||notification.body.directives?.length)return null;
 const a=setter.params[0].name,v=setter.params[1].name;
 if(a===v||!same(setter,parseMethod(`${setter.key.name}(${a},${v}){this[${a}]=${v};}`)))return null;
 const send=t.isExpressionStatement(notification.body.body[0])&&notification.body.body[0].expression;
 if(!t.isCallExpression(send)||!own(send.callee)||send.arguments.length!==2||!t.isStringLiteral(send.arguments[0])
  ||!t.isIdentifier(send.arguments[1],{name:notification.params[0].name}))return null;
 const emitter=method(methods,send.callee.property.name);
 if(!emitter||emitter.params.length!==2||emitter.params.some(p=>!t.isIdentifier(p)))return null;
 const e=emitter.params.map(p=>p.name);
 if(e[0]===e[1]||!same(emitter,parseMethod(`${emitter.key.name}(${e}){this.$emit(${e});}`)))return null;
 const expectedEmitter=t.cloneNode(emitter,true);expectedEmitter.body.body[0].expression.callee.property=t.identifier('fire');
 const each=t.isExpressionStatement(b[7])&&b[7].expression;
 if(!t.isCallExpression(each)||!t.isArrowFunctionExpression(each.arguments[0])||each.arguments[0].params.length!==1
  ||!t.isIdentifier(each.arguments[0].params[0])||!t.isArrowFunctionExpression(map.arguments[0])
  ||map.arguments[0].params.length!==1||!t.isIdentifier(map.arguments[0].params[0]))return null;
 const item=each.arguments[0].params[0].name,record=map.arguments[0].params[0].name;
 const test=map.arguments[0].body?.test;
 if(!t.isMemberExpression(test)||!t.isMemberExpression(test.property)||test.property.computed)return null;
 const id=test.property.property.name,property=t.isMemberExpression(temp.init)&&!temp.init.computed&&temp.init.property.name;
 if(!namesafe(id)||!namesafe(property))return null;
 const [index,delta]=fn.params.map(p=>p.name),r=rows.id.name,j=target.id.name,x=temp.id.name,m=mapped.id.name,n=next.id.name;
 if(new Set([index,delta,r,j,x,m,n]).size!==7)return null;
 const expected=parseMethod(`${fn.key.name}(${index},${delta}){
 const ${r}=this.${derived}.slice();const ${j}=${index}+${delta};if(${j}<0||${j}>=${r}.length)return;
 const ${x}=${r}[${index}].${property};${r}[${index}].${property}=${r}[${j}].${property};${r}[${j}].${property}=${x};
 const ${m}={};${r}.forEach(${item}=>${m}[${item}.${id}]=${item});
 const ${n}=this.${root}.map(${record}=>${m}[${record}.${id}]?Object.assign({},${m}[${record}.${id}]):${record});
 this.${setter.key.name}('${root}',${n});this.${setter.key.name}(${JSON.stringify(flag.arguments[0].value)},${flag.arguments[1].value});this.${notification.key.name}(${n});}`);
 if(!same(fn,expected))return null;
 const flagName=flag.arguments[0].value;
 if(new Set([root,derived,flagName]).size!==3||one(methods,flagName)||one(computed,flagName))return null;
 const data=method(src.object,'data'),dataObject=data?.body.body.length===1&&data.body.body[0].argument;
 if(!safe(dataObject)||!one(dataObject,flagName)||one(dataObject,derived)
  ||[root,derived,flagName].some(f=>one(one(src.object,'props')?.value,f))
  ||one(one(src.object,'computed')?.value,root)||one(methods,root)||one(methods,derived))return null;
 const output=t.cloneNode(fn,true),tree=t.file(t.program([t.expressionStatement(t.objectExpression([output]))]));
 traverse(tree,{CallExpression(p){if(own(p.node.callee,setter.key.name))p.node.callee=t.memberExpression(t.memberExpression(t.thisExpression(),t.identifier('data')),t.identifier('set'));},
  MemberExpression(p){if(own(p.node)&&[root,derived].includes(p.node.property.name))p.replaceWith(t.callExpression(t.memberExpression(t.memberExpression(t.thisExpression(),t.identifier('data')),t.identifier('get')),[t.stringLiteral(p.node.property.name)]));}});
 return {name:fn.key.name,root,derived,property,id,event:send.arguments[0].value,notification:notification.key.name,
  flag:flagName,flagValue:flag.arguments[1].value,emitterName:emitter.key.name,expectedEmitter,expectedNotification:notification,output};
}
function bindingFor(ast,fn,name){let found;traverse(ast,{ObjectMethod(p){if(p.node===fn){found=p.scope.getBinding(name);p.stop();}}});return found;}
function exactHelper(binding,kind){
 if(!binding?.constant||!binding.path.isFunctionDeclaration()||!binding.path.parentPath.isProgram())return false;
 const fn=binding.path.node,b=fn.body.body,p=fn.params;
 if(fn.async||fn.generator||fn.body.directives?.length||p.some(n=>!t.isIdentifier(n)))return false;
 const name=fn.id.name;
 let text;
 if(kind==='clone'&&p.length===1&&b.length===5&&variable(b[2])&&t.isForInStatement(b[3])){
  const arg=p[0].name,r=variable(b[2]).id.name,k=b[3].left?.declarations?.[0]?.id?.name;
  if(!k)return false;
  text=`function ${name}(${arg}){if(${arg}===null||typeof ${arg}!=='object')return ${arg};if(Array.isArray(${arg}))return ${arg}.map(${name});const ${r}={};for(let ${k} in ${arg}){if(${arg}.hasOwnProperty(${k})){${r}[${k}]=${name}(${arg}[${k}]);}}return ${r};}`;
 }else if(kind==='map'&&p.length===2&&b.length===3&&variable(b[0])&&t.isForStatement(b[1])){
  const [arg,cb]=p.map(n=>n.name),r=variable(b[0]).id.name,i=b[1].init?.declarations?.[0]?.id?.name;if(!i)return false;
  text=`function ${name}(${arg},${cb}){const ${r}=[];for(let ${i}=0;${i}<${arg}.length;${i}++){${r}.push(${cb}(${arg}[${i}],${i},${arg}));}return ${r};}`;
 }else if(kind==='slice'&&p.length===3&&b.length===6&&b.slice(0,4).every(variable)&&t.isForStatement(b[4])){
  const [arg,start,end]=p.map(n=>n.name),[r,len,s,e]=b.slice(0,4).map(n=>variable(n).id.name),i=b[4].init?.declarations?.[0]?.id?.name;if(!i)return false;
  text=`function ${name}(${arg},${start},${end}){const ${r}=[];const ${len}=${arg}.length;const ${s}=${start}==null?0:(${start}<0?Math.max(${len}+${start},0):Math.min(${start},${len}));const ${e}=${end}==null?${len}:(${end}<0?Math.max(${len}+${end},0):Math.min(${end},${len}));for(let ${i}=${s};${i}<${e};${i}++){${r}.push(${arg}[${i}]);}return ${r};}`;
 }else return false;
 return same(fn,parser.parse(text).program.body[0]);
}
function legacy(target,spec,ast){
 const b=target?.body.body;if(!b||b.length!==14||target.params.length!==2||target.params.some(p=>!t.isIdentifier(p)))return false;
 const ds=[0,1,2,4,7,9,10].map(i=>variable(b[i]));if(ds.some(d=>!d))return false;
 const [d,r,j,x,m,items,n]=ds.map(d=>d.id.name),[index,delta]=target.params.map(p=>p.name);
 if(new Set([d,r,j,x,m,items,n,index,delta]).size!==9)return false;
 const slice=ds[1].init,map=ds[6].init,loop=b[8];
 if(!t.isCallExpression(slice)||!t.isIdentifier(slice.callee)||!t.isCallExpression(map)||!t.isIdentifier(map.callee)
  ||!t.isArrowFunctionExpression(map.arguments[1])||map.arguments[1].params.length!==1||!t.isIdentifier(map.arguments[1].params[0])
  ||!t.isForStatement(loop))return false;
 const cb=map.arguments[1],cloned=cb.body?.consequent,k=loop.init?.declarations?.[0]?.id?.name,item=cb.params[0].name;
 if(!t.isCallExpression(cloned)||!t.isIdentifier(cloned.callee)||!k)return false;
 for(const [name,kind] of [[slice.callee.name,'slice'],[map.callee.name,'map'],[cloned.callee.name,'clone']])
  if(!exactHelper(bindingFor(ast,target,name),kind))return false;
 const expected=parseMethod(`${spec.name}(${index},${delta}){
 const ${d}=this.data.get('${spec.derived}');const ${r}=${slice.callee.name}(${d},0);const ${j}=${index}+${delta};
 if(${j}<0||${j}>=${r}.length)return;const ${x}=${r}[${index}].${spec.property};${r}[${index}].${spec.property}=${r}[${j}].${spec.property};${r}[${j}].${spec.property}=${x};
 const ${m}={};for(let ${k}=0;${k}<${r}.length;${k}++){${m}[${r}[${k}].${spec.id}]=${r}[${k}];}
 const ${items}=this.data.get('${spec.root}');const ${n}=${map.callee.name}(${items},${item}=>${m}[${item}.${spec.id}]?${cloned.callee.name}(${m}[${item}.${spec.id}]):${item});
 this.data.set('${spec.root}',${n});this.data.set('${spec.flag}',${spec.flagValue});this.fire(${JSON.stringify(spec.event)},${n});}`);
 return same(target,expected)&&same(t.arrayExpression(target.params),t.arrayExpression(spec.output.params));
}
module.exports=function sharedSwaps(ctx,src,methods){
 if(!safe(src.object)||!safe(methods)||!safe(ctx.parent)||one(src.object,'mixins')||one(src.object,'extends')||one(src.object,'watch')
  ||one(ctx.parent,'mixins')||one(ctx.parent,'extends')||one(ctx.parent,'methods')||one(ctx.parent,'fire')||one(ctx.parent,'data')
  ||one(methods,'$emit')||one(src.object,'$emit'))return;
 let unsafe=false,runtime;traverse(ctx.ast,{Program(p){runtime=p.scope.getBinding('san');p.stop();}});
 const direct=ctx.ast.program.body.some(s=>t.isExpressionStatement(s)&&t.isAssignmentExpression(s.expression,{operator:'='})
  &&t.isMemberExpression(s.expression.left)&&!s.expression.left.computed&&t.isIdentifier(s.expression.left.object,{name:'module'})
  &&t.isIdentifier(s.expression.left.property,{name:'exports'})&&t.isCallExpression(s.expression.right)
  &&t.isMemberExpression(s.expression.right.callee)&&!s.expression.right.callee.computed
  &&t.isIdentifier(s.expression.right.callee.object,{name:'san'})&&t.isIdentifier(s.expression.right.callee.property,{name:'defineComponent'})
  &&s.expression.right.arguments[0]===ctx.parent);
 if(!direct||!runtime?.constant||!runtime.path.isVariableDeclarator()||!t.isCallExpression(runtime.path.node.init)
  ||!t.isIdentifier(runtime.path.node.init.callee,{name:'require'})||runtime.path.node.init.arguments.length!==1
  ||!t.isStringLiteral(runtime.path.node.init.arguments[0],{value:'san'})||runtime.path.scope.getBinding('require'))return;
 for(const a of [src.ast,ctx.ast]){
  traverse(a,{Scope(p){if(['Object','Array','Math'].some(n=>p.scope.hasOwnBinding(n)))unsafe=true;}});
  walk(a,n=>{if(t.isAssignmentExpression(n)||t.isUpdateExpression(n)||t.isUnaryExpression(n,{operator:'delete'})){
   let root=t.isAssignmentExpression(n)?n.left:n.argument;while(t.isMemberExpression(root))root=root.object;
   if(t.isIdentifier(root)&&['Object','Array','Math','san'].includes(root.name))unsafe=true;
  }});
 }
 if(unsafe)return;
 for(const fn of methods.properties){const spec=sourceSpec(fn,src,methods);if(!spec)continue;
  const targetData=method(ctx.parent,'initData'),data=targetData?.body.body.length===1&&targetData.body.body[0].argument;
  const targetDerived=method(one(ctx.parent,'computed')?.value,spec.derived);
  const fields=safe(data)&&t.isArrayExpression(one(data,spec.root)?.value)&&!!one(data,spec.flag)&&!one(data,spec.derived)
   &&!!targetDerived&&!targetDerived.params.length&&!one(one(ctx.parent,'computed')?.value,spec.root)
   &&!one(one(ctx.parent,'computed')?.value,spec.flag);
  const exact=(name,node)=>{const m=method(ctx.parent,name);return !!m&&same(m,node);};
  const planned=name=>!!ctx.input.repair&&!one(ctx.parent,name)&&!!ctx.method_contracts?.some(c=>c.name===name&&c.restore_eligible
   &&c.proof==='closed_two_argument_source_emit_forwarding_graph_no_target_triggers');
  const actualHelpers=exact(spec.emitterName,spec.expectedEmitter)&&exact(spec.notification,spec.expectedNotification);
  const helpers=actualHelpers||(exact(spec.emitterName,spec.expectedEmitter)||planned(spec.emitterName))
   &&(exact(spec.notification,spec.expectedNotification)||planned(spec.notification));
  const target=method(ctx.parent,spec.name),landed=!!fields&&actualHelpers&&!!target&&same(target,spec.output);
  const eligible=!!fields&&helpers&&!!target&&legacy(target,spec,ctx.ast);
  const contract=`script.methods.${spec.name}@${spec.root}`;
  ctx.shared_record_contracts.push({contract,name:spec.name,field:spec.root,derived_boundary:spec.derived,landed,repair_eligible:eligible,
   proof:'exact_source_shared_swap_then_shallow_projection_and_ordered_root_commits',nested_mutation_exemption:false,
   reuses_planned_event_forwarders:!!eligible&&!actualHelpers});
  if(landed)continue;
  ctx.findings.push({code:'source_shared_record_projection_not_landed',location:contract,
   message:'Preserve source shared-record writes, shallow selected-record projection, unchanged-record identities and ordered root commit/notification. Do not deep-clone or waive the separate mutation review.'});
  if(ctx.input.repair&&eligible){ctx.edit(ctx.offset+target.start,ctx.offset+target.end,print(spec.output));ctx.changes.push('restored_source_shared_swap_shallow_projection');}
 }
};
