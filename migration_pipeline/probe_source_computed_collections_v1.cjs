// Native constructor AND equal-demand computed oracle. No model or production patch.
// stdin {vue,code,runtime}; stdout JSON. Sparse fixtures are not browser acceptance.
const fs=require('fs'),{parse}=require('@vue/compiler-sfc'),san=require('san');
const x=JSON.parse(fs.readFileSync(0,'utf8')),Vue=require(x.runtime),m={exports:{}},n={exports:{}};
Function('module',parse(x.vue).descriptor.script.content)(m);
let targetOptions;
Function('require','module',/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(x.code)[1])(
 name=>{if(name!=='san')throw Error('unexpected dependency');return {...san,defineComponent:o=>{targetOptions=o;return san.defineComponent(o);}};},n);
const names=Object.keys(m.exports.computed);
function inputs(kind){
 const a={id:1,dayId:'d1',start:'09:00',end:'10:00',cost:2,meta:{tag:1}},b={id:2,dayId:'d1',start:'11:00',end:'12:00',cost:3,meta:{tag:2}};
 return {initialItems:kind==='empty'?[]:kind==='sparse'?[a,,b]:kind==='undefined-record'?[a,undefined]:kind==='null-record'?[a,null]:[a,b],
  days:kind==='days-hole'?Array(1):kind==='days-null'?[null]:kind==='empty'?[]:[{id:'d1',label:'one'}]};
}
function run(kind,isVue,only){
 const props=inputs(kind),captured=[],old=Vue.config.errorHandler;let c,error=null,created=false;
 Vue.config.errorHandler=e=>captured.push(e.name);
 try{
  if(isVue){const computed=only?{[only]:m.exports.computed[only]}:m.exports.computed;c=new Vue({...m.exports,computed,propsData:props});}
  else{const C=only?san.defineComponent({...targetOptions,computed:{[only]:targetOptions.computed[only]}}):n.exports;c=new C({data:props});}
  created=true;
 }catch(e){error=e.name;}finally{Vue.config.errorHandler=old;}
 if(!c)return {constructed:created,constructorError:error,computed:{}};
 const computed={};
 for(const name of only?[only]:names){try{const value=isVue?c[name]:c.data.get(name);computed[name]={value};}catch(e){computed[name]={error:e.name};}}
 const out={constructed:created,constructorError:captured[0]||error,computed};
 if(isVue)c.$destroy();else c.dispose();return out;
}
const results={};
for(const kind of ['normal','sparse','empty','undefined-record','null-record','days-hole','days-null']){
 results[kind]={source:run(kind,true),target:run(kind,false),isolated:{}};
 for(const name of ['dayItems','totalCost','activeDayLabel'])results[kind].isolated[name]={source:run(kind,true,name),target:run(kind,false,name)};
}
function reactivity(empty,isVue){
 const props=inputs(empty?'empty':'normal');props.days=[{id:'d1',label:'one'},{id:'d2',label:'two'}];
 const c=isVue?new Vue({...m.exports,propsData:props}):new n.exports({data:props});
 const get=k=>isVue?c[k]:c.data.get(k),set=(k,v)=>isVue?(c[k]=v):c.data.set(k,v),snap=()=>({ids:get('dayItems').map(r=>r.id),sum:get('totalCost')});
 const rows=[snap()];c.selectDay('d2');rows.push(snap());set('items',[{id:9,dayId:'d2',start:'08:00',end:'09:00',cost:7}]);rows.push(snap());
 c.selectDay('d1');rows.push(snap());c.selectDay('d2');rows.push(snap());set('items',[]);rows.push(snap());
 if(isVue)c.$destroy();else c.dispose();return rows;
}
const reactive={};for(const empty of [false,true])reactive[empty?'initially-empty':'initially-populated']={source:reactivity(empty,true),target:reactivity(empty,false)};
process.stdout.write(JSON.stringify({computed_order:names,cases:results,reactive},(k,v)=>typeof v==='number'&&!Number.isFinite(v)?{nonfinite_number:String(v)}:v),()=>process.exit(0));
