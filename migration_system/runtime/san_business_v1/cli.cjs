'use strict';
const fs=require('node:fs');
const {compile,inspectSource,verify}=require('./compiler.cjs');
try {
  const request=JSON.parse(fs.readFileSync(0,'utf8'));
  if(request.action==='inspect') {
    const result=inspectSource(request.source);
    process.stdout.write(JSON.stringify({status:'completed',contract_id:'san-business-instance-v1',method_names:result.methodNames,
      source_layout:'derived_from_source_not_user_whitelist',production_admission_eligible:false}));
  }else if(request.action==='compile'){
    process.stdout.write(JSON.stringify({status:'completed',...compile(request.source,request.code,request.mode)}));
  }else if(request.action==='verify'){
    process.stdout.write(JSON.stringify({status:verify(request.source,request.code,request.manifest)?'completed':'fail'}));
  }else throw Error('unknown_business_action');
} catch(error) {
  process.stdout.write(JSON.stringify({status:'blocked',error:error.code||'business_compile_failed',details:String(error.details||error.message).slice(0,500)}));
  process.exitCode=2;
}
