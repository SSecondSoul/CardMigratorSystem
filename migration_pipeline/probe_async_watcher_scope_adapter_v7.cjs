/* Isolated v7: route only from a private Promise-entered watcher scope. */
'use strict';
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types'),traverse=require('@babel/traverse').default;
const {run:baseRun,POLICY:V5_POLICY}=require('./probe_parent_watch_error_router_v5.cjs');
const {createSourceErrorContext}=require('./probe_source_error_context_v6.cjs');
const {createAsyncWatcherScope}=require('./probe_async_watcher_scope_v7.cjs');
const {parentOf}=require('./utils/inline_identifier_recovery.cjs');
const {one,print,same}=require('./utils/source_render_call_semantics.cjs');
const PREFIX='__watcherScope_v7',POLICY='private-async-parent-watch-source-context';
function run(input){
 const result={code:input.code,changes:[],reviews:[],production_eligible:false,contract:POLICY,
  contextConfigureMethod:PREFIX+'Configure',limitations:[
   'Experimental only; explicit browser async-parent-watch reporting-only binding required before first enqueue.',
   'Private scope schedules its own Promise entry; no public context.handle, scope.run or route capability on the component.',
   'Configuration is locked at first schedule; disposed/invalid/out-of-scope calls are refused.',
   'Application capability functions are trusted: reactive purity, async hook effects and arbitrary mapping correctness are NOT enforced.',
   'No generalized dependency suspension, SSR/default production policy or diagnostic renderer; all v4-v6 limitations and production diagnostics remain.',
   'Missing binding retains original v5 explicit-reporter/rethrow behavior. No production integration.']};
 const decline=why=>{result.reviews.push(why);return result;};
 if(input.error_context_policy!==POLICY)return decline('explicit_async_scope_policy_required');
 if(input.code.includes(PREFIX)||input.vue.includes(PREFIX)||input.code.includes('__sourceErrorContext_v6'))return decline('scope_marker_present_or_collision');
 const base=baseRun({...input,error_policy:V5_POLICY});if(!base.changes.length){result.reviews=base.reviews;return result;}
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(base.code);
 const ast=parser.parse(block[1],{sourceType:'unambiguous'}),parent=parentOf(ast),init=one(parent,'inited');
 let shadowed=false;traverse(ast,{Scope(p){if(['Object','Number','Promise','window','Set','TypeError'].some(n=>p.scope.hasOwnBinding(n)))shadowed=true;}});
 if(shadowed)return decline('shadowed_scope_global');
 const fixed=t.cloneNode(init,true),schedule=parser.parseExpression('Promise.resolve().then(flush)');let catches=0,schedules=0;
 function visit(n){if(!n||typeof n!=='object')return;
  if(t.isCatchClause(n)&&t.isIdentifier(n.param,{name:'__parentWatchError_v5Error'})){
   const wrap=parser.parse(`if(!${PREFIX}Local.route(__parentWatchError_v5Error,index)){}`).program.body[0];
   wrap.consequent=n.body;n.body=t.blockStatement([wrap]);catches++;return;
  }
  for(const [k,v] of Object.entries(n)){
   if(['loc','start','end','extra'].includes(k))continue;
   if(t.isCallExpression(v)&&same(v,schedule)){
    n[k]=parser.parseExpression(`${PREFIX}Local.schedule(flush)`);schedules++;
   }else if(Array.isArray(v))v.forEach(visit);else visit(v);
  }
 }visit(fixed.body);
 if(catches!==1||schedules!==1)return decline('unknown_exact_async_dispatch_shape');
 fixed.body.body.unshift(...parser.parse(`const ${PREFIX}Local=${PREFIX}Create(__sourceErrorContext_v6Create,this,${JSON.stringify(base.fields)});
 this.${PREFIX}Configure=binding=>${PREFIX}Local.configure(binding);`).program.body);
 fixed.body.body.push(...parser.parse(`const ${PREFIX}Dispose=this.__sourceParentWatchDispose_v1;
 this.__sourceParentWatchDispose_v1=()=>{${PREFIX}Local.dispose();${PREFIX}Dispose();};`).program.body);
 const sanBinding=ast.program.body.find(s=>t.isVariableDeclaration(s)&&s.declarations.some(d=>d.id.name==='san'));
 if(!sanBinding)return decline('missing_san_binding');
 const edits=[{start:init.start,end:init.end,text:print(fixed)},
  {start:sanBinding.end,end:sanBinding.end,text:`\nconst __sourceErrorContext_v6Create=(${createSourceErrorContext.toString()});\nconst ${PREFIX}Create=(${createAsyncWatcherScope.toString()});\n`}];
 let script=block[1];for(const e of edits.sort((a,b)=>b.start-a.start))script=script.slice(0,e.start)+e.text+script.slice(e.end);
 parser.parse(script,{sourceType:'unambiguous'});const offset=block.index+block[0].indexOf('>')+1;
 result.code=base.code.slice(0,offset)+script+base.code.slice(offset+block[1].length);
 result.changes=['experimental_private_async_watcher_context_scope'];result.fields=base.fields;result.base_changes=base.changes;return result;
}
if(require.main===module){try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(e){process.stderr.write(e.stack);process.exitCode=1;}}
module.exports={run,PREFIX,POLICY};
