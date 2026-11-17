'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{createHash}=require('node:crypto');
const {registryFor}=require('./registry.cjs'),{splitInputs}=require('./component.cjs');
function run(){
  const cases=[];
  const san={},first={},second={};
  const registry=registryFor(san,first,'pinned-hash');
  assert.equal(registryFor(san,second,'pinned-hash'),registry);
  assert.equal(registryFor(san,second,'pinned-hash').kernel,first);
  cases.push({name:'separate-artifacts-share-one-branded-kernel',equal:true});
  const descriptor=Object.getOwnPropertyDescriptor(san,Symbol.for('cardmig.san-business-instance-v1.registry'));
  assert.equal(descriptor.enumerable,false);assert.equal(descriptor.writable,false);assert.equal(descriptor.configurable,false);
  assert.ok(Object.isFrozen(registry.emptyData));
  cases.push({name:'native-registry-not-enumerable-or-replaceable',equal:true});
  for(const hash of ['different',undefined])assert.throws(()=>registryFor(san,second,hash),error=>error.code==='san_business_capability_unsupported');
  cases.push({name:'incompatible-kernel-rejected-not-silently-mixed',equal:true});
  for(const name of ['ref','onVnodeMounted','onVnodeBeforeUnmount'])assert.throws(()=>splitInputs({},null,{[name]:()=>{}}),error=>error.code==='san_business_capability_unsupported');
  cases.push({name:'unimplemented-renderer-callbacks-rejected-not-dropped',equal:true});
  const project=path.resolve(__dirname,'../..');
  return {contract_id:'san-business-instance-v1',status:'finite_controls_match',cases,
    fingerprints:Object.fromEntries([__filename,...['registry.cjs','component.cjs','runtime.cjs','owner.cjs','dom.cjs','errors.cjs'].map(name=>path.join(__dirname,name))]
      .map(file=>[path.relative(project,file).replaceAll('\\','/'),createHash('sha256').update(fs.readFileSync(file)).digest('hex')])),
    browser_execution:false,model_calls:0,production_admission_eligible:false};
}
if(require.main===module)console.log(JSON.stringify(run()));
module.exports={run};
