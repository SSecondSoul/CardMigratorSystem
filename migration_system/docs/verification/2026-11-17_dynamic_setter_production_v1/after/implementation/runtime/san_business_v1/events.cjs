'use strict';
const {PrototypeCapabilityError}=require('./errors.cjs');
const phaseName=phase=>({2:'watcher getter',3:'watcher callback',4:'watcher cleanup function',5:'native event handler',6:'component event handler',14:'scheduler flush',15:'component update'})[phase]||phase;
function routeError(registry,native,error,receiver,phase,fallback){
  for(let ancestor=native.owner;ancestor;ancestor=ancestor.owner){
    const host=registry.hosts.get(ancestor);
    if(!host)throw new PrototypeCapabilityError('error capture through unregistered owner');
    for(const capture of [].concat(host.options.errorCaptured||[])){
      try {if(capture.call(host.handle.instance,error,receiver,phaseName(phase))===false)return;}
      catch(captureError){routeError(registry,ancestor,captureError,host.handle.instance,'errorCaptured hook',host.onError);}
    }
  }
  if(fallback)return fallback(error,receiver,phaseName(phase));
  throw error;
}
function bindParentEvents(registry,native,raw,san){
  const parent=registry.hosts.get(native.owner);
  const states=[];
  for(const binding of native.source?.events||[]){
    const name=binding.expr?.name?.paths?.map(part=>part.value).join('.');
    const entry=parent?.metadata.eventHandlers?.[name];
    if(!entry||binding.modifier.native)throw new PrototypeCapabilityError('uncompiled parent event bridge');
    const suffix=entry.once?'Once':'';
    const key='on'+binding.name[0].toUpperCase()+binding.name.slice(1)+suffix;
    const state={parent,entry,name,locals:null,callback:null,raw,key,base:raw[key]};states.push(state);
    state.listener=(...args)=>entry.invoke(parent.handle.instance,state.locals,args);
  }
  registry.parentEvents.set(native,states);refreshParentEvents(registry,native,san);
  return raw;
}
function refreshParentEvents(registry,native,san){
  for(const state of registry.parentEvents.get(native)||[]){
    state.locals=Object.fromEntries(state.entry.locals.map(key=>[key,san.evalExpr(san.parseExpr(key),native.scope,native.owner)]));
    state.callback=state.entry.resolve?(state.parent.renderSnapshots.has(state.name)?state.parent.renderSnapshots.get(state.name).handler:state.entry.resolve(state.parent.handle.instance,state.locals,[])):null;
    const listener=state.entry.resolve?state.callback:state.listener;
    state.raw[state.key]=state.base?[].concat(state.base,listener):listener;
  }
}
function captureDOMEvents(registry,native,san){
  const host=registry.hosts.get(native);
  const retained=new Set();
  const visit=node=>{
    if(!node||node!==native&&registry.hosts.has(node))return;
    const snapshots=new Map();
    for(const binding of node.aNode?.events||[]){
      const name=binding.expr?.name?.paths?.map(part=>part.value).join('.');
      const entry=host.metadata.eventHandlers?.[name];
      if(entry){
        if(entry.resolve&&!entry.locals.length)snapshots.set(name,host.renderSnapshots.get(name));
        else{
          let record=host.eventSnapshots.get(node.el)?.get(name)?.record;
          if(!record){record={read:host.handle.trackRenderRead(()=>{
            const locals=Object.fromEntries(entry.locals.map(key=>[key,san.evalExpr(san.parseExpr(key),node.scope||native.data,native)]));
            return {locals,handler:entry.resolve?.(host.handle.instance,locals,[])};
          })};}
          retained.add(record);snapshots.set(name,{...record.read.run(),record});
        }
      }else if(host.options.methods&&Object.prototype.hasOwnProperty.call(host.options.methods,name))host.methodSnapshots.set(name,host.handle.instance[name]);
    }
    if(node.el&&snapshots.size)host.eventSnapshots.set(node.el,snapshots);
    if(node._rootNode)visit(node._rootNode);
    for(const child of node.children||[])visit(child);
  };
  visit(native);
  for(const record of host.activeEventReads)if(!retained.has(record))record.read.stop();
  host.activeEventReads=retained;
}
module.exports={routeError,bindParentEvents,refreshParentEvents,phaseName,captureDOMEvents};
