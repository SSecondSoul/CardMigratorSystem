// Audit only. Never rewrites code, grants an exemption, or changes validation.
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types'),traverse=require('@babel/traverse').default;
const {parse}=require('@vue/compiler-sfc');
const {one,safe,method,same,sourceParent}=require('./utils/source_render_call_semantics.cjs');
const own=(n,name)=>t.isMemberExpression(n)&&!n.computed&&t.isThisExpression(n.object)&&(!name||t.isIdentifier(n.property,{name}));
const sourceCall=(n,name)=>t.isCallExpression(n)&&own(n.callee,name);
function staticAudit(x){
 const {descriptor,errors}=parse(x.vue);if(errors.length||!descriptor.script||!descriptor.template||descriptor.scriptSetup)return {status:'unassessed',reason:'unsupported_sfc'};
 const ast=parser.parse(descriptor.script.content,{sourceType:'unambiguous'}),parent=sourceParent(ast),methods=one(parent,'methods')?.value;
 const block=/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(x.code);if(!safe(parent)||!safe(methods)||!block)return {status:'unassessed',reason:'ambiguous_options'};
 const targetAst=parser.parse(block[1],{sourceType:'unambiguous'}),exports=[];let badExport=false;
 traverse(targetAst,{AssignmentExpression(p){if(same(p.node.left,parser.parseExpression('module.exports'))){
  const n=p.node.right;if(p.node.operator!=='='||!t.isCallExpression(n)||!same(n.callee,parser.parseExpression('san.defineComponent'))||n.arguments.length!==1||!safe(n.arguments[0]))badExport=true;
  else exports.push(n.arguments[0]);
 }}});
 if(badExport||exports.length!==1)return {status:'unassessed',reason:'ambiguous_target_parent'};
 if(one(parent,'components')&&!safe(one(parent,'components').value)||one(parent,'components')?.value?.properties?.length)
  return {status:'unassessed',reason:'child_scopes_require_separate_resolution'};
 const target=exports[0],setters=methods.properties.filter(p=>{
  if(!t.isObjectMethod(p)||p.params.length!==2||p.params.some(p=>!t.isIdentifier(p))||p.async||p.generator||p.kind!=='method')return false;
  const [k,v]=p.params.map(p=>p.name);if(k===v)return false;
  return same(p,parser.parseExpression(`({${p.key.name}(${k},${v}){this[${k}]=${v};}})`).properties[0]);
 });
 if(setters.length!==1)return {status:'unassessed',reason:'no_unique_exact_instance_assignment_setter'};
 const setter=setters[0],name=setter.key.name,data=method(parent,'data');
 const dataObject=data?.body.body.length===1&&data.body.body[0].argument;
 if(!safe(dataObject))return {status:'unassessed',reason:'unknown_declared_data'};
 const fields=new Set(dataObject.properties.map(p=>p.key.name||p.key.value)),calls=[],escapes=[],dynamicAccess=[],instanceEscapes=[];
 const owner=p=>p.findParent(p=>p.isObjectMethod())?.node.key.name||'<non-method>';
 traverse(ast,{CallExpression(p){if(sourceCall(p.node,name)){
  const arg=p.node.arguments[0];calls.push({caller:owner(p),key:t.isStringLiteral(arg)?arg.value:null,
   key_is_literal:t.isStringLiteral(arg),declared_data:t.isStringLiteral(arg)&&fields.has(arg.value),arguments:p.node.arguments.length});
 }},MemberExpression(p){
  if(own(p.node,name)&&!(p.parentPath.isCallExpression()&&p.parentPath.node.callee===p.node))escapes.push({caller:owner(p)});
  if(t.isThisExpression(p.node.object)&&p.node.computed){
   const allowed=p.findParent(p=>p.isObjectMethod())?.node===setter&&p.parentPath.isAssignmentExpression()&&p.parentPath.node.left===p.node;
   if(!allowed)dynamicAccess.push({caller:owner(p)});
  }
 },OptionalMemberExpression(p){if(t.isThisExpression(p.node.object))dynamicAccess.push({caller:owner(p),optional:true});},
 ThisExpression(p){if(!(p.parentPath.isMemberExpression()||p.parentPath.isOptionalMemberExpression())||p.parentPath.node.object!==p.node)instanceEscapes.push({caller:owner(p)});}});
 const template=descriptor.template.content,escaped=name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),templateMention=new RegExp('(^|[^A-Za-z0-9_$])'+escaped+'(?![A-Za-z0-9_$])').test(template);
 const targetWrites=[];traverse(targetAst,{CallExpression(p){const n=p.node;
  if(t.isMemberExpression(n.callee)&&!n.callee.computed&&t.isIdentifier(n.callee.property,{name:'set'})&&own(n.callee.object,'data')){
   const arg=n.arguments[0];targetWrites.push({caller:owner(p),key:t.isStringLiteral(arg)?arg.value:null,key_is_literal:t.isStringLiteral(arg)});
  }
 }});
 const counts=rows=>{const o={};for(const r of rows){const caller=r.caller==='created'?'inited':r.caller,k=caller+':'+r.key;o[k]=(o[k]||0)+1;}return o;};
 const sourceCounts=counts(calls),targetCounts=counts(targetWrites);
 const pairs=Object.keys(sourceCounts).sort().map(k=>({site:k,source_count:sourceCounts[k],target_count:targetCounts[k]||0}));
 return {status:'assessed',helper:name,declared_data:[...fields].sort(),source_calls:calls,target_root_writes:targetWrites,
  source_call_count:calls.length,source_key_counts:counts(calls.map(c=>({...c,caller:'all'}))),
  all_known_calls_literal_declared:calls.length>0&&calls.every(c=>c.key_is_literal&&c.declared_data&&c.arguments===2),
  call_site_write_counts:pairs,site_counts_match:pairs.every(p=>p.source_count===p.target_count)&&Object.keys(targetCounts).length===pairs.length,
  source_reference_escapes:escapes,dynamic_instance_accesses:dynamicAccess,instance_escapes:instanceEscapes,template_mentions_helper:templateMention,
  no_source_watch_option:!one(parent,'watch'),source_mixins_or_extends:!!(one(parent,'mixins')||one(parent,'extends')),
  supplied_sfc_calls_closed:!escapes.length&&!dynamicAccess.length&&!instanceEscapes.length&&!templateMention&&!one(parent,'mixins')&&!one(parent,'extends')
   &&calls.length>0&&calls.every(c=>c.key_is_literal&&c.declared_data&&c.arguments===2),
  target_callable_present:!!method(target,name),rhs_and_timing_equivalence_proven:false,
  external_consumers_checked:false,external_calls_excluded_from_contract:false,validation_exemption_granted:false};
}
async function nativeAudit(x){
 const san=require('san'),Vue=require(x.runtime),sourceModule={exports:{}},targetModule={exports:{}};
 Function('module',parse(x.vue).descriptor.script.content)(sourceModule);
 Function('require','module',/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(x.code)[1])(require,targetModule);
 const rows=()=>[{id:1,dayId:'d1',start:'09:00',end:'11:00',place:'A',cost:2,meta:{tag:1}},
  {id:2,dayId:'d1',start:'10:00',end:'12:00',place:'B',cost:3,meta:{tag:2}},
  {id:3,dayId:'d2',start:'14:00',end:'15:00',place:'C',cost:7,meta:{tag:3}}];
 async function run(isVue,args,observer){
  const c=isVue?new Vue({...sourceModule.exports,propsData:{initialItems:rows()}}):new targetModule.exports({data:{initialItems:rows()}});
  const get=k=>isVue?c[k]:c.data.get(k),trace=[],getStarts=items=>items.map(r=>r.start),original=get('items'),oldRecords=original.slice();
  if(isVue)c.saved=true;else c.data.set('saved',true);
  const view=()=>({starts:getStarts(get('items')),visibleIds:get('dayItems').map(r=>r.id),conflicts:get('conflictIds').slice(),
   counts:[c.dayCount('d1'),c.dayCount('d2')],totalCost:get('totalCost'),remainingBudget:get('remainingBudget'),saved:get('saved')});
  view(); // Warm both computed graphs before the source-observable writes.
  if(isVue){const f=c.setValue;c.setValue=function(k,v){trace.push({phase:'root_commit',key:k});return f.call(this,k,v);};}
  else{const f=c.data.set;c.data.set=function(k,v,...rest){trace.push({phase:typeof k==='string'?'root_commit':'runtime_internal_store',key:k});return f.call(this,k,v,...rest);};}
  const notify=c.notify;c.notify=function(p){trace.push({phase:'notify',payloadIsState:p===get('items'),view:view()});return notify.call(this,p);};
  const on=p=>trace.push({phase:'event',payloadIsState:p===get('items'),oldStarts:getStarts(oldRecords),view:view()});
  if(isVue)c.$on('itinerary-change',on);else c.on('itinerary-change',on);
  const notices=[];
  if(observer){const fn=value=>{const item={starts:getStarts(value),saved:get('saved')};notices.push(item);trace.push({phase:'extra_observer',...item});};
   if(isVue)c.$watch(()=>c.items,fn,{deep:true,sync:true});else c.watch('items',fn);
  }
  let error=null,value;try{value=c.moveItem(...args);}catch(e){error=e.name;}
  const immediate=view();await new Promise(resolve=>isVue?Vue.nextTick(resolve):san.nextTick(resolve));
  const now=get('items'),result={error,returnUndefined:value===undefined,immediate,afterTick:view(),rootChanged:now!==original,
   oldStarts:getStarts(oldRecords),sameRecords:now.map((r,i)=>r===oldRecords[i]),sameNested:now.map((r,i)=>r.meta===oldRecords[i].meta),trace,notices};
  if(isVue)c.$destroy();else c.dispose();return result;
 }
 const cases={};for(const [name,args] of Object.entries({forward:[0,1],backward:[1,-1],noop:[0,0],lower:[0,-1],upper:[1,1]}))
  cases[name]={source:await run(true,args,false),target:await run(false,args,false)};
 const observer={source:await run(true,[0,1],true),target:await run(false,[0,1],true),
  scope:'extra external deep/synchronous observer probe, absent from supplied source SFC; not a provider implementation or waiver'};
 const a=new Vue(sourceModule.exports),b=new targetModule.exports(),start=a.draft.start;
 a.setValue('draft.start','literal');a.setValue('lateField',7);
 b.data.set('draft.start','literal');b.data.set('lateField',7);
 const setter={source:{literalInstanceKey:a['draft.start'],nestedStart:a.draft.start,originalNestedStart:start,lateInstanceField:a.lateField,
   lateDeclared:Object.prototype.hasOwnProperty.call(a.$data,'lateField')},
  target:{callableType:typeof b.setValue},naivePathStore:{literalInstanceKeyPresent:Object.prototype.hasOwnProperty.call(b,'draft.start'),
   nestedStart:b.data.get('draft').start,lateInstanceFieldPresent:Object.prototype.hasOwnProperty.call(b,'lateField'),lateStoreField:b.data.get('lateField')},
  production_adapter_installed:false};
 a.$destroy();b.dispose();
 // These are actual supplied-source action paths, not arbitrary external APIs.
 function sparseAction(isVue,action){
  const normal=rows(),initial=[normal[0],,normal[1]],c=isVue?new Vue({...sourceModule.exports,propsData:{initialItems:initial}}):new targetModule.exports({data:{initialItems:initial}});
  const get=k=>isVue?c[k]:c.data.get(k),events=[];
  const snapshot=()=>({keys:Object.keys(get('items')),length:get('items').length,ids:get('dayItems').map(r=>r.id),total:get('totalCost'),saved:get('saved')});
  const on=p=>events.push({payloadIsState:p===get('items'),snapshot:snapshot()});if(isVue)c.$on('itinerary-change',on);else c.on('itinerary-change',on);
  const before=snapshot();let error=null;
  try{if(action==='remove')c.removeItem(1);else if(action==='public-count')c.dayCount('d1');}
  catch(e){error={name:e.name,message:e.message};}
  const out={error,before,after:snapshot(),events};if(isVue)c.$destroy();else c.dispose();return out;
 }
 const actionPaths={};for(const action of ['remove','public-count'])actionPaths[action]={source:sparseAction(true,action),target:sparseAction(false,action),
  scope:action==='remove'?'supplied source template click path':'public source method; target template uses a private source-derived copy'};
 return {component_only:cases,extra_observer:observer,dynamic_setter:setter,additional_call_path_probes:actionPaths};
}
module.exports={staticAudit,nativeAudit};
if(require.main===module)(async()=>{
 try{const x=JSON.parse(fs.readFileSync(0,'utf8')),out={static:staticAudit(x)};if(x.run_native)out.native=await nativeAudit(x);
  process.stdout.write(JSON.stringify(out),()=>process.exit(0));
 }catch(e){process.stdout.write(JSON.stringify({error:e.message}),()=>process.exit(1));}
})();
