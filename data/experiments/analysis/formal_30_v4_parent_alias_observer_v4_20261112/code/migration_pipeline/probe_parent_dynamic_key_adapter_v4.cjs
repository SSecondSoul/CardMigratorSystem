/* Isolated bounded observer/receiver experiment. Never a production rule. */
'use strict';
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types');
const traverse=require('@babel/traverse').default;
const {run:baseRun}=require('./probe_parent_dynamic_key_adapter_v3.cjs');
const {createAliasBridge}=require('./probe_parent_alias_observer_v4.cjs');
const {parentOf}=require('./utils/inline_identifier_recovery.cjs');
const {one,print}=require('./utils/source_render_call_semantics.cjs');
const PREFIX='__aliasBridge_v4';
function run(input){
 const result={code:input.code,changes:[],reviews:[],writers:[],production_eligible:false,
  contract:'experimental_existing_plain_property_array_observer_native_receiver_v4',
  limitations:['Isolated opt-in only; no production diagnostic waiver or source API/schema restriction.',
   'Existing validated plain properties and dense-array mutators only; no full Vue observation/reflection contract.',
   'Observer descriptors and own non-enumerable array methods are observable; Proxy, refs, accessors, Symbols, cycles and arbitrary values remain unproven.',
   'Per-instance San Data.set receiver wrappers and pinned native child-tree traversal; no framework prototype patch or manual prop forwarding.',
   'Native deep Data.set identity, silent/force data API policies, exotic lifecycle trees and exception policy remain unclosed.',
   'Actual canonical TaskManager child/browser/CSS acceptance is not claimed.']};
 const decline=reason=>{result.reviews.push(reason);return result;};
 if(input.code.includes(PREFIX)||input.vue.includes(PREFIX))return decline('v4_marker_present_or_collision');
 const base=baseRun(input);if(!base.changes.length){result.reviews=base.reviews;return result;}
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(base.code);
 const ast=parser.parse(block[1],{sourceType:'unambiguous'}),parent=parentOf(ast);
 let shadowed=false;traverse(ast,{Scope(p){if(['Object','Array','Map','Set','WeakMap','TypeError'].some(n=>p.scope.hasOwnBinding(n)))shadowed=true;}});
 if(shadowed)return decline('shadowed_v4_observer_global');
 const init=one(parent,'inited'),attached=one(parent,'attached'),disposed=one(parent,'disposed');
 if(![init,attached,disposed].every(t.isObjectMethod)||one(parent,'updated'))return decline('unsupported_parent_lifecycle');
 const fixed=t.cloneNode(init,true);
 const index=fixed.body.body.findIndex(s=>t.isVariableDeclaration(s)&&s.declarations.some(d=>d.id.name?.startsWith('__dynamicKeyProbe_v1_')));
 if(index<0)return decline('missing_exact_v3_tail');
 fixed.body.body=fixed.body.body.slice(0,index);
 const rows=base.writers.map(({field,queue_index})=>({field,queue_index}));
 fixed.body.body.push(...parser.parse(`this.${PREFIX}Parent=${PREFIX}.parent(this,${JSON.stringify(rows)},enqueue);`).program.body);
 const edits=[{start:init.start,end:init.end,text:print(fixed)}];
 for(let i=0;i<base.writers.length;i++){
  const method=one(parent,base.writers[i].method);if(!t.isObjectMethod(method))return decline('missing_exact_v3_public_writer');
  const copy=t.cloneNode(method,true),oldCall=copy.body.body[0]?.expression;
  if(!t.isCallExpression(oldCall)||oldCall.arguments.length!==2)return decline('unexpected_v3_writer_call');
  // Preserve the SOURCE assignment RHS, including Number(value), conditions,
  // evaluation order and side effects. It is not necessarily the raw parameter.
  const replacement=parser.parse(`this.${PREFIX}Parent.write(${i},null,null);`).program.body[0];
  replacement.expression.arguments.splice(1,2,...oldCall.arguments.map(a=>t.cloneNode(a,true)));
  copy.body.body[0]=replacement;
  edits.push({start:method.start,end:method.end,text:print(copy)});
 }
 const attach=t.cloneNode(attached,true);attach.body.body.push(...parser.parse(`this.${PREFIX}Parent.attachReceivers();`).program.body);
 const dispose=t.cloneNode(disposed,true);dispose.body.body.unshift(...parser.parse(`this.${PREFIX}Parent.dispose();`).program.body);
 edits.push({start:attached.start,end:attached.end,text:print(attach)},
   {start:disposed.start,end:disposed.end,text:print(dispose)},
   {start:parent.end-1,end:parent.end-1,text:`,updated(){this.${PREFIX}Parent.attachReceivers();}`});
 const requireSan=ast.program.body.find(s=>t.isVariableDeclaration(s)&&s.declarations.some(d=>d.id.name==='san'));
 if(!requireSan)return decline('missing_san_binding');
 edits.push({start:requireSan.end,end:requireSan.end,text:`\nconst ${PREFIX}=(${createAliasBridge.toString()})(san);\n`});
 let script=block[1];for(const edit of edits.sort((a,b)=>b.start-a.start))script=script.slice(0,edit.start)+edit.text+script.slice(edit.end);
 parser.parse(script,{sourceType:'unambiguous'});
 const offset=block.index+block[0].indexOf('>')+1;
 result.code=base.code.slice(0,offset)+script+base.code.slice(offset+block[1].length);
 result.changes=['experimental_existing_property_array_observer_and_native_receiver_revision'];
 result.writers=base.writers;result.base_changes=base.changes;return result;
}
if(require.main===module){try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(e){process.stderr.write(e.stack);process.exitCode=1;}}
module.exports={run,PREFIX};
