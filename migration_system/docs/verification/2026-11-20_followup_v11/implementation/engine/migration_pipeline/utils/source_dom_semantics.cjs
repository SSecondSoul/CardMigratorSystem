// Native DOM syntax/semantics only. Custom-component event names are untouched.
const fs=require('fs'), parser=require('@babel/parser'), t=require('@babel/types');
const traverse=require('@babel/traverse').default, generate=require('@babel/generator').default;
const dom=require('@vue/compiler-dom'), {parse:parseSFC}=require('@vue/compiler-sfc');
const {isHTMLTag}=require('@vue/shared');
const {key,component,parentOf}=require('./inline_identifier_recovery.cjs');
const {run:renderDependencies}=require('./source_render_dependency_semantics.cjs');
const one=(o,k)=>{const xs=o?.properties?.filter(p=>key(p)===k)||[];return xs.length===1?xs[0]:null;};
const ident=s=>typeof s==='string'&&/^[A-Za-z_$][\w$]*$/.test(s)&&!['__proto__','prototype','constructor'].includes(s);
const print=n=>generate(n,{compact:true,comments:false}).code;
const expr=s=>parser.parseExpression(s);
const clean=n=>Array.isArray(n)?n.map(clean):n&&typeof n==='object'
 ?Object.fromEntries(Object.keys(n).sort().filter(k=>!['start','end','loc','extra','leadingComments','trailingComments','innerComments'].includes(k)).map(k=>[k,clean(n[k])])):n;
