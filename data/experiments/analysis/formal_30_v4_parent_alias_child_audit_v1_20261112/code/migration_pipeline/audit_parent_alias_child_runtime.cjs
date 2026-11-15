/* Native Vue/San component mounting on an explicitly LIMITED DOM adapter.
 * No simulated Data/watch/renderer: framework patching, props, computed, queue,
 * component creation and text-node writes execute natively. Not a browser/CSS test.
 */
'use strict';
const fs=require('fs'),vm=require('vm'),crypto=require('crypto');
const script=s=>/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(s)[1];
const copy=v=>JSON.parse(JSON.stringify(v,(_k,x)=>x===undefined?{$type:'undefined'}:x));
const drain=async()=>{await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));};
function miniDOM(){
 const operations=[];let doc;
 class Node{
  constructor(type,name,text=''){
   this.nodeType=type;this.tagName=type===1?name.toUpperCase():undefined;this.nodeName=this.tagName||name;
   this.data=String(text);this.childNodes=[];this.parentNode=null;this.ownerDocument=doc;
   this.attributes={};this.style={};this.listeners={};
  }
  get firstChild(){return this.childNodes[0]||null;}get lastChild(){return this.childNodes.at(-1)||null;}
  get nextSibling(){return this.parentNode?.childNodes[this.parentNode.childNodes.indexOf(this)+1]||null;}
  get previousSibling(){return this.parentNode?.childNodes[this.parentNode.childNodes.indexOf(this)-1]||null;}
  get parentElement(){return this.parentNode?.nodeType===1?this.parentNode:null;}
  get children(){return this.childNodes.filter(n=>n.nodeType===1);}
  appendChild(n){return this.insertBefore(n,null);}
  insertBefore(n,before){
   if(before!==null&&!this.childNodes.includes(before))throw Error('MiniDOM: invalid insertion anchor');
   if(n===before)return n;if(n.parentNode)n.parentNode.removeChild(n);
   const at=before===null?this.childNodes.length:this.childNodes.indexOf(before);
   this.childNodes.splice(at,0,n);n.parentNode=this;operations.push({kind:'insert',parent:this.nodeName,node:n.nodeName});return n;
  }
  removeChild(n){const at=this.childNodes.indexOf(n);if(at<0)throw Error('MiniDOM: invalid removal');
   this.childNodes.splice(at,1);n.parentNode=null;operations.push({kind:'remove',node:n.nodeName});return n;}
  setAttribute(name,value){this.attributes[name]=String(value);}
  getAttribute(name){return Object.prototype.hasOwnProperty.call(this.attributes,name)?this.attributes[name]:null;}
  hasAttribute(name){return Object.prototype.hasOwnProperty.call(this.attributes,name);}
  removeAttribute(name){delete this.attributes[name];}
  setAttributeNS(_ns,name,value){this.setAttribute(name,value);}removeAttributeNS(_ns,name){this.removeAttribute(name);}
  addEventListener(name,fn){(this.listeners[name]||(this.listeners[name]=[])).push(fn);}
  removeEventListener(name,fn){this.listeners[name]=(this.listeners[name]||[]).filter(x=>x!==fn);}
  get nodeValue(){return this.nodeType===1?null:this.data;}set nodeValue(v){this.data=String(v);operations.push({kind:'text',value:this.data});}
  get textContent(){return this.nodeType===1?this.childNodes.filter(n=>n.nodeType!==8).map(n=>n.textContent).join(''):this.data;}
  set textContent(v){if(this.nodeType!==1){this.nodeValue=v;return;}
   while(this.childNodes.length)this.removeChild(this.childNodes[0]);if(String(v)!=='')this.appendChild(doc.createTextNode(String(v)));}
  get innerHTML(){return this.textContent;}
  set innerHTML(v){if(/[<>]/.test(String(v)))throw Error('MiniDOM: HTML parsing is deliberately unsupported');this.textContent=v;}
  cloneNode(deep){const n=new Node(this.nodeType,this.nodeName,this.data);n.attributes={...this.attributes};n.style={...this.style};
   if(deep)for(const child of this.childNodes)n.appendChild(child.cloneNode(true));return n;}
  contains(n){return n===this||this.childNodes.some(c=>c.contains(n));}
 }
 doc={nodeType:9,createElement:name=>new Node(1,name),createElementNS:(_ns,name)=>new Node(1,name),
  createTextNode:text=>new Node(3,'#text',text),createComment:text=>new Node(8,'#comment',text),
  createEvent:()=>({timeStamp:0,initEvent(){}}),querySelector(){throw Error('MiniDOM: selectors unsupported');}};
 doc.documentElement=new Node(1,'html');doc.body=new Node(1,'body');doc.documentElement.appendChild(doc.body);
 const window={document:doc,navigator:{userAgent:'limited-node-dom-adapter'},addEventListener(){},removeEventListener(){},
  HTMLElement:Node,HTMLUnknownElement:class Unknown{},requestAnimationFrame:fn=>setImmediate(fn),
  getComputedStyle:()=>({})};doc.defaultView=window;
 return {document:doc,window,Node,operations,host:()=>{const n=doc.createElement('div');doc.body.appendChild(n);return n;}};
}
function evaluate(text,c,requireFn){
 c.__module={exports:{}};c.__require=requireFn||(()=>{throw Error('Unexpected require');});
 vm.runInContext('(function(module,exports,require){\n'+text+'\n})(__module,__module.exports,__require)',c,{timeout:5000});
 const result=c.__module.exports;delete c.__module;delete c.__require;return result;
}
const scenarios=['writer_scalar','writer_object','borrowed_existing_property','borrowed_array_push','borrowed_nested_item',
 'control_same_value','control_root_replacement','control_data_api_nested','borrowed_new_key_control'];
