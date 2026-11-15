/* Read-only structural obligations for the exact experimental V7 composition.
 * NOT imported by production validation/repair. No source API equivalence waiver.
 * Known ASTs are compared in full; marker names alone never establish a match.
 */
'use strict';
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types');
const traverse=require('@babel/traverse').default,{parse}=require('@vue/compiler-sfc');
const {parentOf,key}=require('./inline_identifier_recovery.cjs');
const {one,safe,same,sourceParent,walk}=require('./source_render_call_semantics.cjs');
const {normalize,inspection:{sourceSpec,callbacks,graph,readonlyMethods}}=require('./source_parent_watch_semantics.cjs');
const {createAsyncWatcherScope}=require('../probe_async_watcher_scope_v7.cjs');
const {createSourceErrorContext}=require('../probe_source_error_context_v6.cjs');
const {createAliasBridge}=require('../probe_parent_alias_observer_v4.cjs');
const S='__watcherScope_v7',E='__parentWatchError_v5',A='__aliasBridge_v4',D='__sourceParentWatchDispose_v1';
const statements=s=>parser.parse(s).program.body;
const method=(o,k)=>{const p=one(o,k);return t.isObjectMethod(p)&&p.kind==='method'&&!p.async&&!p.generator?p:null;};
const renamed=(m,name)=>{const copy=t.cloneNode(m,true);copy.key=t.identifier(name);return copy;};
const listSame=(a,b)=>same(t.program(a),t.program(b));
function expectedInit(spec,rows){
 const init=callbacks(spec);
 // Rebuild from source, not from a target marker or a mutable extracted handler.
 const tree=t.file(t.program([t.expressionStatement(t.objectExpression([init]))]));
 traverse(tree,{ExpressionStatement(p){
  if(same(p.node,statements('handlers[index]();')[0])){
   p.replaceWith(statements(`try{handlers[index]();}catch(${E}Error){
    if(!${S}Local.route(${E}Error,index)){
     const ${E}Report=this.${E}Reporter;
     if(typeof ${E}Report!=='function')throw ${E}Error;
     ${E}Report.call(null,${E}Error,this,'callback for watcher "'+${JSON.stringify(spec.rows.map(r=>r.field))}[index]+'"');
    }} `)[0]);p.skip();
  }
 },CallExpression(p){if(same(p.node,parser.parseExpression('Promise.resolve().then(flush)'))){
  p.replaceWith(parser.parseExpression(`${S}Local.schedule(flush)`));p.skip();
 }}});
 init.body.body.unshift(...statements(`const ${S}Local=${S}Create(__sourceErrorContext_v6Create,this,${JSON.stringify(spec.rows.map(r=>r.field))});
 this.${S}Configure=binding=>${S}Local.configure(binding);`));
 init.body.body.push(...statements(`this.${A}Parent=${A}.parent(this,${JSON.stringify(rows.map(({field,queue_index})=>({field,queue_index})))},enqueue);
 const ${S}Dispose=this.${D};this.${D}=()=>{${S}Local.dispose();${S}Dispose();};`));
 return init;
}
function run(input){
 const result={queue_lifecycle_structure_matched:false,source_equivalence_proven:false,production_eligible:false,
  changes:[],reviews:[],checks:{},remaining_production_codes:[],limitations:[
   'Read-only experimental structural inspection, not a production semantic proof or automatic diagnostic waiver.',
   'Dynamic key/shape/alias observer behavior and application error binding/purity are NOT proven.',
   'Assumes pinned ordinary framework/global runtime; arbitrary JS side channels or monkey patches are outside this inspection.']};
 const reject=reason=>{result.reviews.push(reason);return result;};
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(input.code||''),source=parse(input.vue||'');
 if(!block||source.errors.length||!source.descriptor.script||source.descriptor.scriptSetup)return reject('missing_plain_source_script');
 let ast,srcAst;
 try{ast=parser.parse(block[1],{sourceType:'unambiguous'});srcAst=parser.parse(source.descriptor.script.content,{sourceType:'unambiguous'});}
 catch(_){return reject('parse_failed');}
 const parent=parentOf(ast),original=sourceParent(srcAst),spec=sourceSpec(original);
 if(!safe(parent)||!spec)return reject('unsupported_source_or_parent');
 const production=require('./source_parent_watch_semantics.cjs').run(input);
 result.remaining_production_codes=[...new Set(production.findings.map(f=>f.code))].sort();
 result.fields=spec.rows.map(r=>r.field);result.contract='script.parent.watch@'+result.fields.join(',');
 const init=method(parent,'inited'),attached=method(parent,'attached'),disposed=method(parent,'disposed'),data=method(parent,'initData');
 if(!init||!attached||!disposed||!data)return reject('missing_exact_lifecycle');
 const rows=[];
 for(const m of spec.methods.properties){
  const assignment=m.body?.body[0]?.expression,lhs=assignment?.left;
  if(!t.isAssignmentExpression(assignment,{operator:'='})||!t.isMemberExpression(lhs)||!lhs.computed
   ||!t.isMemberExpression(lhs.object)||lhs.object.computed||!t.isThisExpression(lhs.object.object)
   ||!spec.rows.some(r=>r.field===lhs.object.property.name))continue;
  if(!t.isObjectMethod(m)||m.params.length!==2||!m.params.every(t.isIdentifier)
   ||!t.isIdentifier(lhs.property,{name:m.params[0].name}))return reject('unsupported_dynamic_writer_structure');
  rows.push({method:key(m),field:lhs.object.property.name,queue_index:result.fields.indexOf(lhs.object.property.name),source:m,assignment});
 }
 if(!rows.length)return reject('missing_v4_composition_writer');
 // Full source-derived queue includes every registration in declaration order,
 // one private dispatch, cleanup, and known observer installation before attach.
 result.checks.queue_and_private_scope=same(init,expectedInit(spec,rows));
 if(!result.checks.queue_and_private_scope)return reject('source_queue_or_private_scope_mismatch');
 const attach=t.cloneNode(attached,true),dispose=t.cloneNode(disposed,true);
 const attachTail=statements(`this.${A}Parent.attachReceivers();`),disposeHead=statements(`this.${A}Parent.dispose();this.${D}();`);
 if(!listSame(attach.body.body.slice(-1),attachTail)||!listSame(dispose.body.body.slice(0,2),disposeHead))return reject('lifecycle_wrapper_mismatch');
 attach.body.body.pop();dispose.body.body.splice(0,2);
 result.checks.source_data_and_lifecycle=same(renamed(data,'data'),spec.data)
  &&same(renamed(normalize(attach,spec.fields),'mounted'),spec.mounted)
  &&same(renamed(normalize(dispose,spec.fields),'beforeDestroy'),spec.destroyed);
 const updated=method(parent,'updated');
 const expectedUpdated=parser.parseExpression(`({updated(){this.${A}Parent.attachReceivers();}})`).properties[0];
 if(!result.checks.source_data_and_lifecycle||!updated||!same(updated,expectedUpdated))return reject('source_data_or_lifecycle_mismatch');
 const effects=graph(spec,[...spec.rows.map(r=>r.handler),spec.mounted,spec.destroyed],parent);
 result.checks.source_transitive_effects=effects.ok;result.effect_methods=effects.methods;
 if(!effects.ok)return reject(effects.reason);
 // No promise of bridge semantics: this checks only source RHS/evaluation order
 // and notification tail, without restricting the source's public key domain.
 const writerNodes=[];
 for(let index=0;index<rows.length;index++){
  const row=rows[index],target=method(parent,row.method);
  if(!target)return reject('missing_writer');
  const copy=t.cloneNode(target,true),expected=statements(`this.${A}Parent.write(${index},null,null);`)[0];
  expected.expression.arguments.splice(1,2,t.cloneNode(row.source.params[0]),t.cloneNode(row.assignment.right,true));
  if(!same(copy.body.body[0],expected))return reject('source_writer_arguments_mismatch');
  copy.body.body[0]=t.expressionStatement(t.cloneNode(row.assignment,true));
  if(!same(normalize(copy,spec.fields,readonlyMethods(spec)),row.source))return reject('source_writer_tail_mismatch');
  writerNodes.push(target);
 }
 result.checks.writer_invocation_structure_only=true;
 const reporter=method(parent,E+'Configure');
 const expectedReporter=parser.parseExpression(`({${E}Configure(reporter){
 if(reporter!==null&&typeof reporter!=='function')throw new TypeError('Watcher v5 probe: reporter must be a function or null');
 this.${E}Reporter=reporter;}})`).properties[0];
 if(!reporter||!same(reporter,expectedReporter))return reject('legacy_fallback_configuration_mismatch');
 const factorySpecs=[
  [S+'Create',parser.parseExpression('('+createAsyncWatcherScope.toString()+')')],
  ['__sourceErrorContext_v6Create',parser.parseExpression('('+createSourceErrorContext.toString()+')')],
  [A,parser.parseExpression('('+createAliasBridge.toString()+')(san)')]
 ];
 const known=[init,attached,disposed,updated,reporter,...writerNodes],factoryNodes=[];
 let program;traverse(ast,{Program(p){program=p;p.stop();}});
 for(const [name,expected] of factorySpecs){
  const binding=program.scope.getBinding(name),p=binding?.path;
  if(!binding?.constant||!p.isVariableDeclarator()||p.parent.kind!=='const'||p.parent.declarations.length!==1
   ||!p.parentPath.parentPath.isProgram()||p.node.end>=parent.start||!same(p.node.init,expected))return reject('factory_definition_or_binding_mismatch:'+name);
  // Every outer factory/bridge reference must belong to an exact matched node.
  if(binding.referencePaths.some(ref=>!known.some(n=>ref.node.start>=n.start&&ref.node.end<=n.end)))return reject('escaped_factory_reference:'+name);
  factoryNodes.push(p.node);
 }
 result.checks.exact_factory_definitions_and_references=true;
 // Reject global shadowing, framework overwrites, unknown phase hooks, and
 // experimental member access outside the fully matched nodes. Not a sandbox.
 const globals=['Promise','Object','Number','Array','WeakMap','Set','Map','TypeError','window','localStorage',
  'Date','JSON','setInterval','clearInterval','setTimeout','clearTimeout','undefined'];
 let unsafe=false;
 for(const tree of [ast,srcAst])traverse(tree,{Scope(p){if(globals.some(n=>p.scope.hasOwnBinding(n)))unsafe=true;}});
 const san=program.scope.getBinding('san');
 if(!san?.constant||!san.path.isVariableDeclarator()||!same(san.path.node.init,parser.parseExpression('require("san")'))
  ||san.path.scope.getBinding('require'))unsafe=true;
 for(const prop of parent.properties){
  if(known.includes(prop))continue;
  if(['watch','created','compiled','beforeCreate','beforeMount','mixins','extends','error'].includes(key(prop)))unsafe=true;
 }
 walk(ast,n=>{
  if(t.isAssignmentExpression(n)||t.isUpdateExpression(n)){
   let left=t.isAssignmentExpression(n)?n.left:n.argument;while(t.isMemberExpression(left))left=left.object;
   if(t.isIdentifier(left,{name:'san'}))unsafe=true;
  }
  if(t.isMemberExpression(n)&&t.isThisExpression(n.object)){
   const allowed=known.some(p=>n.start>=p.start&&n.end<=p.end)||factoryNodes.some(p=>n.start>=p.start&&n.end<=p.end);
   if(n.computed||(!allowed&&[S,E,A,D].some(prefix=>n.property.name?.startsWith(prefix))))unsafe=true;
  }
 });
 if(unsafe)return reject('shadowed_global_unknown_hook_or_escaped_control');
 result.checks.closed_known_control_references=true;
 result.queue_lifecycle_structure_matched=true;
 return result;
}
if(require.main===module){try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(e){process.stdout.write(JSON.stringify({error:e.message,queue_lifecycle_structure_matched:false,production_eligible:false}));}}
module.exports={run};
