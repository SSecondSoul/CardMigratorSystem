// Complete source-native filter methods only; never rewrite a shared helper.
const parser=require('@babel/parser'),t=require('@babel/types'),traverse=require('@babel/traverse').default;
const {one,safe,method,same,print,walk}=require('./source_render_call_semantics.cjs');
const reserved=new Set(['data','watch','fire','initData','inited','attached','created','computed','components','template','dataTypes','constructor','prototype','__proto__','Array','Object','san']);
const nameOK=n=>typeof n==='string'&&/^[A-Za-z][\w$]*$/.test(n)&&!reserved.has(n);
const own=(n,k)=>t.isMemberExpression(n)&&!n.computed&&t.isThisExpression(n.object)&&t.isIdentifier(n.property)&&(!k||n.property.name===k);
const parseMethod=s=>parser.parseExpression('({'+s+'})').properties[0];
function dataObject(o,key){const m=method(o,key);return m&&!m.params.length&&!m.body.directives?.length&&m.body.body.length===1
 &&t.isReturnStatement(m.body.body[0])&&safe(m.body.body[0].argument)?m.body.body[0].argument:null;}
function exactSetter(methods,name){const m=method(methods,name);return m&&m.params.length===2&&m.params.every(p=>nameOK(p.name))
 &&m.params[0].name!==m.params[1].name&&same(m,parseMethod(`${name}(${m.params.map(p=>p.name)}){this[${m.params[0].name}]=${m.params[1].name};}`));}
function spec(fn,src,methods){
 if(!method(methods,fn.key.name)||!nameOK(fn.key.name)||fn.params.length!==1||!nameOK(fn.params[0].name)||fn.body.directives?.length)return null;
 const p=fn.params[0].name,b=fn.body.body;let expr,kind,next,setter,flag,flagValue,notify;
 if(b.length===1&&t.isReturnStatement(b[0])&&t.isMemberExpression(b[0].argument)&&!b[0].argument.computed
  &&t.isIdentifier(b[0].argument.property,{name:'length'})){kind='count';expr=b[0].argument.object;}
 else if(b.length===4&&t.isVariableDeclaration(b[0],{kind:'const'})&&b[0].declarations.length===1){
  const d=b[0].declarations[0];if(!t.isIdentifier(d.id)||!nameOK(d.id.name))return null;next=d.id.name;expr=d.init;kind='commit';
  const a=t.isExpressionStatement(b[1])&&b[1].expression,c=t.isExpressionStatement(b[2])&&b[2].expression,last=t.isExpressionStatement(b[3])&&b[3].expression;
  if(!t.isCallExpression(a)||!own(a.callee)||a.arguments.length!==2||!t.isStringLiteral(a.arguments[0])
   ||!t.isCallExpression(c)||!same(a.callee,c.callee)||c.arguments.length!==2||!t.isStringLiteral(c.arguments[0])||!t.isBooleanLiteral(c.arguments[1])
   ||!t.isCallExpression(last)||!own(last.callee)||last.arguments.length!==1||!t.isIdentifier(last.arguments[0],{name:next}))return null;
  setter=a.callee.property.name;flag=c.arguments[0].value;flagValue=c.arguments[1].value;notify=last.callee.property.name;
  if(![setter,flag,notify].every(nameOK)||!exactSetter(methods,setter))return null;
 }
 if(!t.isCallExpression(expr)||expr.optional||!t.isMemberExpression(expr.callee)||expr.callee.computed
  ||!t.isIdentifier(expr.callee.property,{name:'filter'})||!own(expr.callee.object)||expr.arguments.length!==1)return null;
 const root=expr.callee.object.property.name,cb=expr.arguments[0],test=cb?.body;
 if(!t.isArrowFunctionExpression(cb)||cb.async||cb.params.length!==1||!t.isIdentifier(cb.params[0])||!nameOK(cb.params[0].name)
  ||!t.isBinaryExpression(test,{operator:kind==='count'?'===':'!=='})||!t.isMemberExpression(test.left)||test.left.computed||!t.isIdentifier(test.left.property))return null;
 const row=cb.params[0].name,field=test.left.property.name;if(![root,field].every(nameOK)||row===p||next&&new Set([p,row,next]).size!==3)return null;
 const expression=`this.${root}.filter(${row}=>${row}.${field}${kind==='count'?'===':'!=='}${p})`;
 const expected=parseMethod(kind==='count'?`${fn.key.name}(${p}){return ${expression}.length;}`:
  `${fn.key.name}(${p}){const ${next}=${expression};this.${setter}('${root}',${next});this.${setter}('${flag}',${flagValue});this.${notify}(${next});}`);
 const data=dataObject(src.object,'data');
 if(!same(fn,expected)||!data||one(data,fn.key.name)||one(one(src.object,'props')?.value,fn.key.name)||one(one(src.object,'computed')?.value,fn.key.name)
  ||!t.isArrayExpression(one(data,root)?.value)||flag===root
  ||kind==='commit'&&!t.isBooleanLiteral(one(data,flag)?.value)
  ||[root,...(flag?[flag]:[])].some(k=>one(one(src.object,'props')?.value,k)||one(one(src.object,'computed')?.value,k)||one(methods,k)))return null;
 const output=t.cloneNode(fn,true),tree=t.file(t.program([t.expressionStatement(t.objectExpression([output]))]));
 traverse(tree,{CallExpression(path){const n=path.node;if(kind==='commit'&&own(n.callee,setter)){
   n.callee=parser.parseExpression('this.data.set');return;
  }},MemberExpression(path){if(own(path.node,root))path.replaceWith(parser.parseExpression(`this.data.get('${root}')`));}});
 return {name:fn.key.name,p,row,root,field,kind,next,flag,flagValue,notify,output,data};
}
function binding(ast,node,name){let b;traverse(ast,{ObjectMethod(p){if(p.node===node){b=p.scope.getBinding(name);p.stop();}}});return b;}
function definition(b){return b?.constant&&b.path.isFunctionDeclaration()&&b.path.parentPath.isProgram()
 &&!b.path.node.async&&!b.path.node.generator&&!b.path.node.body.directives?.length
 &&b.path.node.params.every(p=>t.isIdentifier(p)&&nameOK(p.name))
 &&new Set(b.path.node.params.map(p=>p.name)).size===b.path.node.params.length
 &&b.referencePaths.every(p=>p.parentPath.isCallExpression()&&p.parentPath.node.callee===p.node)?b.path.node:null;}
