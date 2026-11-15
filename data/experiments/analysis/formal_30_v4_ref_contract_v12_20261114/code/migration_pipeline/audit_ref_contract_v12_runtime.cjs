/* Test inputs only: genuine pinned Vue refs are constructed in BOTH realms.
 * On San the extra Vue runtime only constructs incoming values: no Vue parent,
 * render, watch or effect is used to supply the candidate's missing behavior.
 */
'use strict';
const fs=require('fs'),crypto=require('crypto'),Module=require('module');
const filename=require.resolve('./audit_v7_dynamic_shape_runtime.cjs');
const original=fs.readFileSync(filename,'utf8'),expected='cd1ba81e7e524966ab84012b317bc9ec9c429215e96381f1bfc237e0edf90122';
if(crypto.createHash('sha256').update(original).digest('hex')!==expected)throw Error('Frozen device drift');
let generated=original;
function inject(anchor,replacement){if(generated.split(anchor).length!==2)throw Error('Nonunique device anchor');generated=generated.replace(anchor,replacement);}
inject("c.existing=task?'notifications':'enabled';",`const refAPI=isSource?runtime:evaluate(input.vueRuntime,c),createdRefs=[];
c.makeRef=(value,shallow=false)=>{const r=shallow?refAPI.shallowRef(value):refAPI.ref(value);createdRefs.push(r);return r;};
const subscriberCounts=()=>createdRefs.map(r=>r.dep.subs.filter(Boolean).length);
c.existing=task?'notifications':'enabled';`);
inject("phase='dispose';events=[];errors.length=0;warnings.length=0;", "const refSubscribersBeforeDispose=subscriberCounts();phase='dispose';events=[];errors.length=0;warnings.length=0;");
inject('hostPrototypeClean:!', 'refSubscribersBeforeDispose,refSubscribersAfterDispose:subscriberCounts(),hostPrototypeClean:!');
const device=new Module(filename,module);device.filename=filename;device.paths=Module._nodeModulePaths(__dirname);device._compile(generated,filename);
const scenarios=[
 {name:'marker_object_unwrap',actions:["held={__v_isRef:true,value:{name:'raw'}};write('extra',held);mark('unwrapped-identity:'+(root().extra===held.value));","root().extra.name='changed';"]},
 {name:'marker_writeback_keeps_ref',actions:["held={__v_isRef:true,value:'initial'};write('extra',held);","write('extra','changed');mark('writeback:'+held.value);"]},
 {name:'marker_value_mutation_is_raw',actions:["held={__v_isRef:true,value:'initial'};write('extra',held);","held.value='changed';"]},
 {name:'marker_ref_replacement',actions:["held={__v_isRef:true,value:'first'};write('extra',held);","write('extra',{__v_isRef:true,value:'second'});mark('old-value:'+held.value);"]},
 {name:'marker_no_value',actions:["write('extra',{__v_isRef:true});","write('extra',7);"]},
 {name:'marker_false_not_unwrapped',actions:["write('extra',{__v_isRef:false,value:'ordinary'});"]},
 {name:'marker_truthy_string_not_ref',actions:["write('extra',{__v_isRef:'true',value:'ordinary'});"]},
 {name:'marker_frozen_writeback_throws',actions:["write('extra',Object.freeze({__v_isRef:true,value:'frozen'}));","write('extra','changed');"]},
 {name:'marker_getter_only_writeback_throws',actions:["write('extra',Object.defineProperty({__v_isRef:true},'value',{enumerable:true,configurable:true,get(){return 'getter';}}));","write('extra','changed');"]},
 {name:'native_scalar_ref_external_value_update',actions:["held=makeRef('initial');write('extra',held);","held.value='changed';"]},
 {name:'native_scalar_parent_writeback',actions:["held=makeRef('initial');write('extra',held);","write('extra','changed');mark('writeback:'+held.value);"]},
 {name:'native_scalar_same_value_no_notification',actions:["held=makeRef(7);write('extra',held);","write('extra',7);","held.value=7;"]},
 {name:'native_ref_nan_same_value',actions:["held=makeRef(NaN);write('extra',held);","held.value=NaN;"]},
 {name:'native_ref_signed_zero',actions:["held=makeRef(0);write('extra',held);","held.value=-0;"]},
 {name:'native_ref_replacement_cleans_old_subscription',actions:["held=makeRef('first');write('extra',held);","write('extra',makeRef('second'));","held.value='detached';"]},
 {name:'native_ref_old_alias_before_first_flush',actions:["held=makeRef('first');write('extra',held);","write('extra',makeRef('second'));held.value='old-before-flush';"]},
 {name:'native_ref_array_element_not_auto_unwrapped',actions:["held=makeRef('initial');write('extra',[held]);mark('element-identity:'+(root().extra[0]===held));","held.value='changed';"]},
 {name:'native_shallow_ref_raw_nested_mutation',actions:["held=makeRef({name:'raw'},true);write('extra',held);","root().extra.name='changed';"]},
 {name:'native_shallow_ref_value_replacement',actions:["held=makeRef({name:'initial'},true);write('extra',held);","held.value={name:'replacement'};"]},
 {name:'native_shallow_ref_parent_writeback',actions:["held=makeRef({name:'initial'},true);write('extra',held);","write('extra',{name:'replacement'});mark('writeback-identity:'+(root().extra===held.value));"]},
 {name:'native_deep_ref_value_replacement',actions:["held=makeRef({name:'initial'});write('extra',held);","held.value={name:'replacement'};"]},
 {name:'native_deep_ref_nested_property_dependency',actions:["held=makeRef({name:'initial'});write('extra',held);","held.value.name='changed';"]},
 {name:'native_deep_ref_array_mutator_dependency',actions:["held=makeRef([{name:'initial'}]);write('extra',held);","held.value.push({name:'next'});"]},
 {name:'native_deep_ref_array_element_dependency',actions:["held=makeRef([{name:'initial'}]);write('extra',held);","held.value[0].name='changed';"]}
];
device.exports.scenarios.splice(0,device.exports.scenarios.length,...scenarios);
async function audit(input){
 const result=await device.exports.audit(input);
 result.harness={baseSha256:expected,generatedSha256:crypto.createHash('sha256').update(generated).digest('hex'),
  nativeRefConstructor:'Frozen Vue2.7.16 ref/shallowRef in each realm; San uses Vue solely as incoming input factory, not as a parent/watch/effect.',
  componentCodeModified:false,addedBindings:['makeRef'],refSubscriberCleanupCompared:true,
  limits:'No customRef, computed Ref, arbitrary dep spoofing or foreign observer proof; these are not silently admitted.'};
 result.cleanup_pairs=[];
 for(const source of result.runs.filter(r=>r.variant==='vue_source')){
  const candidate=result.runs.find(r=>r.variant==='san_v7'&&r.subject===source.subject&&r.scenario===source.scenario);
  const normalize=rows=>rows.map(({phase,channel,name,info})=>({phase,channel,name,info}));
  result.cleanup_pairs.push({subject:source.subject,scenario:source.scenario,
   errorsEqual:JSON.stringify(normalize(source.cleanupErrors))===JSON.stringify(normalize(candidate.cleanupErrors)),
   sourceSubscribersReleased:source.refSubscribersAfterDispose.every(n=>n===0),
   sanSubscribersReleased:candidate.refSubscribersAfterDispose.every(n=>n===0)});
 }
 return result;
}
if(require.main===module)audit(JSON.parse(fs.readFileSync(0,'utf8'))).then(r=>process.stdout.write(JSON.stringify(r)))
 .catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
module.exports={audit,scenarios};
