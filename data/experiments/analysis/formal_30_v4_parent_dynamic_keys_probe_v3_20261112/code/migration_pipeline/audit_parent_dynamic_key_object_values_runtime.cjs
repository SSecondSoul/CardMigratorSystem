/* Standalone native framework assignment sequence; no production helper imports. */
'use strict';
const fs=require('fs'),vm=require('vm'),crypto=require('crypto');
const script=text=>/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(text)[1];
const copy=v=>JSON.parse(JSON.stringify(v,(_k,x)=>x===undefined?{$type:'undefined'}:x));
const drain=async()=>{await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));};
const actions=[
 ['new_object','newConfig','a'],['repeat_new_object','newConfig','a'],['replace_new_object','newConfig','b'],
 ['existing_object','extra','c'],['repeat_existing_object','extra','c'],['equal_content_new_identity','extra','d'],
 ['existing_array','extra','array'],['repeat_existing_array','extra','array'],['existing_nested_alias','extra','child'],
 ['new_alias','newAlias','child'],['replace_scalar','extra','scalar'],['destroy_pending','extra','c']
];
function evaluate(text,c,required){
 c.__module={exports:{}};c.__require=required||(()=>{throw Error('Unexpected dependency');});
 vm.runInContext('(function(module,exports,require){\n'+text+'\n})(__module,__module.exports,__require)',c,{timeout:5000});
 const result=c.__module.exports;delete c.__module;delete c.__require;return result;
}
async function run(input,variant,active){
 let phase='construct',events=[];const errors=[],warnings=[];
 const c=vm.createContext({Promise,process:{env:{NODE_ENV:'development'}},
  console:{log(){},warn:(...a)=>warnings.push(a.map(String).join(' ')),error:(...a)=>warnings.push(a.map(String).join(' '))}});c.global=c;
 const error=(channel,e)=>errors.push({phase,channel,message:e.message||String(e)});active(error);
 const runtime=evaluate(variant==='vue_source'?input.vueRuntime:input.sanRuntime,c);
 let instance,read,destroy;
 if(variant==='vue_source'){
  if(runtime.version!=='2.7.16')throw Error('Vue version drift');
  runtime.config.errorHandler=e=>error('vue.config.errorHandler',e);runtime.config.warnHandler=m=>warnings.push(m);
  const options=evaluate(script(input.vue).replace('export default','module.exports='),c),recount=options.methods.recount;
  options.methods.recount=function(){events.push({phase,kind:'call',name:'recount'});return recount.call(this);};
  options.render=h=>h('main');instance=new runtime(options);phase='mount_sync';instance.$mount();
  read=key=>instance[key];destroy=()=>instance.$destroy();
 }else{
  if(runtime.version!=='3.15.6')throw Error('San version drift');
  const Parent=evaluate(script(input[variant]),c,name=>{if(name!=='san')throw Error(name);return runtime;});
  Parent.prototype.template='<main></main>';const recount=Parent.prototype.recount;
  Parent.prototype.recount=function(){events.push({phase,kind:'call',name:'recount'});return recount.call(this);};
  instance=new Parent();phase='mount_sync';instance.attached();read=key=>instance.data.get(key);destroy=()=>instance.dispose(true,true);
 }
 c.__instance=instance;c.__originalRoot=read('settings');
 vm.runInContext(`globalThis.__values={a:{groups:[{name:'a'}]},b:{groups:[{name:'b'}]},
   c:{groups:[{name:'same'}]},d:{groups:[{name:'same'}]},array:[{name:'child'},['nested',1]],scalar:false};
   __values.child=__values.array[0];globalThis.__lastKey=null;globalThis.__lastValue=null;`,c);
 const phases=[];
 const capture=name=>{
  c.__root=read('settings');
  const identity=vm.runInContext(`({rootPreserved:__root===__originalRoot,
    writtenValuePreserved:__lastKey===null?null:__root[__lastKey]===__lastValue,
    aliasEqualsExtra:Object.prototype.hasOwnProperty.call(__root,'newAlias')&&__root.newAlias===__root.extra})`,c);
  phases.push({name,state:{settings:copy(read('settings')),count:read('count'),valueShape:read('valueShape'),identity:copy(identity)},
   events:copy(events),errors:copy(errors),warnings:copy(warnings)});
 };
 capture('mount_sync');phase='mount_tick';events=[];await drain();capture('mount_tick');
 for(const [name,key,value] of actions){
  phase=name+'_sync';events=[];c.__key=key;c.__valueName=value;
  try{vm.runInContext('__lastKey=__key;__lastValue=__values[__valueName];__instance.assign(__key,__lastValue);',c);}
  catch(e){error('synchronous_public_method_throw',e);}
  if(name==='destroy_pending')destroy();
  capture(phase);phase=name+'_tick';events=[];await drain();capture(phase);
 }
 return {variant,frameworkVersion:runtime.version,phases,errors,
  limitations:{nativeFrameworks:true,sourceBusinessBodyChanged:false,sourceExportSyntaxAdapted:true,
    sourceDummyRender:true,sanFullAttach:false,browser:false,realStorage:false,
    reflectionOrDeepAliasMutationTested:false,borrowedIdentityTested:true}};
}
async function audit(input){
 const variants=['vue_source','normal','v2','v3'],runs=[];let error;
 const count=process.listenerCount('unhandledRejection');const listener=e=>{if(!error)throw e;error('process.unhandledRejection',e);};
 process.on('unhandledRejection',listener);
 try{for(const variant of variants)runs.push(await run(input,variant,fn=>{error=fn;}));}
 finally{await drain();process.removeListener('unhandledRejection',listener);error=null;}
 const source=runs[0],pairs=[];
 for(const target of runs.slice(1))for(let i=0;i<source.phases.length;i++){
  const a=source.phases[i],b=target.phases[i];if(a.name!==b.name)throw Error('Phase mismatch');
  pairs.push({variant:target.variant,phase:a.name,stateEqual:JSON.stringify(a.state)===JSON.stringify(b.state),
   eventsEqual:JSON.stringify(a.events)===JSON.stringify(b.events),errorsEqual:JSON.stringify(a.errors)===JSON.stringify(b.errors),
   warningsEqual:JSON.stringify(a.warnings)===JSON.stringify(b.warnings)});
 }
 return {runs,pairs,actions:actions.map(a=>a[0]),nodeVersion:process.version,
  rejectionListenerRestored:process.listenerCount('unhandledRejection')===count,
  vueRuntimeSha256:crypto.createHash('sha256').update(input.vueRuntime).digest('hex'),
  sanRuntimeSha256:crypto.createHash('sha256').update(input.sanRuntime).digest('hex'),
  modelRequests:0,productionIntegrationEnabled:false};
}
if(require.main===module)audit(JSON.parse(fs.readFileSync(0,'utf8'))).then(r=>process.stdout.write(JSON.stringify(r)))
 .catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
module.exports={audit};
