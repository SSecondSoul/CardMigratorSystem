/* Additional audit-device bindings only. Frozen component/runtime bytes remain
 * unchanged; no observer or application behavior is patched by this device.
 */
'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),Module=require('module');
const filename=path.join(__dirname,'audit_v7_dynamic_shape_runtime.cjs');
const original=fs.readFileSync(filename,'utf8');
const expected='cd1ba81e7e524966ab84012b317bc9ec9c429215e96381f1bfc237e0edf90122';
if(crypto.createHash('sha256').update(original).digest('hex')!==expected)throw Error('Frozen audit device drift');
const anchor="c.existing=task?'notifications':'enabled';";
if(original.split(anchor).length!==2)throw Error('Unknown exact device binding point');
const injected=`c.replaceRoot=value=>{if(isSource)instance.settings=value;else instance.data.set('settings',value);};
c.setPath=(parts,value)=>{
 if(!Array.isArray(parts)||!parts.length||parts.some(k=>typeof k!=='string'&&typeof k!=='number'))throw Error('Unsupported audit path');
 if(isSource){let object=read();for(const key of parts.slice(0,-1))object=object[key];object[parts.at(-1)]=value;}
 else{const expression='settings'+parts.map(k=>'['+JSON.stringify(k)+']').join('');instance.data.set(expression,value);}
};`;
const generated=original.replace(anchor,injected+anchor);
const device=new Module(filename,module);device.filename=filename;device.paths=Module._nodeModulePaths(__dirname);
device._compile(generated,filename);
const expansion=[
 {name:'sealed_value',actions:["write('extra',Object.seal({name:'sealed',items:[]}));","root().extra.name='changed';"]},
 {name:'prevent_extensions_value',actions:["write('extra',Object.preventExtensions({name:'fixed-shape',items:[]}));","root().extra.name='changed';"]},
 {name:'frozen_with_observed_child',actions:["held=root().extra;write('extra',Object.freeze({nested:held}));","held.name='after-frozen';"]},
 {name:'sealed_with_observed_child',actions:["held=root().extra;write('extra',Object.seal({nested:held}));","held.name='after-sealed';"]},
 {name:'pure_getter_value',actions:["write('extra',Object.defineProperty({},'name',{enumerable:true,configurable:true,get(){return 'getter';}}));"]},
 {name:'getter_setter_value',actions:["let value='initial';write('extra',Object.defineProperty({},'name',{enumerable:true,configurable:true,get(){return value;},set(next){value=next;}}));","root().extra.name='changed';"]},
 {name:'nonconfigurable_data_value',actions:["write('extra',Object.defineProperty({},'name',{value:'fixed',enumerable:true,writable:true,configurable:false}));","root().extra.name='changed';"]},
 {name:'symbol_properties_value',actions:["write('extra',{name:'symbol-property',[Symbol.for('hidden-key')]:7});"]},
 {name:'null_prototype_value',actions:["write('extra',Object.assign(Object.create(null),{name:'null-prototype'}));","root().extra.name='changed';"]},
 {name:'custom_prototype_value',actions:["write('extra',Object.assign(Object.create({auditMarker:'custom-prototype'}),{name:'custom'}));","root().extra.name='changed';"]},
 {name:'false_ref_marker_value',actions:["write('extra',{__v_isRef:false,name:'not-a-ref'});"]},
 {name:'true_ref_marker_value',actions:["write('extra',{__v_isRef:true,value:{name:'ref-value'}});"]},
 {name:'skip_true_marker_value',actions:["write('extra',{__v_skip:true,name:'skip'});","root().extra.name='changed';"]},
 {name:'skip_false_marker_value',actions:["write('extra',{__v_skip:false,name:'do-not-skip'});","root().extra.name='changed';"]},
 {name:'function_value',actions:["write('extra',function callback(){});"]},
 {name:'regexp_value',actions:["write('extra',/audit/gi);"]},
 {name:'map_value',actions:["write('extra',new Map([['key',7]]));mark('map-value:'+root().extra.get('key'));"]},
 {name:'set_value',actions:["write('extra',new Set([7]));mark('set-value:'+root().extra.has(7));"]},
 {name:'cyclic_plain_value',actions:["const value={name:'cycle'};value.self=value;write('extra',value);"]},
 {name:'restored_observed_alias',actions:["held=root().extra;write('extra',{name:'replacement',items:[]});","write('extra',held);","held.name='restored';"]},
 {name:'shared_dag_value',actions:["held=root().extra;write('extra',{left:{nested:held},right:{nested:held}});","held.name='shared-leaf';"]},
 {name:'external_known_path',actions:["held=root();setPath(['extra','name'],'native-path');mark('root-identity:'+(root()===held));"]},
 {name:'external_new_path',actions:["held=root();setPath(['extra','newRaw'],42);mark('root-identity:'+(root()===held));"]},
 {name:'external_root_replace',actions:["const next={...root(),extra:{name:'new-root',items:[]}};replaceRoot(next);mark('incoming-identity:'+(root()===next));","root().extra.name='changed';"]}
];
device.exports.scenarios.splice(0,device.exports.scenarios.length,...expansion);
async function audit(input){
 const result=await device.exports.audit(input);
 for(const run of result.runs)if(run.variant==='san_v7')run.variant='san_v9_expanded_inputs';
 result.harness={baseSha256:expected,generatedSha256:crypto.createHash('sha256').update(generated).digest('hex'),
  extraBindings:['replaceRoot','setPath'],componentCodeModified:false,originalDeviceModified:false,
  comparison:'raw source root/property assignment versus San Data.set without force/silent options',
  accessorCoverage:'Pure getters and stable getter/setter only; snapshot getter reads are not a proof of arbitrary accessor side effects.'};
 result.cleanup_pairs=[];
 for(const source of result.runs.filter(r=>r.variant==='vue_source')){
  const candidate=result.runs.find(r=>r.variant==='san_v9_expanded_inputs'&&r.subject===source.subject&&r.scenario===source.scenario);
  const normalize=rows=>rows.map(({phase,channel,name,info})=>({phase,channel,name,info}));
  result.cleanup_pairs.push({subject:source.subject,scenario:source.scenario,
   equal:JSON.stringify(normalize(source.cleanupErrors))===JSON.stringify(normalize(candidate.cleanupErrors))});
 }
 result.coverage_obligations=[
  {id:'EXP-ACCESSOR',category:'remaining_risk',scope:'getter/setter and non-configurable descriptors',
   requirement:'Native Vue descriptor/observation behavior and original accessor receiver/order must be preserved; rejecting all accessor inputs is not equivalent.'},
  {id:'EXP-METADATA',category:'remaining_risk',scope:'Ref/skip markers, Symbol properties and non-standard prototypes',
   requirement:'Distinguish false markers, raw-skipped values and actual Ref unwrapping. No key/marker blacklist may silently waive the source API contract.'},
  {id:'EXP-OPAQUE',category:'remaining_risk',scope:'Map, Set and RegExp values',
   requirement:'Separate native assignment acceptance and observation eligibility; retain object identity, no cloning to empty objects.'},
  {id:'EXP-DATA-PATH',category:'remaining_risk',scope:'external deep/root Data.set mappings',
   requirement:'For the explicitly tested raw-assignment mapping, preserve identity and notification policy for new keys. San-specific silent/force policies have no assumed source counterpart.'},
  {id:'EXP-LIFECYCLE-ERROR',category:'remaining_risk',scope:'cyclic serialization on destruction',
   requirement:'Cleanup is compared separately, not dropped. Source beforeDestroy reports through its framework; San disposal may escape directly. Async watcher reporting scope alone does not prove lifecycle-error equivalence.'}
 ];return result;
}
if(require.main===module)audit(JSON.parse(fs.readFileSync(0,'utf8'))).then(r=>process.stdout.write(JSON.stringify(r)))
 .catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
module.exports={audit,expansion};
