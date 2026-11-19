// Source-derived parent computed collection bodies, never global helper rewrites.
// Legacy dense loops authorize correction only; they are NOT native equivalence.
const parser=require('@babel/parser'),t=require('@babel/types'),traverse=require('@babel/traverse').default;
const {one,safe,method,same,print,walk}=require('./source_render_call_semantics.cjs');
const own=n=>t.isMemberExpression(n)&&!n.computed&&t.isThisExpression(n.object)&&t.isIdentifier(n.property);
const member=(n,k)=>t.isMemberExpression(n)&&!n.computed&&t.isIdentifier(n.property,{name:k});
const nameOK=n=>typeof n==='string'&&/^[A-Za-z][\w$]*$/.test(n)
 &&!['data','watch','fire','initData','inited','attached','constructor','prototype','__proto__'].includes(n);
const parseMethod=s=>parser.parseExpression('({'+s+'})').properties[0];
function dataObject(o,name){const m=method(o,name);return m&&!m.params.length&&m.body.body.length===1
 &&t.isReturnStatement(m.body.body[0])&&safe(m.body.body[0].argument)?m.body.body[0].argument:null;}
function specification(fn,src){
 if(!t.isObjectMethod(fn)||!nameOK(fn.key.name)||fn.params.length||fn.async||fn.generator
  ||fn.kind!=='method'||fn.body.directives?.length||fn.body.body.length!==1||!t.isReturnStatement(fn.body.body[0]))return null;
 const value=fn.body.body[0].argument;let kind,root,field,matchField,orderField,expected;
 if(t.isCallExpression(value)&&member(value.callee,'sort')){
  const slice=value.callee.object,filter=t.isCallExpression(slice)&&member(slice.callee,'slice')&&slice.callee.object;
  const cb=t.isCallExpression(filter)&&filter.arguments[0],compare=value.arguments[0],test=cb?.body,call=compare?.body;
  if(!t.isCallExpression(filter)||!member(filter.callee,'filter')||!own(filter.callee.object)
   ||!t.isArrowFunctionExpression(cb)||cb.params.length!==1||!t.isIdentifier(cb.params[0])
   ||!t.isBinaryExpression(test,{operator:'==='})||!t.isMemberExpression(test.left)||test.left.computed||!own(test.right)
   ||!t.isArrowFunctionExpression(compare)||compare.params.length!==2||compare.params.some(p=>!t.isIdentifier(p))
   ||!t.isCallExpression(call)||!member(call.callee,'localeCompare')||!t.isMemberExpression(call.callee.object)
   ||call.callee.object.computed)return null;
  root=filter.callee.object.property.name;field=test.right.property.name;matchField=test.left.property.name;orderField=call.callee.object.property.name;
  const item=cb.params[0].name,[a,b]=compare.params.map(p=>p.name);
  expected=parseMethod(`${fn.key.name}(){return this.${root}.filter(${item}=>${item}.${matchField}===this.${field}).slice().sort((${a},${b})=>${a}.${orderField}.localeCompare(${b}.${orderField}));}`);
  kind='filter_slice_sort';
 }else if(t.isCallExpression(value)&&member(value.callee,'reduce')&&own(value.callee.object)){
  const cb=value.arguments[0],sum=cb?.body;
  if(!t.isArrowFunctionExpression(cb)||cb.params.length!==2||cb.params.some(p=>!t.isIdentifier(p))
   ||!t.isBinaryExpression(sum,{operator:'+'})||!t.isMemberExpression(sum.right)||sum.right.computed)return null;
  root=value.callee.object.property.name;matchField=sum.right.property.name;
  const [a,b]=cb.params.map(p=>p.name);
  expected=parseMethod(`${fn.key.name}(){return this.${root}.reduce((${a},${b})=>${a}+${b}.${matchField},0);}`);
  kind='reduce_sum';
 }else return null;
 if(![root,matchField,...(field?[field,orderField]:[])].every(nameOK)||!same(fn,expected))return null;
 const data=dataObject(src.object,'data'),props=one(src.object,'props')?.value,computed=one(src.object,'computed')?.value,
  methods=one(src.object,'methods')?.value;
 const fields=field?[root,field]:[root];
 if(!data||!t.isArrayExpression(one(data,root)?.value)||field&&(!['StringLiteral','NumericLiteral','BooleanLiteral'].includes(one(data,field)?.value?.type)||field===root)
  ||one(data,fn.key.name)||one(props,fn.key.name)||one(methods,fn.key.name)
  ||fields.some(n=>one(props,n)||one(computed,n)||one(methods,n)))return null;
 const output=t.cloneNode(fn,true),tree=t.file(t.program([t.expressionStatement(t.objectExpression([output]))]));
 traverse(tree,{MemberExpression(p){if(own(p.node)&&fields.includes(p.node.property.name))p.replaceWith(parser.parseExpression(`this.data.get(${JSON.stringify(p.node.property.name)})`));}});
 return {name:fn.key.name,root,field,matchField,orderField,kind,output,fields,data};
}
function binding(ast,node,name){let b;traverse(ast,{ObjectMethod(p){if(p.node===node){b=p.scope.getBinding(name);p.stop();}}});return b;}
function definition(b){return b?.constant&&b.path.isFunctionDeclaration()&&b.path.parentPath.isProgram()
 &&!b.path.node.async&&!b.path.node.generator&&b.path.node.params.every(p=>t.isIdentifier(p))
 &&new Set(b.path.node.params.map(p=>p.name)).size===b.path.node.params.length
 &&b.referencePaths.every(p=>p.parentPath.isCallExpression()&&p.parentPath.node.callee===p.node)?b.path.node:null;}