const equal=(a,b)=>print(clean(a))===print(clean(b));
const elements=n=>(n.children||[]).filter(c=>c.type===1);
const shape=(a,b)=>elements(a).length===elements(b).length&&elements(a).every((n,i)=>n.tag===elements(b)[i].tag&&shape(n,elements(b)[i]));
const attr=(n,name)=>{const xs=n.props.filter(p=>p.type===6&&p.name===name);return xs.length===1?xs[0]:null;};
const directive=(n,name)=>{const xs=n.props.filter(p=>p.type===7&&p.name===name);return xs.length===1?xs[0]:null;};
const bind=(n,name)=>{const xs=n.props.filter(p=>p.type===7&&p.name==='bind'&&p.arg?.isStatic&&p.arg.content===name&&!p.modifiers.length);return xs.length===1?xs[0].exp?.content:null;};
const modifiers=p=>p.modifiers.map(m=>typeof m==='string'?m:m.content);
function quoted(p,text){
 const raw=p?.value?.loc.source;
 if(!raw||!['"',"'"].includes(raw[0])||raw.at(-1)!==raw[0]||/&(?:#|\w+;)/.test(raw))return null;
 const start=p.value.loc.start.offset+1;
 if(text.slice(start,start+raw.length-2)!==raw.slice(1,-1))return null;
 return {value:raw.slice(1,-1),quote:raw[0],start};
}
function parseTemplate(text){const errors=[];const ast=dom.parse(text,{onError:e=>errors.push(e)});return {text,ast,errors};}
function loop(value){
 if(value==null)return {aliases:[],collection:'',track:'',tuple:false};
 const m=/^\s*(\()?\s*([A-Za-z_$][\w$]*)(?:\s*,\s*([A-Za-z_$][\w$]*))?\s*(\))?\s+in\s+([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)(?:\s+trackby\s+([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*))?\s*$/.exec(value);
 if(!m||!!m[1]!==!!m[4]||[m[2],m[3]].filter(Boolean).some(x=>!ident(x))||m[2]===m[3])return null;
 return {aliases:[m[2],m[3]].filter(Boolean),collection:m[5],track:m[6]||'',tuple:!!m[1]};
}
function scope(node,vue,provenConditions=[]){
 const p=vue?directive(node,'for'):attr(node,'s-for');
 const value=vue?p?.exp?.content:p?.value?.content, l=loop(value);
 if(!l||(p&&!value))return null;
 const conditions=[];
 for(const name of ['if','else-if','else']){
  const p=vue?directive(node,name):attr(node,'s-'+name);
  if(!p)continue;
  const s=vue?p.exp?.content:p.value?.content;
  if(name!=='else'&&!s)return null;
  try{
   let expression=s?print(expr(s)):null;
   const proven=provenConditions.filter(p=>p.kind===name&&p.target===expression);
   if(!vue&&proven.length===1)expression=proven[0].source;
   conditions.push([name,expression]);
  }catch(_){return null;}
 }
 return {...l,signature:JSON.stringify([l.aliases,l.collection,conditions])};
}
function method(o,name){const m=one(o,name);return t.isObjectMethod(m)&&m.kind==='method'&&!m.async&&!m.generator?m:null;}
function dataNames(o,vue){
 const result=new Set(),p=one(o,vue?'props':'dataTypes')?.value;
 if(t.isObjectExpression(p))p.properties.forEach(p=>{if(ident(key(p)))result.add(key(p));});
 if(t.isArrayExpression(p))p.elements.forEach(p=>{if(t.isStringLiteral(p)&&ident(p.value))result.add(p.value);});
 const init=method(o,vue?'data':'initData');
 for(const s of init?.body.body||[])if(t.isReturnStatement(s)&&t.isObjectExpression(s.argument))
  s.argument.properties.forEach(p=>{if(ident(key(p)))result.add(key(p));});
 return result;
}
function own(n,name){return t.isMemberExpression(n)&&!n.computed&&t.isThisExpression(n.object)&&t.isIdentifier(n.property,{name});}
function guardAction(m,kind='self'){
 if(!m||m.params.length!==1||!t.isIdentifier(m.params[0])||m.body.body.length!==1)return null;
 const param=m.params[0].name,stmt=m.body.body[0];
 if(!t.isIfStatement(stmt)||stmt.alternate)return null;
 let cond=stmt.test;
 if(t.isLogicalExpression(cond,{operator:'&&'})&&t.isIdentifier(cond.left,{name:param}))cond=cond.right;
 const field=(n,k)=>t.isMemberExpression(n)&&!n.computed&&t.isIdentifier(n.object,{name:param})&&t.isIdentifier(n.property,{name:k});
 if(kind==='self'){
  if(!t.isBinaryExpression(cond,{operator:'==='})||!field(cond.left,'target')||!field(cond.right,'currentTarget'))return null;
 }else{
  const expected=expr(`${param}.key ? ${param}.key === 'Enter' : ${param}.keyCode === 13`);
  if(!equal(cond,expected))return null;
 }
 let body=stmt.consequent;
 if(t.isBlockStatement(body)&&body.body.length===1)body=body.body[0];
 return t.isExpressionStatement(body)?body.expression:null;
}
function handlerValue(value){
 const m=/^((?:(?:stop|prevent|enter):)*)([\s\S]*)$/.exec(value.trim());
 if(!m)return null;
 try{return {modifiers:m[1].split(':').filter(Boolean),text:m[2],node:m[2]?expr(m[2]):null};}catch(_){return null;}
}
function sourceParent(ast){
 const xs=[];
 traverse(ast,{ExportDefaultDeclaration(p){if(p.parentPath.isProgram())xs.push(p.node.declaration);},
 AssignmentExpression(p){const n=p.node;if(p.parentPath.parentPath?.isProgram()&&n.operator==='='
  &&t.isMemberExpression(n.left)&&!n.left.computed&&n.left.object.name==='module'&&n.left.property.name==='exports')xs.push(n.right);}});
 return xs.length===1&&t.isObjectExpression(xs[0])?xs[0]:null;
}
function analyze(input){
 const code=input.code,findings=[],changes=[],proofs=[],reviews=[],edits=[],native_guards=[],mapped_scopes=[],mapped_nodes=[];
 const result=()=>({code,findings,changes:[],proofs,reviews,native_guards,mapped_scopes,mapped_nodes});
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code);
 if(!block)return result();
 const script=block[1],scriptOffset=block.index+block[0].indexOf('>')+1;
 const ast=parser.parse(script,{sourceType:'unambiguous'}),parent=parentOf(ast);
 const dependencyConditions=input.vue?renderDependencies({code,vue:input.vue,repair:false}).scope_conditions||[]:[];
 if(!parent||parent.properties.some(p=>!key(p))||new Set(parent.properties.map(key)).size!==parent.properties.length)return result();
 const scopes=[];
 const outer=/<template\b[^>]*>([\s\S]*?)<\/template\s*>/i.exec(code);
 if(input.vue&&outer){
  const {descriptor,errors}=parseSFC(input.vue);
  if(!errors.length&&descriptor.template&&descriptor.script&&!descriptor.scriptSetup){
   const source=sourceParent(parser.parse(descriptor.script.content,{sourceType:'unambiguous'}));
   if(source&&!one(source,'mixins')&&!one(source,'extends'))scopes.push({id:'template',source,target:parent,
    sourceText:descriptor.template.content,targetText:outer[1],offset:outer.index+outer[0].indexOf('>')+1});
  }
 }
 const registry=one(parent,'components')?.value,contracts=input.ssm?.script?.options?.components||[],seen=new Set();
 if(t.isObjectExpression(registry)&&registry.properties.every(p=>key(p))){
  for(const c of contracts){
   if(contracts.filter(x=>x.registered_tag===c.registered_tag).length!==1)continue;
   const r=one(registry,c.registered_tag);
   if(!t.isIdentifier(r?.value)||seen.has(r.value.name))continue;
   const declarations=[];
   traverse(ast,{VariableDeclarator(p){if(t.isIdentifier(p.node.id,{name:r.value.name})&&component(p.node.init))declarations.push(p);}});
   if(declarations.length!==1)continue;
   const p=declarations[0],binding=p.scope.getBinding(r.value.name),target=p.node.init.arguments[0];
   if(!binding?.constant||!binding.referencePaths.some(p=>p.node===r.value)
    ||binding.referencePaths.some(p=>!registry.properties.some(r=>r.value===p.node))
    ||target.properties.some(p=>!key(p))||new Set(target.properties.map(key)).size!==target.properties.length)continue;
   if(contracts.some(x=>one(registry,x.registered_tag)?.value?.name===r.value.name
    &&x.inline_definition?.source_code!==c.inline_definition?.source_code))continue;
   let source;
   try{source=expr(c.inline_definition?.source_code||'');}catch(_){continue;}
   if(!t.isObjectExpression(source)||source.properties.some(p=>!key(p))||one(source,'mixins')||one(source,'extends'))continue;
   const a=one(source,'template')?.value,b=one(target,'template')?.value;
   if(!t.isTemplateLiteral(a)||a.expressions.length||!t.isTemplateLiteral(b)||b.expressions.length
    ||a.quasis[0].value.raw.includes('\\')||b.quasis[0].value.raw.includes('\\'))continue;
   seen.add(r.value.name);
   scopes.push({id:'script.'+c.registered_tag+'.template',source,target,
    sourceText:a.quasis[0].value.raw,targetText:b.quasis[0].value.raw,offset:scriptOffset+b.quasis[0].start});
  }
 }
 const used=new Set([...script.matchAll(/[A-Za-z_$][\w$]*/g)].map(m=>m[0]));
 const fresh=kind=>{let i=0,name;do{name='__sourceDom'+kind+'_'+i++;}while(used.has(name));used.add(name);return name;};
 const issue=(kind,id,path,detail)=>{const location=id+path+'@'+detail;
  if(!findings.some(f=>f.code===kind&&f.location===location))findings.push({code:kind,location,
   message:kind==='source_dom_loop_not_landed'?'Source-scoped loop aliases/key require San inline trackby syntax.'
    :'Source-scoped native event requires its original handler/modifier/self contract.'});};
 for(const scopeItem of scopes){
  const {id,source,target,offset}=scopeItem,a=parseTemplate(scopeItem.sourceText),b=parseTemplate(scopeItem.targetText);
  if(a.errors.length||b.errors.length||!shape(a.ast,b.ast)){reviews.push({scope:id,reason:'unmatched_or_unparseable_element_shape'});continue;}
  mapped_scopes.push(id);
  const additions=[],declared=dataNames(target,false),srcDeclared=dataNames(source,true);
  const add=(start,end,text,rule,path)=>{edits.push({start:offset+start,end:offset+end,text});changes.push(rule);proofs.push({scope:id,path,rule});};
  const eventAttribute=(n,event)=>{
   const xs=n.props.filter(p=>p.type===6&&(p.name==='on-'+event||p.name.startsWith('on-'+event+'.')));
   return xs.length<=1?{p:xs[0],ambiguous:false}:{ambiguous:true};
  };
  const pair=(s,n,path,valid=true,aliases=[])=>{
   let sa,na;try{sa=scope(s,true);na=scope(n,false,id==='template'?dependencyConditions.filter(p=>p.path===path):[]);}catch(_){return;}
   valid=valid&&!!sa&&!!na&&sa.signature===na.signature
    &&!s.props.some(p=>(p.type===7&&p.name==='slot')||(p.type===6&&['slot-scope','scope'].includes(p.name)));
   const local=[...aliases,...(sa?.aliases||[])];
   if(valid){
    mapped_nodes.push(id+path);
    const sf=attr(n,'s-for'),srcFor=directive(s,'for');
    if(sf&&srcFor){
     const q=quoted(sf,b.text),sourceKey=bind(s,'key'),extras=n.props.filter(p=>p.type===6&&['key','trackby'].includes(p.name));
     let keyText=null;
     try{keyText=sourceKey?print(expr(sourceKey)):null;}catch(_){}
     const indexDefault=keyText&&keyText===sa.aliases[1];
     if(indexDefault)reviews.push({scope:id,path,reason:'source_index_key_runtime_identity_unproven',
      note:'San only builds an item-key getter for item-prefixed accessors; index identity across splice/reorder is not certified here.'});
     const sourceKeyKnown=keyText&&/^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$/.test(keyText)
      &&sa.aliases.includes(keyText.split('.')[0]);
     if(q&&keyText&&!na.track&&!extras.length&&!indexDefault)issue('source_dom_loop_not_landed',id,path,'s-for');
     // Only observed invalid alias/redundant-attribute forms, not an invented
     // list identity policy for already well-formed unkeyed target loops.
     if(q&&(na.tuple||extras.length||(!na.track&&sourceKeyKnown&&!indexDefault))&&(!keyText||/^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$/.test(keyText))){
      const validExtras=extras.every(p=>{const v=quoted(p,b.text);if(!v||!keyText)return false;
       let raw=v.value.trim();if(raw.startsWith('{{')&&raw.endsWith('}}'))raw=raw.slice(2,-2).trim();
       try{return print(expr(raw))===keyText;}catch(_){return false;}});
      if(validExtras&&(!na.track||na.track===keyText)&&(!na.track||keyText)){
       const fixed=sa.aliases.join(', ')+' in '+sa.collection+(keyText?' trackby '+keyText:'');
       if(q.value!==fixed||extras.length){
        issue('source_dom_loop_not_landed',id,path,'s-for');
        add(q.start,q.start+q.value.length,fixed,'restored_source_loop_syntax',path);
        extras.forEach(p=>add(p.loc.start.offset,p.loc.end.offset,'','restored_source_loop_syntax',path));
       }
      }
     }
    }
    if(isHTMLTag(s.tag))for(const p of s.props){
     if(p.type!==7||p.name!=='on'||!p.arg?.isStatic)continue;
     const event=p.arg.content,mods=modifiers(p),sourceValue=p.exp?.content?.trim()||'';
     if(!/^[a-z]+$/.test(event)||mods.length>1||mods.some(m=>!['self','stop','prevent','enter'].includes(m))
       ||(mods[0]==='enter'&&!['keyup','keydown','keypress'].includes(event))||(mods[0]==='self'&&event!=='click'))continue;
     const {p:tp,ambiguous}=eventAttribute(n,event);if(ambiguous)continue;
     const q=tp&&quoted(tp,b.text);if(tp&&!q)continue;
     const value=q?handlerValue(q.value):{modifiers:[],text:'',node:null};if(!value)continue;
     if(tp&&tp.name!=='on-'+event&&tp.name!=='on-'+event+'.'+mods[0])continue;
     let expected,action,kind;
     try{
      if(!sourceValue&&['prevent','stop'].includes(mods[0]))kind='noop';
      else{
       expected=expr(sourceValue);
       if(t.isIdentifier(expected)&&!local.includes(expected.name)&&method(target,expected.name)
        &&method(one(source,'methods')?.value,expected.name)){
        kind='method';action=t.callExpression(t.memberExpression(t.thisExpression(),t.identifier(expected.name)),[]);
       }else if(t.isCallExpression(expected)&&t.isIdentifier(expected.callee,{name:'$emit'})&&!local.includes('$emit')
        &&expected.arguments.length<=2&&expected.arguments.length>=1&&t.isStringLiteral(expected.arguments[0])){
        expected=t.callExpression(t.identifier('fire'),expected.arguments);kind='emit';
       }else if(t.isAssignmentExpression(expected,{operator:'='})&&t.isIdentifier(expected.left)
        &&t.isBooleanLiteral(expected.right)&&!local.includes(expected.left.name)
        &&declared.has(expected.left.name)&&srcDeclared.has(expected.left.name)){
        action=expr(`this.data.set(${JSON.stringify(expected.left.name)},${expected.right.value})`);kind='boolean';
       }else continue;
      }
     }catch(_){continue;}
     let replacement=null;
     if(mods[0]==='self'&&(kind==='method'||kind==='boolean')){
      if(kind==='method'&&method(target,expected.name).params.length)continue;
      let callable=null;
      if(t.isIdentifier(value.node))callable=method(target,value.node.name);
      if(t.isCallExpression(value.node)&&t.isIdentifier(value.node.callee)&&value.node.arguments.length===1
       &&t.isIdentifier(value.node.arguments[0],{name:'$event'}))callable=method(target,value.node.callee.name);
      let guarded=guardAction(callable);
      // One exact, zero-argument setter indirection is still a single proven
      // boolean effect, not a general alias-name exemption.
      if(kind==='boolean'&&t.isCallExpression(guarded)&&!guarded.arguments.length
       &&t.isMemberExpression(guarded.callee)&&!guarded.callee.computed&&t.isThisExpression(guarded.callee.object)){
       const setter=method(target,guarded.callee.property.name);
       if(setter&&!setter.params.length&&setter.body.body.length===1&&t.isExpressionStatement(setter.body.body[0]))
        guarded=setter.body.body[0].expression;
      }
      if(guarded&&equal(guarded,action)&&!value.modifiers.length&&tp?.name==='on-'+event){
       if(kind==='method')native_guards.push({scope:id,event,source_handler:sourceValue,target_handler:value.text,kind:'self'});
       continue;
      }
      let equivalent=value.node&&equal(value.node,expected);
      if(kind==='boolean'&&callable&&!callable.params.length&&callable.body.body.length===1
       &&t.isExpressionStatement(callable.body.body[0])&&equal(callable.body.body[0].expression,action))equivalent=true;
      // A missing .self boolean assignment can be restored from the declared
      // source state contract; never replace an unknown existing handler.
      if((equivalent||!tp)&&!value.modifiers.length){
       const name=fresh('Self');
       additions.push(`${name}(event){if(event && event.target === event.currentTarget) ${print(action)};}`);
       replacement=name+'($event)';
      }else{issue('source_dom_event_not_landed',id,path,event);continue;}
     }else if(mods[0]==='enter'&&kind==='method'){
      if(method(target,expected.name).params.length)continue;
      let callable=null;
      if(t.isIdentifier(value.node))callable=method(target,value.node.name);
      if(t.isCallExpression(value.node)&&t.isIdentifier(value.node.callee)&&value.node.arguments.length===1
       &&t.isIdentifier(value.node.arguments[0],{name:'$event'}))callable=method(target,value.node.callee.name);
      const guarded=guardAction(callable,'enter');
      if(guarded&&equal(guarded,action)&&!value.modifiers.length&&tp?.name==='on-'+event){
       native_guards.push({scope:id,event,source_handler:sourceValue,target_handler:value.text,kind:'enter'});
       continue;
      }
      if((!tp||(value.node&&equal(value.node,expected)))&&value.modifiers.every(m=>m==='enter')){
       const name=fresh('Enter');
       additions.push(`${name}(event){if(event && (event.key ? event.key === 'Enter' : event.keyCode === 13)) ${print(action)};}`);
       replacement=name+'($event)';
      }else{issue('source_dom_event_not_landed',id,path,event);continue;}
     }else if(kind==='noop'){
      if(value.text){
       if(t.isIdentifier(value.node)){
        const m=method(target,value.node.name);
        if(m&&!m.params.length&&!m.body.body.length){
         if(value.modifiers.join()===mods.join()&&tp.name==='on-'+event)continue;
         issue('source_dom_event_not_landed',id,path,event);
         if(!value.modifiers.length)replacement=mods[0]+':'+value.node.name;
        }
       }
       if(replacement===null)continue;
      }else{
       const name=fresh('Noop');additions.push(`${name}(){}`);replacement=mods[0]+':'+name;
      }
     }else if(kind==='method'||kind==='emit'){
      // Missing named handlers are restored only for native drag/drop bindings;
      // method-body/dataTransfer equivalence is a separate, still-required proof.
      if(!tp&&!['drop','dragend'].includes(event)){issue('source_dom_event_not_landed',id,path,event);continue;}
      if(tp&&(!value.node||!equal(value.node,expected)))continue;
      const targetMods=tp?.name.includes('.')?[tp.name.split('.').at(-1)]:value.modifiers;
      if(tp&&targetMods.join()!==mods.join()&&targetMods.length){issue('source_dom_event_not_landed',id,path,event);continue;}
      replacement=(mods.length?mods[0]+':':'')+print(expected);
      if(tp?.name==='on-'+event&&value.modifiers.join()===mods.join()&&value.node&&equal(value.node,expected))continue;
     }
     if(replacement!==null){
      let quote=q?.quote||'"';if(replacement.includes(quote))quote=quote==='"'?"'":'"';
      if(replacement.includes(quote))continue;
      issue('source_dom_event_not_landed',id,path,event);
      const text='on-'+event+'='+quote+replacement+quote;
      if(tp)add(tp.loc.start.offset,tp.loc.end.offset,text,'restored_source_native_event_contract',path+'@'+event);
      else add(n.loc.start.offset+1+n.tag.length,n.loc.start.offset+1+n.tag.length,' '+text,'restored_source_native_event_contract',path+'@'+event);
     }
    }
   }
   elements(s).forEach((c,i)=>pair(c,elements(n)[i],path+'/'+c.tag+'['+i+']',valid,local));
  };
  elements(a.ast).forEach((s,i)=>pair(s,elements(b.ast)[i],'/'+s.tag+'['+i+']'));
  if(additions.length)edits.push({start:scriptOffset+target.start+1,end:scriptOffset+target.start+1,text:'\n'+additions.join(',\n')+',\n'});
 }
 // Multiple missing attributes on the same node are one insertion, preserving
 // discovery order and avoiding conflicting offsets.
 const grouped=[];
 for(const e of edits){const prior=grouped.find(x=>x.start===e.start&&x.end===e.end&&x.start===x.end);
  if(prior)prior.text+=e.text;else grouped.push({...e});}
 grouped.sort((a,b)=>b.start-a.start);
 for(let i=1;i<grouped.length;i++)if(grouped[i].end>grouped[i-1].start)throw Error('Overlapping source DOM edits');
 let next=code;
 if(input.repair)for(const e of grouped)next=next.slice(0,e.start)+e.text+next.slice(e.end);
 if(input.repair&&grouped.length)parser.parse(/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(next)[1],{sourceType:'unambiguous'});
 return {code:next,findings,changes:input.repair?[...new Set(changes)]:[],proofs,reviews,native_guards,mapped_scopes,mapped_nodes};
}
try{process.stdout.write(JSON.stringify(analyze(JSON.parse(fs.readFileSync(0,'utf8')))));}
catch(e){process.stdout.write(JSON.stringify({error:e.message}));}
