// Exact source created -> parent inited projection. No dynamic setter adapter,
// recursive cloning, lifecycle relocation or child initialization rewrite.
const parser=require('@babel/parser'),t=require('@babel/types'),traverse=require('@babel/traverse').default;
const {one,safe,method,arrayPath,same,print,walk}=require('./source_render_call_semantics.cjs');
const own=(n)=>t.isMemberExpression(n)&&!n.computed&&t.isThisExpression(n.object);
const nameOK=s=>typeof s==='string'&&/^[A-Za-z][\w$]*$/.test(s)
 &&!['data','fire','watch','initData','inited','attached','constructor','prototype','__proto__'].includes(s);
const parseMethod=s=>parser.parseExpression('({'+s+'})').properties[0];
function dataObject(o,name){const m=method(o,name);return m&&!m.params.length&&m.body.body.length===1
 &&t.isReturnStatement(m.body.body[0])&&safe(m.body.body[0].argument)?m.body.body[0].argument:null;}
function binding(ast,node,name){let b;traverse(ast,{ObjectMethod(p){if(p.node===node){b=p.scope.getBinding(name);p.stop();}}});return b;}
function helper(ast,node,name,kind){const b=binding(ast,node,name);
 if(!b?.constant||!b.path.isFunctionDeclaration()||!b.path.parentPath.isProgram())return false;
 const f=b.path.node,p=f.params,body=f.body.body;if(p.some(x=>!t.isIdentifier(x))||f.async||f.generator)return false;
 let text;
 if(kind==='map'&&p.length===2&&body.length===3){
  const r=body[0]?.declarations?.[0]?.id?.name,i=body[1]?.init?.declarations?.[0]?.id?.name;if(!r||!i)return false;
  text=`function ${name}(${p[0].name},${p[1].name}){const ${r}=[];for(let ${i}=0;${i}<${p[0].name}.length;${i}++){${r}.push(${p[1].name}(${p[0].name}[${i}],${i},${p[0].name}));}return ${r};}`;
 }else if(kind==='clone'&&p.length===1&&body.length===5){
  const a=p[0].name,r=body[2]?.declarations?.[0]?.id?.name,k=body[3]?.left?.declarations?.[0]?.id?.name;if(!r||!k)return false;
  text=`function ${name}(${a}){if(${a}===null||typeof ${a}!=='object')return ${a};if(Array.isArray(${a}))return ${a}.map(${name});const ${r}={};for(let ${k} in ${a}){if(${a}.hasOwnProperty(${k})){${r}[${k}]=${name}(${a}[${k}]);}}return ${r};}`;
 }else return false;
 return same(f,parser.parse(text).program.body[0]);
}
function specification(src,methods){
 const hook=method(src.object,'created');if(!hook||hook.params.length||hook.body.body.length!==2||hook.body.directives?.length)return null;
 const [s1,s2]=hook.body.body,first=t.isExpressionStatement(s1)&&s1.expression,second=t.isExpressionStatement(s2)&&s2.expression;
 if(!t.isCallExpression(first)||!own(first.callee)||first.arguments.length!==2||!t.isStringLiteral(first.arguments[0])
  ||!t.isCallExpression(second)||!own(second.callee)||second.arguments.length!==2||!t.isStringLiteral(second.arguments[0]))return null;
 const setter=method(methods,first.callee.property.name);
 if(!setter||setter.params.length!==2||setter.params.some(p=>!t.isIdentifier(p))||!same(first.callee,second.callee))return null;
 const [k,v]=setter.params.map(p=>p.name);if(k===v||!same(setter,parseMethod(`${setter.key.name}(${k},${v}){this[${k}]=${v};}`)))return null;
 const map=first.arguments[1],choice=second.arguments[1];
 if(!t.isCallExpression(map)||!t.isMemberExpression(map.callee)||map.callee.computed||!own(map.callee.object)
  ||!t.isArrowFunctionExpression(map.arguments[0])||map.arguments[0].params.length!==1||!t.isIdentifier(map.arguments[0].params[0])
  ||!t.isConditionalExpression(choice)||!t.isMemberExpression(choice.test)||!own(choice.test.object)
  ||!t.isMemberExpression(choice.consequent)||choice.consequent.computed||!t.isIdentifier(choice.consequent.property))return null;
 const root=first.arguments[0].value,selected=second.arguments[0].value,prop=map.callee.object.property.name,
  days=choice.test.object.property.name,id=choice.consequent.property.name,item=map.arguments[0].params[0].name;
 if(![root,selected,prop,days,id,item].every(nameOK)||new Set([root,selected,prop,days]).size!==4)return null;
 const expected=parseMethod(`created(){this.${setter.key.name}('${root}',this.${prop}.map(${item}=>Object.assign({},${item})));this.${setter.key.name}('${selected}',this.${days}[0]?this.${days}[0].${id}:'');}`);
 if(!same(hook,expected)||!arrayPath(src.object,[prop])||!arrayPath(src.object,[days]))return null;
 const data=dataObject(src.object,'data'),props=one(src.object,'props')?.value,computed=one(src.object,'computed')?.value;
 if(!data||!safe(props)||!t.isArrayExpression(one(data,root)?.value)||!t.isStringLiteral(one(data,selected)?.value)
  ||[root,selected].some(n=>one(props,n))||[prop,days].some(n=>one(data,n))
  ||[root,selected,prop,days].some(n=>one(methods,n)||one(computed,n)))return null;
 const output=parseMethod(`inited(){this.data.set('${root}',this.data.get('${prop}').map(${item}=>Object.assign({},${item})));this.data.set('${selected}',this.data.get('${days}')[0]?this.data.get('${days}')[0].${id}:'');}`);
 return {root,selected,prop,days,id,output,data};
}
module.exports=function parentInitialization(ctx,src,methods){
 if(!safe(src.object)||!safe(methods)||!safe(ctx.parent)||one(src.object,'mixins')||one(src.object,'extends')
  ||one(src.object,'watch')||one(src.object,'beforeCreate')||one(ctx.parent,'mixins')||one(ctx.parent,'extends')
  ||one(ctx.parent,'methods')||one(ctx.parent,'data')||one(ctx.parent,'watch'))return;
 const spec=specification(src,methods);if(!spec)return;
 let unsafe=false;
 for(const ast of [src.ast,ctx.ast]){
  traverse(ast,{Scope(p){if(['Object','Array'].some(n=>p.scope.hasOwnBinding(n)))unsafe=true;}});
  walk(ast,n=>{if(t.isAssignmentExpression(n)||t.isUpdateExpression(n)||t.isUnaryExpression(n,{operator:'delete'})){
   let root=t.isAssignmentExpression(n)?n.left:n.argument;while(t.isMemberExpression(root))root=root.object;
   if(t.isIdentifier(root)&&['Object','Array','san'].includes(root.name))unsafe=true;
  }
  if(t.isCallExpression(n)&&own(n.callee)&&n.callee.property.name==='watch')unsafe=true;
  });
 }
 let runtime;traverse(ctx.ast,{Program(p){runtime=p.scope.getBinding('san');p.stop();}});
 const direct=ctx.ast.program.body.some(s=>t.isExpressionStatement(s)&&t.isAssignmentExpression(s.expression,{operator:'='})
  &&same(s.expression.left,parser.parseExpression('module.exports'))&&t.isCallExpression(s.expression.right)
  &&same(s.expression.right.callee,parser.parseExpression('san.defineComponent'))&&s.expression.right.arguments.length===1
  &&s.expression.right.arguments[0]===ctx.parent);
 if(unsafe||!direct||!runtime?.constant||!runtime.path.isVariableDeclarator()
  ||!same(runtime.path.node.init,parser.parseExpression("require('san')"))||runtime.path.scope.getBinding('require'))return;
 const target=method(ctx.parent,'inited'),data=dataObject(ctx.parent,'initData'),computed=one(ctx.parent,'computed')?.value;
 const fields=!!data&&[spec.root,spec.selected].every(n=>!!one(data,n)&&same(one(data,n).value,one(spec.data,n).value))
  &&[spec.prop,spec.days].every(n=>!!one(data,n)&&t.isArrayExpression(one(data,n).value))
  &&[spec.root,spec.selected,spec.prop,spec.days].every(n=>!one(computed,n)&&!one(ctx.parent,n));
 const landed=fields&&!!target&&same(target,spec.output);
 let eligible=false;
 if(fields&&target&&!target.params.length&&target.body.body.length===6){
  const b=target.body.body,ds=[0,1,3,4].map(i=>b[i]?.declarations?.[0]);
  if(ds.every(d=>t.isIdentifier(d?.id))){
   const [p,r,d,s]=ds.map(d=>d.id.name),map=ds[1].init,cb=map?.arguments?.[1];
   if(new Set([p,r,d,s]).size===4&&t.isCallExpression(map)&&t.isIdentifier(map.callee)&&t.isArrowFunctionExpression(cb)
    &&cb.params.length===1&&t.isIdentifier(cb.params[0])&&t.isCallExpression(cb.body)&&t.isIdentifier(cb.body.callee)){
    const m=map.callee.name,c=cb.body.callee.name,i=cb.params[0].name;
    const expected=parseMethod(`inited(){const ${p}=this.data.get('${spec.prop}');const ${r}=${m}(${p},${i}=>${c}(${i}));this.data.set('${spec.root}',${r});const ${d}=this.data.get('${spec.days}');const ${s}=${d}.length>0?${d}[0].${spec.id}:'';this.data.set('${spec.selected}',${s});}`);
    eligible=same(target,expected)&&helper(ctx.ast,target,m,'map')&&helper(ctx.ast,target,c,'clone');
   }
  }
 }
 const contract=`script.created@${spec.root}:${spec.prop}`;
 ctx.parent_initialization_contracts.push({contract,field:spec.root,prop:spec.prop,phase:'inited',landed,repair_eligible:eligible,
  proof:'exact_source_shallow_record_map_then_first_element_guard',nested_reference_policy:'shared',dynamic_setter_restored:false});
 if(landed)return;
 ctx.findings.push({code:'source_parent_initialization_not_landed',location:contract,
  message:'Preserve source native map and shallow Object.assign record initialization, nested references and first-element guard in the original ordered startup phase; recursive clone is not equivalent.'});
 if(ctx.input.repair&&eligible){ctx.edit(ctx.offset+target.start,ctx.offset+target.end,print(spec.output));ctx.changes.push('restored_source_parent_shallow_initialization');}
};
