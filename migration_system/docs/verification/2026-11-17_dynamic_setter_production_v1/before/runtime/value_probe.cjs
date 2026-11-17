'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {createRequire}=require('node:module'),{createHash}=require('node:crypto');
const {compile,verify}=require('./compiler.cjs');
const project=path.resolve(__dirname,'../..');
const puppeteer=createRequire(path.join(project,'browser/package.json'))('puppeteer-core');
const source='<template><section><span>{{value}}</span><input :value="value"></section></template><script>export default {data(){return {value:"start"}},methods:{setValue(key,value){this[key]=value}}}</script>';
const target='<template><section><span>{{value}}</span><input value="{{value}}"></section></template><script>module.exports={};</script>';
async function run(executable){
  const compiled=compile(source,target);assert.ok(verify(source,compiled.code,compiled.manifest));
  const browser=await puppeteer.launch({executablePath:executable,headless:true,args:['--disable-background-networking','--disable-extensions','--disable-sync']});
  const observations=[],errors=[];
  try{
    for(const kind of ['source','target']){
      const context=await browser.createBrowserContext(),page=await context.newPage();
      try{
        page.on('pageerror',e=>errors.push({kind,message:e.message}));
        await page.setRequestInterception(true);page.on('request',r=>r.abort());
        await page.setContent('<!doctype html><main id="app"></main>');
        await page.addScriptTag({path:path.join(project,kind==='source'?'frontend/node_modules/vue/dist/vue.global.js':'engine/node_modules/san/dist/san.dev.js')});
        observations.push({kind,...await page.evaluate(async({kind,source,code})=>{
          const match=text=>({script:text.match(/<script>([\s\S]*)<\/script>/)[1],template:text.match(/<template>([\s\S]*?)<\/template>/)[1]});
          let app,native,vm,R;
          if(kind==='source'){
            const parts=match(source),module={exports:{}};
            new Function('module',parts.script.replace('export default','module.exports='))(module);
            app=Vue.createApp({...module.exports,template:parts.template});vm=app.mount('#app');R=Vue;
          }else{
            const parts=match(code),module={exports:{}};
            const exported=new Function('require','module','exports',parts.script+'\nreturn {C:module.exports,R:__businessR};')(name=>{if(name!=='san')throw Error('unexpected dependency');return san;},module,module.exports);
            native=new exported.C();vm=exported.C.business(native).instance;R=exported.R;native.attach(document.getElementById('app'));
          }
          const values=[['null',null],['undefined',undefined],['false',false],['zero',0],['symbol',Symbol('value')],
            ['bigint',123n],['object',{a:1,nested:{b:2}}],['array',[1,'two',null]],['map',new Map([['a',1]])],
            ['set',new Set([1,2])],['ref',R.ref('ref-value')],['custom',{toString(){return 'custom-value'}}]];
          const rows=[];
          for(const [name,value]of values){
            vm.setValue('value',value);await vm.$nextTick();
            const input=document.querySelector('input');
            rows.push({name,text:document.querySelector('span').textContent,value:input.value,attribute:input.getAttribute('value')});
          }
          const coercions=[];
          vm.setValue('value',{toString(){coercions.push('convert');return 'effectful'}});
          const beforeTick=[...coercions];await vm.$nextTick();
          const input=document.querySelector('input');
          rows.push({name:'side_effectful_to_string',beforeTick,coercions,text:document.querySelector('span').textContent,value:input.value,attribute:input.getAttribute('value')});
          if(kind==='source')app.unmount();else native.dispose();await vm.$nextTick();
          return {rows,empty:!document.getElementById('app').textContent,runtime:{vue:typeof globalThis.Vue!=='undefined'}};
        },{kind,source,code:compiled.code})});
      }finally{await context.close();}
    }
    const cases=observations[0].rows.map((row,index)=>({name:row.name,source:row,target:observations[1].rows[index],equal:JSON.stringify(row)===JSON.stringify(observations[1].rows[index])}));
    return {contract_id:'san-business-instance-v1',status:cases.every(row=>row.equal)&&!errors.length?'finite_value_cases_match':'value_difference_observed',
      cases,errors,observations,manifest:compiled.manifest,
      fingerprints:{...compiled.manifest.runtime_fingerprints,...Object.fromEntries([__filename,path.join(project,'frontend/node_modules/vue/dist/vue.global.js')].map(file=>[path.relative(project,file).replaceAll('\\','/'),createHash('sha256').update(fs.readFileSync(file)).digest('hex')]))},
      metadata_from_actual_source:true,scope:'finite_values_not_arbitrary_side_effectful_coercion',model_calls:0,production_admission_eligible:false,browser_version:await browser.version()};
  }finally{await browser.close();}
}
if(require.main===module){const input=JSON.parse(fs.readFileSync(0,'utf8'));run(input.executable).then(report=>{
  if(input.output){const file=path.resolve(input.output);assert.ok(file.startsWith(path.join(project,'var')+path.sep));fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(report,null,2),{flag:'wx'});}
  console.log(JSON.stringify(report));
}).catch(error=>{console.error(error.stack);process.exitCode=1;});}
module.exports={run};
