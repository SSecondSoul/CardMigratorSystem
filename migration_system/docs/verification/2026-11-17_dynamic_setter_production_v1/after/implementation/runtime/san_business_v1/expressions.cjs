'use strict';
// A private native dependency makes method-body reads visible to San's change
// matcher. It is a Symbol, never an exposed business key or a finite-key list.
const signal=Symbol('private-business-template-expression');
const root=()=>({type:4,paths:[{type:1,value:signal}]});
function installExpressions(native,host){
  const entries=host.metadata.expressionHandlers||{},names=new Set(Object.keys(entries));
  if(!names.size)return;
  const seen=new WeakSet();
  const visit=node=>{
    if(!node||typeof node!=='object'||seen.has(node))return;seen.add(node);
    // San preheats ancestor/loop dependency summaries before inited. The
    // injected expression dependency must be present there as well, otherwise
    // unchanged loop collections suppress descendant method-body updates.
    if(node.tagName||node.textExpr){node._d=node._d||{};node._d[signal]=1;}
    if(node.type===6&&names.has(node.name?.paths?.map(part=>part.value).join('.')))node.args[0]=root();
    for(const child of Object.values(node))if(Array.isArray(child))child.forEach(visit);else visit(child);
  };
  visit(native.aNode);
  host.expressionEpoch=0;host.expressionReads=new Map();
  host.handle.addRenderPrelude(()=>{
    host.expressionEpoch++;
    // Pinned San 3.15.6 consumes this batch synchronously; don't fire another
    // queued update from a render prelude (which would cause an update loop).
    if(native._dataChanges)native._dataChanges.push({type:1,expr:root(),option:{force:true}});
  });
}
function evaluateExpression(host,name,values){
  const entry=host.metadata.expressionHandlers[name],locals=values.slice(1);
  let records=host.expressionReads.get(name);if(!records){records=[];host.expressionReads.set(name,records);}
  let record=records.find(item=>item.values.length===locals.length&&item.values.every((v,i)=>Object.is(v,locals[i])));
  if(!record){
    record={values:locals,epoch:0};
    record.read=host.handle.trackRenderRead(()=>entry.invoke(host.handle.instance,
      Object.fromEntries(entry.locals.map((key,index)=>[key,record.values[index]])),[]));
    records.push(record);
  }
  record.epoch=host.expressionEpoch;
  return record.read.run();
}
function finishExpressions(host){
  for(const [name,records]of host.expressionReads||[]){
    const active=records.filter(record=>{if(record.epoch===host.expressionEpoch)return true;record.read.stop();return false;});
    if(active.length)host.expressionReads.set(name,active);else host.expressionReads.delete(name);
  }
}
module.exports={installExpressions,evaluateExpression,finishExpressions};
