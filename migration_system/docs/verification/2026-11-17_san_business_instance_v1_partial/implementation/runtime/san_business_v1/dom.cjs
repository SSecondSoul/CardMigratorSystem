'use strict';
// Native prop handlers receive the ALREADY evaluated value. Do not re-run a
// template getter, mutate captured snapshots, or guess DOM selectors.
const patched = new WeakSet(), modes = new WeakMap();
function elements(node, result=[]) {
  if(node.tagName)result.push(node);
  for(const child of node.children||[])elements(child,result);
  for(const child of node.elses||[])elements(child,result);
  return result;
}
function installDOMPolicy(aNode, policy) {
  if(!policy?.length)return;
  const nodes=elements(aNode);
  if(nodes.length!==policy.length)throw Error('business_dom_policy_shape_mismatch');
  for(let index=0;index<nodes.length;index++){
    const node=nodes[index],expected=policy[index];
    if(node.tagName!==expected.tag)throw Error('business_dom_policy_tag_mismatch');
    for(const name of expected.attributes){
      const prop=node.props.find(prop=>prop.name===name);
      if(!prop)throw Error('business_dom_policy_property_missing:'+name);
      modes.set(prop,name);
      if(patched.has(prop))continue;patched.add(prop);
      const original=prop.handler;
      prop.handler=function(el,value,propName,element){
        const nativeValue=name==='value'&&typeof value==='symbol'?String(value):value;
        original(el,nativeValue,propName,element);
        if(name==='value'){
          if(value==null)el.removeAttribute(name);else el.setAttribute(name,nativeValue);
        }else if(name==='checked'||name==='selected'){
          const checked=!!value||value==='';el[name]=checked;
          if(checked)el.setAttribute(name,'');else el.removeAttribute(name);
        }else if(name==='class'&&!el.hasAttribute('class'))el.setAttribute('class','');
      };
    }
  }
}
function synchronizeClassPresence(runtime) {
  const seen=new Set();
  const visit=node=>{
    if(!node||seen.has(node))return;seen.add(node);
    if(node.el?.nodeType===1&&node.aNode?.props?.some(prop=>modes.get(prop)==='class')&&!node.el.hasAttribute('class'))node.el.setAttribute('class','');
    if(node._rootNode)visit(node._rootNode);
    for(const child of node.children||[])visit(child);
  };
  visit(runtime);
}
module.exports={installDOMPolicy,synchronizeClassPresence};
