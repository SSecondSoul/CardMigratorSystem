// Local function/native-runtime oracle only. Not production or DOM acceptance.
const fs=require('fs'),san=require('san'),{parse}=require('@vue/compiler-sfc');
const {nativeAudit}=require('./audit_remaining_source_contracts_v1.cjs');
function options(code){let out;Function('require','module',/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(code)[1])(
 name=>{if(name!=='san')throw Error('unexpected require');return {...san,defineComponent:o=>{out=o;return san.defineComponent(o);}};},{exports:{}});return out;}
function functions(x){const m={exports:{}};Function('module',parse(x.vue).descriptor.script.content)(m);
 const source=m.exports.methods,before=options(x.before),after=options(x.after),out={};
 const modes=['dense','sparse','all-holes','empty','explicit-null','explicit-undefined','missing-field','append','delete-next','inherited-index','throwing-getter'];
 for(const method of ['removeItem','dayCount'])for(const mode of modes){
  function run(methods,target){
   const a={id:1,dayId:'d1'},b={id:2,dayId:'d1'},added={id:3,dayId:'d1'},labels=new Map([[a,'a'],[b,'b'],[added,'added']]);
   let items=[a,b],saved=true;const getterReads=[],trace=[],field=method==='removeItem'?'id':'dayId';
   if(mode==='sparse')items=[a,,b];if(mode==='all-holes')items=new Array(3);if(mode==='empty')items=[];
   if(mode==='explicit-null')items=[a,null,b];if(mode==='explicit-undefined')items=[a,undefined,b];
   if(mode==='missing-field')delete a[field];
   if(mode==='inherited-index'){items=[a,,b];const proto=Object.create(Array.prototype);proto[1]=added;Object.setPrototypeOf(items,proto);}
   if(['append','delete-next','throwing-getter'].includes(mode))Object.defineProperty(a,field,{get(){getterReads.push(field);
    if(mode==='throwing-getter')throw new RangeError('source getter');
    if(mode==='append')items.push(added);else delete items[1];return method==='removeItem'?1:'d1';}});
   const original=items,records=[a,b,added],snapshot=()=>({length:items.length,keys:Object.keys(items),labels:items.map(r=>labels.get(r)||(r===null?'null':'undefined')),saved});
   const context={};for(const [k,v] of Object.entries(methods))if(typeof v==='function')context[k]=v;
   const write=(k,v)=>{if(k==='items')items=v;else if(k==='saved')saved=v;else throw Error('unexpected field');trace.push({phase:'commit',key:k,view:snapshot()});};
   if(target){context.data={get:k=>k==='items'?items:saved,set:write};context.fire=(name,p)=>trace.push({phase:'event',name,payloadIsState:p===items,view:snapshot()});}
   else{Object.defineProperties(context,{items:{get:()=>items,set:v=>write('items',v)},saved:{get:()=>saved,set:v=>write('saved',v)}});
    context.$emit=(name,p)=>trace.push({phase:'event',name,payloadIsState:p===items,view:snapshot()});}
   if(context.notify){const notify=context.notify;context.notify=function(p){trace.push({phase:'notify',payloadIsState:p===items,view:snapshot()});return notify.call(this,p);};}
   let error=null,value;try{value=context[method](method==='removeItem'?1:'d1');}catch(e){error={name:e.name,message:e.message};}
   return {error,returnUndefined:value===undefined,value:value===undefined?null:value,getterReads,trace,view:snapshot(),rootChanged:items!==original,
    originalLabels:original.map(r=>labels.get(r)||(r===null?'null':'undefined')),recordIdentities:items.every(r=>records.includes(r)||r===null||r===undefined)};
  }
  out[method+':'+mode]={source:run(source,false),before:run(before,true),after:run(after,true)};
 }
 return out;
}
module.exports={functions};
if(require.main===module)(async()=>{try{
 const x=JSON.parse(fs.readFileSync(0,'utf8')),out={body:functions(x),before:await nativeAudit({vue:x.vue,code:x.before,runtime:x.runtime}),after:await nativeAudit({vue:x.vue,code:x.after,runtime:x.runtime})};
 process.stdout.write(JSON.stringify(out),()=>process.exit(0));
}catch(e){process.stderr.write(e.stack,()=>process.exit(1));}})();
