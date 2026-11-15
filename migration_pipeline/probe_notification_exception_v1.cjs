// Frozen-fixture proposals only. Not a production rewrite or observer adapter.
const fs=require('fs'),san=require('san'),{parse}=require('@vue/compiler-sfc');
function load(x){
  const source={exports:{}},target={exports:{}};let targetOptions;
  Function('module',parse(x.vue).descriptor.script.content)(source);
  Function('require','module',/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(x.code)[1])(
    name=>{if(name!=='san')throw Error('unexpected dependency');return {...san,defineComponent:options=>{
      targetOptions=options;return san.defineComponent(options);
    }};},target);
  return {source:source.exports,target:targetOptions,Vue:require(x.runtime)};
}
const proposals={
  unchanged:null,
  deep_detach:function(index,delta){
    const rows=JSON.parse(JSON.stringify(this.data.get('dayItems'))),target=index+delta;
    if(target<0||target>=rows.length)return;
    const temp=rows[index].start;rows[index].start=rows[target].start;rows[target].start=temp;
    const mapped={};rows.forEach(item=>mapped[item.id]=item);
    const next=this.data.get('items').map(item=>mapped[item.id]?Object.assign({},mapped[item.id]):item);
    this.data.set('items',next);this.data.set('saved',false);this.notify(next);
  },
  nested_data_set:function(index,delta){
    const root=this.data.get('items'),rows=this.data.get('dayItems').slice(),target=index+delta;
    if(target<0||target>=rows.length)return;
    const a=root.indexOf(rows[index]),b=root.indexOf(rows[target]),temp=rows[index].start,nextStart=rows[target].start;
    this.data.set('items['+a+'].start',nextStart);this.data.set('items['+b+'].start',temp);
    const selected=new Set(rows.map(item=>item.id));
    const next=this.data.get('items').map(item=>selected.has(item.id)?Object.assign({},item):item);
    this.data.set('items',next);this.data.set('saved',false);this.notify(next);
  },
  force_same_root:function(index,delta){
    const root=this.data.get('items'),rows=this.data.get('dayItems').slice(),target=index+delta;
    if(target<0||target>=rows.length)return;
    const temp=rows[index].start;rows[index].start=rows[target].start;
    this.data.set('items',root,{force:true});rows[target].start=temp;this.data.set('items',root,{force:true});
    const mapped={};rows.forEach(item=>mapped[item.id]=item);
    const next=this.data.get('items').map(item=>mapped[item.id]?Object.assign({},mapped[item.id]):item);
    this.data.set('items',next);this.data.set('saved',false);this.notify(next);
  },
  shallow_republish:function(index,delta){
    const root=this.data.get('items'),rows=this.data.get('dayItems').slice(),target=index+delta;
    if(target<0||target>=rows.length)return;
    const temp=rows[index].start;rows[index].start=rows[target].start;
    this.data.set('items',root.slice());rows[target].start=temp;this.data.set('items',root.slice());
    const mapped={};rows.forEach(item=>mapped[item.id]=item);
    const next=this.data.get('items').map(item=>mapped[item.id]?Object.assign({},mapped[item.id]):item);
    this.data.set('items',next);this.data.set('saved',false);this.notify(next);
  }
};
const rows=()=>[
  {id:1,dayId:'d1',start:'09:00',end:'11:00',place:'A',cost:2,meta:{tag:1}},
  {id:2,dayId:'d1',start:'10:00',end:'12:00',place:'B',cost:3,meta:{tag:2}},
  {id:3,dayId:'d2',start:'14:00',end:'15:00',place:'C',cost:7,meta:{tag:3}}
];
async function shared(x){
  const {source,target,Vue}=load(x);
  async function run(isVue,proposal,args){
    const C=isVue?null:san.defineComponent(proposal?{...target,moveItem:proposal}:target);
    const c=isVue?new Vue({...source,propsData:{initialItems:rows()}}):new C({data:{initialItems:rows()}});
    const get=k=>isVue?c[k]:c.data.get(k),original=get('items'),records=original.slice();
    if(isVue)c.saved=true;else c.data.set('saved',true);
    const starts=items=>items.map(item=>item.start);
    const view=()=>({starts:starts(get('items')),visibleIds:get('dayItems').map(item=>item.id),
      conflicts:get('conflictIds').slice(),totalCost:get('totalCost'),remainingBudget:get('remainingBudget'),saved:get('saved')});
    view();
    const commits=[],rawItemsChanges=[],notices=[],notifications=[],events=[];
    if(isVue){const setter=c.setValue;c.setValue=function(k,v){if(k==='items')commits.push({key:k,force:false});return setter.call(this,k,v);};}
    else{
      const setter=c.data.set;c.data.set=function(k,v,options){
        if(typeof k==='string'&&(k==='items'||k.startsWith('items[')))commits.push({key:k,force:!!options?.force});
        return setter.call(this,k,v,options);
      };
      c.data.listen(change=>{if(change.expr.paths[0].value==='items')rawItemsChanges.push({
        rootIsOriginal:get('items')===original,starts:starts(get('items')),force:!!change.option?.force});});
    }
    const observe=(value,oldValue)=>notices.push({starts:starts(value),saved:get('saved'),
      rootIsOriginal:value===original,oldRootIsOriginal:oldValue===original,valueIsOld:value===oldValue,
      recordsAreOriginal:value.map((r,i)=>r===records[i])});
    if(isVue)c.$watch(()=>c.items,(value,old)=>observe(value,old),{deep:true,sync:true});
    else c.watch('items',(value,info)=>observe(value,info.oldValue));
    const notify=c.notify;c.notify=function(payload){notifications.push({payloadIsState:payload===get('items'),view:view()});return notify.call(this,payload);};
    const on=payload=>events.push({payloadIsState:payload===get('items'),oldStarts:starts(records),view:view()});
    if(isVue)c.$on('itinerary-change',on);else c.on('itinerary-change',on);
    let error=null;try{c.moveItem(...args);}catch(e){error={name:e.name,message:e.message};}
    const immediate=view();await new Promise(resolve=>isVue?Vue.nextTick(resolve):san.nextTick(resolve));
    const current=get('items'),out={error,immediate,afterTick:view(),rootChanged:current!==original,
      oldStarts:starts(records),sameRecords:current.map((r,i)=>r===records[i]),sameNested:current.map((r,i)=>r.meta===records[i].meta),
      commits,notices,rawItemsChanges,notifications,events};
    if(isVue)c.$destroy();else c.dispose();return out;
  }
  const out={};
  for(const [name,proposal] of Object.entries(proposals)){
    out[name]={};
    for(const [kind,args] of Object.entries({forward:[0,1],backward:[1,-1],noop:[0,0],lower:[0,-1],upper:[1,1]}))
      out[name][kind]={source:await run(true,null,args),target:await run(false,proposal,args)};
  }
  return {scope:'controlled_native_unmounted_fixture; added external deep/sync observer is not a new source requirement',
    proposals:out,production_rewrite_installed:false,all_observers_equivalent_proven:false};
}
function phases(x){
  const {source,target,Vue}=load(x);
  const kinds=['normal','empty-days','days-hole','days-null','days-undefined'];
  const days=kind=>kind==='normal'?[{id:'d1',label:'one'}]:kind==='empty-days'?[]:
    kind==='days-hole'?Array(1):kind==='days-null'?[null]:[undefined];
  function run(kind,isVue,proposal){
    const trace=[],handlerErrors=[],oldHandler=Vue.config.errorHandler;
    const original=isVue?source.computed.activeDayLabel:target.computed.activeDayLabel;
    const evaluated=function(){trace.push('label:evaluate');try{return original.call(this);}catch(e){trace.push('label:throw:'+e.name);throw e;}};
    const getter=proposal==='catch_return_empty'?function(){try{return evaluated.call(this);}catch(e){trace.push('label:swallowed');return '';}}:evaluated;
    const computed={...(isVue?source.computed:target.computed),activeDayLabel:getter};
    if(proposal==='drop_computed'&&!isVue)delete computed.activeDayLabel;
    const initialItems=rows(),props={initialItems,days:days(kind)};
    let c,constructorError=null;
    Vue.config.errorHandler=e=>handlerErrors.push(e.name);
    trace.push('construct:start');
    try{
      if(isVue){const created=source.created;c=new Vue({...source,computed,propsData:props,created(){
        trace.push('created:enter');try{return created.call(this);}finally{trace.push('created:exit');}
      }});}
      else{const inited=target.inited,C=san.defineComponent({...target,computed,inited(){
        trace.push('inited:enter');try{return inited.call(this);}finally{trace.push('inited:exit');}
      }});c=new C({data:props});}
      trace.push('construct:return');
    }catch(e){constructorError=e.name;trace.push('construct:throw:'+e.name);}
    finally{Vue.config.errorHandler=oldHandler;}
    if(!c)return {constructed:false,constructorError,handlerErrors,trace,firstRead:null,recovery:null};
    const demand=()=>{trace.push('demand:start');try{const value=isVue?c.activeDayLabel:c.data.get('activeDayLabel');
      trace.push('demand:return');return {kind:'value',type:typeof value,value:value===undefined?null:value};
    }catch(e){trace.push('demand:throw:'+e.name);return {kind:'error',name:e.name};}};
    const firstRead=demand();trace.push('recover:start');
    let recoveryError=null;try{
      const good=[{id:'d1',label:'one'}];if(isVue)c.days=good;else c.data.set('days',good);
      c.selectDay('d1');
    }catch(e){recoveryError=e.name;}
    const recovery={error:recoveryError,read:demand()};trace.push('recover:end');
    const out={constructed:true,constructorError,handlerErrors,trace,firstRead,recovery};
    if(isVue)c.$destroy();else c.dispose();return out;
  }
  const out={};
  for(const proposal of ['unchanged','catch_return_empty','drop_computed']){
    out[proposal]={};for(const kind of kinds)out[proposal][kind]={source:run(kind,true,'unchanged'),target:run(kind,false,proposal)};
  }
  return {scope:'native constructor / explicit computed demand / recovery, not DOM render or full exception-policy equivalence',
    variants:out,production_rewrite_installed:false};
}
async function native(x){return {shared:await shared(x),phases:phases(x),runtime:{source:require(x.runtime).version,target:san.version},
  source_or_target_files_written:false,browser_started:false};}
module.exports={native,proposals};
if(require.main===module)(async()=>{try{const x=JSON.parse(fs.readFileSync(0,'utf8'));
  process.stdout.write(JSON.stringify(await native(x)),()=>process.exit(0));}
catch(e){process.stderr.write(e.stack,()=>process.exit(1));}})();
