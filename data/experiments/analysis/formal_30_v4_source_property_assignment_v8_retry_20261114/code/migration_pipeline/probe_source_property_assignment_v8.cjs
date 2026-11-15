/* Experimental source-native writer restoration. No production integration.
 * Only an already exact V7 composition is accepted; observer gaps stay open.
 */
'use strict';
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types'),{parse}=require('@vue/compiler-sfc');
const {parentOf,key}=require('./utils/inline_identifier_recovery.cjs');
const {one,sourceParent,print}=require('./utils/source_render_call_semantics.cjs');
const {inspection:{sourceSpec}}=require('./utils/source_parent_watch_semantics.cjs');
const {run:inspect}=require('./utils/v7_source_queue_contract.cjs');
function run(input){
 const result={code:input.code,changes:[],reviews:[],production_eligible:false,
  proof_scope:'source_assignment_statement_only_not_observer_or_error_equivalence',writers:[],
  limitations:['Experimental opt-in only; no source API/key whitelist and no global/framework patch.',
   'Restores native source property-key conversion, assignment and strict method execution; matched notification tail is retained.',
   'Existing observed-value setters still reject some source-supported values; stale observer subscription and error bridge gaps remain.',
   'No production diagnostic waiver, no complete dynamic-shape/reflection equivalence claim.']};
 const reject=reason=>{result.reviews.push(reason);return result;};
 if(input.experimental!==true)return reject('explicit_experimental_opt_in_required');
 const inspected=inspect(input);
 if(!inspected.queue_lifecycle_structure_matched)return reject('requires_exact_source_matched_v7_composition');
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/.exec(input.code);
 const ast=parser.parse(block[1],{sourceType:'unambiguous'}),parent=parentOf(ast);
 const source=sourceParent(parser.parse(parse(input.vue).descriptor.script.content,{sourceType:'module'})),spec=sourceSpec(source);
 const edits=[];
 for(const original of spec.methods.properties){
  const assignment=original.body?.body[0]?.expression,lhs=assignment?.left;
  if(!t.isAssignmentExpression(assignment,{operator:'='})||!t.isMemberExpression(lhs)||!lhs.computed
   ||!t.isMemberExpression(lhs.object)||lhs.object.computed||!t.isThisExpression(lhs.object.object)
   ||!spec.rows.some(r=>r.field===lhs.object.property.name))continue;
  const target=one(parent,key(original)),copy=t.cloneNode(target,true),restored=t.cloneNode(assignment,true);
  // Preserve the source assignment as one native expression. In particular do
  // not coerce keys in a different statement or evaluate RHS before LHS.
  restored.left.object=t.callExpression(t.memberExpression(t.memberExpression(t.thisExpression(),t.identifier('data')),t.identifier('get')),
   [t.stringLiteral(lhs.object.property.name)]);
  copy.body.body[0]=t.expressionStatement(restored);
  // The Vue source is an ES module. CommonJS/new Function loaders otherwise
  // silently turn failed native assignments into non-strict no-ops.
  copy.body.directives=[t.directive(t.directiveLiteral('use strict'))];
  edits.push({start:target.start,end:target.end,text:print(copy)});
  result.writers.push({method:key(original),field:lhs.object.property.name,source_assignment_and_strict_mode_retained:true});
 }
 if(!edits.length)return reject('no_source_assignment_writer');
 let script=block[1];for(const e of edits.sort((a,b)=>b.start-a.start))script=script.slice(0,e.start)+e.text+script.slice(e.end);
 parser.parse(script,{sourceType:'unambiguous'});
 const offset=block.index+block[0].indexOf('>')+1;
 result.code=input.code.slice(0,offset)+script+input.code.slice(offset+block[1].length);
 result.changes=['experimental_restored_source_native_property_assignment'];return result;
}
if(require.main===module){try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(e){process.stderr.write(e.stack);process.exitCode=1;}}
module.exports={run};