async function runOne(input,variant,scenario,active){
 const dom=miniDOM(),host=dom.host();let phase='construct',events=[];const errors=[],warnings=[];
 const c=vm.createContext({Promise,setTimeout,clearTimeout,setImmediate,
  window:dom.window,document:dom.document,navigator:dom.window.navigator,Node:dom.Node,HTMLElement:dom.Node,
  process:{env:{NODE_ENV:'development'}},console:{log(){},warn:(...a)=>warnings.push(a.map(String).join(' ')),error:(...a)=>warnings.push(a.map(String).join(' '))}});
 c.global=c;const error=(channel,e)=>errors.push({phase,channel,message:e.message||String(e)});active(error);
 const runtime=evaluate(variant==='vue_source'?input.vueRuntime:input.sanRuntime,c);
 let instance,child,read,readChild,dispose;
 if(variant==='vue_source'){
  if(runtime.version!=='2.7.16')throw Error('Vue version drift');
  runtime.config.errorHandler=e=>error('vue.config.errorHandler',e);runtime.config.warnHandler=m=>warnings.push(m);
  const options=evaluate(script(input.vue).replace('export default','module.exports='),c),old=options.methods.recount;
  options.methods.recount=function(){events.push({phase,kind:'call',name:'recount'});return old.call(this);};
  const Child=vm.runInContext(`({props:['settings'],computed:{valueText(){const s=this.settings;
     return String(s.enabled)+'|'+s.extra.name+'|'+s.extra.items.length+'|'+s.extra.items[0].value;}},
     render(h){return h('span',[this.valueText]);}})`,c);
  options.render=function(h){return h('main',[h(Child,{props:{settings:this.settings}})]);};
  instance=new runtime(options);phase='mount_sync';instance.$mount();host.appendChild(instance.$el);
  child=instance.$children[0];if(!child)throw Error('Vue native child was not created');
  read=k=>instance[k];readChild=()=>({raw:copy(child.settings),computed:child.valueText,sharesRoot:child.settings===instance.settings});
  dispose=()=>instance.$destroy();
 }else{
  if(runtime.version!=='3.15.6')throw Error('San version drift');
  const Parent=evaluate(script(input[variant]),c,name=>{if(name!=='san')throw Error(name);return runtime;});
  c.__san=runtime;
  const Child=vm.runInContext(`__san.defineComponent({template:'<span>{{valueText}}</span>',
    dataTypes:{settings:__san.DataTypes.object},computed:{valueText(){const s=this.data.get('settings');
      return String(s.enabled)+'|'+s.extra.name+'|'+s.extra.items.length+'|'+s.extra.items[0].value;}}})`,c);
  Parent.prototype.components={'bound-child':Child};Parent.prototype.template='<main><bound-child settings="{{settings}}"/></main>';
  const old=Parent.prototype.recount;Parent.prototype.recount=function(){events.push({phase,kind:'call',name:'recount'});return old.call(this);};
  instance=new Parent();phase='mount_sync';instance.attach(host);child=instance.children[0];
  if(!child||child.nodeType!==5||child.owner!==instance)throw Error('San native child/binding was not created');
  read=k=>instance.data.get(k);readChild=()=>({raw:copy(child.data.get('settings')),computed:child.data.get('valueText'),
     sharesRoot:child.data.get('settings')===instance.data.get('settings')});
  dispose=()=>instance.dispose();
 }
 c.__instance=instance;
 const frames=[];
 const capture=name=>frames.push({name,state:{parentSettings:copy(read('settings')),count:read('count'),child:readChild(),domText:host.textContent},
  events:copy(events),errors:copy(errors),warnings:copy(warnings)});
 capture('mount_sync');phase='mount_tick';events=[];await drain();capture(phase);
 phase='action_sync';events=[];
 const root=variant==='vue_source'?'__instance.settings':"__instance.data.get('settings')";
 const replacements="{enabled:true,extra:{name:'replaced',items:[{value:7}]}}";
 const actions={writer_scalar:"__instance.assign('enabled',true);",
  writer_object:"__instance.assign('extra',{name:'object',items:[{value:8}]});",
  borrowed_existing_property:`const alias=${root}.extra;alias.name='changed';`,
  borrowed_array_push:`const alias=${root}.extra.items;alias.push({value:2});`,
  borrowed_nested_item:`const alias=${root}.extra.items[0];alias.value=9;`,
  control_same_value:"__instance.assign('enabled',false);",
  control_root_replacement:variant==='vue_source'?`__instance.settings=${replacements};`:`__instance.data.set('settings',${replacements});`,
  control_data_api_nested:variant==='vue_source'?"__instance.settings.extra.name='api';":"__instance.data.set('settings.extra.name','api');",
  borrowed_new_key_control:`const alias=${root}.extra;alias.newFlag='new';`};
 try{vm.runInContext('(()=>{'+actions[scenario]+'})()',c);}catch(e){error('synchronous_action_throw',e);}
 capture(phase);phase='action_tick';events=[];await drain();capture(phase);
 const attached=variant==='vue_source'?!!(instance._isMounted&&child._isMounted):!!(instance.lifeCycle.attached&&child.lifeCycle.attached);
 dispose();await drain();
 return {scenario,variant,frameworkVersion:runtime.version,frames,nativeParentAndChildAttached:attached,
  domOperations:dom.operations,errors:copy(errors),
  boundary:{frameworkDataMocked:false,nativePropBinding:true,nativeComponentCreation:true,nativeDOMTextWrites:true,
   minimalDOMAdapter:true,browser:false,cssLayoutTested:false,canonicalTaskManagerChildTested:false,
   parentFixtureBusinessBodyChanged:false,sourceExportSyntaxAdapted:true,cleanupNotCompared:true}};
}
async function audit(input){
 const runs=[];let current;const listener=e=>{if(!current)throw e;current('process.unhandledRejection',e);};
 const count=process.listenerCount('unhandledRejection');process.on('unhandledRejection',listener);
 try{for(const scenario of scenarios)for(const variant of ['vue_source','normal','v3'])
  runs.push(await runOne(input,variant,scenario,fn=>{current=fn;}));}
 finally{await drain();process.removeListener('unhandledRejection',listener);current=null;}
 const pairs=[];
 for(const scenario of scenarios){const source=runs.find(r=>r.scenario===scenario&&r.variant==='vue_source');
  for(const variant of ['normal','v3']){const target=runs.find(r=>r.scenario===scenario&&r.variant===variant);
   for(let i=0;i<source.frames.length;i++){const a=source.frames[i],b=target.frames[i];
    pairs.push({scenario,variant,phase:a.name,parentStateEqual:JSON.stringify(a.state.parentSettings)===JSON.stringify(b.state.parentSettings),
     childComputedEqual:a.state.child.computed===b.state.child.computed,domTextEqual:a.state.domText===b.state.domText,
     effectsEqual:JSON.stringify(a.events)===JSON.stringify(b.events),errorsEqual:JSON.stringify(a.errors)===JSON.stringify(b.errors)});
   }
  }
 }
 return {runs,pairs,scenarios,nodeVersion:process.version,modelRequests:0,productionIntegrationEnabled:false,
  rejectionListenerRestored:process.listenerCount('unhandledRejection')===count,
  vueRuntimeSha256:crypto.createHash('sha256').update(input.vueRuntime).digest('hex'),
  sanRuntimeSha256:crypto.createHash('sha256').update(input.sanRuntime).digest('hex')};
}
if(require.main===module)audit(JSON.parse(fs.readFileSync(0,'utf8'))).then(r=>process.stdout.write(JSON.stringify(r)))
 .catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
module.exports={audit,miniDOM};
