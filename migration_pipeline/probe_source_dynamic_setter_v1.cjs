// Frozen-input native counterexamples only; no production adapter is installed.
const fs=require('fs'),{parse}=require('@vue/compiler-sfc'),san=require('san');
const definitions={
 no_op:'setValue(key,value){}',
 instance:'setValue(key,value){this[key]=value;}',
 path:'setValue(key,value){this.data.set(key,value);}',
 finite_fallback:"setValue(key,value){if(['items','activeDayId','draft','budgetLimit','saved','nextId'].includes(key)){this.data.set(key,value);}else{this[key]=value;}}",
 coerced_finite_fallback:"setValue(key,value){const property=Reflect.ownKeys({[key]:0})[0];if(['items','activeDayId','draft','budgetLimit','saved','nextId'].includes(property)){this.data.set(property,value);}else{this[property]=value;}}"
};
function variants(code){const anchor='module.exports = san.defineComponent({';if(code.split(anchor).length!==2)throw Error('ambiguous audit fixture');
 return {missing:code,...Object.fromEntries(Object.entries(definitions).map(([name,body])=>[name,code.replace(anchor,anchor+'\n'+body+',\n')]))};}
function native(x){
 const Vue=require(x.runtime),source={exports:{}};Function('module',parse(x.vue).descriptor.script.content)(source);
 const rootValues={items:()=>[],activeDayId:()=>'d2',draft:()=>({start:'12:00',end:'13:00',place:'A',cost:2}),budgetLimit:()=>123,saved:()=>true,nextId:()=>42};
 const cases=[...Object.keys(rootValues).map(field=>({name:'root:'+field,key:()=>field,value:rootValues[field],property:field})),
  {name:'dotted-literal',key:()=>'draft.start',value:()=>'literal',property:'draft.start'},
  {name:'late-instance',key:()=>'lateField',value:()=>7,property:'lateField'},
  {name:'coerced-root',key:log=>({[Symbol.toPrimitive](hint){log.push(hint);return 'saved';}}),value:()=>true,property:'saved'},
  {name:'coerced-dotted',key:log=>({[Symbol.toPrimitive](hint){log.push(hint);return 'draft.start';}}),value:()=>'literal',property:'draft.start'},
  {name:'throwing-key',key:log=>({[Symbol.toPrimitive](hint){log.push(hint);throw new RangeError('key coercion');}}),value:()=>7,property:'unwritten'},
  {name:'symbol-literal',key:()=>Symbol('literal'),value:()=>7,symbol:true},
  {name:'runtime-data-collision',key:()=>'data',value:()=>({marker:7}),property:'data'},
  {name:'numeric-literal',key:()=>0,value:()=>7,property:'0'},
  {name:'undefined-literal',key:()=>undefined,value:()=>7,property:'undefined'}];
 function run(code,entry,isVue){const m={exports:{}};if(!isVue)Function('require','module',/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(code)[1])(require,m);
  const c=isVue?new Vue(source.exports):new m.exports(),originalStore=isVue?c.$data:c.data;
  const read=k=>isVue?originalStore[k]:originalStore.get(k),coercions=[],key=entry.key(coercions),value=entry.value(),property=entry.symbol?key:entry.property;
  let error=null,result;try{result=c.setValue(key,value);}catch(e){error=e.name;}
  const declared=Object.hasOwn(rootValues,property);
  const out={error,returnUndefined:result===undefined,coercions,
   state:{ids:read('items').map(r=>r.id),active:read('activeDayId'),draft:read('draft'),budget:read('budgetLimit'),saved:read('saved'),next:read('nextId')},
   mappedRootIsInput:declared?read(property)===value:null,
   extraInstancePropertyIsInput:declared?null:Object.hasOwn(c,property)&&c[property]===value,
   extraStorePropertyPresent:declared?null:Object.hasOwn(isVue?originalStore:originalStore.raw,property),
   frameworkStorePointerIntact:isVue?c.$data===originalStore:c.data===originalStore};
  // Record the corruption above, then restore only to dispose this test instance.
  if(!isVue&&c.data!==originalStore)c.data=originalStore;
  if(isVue)c.$destroy();else c.dispose();return out;
 }
 const outputs={};for(const [name,code] of Object.entries(variants(x.code))){outputs[name]={};for(const entry of cases){
  const a=run(code,entry,true),b=run(code,entry,false);outputs[name][entry.name]={source:a,target:b,mappedProjectionEqual:JSON.stringify(a)===JSON.stringify(b)};
 }}
 return {scope:'mapped declared-state + literal extra property projection, not complete instance/API equivalence',cases:cases.map(c=>c.name),variants:outputs,production_adapter_installed:false};
}
module.exports={definitions,variants,native};
if(require.main===module){try{const x=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(native(x)),()=>process.exit(0));}
 catch(e){process.stderr.write(e.stack,()=>process.exit(1));}}
