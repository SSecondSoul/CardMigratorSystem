// Exact parent source method + closed local two-splice transaction only.
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types');
const traverse=require('@babel/traverse').default,{parse}=require('@vue/compiler-sfc');
const {parentOf,key}=require('./inline_identifier_recovery.cjs');
const {one,safe,declared,arrayPath,print,same,sourceParent,walk}=require('./source_render_call_semantics.cjs');
const own=(n,name)=>t.isMemberExpression(n)&&!n.computed&&t.isThisExpression(n.object)&&(!name||t.isIdentifier(n.property,{name}));
const store=(n,name)=>t.isCallExpression(n)&&!n.optional&&t.isMemberExpression(n.callee)&&!n.callee.computed
 &&own(n.callee.object,'data')&&t.isIdentifier(n.callee.property,{name});
const get=n=>store(n,'get')&&n.arguments.length===1&&t.isStringLiteral(n.arguments[0])?n.arguments[0].value:null;
const set=n=>store(n,'set')&&n.arguments.length===2&&t.isStringLiteral(n.arguments[0])?n.arguments[0].value:null;
const method=(o,name)=>{const m=one(o,name);return t.isObjectMethod(m)&&m.kind==='method'&&!m.async&&!m.generator
 &&m.params.every(p=>t.isIdentifier(p)||(t.isAssignmentPattern(p)&&t.isIdentifier(p.left)&&t.isBooleanLiteral(p.right)))?m:null;};
function tree(m){return t.file(t.program([t.expressionStatement(t.objectExpression([t.cloneNode(m,true)]))]));}
function normalize(m,source,fields,ids){
 const ast=tree(m);let path;traverse(ast,{ObjectMethod(p){path=p;p.stop();}});
 path.traverse({CallExpression(p){if(source)return;const f=get(p.node),w=set(p.node);
  if(f&&fields.has(f))p.replaceWith(t.identifier(ids.get(f)));
  else if(w&&fields.has(w))p.replaceWith(t.assignmentExpression('=',t.identifier(ids.get(w)),p.node.arguments[1]));
 },MemberExpression(p){if(source&&own(p.node)&&fields.has(p.node.property.name))p.replaceWith(t.identifier(ids.get(p.node.property.name)));}});
 let changed=true;
 while(changed){changed=false;path.scope.crawl();
  for(const stmt of path.get('body.body')){
   const n=stmt.node;if(!t.isVariableDeclaration(n,{kind:'const'})||n.declarations.length!==1)continue;
   const d=n.declarations[0];if(!t.isIdentifier(d.id)||!t.isIdentifier(d.init)||![...ids.values()].includes(d.init.name))continue;
   const b=path.scope.getBinding(d.id.name);if(!b?.constant)continue;
   b.referencePaths.forEach(p=>p.replaceWith(t.identifier(d.init.name)));stmt.remove();changed=true;break;
  }
 }
 return path.node;
}
const arrayCall=(n,field,name)=>t.isCallExpression(n)&&!n.optional&&t.isMemberExpression(n.callee)&&!n.callee.computed
 &&t.isIdentifier(n.callee.object,{name:field})&&t.isIdentifier(n.callee.property,{name});
