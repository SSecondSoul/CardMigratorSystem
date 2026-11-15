/* Real pinned San, serialized factory, application-instance-only delegation checks. */
'use strict';
const fs=require('fs'),vm=require('vm');
function audit(input){
 const context=vm.createContext({console,Promise,process:{env:{NODE_ENV:'development'}}});
 context.module={exports:{}};context.exports=context.module.exports;
 vm.runInContext(input.sanRuntime,context);const san=context.module.exports;
 if(san.version!=='3.15.6')throw Error('Pinned San required');
 const {createShapeBridge}=require('./probe_source_path_assignment_v11.cjs');
 // Recreate the exact serialization boundary used by the emitter, rather than
 // inheriting the Node module's strict directive in a direct factory call.
 context.san=san;
 const bridge=vm.runInContext('('+createShapeBridge.toString()+')(san)',context);
 const Parent=san.defineComponent({template:'<main></main>',initData(){return {settings:{extra:{name:'initial'}},selector:'name',other:{value:1}};}});
 const prototypeBefore=Object.getPrototypeOf(new Parent().data).set,results=[];
 for(const label of ['force','silent','null-option','empty-option','dynamic-path','unrelated-root','root-replace']){
  const p=new Parent(),native=p.data.set,calls=[];let queued=0;
  const option=label==='force'?{force:true}:label==='silent'?{silent:true}:label==='null-option'?null:label==='empty-option'?{}:undefined;
  const expr=label==='dynamic-path'?'settings.extra[selector]':label==='unrelated-root'?'other.value':label==='root-replace'?'settings':'settings.extra.name';
  const value=label==='root-replace'?{extra:{name:'new-root'}}:'changed';
  const spy=function(...args){calls.push({expr:args[0],optionSame:args[2]===option});return native.apply(this,args);};
  p.data.set=spy;const contract=bridge.parent(p,[{field:'settings',queue_index:0}],()=>queued++);
  p.data.set(expr,value,option);
  const finalRead=p.data.get(expr),rootIdentity=label==='root-replace'?p.data.get('settings')===value:null;
  contract.dispose();const restored=p.data.set===spy;
  results.push({label,calls,finalValue:typeof finalRead==='object'?'object':finalRead,rootIdentity,restored,queued});
  p.data.set=native;p.dispose(true,true);
 }
 const p=new Parent(),native=p.data.set,root=p.data.get('settings');
 const contract=bridge.parent(p,[{field:'settings',queue_index:0}],()=>{});
 p.data.set('settings.extra.newRaw',1);const whileMapped=p.data.get('settings')===root;
 contract.dispose();p.data.set('settings.extra.afterDispose',2);
 const nativeCloneRestored=p.data.get('settings')!==root,prototypeUnchanged=Object.getPrototypeOf(p.data).set===prototypeBefore;
 p.dispose(true,true);
 return {production_eligible:false,results,whileMapped,nativeCloneRestored,prototypeUnchanged};
}
if(require.main===module){try{process.stdout.write(JSON.stringify(audit(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(e){process.stderr.write(e.stack);process.exitCode=1;}}
module.exports={audit};
