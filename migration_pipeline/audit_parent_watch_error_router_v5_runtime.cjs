/* Native headless Vue/San under an EXPLICIT APPLICATION REPORTER contract.
 * Preserves all raw routes/warnings. Browser defaults are NOT emulated here.
 */
'use strict';
const fs=require('fs'),vm=require('vm');
const EPOCH=Date.UTC(2026,10,11,12),CONFIG='__parentWatchError_v5Configure';
const script=s=>/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(s)[1];
const copy=v=>JSON.parse(JSON.stringify(v,(_k,x)=>x===undefined?{$type:'undefined'}:x));
const drain=async()=>{await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));};
function evaluate(text,c,requireFn){
 c.__module={exports:{}};c.__require=requireFn||(()=>{throw Error('Unexpected require');});
 vm.runInContext('(function(module,exports,require){\n'+text+'\n})(__module,__module.exports,__require)',c,{timeout:5000});
 const result=c.__module.exports;delete c.__module;delete c.__require;return result;
}
const scenarios=[
 {name:'normal',positive:true,failures:0},
 {name:'tasks_failure_once',positive:true,failures:1},
 {name:'settings_failure_once',positive:true,failures:1,settingsOnly:true},
 {name:'two_watcher_failures',positive:true,failures:2},
 {name:'repeat_settings_failure',positive:true,failures:0,repeatFailures:1},
 {name:'reporter_returns_false',positive:true,failures:1,returnsFalse:true},
 {name:'headless_default_not_closed',positive:false,failures:1,noReporter:true},
 {name:'missing_target_reporter_not_closed',positive:false,failures:1,noTargetReporter:true},
 {name:'throwing_reporter_not_closed',positive:false,failures:1,throwingReporter:true}
];
async function runOne(input,variant,spec,onActive){
 let phase='construct',events=[],stored=null,failures=0,lastFailure=null,intervalId=0,timeoutId=0;
 const errors=[],warnings=[],intervals=new Map(),timeouts=new Map();let instance;
 const log=e=>events.push(copy({phase,...e}));
 class FixedDate extends Date{constructor(...args){super(...(args.length?args:[EPOCH]));}static now(){return EPOCH;}}
 const c=vm.createContext({Promise,Date:FixedDate,process:{env:{NODE_ENV:'development'}},
  console:{log(){},warn:(...a)=>warnings.push(a.map(String).join(' ')),error:(...a)=>warnings.push(a.map(String).join(' '))},
  localStorage:{getItem(key){log({kind:'storage-read',key});return stored;},setItem(key,text){
   const value=JSON.parse(text);log({kind:'storage-write-attempt',key,value});
   if(failures>0){failures--;lastFailure=new Error('BoundaryStorageWriteFailure');log({kind:'storage-write-failure',key});throw lastFailure;}
   stored=text;log({kind:'storage-write',key,value});}},
  setInterval(fn,delay){const id=++intervalId;intervals.set(id,{fn,delay});log({kind:'interval-start',id,delay});return id;},
  clearInterval(id){const existed=intervals.delete(id);log({kind:'interval-clear',id,existed});},
  setTimeout(fn,delay){const id=++timeoutId;timeouts.set(id,{fn,delay});return id;},clearTimeout(id){timeouts.delete(id);}});c.global=c;
 const error=(channel,e,info=null)=>errors.push({phase,channel,name:e.name||'Error',message:e.message||String(e),info});onActive(error);
 const source=variant==='vue_source',runtime=evaluate(source?input.vueRuntime:input.sanRuntime,c);
 if(runtime.version!==(source?'2.7.16':'3.15.6'))throw Error('Runtime version drift');
 function reporter(e,subject,info){
  const record={kind:'application-error-report',name:e.name,message:e.message,info,
   originalError:e===lastFailure,subjectIsInstance:subject===instance,thisIsNull:this===null};
  log(record);error(source?'vue.config.errorHandler':'san.instance.explicitReporter',e,info);
  if(spec.throwingReporter)throw new Error('ApplicationReporterFailure');
  return spec.returnsFalse?false:undefined;
 }
 const trace=object=>{for(const name of ['updateSettings','updateStatistics','saveToLocalStorage','startAutoSync','updateSyncInterval','showNotification']){
  const old=object[name];if(typeof old!=='function')throw Error('Missing method '+name);
  object[name]=function(...args){log({kind:'call',name,args});return old.apply(this,args);};}};
 const task={id:10,title:'saved',description:'',completed:false,tags:[],priority:'medium',dueDate:''};
 stored=JSON.stringify({tasks:[task],settings:{autoSave:true,syncInterval:0,defaultView:'list',notifications:true}});
 let read,destroy;
 if(source){
  runtime.config.warnHandler=m=>warnings.push(m);
  if(!spec.noReporter)runtime.config.errorHandler=reporter;
  const options=evaluate(script(input.vue),c);options.render=h=>h('section');trace(options.methods);
  instance=new runtime(options);phase='mount_sync';instance.$mount();read=k=>instance[k];destroy=()=>instance.$destroy();
 }else{
  const Parent=evaluate(script(input[variant]),c,n=>{if(n!=='san')throw Error(n);return runtime;});
  Parent.prototype.template='<section></section>';trace(Parent.prototype);instance=new Parent();
  if(variant==='san_v5'&&!spec.noReporter&&!spec.noTargetReporter)instance[CONFIG](reporter);
  phase='mount_sync';instance.attached();read=k=>instance.data.get(k);destroy=()=>instance.dispose(true,true);
 }
 c.subject=instance;
 const update=(interval,withTasks)=>vm.runInContext("subject.updateSettings('syncInterval',"+interval+");"+
  (withTasks?(source?"subject.tasks[0].title='changed';":"subject.data.set('tasks[0].title','changed');"):'') ,c);
 const phases=[];
 const capture=name=>phases.push({name,state:{tasks:copy(read('tasks')),settings:copy(read('settings')),
  statistics:copy(read('statistics')),notification:copy(read('notification')),stored:JSON.parse(stored),
  activeIntervals:[...intervals.values()].map(v=>v.delay),notificationTimeouts:[...timeouts.values()].filter(v=>v.delay===3000).length,
  disposed:source?!!instance._isDestroyed:!!instance.lifeCycle.disposed},events:copy(events),rawErrors:copy(errors),warnings:copy(warnings)});
 const turn=async(name,fn)=>{phase=name+'_sync';events=[];try{fn();}catch(e){error('synchronous_throw',e);}
  capture(phase);phase=name+'_tick';events=[];await drain();capture(phase);};
 capture('mount_sync');phase='mount_tick';events=[];await drain();capture(phase);
 await turn('primary',()=>{failures=spec.failures;update(30,!spec.settingsOnly);});
 await turn('repeat',()=>{failures=spec.repeatFailures||0;update(60,false);});
 await turn('recovery',()=>{failures=0;update(0,false);});
 await turn('destroy',()=>{failures=0;destroy();});
 return {scenario:spec.name,variant,positiveContract:spec.positive,phases,rawErrors:copy(errors),warnings:copy(warnings),
  applicationReporterConfigured:source?!spec.noReporter:variant==='san_v5'&&!spec.noReporter&&!spec.noTargetReporter,
  boundary:{headless:true,browserDefaultTested:false,sourceBusinessBodyChanged:false,
   nativeFrameworks:true,realStorage:false,realApplicationTimers:false,queuePromiseCatchAdded:false}};
}
async function audit(input){
 const runs=[];let current;const before=process.listenerCount('unhandledRejection');
 const listener=e=>{if(!current)throw e;current('process.unhandledRejection',e);};process.on('unhandledRejection',listener);
 try{for(const s of scenarios)for(const v of ['vue_source','san_v4','san_v5'])runs.push(await runOne(input,v,s,fn=>{current=fn;}));}
 finally{await drain();process.removeListener('unhandledRejection',listener);current=null;}
 const pairs=[];
 for(const s of scenarios){const source=runs.find(r=>r.scenario===s.name&&r.variant==='vue_source');
  for(const variant of ['san_v4','san_v5']){const target=runs.find(r=>r.scenario===s.name&&r.variant===variant);
   for(let i=0;i<source.phases.length;i++){const a=source.phases[i],b=target.phases[i];
    pairs.push({scenario:s.name,variant,positiveContract:s.positive,phase:a.name,
     stateEqual:JSON.stringify(a.state)===JSON.stringify(b.state),
     businessAndApplicationErrorEventsEqual:JSON.stringify(a.events)===JSON.stringify(b.events),
     warningsEqual:JSON.stringify(a.warnings)===JSON.stringify(b.warnings)});
   }
  }
 }
 return {runs,pairs,scenarios,nodeVersion:process.version,modelRequests:0,productionIntegrationEnabled:false,
  rawErrorRoutesComparedAsIdentical:false,applicationErrorIdentityAndAttributionTested:true,
  rejectionListenerRestored:process.listenerCount('unhandledRejection')===before};
}
if(require.main===module)audit(JSON.parse(fs.readFileSync(0,'utf8'))).then(r=>process.stdout.write(JSON.stringify(r)))
 .catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
module.exports={audit};
