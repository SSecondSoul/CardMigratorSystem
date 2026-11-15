// Frozen-component native namespace counterexamples; proposals stay in memory.
const fs=require('fs'),{parse}=require('@vue/compiler-sfc'),san=require('san');
const original=require('./probe_source_dynamic_setter_v1.cjs');
const definitions={missing:null,instance:original.definitions.instance,path:original.definitions.path,
  coerced_finite_fallback:original.definitions.coerced_finite_fallback,
  reject_data_then_finite:"setValue(key,value){const property=Reflect.ownKeys({[key]:0})[0];if(property==='data')throw new RangeError('reserved data');if(['items','activeDayId','draft','budgetLimit','saved','nextId'].includes(property)){this.data.set(property,value);}else{this[property]=value;}}"};
function variants(code){
  const anchor='module.exports = san.defineComponent({';
  if(code.split(anchor).length!==2)throw Error('ambiguous frozen candidate');
  return Object.fromEntries(Object.entries(definitions).map(([name,body])=>[name,body===null?code:code.replace(anchor,()=>anchor+'\n'+body+',\n')]));
}
function native(x){
  const Vue=require(x.runtime),source={exports:{}};
  Function('module',parse(x.vue).descriptor.script.content)(source);
  const cases=[
    {name:'root-control',key:()=> 'saved',value:()=>true,namespace:false},
    {name:'data-null',key:()=> 'data',value:()=>null,namespace:true},
    {name:'data-number',key:()=> 'data',value:()=>42,namespace:true},
    {name:'data-object',key:()=> 'data',value:()=>({marker:7}),namespace:true},
    {name:'coerced-data-null',key:log=>({[Symbol.toPrimitive](hint){log.push(hint);return 'data';}}),value:()=>null,namespace:true}
  ];
  function run(code,entry,isVue){
    const m={exports:{}};
    if(!isVue)Function('require','module',/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code)[1])(require,m);
    const component=isVue?new Vue(source.exports):new m.exports();
    const store=isVue?component.$data:component.data;
    const read=k=>isVue?store[k]:store.get(k);
    const coercions=[],key=entry.key(coercions),value=entry.value();
    let setterError=null,businessError=null,watchError=null;
    try{component.setValue(key,value);}catch(e){setterError=e.name;}
    const publicDataMatchesInput=entry.namespace?Object.hasOwn(component,'data')&&component.data===value:null;
    const pointerIntact=isVue?component.$data===store:component.data===store;
    // This is the real frozen public business method, not an invented setter caller.
    try{component.updateBudget({target:{value:'321'}});}catch(e){businessError=e.name;}
    // Mapped native watch registration demonstrates continued framework operation.
    try{if(isVue){const stop=component.$watch('budgetLimit',()=>{});stop();}
      else component.watch('budgetLimit',()=>{});}catch(e){watchError=e.name;}
    const observation={setterError,businessError,watchError,publicDataMatchesInput,
      nativeStorePointerIntact:pointerIntact,budgetAfterBusinessCall:read('budgetLimit'),
      savedProjected:read('saved'),keyCoercions:coercions};
    // Only after recording failures, restore for test disposal. Never a repair.
    if(!isVue&&component.data!==store)component.data=store;
    if(isVue)component.$destroy();else component.dispose();
    return observation;
  }
  const rows={};
  for(const [name,code] of Object.entries(variants(x.code))){
    rows[name]={};
    for(const entry of cases){
      const a=run(code,entry,true),b=run(code,entry,false);
      rows[name][entry.name]={source:a,target:b,declaredObservationEqual:JSON.stringify(a)===JSON.stringify(b)};
    }
  }
  return {scope:'native_unmounted_frozen_component_instances_with_mapped_state_and_public_data_read',
    cases:cases.map(c=>c.name),variants:rows,source_runtime:Vue.version,target_runtime:san.version,
    production_adapter_installed:false,browser_or_dom_render_verified:false,
    cleanup_restore_is_test_disposal_only:true};
}
module.exports={definitions,variants,native};
if(require.main===module){try{const x=JSON.parse(fs.readFileSync(0,'utf8'));
  process.stdout.write(JSON.stringify(native(x)),()=>process.exit(0));}
catch(e){process.stderr.write(e.stack,()=>process.exit(1));}}