function alpha(fn){
 const tree=t.file(t.program([t.expressionStatement(t.functionExpression(null,fn.params.map(p=>t.cloneNode(p,true)),t.cloneNode(fn.body,true)))]));
 let unsafe=false;traverse(tree,{Identifier(p){if(p.node.name.startsWith('__collectionProof'))unsafe=true;}});if(unsafe)return null;
 const bindings=[];traverse(tree,{BindingIdentifier(p){const b=p.scope.getBinding(p.node.name);if(b&&!bindings.includes(b))bindings.push(b);}});
 bindings.forEach((b,i)=>b.scope.rename(b.identifier.name,'__collectionProof'+i));return print(tree);
}
const primitives={
 filter:'function(a,p){const r=[];for(let i=0;i<a.length;i++){if(p(a[i],i,a)){r.push(a[i]);}}return r;}',
 reduce:'function(a,cb,start){let sum=start;for(let i=0;i<a.length;i++){sum=cb(sum,a[i],i,a);}return sum;}',
 sort:'function(a,cb){const r=a.slice();r.sort(cb);return r;}'
};
function primitive(ast,target,name,kind){const fn=definition(binding(ast,target,name));return !!fn&&alpha(fn)===alpha(parser.parseExpression(primitives[kind]));}
function legacy(target,spec,ast){
 if(!target||target.params.length)return false;
 const b=target.body.body,decls=b.slice(0,-1).map(s=>t.isVariableDeclaration(s,{kind:'const'})&&s.declarations.length===1?s.declarations[0]:null);
 if(decls.length!==spec.fields.length||decls.some(d=>!t.isIdentifier(d?.id))||new Set(decls.map(d=>d.id.name)).size!==decls.length)return false;
 const call=t.isReturnStatement(b.at(-1))&&b.at(-1).argument;
 if(!t.isCallExpression(call)||!t.isIdentifier(call.callee))return false;
 const fn=definition(binding(ast,target,call.callee.name));if(!fn||fn.params.length!==decls.length||fn.body.body.length!==1||!t.isReturnStatement(fn.body.body[0]))return false;
 const expected=parseMethod(`${spec.name}(){${decls.map((d,i)=>`const ${d.id.name}=this.data.get('${spec.fields[i]}');`).join('')}return ${call.callee.name}(${decls.map(d=>d.id.name)});}`);
 if(!same(target,expected))return false;
 const ret=fn.body.body[0].argument,p=fn.params.map(p=>p.name);let text;
 if(spec.kind==='reduce_sum'){
  const cb=ret?.arguments?.[1];if(!t.isCallExpression(ret)||!t.isIdentifier(ret.callee)||!t.isArrowFunctionExpression(cb)||cb.params.length!==2||cb.params.some(p=>!t.isIdentifier(p)))return false;
  const [a,b]=cb.params.map(p=>p.name);
  text=`function ${fn.id.name}(${p}){return ${ret.callee.name}(${p[0]},(${a},${b})=>${a}+${b}.${spec.matchField},0);}`;
  if(!primitive(ast,target,ret.callee.name,'reduce'))return false;
 }else{
  const filter=ret?.arguments?.[0],cb=filter?.arguments?.[1],compare=ret?.arguments?.[1];
  if(!t.isCallExpression(ret)||!t.isIdentifier(ret.callee)||!t.isCallExpression(filter)||!t.isIdentifier(filter.callee)
   ||!t.isArrowFunctionExpression(cb)||cb.params.length!==1||!t.isIdentifier(cb.params[0])
   ||!t.isArrowFunctionExpression(compare)||compare.params.length!==2||compare.params.some(p=>!t.isIdentifier(p)))return false;
  const item=cb.params[0].name,[a,b]=compare.params.map(p=>p.name);
  text=`function ${fn.id.name}(${p}){return ${ret.callee.name}(${filter.callee.name}(${p[0]},${item}=>${item}.${spec.matchField}===${p[1]}),(${a},${b})=>${a}.${spec.orderField}.localeCompare(${b}.${spec.orderField}));}`;
  if(!primitive(ast,target,ret.callee.name,'sort')||!primitive(ast,target,filter.callee.name,'filter'))return false;
 }
 return same(fn,parser.parse(text).program.body[0]);
}
function nativeRootAlias(target,spec){
 if(!target||target.params.length||target.body.body.length!==2||target.body.directives?.length)return false;
 const declaration=target.body.body[0],d=t.isVariableDeclaration(declaration,{kind:'const'})&&declaration.declarations.length===1&&declaration.declarations[0];
 if(!d||!t.isIdentifier(d.id)||!same(d.init,parser.parseExpression(`this.data.get('${spec.root}')`)))return false;
 const expected=t.cloneNode(spec.output,true),tree=t.file(t.program([t.expressionStatement(t.objectExpression([expected]))]));
 let count=0;traverse(tree,{CallExpression(p){if(same(p.node,parser.parseExpression(`this.data.get('${spec.root}')`))){count++;p.replaceWith(t.cloneNode(d.id));}}});
 if(count!==1)return false;
 expected.body.body.unshift(t.cloneNode(declaration,true));return same(target,expected);
}
module.exports=function computedCollections(ctx,src){
 const source=one(src.object,'computed')?.value,target=one(ctx.parent,'computed')?.value;
 if(!safe(src.object)||!safe(source)||!safe(ctx.parent)||one(src.object,'mixins')||one(src.object,'extends')
  ||one(src.object,'watch')||one(ctx.parent,'mixins')||one(ctx.parent,'extends')||one(ctx.parent,'data'))return;
 let unsafe=false,runtime;traverse(ctx.ast,{Program(p){runtime=p.scope.getBinding('san');p.stop();}});
 for(const ast of [src.ast,ctx.ast]){
  traverse(ast,{Scope(p){if(['Array','Object','String'].some(n=>p.scope.hasOwnBinding(n)))unsafe=true;}});
  walk(ast,n=>{if(t.isAssignmentExpression(n)||t.isUpdateExpression(n)||t.isUnaryExpression(n,{operator:'delete'})){
   let root=t.isAssignmentExpression(n)?n.left:n.argument;while(t.isMemberExpression(root))root=root.object;
   if(t.isIdentifier(root)&&['Array','Object','String','san'].includes(root.name))unsafe=true;
  }});
 }
 const direct=ctx.ast.program.body.some(s=>t.isExpressionStatement(s)&&t.isAssignmentExpression(s.expression,{operator:'='})
  &&same(s.expression.left,parser.parseExpression('module.exports'))&&t.isCallExpression(s.expression.right)
  &&same(s.expression.right.callee,parser.parseExpression('san.defineComponent'))&&s.expression.right.arguments.length===1&&s.expression.right.arguments[0]===ctx.parent);
 if(unsafe||!direct||!runtime?.constant||!runtime.path.isVariableDeclarator()
  ||!same(runtime.path.node.init,parser.parseExpression("require('san')"))||runtime.path.scope.getBinding('require'))return;
 for(const fn of source.properties){
  const spec=specification(fn,src);if(!spec)continue;
  const current=safe(target)&&method(target,spec.name),data=dataObject(ctx.parent,'initData');
  const fields=!!data&&!one(data,spec.name)&&!one(ctx.parent,spec.name)
   &&spec.fields.every(n=>!!one(data,n)&&same(one(data,n).value,one(spec.data,n).value)&&!one(ctx.parent,n));
  const nativeAlias=!!fields&&!!current&&nativeRootAlias(current,spec);
  const landed=!!fields&&!!current&&(same(current,spec.output)||nativeAlias),eligible=!!fields&&!!current&&legacy(current,spec,ctx.ast);
  const contract=`script.computed.${spec.name}@${spec.root}`;
  ctx.computed_collection_contracts.push({contract,name:spec.name,field:spec.root,kind:spec.kind,fields:spec.fields,landed,repair_eligible:eligible,
   proof:'exact_source_native_collection_body_and_lexically_closed_legacy_bridge',native_root_alias_proven:!!nativeAlias,sparse_policy:'source_native',global_helpers_modified:false});
  if(landed)continue;
  ctx.findings.push({code:'source_computed_collection_not_landed',location:contract,
   message:'Preserve the complete source native computed collection operation, sparse holes, callback length/order, accumulator and exceptions. A dense helper loop is not native equivalence; do not invent a null guard or alter global helpers.'});
  if(ctx.input.repair&&eligible){ctx.edit(ctx.offset+current.start,ctx.offset+current.end,print(spec.output));ctx.changes.push('restored_source_native_computed_collection');}
 }
};
