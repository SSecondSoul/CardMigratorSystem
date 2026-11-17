'use strict';
const {PrototypeCapabilityError}=require('./errors.cjs');
const key=Symbol.for('cardmig.san-business-instance-v1.registry');
// Attached only to the native module namespace, never to a business instance.
// Separate exported SFC bundles must share owner brands AND one reactive kernel.
function registryFor(san,kernel,hash){
  const previous=san[key];
  if(previous){
    if(previous.protocol!=='san-business-instance-v1'||
       (previous.kernel!==kernel&&(!hash||previous.reactivityHash!==hash))) {
      throw new PrototypeCapabilityError('incompatible shared business kernel');
    }
    return previous;
  }
  const registry=Object.freeze({protocol:'san-business-instance-v1',kernel,reactivityHash:hash,
    owners:new WeakMap(),records:new WeakMap(),hosts:new WeakMap(),parentEvents:new WeakMap(),emptyData:Object.freeze({})});
  Object.defineProperty(san,key,{value:registry});
  return registry;
}
module.exports={registryFor};
