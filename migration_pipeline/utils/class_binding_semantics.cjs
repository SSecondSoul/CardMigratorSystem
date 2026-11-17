/* Class-only contracts: inspect full attribute expressions, never San's prefix parse.
 * No component-name rules. Edits require source registry/path/scope/static/token/condition proof.
 */
'use strict';
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types'),traverse=require('@babel/traverse').default;
const generate=require('@babel/generator').default,dom=require('@vue/compiler-dom');
const {key,component,parentOf}=require('./inline_identifier_recovery.cjs');
const one=(o,k)=>{const ps=o?.properties?.filter(p=>key(p)===k)||[];return ps.length===1?ps[0]:null;};
const print=n=>generate(n,{compact:true,comments:false,jsescOption:{quotes:'single'}}).code;
const expr=s=>parser.parseExpression(s),same=(a,b)=>print(a)===print(b),elements=n=>(n.children||[]).filter(c=>c.type===1);
const shape=(a,b)=>elements(a).length===elements(b).length&&elements(a).every((n,i)=>n.tag===elements(b)[i].tag&&shape(n,elements(b)[i]));
const tag=s=>s.replace(/([a-z\d])([A-Z])/g,'$1-$2').toLowerCase();
const attr=(n,name)=>{const p=n.props.filter(p=>p.type===6&&p.name===name);return p.length===1?p[0]:null;};
const bind=n=>{const p=n.props.filter(p=>p.type===7&&p.name==='bind'&&p.arg?.isStatic&&p.arg.content==='class'&&!p.modifiers.length);return p.length===1?p[0].exp?.content:null;};
const parseTemplate=text=>{const errors=[];return {text,ast:dom.parse(text,{onError:e=>errors.push(e)}),errors};};
function sourceParent(ast){const found=[];traverse(ast,{
 ExportDefaultDeclaration(p){if(p.parentPath.isProgram())found.push(p.node.declaration);},
 AssignmentExpression(p){const n=p.node;if(p.parentPath.parentPath?.isProgram()&&n.operator==='='&&t.isMemberExpression(n.left)
  &&!n.left.computed&&n.left.object.name==='module'&&n.left.property.name==='exports')found.push(n.right);}
});return found.length===1&&t.isObjectExpression(found[0])?found[0]:null;}
function chunks(text){
 const out=[];let at=0;
 while(at<text.length){const start=text.indexOf('{{',at);if(start<0){out.push({text:text.slice(at)});break;}
  if(start>at)out.push({text:text.slice(at,start)});
  let depth=0,quote=null,end=-1;
  for(let i=start+2;i<text.length;i++){
   const c=text[i];if(quote){if(c==='\\'){i++;continue;}if(c===quote)quote=null;continue;}
   if(['"',"'",'`'].includes(c)){quote=c;continue;}
   if(c==='{' )depth++;else if(c==='}'){
    if(!depth&&text[i+1]==='}'){end=i;break;}depth--;
   }
   if(depth<0)return null;
  }
  if(end<0)return null;out.push({expression:text.slice(start+2,end).trim()});at=end+2;
 }return out;
}
function objectForm(text){
 try{const n=expr(text);return t.isObjectExpression(n)?n:null;}catch(_){
  try{const n=expr('({'+text+'})');return t.isObjectExpression(n)&&n.properties.length?n:null;}catch(_e){return null;}
 }
}
function fields(o,vue){const result=new Set();
 for(const name of [vue?'props':'dataTypes','computed']){const n=one(o,name)?.value;
  if(t.isObjectExpression(n))n.properties.forEach(p=>{if(key(p))result.add(key(p));});
  if(t.isArrayExpression(n))n.elements.forEach(p=>{if(t.isStringLiteral(p))result.add(p.value);});
 }
 const fn=one(o,vue?'data':'initData');
 if(t.isObjectMethod(fn))for(const s of fn.body.body)if(t.isReturnStatement(s)&&t.isObjectExpression(s.argument))s.argument.properties.forEach(p=>{if(key(p))result.add(key(p));});
 return result;
}
function scope(n,vue){const rows=[];let aliases=[];
 for(const name of ['for','if','else-if','else']){
  const ps=n.props.filter(p=>vue?p.type===7&&p.name===name:p.type===6&&p.name==='s-'+name);
  if(ps.length>1)return null;if(!ps.length)continue;
  const value=vue?ps[0].exp?.content:ps[0].value?.content;
  if(name==='else'){rows.push([name]);continue;}
  if(!value)return null;
  if(name==='for'){
   const m=/^\s*\(?\s*([\w$]+)(?:\s*,\s*([\w$]+))?\s*\)?\s+in\s+([\w$.]+)(?:\s+trackby\s+[\w$.]+)?\s*$/.exec(value);
   if(!m)return null;aliases=[m[1],m[2]].filter(Boolean);rows.push([name,...aliases,m[3]]);
  }else{try{rows.push([name,print(expr(value))]);}catch(_){return null;}}
 }return {signature:JSON.stringify(rows),aliases};
}
function sourceMap(node,allowed){
 if(!t.isObjectExpression(node)||!node.properties.length)return null;
 const seen=new Set(),terms=[];
 for(const p of node.properties){const name=key(p);
  if(!t.isObjectProperty(p)||p.computed||!name||seen.has(name)||['__proto__','constructor','prototype'].includes(name)
   ||!/^[-_a-zA-Z][\w-]*(?:\s+[-_a-zA-Z][\w-]*)*$/.test(name))return null;
  seen.add(name);
  // Positive San-compatible grammar, rather than a JavaScript blacklist (which
  // would accidentally admit optional calls, template literals or **).
  function safe(n){
   if(t.isIdentifier(n))return allowed.has(n.name)||n.name==='undefined';
   if(t.isStringLiteral(n)||t.isNumericLiteral(n)||t.isBooleanLiteral(n)||t.isNullLiteral(n))return true;
   if(t.isMemberExpression(n)&&!n.optional)return safe(n.object)&&
    (n.computed?(t.isStringLiteral(n.property)||t.isNumericLiteral(n.property)):t.isIdentifier(n.property));
   if(t.isUnaryExpression(n)&&['!','+','-'].includes(n.operator))return safe(n.argument);
   if(t.isBinaryExpression(n)&&['+','-','*','/','%','==','!=','===','!==','<','>','<=','>='].includes(n.operator))return safe(n.left)&&safe(n.right);
   if(t.isLogicalExpression(n)&&['&&','||'].includes(n.operator))return safe(n.left)&&safe(n.right);
   if(t.isConditionalExpression(n))return safe(n.test)&&safe(n.consequent)&&safe(n.alternate);
   return false;
  }
  if(!safe(p.value))return null;terms.push({name:name.replace(/\s+/g,' '),condition:print(p.value)});
 }return terms;
}
function signature(parts){
 const statics=[],terms=[];let safe=true,lastToken=false;
 // Token boundaries matter: base{{flag?'active':''}} is baseactive,
 // not the two classes base/active. Empty ternaries cannot add a delimiter.
 function segment(value,optional){
  if(!value)return;if(lastToken&&!/^\s/.test(value))safe=false;
  lastToken=/\S$/.test(value)||(optional&&lastToken);
 }
 function literal(value){segment(value,false);statics.push(...value.split(/\s+/).filter(Boolean));}
 function visit(n){
  if(t.isStringLiteral(n))return literal(n.value);
  if(t.isBinaryExpression(n,{operator:'+'})){visit(n.left);visit(n.right);return;}
  if(t.isConditionalExpression(n)&&t.isStringLiteral(n.consequent)&&t.isStringLiteral(n.alternate,{value:''})){
   // Check boundaries against the ORIGINAL bytes first. Whitespace inside the
   // optional string is a valid separator, but must not hide baseactive merges.
   segment(n.consequent.value,true);terms.push({name:n.consequent.value.trim().replace(/\s+/g,' '),condition:print(n.test)});return;
  }safe=false;
 }
 for(const p of parts||[]){if(p.text!==undefined)literal(p.text);else try{visit(expr(p.expression));}catch(_){safe=false;}}
 return safe?{statics,terms}:null;
}
function analyze(input){
 const code=input.code,findings=[],reviews=[],changes=[],proofs=[],mapped_bindings=[],edits=[];
 const none={code,findings,reviews,changes,proofs,mapped_bindings,boundary:'No class attribute candidate in source or target; JavaScript syntax remains the compiler contract.'};
 if(!/(?:^|[^\w-])(?:class|:class|v-bind:class)\s*=/.test(code+'\n'+(input.vue||'')))return none;
 const script=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code),outer=/<template\b[^>]*>([\s\S]*?)<\/template\s*>/i.exec(code);
 const scopes=[];let ast=null,targetParent=null,sourceRoot=null,sourceAst=null;
 if(script){ast=parser.parse(script[1],{sourceType:'unambiguous'});targetParent=parentOf(ast);}
 if(input.vue){const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(input.vue);
  if(block){sourceAst=parser.parse(block[1],{sourceType:'unambiguous'});sourceRoot=sourceParent(sourceAst);}}
 const opaque=o=>!o||one(o,'mixins')||one(o,'extends')||o.properties.some(p=>!key(p));
 const sourceOuter=input.vue&&/<template\b[^>]*>([\s\S]*?)<\/template\s*>/i.exec(input.vue);
 if(outer)scopes.push({id:'template',text:outer[1],offset:outer.index+outer[0].indexOf('>')+1,
  sourceText:sourceOuter&&!opaque(sourceRoot)?sourceOuter[1]:null,source:sourceRoot,target:targetParent});
 const inline=[];
 if(ast)traverse(ast,{CallExpression(p){if(!component(p.node))return;
  const o=p.node.arguments[0],value=one(o,'template')?.value;
  const text=t.isTemplateLiteral(value)&&!value.expressions.length?value.quasis[0].value.cooked:t.isStringLiteral(value)?value.value:null;
  if(typeof text!=='string')return;
  const raw=script[1].slice(value.start+1,value.end-1);
  const row={id:'script.'+(p.parentPath.isVariableDeclarator()?p.parentPath.node.id.name:'parent')+'.template',
   text,offset:script.index+script[0].indexOf('>')+1+value.start+1,editable:raw===text,target:o,declaration:p.parentPath.isVariableDeclarator()?p.parentPath:null};
  scopes.push(row);inline.push(row);
 }});
 const a=one(sourceRoot,'components')?.value,b=one(targetParent,'components')?.value;
 if(sourceAst&&t.isObjectExpression(a)&&t.isObjectExpression(b)&&!opaque(sourceRoot)&&!opaque(targetParent)){
  for(const row of inline){if(!row.declaration)continue;const id=row.declaration.node.id.name;
   const regs=b.properties.filter(p=>t.isIdentifier(p.value,{name:id}));if(regs.length!==1||!key(regs[0]))continue;
   const refs=a.properties.filter(p=>key(p)&&tag(key(p))===tag(key(regs[0])));if(refs.length!==1||!t.isIdentifier(refs[0].value))continue;
   const binding=row.declaration.scope.getBinding(id);if(!binding?.constant||binding.referencePaths.some(p=>p.node!==regs[0].value))continue;
   const declarations=[];traverse(sourceAst,{VariableDeclarator(p){if(t.isIdentifier(p.node.id,{name:refs[0].value.name})&&t.isObjectExpression(p.node.init))declarations.push(p);}});
   if(declarations.length!==1)continue;const src=declarations[0],srcBinding=src.scope.getBinding(src.node.id.name);
   if(!srcBinding?.constant||srcBinding.referencePaths.some(p=>p.node!==refs[0].value)||opaque(src.node.init))continue;
   const tpl=one(src.node.init,'template')?.value;
   if(t.isTemplateLiteral(tpl)&&!tpl.expressions.length)row.sourceText=tpl.quasis[0].value.cooked;
   else if(t.isStringLiteral(tpl))row.sourceText=tpl.value;
   row.source=src.node.init;
  }
 }
 function finding(code,location,message){if(!findings.some(f=>f.code===code&&f.location===location))findings.push({code,location,message});}
 for(const row of scopes){const target=parseTemplate(row.text);const source=row.sourceText&&parseTemplate(row.sourceText);
  function inspect(n,path){
   if(n.type===1)for(const p of n.props)if(p.type===6&&p.name==='class'&&p.value){
    for(const part of chunks(p.value.content)||[])if(part.expression&&objectForm(part.expression)){
     finding('invalid_object_class_binding',row.id+path+'@class','Class interpolation contains an object/map, including bare key:value syntax; San may silently parse only its first literal. Use complete conditional string expressions.');
    }
   }elements(n).forEach((c,i)=>inspect(c,path+'/'+c.tag+'['+i+']'));
  }inspect(target.ast,'');
  if(!source||source.errors.length||target.errors.length||!shape(source.ast,target.ast)||opaque(row.source)||opaque(row.target))continue;
  const knownSource=fields(row.source,true),knownTarget=fields(row.target,false);
  function pair(s,n,path,aliases,valid){
   const ss=scope(s,true),ns=scope(n,false);valid=valid&&!!ss&&!!ns&&ss.signature===ns.signature;
   const local=[...aliases,...(ns?.aliases||[])];
   if(valid){const binding=bind(s),attrs=n.props.filter(p=>p.type===6&&p.name==='class'),sourceStatic=attr(s,'class')?.value?.content||'';
    // Duplicate attributes remain the existing source-template contract's job;
    // do not emit a second incompatible finding for its partial repairs.
    if(binding&&attrs.length<=1){
     let src;try{src=expr(binding);}catch(_){}
     // A string/member binding is not an object-map. Prove only its unchanged
     // expression and the literal token separator; do not certify arbitrary
     // runtime object/array normalization as equivalent.
     const refPath=n=>{if(t.isIdentifier(n))return [n.name];
      if(t.isMemberExpression(n)&&!n.computed&&!n.optional&&t.isIdentifier(n.property)){
       const base=refPath(n.object);return base?base.concat(n.property.name):null;
      }return null;};
     const ref=src&&refPath(src);
     if(ref?.length&&(knownSource.has(ref[0])&&knownTarget.has(ref[0])||local.includes(ref[0]))&&sourceStatic.trim()){
      const p=attrs.length===1?attrs[0]:null,value=p?.value?.content||'',parts=chunks(value);
      const segments=[];
      const flatten=node=>{
       if(t.isStringLiteral(node))segments.push({text:node.value});
       else if(t.isBinaryExpression(node,{operator:'+'})){flatten(node.left);flatten(node.right);}
       else segments.push({node});
      };
      for(const part of parts||[]){if(part.text!==undefined)segments.push(part);else try{flatten(expr(part.expression));}catch(_){segments.push({unknown:true});}}
      const tail=segments.at(-1),leading=segments.slice(0,-1);
      const onlyPrefix=leading.length&&leading.every(p=>p.text!==undefined),prefix=onlyPrefix?leading.map(p=>p.text).join(''):null;
      const exact=tail?.node&&same(tail.node,src);
      if(onlyPrefix&&exact&&prefix.trim()===sourceStatic.trim()){
       if(/\s$/.test(prefix))mapped_bindings.push(row.id+path+'@class');
       else{
        finding('source_class_binding_not_landed',row.id+path+'@class','Static and source-matched dynamic class tokens lack a separator.');
        const raw=p?.value?.loc.source||'',quote=raw[0];
        if(p?.value&&row.editable!==false&&['"',"'"].includes(quote)&&raw.at(-1)===quote
          &&raw.slice(1,-1)===value&&!/[&\\]/.test(value)){
         const start=row.offset+p.value.loc.start.offset+1,replacement=sourceStatic+' {{'+print(src)+'}}';
         if(!replacement.includes(quote)){
          edits.push({start,end:start+value.length,text:replacement});changes.push('restored_source_class_token_separator');
          proofs.push({location:row.id+path+'@class',source_expression_matched:true,
           proof:'literal_separator_only_runtime_dynamic_type_equivalence_not_proven'});
         }
        }
       }
      }else{
       reviews.push({location:row.id+path+'@class',reason:'Dynamic class shape outside separator proof; unchanged, not certified or relabelled as a definite mismatch.'});
      }
     }
     if(t.isObjectExpression(src)){
      const allowed=new Set([...knownSource].filter(n=>knownTarget.has(n)));local.forEach(n=>allowed.add(n));
      const terms=sourceMap(src,allowed),p=attrs.length===1?attrs[0]:null,value=p?.value?.content||'',parts=chunks(value),sig=parts&&signature(parts);
      const expected={statics:sourceStatic.split(/\s+/).filter(Boolean),terms};
      if(terms&&sig&&JSON.stringify(sig)===JSON.stringify(expected))mapped_bindings.push(row.id+path+'@class');
      else{
       // Unsupported but syntactically string-valued source expressions are
       // explicitly reviewed, not claimed to be mapped or blindly rewritten.
       const malformed=(parts||[]).some(p=>p.expression&&objectForm(p.expression));
       if(terms||malformed)finding(terms?'source_class_binding_not_landed':'source_class_binding_unproven',row.id+path+'@class',
        terms?'Source conditional class tokens/conditions are not proven on the corresponding element.':'Source class map uses an unsupported condition, field or key; do not guess a rewrite.');
       const maps=(parts||[]).filter(p=>p.expression!==undefined),staticText=(parts||[]).filter(p=>p.text!==undefined).map(p=>p.text).join('').trim();
       const raw=p?.value?.loc.source||'',quote=raw[0],rawValue=raw.slice(1,-1);
       const node=maps.length===1&&objectForm(maps[0].expression);
       if(p?.value&&terms&&node&&same(node,src)&&staticText===sourceStatic.trim()&&row.editable!==false
        &&['"',"'"].includes(quote)&&raw.at(-1)===quote&&rawValue===value&&!/[&]|[\\]/.test(rawValue)){
        const literalQuote=quote==='"'?"'":'"';
        const safeValue=(sourceStatic?sourceStatic+' ':'')+terms.map(v=>'{{ '+v.condition+' ? '+literalQuote+v.name+literalQuote+' : '+literalQuote+literalQuote+' }}').join(' ');
        if(!safeValue.includes(quote)){
         const start=row.offset+p.value.loc.start.offset+1;
         edits.push({start,end:start+rawValue.length,text:safeValue});
         changes.push('restored_source_conditional_class_map');proofs.push({location:row.id+path+'@class',tokens:terms.map(v=>v.name),source_expression_matched:true});
        }
       }else reviews.push({location:row.id+path+'@class',reason:'No complete source/path/scope/static/condition proof; unchanged.'});
      }
     }
    }
   }const sa=elements(s),na=elements(n);sa.forEach((c,i)=>pair(c,na[i],path+'/'+c.tag+'['+i+']',local,valid));
  }
  const sa=elements(source.ast),na=elements(target.ast);sa.forEach((s,i)=>pair(s,na[i],'/'+s.tag+'['+i+']',[],true));
 }
 edits.sort((a,b)=>b.start-a.start);for(let i=1;i<edits.length;i++)if(edits[i].end>edits[i-1].start)throw Error('Overlapping class edits');
 let next=code;if(input.repair)for(const e of edits)next=next.slice(0,e.start)+e.text+next.slice(e.end);
 return {code:next,findings,changes:input.repair?[...new Set(changes)]:[],proofs,reviews,mapped_bindings,
  boundary:'Literal-key maps and unchanged identifier/member class token separators; matching registry, DOM shape, loop/conditional scope, fields, static classes and conditions. Separator proof does not certify arbitrary runtime dynamic types. Unknown cases remain diagnostics.'};
}
module.exports={analyze};
if(require.main===module){try{process.stdout.write(JSON.stringify(analyze(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(e){process.stdout.write(JSON.stringify({error:e.message}));}}
