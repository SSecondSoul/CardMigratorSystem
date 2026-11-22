// Parser-only evidence extraction. Never executes uploaded/generated JS.
const fs=require('fs'),path=require('path'),{createRequire}=require('module');
const req=createRequire(path.join(process.cwd(),'migration_system/engine/package.json'));
const parser=req('@babel/parser'),traverse=req('@babel/traverse').default,generate=req('@babel/generator').default;
const {parse}=req('@vue/compiler-sfc');
const key=n=>n&&!n.computed&&(n.key?.name??n.key?.value);
function inspect(text,setter,side){
  const descriptor=parse(text).descriptor;
  if(!descriptor.script)return {error:'no_script'};
  let ast;try{ast=parser.parse(descriptor.script.content,{sourceType:'unambiguous'})}catch(e){return {error:'script_syntax_error',message:e.message}};
  const calls=[],owners=new Map();
  traverse(ast,{CallExpression(p){
    const n=p.node,c=n.callee;
    const helper=c.type==='MemberExpression'&&!c.computed&&c.object.type==='ThisExpression'&&c.property.name===setter;
    const store=c.type==='MemberExpression'&&!c.computed&&c.property.name==='set'&&c.object.type==='MemberExpression'
      &&!c.object.computed&&c.object.property.name==='data'&&c.object.object.type==='ThisExpression';
    if(!helper&&!store)return;
    let owner=p.getFunctionParent();while(owner?.isArrowFunctionExpression())owner=owner.getFunctionParent();
    const prop=owner?.isObjectMethod()?owner:owner?.parentPath?.isObjectProperty()?owner.parentPath:null;
    const container=prop?.parentPath;
    const containerProperty=container?.parentPath?.isObjectProperty()?key(container.parentPath.node):null;
    const ownerKey=prop&&key(prop.node);
    const origin={method:ownerKey||null,container:containerProperty||'root_or_unknown',
      syntax:owner?.node.type||null,owner_line:owner?.node.loc?.start.line||null};
    calls.push({...origin,kind:helper?'helper_call':'direct_data_set',line:n.loc?.start.line,
      key:n.arguments[0]?.type==='StringLiteral'?n.arguments[0].value:null,
      code:generate(n,{compact:true,comments:false}).code});
    if(owner?.node&&prop)owners.set(JSON.stringify(origin),{...origin,
      body:generate(owner.node,{comments:false}).code});
  }});
  return {side,calls,owners:[...owners.values()]};
}
const input=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(input.map(row=>({component:row.component,
  source:inspect(row.source,row.setter,'source'),target:inspect(row.code,row.setter,'target')}))));
