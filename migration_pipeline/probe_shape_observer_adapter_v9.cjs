/* Explicit source-proven V7 -> V8 writer -> V9 observer experiment. */
'use strict';
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types'),traverse=require('@babel/traverse').default;
const {run:baseRun}=require('./probe_source_property_assignment_v8.cjs');
const {createAliasBridge}=require('./probe_parent_alias_observer_v4.cjs');
const {createShapeBridge}=require('./probe_shape_observer_v9.cjs');
const {parentOf}=require('./utils/inline_identifier_recovery.cjs');
const {one,print,same}=require('./utils/source_render_call_semantics.cjs');
function run(input){
 const result={code:input.code,changes:[],reviews:[],production_eligible:false,
  proof_scope:'isolated_source_skipped_values_and_dependency_recollection',limitations:[
   'Experimental only: no production diagnostic waiver, template rewrite or default deployment.',
   'Frozen/non-extensible and Date values are retained without observing; sparse array holes remain holes.',
   'Subscriptions are captured at initialization and before real callback dispatch, not guessed from current ancestry at mutation time.',
   'Custom accessors/prototypes, Ref/skip metadata, arbitrary external San Data APIs, Proxy and full reflection equivalence remain unproven.',
   'The experimental browser reporting scope remains explicitly configured by the test application, not a production bridge.']};
 const reject=reason=>{result.reviews.push(reason);return result;};
 if(input.experimental!==true)return reject('explicit_experimental_opt_in_required');
 const base=baseRun(input);if(!base.changes.length)return reject('requires_exact_source_v7_and_native_writer_match');
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/.exec(base.code);
 const ast=parser.parse(block[1]),parent=parentOf(ast),init=one(parent,'inited');
 let declaration;traverse(ast,{VariableDeclarator(p){if(t.isIdentifier(p.node.id,{name:'__aliasBridge_v4'}))declaration=p.node;}});
 const expected=parser.parseExpression('('+createAliasBridge.toString()+')(san)');
 if(!declaration||!same(declaration.init,expected)||!t.isObjectMethod(init))return reject('unknown_exact_v4_factory');
 const fixed=t.cloneNode(init,true);let replacements=0;
 const tree=t.file(t.program([t.expressionStatement(t.objectExpression([fixed]))]));
 traverse(tree,{ExpressionStatement(p){if(same(p.node,parser.parse('handlers[index]();').program.body[0])){
  p.insertBefore(parser.parse('this.__aliasBridge_v4Parent.refresh(index);').program.body[0]);replacements++;p.skip();
 }}});
 if(replacements!==1)return reject('unknown_exact_dispatch_entry');
 const edits=[{start:declaration.init.start,end:declaration.init.end,text:'('+createShapeBridge.toString()+')(san)'},
  {start:init.start,end:init.end,text:print(fixed)}];
 let script=block[1];for(const e of edits.sort((a,b)=>b.start-a.start))script=script.slice(0,e.start)+e.text+script.slice(e.end);
 parser.parse(script);const offset=block.index+block[0].indexOf('>')+1;
 result.code=base.code.slice(0,offset)+script+base.code.slice(offset+block[1].length);
 result.changes=['experimental_source_native_writer_and_shape_observer_recollection'];
 result.writers=base.writers;return result;
}
if(require.main===module){try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(e){process.stderr.write(e.stack);process.exitCode=1;}}
module.exports={run};