function alpha(fn){const ast=t.file(t.program([t.expressionStatement(t.functionExpression(null,fn.params.map(p=>t.cloneNode(p)),t.cloneNode(fn.body,true)))]));
 let unsafe=false;const bindings=[];traverse(ast,{Identifier(p){if(p.node.name.startsWith('__filterProof'))unsafe=true;},BindingIdentifier(p){const b=p.scope.getBinding(p.node.name);if(b&&!bindings.includes(b))bindings.push(b);}});
 if(unsafe)return null;bindings.forEach((b,i)=>b.scope.rename(b.identifier.name,'__filterProof'+i));return print(ast);}
function dense(ast,node,name){const fn=definition(binding(ast,node,name));return !!fn&&alpha(fn)===alpha(parser.parseExpression(
 'function(a,p){const r=[];for(let i=0;i<a.length;i++){if(p(a[i],i,a)){r.push(a[i]);}}return r;}'));}
// Prove the entire source event-only chain AND every target forwarding method.
function notification(ctx,src,methods,name){const active=new Set();
 if(one(methods,'$emit')||one(src.object,'$emit')||one(dataObject(src.object,'data'),'$emit')||one(one(src.object,'props')?.value,'$emit')||one(one(src.object,'computed')?.value,'$emit'))return null;
 function visit(name,args){if(active.has(name)||!nameOK(name))return null;active.add(name);
  const a=method(methods,name),b=method(ctx.parent,name)||(ctx.input.repair&&ctx.pending_event_forwarders?.get(name));if(!a||!b||a.body.directives?.length||a.body.body.length!==1||a.params.length!==args.length
   ||one(dataObject(src.object,'data'),name)||one(one(src.object,'props')?.value,name)||one(one(src.object,'computed')?.value,name)
   ||one(dataObject(ctx.parent,'initData'),name)||one(one(ctx.parent,'computed')?.value,name))return null;
  const s=a.body.body[0],c=t.isExpressionStatement(s)&&s.expression;
  if(!t.isCallExpression(c)||c.optional||!own(c.callee)||c.arguments.length!==2&&c.callee.property.name==='$emit')return null;
  const ps=a.params.map(p=>p.name);if(!c.arguments.every(x=>t.isStringLiteral(x)||t.isIdentifier(x)&&ps.includes(x.name)))return null;
  const output=t.cloneNode(a,true),leaf=c.callee.property.name==='$emit';
  if(leaf)output.body.body[0].expression.callee.property=t.identifier('fire');
  if(!same(output,b))return null;
  const passed=c.arguments.map(x=>t.isIdentifier(x)?args[ps.indexOf(x.name)]:x);
  if(leaf)return passed;
  return visit(c.callee.property.name,passed);
 }
 const result=visit(name,[t.identifier('__payload')]);return result&&result.length===2&&t.isStringLiteral(result[0])
  &&t.isIdentifier(result[1],{name:'__payload'})?result[0].value:null;
}
function legacy(current,s,ctx,event){
 if(!current)return false;const body=current.body.body,d=body[0]?.declarations?.[0];
 if(!t.isVariableDeclaration(body[0],{kind:'const'})||body[0].declarations.length!==1||!t.isIdentifier(d?.id)||!nameOK(d.id.name))return false;
 const root=d.id.name;if(root===s.p)return false;
 if(s.kind==='count'){
  const ret=body[1]?.argument;if(body.length!==2||!t.isReturnStatement(body[1])||!t.isCallExpression(ret)||!t.isIdentifier(ret.callee))return false;
  const helper=definition(binding(ctx.ast,current,ret.callee.name));if(!helper||helper.params.length!==2)return false;
  const [a,p]=helper.params.map(p=>p.name),length=helper.body.body[0]?.argument,call=t.isMemberExpression(length)&&length.object;
  const cb=call?.arguments?.[1],row=cb?.params?.[0]?.name;if(!nameOK(row)||!t.isCallExpression(call)||!t.isIdentifier(call.callee)||!dense(ctx.ast,current,call.callee.name))return false;
  const expected=parser.parse(`function ${helper.id.name}(${a},${p}){return ${call.callee.name}(${a},${row}=>${row}.${s.field}===${p}).length;}`).program.body[0];
  return same(helper,expected)&&same(current,parseMethod(`${s.name}(${s.p}){const ${root}=this.data.get('${s.root}');return ${ret.callee.name}(${root},${s.p});}`));
 }
 const second=body[1]?.declarations?.[0],call=second?.init,row=call?.arguments?.[1]?.params?.[0]?.name;
 if(!t.isVariableDeclaration(body[1],{kind:'const'})||body[1].declarations.length!==1||!t.isIdentifier(second?.id)||!nameOK(second.id.name)
  ||!t.isCallExpression(call)||!t.isIdentifier(call.callee)||!nameOK(row)||!event||!dense(ctx.ast,current,call.callee.name))return false;
 const next=second.id.name;if(new Set([root,next,s.p,row]).size!==4)return false;
 return same(current,parseMethod(`${s.name}(${s.p}){const ${root}=this.data.get('${s.root}');const ${next}=${call.callee.name}(${root},${row}=>${row}.${s.field}!==${s.p});this.data.set('${s.root}',${next});this.data.set('${s.flag}',${s.flagValue});this.fire(${JSON.stringify(event)},${next});}`));
}
function native(current,s){
 if(!current||current.params.length!==s.output.params.length||current.body.directives?.length)return false;
 if(alpha(current)===alpha(s.output))return true;
 const first=current.body.body[0],d=t.isVariableDeclaration(first,{kind:'const'})&&first.declarations.length===1&&first.declarations[0];
 if(!t.isIdentifier(d?.id)||!same(d.init,parser.parseExpression(`this.data.get('${s.root}')`)))return false;
 const expected=t.cloneNode(s.output,true),tree=t.file(t.program([t.expressionStatement(t.objectExpression([expected]))]));
 let collision=false,count=0;
 traverse(tree,{BindingIdentifier(p){if(p.node.name===d.id.name)collision=true;},CallExpression(p){
  if(same(p.node,parser.parseExpression(`this.data.get('${s.root}')`))){count++;p.replaceWith(t.cloneNode(d.id));}
 }});
 if(collision||count!==1)return false;expected.body.body.unshift(t.cloneNode(first,true));
 return alpha(current)===alpha(expected);
}
module.exports=function filterMethods(ctx,src,methods){
 if(!safe(src.object)||!safe(methods)||!safe(ctx.parent)||one(src.object,'mixins')||one(src.object,'extends')||one(src.object,'watch')
  ||one(ctx.parent,'mixins')||one(ctx.parent,'extends')||one(ctx.parent,'methods')||one(ctx.parent,'data')||one(ctx.parent,'fire'))return;
 let unsafe=false,runtime;traverse(ctx.ast,{Program(p){runtime=p.scope.getBinding('san');p.stop();}});
 for(const ast of [src.ast,ctx.ast]){traverse(ast,{Scope(p){if(['Array','Object'].some(n=>p.scope.hasOwnBinding(n)))unsafe=true;}});
  walk(ast,n=>{if(t.isAssignmentExpression(n)||t.isUpdateExpression(n)||t.isUnaryExpression(n,{operator:'delete'})){
   let a=t.isAssignmentExpression(n)?n.left:n.argument;while(t.isMemberExpression(a))a=a.object;
   if(t.isIdentifier(a)&&['Array','Object','san'].includes(a.name))unsafe=true;
  }});}
 const direct=ctx.ast.program.body.some(s=>t.isExpressionStatement(s)&&t.isAssignmentExpression(s.expression,{operator:'='})
  &&same(s.expression.left,parser.parseExpression('module.exports'))&&t.isCallExpression(s.expression.right)
  &&same(s.expression.right.callee,parser.parseExpression('san.defineComponent'))&&s.expression.right.arguments.length===1&&s.expression.right.arguments[0]===ctx.parent);
 if(unsafe||!direct||!runtime?.constant||!runtime.path.isVariableDeclarator()||!same(runtime.path.node.init,parser.parseExpression("require('san')"))||runtime.path.scope.getBinding('require'))return;
 const targetData=dataObject(ctx.parent,'initData');
 for(const fn of methods.properties){const s=spec(fn,src,methods);if(!s)continue;
  const current=method(ctx.parent,s.name),fields=[s.root,...(s.flag?[s.flag]:[])];
  const fieldsSafe=!!targetData&&!one(targetData,s.name)&&!one(one(ctx.parent,'dataTypes')?.value,s.name)&&!one(one(ctx.parent,'computed')?.value,s.name)
   &&fields.every(k=>!!one(targetData,k)&&same(one(targetData,k).value,one(s.data,k).value)&&!one(ctx.parent,k)&&!one(one(ctx.parent,'computed')?.value,k));
  const event=s.kind==='commit'?notification(ctx,src,methods,s.notify):null;
  const landed=fieldsSafe&&native(current,s)&&(s.kind==='count'||!!event);
  const eligible=fieldsSafe&&legacy(current,s,ctx,event),contract=`script.methods.${s.name}@${s.root}`;
  ctx.filter_method_contracts.push({contract,name:s.name,field:s.root,kind:s.kind,landed:!!landed,repair_eligible:!!eligible,
   proof:'complete_source_native_filter_method_and_closed_legacy_bindings',global_helpers_modified:false});
  if(landed)continue;
  ctx.findings.push({code:'source_filter_method_not_landed',location:contract,message:'Preserve the complete source native filter method: holes, snapshot length, callbacks, identities, exceptions and ordered root commit / flag / notification. Do not globally replace helpers or erase effects.'});
  if(ctx.input.repair&&eligible){ctx.edit(ctx.offset+current.start,ctx.offset+current.end,print(s.output));ctx.changes.push('restored_source_native_filter_method');}
 }
};
