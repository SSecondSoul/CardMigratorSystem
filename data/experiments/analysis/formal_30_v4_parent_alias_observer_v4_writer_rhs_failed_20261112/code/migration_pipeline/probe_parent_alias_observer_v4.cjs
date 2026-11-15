/* ISOLATED experiment. No framework prototype patch, clone, Proxy or dependency.
 * Observe only previously validated plain-data existing properties/dense arrays.
 * Receiver wrappers are PER INSTANCE and preserve native San prop binding.
 * Reflection, arbitrary inputs, exceptional routing and external data APIs are
 * NOT a full Vue observer implementation or a production compatibility claim.
 */
'use strict';
function createAliasBridge(san){
 const nodes=new WeakMap(),owners=new Set(),receivers=new WeakMap(),liveReceivers=new Set();
 const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
 const scalar=v=>v===null||['undefined','boolean','number','string'].includes(typeof v);
 const mutators=['push','pop','shift','unshift','splice','sort','reverse'];
 const children=o=>Array.isArray(o)?o.filter(v=>!scalar(v)):
   [...nodes.get(o).values.values()].filter(v=>!scalar(v));
 function allowed(value,parents=[]){
  if(scalar(value))return true;
  if(typeof value!=='object'||parents.includes(value))return false;
  const meta=nodes.get(value);
  if(meta)return children(value).every(v=>allowed(v,parents.concat([value])));
  const array=Array.isArray(value),names=Object.getOwnPropertyNames(value);
  if(Object.getPrototypeOf(value)!==(array?Array.prototype:Object.prototype)
    ||Object.getOwnPropertySymbols(value).length||own(value,'__ob__')||own(value,'__v_isRef')
    ||!Object.isExtensible(value)||(array&&names.length!==value.length+1))return false;
  return names.every(k=>{
   if(array&&k==='length')return true;
   if(array&&(!/^(0|[1-9][0-9]*)$/.test(k)||+k>=value.length))return false;
   const d=Object.getOwnPropertyDescriptor(value,k);
   return d.enumerable&&d.configurable&&d.writable&&own(d,'value')&&allowed(d.value,parents.concat([value]));
  });
 }
 function requireValue(v,parents=[]){if(!allowed(v,parents))throw new TypeError('Alias v4 probe: unsupported observed value');}
 function ancestors(root,target,result,seen=new Set()){
  if(scalar(root)||seen.has(root)||!nodes.has(root))return false;
  seen.add(root);let found=root===target;
  for(const child of children(root))if(ancestors(child,target,result,new Set(seen)))found=true;
  if(found)result.add(root);return found;
 }
 function changed(node){
  const affected=new Set([node]),targets=[],bound=[];
  for(const owner of owners){
   for(const row of owner.rows){
    const root=owner.instance.data.get(row.field);
    if(ancestors(root,node,affected))targets.push([owner,row,root]);
   }
  }
  // Source lazy child computed values are observable BEFORE the render tick.
  // Invalidate already-bound shared values synchronously; do not forward a new
  // prop or call a private renderer. The native binding still owns replacement.
  for(const receiver of liveReceivers){
   if(receiver.instance.lifeCycle?.disposed)continue;
   for(const key of receiver.versions.keys()){
    const value=receiver.data.get(key);
    if(ancestors(value,node,affected))bound.push([receiver,key,value]);
   }
  }
  for(const value of affected)nodes.get(value).version++;
  for(const [owner,row,root] of targets){
   owner.instance.data.set(row.field,root,{force:true});
   owner.enqueue(row.queue_index);
  }
  for(const [receiver,key,value] of bound)receiver.data.set(key,value,{force:true});
 }
 function observe(value){
  if(scalar(value)||nodes.has(value))return;
  const meta={version:0,values:new Map()};nodes.set(value,meta);
  if(Array.isArray(value)){
   value.forEach(observe);
   for(const name of mutators)Object.defineProperty(value,name,{configurable:true,writable:true,enumerable:false,
    value:function(...args){
     const inserted=name==='push'||name==='unshift'?args:name==='splice'?args.slice(2):[];
     for(const v of inserted)requireValue(v,[this]);
     const result=Array.prototype[name].apply(this,args);
     inserted.forEach(observe);changed(this);return result;
    }});
  }else for(const key of Object.keys(value)){
   let current=value[key];meta.values.set(key,current);observe(current);
   Object.defineProperty(value,key,{enumerable:true,configurable:true,
    get(){return current;},set(next){
     if(Object.is(current,next))return;
     requireValue(next,[value]);observe(next);current=next;meta.values.set(key,next);changed(value);
    }});
  }
 }
 function rootName(expr){
  const parsed=san.parseExpr(expr);
  return parsed?.paths?.length===1&&typeof parsed.paths[0].value==='string'?parsed.paths[0].value:null;
 }
 function receiver(instance){
  const data=instance.data;
  if(!data||receivers.has(data))return null;
  const original=data.set,versions=new Map();
  for(const key of Object.keys(data.get())){
   const v=data.get(key),m=v&&nodes.get(v);if(m)versions.set(key,{value:v,version:m.version});
  }
  const wrapped=function(expr,value,option){
   const key=rootName(expr),meta=value&&nodes.get(value),before=versions.get(key);
   if(meta&&key&&data.get(expr)===value&&before?.value===value&&before.version!==meta.version)
    option={...option,force:true};
   const result=original.call(data,expr,value,option);
   if(key){if(meta)versions.set(key,{value,version:meta.version});else versions.delete(key);}
   return result;
  };
  const record={instance,data,versions};liveReceivers.add(record);
  data.set=wrapped;receivers.set(data,wrapped);
  return ()=>{if(data.set===wrapped)data.set=original;receivers.delete(data);liveReceivers.delete(record);versions.clear();};
 }
 function parent(instance,rows,enqueue){
  if(san.version!=='3.15.6')throw new TypeError('Alias v4 probe: pinned San 3.15.6 required');
  // Validate the entire initial group BEFORE changing descriptors.
  for(const row of rows){const root=instance.data.get(row.field);requireValue(root);
   if(!root||Array.isArray(root)||typeof root!=='object')throw new TypeError('Alias v4 probe: object root required');}
  for(const row of rows)observe(instance.data.get(row.field));
  const owner={instance,rows,enqueue},restores=[];owners.add(owner);
  const data=instance.data,original=data.set;
  const wrapped=function(expr,value,option){
   const parsed=san.parseExpr(expr),row=rows.find(r=>r.field===parsed?.paths?.[0]?.value);
   if(row&&parsed.paths.length>1&&!option&&parsed.paths.every(p=>typeof p.value==='string'||typeof p.value==='number')){
    const path=parsed.paths.map(p=>p.value),key=path.pop();let object=data.get(path.shift());
    for(const k of path)object=object?.[k];
    if(object&&nodes.get(object)?.values.has(String(key))){object[key]=value;return;}
   }
   if(row&&parsed.paths.length===1){requireValue(value);observe(value);}
   const result=original.call(data,expr,value,option);
   // Other native deep Data API routes still clone. Their silent/force/unknown
   // path identity policies are not claimed equivalent by this experiment.
   if(row){const root=data.get(row.field);requireValue(root);observe(root);}
   return result;
  };
  data.set=wrapped;
  const attachReceivers=()=>{
   const visit=items=>{for(const child of items||[]){if(child.nodeType===5&&child.data){const undo=receiver(child);if(undo)restores.push(undo);}
     visit(child.children);}};
   visit(instance.children);
  };
  return {attachReceivers,
   write(index,key,value){
    const row=rows[index],object=data.get(row.field);
    if(typeof key!=='string'||key==='__ob__')throw new TypeError('Alias v4 probe: unsupported key');
    if(key==='__proto__'){
     if(!scalar(value)&&(Object.getPrototypeOf(value)!==Object.prototype
       ||!Object.getOwnPropertyNames(value).every(k=>{
        const d=Object.getOwnPropertyDescriptor(value,k);return d.enumerable&&d.configurable&&d.writable&&own(d,'value')&&scalar(d.value);
       })||Object.getOwnPropertySymbols(value).length))throw new TypeError('Alias v4 probe: unsupported prototype value');
    }else requireValue(value);
    // Existing observed keys invoke their own setter. New keys deliberately do
    // not become reactive, just as raw Vue 2 object-key assignment does not.
    object[key]=value;
   },
   dispose(){owners.delete(owner);for(const undo of restores)undo();restores.length=0;
    if(data.set===wrapped)data.set=original;}
  };
 }
 return {parent};
}
module.exports={createAliasBridge};
