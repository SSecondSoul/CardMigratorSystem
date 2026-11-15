/* Isolated V10 descriptor/opaque-value revision. Source-matched bounded cases,
 * NOT complete Vue observation, arbitrary accessor purity or a production rule.
 */
'use strict';
function createShapeBridge(san){
 const nodes=new WeakMap(),owners=new Set(),receivers=new WeakMap(),liveReceivers=new Set();
 const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
 const scalar=v=>v===null||typeof v!=='object';
 const mutators=['push','pop','shift','unshift','splice','sort','reverse'];
 let collecting=null;
 const skipped=value=>!Object.isExtensible(value)||!!value.__v_skip||
  (!Array.isArray(value)&&Object.prototype.toString.call(value)!=='[object Object]');
 function allowed(value,seen=new Set()){
  if(scalar(value)||seen.has(value))return true;seen.add(value);
  // Ref unwrapping / foreign observer interoperability are separate open contracts.
  if(own(value,'__ob__')||value.__v_isRef===true)return false;
  if(nodes.has(value)||skipped(value))return true;
  return Object.keys(value).every(key=>{
   const d=Object.getOwnPropertyDescriptor(value,key);
   // Vue skips non-configurable slots. Do not pre-read an accessor as a guard.
   return !d.configurable||!own(d,'value')||allowed(d.value,seen);
  });
 }
 function requireValue(value){if(!allowed(value))throw new TypeError('Shape v10 experiment: unsupported Ref/foreign observer contract');}
 function children(value){
  if(scalar(value)||!nodes.has(value)||Object.isFrozen(value))return [];
  return Object.keys(value).map(k=>value[k]).filter(v=>!scalar(v));
 }
 function ancestors(root,target,result,seen=new Set()){
  if(scalar(root)||seen.has(root)||!nodes.has(root))return false;seen.add(root);
  let found=root===target;
  for(const child of children(root))if(ancestors(child,target,result,seen))found=true;
  if(found)result.add(root);return found;
 }
 function dependArray(array,seen=new Set()){
  if(seen.has(array))return;seen.add(array);
  for(const value of array){const meta=!scalar(value)&&nodes.get(value);if(meta)collecting.add(meta.dep);
   if(Array.isArray(value))dependArray(value,seen);}
 }
 function traverse(value,seen=new Set()){
  if(scalar(value)||value.__v_skip||Object.isFrozen(value)||seen.has(value))return;seen.add(value);
  if(Array.isArray(value)){for(let i=value.length-1;i>=0;i--)traverse(value[i],seen);}
  else for(const key of Object.keys(value).reverse())traverse(value[key],seen);
 }
 function refresh(owner,row){
  const previous=collecting,next=new Set();collecting=next;
  try{const root=owner.instance.data.get(row.field),meta=!scalar(root)&&nodes.get(root);
   if(meta)next.add(meta.dep);traverse(root);
  }finally{collecting=previous;owner.dependencies.set(row.queue_index,next);}
 }
 function changed(node,dependency){
  const affected=new Set([node]),targets=[],bound=[];
  for(const owner of owners)for(const row of owner.rows){
   if(!owner.dependencies.get(row.queue_index)?.has(dependency))continue;
   const root=owner.instance.data.get(row.field);targets.push([owner,row,root]);
   if(!scalar(root)&&nodes.has(root))affected.add(root);
   ancestors(root,node,affected);
  }
  for(const receiver of liveReceivers){
   if(receiver.instance.lifeCycle?.disposed)continue;
   for(const key of receiver.versions.keys()){
    const value=receiver.data.get(key);
    if(targets.some(([, ,root])=>root===value)||ancestors(value,node,affected))bound.push([receiver,key,value]);
   }
  }
  for(const value of affected){const meta=!scalar(value)&&nodes.get(value);if(meta)meta.version++;}
  for(const [owner,row,root] of targets){owner.instance.data.set(row.field,root,{force:true});owner.enqueue(row.queue_index);}
  for(const [receiver,key,value] of bound)receiver.data.set(key,value,{force:true});
 }
 function observe(value){
  if(scalar(value))return;
  const existing=nodes.get(value);if(existing)return existing;
  if(skipped(value))return;
  const meta={version:0,dep:{},properties:new Map()};nodes.set(value,meta);
  if(Array.isArray(value)){
   value.forEach(observe);
   for(const name of mutators)Object.defineProperty(value,name,{configurable:true,writable:true,enumerable:false,
    value:function(...args){
     const inserted=name==='push'||name==='unshift'?args:name==='splice'?args.slice(2):[];
     for(const v of inserted)requireValue(v);
     const result=Array.prototype[name].apply(this,args);
     inserted.forEach(observe);changed(this,nodes.get(this)?.dep);return result;
    }});
  }else for(const key of Object.keys(value)){
   const descriptor=Object.getOwnPropertyDescriptor(value,key);
   if(!descriptor.configurable)continue;
   const originalGetter=descriptor.get,originalSetter=descriptor.set,dependency={};
   let current;
   // Getter-only properties are not evaluated during defineReactive initialization.
   if(!originalGetter||originalSetter)current=value[key];
   let child=observe(current);
   const getter=function(){
    const result=originalGetter?originalGetter.call(value):current;
    if(collecting){collecting.add(dependency);
     if(child){collecting.add(child.dep);if(Array.isArray(result))dependArray(result);}}
    return result;
   };
   meta.properties.set(key,{getter,dependency});
   Object.defineProperty(value,key,{enumerable:true,configurable:true,get:getter,set(next){
    const before=originalGetter?originalGetter.call(value):current;
    if(Object.is(before,next))return;
    if(originalGetter&&!originalSetter)return;
    requireValue(next);
    if(originalSetter)originalSetter.call(value,next);else current=next;
    child=observe(next);changed(value,dependency);
   }});
  }
  return meta;
 }
 function rootName(expr){const parsed=san.parseExpr(expr);
  return parsed?.paths?.length===1&&typeof parsed.paths[0].value==='string'?parsed.paths[0].value:null;}
 function receiver(instance){
  const data=instance.data;if(!data||receivers.has(data))return null;
  const original=data.set,versions=new Map();
  for(const key of Object.keys(data.get())){const value=data.get(key),meta=value&&nodes.get(value);if(meta)versions.set(key,{value,version:meta.version});}
  const wrapped=function(expr,value,option){
   const key=rootName(expr),meta=value&&nodes.get(value),before=versions.get(key);
   if(meta&&key&&data.get(expr)===value&&before?.value===value&&before.version!==meta.version)option={...option,force:true};
   const result=original.call(data,expr,value,option);
   if(key){if(meta)versions.set(key,{value,version:meta.version});else versions.delete(key);}return result;
  };
  const record={instance,data,versions};liveReceivers.add(record);data.set=wrapped;receivers.set(data,wrapped);
  return ()=>{if(data.set===wrapped)data.set=original;receivers.delete(data);liveReceivers.delete(record);versions.clear();};
 }
 function parent(instance,rows,enqueue){
  if(san.version!=='3.15.6')throw new TypeError('Shape v10 experiment: pinned San required');
  for(const row of rows){const root=instance.data.get(row.field);requireValue(root);
   if(!root||Array.isArray(root)||typeof root!=='object')throw new TypeError('Shape v10 experiment: object root required');}
  for(const row of rows)observe(instance.data.get(row.field));
  const owner={instance,rows,enqueue,dependencies:new Map()},restores=[];owners.add(owner);
  for(const row of rows)refresh(owner,row);
  const data=instance.data,original=data.set;
  const wrapped=function(expr,value,option){
   const parsed=san.parseExpr(expr),row=rows.find(r=>r.field===parsed?.paths?.[0]?.value);
   if(row&&parsed.paths.length>1&&!option&&parsed.paths.every(p=>typeof p.value==='string'||typeof p.value==='number')){
    const path=parsed.paths.map(p=>p.value),key=path.pop();let object=data.get(path.shift());for(const part of path)object=object?.[part];
    const descriptor=object&&Object.getOwnPropertyDescriptor(object,String(key)),known=object&&nodes.get(object)?.properties.get(String(key));
    if(known&&descriptor?.get===known.getter){object[key]=value;return;}
   }
   if(row&&parsed.paths.length===1){requireValue(value);observe(value);}
   const result=original.call(data,expr,value,option);
   if(row){const root=data.get(row.field);requireValue(root);observe(root);}return result;
  };
  data.set=wrapped;
  const attachReceivers=()=>{const visit=items=>{for(const child of items||[]){
   if(child.nodeType===5&&child.data){const undo=receiver(child);if(undo)restores.push(undo);}visit(child.children);}};visit(instance.children);};
  return {attachReceivers,
   refresh(index){const row=rows.find(r=>r.queue_index===index);if(row&&owners.has(owner))refresh(owner,row);},
   write(index,key,value){const object=data.get(rows[index].field);object[key]=value;},
   dispose(){owners.delete(owner);owner.dependencies.clear();for(const undo of restores)undo();restores.length=0;if(data.set===wrapped)data.set=original;}
  };
 }
 return {parent};
}
module.exports={createShapeBridge};
