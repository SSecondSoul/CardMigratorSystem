/* Extended IDENTITY/queue/array test on pinned native runtimes. Headless lifecycle
 * only; native mounted child/DOM coverage comes from the separate frozen audit.
 */
'use strict';
const fs=require('fs'),vm=require('vm');
const script=s=>/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(s)[1];
const copy=v=>JSON.parse(JSON.stringify(v));
const drain=async()=>{await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));};
function evaluate(text,c,requireFn){
 c.__module={exports:{}};c.__require=requireFn||(()=>{throw Error('Unexpected require');});
 vm.runInContext('(function(module,exports,require){\n'+text+'\n})(__module,__module.exports,__require)',c,{timeout:5000});
 const result=c.__module.exports;delete c.__module;delete c.__require;return result;
}
const actions=[
 ['scalar',"a.assign('enabled',true);"],['same_scalar',"a.assign('enabled',true);"],
 ['borrow_name',"root(a).extra.name='borrowed';"],['same_name',"root(a).extra.name='borrowed';"],
 ['push',"incoming={value:2};result=root(a).extra.items.push(incoming);"],
 ['inserted_alias',"incoming.value=9;"],
 ['unshift',"result=root(a).extra.items.unshift({value:8});"],
 ['shift',"result=root(a).extra.items.shift();"],
 ['push_again',"result=root(a).extra.items.push({value:3});"],
 ['splice',"result=root(a).extra.items.splice(0,1,{value:4});"],
 ['sort',"result=root(a).extra.items.sort((a,b)=>b.value-a.value)===root(a).extra.items;"],
 ['reverse',"result=root(a).extra.items.reverse()===root(a).extra.items;"],
 ['pop',"result=root(a).extra.items.pop();"],
 ['empty_push_not_silent',"result=root(a).extra.items.push();"],
 ['new_key_object',"a.assign('newFlag',{inner:1});"],
 ['unobserved_new_value_alias',"root(a).newFlag.inner=2;"],
 ['replace_extra',"incoming={name:'replacement',items:[{value:7}]};a.assign('extra',incoming);"],
 ['same_extra',"a.assign('extra',incoming);"],
 ['new_extra_alias',"incoming.name='newAlias';"],
 ['replace_root',"setRoot(a,{enabled:false,extra:{name:'root',items:[{value:5}]}});"],
 ['detached_alias',"oldExtra.name='detached';"],
 ['restore_original_root',"setRoot(a,oldRoot);"],
 ['still_unobserved_new_key',"a.assign('newFlag',{inner:3});"],
 ['share_between_instances',"setRoot(b,root(a));"],
 ['shared_alias',"root(a).extra.name='shared';"],
 ['dispose_pending_first_instance',"a.assign('enabled',false);destroy(a);"],
 ['dispose_both_then_mutate',"destroy(b);oldRoot.extra.name='after-dispose';"]
];
async function run(input,variant,onError){
 let phase='construct',events=[];const errors=[],warnings=[];
 const c=vm.createContext({Promise,process:{env:{NODE_ENV:'development'}},
  console:{log(){},warn:(...a)=>warnings.push(a.map(String).join(' ')),error:(...a)=>warnings.push(a.map(String).join(' '))}});c.global=c;
 const error=e=>errors.push({phase,message:e.message||String(e)});onError(error);
 const source=variant==='vue_source',runtime=evaluate(source?input.vueRuntime:input.sanRuntime,c);
 if(runtime.version!==(source?'2.7.16':'3.15.6'))throw Error('Runtime version drift');
 const prototypeSet=source?null:runtime.Data.prototype.set;
 let create,read,destroy,setRoot;
 if(source){
  runtime.config.errorHandler=error;runtime.config.warnHandler=m=>warnings.push(m);
  const options=evaluate(script(input.vue).replace('export default','module.exports='),c),old=options.methods.recount;
  options.methods.recount=function(){events.push({phase,instance:this.__tag,name:'recount'});return old.call(this);};
  options.render=h=>h('main');create=tag=>{const p=new runtime(options);p.__tag=tag;p.$mount();return p;};
  read=(p,k)=>p[k];destroy=p=>p.$destroy();setRoot=(p,v)=>{p.settings=v;};
 }else{
  const Parent=evaluate(script(input.v4),c,n=>{if(n!=='san')throw Error(n);return runtime;});
  Parent.prototype.template='<main></main>';const old=Parent.prototype.recount;
  Parent.prototype.recount=function(){events.push({phase,instance:this.__tag,name:'recount'});return old.call(this);};
  create=tag=>{const p=new Parent();p.__tag=tag;p.attached();return p;};
  read=(p,k)=>p.data.get(k);destroy=p=>p.dispose(true,true);setRoot=(p,v)=>p.data.set('settings',v);
 }
 phase='mount_sync';const a=create('a'),b=create('b');
 c.a=a;c.b=b;c.root=p=>read(p,'settings');c.destroy=destroy;c.setRoot=setRoot;
 vm.runInContext('globalThis.oldRoot=root(a);globalThis.oldExtra=oldRoot.extra;globalThis.oldItems=oldExtra.items;globalThis.secondRoot=root(b);globalThis.incoming=null;globalThis.result=null;',c);
 const nativeSets=source?null:[a.data.set,b.data.set];
 const snapshots=[];
 const capture=name=>snapshots.push({name,state:{a:copy(read(a,'settings')),b:copy(read(b,'settings')),
   countA:read(a,'count'),countB:read(b,'count'),identity:copy(vm.runInContext(`({
    rootPreserved:root(a)===oldRoot,extraPreserved:root(a).extra===oldExtra,itemsPreserved:root(a).extra.items===oldItems,
    secondIndependent:root(b)===secondRoot,shared:root(a)===root(b),incomingIsExtra:root(a).extra===incoming})`,c)),result:copy(c.result)},
   events:copy(events),errors:copy(errors),warnings:copy(warnings)});
 capture(phase);phase='mount_tick';events=[];await drain();capture(phase);
 for(const [name,code] of actions){
  phase=name+'_sync';events=[];c.result=null;
  try{vm.runInContext(code,c);}catch(e){error(e);}
  capture(phase);phase=name+'_tick';events=[];await drain();capture(phase);
 }
 return {variant,version:runtime.version,snapshots,errors,
   frameworkPrototypeUnchanged:source||runtime.Data.prototype.set===prototypeSet,
   instanceWrappersRemoved:source||(a.data.set===prototypeSet&&b.data.set===prototypeSet),
   boundary:{headless:true,nativeFrameworks:true,browser:false,childDOMTested:false}};
}
async function audit(input){
 const runs=[];let current;
 const listener=e=>{if(!current)throw e;current(e);},before=process.listenerCount('unhandledRejection');process.on('unhandledRejection',listener);
 try{for(const v of ['vue_source','v4'])runs.push(await run(input,v,fn=>{current=fn;}));}
 finally{await drain();process.removeListener('unhandledRejection',listener);current=null;}
 const pairs=runs[0].snapshots.map((a,i)=>{const b=runs[1].snapshots[i];
  return {phase:a.name,stateEqual:JSON.stringify(a.state)===JSON.stringify(b.state),eventsEqual:JSON.stringify(a.events)===JSON.stringify(b.events),
   errorsEqual:JSON.stringify(a.errors)===JSON.stringify(b.errors),warningsEqual:JSON.stringify(a.warnings)===JSON.stringify(b.warnings)};});
 return {runs,pairs,actions:actions.map(a=>a[0]),nodeVersion:process.version,
  rejectionListenerRestored:process.listenerCount('unhandledRejection')===before,modelRequests:0,productionIntegrationEnabled:false};
}
if(require.main===module)audit(JSON.parse(fs.readFileSync(0,'utf8'))).then(r=>process.stdout.write(JSON.stringify(r)))
 .catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
module.exports={audit};
