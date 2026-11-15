/* Explicit, unpromoted browser error-context capability; keep v1-v5 frozen. */
'use strict';
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types'),traverse=require('@babel/traverse').default;
const {run:baseRun,POLICY:V5_POLICY}=require('./probe_parent_watch_error_router_v5.cjs');
const {createSourceErrorContext}=require('./probe_source_error_context_v6.cjs');
const {parentOf}=require('./utils/inline_identifier_recovery.cjs');
const {one,print}=require('./utils/source_render_call_semantics.cjs');
const PREFIX='__sourceErrorContext_v6',POLICY='mapped-browser-reporting-only-source-error-context';
function run(input){
 const result={code:input.code,changes:[],reviews:[],production_eligible:false,contract:POLICY,
  contextConfigureMethod:PREFIX+'Configure',
  limitations:['Explicit experimental opt-in, browser context and application-supplied parent/hook/config/logger mapping required.',
   'No source ancestor/config migration is inferred from a component SFC or San.error hooks.',
   'Only synchronous reporting-only hook bodies without reactive reads/writes; dependency suspension and reentrancy are unproven.',
   'Diagnostic text equivalence depends on the supplied logger; the core protocol does not implement Vue component-trace rendering.',
   'SSR/Node fallback, async/stateful hooks, arbitrary mappings and throwing diagnostic sinks remain unclosed.',
   'Missing context retains v5 behavior; production diagnostics, normal queue and all v4 observer limitations remain.']};
 const decline=reason=>{result.reviews.push(reason);return result;};
 if(input.error_context_policy!==POLICY)return decline('explicit_source_error_context_policy_required');
 if(input.code.includes(PREFIX)||input.vue.includes(PREFIX))return decline('source_context_marker_present_or_collision');
 const base=baseRun({...input,error_policy:V5_POLICY});if(!base.changes.length){result.reviews=base.reviews;return result;}
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(base.code);
 const ast=parser.parse(block[1],{sourceType:'unambiguous'}),parent=parentOf(ast),init=one(parent,'inited');
 let shadowed=false;traverse(ast,{Scope(p){if(['window','document'].some(n=>p.scope.hasOwnBinding(n)))shadowed=true;}});
 if(shadowed)return decline('shadowed_browser_context_global');
 const fixed=t.cloneNode(init,true);let count=0;
 function visit(n){if(!n||typeof n!=='object')return;
  if(t.isCatchClause(n)&&t.isIdentifier(n.param,{name:'__parentWatchError_v5Error'})){
   const info=parser.parseExpression(`'callback for watcher "'+${JSON.stringify(base.fields)}[index]+'"'`);
   const wrap=parser.parse(`if(this.${PREFIX}Active){this.${PREFIX}Active.handle(__parentWatchError_v5Error,this,null);}else{}`).program.body[0];
   wrap.consequent.body[0].expression.arguments[2]=info;
   wrap.alternate.body=n.body.body;n.body=t.blockStatement([wrap]);count++;return;
  }
  for(const [k,v] of Object.entries(n))if(!['loc','start','end','extra'].includes(k))Array.isArray(v)?v.forEach(visit):visit(v);
 }visit(fixed.body);
 if(count!==1)return decline('unknown_v5_dispatch_catch');
 const sanBinding=ast.program.body.find(s=>t.isVariableDeclaration(s)&&s.declarations.some(d=>d.id.name==='san'));
 if(!sanBinding)return decline('missing_san_binding');
 const edits=[{start:init.start,end:init.end,text:print(fixed)},
  {start:sanBinding.end,end:sanBinding.end,text:`\nconst ${PREFIX}Create=(${createSourceErrorContext.toString()});\n`},
  {start:parent.end-1,end:parent.end-1,text:`,${PREFIX}Configure(binding){this.${PREFIX}Active=${PREFIX}Create(binding);}`}];
 let script=block[1];for(const e of edits.sort((a,b)=>b.start-a.start))script=script.slice(0,e.start)+e.text+script.slice(e.end);
 parser.parse(script,{sourceType:'unambiguous'});const offset=block.index+block[0].indexOf('>')+1;
 result.code=base.code.slice(0,offset)+script+base.code.slice(offset+block[1].length);
 result.changes=['experimental_mapped_browser_source_error_context'];result.fields=base.fields;result.base_changes=base.changes;return result;
}
if(require.main===module){try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(e){process.stderr.write(e.stack);process.exitCode=1;}}
module.exports={run,PREFIX,POLICY};
