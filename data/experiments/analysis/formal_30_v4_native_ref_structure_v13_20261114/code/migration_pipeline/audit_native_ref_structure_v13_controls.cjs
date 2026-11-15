/* Real San + pinned native Vue input Ref, no Vue application/watch/effect. */
'use strict';
const fs=require('fs'),vm=require('vm');
function audit(input){
 const c=vm.createContext({Promise,console,process:{env:{NODE_ENV:'development'}}});
 function load(source){c.module={exports:{}};c.exports=c.module.exports;vm.runInContext(source,c);return c.module.exports;}
 const san=load(input.sanRuntime),vue=load(input.vueRuntime);
 if(san.version!=='3.15.6'||vue.version!=='2.7.16')throw Error('Pinned runtimes required');
 const {createShapeBridge}=require('./probe_native_ref_structure_v13.cjs');c.san=san;
 const bridge=vm.runInContext('('+createShapeBridge.toString()+')(san)',c);
 const value=vue.ref([{name:'initial'}]),targetBefore=value.dep.constructor.target;
 const array=value.value,observer=array.__ob__,firstElement=array[0],slot=Object.getOwnPropertyDescriptor(firstElement,'name');
 const depDependBefore=Object.getPrototypeOf(value.dep).depend;
 const structuralActive=()=>[value.dep,array.__ob__.dep,firstElement.__ob__.dep].map(dep=>dep.subs.filter(Boolean).length);
 const Parent=san.defineComponent({template:'<main></main>',initData(){return {settings:{extra:value}};}});
 const parents=[new Parent(),new Parent()],dataPrototype=Object.getPrototypeOf(parents[0].data),setBefore=dataPrototype.set;
 const nativeSets=parents.map(p=>p.data.set),counts=[0,0];
 const contracts=parents.map((p,i)=>bridge.parent(p,[{field:'settings',queue_index:0}],()=>counts[i]++));
 const active=()=>value.dep.subs.filter(Boolean).length,subscribers=[active()];
 const structuralBefore=structuralActive();array.push({name:'next'});const first=counts.slice();contracts[0].dispose();subscribers.push(active());
 array.pop();const second=counts.slice();contracts[1].dispose();subscribers.push(active());const structuralAfter=structuralActive();
 array.push({name:'after-dispose'});const third=counts.slice();
 const restored=parents.every((p,i)=>p.data.set===nativeSets[i]);
 parents.forEach(p=>p.dispose(true,true));
 const afterSlot=Object.getOwnPropertyDescriptor(firstElement,'name');
 return {production_eligible:false,subscribers,structuralBefore,structuralAfter,first,second,third,restored,
  valueIdentityPreserved:value.value===array,observerIdentityPreserved:array.__ob__===observer,
  propertyAccessorPreserved:slot.get===afterSlot.get&&slot.set===afterSlot.set,
  depPrototypeUnchanged:Object.getPrototypeOf(value.dep).depend===depDependBefore,
  dataPrototypeUnchanged:dataPrototype.set===setBefore,globalDepTargetUnchanged:value.dep.constructor.target===targetBefore};
}
if(require.main===module){try{process.stdout.write(JSON.stringify(audit(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(e){process.stderr.write(e.stack);process.exitCode=1;}}
module.exports={audit};
