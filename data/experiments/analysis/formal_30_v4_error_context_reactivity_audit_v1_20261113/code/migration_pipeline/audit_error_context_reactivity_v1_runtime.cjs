/* Derived dependency/reentrancy audit of the FROZEN v6 candidate.
 * Original Vue and v5 runs remain byte-for-byte observational controls.
 * Diagnostic rendering here is a bounded APPLICATION binding for this named,
 * nonrecursive fixture tree, not a built-in implementation of all Vue traces.
 */
'use strict';
const fs=require('fs'),vm=require('vm');
const EPOCH=Date.UTC(2026,10,11,12);
const script=s=>/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(s)[1];
const copy=v=>JSON.parse(JSON.stringify(v,(_k,x)=>x===undefined?{$type:'undefined'}:x));
const drain=async()=>{await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));};
function evaluate(text,c,requireFn){
 c.__module={exports:{}};c.__require=requireFn||(()=>{throw Error('Unexpected dependency');});
 vm.runInContext('(function(module,exports,require){\n'+text+'\n})(__module,__module.exports,__require)',c,{timeout:5000});
 const out=c.__module.exports;delete c.__module;delete c.__require;return out;
}
const scenarios=[
 {name:'normal',failure:false},
 {name:'normal_two_updates',failure:false,doublePrimary:true},
 {name:'positive_computed_dependency',failure:false,tracksSentinel:true},
 {name:'capture_reads_subject',failure:true,near:['true'],far:['false'],reactive:'read'},
 {name:'global_reads_subject',failure:true,global:'return',reactive:'read'},
 {name:'capture_writes_unrelated',failure:true,near:['false'],reactive:'unrelated'},
 {name:'global_writes_unrelated',failure:true,global:'return',reactive:'unrelated'},
 {name:'capture_reenters_settings',failure:true,near:['false'],reactive:'settings'},
 {name:'global_reenters_tasks',failure:true,global:'return',reactive:'tasks'}
];
async function runOne(input,variant,spec,onError){
 const {miniDOM}=require(input.domModule),dom=miniDOM(),host=dom.host();
 let phase='construct',events=[],lastError=null,remaining=0,stored=null,nextTimer=0,nextTimeout=0;
 let instance,near,far,root,auditComputedRuns=0,reactiveDone=false;
 const rejections=[],consoleRecords=[],intervals=new Map(),timeouts=new Map(),captureFailures=new Set(),reporterFailures=new Set();
 const log=e=>events.push(copy({phase,...e}));
 const role=c=>c===instance?'subject':c===near?'near':c===far?'far':c==null?'null':'other';
 const errorCode=e=>e===lastError?'original':captureFailures.has(e)?'capture-error':reporterFailures.has(e)?'reporter-error':'other';
 const consoleRecord=(method,args)=>consoleRecords.push({phase,method,args:args.map(v=>
   v&&typeof v==='object'&&typeof v.message==='string'?{kind:'error',name:v.name,message:v.message,identity:errorCode(v)}:
   {kind:'value',text:String(v)})});
 class FixedDate extends Date{constructor(...args){super(...(args.length?args:[EPOCH]));}static now(){return EPOCH;}}
 const c=vm.createContext({Promise,Date:FixedDate,process:{env:{NODE_ENV:'development'}},
  window:dom.window,document:dom.document,navigator:dom.window.navigator,Node:dom.Node,HTMLElement:dom.Node,
  console:{log(){},warn:(...a)=>consoleRecord('warn',a),error:(...a)=>consoleRecord('error',a)},
  localStorage:{getItem(key){log({kind:'storage-read',key});return stored;},setItem(key,text){
   const value=JSON.parse(text);log({kind:'storage-write-attempt',key,value});
   if(remaining){remaining--;lastError=new Error('BoundaryStorageWriteFailure');log({kind:'storage-write-failure',key});throw lastError;}
   stored=text;log({kind:'storage-write',key,value});}},
  setInterval(fn,delay){const id=++nextTimer;intervals.set(id,{fn,delay});log({kind:'interval-start',id,delay});return id;},
  clearInterval(id){const existed=intervals.delete(id);log({kind:'interval-clear',id,existed});},
  setTimeout(fn,delay){const id=++nextTimeout;timeouts.set(id,{fn,delay});return id;},clearTimeout(id){timeouts.delete(id);}});c.global=c;
 const rejection=e=>rejections.push({phase,message:e.message,name:e.name,identity:errorCode(e)});onError(rejection);
 const source=variant==='vue_source',runtime=evaluate(source?input.vueRuntime:input.sanRuntime,c);
 if(runtime.version!==(source?'2.7.16':'3.15.6'))throw Error('Pinned runtime drift');
 function reactiveAction(){
  if(!spec.reactive)return;
  const value=source?instance.auditSentinel:instance.data.get('auditSentinel');
  log({kind:'reactive-error-read',value});
  if(reactiveDone)return;reactiveDone=true;
  if(spec.reactive==='unrelated'){
   if(source)instance.auditSentinel++;else instance.data.set('auditSentinel',value+1);
   log({kind:'reactive-error-write',field:'auditSentinel',value:value+1});
  }else if(spec.reactive==='settings'){
   instance.updateSettings('syncInterval',15);
  }else if(spec.reactive==='tasks'){
   if(source)instance.tasks[0].title='from-error-hook';else instance.data.set('tasks[0].title','from-error-hook');
   log({kind:'reactive-error-write',field:'tasks[0].title',value:'from-error-hook'});
  }
 }
 function globalHandler(e,subject,info){
  reactiveAction();
  log({kind:'global-handler',identity:errorCode(e),message:e.message,subject:role(subject),info,thisIsNull:this===null});
  if(spec.global==='throw'){const next=new Error('ApplicationReporterFailure');reporterFailures.add(next);throw next;}
  if(spec.global==='rethrow')throw e;
 }
 const capture=(which,behavior,index)=>function(e,subject,info){
  reactiveAction();
  log({kind:'capture-hook',ancestor:which,index,behavior,identity:errorCode(e),subject:role(subject),info,receiver:role(this)});
  if(behavior==='throw'){const next=new Error('AncestorCaptureFailure');captureFailures.add(next);throw next;}
  return behavior==='false'?false:true;
 };
 const sanError=which=>function(e,subject,info){
  log({kind:'san-native-error-hook',ancestor:which,identity:errorCode(e),subject:role(subject),info,receiver:role(this)});return false;
 };
 const trace=options=>{for(const name of ['updateSettings','updateStatistics','saveToLocalStorage','startAutoSync','updateSyncInterval','showNotification']){
  const original=options[name];if(typeof original!=='function')throw Error('Missing '+name);
  options[name]=function(...args){log({kind:'call',name,args});return original.apply(this,args);};}};
 stored=JSON.stringify({tasks:[{id:10,title:'saved',description:'',completed:false,tags:[],priority:'medium',dueDate:''}],
  settings:{autoSave:true,syncInterval:0,defaultView:'list',notifications:true}});
 if(source){
  if(spec.global)runtime.config.errorHandler=globalHandler;
  const options=evaluate(script(input.vue),c);trace(options.methods);
  const oldData=options.data;options.data=function(){return {...oldData.call(this),auditSentinel:0};};
  options.computed={...options.computed,auditValue(){auditComputedRuns++;return this.settings.syncInterval+(spec.tracksSentinel?this.auditSentinel:0);}};
  options.render=function(h){return h('main',[String(this.auditValue)]);};options.name='ErrorAuditSubject';
  const Subject=runtime.extend(options);
  const Near=runtime.extend({name:'ErrorAuditNear',errorCaptured:(spec.near||[]).map((b,i)=>capture('near',b,i)),render:h=>h(Subject)});
  const Far=runtime.extend({name:'ErrorAuditFar',errorCaptured:(spec.far||[]).map((b,i)=>capture('far',b,i)),render:h=>h(Near)});
  root=new Far();phase='mount_sync';root.$mount();host.appendChild(root.$el);far=root;near=far.$children[0];instance=near.$children[0];
 }else{
  const Subject=evaluate(script(input[variant]),c,n=>{if(n!=='san')throw Error(n);return runtime;});
  const oldData=Subject.prototype.initData;Subject.prototype.initData=function(){return {...oldData.call(this),auditSentinel:0};};
  Subject.prototype.computed={...Subject.prototype.computed,auditValue(){auditComputedRuns++;return this.data.get('settings.syncInterval')+(spec.tracksSentinel?this.data.get('auditSentinel'):0);}};
  Subject.prototype.template='<main>{{ auditValue }}</main>';trace(Subject.prototype);
  const old=Subject.prototype.inited;
  Subject.prototype.inited=function(){
   old.call(this);if(spec.global)this.__parentWatchError_v5Configure(globalHandler);
   if(variant==='san_v6')this.__sourceErrorContext_v6Configure({
    environment:'browser',trackingPolicy:'no-reactive-reads-or-writes',
    parentOf:component=>component.parentComponent,
    hooksOf:component=>component.__sourceMappedCaptures_v6||[],
    globalHandler:()=>spec.global?globalHandler:null,
    logError:(error,subject,info)=>{
     // Bounded diagnostic sink: use actual native ancestors plus explicit names.
     const names=[];for(let n=subject;n;n=n.parentComponent){
      if(!n.__sourceMappedName_v6)throw Error('Unmapped diagnostic component');
      names.push(n.__sourceMappedName_v6);
     }
     const trace=names.length===0?'':names.length===1?'\n\n(found in <'+names[0]+'>)':
      '\n\nfound in\n\n'+names.map((name,index)=>(index===0?'---> ':' '.repeat(5+2*index))+'<'+name+'>').join('\n');
     c.console.error('[Vue warn]: Error in '+info+': "'+String(error)+'"'+trace);c.console.error(error);
    }
   });
  };
  const nearOptions={template:'<div><audit-subject/></div>',components:{'audit-subject':Subject},error:sanError('near')};
  if(variant==='san_v6'){
   Subject.prototype.__sourceMappedName_v6='ErrorAuditSubject';
   nearOptions.__sourceMappedName_v6='ErrorAuditNear';
   nearOptions.__sourceMappedCaptures_v6=(spec.near||[]).map((b,i)=>capture('near',b,i));
  }
  const Near=runtime.defineComponent(nearOptions);
  const farOptions={template:'<div><audit-near/></div>',components:{'audit-near':Near},error:sanError('far')};
  if(variant==='san_v6'){
   farOptions.__sourceMappedName_v6='Root';
   farOptions.__sourceMappedCaptures_v6=(spec.far||[]).map((b,i)=>capture('far',b,i));
  }
  const Far=runtime.defineComponent(farOptions);
  root=new Far();phase='mount_sync';root.attach(host);far=root;
  const components=n=>n.children?.flatMap(k=>k.nodeType===5?[k]:components(k)||[])||[];
  near=components(far)[0];instance=components(near)[0];
 }
 if(!instance||!near)throw Error('Native ancestors missing');
 const chain=source?instance.$parent===near&&near.$parent===far:instance.parentComponent===near&&near.parentComponent===far;
 if(!chain)throw Error('Not a native parent chain');
 c.subject=instance;const read=k=>source?instance[k]:instance.data.get(k),phases=[];
 const captureFrame=name=>phases.push({name,state:{tasks:copy(read('tasks')),settings:copy(read('settings')),statistics:copy(read('statistics')),
  notification:copy(read('notification')),auditSentinel:read('auditSentinel'),auditComputedRuns,stored:JSON.parse(stored),intervalDelays:[...intervals.values()].map(t=>t.delay),
  notificationTimeouts:[...timeouts.values()].filter(t=>t.delay===3000).length,domText:host.textContent},
  events:copy(events),consoleRecords:copy(consoleRecords),unhandledRejections:copy(rejections)});
 const update=(interval,title)=>vm.runInContext("subject.updateSettings('syncInterval',"+interval+");"+
   (title?(source?"subject.tasks[0].title='changed';":"subject.data.set('tasks[0].title','changed');"):'') ,c);
 const turn=async(name,fn)=>{phase=name+'_sync';events=[];try{fn();}catch(e){rejection(e);}
  captureFrame(phase);phase=name+'_tick';events=[];await drain();captureFrame(phase);};
 captureFrame('mount_sync');phase='mount_tick';events=[];await drain();captureFrame(phase);
 await turn('primary',()=>{remaining=spec.failure?1:0;update(30,true);if(spec.doublePrimary)update(15,false);});
 await turn('repeat',()=>update(60,false));
 await turn('recovery',()=>update(0,false));
 await turn('unrelated',()=>{if(source)instance.auditSentinel++;else instance.data.set('auditSentinel',read('auditSentinel')+1);});
 await turn('destroy',()=>source?root.$destroy():root.dispose());
 let nativeSanControl=null;
 if(!source){
  const received=[],original=new Error('NativeSanControlFailure');let nativeChild;
  const Child=runtime.defineComponent({template:'<b>probe</b>',initData(){return {value:0};},inited(){this.watch('value',()=>{throw original;});}});
  const Parent=runtime.defineComponent({template:'<div><native-probe/></div>',components:{'native-probe':Child},
   error(e,subject,info){received.push({ancestor:'near',originalError:e===original,subjectIsChild:subject===nativeChild,info});return true;}});
  const Grand=runtime.defineComponent({template:'<div><native-near/></div>',components:{'native-near':Parent},
   error(e,subject,info){received.push({ancestor:'far',originalError:e===original,subjectIsChild:subject===nativeChild,info});}});
  const control=new Grand();control.attach(dom.host());const nativeNear=control.children[0];nativeChild=nativeNear.children[0];
  nativeChild.data.set('value',1);await drain();
  nativeSanControl={received,nearReturnedTrue:true,
   nativeChildParentLink:nativeChild.parentComponent===nativeNear&&nativeNear.parentComponent===control};control.dispose();await drain();
 }
 return {scenario:spec.name,variant,phases,nativeAncestorChain:true,nativeSanControl,
  boundary:{realBrowser:false,limitedDOM:true,nativeComponentsMounted:true,vueBrowserBranch:source,
    originalSubjectRenderReplaced:true,subjectBusinessBodyChanged:false,realStorage:false,realBusinessTimers:false,
    sanReporterConfiguredByHarness:!source&&!!spec.global,sanAncestorErrorHooksInstalled:!source,
    privateFrameworkErrorFunctionInvokedByHarness:false}};
}
async function audit(input){
 const runs=[];let current;
 const before=process.listenerCount('unhandledRejection'),listener=e=>{if(!current)throw e;current(e);};
 process.on('unhandledRejection',listener);
 try{for(const s of scenarios)for(const v of ['vue_source','san_v6'])runs.push(await runOne(input,v,s,fn=>{current=fn;}));}
 finally{await drain();process.removeListener('unhandledRejection',listener);current=null;}
 const pairs=[];
 for(const s of scenarios){const a=runs.find(r=>r.scenario===s.name&&r.variant==='vue_source');
  for(const variant of ['san_v6']){const b=runs.find(r=>r.scenario===s.name&&r.variant===variant);
  for(let i=0;i<a.phases.length;i++){const x=a.phases[i],y=b.phases[i];pairs.push({scenario:s.name,variant,phase:x.name,
   stateEqual:JSON.stringify(x.state)===JSON.stringify(y.state),eventsEqual:JSON.stringify(x.events)===JSON.stringify(y.events),
   rawConsoleEqual:JSON.stringify(x.consoleRecords)===JSON.stringify(y.consoleRecords),
   unhandledRejectionsEqual:JSON.stringify(x.unhandledRejections)===JSON.stringify(y.unhandledRejections)});}
 }}
 return {runs,pairs,scenarios,nodeVersion:process.version,rejectionListenerRestored:process.listenerCount('unhandledRejection')===before,
  modelRequests:0,productionIntegrationEnabled:false,adapterChanged:true,
  explicitApplicationMappings:true,boundedDiagnosticSinkIsHarnessCode:true,
  reactiveHooksIntentionallyOutsideDeclaredV6Profile:true,realCandidateDispatchUsed:true,
  computedGetterAndRenderAreAuditFixture:true,dependencySuspensionImplemented:false};
}
if(require.main===module)audit(JSON.parse(fs.readFileSync(0,'utf8'))).then(r=>process.stdout.write(JSON.stringify(r)))
 .catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
module.exports={audit};
