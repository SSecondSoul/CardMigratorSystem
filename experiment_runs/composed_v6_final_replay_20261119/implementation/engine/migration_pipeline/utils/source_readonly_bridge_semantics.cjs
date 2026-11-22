// Static recognition only: these legacy loops are NOT native-equivalence proofs.
// They authorize a source-derived private render copy, never public-method edits.
const parser=require('@babel/parser'),t=require('@babel/types'),traverse=require('@babel/traverse').default;
const {print}=require('./source_render_call_semantics.cjs');
const patterns={
 filter:'function(a,p){const r=[];for(let i=0;i<a.length;i++){if(p(a[i],i,a)){r.push(a[i]);}}return r;}',
 indexOf:'function(a,v){for(let i=0;i<a.length;i++){if(a[i]===v){return i;}}return -1;}'
};
function tree(fn){return t.file(t.program([t.expressionStatement(t.functionExpression(null,
 fn.params.map(p=>t.cloneNode(p,true)),t.cloneNode(fn.body,true)))]));}
function alpha(fn){
 const ast=tree(fn);let index=0,valid=true;
 traverse(ast,{Identifier(p){if(p.node.name.startsWith('__closedBridge'))valid=false;}});
 if(!valid)return null;
 const bindings=[];
 traverse(ast,{BindingIdentifier(p){const b=p.scope.getBinding(p.node.name);if(b&&!bindings.includes(b))bindings.push(b);}});
 for(const b of bindings)b.scope.rename(b.identifier.name,'__closedBridge'+index++);
 return print(ast.program.body[0].expression);
}
const shapes=new Map(Object.entries(patterns).map(([name,text])=>[name,alpha(parser.parseExpression(text))]));
function expandBridges(method,program){
 const ast=t.file(t.program([t.expressionStatement(t.objectExpression([t.cloneNode(method,true)]))]));
 let root;traverse(ast,{ObjectMethod(p){root=p;p.stop();}});
 let top;traverse(program,{Program(p){top=p;p.stop();}});
 const corrections=new Set(),active=new Set();
 function definition(name){
  const b=top.scope.getBinding(name),p=b?.path;
  if(!b?.constant||!p?.isFunctionDeclaration()||!p.parentPath.isProgram()
   ||p.node.async||p.node.generator||p.node.params.some(x=>!t.isIdentifier(x))
   ||new Set(p.node.params.map(x=>x.name)).size!==p.node.params.length
   ||b.referencePaths.some(r=>!r.parentPath.isCallExpression()||r.parentPath.node.callee!==r.node))return null;
  return p.node;
 }
 function expand(path){
  if(!path.isCallExpression()||!t.isIdentifier(path.node.callee)||path.scope.getBinding(path.node.callee.name))return;
  const name=path.node.callee.name,fn=definition(name);if(!fn)return;
  if(active.has(name))throw Error('recursive_external_render_bridge');
  const args=path.node.arguments;
  if(args.length!==fn.params.length)return;
  const primitive=[...shapes].find(([_,shape])=>shape===alpha(fn))?.[0];
  if(primitive){
   if(!t.isIdentifier(args[0])||!t.isIdentifier(args[1])
    &&!(primitive==='filter'&&t.isArrowFunctionExpression(args[1])&&!args[1].async))return;
   corrections.add(primitive);
   path.replaceWith(t.callExpression(t.memberExpression(t.cloneNode(args[0]),t.identifier(primitive)),args.slice(1).map(a=>t.cloneNode(a))));
   path.skip();return;
  }
  if(args.some(a=>!t.isIdentifier(a)))return;
  if(fn.body.body.length!==1||!t.isReturnStatement(fn.body.body[0])||!fn.body.body[0].argument)return;
  // Parameter-only actuals preserve order/number of observable argument evaluations.
  const copy=tree(fn);let f;traverse(copy,{FunctionExpression(p){f=p;p.stop();}});
  let unsafe=false;f.traverse({ThisExpression(){unsafe=true;},Identifier(p){if(p.node.name.startsWith('__closedBridge'))unsafe=true;}});
  if(unsafe)return;
  for(let i=0;i<fn.params.length;i++){
   const binding=f.scope.getBinding(fn.params[i].name);
   if(!binding?.constant)return;
   for(const ref of binding.referencePaths){
    if(ref.scope.getBinding(args[i].name)&&ref.scope.getBinding(args[i].name)!==binding)return;
   }
  }
  // Alpha-rename parameters first to avoid capture by another parameter.
  fn.params.forEach((p,i)=>f.scope.rename(p.name,'__closedBridgeArg'+i));
  for(let i=0;i<args.length;i++){
   const binding=f.scope.getBinding('__closedBridgeArg'+i);
   for(const ref of binding.referencePaths)ref.replaceWith(t.cloneNode(args[i]));
  }
  const value=f.node.body.body[0].argument;
  // Remaining free helpers must resolve in the original top-level scope.
  active.add(name);path.replaceWith(value);path.traverse({CallExpression:expand});expand(path);active.delete(name);
 }
 // A sole tail-forwarder can expose a complete readonly helper body (including
 // early returns). Matching the source graph and readonly checking still follow.
 // This is never a general statement inliner or a public-method rewrite.
 const tailSeen=new Set();
 while(root.node.body.body.length===1&&t.isReturnStatement(root.node.body.body[0])){
  const call=root.node.body.body[0].argument;
  if(!t.isCallExpression(call)||!t.isIdentifier(call.callee)||root.scope.getBinding(call.callee.name))break;
  const fn=definition(call.callee.name),args=call.arguments;
  if(!fn||fn.body.body.length<=1||args.length!==fn.params.length||args.some(a=>!t.isIdentifier(a)))break;
  if([...shapes.values()].includes(alpha(fn)))break;
  if(tailSeen.has(call.callee.name))throw Error('recursive_external_render_bridge');tailSeen.add(call.callee.name);
  const copy=tree(fn);let f,unsafe=false;traverse(copy,{FunctionExpression(p){f=p;p.stop();}});
  f.traverse({ThisExpression(){unsafe=true;},Identifier(p){if(p.node.name.startsWith('__closedBridge'))unsafe=true;}});
  for(let i=0;i<args.length;i++){
   const b=f.scope.getBinding(fn.params[i].name);
   if(!b?.constant||b.referencePaths.some(r=>r.scope.getBinding(args[i].name)&&r.scope.getBinding(args[i].name)!==b))unsafe=true;
  }
  if(unsafe)break;
  fn.params.forEach((p,i)=>f.scope.rename(p.name,'__closedBridgeArg'+i));
  for(let i=0;i<args.length;i++)for(const ref of f.scope.getBinding('__closedBridgeArg'+i).referencePaths)ref.replaceWith(t.cloneNode(args[i]));
  root.node.body=t.cloneNode(f.node.body,true);root.scope.crawl();
 }
 root.traverse({CallExpression:expand});
 return {node:root.node,corrections:[...corrections].sort()};
}
module.exports={expandBridges};
