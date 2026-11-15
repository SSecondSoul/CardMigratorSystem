/* Real San + pinned native Vue input Ref, no Vue application/watch/effect. */
'use strict';
const fs=require('fs'),vm=require('vm');
function audit(input){
 const c=vm.createContext({Promise,console,process:{env:{NODE_ENV:'development'}}});
 function load(source){c.module={exports:{}};c.exports=c.module.exports;vm.runInContext(source,c);return c.module.exports;}
 const san=load(input.sanRuntime),vue=load(input.vueRuntime);
 if(san.version!=='3.15.6'||vue.version!=='2.7.16')throw Error('Pinned runtimes required');
 const {createShapeBridge}=require('./probe_ref_contract_v12.cjs');c.san=san;
 const bridge=vm.runInContext('('+createShapeBridge.toString()+')(san)',c);
 const value=vue.ref(7),targetBefore=value.dep.constructor.target;
 const Parent=san.defineComponent({template:'<main></main>',initData(){return {settings:{extra:value}};}});
 const parents=[new Parent(),new Parent()],dataPrototype=Object.getPrototypeOf(parents[0].data),setBefore=dataPrototype.set;
 const nativeSets=parents.map(p=>p.data.set),counts=[0,0];
 const contracts=parents.map((p,i)=>bridge.parent(p,[{field:'settings',queue_index:0}],()=>counts[i]++));
 const active=()=>value.dep.subs.filter(Boolean).length,subscribers=[active()];
 value.value=8;const first=counts.slice();contracts[0].dispose();subscribers.push(active());
 value.value=9;const second=counts.slice();contracts[1].dispose();subscribers.push(active());
 value.value=10;const third=counts.slice();
 const restored=parents.every((p,i)=>p.data.set===nativeSets[i]);
 parents.forEach(p=>p.dispose(true,true));
 return {production_eligible:false,subscribers,first,second,third,restored,
  dataPrototypeUnchanged:dataPrototype.set===setBefore,globalDepTargetUnchanged:value.dep.constructor.target===targetBefore};
}
if(require.main===module){try{process.stdout.write(JSON.stringify(audit(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(e){process.stderr.write(e.stack);process.exitCode=1;}}
module.exports={audit};
