/* Explicit source-matched composition; static raw assignment path experiment. */
'use strict';
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types'),traverse=require('@babel/traverse').default;
const {run:baseRun}=require('./probe_shape_observer_adapter_v10.cjs');
const {createShapeBridge:previous}=require('./probe_shape_observer_v10.cjs');
const {createShapeBridge}=require('./probe_source_path_assignment_v11.cjs');
const {same}=require('./utils/source_render_call_semantics.cjs');
function run(input){
 const result={code:input.code,changes:[],reviews:[],production_eligible:false,
  proof_scope:'isolated_raw_source_property_path_assignment',limitations:[
   'Experimental only: no production deployment, diagnostic waiver or template/style rewrite.',
   'Descriptor/accessor cases cover pure getters and stable setters; arbitrary accessor side effects remain unproven.',
   'False Ref markers are ordinary values; actual Ref unwrapping, foreign observers, Proxy and full reflection remain unproven.',
   'Only explicit raw assignment to static paths without options is mapped; force/silent/dynamic expressions are not source equivalence claims.',
   'Lifecycle-error routing remains open; the configured test application reporting scope is not a production bridge.']};
 const reject=reason=>{result.reviews.push(reason);return result;};
 if(input.experimental!==true)return reject('explicit_experimental_opt_in_required');
 const base=baseRun(input);if(!base.changes.length)return reject('requires_exact_source_v7_composition');
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/.exec(base.code);
 const ast=parser.parse(block[1]);let matches=[];
 const expected=parser.parseExpression('('+previous.toString()+')(san)');
 traverse(ast,{VariableDeclarator(p){if(t.isIdentifier(p.node.id,{name:'__aliasBridge_v4'})&&same(p.node.init,expected))matches.push(p.node.init);}});
 if(matches.length!==1)return reject('requires_exact_v10_factory');
 const found=matches[0],script=block[1].slice(0,found.start)+'('+createShapeBridge.toString()+')(san)'+block[1].slice(found.end);
 parser.parse(script);const offset=block.index+block[0].indexOf('>')+1;
 result.code=base.code.slice(0,offset)+script+base.code.slice(offset+block[1].length);
 result.changes=['experimental_source_raw_property_path_assignment'];result.writers=base.writers;return result;
}
if(require.main===module){try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(e){process.stderr.write(e.stack);process.exitCode=1;}}
module.exports={run};
