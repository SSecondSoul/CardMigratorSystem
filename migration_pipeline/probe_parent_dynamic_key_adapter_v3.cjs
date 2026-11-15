/* Isolated value-compatibility experiment, NOT production integration.
 * Preserve v1/v2 and their frozen evidence. Accept bounded plain-data values;
 * do not pretend to implement Vue Ref/Proxy/deep-alias observation semantics.
 */
'use strict';
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types');
const {run:baseRun}=require('./probe_parent_dynamic_key_adapter_v2.cjs');
const {PREFIX:BASE_PREFIX}=require('./probe_parent_dynamic_key_adapter.cjs');
const {PREFIX:ROOT_PREFIX}=require('./probe_parent_dynamic_key_adapter_v2.cjs');
const {parentOf}=require('./utils/inline_identifier_recovery.cjs');
const {one,print,same}=require('./utils/source_render_call_semantics.cjs');
const PREFIX='__dynamicKeyJsonValue_v3_';
function run(input){
 const result={code:input.code,changes:[],reviews:[],writers:[],production_eligible:false,
  contract:'experimental_plain_data_object_array_value_assignment_v3',
  limitations:['No production integration or source API/schema restriction.',
   'Bounded plain-data object/array assignment only; preserve the caller value identity without cloning or coercion.',
   'Existing __proto__ guard, notification tail, queue, root-key bookkeeping and disposal remain unchanged.',
   'Ref-like markers, observer metadata, accessors, Symbols, cyclic/exotic objects and Proxy behavior are not supported/proven.',
   'Borrowed-value nested mutation, deep reactivity, reflection, actual child/DOM propagation and exception policy remain unclosed.',
   'Experimental refusal of unsupported inputs is NOT arbitrary-input source API equivalence.']};
 const decline=reason=>{result.reviews.push(reason);return result;};
 if(input.code.includes(PREFIX)||input.vue.includes(PREFIX))return decline('v3_marker_present_or_collision');
 const base=baseRun(input);if(!base.changes.length){result.reviews=base.reviews;return result;}
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(base.code);
 const ast=parser.parse(block[1],{sourceType:'unambiguous'}),init=one(parentOf(ast),'inited');
 if(!t.isObjectMethod(init))return decline('unrecognized_v2_initialization');
 const fixed=t.cloneNode(init,true);
 for(let slot=0;slot<base.writers.length;slot++){
  const scalar=BASE_PREFIX+slot+'Scalar',plain=BASE_PREFIX+slot+'Plain',writer=BASE_PREFIX+slot+'Write';
  const helper=PREFIX+slot,rootHelper=ROOT_PREFIX+slot;
  const statements=fixed.body.body;
  const index=statements.findIndex(s=>t.isExpressionStatement(s)&&t.isAssignmentExpression(s.expression,{operator:'='})
   &&t.isMemberExpression(s.expression.left)&&!s.expression.left.computed&&t.isThisExpression(s.expression.left.object)
   &&t.isIdentifier(s.expression.left.property,{name:writer})&&t.isArrowFunctionExpression(s.expression.right));
  if(index<0)return decline('missing_exact_v2_writer');
  const fn=statements[index].expression.right,guard=fn.body.body[0];
  const expected=parser.parseExpression(`typeof key!=='string'||key==='__ob__'||(!${scalar}(value)&&!(key==='__proto__'&&${plain}(value)))`);
  if(!t.isIfStatement(guard)||!same(guard.test,expected))return decline('unexpected_v2_value_guard');
  const writeIndex=fn.body.body.findIndex(s=>t.isExpressionStatement(s)&&same(s,parser.parse('object[key]=value;').program.body[0]));
  if(writeIndex!==4)return decline('unexpected_v2_assignment_scope');
  guard.test=parser.parseExpression(`typeof key!=='string'||key==='__ob__'||(!${scalar}(value)&&!(key==='__proto__'?${plain}(value):${helper}(value)))`);
  // Vue's existing-ref setter can update .value rather than replace the field.
  // Do not silently treat those restored/external states as ordinary data.
  fn.body.body.splice(writeIndex,0,parser.parse(`if(reactive&&!${scalar}(previous)&&!${helper}(previous))
    throw new TypeError('Dynamic-key probe: unsupported previous reactive value');`).program.body[0]);
  const declaration=parser.parse(`const ${helper}=value=>{
    if(!${rootHelper}({value}))return false;
    const noRefs=node=>{
      if(node===null||typeof node!=='object')return true;
      if(Object.prototype.hasOwnProperty.call(node,'__v_isRef'))return false;
      return Object.keys(node).every(name=>noRefs(Object.getOwnPropertyDescriptor(node,name).value));
    };
    return noRefs(value);
  };`).program.body[0];
  statements.splice(index,0,declaration);
 }
 const script=block[1].slice(0,init.start)+print(fixed)+block[1].slice(init.end);
 parser.parse(script,{sourceType:'unambiguous'});
 const offset=block.index+block[0].indexOf('>')+1;
 result.code=base.code.slice(0,offset)+script+base.code.slice(offset+block[1].length);
 result.changes=['experimental_plain_data_object_array_assignment_compatibility'];
 result.base_changes=base.changes;result.writers=base.writers;return result;
}
if(require.main===module){try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(error){process.stderr.write(error.stack);process.exitCode=1;}}
module.exports={run,PREFIX};
