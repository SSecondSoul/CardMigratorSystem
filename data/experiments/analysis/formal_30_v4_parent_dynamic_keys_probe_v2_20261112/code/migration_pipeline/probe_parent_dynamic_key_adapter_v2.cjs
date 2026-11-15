/* Isolated v2: restore JSON-shaped nested values without changing the v1 writer.
 * Never imported by production stages; public object writes/deep reactivity and
 * error-policy compatibility remain unproven. Keep v1 and failed evidence intact.
 */
'use strict';
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types');
const traverse=require('@babel/traverse').default,{parse}=require('@vue/compiler-sfc');
const {run:baseRun,PREFIX:BASE_PREFIX}=require('./probe_parent_dynamic_key_adapter.cjs');
const {parentOf}=require('./utils/inline_identifier_recovery.cjs');
const {one,print,walk}=require('./utils/source_render_call_semantics.cjs');
const PREFIX='__dynamicKeyJsonRoot_v2_';
function run(input){
 const result={code:input.code,changes:[],reviews:[],writers:[],production_eligible:false,
  contract:'experimental_nested_json_root_scalar_writer_v2',
  limitations:['No production integration, source API restriction, or diagnostic waiver.',
   'Only observation bookkeeping accepts nested plain-data objects/dense arrays; it does not clone or coerce their values.',
   'Original string/scalar writer guard, prototype-key guard, enqueue and disposal are unchanged.',
   'Symbols, accessors, nonstandard prototypes, observer metadata, cyclic graphs and Proxy behavior are not proven.',
   'Public object-valued writes, external aliases/nested updates, actual child/DOM propagation and exception policy remain unclosed.',
   'Unsupported observation roots still fail the experimental guard; this is NOT an arbitrary-input source-equivalent public API.']};
 const decline=reason=>{result.reviews.push(reason);return result;};
 if(input.code.includes(PREFIX)||input.vue.includes(PREFIX))return decline('v2_marker_present_or_collision');
 const base=baseRun(input);
 if(!base.changes.length){result.reviews=base.reviews;return result;}
 const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(base.code);
 const ast=parser.parse(block[1],{sourceType:'unambiguous'});
 const sourceAst=parser.parse(parse(input.vue).descriptor.script.content,{sourceType:'unambiguous'});
 let shadowed=false;for(const tree of [ast,sourceAst])traverse(tree,{Scope(p){if(p.scope.hasOwnBinding('Array'))shadowed=true;}});
 if(shadowed)return decline('shadowed_v2_array_global');
 const init=one(parentOf(ast),'inited');if(!t.isObjectMethod(init))return decline('unrecognized_base_initialization');
 const fixed=t.cloneNode(init,true);
 for(let slot=0;slot<base.writers.length;slot++){
  const scalar=BASE_PREFIX+slot+'Scalar',remember=BASE_PREFIX+slot+'Remember',plain=BASE_PREFIX+slot+'Plain';
  const helper=PREFIX+slot;
  const index=fixed.body.body.findIndex(s=>t.isVariableDeclaration(s)&&s.declarations.some(d=>t.isIdentifier(d.id,{name:remember})));
  if(index<0)return decline('missing_exact_base_root_bookkeeping');
  let matches=0;walk(fixed.body.body[index],n=>{
   if(t.isCallExpression(n)&&t.isIdentifier(n.callee,{name:plain})&&n.arguments.length===1&&t.isIdentifier(n.arguments[0],{name:'object'})){
    n.callee=t.identifier(helper);matches++;
   }
  });
  if(matches!==1)return decline('ambiguous_base_observation_guard');
  const declaration=parser.parse(`const ${helper}=object=>{
    const visit=(value,parents)=>{
      if(${scalar}(value))return true;
      if(value===null||typeof value!=='object'||parents.indexOf(value)>=0)return false;
      const array=Array.isArray(value);
      if(Object.getPrototypeOf(value)!==(array?Array.prototype:Object.prototype))return false;
      if(Object.getOwnPropertySymbols(value).length)return false;
      const names=Object.getOwnPropertyNames(value);
      if(array&&names.length!==value.length+1)return false;
      return names.every(name=>{
        if(array&&name==='length')return true;
        if(array&&(!/^(0|[1-9][0-9]*)$/.test(name)||+name>=value.length))return false;
        const d=Object.getOwnPropertyDescriptor(value,name);
        return name!=='__ob__'&&d.enumerable&&d.configurable&&d.writable&&'value' in d
          &&visit(d.value,parents.concat([value]));
      });
    };
    return object!==null&&typeof object==='object'&&!Array.isArray(object)
      &&Object.getPrototypeOf(object)===Object.prototype&&visit(object,[]);
  };`).program.body[0];
  fixed.body.body.splice(index,0,declaration);
 }
 const script=block[1].slice(0,init.start)+print(fixed)+block[1].slice(init.end);
 parser.parse(script,{sourceType:'unambiguous'});
 const offset=block.index+block[0].indexOf('>')+1;
 result.code=base.code.slice(0,offset)+script+base.code.slice(offset+block[1].length);
 result.changes=['experimental_nested_json_root_observation_compatibility'];
 result.writers=base.writers;result.base_changes=base.changes;
 return result;
}
if(require.main===module){try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(error){process.stderr.write(error.stack);process.exitCode=1;}}
module.exports={run,PREFIX};
