/* Input-only native audit extension: static no-option paths vs raw assignment. */
'use strict';
const fs=require('fs'),crypto=require('crypto'),Module=require('module');
const filename=require.resolve('./audit_v7_dynamic_shape_runtime.cjs');
const original=fs.readFileSync(filename,'utf8'),expected='cd1ba81e7e524966ab84012b317bc9ec9c429215e96381f1bfc237e0edf90122';
if(crypto.createHash('sha256').update(original).digest('hex')!==expected)throw Error('Frozen native device drift');
const anchor="c.existing=task?'notifications':'enabled';";
if(original.split(anchor).length!==2)throw Error('Unknown exact binding point');
const binding=`const expression=parts=>'settings'+parts.map(k=>'['+JSON.stringify(k)+']').join('');
c.setPath=(parts,value)=>{
 if(!Array.isArray(parts)||!parts.length||parts.some(k=>typeof k!=='string'&&typeof k!=='number'))throw Error('Unsupported audit path');
 if(isSource){let object=read();for(const key of parts.slice(0,-1))object=object[key];object[parts.at(-1)]=value;}
 else instance.data.set(expression(parts),value);
};
c.readPath=parts=>{if(!isSource)return instance.data.get(expression(parts));let result=read();for(const key of parts)result=result[key];return result;};`;
const generated=original.replace(anchor,binding+anchor),device=new Module(filename,module);
device.filename=filename;device.paths=Module._nodeModulePaths(__dirname);device._compile(generated,filename);
const scenarios=[
 {name:'new_property_repeat_keeps_identity',actions:["held=root();setPath(['extra','newRaw'],42);mark('root-identity:'+(root()===held));","setPath(['extra','newRaw'],43);mark('root-identity:'+(root()===held));"]},
 {name:'new_object_not_force_observed',actions:["held={name:'raw'};setPath(['extra','newRaw'],held);mark('incoming-identity:'+(root().extra.newRaw===held));","held.name='changed';"]},
 {name:'new_property_read_after_read',actions:["mark('before:'+readPath(['extra','newRaw']));setPath(['extra','newRaw'],7);mark('after:'+readPath(['extra','newRaw']));"]},
 {name:'known_property_alias_identity',actions:["held=root().extra;setPath(['extra','name'],'updated');mark('child-identity:'+(root().extra===held));"]},
 {name:'new_top_level_property',actions:["held=root();setPath(['newRaw'],7);mark('root-identity:'+(root()===held));"]},
 {name:'deleted_known_property_is_raw',actions:["delete root().extra.name;setPath(['extra','name'],'raw-again');","setPath(['extra','name'],'still-raw');"]},
 {name:'new_array_index_raw',actions:["held=root().extra.items;setPath(['extra','items',1],{value:2});mark('array-identity:'+(root().extra.items===held));","root().extra.items[1].value=3;"]},
 {name:'existing_array_index_raw',actions:["held=root().extra.items;setPath(['extra','items',0],{value:2});mark('array-identity:'+(root().extra.items===held));","root().extra.items[0].value=3;"]},
 {name:'array_index_then_push_not_reobserve_old',actions:["setPath(['extra','items',1],{value:2});","root().extra.items.push({value:3});","root().extra.items[1].value=4;"]},
 {name:'array_length_truncate_raw',actions:["held=root().extra.items;setPath(['extra','items','length'],0);mark('array-identity:'+(root().extra.items===held));"]},
 {name:'array_length_extend_holes',actions:["setPath(['extra','items','length'],4);"]},
 {name:'array_invalid_length_throws',actions:["setPath(['extra','items','length'],-1);"]},
 {name:'missing_intermediate_throws',actions:["setPath(['extra','missing','name'],'value');"]},
 {name:'null_intermediate_throws',actions:["write('extra',null);","setPath(['extra','name'],'value');"]},
 {name:'primitive_target_throws',actions:["write('extra',7);","setPath(['extra','name'],'value');"]},
 {name:'getter_only_target_noop',actions:["write('extra',Object.defineProperty({},'name',{enumerable:true,configurable:true,get(){return 'getter';}}));","setPath(['extra','name'],'ignored');"]},
 {name:'setter_target_receiver',actions:["let value='initial';write('extra',Object.defineProperty({},'name',{enumerable:true,configurable:true,get(){return value;},set(next){mark('setter-this:'+(this===root().extra));value=next;}}));","setPath(['extra','name'],'changed');"]},
 {name:'nonconfigurable_target_native_write',actions:["write('extra',Object.defineProperty({},'name',{value:'initial',enumerable:true,configurable:false,writable:true}));","setPath(['extra','name'],'changed');"]},
 {name:'frozen_target_native_error',actions:["write('extra',Object.freeze({name:'frozen'}));","setPath(['extra','name'],'changed');"]},
 {name:'new_property_on_sealed_throws',actions:["write('extra',Object.seal({name:'sealed'}));","setPath(['extra','newRaw'],'value');"]},
 {name:'existing_property_on_sealed_raw',actions:["write('extra',Object.seal({name:'sealed'}));","setPath(['extra','name'],'changed');"]},
 {name:'inherited_setter_native_receiver',actions:["Object.setPrototypeOf(root().extra,{set inherited(value){mark('setter-this:'+(this===root().extra));mark('setter-value:'+value);}});setPath(['extra','inherited'],8);"]},
 {name:'non_identifier_keys',actions:["setPath(['extra',''],7);setPath(['extra','a.b'],8);setPath(['extra','quote\"bracket]'],9);"]},
 {name:'prototype_set_local_only',actions:["held=root().extra;setPath(['extra','__proto__'],{auditMarker:'local-prototype'});mark('child-identity:'+(root().extra===held));"]},
 {name:'new_raw_marker_not_unwrapped',actions:["held={__v_isRef:true,value:'raw-marker'};setPath(['extra','newRaw'],held);mark('incoming-identity:'+(root().extra.newRaw===held));"]},
 {name:'negative_numeric_property_is_raw',actions:["held=root().extra.items;setPath(['extra','items',-1],7);mark('array-identity:'+(root().extra.items===held));"]},
 {name:'fractional_numeric_property_is_raw',actions:["held=root().extra.items;setPath(['extra','items',1.5],7);mark('array-identity:'+(root().extra.items===held));"]},
 {name:'string_numeric_key_not_coerced_to_index',actions:["setPath(['extra','items','01'],7);mark('leading-zero:'+root().extra.items['01']);"]}
];
device.exports.scenarios.splice(0,device.exports.scenarios.length,...scenarios);
async function audit(input){
 const result=await device.exports.audit(input);
 result.harness={baseSha256:expected,generatedSha256:crypto.createHash('sha256').update(generated).digest('hex'),
  extraBindings:['setPath','readPath'],componentCodeModified:false,
  comparison:'strict raw source property assignment to static string/number paths versus explicitly mapped no-option San Data.set; not Vue.set, force/silent or dynamic-expression equivalence'};
 return result;
}
if(require.main===module)audit(JSON.parse(fs.readFileSync(0,'utf8'))).then(r=>process.stdout.write(JSON.stringify(r)))
 .catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
module.exports={audit,scenarios};
