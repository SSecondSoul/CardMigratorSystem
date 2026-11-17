'use strict';
const {defineBusinessComponent}=require('./component.cjs');
const {PrototypeCapabilityError}=require('./errors.cjs');
function defineBusinessTree(san,R,options,spec,common){
  const building=new Set();
  function build(definition,node){
    if(building.has(definition))throw new PrototypeCapabilityError('recursive source component registration');
    building.add(definition);
    const components={};
    for(const [name,child]of Object.entries(node.components||{})){
      const C=build(definition.components[name],child);
      for(const alias of [name,name[0].toLowerCase()+name.slice(1),name.replace(/\B([A-Z])/g,'-$1').toLowerCase()])components[alias]=C;
    }
    const result=defineBusinessComponent(san,R,definition,node.template,{...common,...node,components,domPolicy:node.elementPolicies});
    building.delete(definition);return result;
  }
  return build(options,spec);
}
module.exports={defineBusinessTree};
