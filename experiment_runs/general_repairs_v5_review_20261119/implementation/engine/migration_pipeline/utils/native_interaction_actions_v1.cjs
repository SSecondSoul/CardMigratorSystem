/* Bounded real-browser input controls; no eval/code payload or synthetic DOM event. */
'use strict';
const KEYS={Home:36,End:35};
function validateActions(actions){
  if(!Array.isArray(actions)||!actions.length||actions.length>8)throw Error('Explicit 1..8 native actions required');
  const ids=new Set();
  for(const a of actions){
    if(!a||typeof a!=='object'||Array.isArray(a)||Object.keys(a).some(k=>!['id','op','selector','key'].includes(k)))throw Error('No arbitrary action/eval properties');
    if(!/^[a-z][a-z0-9_-]{0,40}$/.test(a.id)||a.id==='initial'||ids.has(a.id))throw Error('Unique non-reserved bounded action id required');ids.add(a.id);
    if(typeof a.selector!=='string'||!a.selector||a.selector.length>300)throw Error('Explicit bounded selector required');
    if(a.op==='key'){if(!Object.hasOwn(KEYS,a.key))throw Error('Only Home/End range keys supported');}
    else if(a.op!=='click'||a.key!==undefined)throw Error('Only click or range key actions supported');
  }
  return actions;
}
async function executeAction(action,send,evaluate,sessionId){
  validateActions([action]);
  const target=await evaluate(`(()=>{const nodes=document.querySelectorAll(${JSON.stringify(action.selector)});if(nodes.length!==1)throw Error('Action selector must match exactly one element');const n=nodes[0],r=n.getBoundingClientRect(),s=getComputedStyle(n);if(n.disabled||s.visibility!=='visible'||r.width<=0||r.height<=0||r.left<0||r.top<0||r.right>innerWidth||r.bottom>innerHeight)throw Error('Native action target unavailable; no auto scroll');const x=r.x+r.width/2,y=r.y+r.height/2,top=document.elementFromPoint(x,y);if(!top||!n.contains(top))throw Error('Action target occluded');return {tag:n.tagName,type:n.type||null,x,y};})()`);
  if(action.op==='key'){
    if(target.tag!=='INPUT'||target.type!=='range')throw Error('Range keyboard target required');
    const {root}=await send('DOM.getDocument',{},sessionId);
    const {nodeId}=await send('DOM.querySelector',{nodeId:root.nodeId,selector:action.selector},sessionId);
    if(!nodeId)throw Error('Native focus target absent');
    await send('DOM.focus',{nodeId},sessionId);
    for(const type of ['keyDown','keyUp'])await send('Input.dispatchKeyEvent',{type,key:action.key,code:action.key,windowsVirtualKeyCode:KEYS[action.key],nativeVirtualKeyCode:KEYS[action.key]},sessionId);
  }else{
    if(target.tag!=='BUTTON')throw Error('Only visible button click supported');
    await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:target.x,y:target.y},sessionId);
    for(const type of ['mousePressed','mouseReleased'])await send('Input.dispatchMouseEvent',{type,x:target.x,y:target.y,button:'left',clickCount:1},sessionId);
  }
  await evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))).then(()=>true)');
  return {id:action.id,op:action.op,selector:action.selector,key:action.key||null,target,driver:'CDP Input',syntheticDispatchEvent:false,executed:true};
}
module.exports={validateActions,executeAction,KEYS};
