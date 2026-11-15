/* Native framework counterexample matrix. No simulated observer and no rewrite.
 * Fresh realm/instance per scenario. Minimal render is explicit, not UI evidence.
 */
'use strict';
const fs=require('fs'),vm=require('vm');
const {miniDOM}=require('./audit_parent_alias_child_runtime.cjs');
const body=s=>/<script\b[^>]*>([\s\S]*?)<\/script\s*>/.exec(s)[1];
const drain=async()=>{await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));};
const scenarios=[
 {name:'existing_same_value',actions:['write(existing,root()[existing]);']},
 {name:'existing_changed_value',actions:['write(existing,!root()[existing]);']},
 {name:'new_scalar_repeat',actions:["write('newOption',1);","write('newOption',2);"]},
 {name:'new_undefined',actions:["write('unsetOption',undefined);"]},
 {name:'inherited_builtin',actions:["write('toString','local');"]},
 {name:'numeric_key',actions:['write(7,42);']},
 {name:'symbol_key',actions:["write(Symbol.for('audit-key'),42);"]},
 {name:'coerced_existing_key',actions:["write({toString(){mark('key:string');return existing;}},false);"]},
 {name:'coerced_new_key',actions:["write({[Symbol.toPrimitive](hint){mark('key:'+hint);return 'converted';}},42);"]},
 {name:'throwing_key_coercion',actions:["write({toString(){mark('key:throw');throw new RangeError('KeyCoercionFailure');}},42);"]},
 {name:'prototype_plain',actions:["write('__proto__',{auditMarker:'local'});"]},
 {name:'prototype_null',actions:["write('__proto__',null);"]},
 {name:'inherited_setter',actions:["Object.setPrototypeOf(root(),{set custom(value){mark('inherited-set:'+value);},get custom(){return 3;}});write('custom',8);"]},
 {name:'date_value',actions:["write('extra',new Date(0));"]},
 {name:'frozen_value',actions:["write('extra',Object.freeze({name:'frozen'}));"]},
 {name:'sparse_array_value',actions:["write('extra',[,1]);"]},
 {name:'new_symbol_value',actions:["write('symbolValue',Symbol.for('audit-value'));"]},
 {name:'borrowed_existing_property',actions:["root().extra.name='updated';"]},
 {name:'borrowed_array_push',actions:["root().extra.items.push({value:2});"]},
 {name:'delete_then_mutate_detached_alias',actions:["held=root().extra;delete root().extra;held.name='first';","held.name='after-recollect';"]},
 {name:'redefine_then_mutate_detached_alias',actions:["held=root().extra;Object.defineProperty(root(),'extra',{value:{name:'replacement',items:[]},enumerable:true,configurable:true,writable:true});held.name='first';","held.name='after-recollect';"]},
 {name:'nonenumerable_then_mutate_alias',actions:["held=root().extra;Object.defineProperty(root(),'extra',{enumerable:false});held.name='first';","held.name='after-recollect';"]},
 {name:'delete_readd_scalar',actions:['delete root()[existing];write(existing,true);','write(existing,false);']},
 {name:'source_rhs_number_conversion',taskOnly:true,actions:["write('syncInterval','12');","write('syncInterval',12);"]}
];
function evaluate(text,c,requireFn){
 c.__module={exports:{}};c.__require=requireFn||(()=>{throw Error('Unexpected dependency');});
 vm.runInContext('(function(module,exports,require){\n'+text+'\n})(__module,__module.exports,__require)',c,{timeout:5000});
 const result=c.__module.exports;delete c.__module;delete c.__require;return result;
}
// A semantic snapshot (not full reflection). Record raw own names separately;
// do not compare Vue's __ob__ to the adapter's WeakMap or array method placement.
const encoder=`(function pack(value,seen=new Map()){
 if(value===undefined)return {$type:'undefined'};
 if(typeof value==='symbol')return {$type:'symbol',value:String(value)};
 if(typeof value==='function')return {$type:'function'};
 if(typeof value==='number'&&!Number.isFinite(value))return {$type:String(value)};
 if(Object.is(value,-0))return {$type:'negative-zero'};
 if(value===null||typeof value!=='object')return value;
 if(seen.has(value))return {$ref:seen.get(value)};seen.set(value,seen.size);
 if(Object.prototype.toString.call(value)==='[object Date]')return {$type:'date',value:value.toISOString()};
 const entries=Object.keys(value).sort().map(k=>[k,pack(value[k],seen)]);
 const symbols=Object.getOwnPropertySymbols(value).map(k=>[String(k),pack(value[k],seen)]);
 const proto=Object.getPrototypeOf(value);
 return {type:Array.isArray(value)?'array':'object',length:Array.isArray(value)?value.length:null,
  entries,symbols,prototype:proto===null?'null':proto===(Array.isArray(value)?Array.prototype:Object.prototype)?'standard':'custom',
  inheritedMarker:proto&&proto.auditMarker||null};
})`;
async function run(input,subject,variant,scenario,setActive){
 const dom=miniDOM(),isSource=variant==='vue_source',task=subject==='task';
 // Full Vue's compiler build checks two newline serialization strings even
 // when render functions are supplied. Model ONLY these startup probes; no
 // general innerHTML parsing, compilation, or component-template rewriting.
 const createElement=dom.document.createElement.bind(dom.document);let compilerFeatureProbes=0;
 dom.document.createElement=name=>{
  const node=createElement(name),descriptor=Object.getOwnPropertyDescriptor(dom.Node.prototype,'innerHTML');let probe=null;
  Object.defineProperty(node,'innerHTML',{get(){return probe===null?descriptor.get.call(this):probe;},set(value){
   if(value==='<div a="\n"/>'||value==='<a href="\n"/>'){probe=value;compilerFeatureProbes++;return;}
   probe=null;descriptor.set.call(this,value);
  }});return node;
 };
 let phase='construct',events=[],stored=JSON.stringify({tasks:[{id:10,title:'saved',completed:false,tags:[],priority:'medium',description:'',dueDate:''}],
  settings:{autoSave:true,syncInterval:0,notifications:true,defaultView:'list',extra:{name:'seed',items:[{value:1}]}}});
 const errors=[],warnings=[],intervals=new Map();let timer=0;
 class FixedDate extends Date{constructor(...a){super(...(a.length?a:[Date.UTC(2026,10,14,0)]));}static now(){return Date.UTC(2026,10,14,0);}}
 const c=vm.createContext({Promise,Date:FixedDate,process:{env:{NODE_ENV:'development'}},
  window:dom.window,document:dom.document,navigator:dom.window.navigator,Node:dom.Node,HTMLElement:dom.Node,
  console:{log(){},warn:(...a)=>warnings.push({phase,args:a.map(String)}),error:(...a)=>warnings.push({phase,args:a.map(String)})},
  localStorage:{getItem(){return stored;},setItem(_key,text){stored=text;events.push({kind:'storage-write',value:JSON.parse(text)});}},
  setInterval(_fn,delay){const id=++timer;intervals.set(id,delay);return id;},clearInterval(id){intervals.delete(id);},
  setTimeout(){return ++timer;},clearTimeout(){}});c.global=c;
 c.pack=vm.runInContext(encoder,c);
 const copy=x=>JSON.parse(JSON.stringify(c.pack(x)));
 const error=(channel,e,info)=>errors.push({phase,channel,name:e.name,message:e.message,info:info||null});
 setActive(e=>error('unhandledRejection',e));
 const runtime=evaluate(isSource?input.vueRuntime:input.sanRuntime,c);
 if(runtime.version!==(isSource?'2.7.16':'3.15.6'))throw Error('Pinned runtime mismatch');
 const logError=(e,_subject,info)=>error('report-only',e,info);
 let instance;
 const trace=methods=>{for(const name of task?['updateSettings','updateStatistics','saveToLocalStorage','updateSyncInterval','showNotification']:['assign','recount']){
  const original=methods[name];if(typeof original!=='function')throw Error('Missing trace method '+name);
  methods[name]=function(...args){events.push({kind:'call',name,args:copy(args)});return original.apply(this,args);};
 }};
 if(isSource){
  runtime.config.errorHandler=logError;runtime.config.warnHandler=m=>warnings.push({phase,args:[m]});
  const options=evaluate('"use strict";\n'+body(task?input.vue:input.genericVue).replace('export default','module.exports='),c);
  trace(options.methods);options.render=h=>h('main');instance=new runtime(options);instance.$mount(dom.host());
 }else{
  const Parent=evaluate(body(task?input.san:input.genericSan),c,n=>{if(n!=='san')throw Error(n);return runtime;});
  Parent.prototype.template='<main></main>';trace(Parent.prototype);const oldInit=Parent.prototype.inited;
  Parent.prototype.inited=function(){oldInit.call(this);this.__watcherScope_v7Configure({
   channel:'async-parent-watch',environment:'browser',trackingPolicy:'no-reactive-reads-or-writes',
   parentOf:n=>n.parentComponent,hooksOf:()=>[],globalHandler:()=>logError,logError
  });};
  instance=new Parent();instance.attach(dom.host());
 }
 const read=()=>isSource?instance.settings:instance.data.get('settings');
 c.root=read;c.write=(key,value)=>instance[task?'updateSettings':'assign'](key,value);
 c.existing=task?'notifications':'enabled';c.mark=text=>events.push({kind:'mark',text});c.held=null;
 const state=()=>({settings:copy(read()),
  statistics:copy(isSource?instance.statistics:instance.data.get('statistics')),
  count:copy(isSource?instance.count:instance.data.get('count')),
  notification:copy(isSource?instance.notification:instance.data.get('notification')),
  stored:stored===null?null:JSON.parse(stored),intervals:[...intervals.values()].sort((a,b)=>a-b)});
 const frames=[];
 function capture(){frames.push({phase,state:state(),events:JSON.parse(JSON.stringify(events)),
  errors:JSON.parse(JSON.stringify(errors)),warnings:JSON.parse(JSON.stringify(warnings)),
  rawRootOwnNames:Object.getOwnPropertyNames(read()).sort()});}
 await drain();events=[];errors.length=0;warnings.length=0;
 for(let index=0;index<scenario.actions.length;index++){
  phase='action_'+index+'_sync';events=[];errors.length=0;warnings.length=0;
  try{vm.runInContext(scenario.actions[index],c,{timeout:5000});}catch(e){error('action',e);}
  capture();phase='action_'+index+'_tick';events=[];errors.length=0;warnings.length=0;await drain();capture();
 }
 // Cleanup is observed separately, never discard its errors or contaminate the
 // next scenario. No real intervals/timeouts were started by this harness.
 phase='dispose';events=[];errors.length=0;warnings.length=0;
 try{isSource?instance.$destroy():instance.dispose(true,true);}catch(e){error('dispose',e);}
 await drain();
 return {subject,variant,scenario:scenario.name,frames,cleanupErrors:errors.slice(),compilerFeatureProbes,
  hostPrototypeClean:!Object.prototype.hasOwnProperty.call(Object.prototype,'auditMarker')};
}
async function audit(input){
 const runs=[];let active;
 const listener=e=>{if(!active)throw e;active(e);},before=process.listenerCount('unhandledRejection');
 process.on('unhandledRejection',listener);
 try{for(const subject of ['task','generic'])for(const scenario of scenarios){
  if(scenario.taskOnly&&subject!=='task')continue;
  for(const variant of ['vue_source','san_v7'])runs.push(await run(input,subject,variant,scenario,fn=>{active=fn;}));
 }}finally{await drain();process.removeListener('unhandledRejection',listener);active=null;}
 const pairs=[];
 for(const source of runs.filter(r=>r.variant==='vue_source')){
  const candidate=runs.find(r=>r.subject===source.subject&&r.scenario===source.scenario&&r.variant==='san_v7');
  for(let index=0;index<source.frames.length;index++){
   const left=source.frames[index],right=candidate.frames[index];if(left.phase!==right.phase)throw Error('Phase mismatch');
   const stateEqual=JSON.stringify(left.state)===JSON.stringify(right.state),eventsEqual=JSON.stringify(left.events)===JSON.stringify(right.events);
   // Different native error messages are retained in raw frames; equality uses
   // channel, category and source watcher context, not engine-specific wording.
   const normalized=errors=>errors.map(({phase,channel,name,info})=>({phase,channel,name,info}));
   const errorsEqual=JSON.stringify(normalized(left.errors))===JSON.stringify(normalized(right.errors));
   const warningsEqual=JSON.stringify(left.warnings)===JSON.stringify(right.warnings);
   pairs.push({subject:source.subject,scenario:source.scenario,phase:left.phase,stateEqual,eventsEqual,errorsEqual,warningsEqual,
    equal:stateEqual&&eventsEqual&&errorsEqual&&warningsEqual});
  }
 }
 return {scenarios:scenarios.map(s=>s.name),runs,pairs,nodeVersion:process.version,
  host_prototype_clean:runs.every(r=>r.hostPrototypeClean),rejection_listener_restored:before===process.listenerCount('unhandledRejection'),
  model_calls:0,production_eligible:false,
  scope:{nativeRuntimes:true,browserDetectedViaLimitedDOM:true,fullBrowser:false,minimalRootRender:true,
   realStorage:false,realApplicationTimers:false,sourceESModuleStrict:true,sanCommonJSPreserved:true,
   sourceBusinessCodeChanged:false,vueMetadataAndFullReflectionEquivalenceClaimed:false}};
}
if(require.main===module)audit(JSON.parse(fs.readFileSync(0,'utf8'))).then(r=>process.stdout.write(JSON.stringify(r)))
 .catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
module.exports={audit,scenarios};
