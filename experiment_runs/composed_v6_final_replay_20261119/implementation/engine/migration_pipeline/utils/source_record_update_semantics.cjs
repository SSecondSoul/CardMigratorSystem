// Literal-root shallow record updates, derived from complete source methods.
// No arbitrary setter migration, clone execution, name-based waiver or polling.
const parser=require('@babel/parser'),t=require('@babel/types');
const traverse=require('@babel/traverse').default;
const {one,safe,method,print,same,walk}=require('./source_render_call_semantics.cjs');
const own=(n,name)=>t.isMemberExpression(n)&&!n.computed&&t.isThisExpression(n.object)
 &&(!name||t.isIdentifier(n.property,{name}));
const identifier=n=>t.isIdentifier(n)&&/^[A-Za-z_$][\w$]*$/.test(n.name);
const forbidden=new Set(['__proto__','constructor','prototype','data','fire','watch']);
const reservedMethods=new Set([...forbidden,'initData','inited','compiled','created','attached','updated',
 'detached','disposed','dispose','attach','detach','ref','slot','error','template','components','computed','dataTypes']);
// Vue does not proxy data names beginning with $ or _ onto the instance.
const rootName=n=>t.isStringLiteral(n)&&/^[A-Za-z][\w$]*$/.test(n.value)&&!forbidden.has(n.value);
function literalRecord(options,factory,field){
 const fn=method(options,factory);
 return !!fn&&!fn.params.length&&fn.body.body.length===1&&t.isReturnStatement(fn.body.body[0])
  &&safe(fn.body.body[0].argument)&&safe(one(fn.body.body[0].argument,field)?.value);
}
function globalsSafe(ast){
 let ok=true;
 traverse(ast,{Scope(p){if(['Object','Number','Array'].some(n=>p.scope.hasOwnBinding(n)))ok=false;}});
 walk(ast,n=>{if(t.isAssignmentExpression(n)||t.isUpdateExpression(n)||t.isUnaryExpression(n,{operator:'delete'})){
  let root=t.isAssignmentExpression(n)?n.left:n.argument;
  while(t.isMemberExpression(root))root=root.object;
  if(t.isIdentifier(root)&&['Object','Number','Array'].includes(root.name))ok=false;
 }});return ok;
}
function valueExpression(n,params){
 if(t.isStringLiteral(n)||t.isNumericLiteral(n)||t.isBooleanLiteral(n)||t.isNullLiteral(n))return true;
 if(t.isIdentifier(n))return params.has(n.name);
 if(t.isMemberExpression(n)&&!n.computed&&!forbidden.has(n.property.name))return valueExpression(n.object,params);
 if(t.isBinaryExpression(n)||t.isLogicalExpression(n))return valueExpression(n.left,params)&&valueExpression(n.right,params);
 if(t.isConditionalExpression(n))return [n.test,n.consequent,n.alternate].every(x=>valueExpression(x,params));
 if(t.isUnaryExpression(n)&&['!','+','-'].includes(n.operator))return valueExpression(n.argument,params);
 return t.isCallExpression(n)&&!n.optional&&t.isIdentifier(n.callee,{name:'Number'})
  &&n.arguments.length===1&&valueExpression(n.arguments[0],params);
}
function sourceSpec(fn,options,methods){
 if(reservedMethods.has(fn.key.name)||!method(methods,fn.key.name)||fn.body.directives?.length||fn.body.body.length!==1
  ||fn.params.length!==2||fn.params.some(p=>!identifier(p))||fn.params[0].name===fn.params[1].name)return null;
 const statement=fn.body.body[0],call=t.isExpressionStatement(statement)&&statement.expression;
 if(!t.isCallExpression(call)||call.optional||!own(call.callee)||call.arguments.length!==2||!rootName(call.arguments[0]))return null;
 const field=call.arguments[0].value,setter=method(methods,call.callee.property.name),copy=call.arguments[1];
 if(!setter||setter.body.directives?.length||setter.params.length!==2||setter.params.some(p=>!identifier(p))
  ||setter.params[0].name===setter.params[1].name||setter.body.body.length!==1)return null;
 const expectedSetter=parser.parseExpression(`({set(${setter.params.map(p=>p.name).join(',')}){this[${setter.params[0].name}]=${setter.params[1].name};}})`).properties[0];
 if(!same(setter.body,expectedSetter.body)||!literalRecord(options,'data',field)
  ||one(methods,field)||one(one(options,'props')?.value,field)||one(one(options,'computed')?.value,field))return null;
 if(!t.isCallExpression(copy)||copy.optional||!t.isMemberExpression(copy.callee)||copy.callee.computed
  ||!t.isIdentifier(copy.callee.object,{name:'Object'})||!t.isIdentifier(copy.callee.property,{name:'assign'})
  ||copy.arguments.length!==3||!safe(copy.arguments[0])||copy.arguments[0].properties.length
  ||!own(copy.arguments[1],field)||!t.isObjectExpression(copy.arguments[2])||copy.arguments[2].properties.length!==1)return null;
 const property=copy.arguments[2].properties[0];
 if(!t.isObjectProperty(property)||!property.computed||!t.isIdentifier(property.key,{name:fn.params[0].name})
  ||!valueExpression(property.value,new Set(fn.params.map(p=>p.name))))return null;
 const output=t.cloneNode(fn,true),root=t.callExpression(t.memberExpression(t.memberExpression(t.thisExpression(),t.identifier('data')),t.identifier('get')),[t.stringLiteral(field)]);
 const copied=t.cloneNode(copy,true);copied.arguments[1]=root;
 output.body=t.blockStatement([t.expressionStatement(t.callExpression(t.memberExpression(t.memberExpression(t.thisExpression(),t.identifier('data')),t.identifier('set')),[t.stringLiteral(field),copied]))]);
 return {field,value:property.value,key:property.key,node:output};
}
function dataCall(n,name,field){
 return t.isCallExpression(n)&&!n.optional&&t.isMemberExpression(n.callee)&&!n.callee.computed
  &&own(n.callee.object,'data')&&t.isIdentifier(n.callee.property,{name})
  &&n.arguments.length===(name==='get'?1:2)&&t.isStringLiteral(n.arguments[0],{value:field});
}
function exactLegacyClone(binding){
 if(!binding?.constant||!binding.path.isFunctionDeclaration())return false;
 const fn=binding.path.node,body=fn.body.body;
 if(fn.async||fn.generator||fn.params.length!==1||!identifier(fn.params[0])||fn.body.directives?.length||body.length!==5)return false;
 const declaration=body[2],loop=body[3];
 if(!t.isVariableDeclaration(declaration,{kind:'const'})||declaration.declarations.length!==1||!identifier(declaration.declarations[0].id)
  ||!t.isForInStatement(loop)||!t.isVariableDeclaration(loop.left,{kind:'let'})||loop.left.declarations.length!==1||!identifier(loop.left.declarations[0].id))return false;
 const name=fn.id.name,arg=fn.params[0].name,result=declaration.declarations[0].id.name,key=loop.left.declarations[0].id.name;
 if(new Set([name,arg,result,key]).size!==4)return false;
 const expected=parser.parse(`function ${name}(${arg}){
 if(${arg}===null||typeof ${arg}!=='object')return ${arg};
 if(Array.isArray(${arg}))return ${arg}.map(${name});
 const ${result}={};for(let ${key} in ${arg}){if(${arg}.hasOwnProperty(${key})){${result}[${key}]=${name}(${arg}[${key}]);}}
 return ${result};}`).program.body[0];
 return same(fn,expected);
}
function legacyTarget(target,spec,ast){
 if(!target||target.body.directives?.length||target.params.length!==spec.node.params.length
  ||!same(t.arrayExpression(target.params),t.arrayExpression(spec.node.params))||target.body.body.length!==5)return false;
 const [read,value,clone,write,commit]=target.body.body;
 const variable=statement=>t.isVariableDeclaration(statement,{kind:'const'})&&statement.declarations.length===1
  &&identifier(statement.declarations[0].id)?statement.declarations[0]:null;
 const a=variable(read),b=variable(value),c=variable(clone);
 if(!a||!b||!c||new Set([...target.params.map(p=>p.name),a.id.name,b.id.name,c.id.name]).size!==5
  ||!dataCall(a.init,'get',spec.field)||!same(b.init,spec.value)
  ||!t.isCallExpression(c.init)||c.init.optional||!identifier(c.init.callee)||c.init.arguments.length!==1
  ||!t.isIdentifier(c.init.arguments[0],{name:a.id.name}))return false;
 const update=t.isExpressionStatement(write)&&write.expression,last=t.isExpressionStatement(commit)&&commit.expression;
 if(!t.isAssignmentExpression(update,{operator:'='})||!t.isMemberExpression(update.left)||!update.left.computed
  ||!t.isIdentifier(update.left.object,{name:c.id.name})||!same(update.left.property,spec.key)
  ||!t.isIdentifier(update.right,{name:b.id.name})||!dataCall(last,'set',spec.field)
  ||!t.isIdentifier(last.arguments[1],{name:c.id.name}))return false;
 let helper,fnPath;
 traverse(ast,{ObjectMethod(p){if(p.node===target){fnPath=p;p.stop();}}});
 if(!fnPath)return false;
 helper=fnPath.scope.getBinding(c.init.callee.name);
 return exactLegacyClone(helper);
}
module.exports=function sourceRecordUpdates(ctx,src,methods){
 if(!safe(src.object)||!safe(methods)||!safe(ctx.parent)||one(src.object,'mixins')||one(src.object,'extends')
  ||one(ctx.parent,'mixins')||one(ctx.parent,'extends')||one(ctx.parent,'methods')||!globalsSafe(src.ast))return;
 let binding;traverse(ctx.ast,{Program(p){binding=p.scope.getBinding('san');p.stop();}});
 const realSan=binding?.constant&&binding.path.isVariableDeclarator()
  &&t.isCallExpression(binding.path.node.init)&&t.isIdentifier(binding.path.node.init.callee,{name:'require'})
  &&binding.path.node.init.arguments.length===1&&t.isStringLiteral(binding.path.node.init.arguments[0],{value:'san'})
  &&!binding.path.scope.getBinding('require');
 let patched=false;walk(ctx.ast,n=>{if(t.isAssignmentExpression(n)||t.isUpdateExpression(n)){
  let root=t.isAssignmentExpression(n)?n.left:n.argument;while(t.isMemberExpression(root))root=root.object;
  if(t.isIdentifier(root,{name:'san'}))patched=true;
 }});
 const directExport=ctx.ast.program.body.some(s=>t.isExpressionStatement(s)&&t.isAssignmentExpression(s.expression,{operator:'='})
  &&t.isMemberExpression(s.expression.left)&&!s.expression.left.computed
  &&t.isIdentifier(s.expression.left.object,{name:'module'})&&t.isIdentifier(s.expression.left.property,{name:'exports'})
  &&t.isCallExpression(s.expression.right)&&s.expression.right.arguments[0]===ctx.parent);
 const targetSafe=realSan&&directExport&&!patched&&globalsSafe(ctx.ast);
 for(const fn of methods.properties){
  const spec=sourceSpec(fn,src.object,methods);if(!spec)continue;
  const name=fn.key.name,target=method(ctx.parent,name),fieldSafe=!one(one(ctx.parent,'computed')?.value,spec.field);
  const landed=targetSafe&&fieldSafe&&!!target&&same(target,spec.node);
  const eligible=targetSafe&&fieldSafe&&literalRecord(ctx.parent,'initData',spec.field)&&legacyTarget(target,spec,ctx.ast);
  ctx.record_update_contracts.push({name,field:spec.field,contract:`script.methods.${name}@${spec.field}`,landed,
   repair_eligible:!!eligible,proof:'literal_root_source_shallow_record_assignment_with_exact_setter_and_value'});
  if(landed)continue;
  ctx.findings.push({code:'source_record_update_not_landed',location:`script.methods.${name}@${spec.field}`,
   message:'Preserve the source shallow Object.assign copy, computed record key, value evaluation and one literal-root data.set commit; deep/unknown clones are not equivalent proof.'});
  if(ctx.input.repair&&eligible){ctx.edit(ctx.offset+target.start,ctx.offset+target.end,print(spec.node));
   ctx.changes.push('restored_source_literal_record_update');}
 }
};
