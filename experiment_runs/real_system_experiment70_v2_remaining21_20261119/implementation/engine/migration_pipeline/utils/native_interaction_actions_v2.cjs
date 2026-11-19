/* v2 adds bounded native editable-input replacement; v1 stays immutable. */
'use strict';
const previous=require('./native_interaction_actions_v1.cjs');
function validateActions(actions){
  if(!Array.isArray(actions)||!actions.length||actions.length>8)throw Error('Explicit 1..8 native actions required');
  const ids=new Set();
  for(const a of actions){
    if(!a||typeof a!=='object'||Array.isArray(a)||!/^[-a-z0-9_]+$/.test(a.id)||a.id==='initial'||ids.has(a.id))throw Error('Unique bounded action id required');
    ids.add(a.id);
    if(a.op!=='replace_text'){previous.validateActions([a]);continue;}
    if(Object.keys(a).some(k=>!['id','op','selector','value'].includes(k))||!/^[a-z][a-z0-9_-]{0,40}$/.test(a.id))throw Error('No arbitrary action/eval properties');
    if(typeof a.selector!=='string'||!a.selector||a.selector.length>300)throw Error('Explicit bounded selector required');
    if(typeof a.value!=='string'||!a.value.length||a.value.length>80||/[^\x20-\x7e]/.test(a.value))throw Error('Nonempty bounded printable ASCII edit required');
  }return actions;
}
async function executeAction(action,send,evaluate,sessionId){
  validateActions([action]);
  if(action.op!=='replace_text')return previous.executeAction(action,send,evaluate,sessionId);
  const target=await evaluate(`(()=>{const nodes=document.querySelectorAll(${JSON.stringify(action.selector)});if(nodes.length!==1)throw Error('Action selector must match exactly one element');const n=nodes[0],r=n.getBoundingClientRect(),s=getComputedStyle(n);if(n.tagName!=='INPUT'||!['text','number'].includes(n.type)||n.readOnly||n.disabled||s.visibility!=='visible'||r.width<=0||r.height<=0||r.left<0||r.top<0||r.right>innerWidth||r.bottom>innerHeight)throw Error('Editable visible text/number input required');const x=r.x+r.width/2,y=r.y+r.height/2;if(!n.contains(document.elementFromPoint(x,y)))throw Error('Action target occluded');return {tag:n.tagName,type:n.type,x,y,min:n.min,max:n.max,step:n.step};})()`);
  if(target.type==='number'&&(!/^[1-9][0-9]{0,5}$/.test(action.value)||(target.min!==''&&Number(action.value)<Number(target.min))||(target.max!==''&&Number(action.value)>Number(target.max))||!['','1','any'].includes(target.step)))throw Error('Only in-range positive integer native edits supported');
  const {root}=await send('DOM.getDocument',{},sessionId);
  const {nodeId}=await send('DOM.querySelector',{nodeId:root.nodeId,selector:action.selector},sessionId);
  if(!nodeId)throw Error('Native edit focus target absent');
  await send('DOM.focus',{nodeId},sessionId);
  const key=async(type,key,code,number,modifiers)=>send('Input.dispatchKeyEvent',{type,key,code,windowsVirtualKeyCode:number,nativeVirtualKeyCode:number,modifiers},sessionId);
  await key('keyDown','Control','ControlLeft',17,2);
  await key('keyDown','a','KeyA',65,2);await key('keyUp','a','KeyA',65,2);
  await key('keyUp','Control','ControlLeft',17,0);
  await send('Input.insertText',{text:action.value},sessionId);
  await evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))).then(()=>true)');
  const actual=await evaluate(`document.querySelector(${JSON.stringify(action.selector)}).value`);
  if(actual!==action.value)throw Error('Native replacement did not produce the requested DOM value');
  return {id:action.id,op:action.op,selector:action.selector,value:action.value,target,driver:'CDP Input',syntheticDispatchEvent:false,executed:true};
}
module.exports={validateActions,executeAction};
