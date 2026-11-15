/* Private async-dispatch capability, not a sandbox for arbitrary hook effects. */
'use strict';
function createAsyncWatcherScope(sourceFactory,subject,fields){
 const fail=code=>{const e=new TypeError('Watcher v7 scope: '+code);e.code=code;throw e;};
 if(typeof sourceFactory!=='function'||!subject||!Array.isArray(fields)||!fields.length
   ||fields.some(f=>typeof f!=='string'||!f)||new Set(fields).size!==fields.length)fail('INVALID_SCOPE');
 const names=fields.slice();let context=null,locked=false,disposed=false,pending=false,active=false;
 return Object.freeze({
  configure(binding){
   if(disposed)fail('DISPOSED');if(locked)fail('CONFIGURATION_LOCKED');
   if(typeof window==='undefined'||window===null||!window.document)fail('BROWSER_REQUIRED');
   if(!binding||binding.channel!=='async-parent-watch'
     ||binding.environment!=='browser'||binding.trackingPolicy!=='no-reactive-reads-or-writes')fail('UNSUPPORTED_PROFILE');
   // Copy capability references: caller cannot replace the binding slots later.
   // Their implementations remain trusted application code, not purity-proven.
   const snapshot={environment:binding.environment,trackingPolicy:binding.trackingPolicy};
   for(const key of ['parentOf','hooksOf','globalHandler','logError']){
    const fn=binding[key];if(typeof fn!=='function')fail('MISSING_CAPABILITY');snapshot[key]=fn;
   }
   const next=sourceFactory(Object.freeze(snapshot));context=next;
  },
  schedule(flush){
   if(disposed)fail('DISPOSED');if(pending||active)fail('REENTRANT_SCHEDULE');
   if(typeof flush!=='function')fail('INVALID_FLUSH');
   locked=true;pending=true;
   return Promise.resolve().then(()=>{
    pending=false;
    // Keep the old queue's cancellation/reset path when disposed before tick.
    if(disposed)return flush();
    active=true;try{return flush();}finally{active=false;}
   });
  },
  route(error,index){
   if(disposed)fail('DISPOSED');if(!active)fail('OUTSIDE_ASYNC_DISPATCH');
   if(!Number.isInteger(index)||index<0||index>=names.length)fail('INVALID_WATCHER_INDEX');
   if(!context)return false;
   context.handle(error,subject,'callback for watcher "'+names[index]+'"');return true;
  },
  dispose(){disposed=true;context=null;}
 });
}
module.exports={createAsyncWatcherScope};
