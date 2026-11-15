/* ISOLATED opt-in for an explicitly supplied RETURNING application reporter.
 * No default logger, global framework config, storage retry or Promise catch.
 * Reporter absence/throw still escapes; neither is claimed source-equivalent.
 */
'use strict';
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types');
const {run:baseRun}=require('./probe_parent_dynamic_key_adapter_v4.cjs');
const {run:assess}=require('./utils/source_parent_watch_semantics.cjs');
const {parentOf}=require('./utils/inline_identifier_recovery.cjs');
const {one,print,same}=require('./utils/source_render_call_semantics.cjs');
const PREFIX='__parentWatchError_v5',POLICY='explicit-returning-application-reporter';
function run(input){
 const result={code:input.code,changes:[],reviews:[],production_eligible:false,
  contract:POLICY,reporterConfigureMethod:PREFIX+'Configure',
  limitations:['Explicit experimental opt-in AND returning-application-reporter policy required.',
   'Only synchronous reporting-only callbacks; reporter component-state reads/writes, reentrancy and async behavior are not proven.',
   'Application must configure a reporter per instance before startup; no reporter is synthesized or silently installed.',
   'Only synchronous watcher callback exceptions are routed; failing callback tail is not resumed.',
   'No catch on the queue Promise; missing or throwing reporter still escapes and is not equivalent to Vue global fallback.',
   'Vue errorCaptured chains, browser/SSR defaults, throwing/async reporters, lifecycle/event errors, dependency tracking and reflection remain unproven.',
   'All v4 observer limitations and production boundary diagnostics remain.']};
 const decline=reason=>{result.reviews.push(reason);return result;};
 if(input.error_policy!==POLICY)return decline('explicit_application_error_policy_required');
 if(input.code.includes(PREFIX)||input.vue.includes(PREFIX))return decline('error_router_marker_present_or_collision');
 const base=baseRun(input);if(!base.changes.length){result.reviews=base.reviews;return result;}
 const proof=assess({code:input.code,vue:input.vue});
 if(proof.error||proof.proofs.length!==1)return decline('missing_exact_source_watch_group');
 const fields=proof.proofs[0].fields;
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(base.code);
 const ast=parser.parse(block[1],{sourceType:'unambiguous'}),parent=parentOf(ast),init=one(parent,'inited');
 if(!t.isObjectMethod(init))return decline('unknown_parent_init');
 const fixed=t.cloneNode(init,true),expected=parser.parse('handlers[index]();').program.body[0];
 let replacements=0;
 function visit(node){
  if(!node||typeof node!=='object')return;
  for(const [key,value] of Object.entries(node)){
   if(['loc','start','end','extra'].includes(key))continue;
   if(Array.isArray(value))for(let i=0;i<value.length;i++){
    if(same(value[i],expected)){
     value[i]=parser.parse(`try{handlers[index]();}catch(${PREFIX}Error){
       const ${PREFIX}Report=this.${PREFIX}Reporter;
       if(typeof ${PREFIX}Report!=='function')throw ${PREFIX}Error;
       ${PREFIX}Report.call(null,${PREFIX}Error,this,'callback for watcher "'+${JSON.stringify(fields)}[index]+'"');
     }`).program.body[0];replacements++;
    }else visit(value[i]);
   }else visit(value);
  }
 }
 visit(fixed.body);
 if(replacements!==1)return decline('unknown_queue_dispatch_shape');
 const configure=`,${PREFIX}Configure(reporter){
   if(reporter!==null&&typeof reporter!=='function')throw new TypeError('Watcher v5 probe: reporter must be a function or null');
   this.${PREFIX}Reporter=reporter;
 }`;
 const edits=[{start:init.start,end:init.end,text:print(fixed)},{start:parent.end-1,end:parent.end-1,text:configure}];
 let script=block[1];for(const edit of edits.sort((a,b)=>b.start-a.start))script=script.slice(0,edit.start)+edit.text+script.slice(edit.end);
 parser.parse(script,{sourceType:'unambiguous'});
 const offset=block.index+block[0].indexOf('>')+1;
 result.code=base.code.slice(0,offset)+script+base.code.slice(offset+block[1].length);
 result.changes=['experimental_per_watcher_explicit_returning_error_reporter'];
 result.fields=fields;result.base_changes=base.changes;return result;
}
if(require.main===module){try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(e){process.stderr.write(e.stack);process.exitCode=1;}}
module.exports={run,PREFIX,POLICY};
