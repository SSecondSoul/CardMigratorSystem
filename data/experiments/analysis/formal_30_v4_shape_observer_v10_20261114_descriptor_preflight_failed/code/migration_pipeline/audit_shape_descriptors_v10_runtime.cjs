/* Supplemental scenarios only; reuse the pinned native test device unmodified. */
'use strict';
const fs=require('fs'),crypto=require('crypto');
const filename=require.resolve('./audit_v7_dynamic_shape_runtime.cjs');
if(crypto.createHash('sha256').update(fs.readFileSync(filename)).digest('hex')!==
 'cd1ba81e7e524966ab84012b317bc9ec9c429215e96381f1bfc237e0edf90122')throw Error('Frozen native device drift');
const device=require(filename);
const scenarios=[
 {name:'getter_only_write_noop',actions:["write('extra',Object.defineProperty({},'name',{enumerable:true,configurable:true,get(){return 'getter';}}));","root().extra.name='ignored';mark('getter-value:'+root().extra.name);"]},
 {name:'getter_only_fresh_child_not_observed',actions:["held={name:'raw-child'};write('extra',Object.defineProperty({},'nested',{enumerable:true,configurable:true,get(){return held;}}));","held.name='changed';"]},
 {name:'getter_setter_receiver',actions:["let value='initial';write('extra',Object.defineProperty({},'name',{enumerable:true,configurable:true,get(){return value;},set(next){mark('setter-this:'+(this===root().extra));value=next;}}));","root().extra.name='changed';"]},
 {name:'setter_transform',actions:["let value='initial';write('extra',Object.defineProperty({},'name',{enumerable:true,configurable:true,get(){return value;},set(next){value=String(next).toUpperCase();}}));","root().extra.name='changed';"]},
 {name:'setter_throw_no_notification',actions:["write('extra',Object.defineProperty({},'name',{enumerable:true,configurable:true,get(){return 'initial';},set(){throw new RangeError('SetterFailure');}}));","root().extra.name='changed';"]},
 {name:'configurable_readonly_data_becomes_reactive',actions:["write('extra',Object.defineProperty({},'name',{value:'initial',enumerable:true,writable:false,configurable:true}));","root().extra.name='changed';"]},
 {name:'nonconfigurable_readonly_data_stays_readonly',actions:["write('extra',Object.defineProperty({},'name',{value:'initial',enumerable:true,writable:false,configurable:false}));","'use strict';root().extra.name='changed';"]},
 {name:'nonconfigurable_accessor_observed_child',actions:["held=root().extra;write('extra',Object.defineProperty({},'nested',{enumerable:true,configurable:false,get(){return held;}}));","held.name='changed';"]},
 {name:'symbol_child_is_not_walked',actions:["held={name:'raw-symbol-child'};write('extra',{name:'ordinary',[Symbol.for('child')]:held});","held.name='changed';"]},
 {name:'opaque_map_mutation_is_raw',actions:["write('extra',new Map([['key',1]]));","root().extra.set('key',2);mark('map-value:'+root().extra.get('key'));"]},
 {name:'array_insert_descriptor',actions:["let value='initial';root().extra.items.push(Object.defineProperty({},'name',{enumerable:true,configurable:true,get(){return value;},set(next){value=next;}}));","root().extra.items.at(-1).name='changed';"]},
 {name:'skip_flag_changed_after_observation_reuses_node',actions:["write('extra',{__v_skip:false,name:'initial'});","root().extra.__v_skip=true;","root().extra.name='changed';"]}
];
device.scenarios.splice(0,device.scenarios.length,...scenarios);
// The exported scenario array is shared with the native device, so changing its
// entries selects inputs, not framework/component semantics.
async function audit(input){return device.audit(input);}
if(require.main===module)audit(JSON.parse(fs.readFileSync(0,'utf8'))).then(r=>process.stdout.write(JSON.stringify(r)))
 .catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
module.exports={audit,scenarios};