function transaction(m,field){
 const body=m.body.body,success=body.at(-1);
 if(!t.isIfStatement(success)||success.alternate||!t.isBlockStatement(success.consequent))return null;
 const statements=success.consequent.body,calls=[];
 walk(m.body,n=>{if(arrayCall(n,field,'splice'))calls.push(n);});
 if(calls.length!==2)return null;
 const first=statements.findIndex(s=>t.isVariableDeclaration(s,{kind:'const'})&&s.declarations.length===1
  &&s.declarations[0].init===calls[0]);
 const last=statements.findIndex(s=>t.isExpressionStatement(s)&&s.expression===calls[1]);
 if(first!==0||last<=first)return null;
 const removed=statements[first].declarations[0].id,a=calls[0].arguments,b=calls[1].arguments;
 if(!t.isArrayPattern(removed)||removed.elements.length!==1||!t.isIdentifier(removed.elements[0])
  ||a.length!==2||!t.isIdentifier(a[0])||!t.isNumericLiteral(a[1],{value:1})
  ||b.length!==3||!t.isIdentifier(b[0])||!t.isNumericLiteral(b[1],{value:0})||!t.isIdentifier(b[2],{name:removed.elements[0].name}))return null;
 // Between removal and insertion, only local numeric index adjustments and pure guards.
 const locals=new Set();walk(m.body,n=>{if(t.isVariableDeclarator(n)&&t.isIdentifier(n.id))locals.add(n.id.name);});
 const params=new Set(m.params.map(p=>t.isIdentifier(p)?p.name:p.left.name));
 const pure=n=>t.isNumericLiteral(n)||t.isBooleanLiteral(n)||t.isNullLiteral(n)
  ||(t.isIdentifier(n)&&(locals.has(n.name)||params.has(n.name)))
  ||(t.isUnaryExpression(n)&&['!','+','-'].includes(n.operator)&&pure(n.argument))
  ||((t.isBinaryExpression(n)||t.isLogicalExpression(n))&&pure(n.left)&&pure(n.right));
 const adjustment=n=>t.isBlockStatement(n)?n.body.every(adjustment)
  :t.isIfStatement(n)?pure(n.test)&&adjustment(n.consequent)&&(!n.alternate||adjustment(n.alternate))
  :t.isExpressionStatement(n)&&t.isAssignmentExpression(n.expression)&&['+=','-=','='].includes(n.expression.operator)
   &&t.isIdentifier(n.expression.left)&&locals.has(n.expression.left.name)&&pure(n.expression.right);
 if(!statements.slice(first+1,last).every(adjustment))return null;
 return {success,first:statements[first],last:statements[last],field};
}
function run(input){
 const result={code:input.code,findings:[],changes:[],proofs:[],reviews:[],mapped_contracts:[]};
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(input.code),src=parse(input.vue);
 if(!block||src.errors.length||!src.descriptor.script||src.descriptor.scriptSetup)return result;
 const script=block[1],offset=block.index+block[0].indexOf('>')+1;
 const ast=parser.parse(script,{sourceType:'unambiguous'}),srcAst=parser.parse(src.descriptor.script.content,{sourceType:'unambiguous'});
 const parent=parentOf(ast),original=sourceParent(srcAst),methods=one(original,'methods')?.value;
 if(!safe(parent)||!safe(original)||!safe(methods)||one(original,'mixins')||one(original,'extends')||one(parent,'mixins')||one(parent,'extends'))return result;
 let binding,unsafe=false;
 traverse(ast,{Program(p){binding=p.scope.getBinding('san');}});
 if(!binding?.constant||!binding.path.isVariableDeclarator()||!t.isCallExpression(binding.path.node.init)
  ||!t.isIdentifier(binding.path.node.init.callee,{name:'require'})||binding.path.node.init.arguments.length!==1
  ||!t.isStringLiteral(binding.path.node.init.arguments[0],{value:'san'}))return result;
 for(const a of [ast,srcAst]){
  traverse(a,{Scope(p){if(p.scope.hasOwnBinding('Array'))unsafe=true;}});
  walk(a,n=>{if(!t.isAssignmentExpression(n))return;let root=n.left;
   while(t.isMemberExpression(root))root=root.object;
   if(t.isIdentifier(root,{name:'Array'}))unsafe=true;});
 }
 if(unsafe)return result;
 const fields=declared(original,true);for(const p of one(original,'computed')?.value?.properties||[])if(key(p))fields.add(key(p));
 if([...fields].some(f=>!/^[A-Za-z_$][\w$]*$/.test(f)||['__proto__','prototype','constructor'].includes(f)))return result;
 const used=new Set([...script.matchAll(/[A-Za-z_$][\w$]*/g),...src.descriptor.script.content.matchAll(/[A-Za-z_$][\w$]*/g)].map(m=>m[0]));
 const ids=new Map([...fields].map(f=>{let name='__sourceArrayField_'+f;while(used.has(name))name+='_';used.add(name);return [f,name];}));
 const edits=[];
 for(const s of methods.properties){const name=key(s);if(!method(methods,name))continue;
  const normalizedSource=normalize(s,true,fields,ids),candidates=[...fields].filter(f=>arrayPath(original,[f])&&transaction(normalizedSource,ids.get(f)));
  if(candidates.length!==1)continue;
  const field=candidates[0],contract='script.methods.'+name+'@'+field;
  result.mapped_contracts.push(contract);
  const issue=message=>result.findings.push({code:'source_array_transaction_not_landed',location:contract,message});
  const target=method(parent,name);
  if(!target){issue('Source array transaction method or signature is missing.');continue;}
  // Locate one root alias and one optional existing root commit; no fallback/escape guessing.
  const aliases=[];for(const statement of target.body.body){if(!t.isVariableDeclaration(statement,{kind:'const'})||statement.declarations.length!==1)continue;
   const d=statement.declarations[0],copy=t.isArrayExpression(d.init)&&d.init.elements.length===1&&t.isSpreadElement(d.init.elements[0]);
   const read=copy?d.init.elements[0].argument:d.init;
   if(t.isIdentifier(d.id)&&get(read)===field)aliases.push({statement,declaration:d,read,copy});
  }
  if(aliases.length!==1){issue('A unique local source-array alias is unproven.');continue;}
  const alias=aliases[0],aliasName=alias.declaration.id.name,commits=[];
  const reads=[];walk(target.body,n=>{if(get(n)===field)reads.push(n);});
  if(reads.length!==1||reads[0]!==alias.read){issue('Additional live array reads could observe stale pre-commit state.');continue;}
  walk(target.body,n=>{if(set(n)===field)commits.push(n);});
  const tail=target.body.body.at(-1);
  if(commits.length>1||!t.isIfStatement(tail)||tail.alternate||!t.isBlockStatement(tail.consequent)){
   issue('A unique single-success-block array commit is unproven.');continue;
  }
  const commit=commits[0],commitStatement=commit&&tail.consequent.body.find(s=>t.isExpressionStatement(s)&&s.expression===commit);
  const value=commit?.arguments[1],commitAlias=t.isIdentifier(value,{name:aliasName})
   ||(t.isArrayExpression(value)&&value.elements.length===1&&t.isSpreadElement(value.elements[0])&&t.isIdentifier(value.elements[0].argument,{name:aliasName}));
  if(commit&&(!commitStatement||!commitAlias)){issue('Existing array commit value or control flow is unproven.');continue;}
  const stripped=t.cloneNode(target,true);
  if(commit)stripped.body.body.at(-1).consequent.body.splice(tail.consequent.body.indexOf(commitStatement),1);
  const strippedAlias=stripped.body.body[target.body.body.indexOf(alias.statement)];
  strippedAlias.declarations[0].init=t.cloneNode(alias.read,true);
  const normalizedTarget=normalize(stripped,false,fields,ids),shape=transaction(normalizedTarget,ids.get(field));
  if(!shape||!same(normalizedSource,normalizedTarget)){
   issue('Complete source array transaction guards, indices, effects or signature differ.');continue;
  }
  const astMethod=tree(stripped);let path;traverse(astMethod,{ObjectMethod(p){path=p;p.stop();}});
  const local=path.scope.getBinding(aliasName);let closed=!!local?.constant;
  for(const ref of local?.referencePaths||[]){const p=ref.parentPath,c=p.parentPath;
   if(!p.isMemberExpression()||p.node.object!==ref.node||p.node.computed||!c.isCallExpression()||c.node.callee!==p.node
    ||!['findIndex','splice'].includes(p.node.property.name)||c.node.optional)closed=false;
   if(p.node.property?.name==='findIndex'){
    const fn=c.node.arguments[0];if(c.node.arguments.length!==1||!t.isArrowFunctionExpression(fn)||fn.async||fn.params.length!==1||!t.isIdentifier(fn.params[0])
     ||!t.isBinaryExpression(fn.body,{operator:'==='})||![fn.body.left,fn.body.right].every(x=>t.isMemberExpression(x)&&!x.computed&&t.isIdentifier(x.object)&&t.isIdentifier(x.property)))closed=false;
   }
  }
  // No side effects between alias capture and removal: only index lookups/declarations.
  const start=target.body.body.indexOf(alias.statement),end=target.body.body.indexOf(tail);
  for(const stmt of target.body.body.slice(start+1,end)){
   if(!t.isVariableDeclaration(stmt)||stmt.declarations.some(d=>!t.isCallExpression(d.init)||!t.isMemberExpression(d.init.callee)
    ||!t.isIdentifier(d.init.callee.object,{name:aliasName})||!t.isIdentifier(d.init.callee.property,{name:'findIndex'})))closed=false;
  }
  if(!closed){issue('Array alias escapes, is reassigned, or crosses unknown effects.');continue;}
  const actualLast=tail.consequent.body.find(s=>t.isExpressionStatement(s)&&arrayCall(s.expression,aliasName,'splice'));
  // first splice is destructured; this is the unique standalone final insertion.
  if(!actualLast){issue('Final insertion statement is missing.');continue;}
  const committed=!!commit&&tail.consequent.body.indexOf(commitStatement)===tail.consequent.body.indexOf(actualLast)+1;
  const proof={contract,method:name,field,alias:aliasName,splice_count:2,copied_before_mutation:!!alias.copy,
    commit_immediately_after_last_splice:committed,proof:'exact_source_method_and_closed_two_splice_transaction'};
  result.proofs.push(proof);
  if(alias.copy&&committed)continue;
  issue('Detach the array before local splices and commit immediately after insertion, before following source effects.');
  if(!alias.copy)edits.push({start:offset+alias.declaration.init.start,end:offset+alias.declaration.init.end,text:'[...'+script.slice(alias.read.start,alias.read.end)+']'});
  if(commit)edits.push({start:offset+commitStatement.start,end:offset+commitStatement.end,text:''});
  edits.push({start:offset+actualLast.end,end:offset+actualLast.end,text:'\n      this.data.set('+JSON.stringify(field)+', [...'+aliasName+']);'});
 }
 edits.sort((a,b)=>b.start-a.start);for(let i=1;i<edits.length;i++)if(edits[i].end>edits[i-1].start)throw Error('Overlapping transaction edits');
 if(input.repair&&edits.length){for(const e of edits)result.code=result.code.slice(0,e.start)+e.text+result.code.slice(e.end);
  parser.parse(/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(result.code)[1],{sourceType:'unambiguous'});
  result.changes=['detached_and_committed_source_array_transaction'];}
 return result;
}
try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
catch(e){process.stdout.write(JSON.stringify({error:e.message}));}
