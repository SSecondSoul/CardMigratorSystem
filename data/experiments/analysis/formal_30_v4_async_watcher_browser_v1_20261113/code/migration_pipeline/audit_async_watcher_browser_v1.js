/* Real browser port: separate same-origin native iframe realms; no miniDOM.
 * Original Vue and v5 runs remain byte-for-byte observational controls.
 * Diagnostic rendering here is a bounded APPLICATION binding for this named,
 * nonrecursive fixture tree, not a built-in implementation of all Vue traces.
 */
'use strict';
const EPOCH=Date.UTC(2026,10,11,12);
const script=s=>/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(s)[1];
const copy=v=>JSON.parse(JSON.stringify(v,(_k,x)=>x===undefined?{$type:'undefined'}:x));
const drain=async()=>{await new Promise(r=>setTimeout(r,0));await new Promise(r=>setTimeout(r,0));};
function evaluate(text,c,requireFn){
 const module={exports:{}};
 new c.Function('module','exports','require',text)(module,module.exports,requireFn||(()=>{throw Error('Unexpected dependency');}));
 return module.exports;
}
const scenarios=[
 {name:'normal',failure:false},
 {name:'browser_default',failure:true},
 {name:'near_capture_false',failure:true,near:['false'],far:['true']},
 {name:'near_bubble_far_false',failure:true,near:['true'],far:['false']},
 {name:'near_two_hooks_false',failure:true,near:['true','false'],far:['true']},
 {name:'capture_returns_true_global',failure:true,near:['true'],far:['true'],global:'return'},
 {name:'near_throw_far_false',failure:true,near:['throw'],far:['false']},
 {name:'global_handler_returns',failure:true,global:'return'},
 {name:'global_handler_throws_different',failure:true,global:'throw'},
 {name:'global_handler_rethrows_original',failure:true,global:'rethrow'},
 {name:'near_throw_global_returns',failure:true,near:['throw'],global:'return'}
];
async function runOne(input,variant,spec){
 const iframe=document.createElement('iframe');iframe.src='/realm.html';
 const ready=new Promise((resolve,reject)=>{iframe.onload=resolve;iframe.onerror=reject;});
 document.getElementById('realms').appendChild(iframe);await ready;
 const c=iframe.contentWindow,host=c.document.createElement('div');c.document.body.appendChild(host);
 let phase='construct',events=[],lastError=null,remaining=0,stored=null,nextTimer=0,nextTimeout=0;
 let instance,near,far,root;const scopeControls={};
 const rejections=[],consoleRecords=[],intervals=new Map(),timeouts=new Map(),captureFailures=new Set(),reporterFailures=new Set();
 const log=e=>events.push(copy({phase,...e}));
 const role=c=>c===instance?'subject':c===near?'near':c===far?'far':c==null?'null':'other';
 const errorCode=e=>e===lastError?'original':captureFailures.has(e)?'capture-error':reporterFailures.has(e)?'reporter-error':'other';
 const consoleRecord=(method,args)=>consoleRecords.push({phase,method,args:args.map(v=>
   v&&typeof v==='object'&&typeof v.message==='string'?{kind:'error',name:v.name,message:v.message,identity:errorCode(v)}:
   {kind:'value',text:String(v)})});
 class FixedDate extends Date{constructor(...args){super(...(args.length?args:[EPOCH]));}static now(){return EPOCH;}}
 Object.assign(c,{Date:FixedDate,process:{env:{NODE_ENV:'development'}},
  console:{log(){},warn:(...a)=>consoleRecord('warn',a),error:(...a)=>consoleRecord('error',a)},
  setInterval(fn,delay){const id=++nextTimer;intervals.set(id,{fn,delay});log({kind:'interval-start',id,delay});return id;},
  clearInterval(id){const existed=intervals.delete(id);log({kind:'interval-clear',id,existed});},
  setTimeout(fn,delay){const id=++nextTimeout;timeouts.set(id,{fn,delay});return id;},clearTimeout(id){timeouts.delete(id);}});
 Object.defineProperty(c,'localStorage',{configurable:true,value:{
  getItem(key){log({kind:'storage-read',key});return stored;},setItem(key,text){
   const value=JSON.parse(text);log({kind:'storage-write-attempt',key,value});
   if(remaining){remaining--;lastError=new Error('BoundaryStorageWriteFailure');log({kind:'storage-write-failure',key});throw lastError;}
   stored=text;log({kind:'storage-write',key,value});}}});
 const rejection=event=>{const e=event.reason;rejections.push({phase,message:e.message,name:e.name,identity:errorCode(e)});};
 c.addEventListener('unhandledrejection',rejection);
 const source=variant==='vue_source',runtime=evaluate(source?input.vueRuntime:input.sanRuntime,c);
 if(runtime.version!==(source?'2.7.16':'3.15.6'))throw Error('Pinned runtime drift');
 function globalHandler(e,subject,info){
  log({kind:'global-handler',identity:errorCode(e),message:e.message,subject:role(subject),info,thisIsNull:this===null});
  if(spec.global==='throw'){const next=new Error('ApplicationReporterFailure');reporterFailures.add(next);throw next;}
  if(spec.global==='rethrow')throw e;
 }
 const capture=(which,behavior,index)=>function(e,subject,info){
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
  const options=evaluate(script(input.vue),c);trace(options.methods);options.render=h=>h('main');options.name='ErrorAuditSubject';
  const Subject=runtime.extend(options);
  const Near=runtime.extend({name:'ErrorAuditNear',errorCaptured:(spec.near||[]).map((b,i)=>capture('near',b,i)),render:h=>h(Subject)});
  const Far=runtime.extend({name:'ErrorAuditFar',errorCaptured:(spec.far||[]).map((b,i)=>capture('far',b,i)),render:h=>h(Near)});
  root=new Far();phase='mount_sync';root.$mount();host.appendChild(root.$el);far=root;near=far.$children[0];instance=near.$children[0];
 }else{
  const Subject=evaluate(script(input[variant]),c,n=>{if(n!=='san')throw Error(n);return runtime;});
  Subject.prototype.template='<main></main>';trace(Subject.prototype);
  const old=Subject.prototype.inited;
  Subject.prototype.inited=function(){
   old.call(this);if(spec.global)this.__parentWatchError_v5Configure(globalHandler);
   if(variant==='san_v7')this.__watcherScope_v7Configure({
    channel:'async-parent-watch',environment:'browser',trackingPolicy:'no-reactive-reads-or-writes',
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
  if(variant==='san_v7'){
   Subject.prototype.__sourceMappedName_v6='ErrorAuditSubject';
   nearOptions.__sourceMappedName_v6='ErrorAuditNear';
   nearOptions.__sourceMappedCaptures_v6=(spec.near||[]).map((b,i)=>capture('near',b,i));
  }
  const Near=runtime.defineComponent(nearOptions);
  const farOptions={template:'<div><audit-near/></div>',components:{'audit-near':Near},error:sanError('far')};
  if(variant==='san_v7'){
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
  notification:copy(read('notification')),stored:JSON.parse(stored),intervalDelays:[...intervals.values()].map(t=>t.delay),
  notificationTimeouts:[...timeouts.values()].filter(t=>t.delay===3000).length,domText:host.textContent},
  events:copy(events),consoleRecords:copy(consoleRecords),unhandledRejections:copy(rejections)});
 const update=(interval,title)=>new c.Function('subject',"subject.updateSettings('syncInterval',"+interval+");"+
   (title?(source?"subject.tasks[0].title='changed';":"subject.data.set('tasks[0].title','changed');"):'') )(instance);
 const turn=async(name,fn)=>{phase=name+'_sync';events=[];fn();
  captureFrame(phase);phase=name+'_tick';events=[];await drain();captureFrame(phase);};
 captureFrame('mount_sync');phase='mount_tick';events=[];await drain();captureFrame(phase);
 if(variant==='san_v7'){
  scopeControls.configureOnly=typeof instance.__watcherScope_v7Configure==='function'
    &&!instance.__sourceErrorContext_v6Configure&&!instance.__sourceErrorContext_v6Active
    &&!instance.__watcherScope_v7Local&&!instance.__watcherScope_v7Create;
  try{instance.__watcherScope_v7Configure({});scopeControls.lateConfiguration=null;}
  catch(e){scopeControls.lateConfiguration=e.code;}
 }
 await turn('primary',()=>{remaining=spec.failure?1:0;update(30,true);});
 await turn('repeat',()=>update(60,false));
 await turn('recovery',()=>update(0,false));
 await turn('destroy',()=>source?root.$destroy():root.dispose());
 if(variant==='san_v7'){
  try{instance.__watcherScope_v7Configure({});scopeControls.disposedConfiguration=null;}
  catch(e){scopeControls.disposedConfiguration=e.code;}
 }
 let nativeSanControl=null;
 if(!source){
  const received=[],original=new Error('NativeSanControlFailure');let nativeChild;
  const Child=runtime.defineComponent({template:'<b>probe</b>',initData(){return {value:0};},inited(){this.watch('value',()=>{throw original;});}});
  const Parent=runtime.defineComponent({template:'<div><native-probe/></div>',components:{'native-probe':Child},
   error(e,subject,info){received.push({ancestor:'near',originalError:e===original,subjectIsChild:subject===nativeChild,info});return true;}});
  const Grand=runtime.defineComponent({template:'<div><native-near/></div>',components:{'native-near':Parent},
   error(e,subject,info){received.push({ancestor:'far',originalError:e===original,subjectIsChild:subject===nativeChild,info});}});
  const control=new Grand();control.attach(c.document.createElement('div'));const nativeNear=control.children[0];nativeChild=nativeNear.children[0];
  nativeChild.data.set('value',1);await drain();
  nativeSanControl={received,nearReturnedTrue:true,
   nativeChildParentLink:nativeChild.parentComponent===nativeNear&&nativeNear.parentComponent===control};control.dispose();await drain();
 }
 const result={scenario:spec.name,variant,phases,nativeAncestorChain:true,nativeSanControl,...(variant==='san_v7'?{scopeControls}:{}),
  boundary:{realBrowser:true,limitedDOM:false,nativeComponentsMounted:true,vueBrowserBranch:source,
    originalSubjectRenderReplaced:true,subjectBusinessBodyChanged:false,realStorage:false,realBusinessTimers:false,
    sanReporterConfiguredByHarness:!source&&!!spec.global,sanAncestorErrorHooksInstalled:!source,
    privateFrameworkErrorFunctionInvokedByHarness:false}};
 c.removeEventListener('unhandledrejection',rejection);iframe.remove();return result;
}
async function audit(input){
 const runs=[];
 for(const s of scenarios)for(const v of ['vue_source','san_v5','san_v7'])runs.push(await runOne(input,v,s));
 const pairs=[];
 for(const s of scenarios){const a=runs.find(r=>r.scenario===s.name&&r.variant==='vue_source');
  for(const variant of ['san_v5','san_v7']){const b=runs.find(r=>r.scenario===s.name&&r.variant===variant);
  for(let i=0;i<a.phases.length;i++){const x=a.phases[i],y=b.phases[i];pairs.push({scenario:s.name,variant,phase:x.name,
   stateEqual:JSON.stringify(x.state)===JSON.stringify(y.state),eventsEqual:JSON.stringify(x.events)===JSON.stringify(y.events),
   rawConsoleEqual:JSON.stringify(x.consoleRecords)===JSON.stringify(y.consoleRecords),
   unhandledRejectionsEqual:JSON.stringify(x.unhandledRejections)===JSON.stringify(y.unhandledRejections)});}
 }}
 return {runs,pairs,scenarios,browserUserAgent:navigator.userAgent,realmCountAfter:document.querySelectorAll('iframe').length,
  modelRequests:0,productionIntegrationEnabled:false,adapterChanged:true,
  explicitApplicationMappings:true,boundedDiagnosticSinkIsHarnessCode:true,privateAsyncScope:true};
}
window.runBrowserWatcherAudit=audit;
