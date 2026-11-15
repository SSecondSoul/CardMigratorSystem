/* Isolated source-context protocol, following the pinned Vue 2 error-flow order.
 * Application owns the native-parent/hook/config mapping AND diagnostic sink.
 * No San.error inference, SSR logger, tracking shim, retry or global patch.
 */
'use strict';
function createSourceErrorContext(binding){
 if(typeof window==='undefined'||!window.document)throw new TypeError('Source v6 probe: browser environment required');
 if(!binding||binding.environment!=='browser'||binding.trackingPolicy!=='no-reactive-reads-or-writes'
   ||!['parentOf','hooksOf','globalHandler','logError'].every(k=>typeof binding[k]==='function'))
  throw new TypeError('Source v6 probe: explicit browser error-context binding required');
 const globalHandle=(error,subject,info)=>{
  const handler=binding.globalHandler();
  if(handler!=null&&typeof handler!=='function')throw new TypeError('Source v6 probe: unsupported global handler');
  if(handler){
   try{return handler.call(null,error,subject,info);}
   catch(next){if(next!==error)binding.logError(next,null,'config.errorHandler');}
  }
  binding.logError(error,subject,info);
 };
 return {handle(error,subject,info){
  // No fake pause of framework dependency collection: the selected experimental
  // profile excludes stateful/reactive hook bodies, not the source public API.
  const seen=new Set();let current=subject;
  while((current=binding.parentOf(current))){
   if(seen.has(current))throw new TypeError('Source v6 probe: cyclic ancestor mapping');
   seen.add(current);const hooks=binding.hooksOf(current);
   if(!Array.isArray(hooks)||hooks.some(h=>typeof h!=='function'))throw new TypeError('Source v6 probe: unsupported capture mapping');
   for(const hook of hooks){
    try{if(hook.call(current,error,subject,info)===false)return;}
    catch(next){globalHandle(next,current,'errorCaptured hook');}
   }
  }
  globalHandle(error,subject,info);
 }};
}
module.exports={createSourceErrorContext};
