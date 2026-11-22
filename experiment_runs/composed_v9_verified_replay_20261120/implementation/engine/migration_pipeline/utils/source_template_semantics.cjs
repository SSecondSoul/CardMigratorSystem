// No component-name exceptions. Require matching DOM element paths, loop /
// conditional scopes and complete source binding expressions for every edit.
const fs=require('fs'), parser=require('@babel/parser'), t=require('@babel/types');
const traverse=require('@babel/traverse').default, generate=require('@babel/generator').default;
const dom=require('@vue/compiler-dom'), {parse:parseSFC}=require('@vue/compiler-sfc');
const key=p=>!p.computed&&(p.key?.name||p.key?.value);
const one=(o,k)=>o?.properties?.filter(p=>key(p)===k).length===1?o.properties.find(p=>key(p)===k):null;
const ident=s=>typeof s==='string'&&/^[A-Za-z_$][\w$]*$/.test(s)&&!['__proto__','constructor','prototype'].includes(s);
const entity=s=>/&(?:#\d+|#x[\da-f]+|[a-z]+);/i.test(s);
function clean(n){
  if(Array.isArray(n))return n.map(clean);
  if(!n||typeof n!=='object')return n;
  return Object.fromEntries(Object.keys(n).sort().filter(k=>!['start','end','loc','extra','comments','errors','tokens','leadingComments',
    'trailingComments','innerComments'].includes(k)).map(k=>[k,clean(n[k])]));
}
const same=(a,b)=>JSON.stringify(clean(a))===JSON.stringify(clean(b));
function walk(n,fn){if(!n||typeof n!=='object')return;if(Array.isArray(n)){n.forEach(x=>walk(x,fn));return;}
 fn(n);for(const[k,v]of Object.entries(n))if(!['loc','extra','comments'].includes(k))walk(v,fn);}
const getCall=n=>t.isCallExpression(n)&&!n.optional&&t.isMemberExpression(n.callee)&&!n.callee.computed
 &&t.isIdentifier(n.callee.property,{name:'get'})&&t.isMemberExpression(n.callee.object)
 &&!n.callee.object.computed&&t.isThisExpression(n.callee.object.object)
 &&t.isIdentifier(n.callee.object.property,{name:'data'});
function parseScript(script){return parser.parse(script,{sourceType:'unambiguous'});}
function parent(ast,vue){
 const found=[];
 traverse(ast,{
  ExportDefaultDeclaration(p){if(vue&&p.parentPath.isProgram())found.push(p.node.declaration);},
  AssignmentExpression(p){const n=p.node;
   if(!t.isMemberExpression(n.left)||n.left.computed||n.left.object.name!=='module'
      ||n.left.property.name!=='exports'||n.operator!=='='||!p.parentPath.parentPath?.isProgram())return;
   if(vue)found.push(n.right);
   else if(t.isCallExpression(n.right)&&t.isMemberExpression(n.right.callee)&&!n.right.callee.computed
     &&n.right.callee.object.name==='san'&&n.right.callee.property.name==='defineComponent'
     &&n.right.arguments.length===1)found.push(n.right.arguments[0]);
  }});
 if(found.length!==1||!t.isObjectExpression(found[0])||found[0].properties.some(p=>!key(p))
   ||new Set(found[0].properties.map(key)).size!==found[0].properties.length)return null;
 return found[0];
}
function names(o,vue){
 const result=new Set();if(!o)return result;
 for(const name of ['computed',vue?'props':'dataTypes']){
  const obj=one(o,name)?.value;if(t.isObjectExpression(obj))obj.properties.forEach(p=>{if(ident(key(p)))result.add(key(p));});
 }
 const fn=one(o,vue?'data':'initData');
 if(t.isObjectMethod(fn))for(const s of fn.body.body)if(t.isReturnStatement(s)&&t.isObjectExpression(s.argument))
  s.argument.properties.forEach(p=>{if(ident(key(p)))result.add(key(p));});
 return result;
}
function truthyStrings(o){
 const result=new Map(),computed=one(o,'computed')?.value;
 if(!t.isObjectExpression(computed))return result;
 const leaves=n=>t.isStringLiteral(n)&&n.value.length?new Set([n.value]):t.isConditionalExpression(n)?combine(leaves(n.consequent),leaves(n.alternate)):null;
 const combine=(a,b)=>a&&b?new Set([...a,...b]):null;
 for(const fn of computed.properties){
  if(!t.isObjectMethod(fn)||fn.async||fn.generator||fn.params.length)continue;
  const body=fn.body.body,last=body.at(-1);
  if(!t.isReturnStatement(last)||!body.slice(0,-1).every(s=>t.isVariableDeclaration(s,{kind:'const'})))continue;
  let unsafe=false;
  walk(body,n=>{if(t.isFunction(n)||t.isAssignmentExpression(n)||t.isUpdateExpression(n)||t.isNewExpression(n)
    ||t.isAwaitExpression(n)||t.isYieldExpression(n)||t.isThrowStatement(n)
    ||(t.isCallExpression(n)&&!getCall(n)))unsafe=true;});
  const values=leaves(last.argument);
  if(!unsafe&&values)result.set(key(fn),[...values].sort());
 }
 return result;
}
function parseTemplate(text){
 const errors=[],ast=dom.parse(text,{onError:e=>errors.push(e)});
 return {ast,errors,text};
}
function directive(n,name){const ps=n.props.filter(p=>p.type===7&&p.name===name);return ps.length===1?ps[0]:null;}
function attribute(n,name){const ps=n.props.filter(p=>p.type===6&&p.name===name);return ps.length===1?ps[0]:null;}
function binding(n,name){const ps=n.props.filter(p=>p.type===7&&p.name==='bind'&&p.arg?.isStatic&&p.arg.content===name&&!p.modifiers.length);return ps.length===1?ps[0].exp?.content:null;}
function loop(value){
 if(value==null)return {aliases:[],signature:''};
 const m=/^\s*\(?\s*([\w$]+)(?:\s*,\s*([\w$]+))?\s*\)?\s+in\s+([\w$.]+)(?:\s+trackby\s+[\w$.]+)?\s*$/.exec(value);
 return m?{aliases:[m[1],m[2]].filter(Boolean),signature:[m[1],m[2]||'',m[3]].join(':')}:null;
}
function scope(n,vue){
 const forProp=vue?directive(n,'for'):attribute(n,'s-for');
 const forValue=vue?forProp?.exp?.content:forProp?.value?.content;
 if(forProp&&!forValue)return null;
 const l=loop(forValue);if(!l)return null;
 const conditions=[];
 for(const name of ['if','else-if','else']){
  const p=vue?directive(n,name):attribute(n,'s-'+name);
  if(p){const text=vue?p.exp?.content:p.value?.content;
   if(name!=='else'&&!text)return null;
   try{conditions.push([name,text?clean(parser.parseExpression(text)):null]);}catch(_){return null;}}
 }
 return {...l,signature:l.signature+JSON.stringify(conditions)};
}
function structure(a,b){const aa=a.children?.filter(n=>n.type===1)||[],bb=b.children?.filter(n=>n.type===1)||[];
 return aa.length===bb.length&&aa.every((n,i)=>n.tag===bb[i].tag&&structure(n,bb[i]));}
function quoted(p,text){
 const raw=p.value?.loc.source;
 if(!raw||!['"',"'"].includes(raw[0])||raw.at(-1)!==raw[0]||entity(raw))return null;
 const start=p.value.loc.start.offset+1;
 if(text.slice(start,start+raw.length-2)!==raw.slice(1,-1))return null;
 return {text:raw.slice(1,-1),start,quote:raw[0]};
}
function interpolation(text,allowMissing=false){
 let missing=false,inner;
 if(/^\s*\{\{[\s\S]*\}\}\s*$/.test(text))inner=text.trim().slice(2,-2);
 else if(allowMissing&&/^\s*\{\{[\s\S]*[^}]\}\s*$/.test(text)){inner=text.trim().slice(2,-1);missing=true;}
 else return null;
 if(inner.includes('{{')||inner.includes('}}')||inner.includes('{=')||entity(inner))return null;
 try{return {node:parser.parseExpression(inner.trim()),missing};}catch(_){return null;}
}
function classExpression(expr){
 const n=parser.parseExpression(expr);
 if(!t.isObjectExpression(n))return n;
 if(n.properties.length!==1)return null;
 const p=n.properties[0],name=key(p);
 if(!t.isObjectProperty(p)||!/^[A-Za-z_][\w-]*$/.test(name||'')||p.method)return null;
 return t.conditionalExpression(t.cloneNode(p.value,true),t.stringLiteral(name),t.stringLiteral(''));
}
function run(input){
 const code=input.code,outer=/<template\b[^>]*>([\s\S]*?)<\/template\s*>/i.exec(code);
 const script=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code),templates=[];
 const ast=script?parseScript(script[1]):null,options=ast&&parent(ast,false);
 if(outer)templates.push({text:outer[1],offset:outer.index+outer[0].indexOf('>')+1,scope:'template',outer:true});
 if(ast)traverse(ast,{CallExpression(p){const n=p.node;
  if(!t.isMemberExpression(n.callee)||n.callee.computed||n.callee.object.name!=='san'
    ||n.callee.property.name!=='defineComponent'||!t.isObjectExpression(n.arguments[0]))return;
  const template=one(n.arguments[0],'template')?.value;
  const text=t.isStringLiteral(template)?template.value:t.isTemplateLiteral(template)&&!template.expressions.length
    ?template.quasis[0].value.cooked:null;
  if(typeof text==='string')
   templates.push({text,offset:0,
    scope:'script.'+(p.parentPath.isVariableDeclarator()?p.parentPath.node.id.name:'parent')+'.template'});
 }});
 const findings=[],edits=[],changes=[],proofs=[];
 // Report real render AST calls, never occurrences in comments / JS examples.
 function inspect(expression,location){
  let node;try{node=parser.parseExpression(expression);}catch(_){return;}
  const fields=[];walk(node,n=>{if(getCall(n))fields.push(n.arguments.length===1&&t.isStringLiteral(n.arguments[0])?n.arguments[0].value:'<dynamic>');});
  if(fields.length)findings.push({code:'invalid_san_template_data_store_access',location,
   message:'San render expression calls the script Data-store API; bind fields directly: '+[...new Set(fields)].sort().join(', ')+'.'});
 }
 for(const template of templates){
  const parsed=parseTemplate(template.text);
  function visit(n,path){
   if(n.type===1){
    for(const p of n.props)if(p.type===6&&p.value&&!p.name.startsWith('on-')){
     const v=quoted(p,template.text);if(!v)continue;
     if(['s-if','s-else-if'].includes(p.name))inspect(v.text,template.scope+path+'@'+p.name);
     else for(const m of v.text.matchAll(/\{\{([\s\S]*?)\}\}/g))inspect(m[1],template.scope+path+'@'+p.name);
    }
   }
   const counts={};let textIndex=0;for(const c of n.children||[]){
    if(c.type===5)inspect(c.content.content,template.scope+path+'#text'+textIndex++);
    if(c.type===1){const i=counts[c.tag]||0;counts[c.tag]=i+1;visit(c,path+'/'+c.tag+'['+i+']');}
   }
  }
  visit(parsed.ast,'');
 }
 if(!input.vue||!outer||!options)return {code,findings,changes,proofs};
 const {descriptor,errors}=parseSFC(input.vue);
 if(errors.length||!descriptor.template||!descriptor.script||descriptor.scriptSetup)return {code,findings,changes,proofs};
 const srcOptions=parent(parseScript(descriptor.script.content),true);
 if(!srcOptions||one(srcOptions,'mixins')||one(srcOptions,'extends'))return {code,findings,changes,proofs};
 const source=parseTemplate(descriptor.template.content),target=parseTemplate(outer[1]);
 if(source.errors.length||target.errors.some(e=>e.code!==dom.ErrorCodes.DUPLICATE_ATTRIBUTE)
   ||!structure(source.ast,target.ast))return {code,findings,changes,proofs};
 const sourceNames=names(srcOptions,true),targetNames=names(options,false),truth=new Set();
 const a=truthyStrings(srcOptions),b=truthyStrings(options);
 for(const[name,values]of a)if(JSON.stringify(values)===JSON.stringify(b.get(name)))truth.add(name);
 const outerOffset=outer.index+outer[0].indexOf('>')+1;
 function rewrite(node,expected,aliases){
  const clone=t.cloneNode(node,true);let count=0,unsafe=false;
  function transform(n){
   if(!n||typeof n!=='object')return n;
   if(Array.isArray(n))return n.map(transform);
   if(t.isFunction(n)||t.isAssignmentExpression(n)||t.isUpdateExpression(n)||t.isNewExpression(n)
     ||t.isAwaitExpression(n)||t.isYieldExpression(n))unsafe=true;
   if(getCall(n)){
    const field=n.arguments.length===1&&t.isStringLiteral(n.arguments[0])&&n.arguments[0].value;
    if(!ident(field)||!sourceNames.has(field)||!targetNames.has(field)||aliases.includes(field)){unsafe=true;return n;}
    count++;return t.identifier(field);
   }
   for(const[k,v]of Object.entries(n))if(v&&typeof v==='object'&&!['loc','extra','comments'].includes(k))n[k]=transform(v);
   if(t.isLogicalExpression(n,{operator:'||'})&&t.isIdentifier(n.left)&&truth.has(n.left.name)&&t.isStringLiteral(n.right,{value:''}))return n.left;
   return n;
  }
  const fixed=transform(clone);
  return !unsafe&&same(fixed,expected)?{node:fixed,count,text:generate(fixed,{compact:true,comments:false}).code}:null;
 }
 function add(start,end,text,rule,path){edits.push({start:outerOffset+start,end:outerOffset+end,text});
  changes.push(rule);proofs.push({rule,path,source_expression_matched:true});}
 function pair(s,n,path,aliases,valid){
  const ss=scope(s,true),ns=scope(n,false);
  valid=valid&&!!ss&&!!ns&&ss.signature===ns.signature;
  const local=[...aliases,...(ns?.aliases||[])];
  if(valid){
   const classes=n.props.filter(p=>p.type===6&&p.name==='class');
   const srcStatic=attribute(s,'class')?.value?.content||'',srcDynamic=binding(s,'class');
   if(srcDynamic&&classes.length<=2){
    try{
     const expected=classExpression(srcDynamic),staticProps=classes.filter(p=>!p.value?.content.includes('{{')),
       dynamicProps=classes.filter(p=>p.value?.content.includes('{{'));
     if(expected&&dynamicProps.length===1&&staticProps.length===(classes.length===2?1:0)){
      const dp=dynamicProps[0],dv=quoted(dp,target.text),sp=staticProps[0],sv=sp&&quoted(sp,target.text),parsed=dv&&interpolation(dv.text,true);
      const fixed=parsed&&rewrite(parsed.node,expected,local);
      if(fixed&&(!sp||sv)&&srcStatic.trim()===(sv?.text||'').trim()){
       if(sp&&!fixed.text.includes(sv.quote)){
        add(sp.loc.start.offset,sp.loc.end.offset,`class=${sv.quote}${sv.text} {{${fixed.text}}}${sv.quote}`,'merged_source_class_bindings',path);
        add(dp.loc.start.offset,dp.loc.end.offset,'','merged_source_class_bindings',path);
        if(parsed.missing)changes.push('restored_source_class_interpolation_delimiter');
       }else if(!sp&&(parsed.missing||fixed.count)&&!fixed.text.includes(dv.quote))
        add(dv.start,dv.start+dv.text.length,`{{${fixed.text}}}`,parsed.missing?'restored_source_class_interpolation_delimiter':'restored_source_render_field_bindings',path);
      }
     }
    }catch(_){/* Source class map / target expression outside the narrow proof subset. */}
   }
   for(const p of n.props){
    if(p.type!==6||!p.value||p.name.startsWith('on-'))continue;
    if(p.name==='class'&&classes.length!==1)continue;
    const value=quoted(p,target.text),parsed=value&&interpolation(value.text);
    const exp=p.name==='s-if'?directive(s,'if')?.exp?.content:p.name==='s-else-if'?directive(s,'else-if')?.exp?.content:binding(s,p.name);
    if(!value||!exp)continue;
    try{
     const direct=['s-if','s-else-if'].includes(p.name),node=direct?parser.parseExpression(value.text):parsed?.node;
     if(!node)continue;
     const expected=p.name==='class'?classExpression(exp):parser.parseExpression(exp),fixed=expected&&rewrite(node,expected,local);
     if(fixed?.count&&!fixed.text.includes(value.quote)&&!edits.some(e=>e.start<=outerOffset+value.start&&e.end>=outerOffset+value.start))
      add(value.start,value.start+value.text.length,direct?fixed.text:`{{${fixed.text}}}`,'restored_source_render_field_bindings',path+'@'+p.name);
    }catch(_){/* Not source-equivalent: preserve it for explicit repair. */}
   }
   const sourceText=s.children.filter(c=>c.type===5),targetText=n.children.filter(c=>c.type===5);
   if(sourceText.length===targetText.length)targetText.forEach((c,i)=>{
    try{
     const parsed=interpolation(c.loc.source),expected=parser.parseExpression(sourceText[i].content.content),fixed=parsed&&rewrite(parsed.node,expected,local);
     if(fixed?.count)add(c.loc.start.offset,c.loc.end.offset,`{{${fixed.text}}}`,'restored_source_render_field_bindings',path+'#text'+i);
    }catch(_){}
   });
  }
  const sc=s.children.filter(c=>c.type===1),nc=n.children.filter(c=>c.type===1),counts={};
  sc.forEach((c,i)=>{const ix=counts[c.tag]||0;counts[c.tag]=ix+1;pair(c,nc[i],path+'/'+c.tag+'['+ix+']',local,valid);});
 }
 const sc=source.ast.children.filter(n=>n.type===1),nc=target.ast.children.filter(n=>n.type===1);
 sc.forEach((s,i)=>pair(s,nc[i],'/'+s.tag+'['+i+']',[],true));
 edits.sort((a,b)=>b.start-a.start);
 for(let i=1;i<edits.length;i++)if(edits[i].end>edits[i-1].start)throw Error('Overlapping template edits');
 let result=code;
 if(input.repair)for(const e of edits)result=result.slice(0,e.start)+e.text+result.slice(e.end);
 const classPaths=new Set(proofs.filter(p=>['merged_source_class_bindings',
   'restored_source_class_interpolation_delimiter'].includes(p.rule)).map(p=>p.path));
 for(const path of classPaths)findings.push({code:'source_class_binding_not_landed',location:'template'+path,
   message:'Source conditional class contract requires one well-formed static/dynamic class binding.'});
 return {code:result,findings,changes:input.repair?[...new Set(changes)]:[],proofs,
  boundary:'Outer source-matched render bindings only; identical element shape and loop/conditional scopes. Unknown mappings stay unchanged.'};
}
try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
catch(e){process.stdout.write(JSON.stringify({error:e.message}));}
