/* Standalone native-runtime counterexamples. No mutable production helper imports. */
'use strict';
const fs=require('fs'),vm=require('vm'),crypto=require('crypto');
const script=text=>/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(text)[1];
const copy=value=>JSON.parse(JSON.stringify(value,(_k,v)=>v===undefined?{$type:'undefined'}:v));
const drain=async()=>{await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));};
function environment(){
 let stored=null,phase='construct',events=[],intervalId=0,timeoutId=0;
 const intervals=new Map(),errors=[],warnings=[];
 const log=value=>events.push(copy({phase,...value}));
 class FixedDate extends Date{constructor(...args){super(...(args.length?args:[Date.UTC(2026,10,11,12)]));}static now(){return Date.UTC(2026,10,11,12);}}
 const context=vm.createContext({Date:FixedDate,Promise,process:{env:{NODE_ENV:'development'}},
  console:{log(){},warn:(...a)=>warnings.push(a.map(String).join(' ')),error:(...a)=>warnings.push(a.map(String).join(' '))},
  localStorage:{getItem(key){log({kind:'storage-read',key});return stored;},setItem(key,value){
   stored=value;log({kind:'storage-write',key,value:JSON.parse(value)});}},
  setTimeout(){return ++timeoutId;},clearTimeout(){},
  setInterval(fn,delay){const id=++intervalId;intervals.set(id,delay);log({kind:'interval-start',id,delay});return id;},
  clearInterval(id){log({kind:'interval-clear',id,existed:intervals.delete(id)});}});
 context.global=context;
 return {context,errors,warnings,log,setStored:value=>{stored=JSON.stringify(value);},phase:name=>{phase=name;events=[];},
  events:()=>copy(events),stored:()=>stored===null?null:JSON.parse(stored),intervals:()=>[...intervals.values()],
  error:(channel,error)=>{errors.push({phase,channel,message:error.message||String(error)});}};
}
function evaluate(text,env,required){
 env.context.__module={exports:{}};env.context.__require=required||(()=>{throw Error('Unexpected require');});
 vm.runInContext('(function(module,exports,require){\n'+text+'\n})(__module,__module.exports,__require)',env.context,{timeout:5000});
 const result=env.context.__module.exports;delete env.context.__module;delete env.context.__require;return result;
}
const scenarios=[
 {name:'flat_ui_control',settings:{defaultView:'list',autoSave:true,notifications:true,syncInterval:0},key:'defaultView',value:'board'},
 {name:'restore_extra_nested_object',settings:{defaultView:'list',autoSave:true,notifications:true,syncInterval:0,extraConfig:{theme:'dark'}}},
 {name:'restore_declared_object_value',settings:{defaultView:'list',autoSave:true,notifications:{enabled:true},syncInterval:0}},
 {name:'public_new_object_value',settings:{defaultView:'list',autoSave:true,notifications:true,syncInterval:0},key:'extraConfig',value:{theme:'dark'}},
 {name:'computed_root_dependency',generic:true,key:'enabled',value:true}
];
async function runOne(input,variant,scenario,active){
 const env=environment();active(env);
 const fixture=scenario.generic?input.generic:input;
 if(!scenario.generic)env.setStored({tasks:[{id:901,title:'retained',description:'',completed:false,tags:[],priority:'medium',dueDate:''}],settings:scenario.settings});
 let runtime,instance,read,destroy;
 if(variant==='vue_source'){
  runtime=evaluate(input.vueRuntime,env);
  if(runtime.version!=='2.7.16')throw Error('Vue version drift');
  runtime.config.errorHandler=e=>env.error('vue.config.errorHandler',e);runtime.config.warnHandler=m=>env.warnings.push(m);
  const options=evaluate(script(fixture.vue).replace('export default','module.exports='),env);
  options.render=h=>h('main');instance=new runtime(options);read=key=>instance[key];destroy=()=>instance.$destroy();
 }else{
  runtime=evaluate(input.sanRuntime,env);
  if(runtime.version!=='3.15.6')throw Error('San version drift');
  const Parent=evaluate(script(variant==='san_normal_flow'?fixture.normal:fixture.candidate),env,
   name=>{if(name!=='san')throw Error('Unexpected dependency');return runtime;});
  Parent.prototype.template=/<template\b[^>]*>([\s\S]*?)<\/template>/.exec(variant==='san_normal_flow'?fixture.normal:fixture.candidate)[1];
  instance=new Parent();read=key=>instance.data.get(key);destroy=()=>instance.dispose(true,true);
 }
 env.context.__instance=instance;
 const phases=[];
 const capture=name=>{
  const state={settings:copy(read('settings')),stored:env.stored(),activeIntervalDelays:env.intervals()};
  if(scenario.generic){state.label=read('label');state.count=read('count');}
  else{state.taskIds=read('tasks').map(v=>v.id);state.notification=copy(read('notification'));}
  phases.push({name,state,events:env.events(),errors:copy(env.errors),warnings:copy(env.warnings)});
 };
 env.phase('mount_sync');try{variant==='vue_source'?instance.$mount():instance.attached();}
 catch(error){env.error('synchronous_mount_throw',error);}capture('mount_sync');
 env.phase('mount_tick');await drain();capture('mount_tick');
 env.phase('action_sync');
 if(scenario.key){env.context.__action=JSON.stringify({key:scenario.key,value:scenario.value});
  try{vm.runInContext('(()=>{const a=JSON.parse(__action);__instance.'+(scenario.generic?'assign':'updateSettings')+'(a.key,a.value);})()',env.context);}
  catch(error){env.error('synchronous_public_method_throw',error);}}
 capture('action_sync');env.phase('action_tick');await drain();capture('action_tick');
 env.phase('destroy_sync');try{destroy();}catch(error){env.error('synchronous_destroy_throw',error);}capture('destroy_sync');
 env.phase('destroy_tick');await drain();capture('destroy_tick');
 return {scenario:scenario.name,variant,frameworkVersion:runtime.version,phases,errors:copy(env.errors),
  limitations:{sourceBusinessBodyChanged:false,sourceExportSyntaxAdapted:!!scenario.generic,
   vueDummyRender:true,sanFullAttach:false,browser:false,realStorage:false,realTimers:false,
   nativeComputedEvaluation:true,candidateInputIsDerivative:true}};
}
async function audit(input){
 const runs=[];let current;
 const listener=e=>{if(!current)throw e;current.error('process.unhandledRejection',e);};
 const before=process.listenerCount('unhandledRejection');process.on('unhandledRejection',listener);
 try{for(const scenario of scenarios)for(const variant of ['vue_source','san_normal_flow','san_dynamic_candidate'])
  runs.push(await runOne(input,variant,scenario,env=>{current=env;}));}
 finally{await drain();process.removeListener('unhandledRejection',listener);current=null;}
 const pairs=[];
 for(const scenario of scenarios){const source=runs.find(r=>r.scenario===scenario.name&&r.variant==='vue_source');
  for(const variant of ['san_normal_flow','san_dynamic_candidate']){
   const target=runs.find(r=>r.scenario===scenario.name&&r.variant===variant);
   for(let i=0;i<source.phases.length;i++){const a=source.phases[i],b=target.phases[i];
    pairs.push({scenario:scenario.name,variant,phase:a.name,stateEqual:JSON.stringify(a.state)===JSON.stringify(b.state),
     eventsEqual:JSON.stringify(a.events)===JSON.stringify(b.events),errorsEqual:JSON.stringify(a.errors)===JSON.stringify(b.errors)});
   }
  }
 }
 return {runs,pairs,scenarios:scenarios.map(v=>v.name),nodeVersion:process.version,
  vueRuntimeSha256:crypto.createHash('sha256').update(input.vueRuntime).digest('hex'),
  sanRuntimeSha256:crypto.createHash('sha256').update(input.sanRuntime).digest('hex'),
  rejectionListenerRestored:process.listenerCount('unhandledRejection')===before,
  hostPrototypeClean:!Object.prototype.hasOwnProperty.call(Object.prototype,'boundaryMarker'),
  modelRequests:0,productionChanged:false,fullBrowserOrInitialDomEvaluated:false};
}
if(require.main===module)audit(JSON.parse(fs.readFileSync(0,'utf8'))).then(r=>process.stdout.write(JSON.stringify(r)))
 .catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
module.exports={audit};
