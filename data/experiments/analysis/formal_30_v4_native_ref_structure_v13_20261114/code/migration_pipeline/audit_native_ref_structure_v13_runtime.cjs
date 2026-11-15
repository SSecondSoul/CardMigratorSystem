/* Input-only extension of the exact V12 native Ref test device. */
'use strict';
const fs=require('fs'),crypto=require('crypto'),Module=require('module');
const filename=require.resolve('./audit_ref_contract_v12_runtime.cjs');
const original=fs.readFileSync(filename,'utf8'),expected='fcc0999cee2dcf24fd30e1ea93d13bf6ba6d657e1db42a17bbdddcf7518582bb';
if(crypto.createHash('sha256').update(original).digest('hex')!==expected)throw Error('Frozen Ref device drift');
let generated=original;
function inject(anchor,replacement){if(generated.split(anchor).length!==2)throw Error('Unknown device point');generated=generated.replace(anchor,replacement);}
inject('const subscriberCounts=()=>', `c.nativeSet=(object,key,value)=>refAPI.set(object,key,value);c.nativeDelete=(object,key)=>refAPI.delete(object,key);
const seenNativeNodes=new Set();
function rememberNativeNodes(value,seen=new Set()){
 if(!value||typeof value!=='object'||seen.has(value))return;seen.add(value);
 const slot=Object.getOwnPropertyDescriptor(value,'__ob__'),observer=slot&&slot.value;
 if(observer&&observer.value===value)seenNativeNodes.add(value);
 for(const key of Object.keys(value))rememberNativeNodes(value[key],seen);
}
const nativeNodeCounts=()=>[...seenNativeNodes].map(value=>value.__ob__.dep.subs.filter(Boolean).length);
const subscriberCounts=()=>`);
inject("const refSubscribersBeforeDispose=subscriberCounts();phase='dispose';", "for(const r of createdRefs)rememberNativeNodes(r.value);const nativeNodesBeforeDispose=nativeNodeCounts();const refSubscribersBeforeDispose=subscriberCounts();phase='dispose';");
inject('refSubscribersBeforeDispose,refSubscribersAfterDispose:subscriberCounts()', 'nativeNodesBeforeDispose,nativeNodesAfterDispose:nativeNodeCounts(),refSubscribersBeforeDispose,refSubscribersAfterDispose:subscriberCounts()');
const scenarios=[
 {name:'native_array_push_pop_splice',actions:["held=makeRef([{name:'initial'}]);write('extra',held);","held.value.push({name:'next'});","held.value.pop();","held.value.splice(0,1,{name:'replacement'});"]},
 {name:'native_array_reverse_sort',actions:["held=makeRef([{name:'b'},{name:'a'}]);write('extra',held);","held.value.reverse();","held.value.sort((a,b)=>a.name.localeCompare(b.name));"]},
 {name:'native_nested_array_structural_dependency',actions:["held=makeRef([[{name:'initial'}]]);write('extra',held);","held.value[0].push({name:'next'});"]},
 {name:'native_array_element_add_delete_structure',actions:["held=makeRef([{name:'initial'}]);write('extra',held);","nativeSet(held.value[0],'added',7);","nativeDelete(held.value[0],'added');"]},
 {name:'native_ref_object_add_delete_structure',actions:["held=makeRef({name:'initial'});write('extra',held);","nativeSet(held.value,'added',7);","nativeDelete(held.value,'added');"]},
 {name:'detached_native_array_stops_after_recollection',actions:["held=makeRef([{name:'initial'}]);write('extra',held);","write('extra',makeRef([{name:'replacement'}]));","held.value.push({name:'detached'});"]},
 {name:'detached_native_array_before_first_flush_notifies',actions:["held=makeRef([{name:'initial'}]);write('extra',held);","write('extra',makeRef([{name:'replacement'}]));held.value.push({name:'old-before-flush'});"]},
 {name:'shallow_ref_of_existing_observed_array',actions:["held=makeRef([{name:'initial'}]);write('extra',makeRef(held.value,true));","held.value.push({name:'next'});"]},
 {name:'raw_shallow_array_must_not_subscribe_child_structure',actions:["held=makeRef({name:'observed-child'});write('extra',makeRef([held.value],true));","nativeSet(held.value,'added',7);"]},
 {name:'native_raw_array_index_assignment_stays_raw',actions:["held=makeRef([{name:'initial'}]);write('extra',held);","held.value[0]={name:'raw-index'};"]},
 {name:'native_new_property_dependency_still_private',actions:["held=makeRef({name:'initial'});write('extra',held);","nativeSet(held.value,'added',7);","held.value.added=8;"]}
];
inject('device.exports.scenarios.splice(0,device.exports.scenarios.length,...scenarios);',
 'scenarios.splice(0,scenarios.length,...'+JSON.stringify(scenarios)+');device.exports.scenarios.splice(0,device.exports.scenarios.length,...scenarios);');
const device=new Module(filename,module);device.filename=filename;device.paths=Module._nodeModulePaths(__dirname);device._compile(generated,filename);
async function audit(input){
 const result=await device.exports.audit(input);
 result.structuralHarness={baseSha256:expected,generatedSha256:crypto.createHash('sha256').update(generated).digest('hex'),
  componentCodeModified:false,extraBindings:['nativeSet','nativeDelete'],
  limits:'Pinned Vue input APIs only. nativeSet is explicitly Vue.set, not raw source assignment or San Data.set.'};
 result.nativeObserverCleanup=result.runs.map(r=>({subject:r.subject,scenario:r.scenario,variant:r.variant,
  allReleased:r.nativeNodesAfterDispose.every(n=>n===0)}));
 return result;
}
if(require.main===module)audit(JSON.parse(fs.readFileSync(0,'utf8'))).then(r=>process.stdout.write(JSON.stringify(r)))
 .catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
module.exports={audit,scenarios};
