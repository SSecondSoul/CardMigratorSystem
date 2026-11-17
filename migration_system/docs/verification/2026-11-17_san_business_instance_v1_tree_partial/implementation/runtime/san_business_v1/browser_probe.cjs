'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {createRequire}=require('node:module');
const {createHash}=require('node:crypto');
const {compile,verify,inspectSource}=require('./compiler.cjs');
const project=path.resolve(__dirname,'../..');
const puppeteer=createRequire(path.join(project,'browser/package.json'))('puppeteer-core');
const source=`<template><section><button ref="counter" :class="count % 2 ? 'chosen' : ''" @click="inc">{{label}}</button><input :value="text" @input="setText"><input type="checkbox" :checked="enabled" @change="setEnabled"><p>{{extra}}</p><i>{{accessor}}</i><em v-if="enabled">{{conditional}}</em></section></template>
<script>globalThis.businessLog=[];globalThis.businessReads=[];export default {
 props:{title:{type:String,default:'one'}},
 data(){const value={count:0,text:'initial',enabled:false,box:{n:1}};
  for(const key of ['accessor','unused','conditional']){let current=0;Object.defineProperty(value,key,{enumerable:true,configurable:true,
   get(){businessReads.push(['get',key,current]);return current},set(next){businessReads.push(['set',key,next]);current=next}})}
  globalThis.businessRawData=value;return value},
 computed:{label(){return this.title+':'+this.count+':'+this.box.n}},
 methods:{setValue(key,value){this[key]=value},inc(){this.count++},setText(event){this.text=event.target.value},setEnabled(event){this.enabled=event.target.checked},record(v,o){businessLog.push(['watch',v,o])}},
 watch:{count:'record'},
 beforeCreate(){businessLog.push(['beforeCreate',typeof this.inc,Object.isFrozen(this.$data)])},
 created(){this.extra='ctx';businessLog.push(['created',this.count])},
 mounted(){businessLog.push(['mounted',this.$refs.counter.textContent,this.$refs.counter.getAttribute('class')])},
 beforeUpdate(){businessLog.push(['beforeUpdate',this.$refs.counter.getAttribute('class')])},
 updated(){businessLog.push(['updated',this.$refs.counter.getAttribute('class')])},
 beforeUnmount(){businessLog.push(['beforeUnmount',this.count])},
 unmounted(){businessLog.push(['unmounted'])}
}</script>`;
const target='<template><section><button s-ref="counter" class="{{count % 2 ? \'chosen\' : \'\'}}" on-click="inc">{{label}}</button><input value="{{text}}" on-input="setText"><input type="checkbox" checked="{{enabled}}" on-change="setEnabled"><p>{{extra}}</p><i>{{accessor}}</i><em s-if="enabled">{{conditional}}</em></section></template><script>module.exports={};</script>';
async function run(executable){
  const compiled=compile(source,target);assert.ok(verify(source,compiled.code,compiled.manifest));
  assert.ok(!verify(source,compiled.code.replace('initial','tampered'),compiled.manifest));
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
          let app,native,vm,handle;
          if(kind==='source'){
            const parts=match(source),module={exports:{}};
            new Function('module',parts.script.replace('export default','module.exports='))(module);
            app=Vue.createApp({...module.exports,template:parts.template});vm=app.mount('#app');
          }else{
            const parts=match(code),module={exports:{}};
            new Function('require','module','exports',parts.script)(name=>{if(name!=='san')throw Error('unexpected dependency');return san;},module,module.exports);
            const C=module.exports;native=new C();handle=C.business(native);vm=handle.instance;native.attach(document.getElementById('app'));
          }
          const tick=()=>vm.$nextTick(),text=()=>document.getElementById('app').textContent;
          await tick();const states=[text()],attributes=[];
          const attrs=()=>attributes.push({class:document.querySelector('button').getAttribute('class'),value:document.querySelector('input').getAttribute('value'),checked:document.querySelector('[type=checkbox]').getAttribute('checked')});
          attrs();
          document.querySelector('button').click();await tick();states.push(text());
          vm.box.n=7;await tick();states.push(text());
          const input=document.querySelector('input');input.value='typed';input.dispatchEvent(new Event('input',{bubbles:true}));await tick();
          const typed=vm.text;
          document.querySelector('[type=checkbox]').click();await tick();attrs();
          vm.setValue('accessor',5);vm.setValue('unused',4);await tick();
          vm.setValue('unused',6);await tick();
          document.querySelector('[type=checkbox]').click();await tick();
          vm.setValue('conditional',7);await tick();
          const setter=vm.setValue,keys=[];
          for(const key of ['extra.key','literal[key]','data','watch','dispose','attach','__proto__',Symbol('same'),Symbol.for('cardmig.san-business-instance-v1.registry')]){
            const value={key:String(key)};setter(key,value);keys.push(vm[key]===value);
          }
          const conversions=[];setter({[Symbol.toPrimitive](hint){conversions.push(hint);return 'coerced.key';}},9);
          document.querySelector('button').click();await tick();states.push(text());
          setter('extra','forced');await tick();const beforeForce=text();vm.$forceUpdate();vm.$forceUpdate();await tick();const afterForce=text();
          const scopeActive=kind==='target'?handle.scope.active:true;
          if(kind==='source')app.unmount();else native.dispose();await tick();
          return {states,typed,keys,conversions,coerced:vm['coerced.key'],beforeForce,afterForce,scopeActive,attributes,
            rawIdentity:vm.$data.__v_raw===globalThis.businessRawData,
            log:globalThis.businessLog,reads:globalThis.businessReads,empty:!document.getElementById('app').textContent,
            runtime:{vue:typeof globalThis.Vue!=='undefined',reactivityGlobal:typeof globalThis.VueReactivity!=='undefined'}};
        },{kind,source,code:compiled.code})});
      }finally{await context.close();}
    }
    const a={...observations[0]},b={...observations[1]};delete a.kind;delete b.kind;delete a.runtime;delete b.runtime;
    return {contract_id:'san-business-instance-v1',status:JSON.stringify(a)===JSON.stringify(b)?'finite_compiled_business_case_matches':'difference_observed',
      equal:JSON.stringify(a)===JSON.stringify(b),observations,errors,manifest:compiled.manifest,
      fingerprints:{...compiled.manifest.runtime_fingerprints,...Object.fromEntries([__filename,path.join(project,'frontend/node_modules/vue/dist/vue.global.js')].map(file=>[path.relative(project,file).replaceAll('\\','/'),createHash('sha256').update(fs.readFileSync(file)).digest('hex')]))},
      metadata_from_actual_source:true,model_calls:0,production_admission_eligible:false,browser_version:await browser.version()};
  }finally{await browser.close();}
}
if(require.main===module){const input=JSON.parse(fs.readFileSync(0,'utf8'));run(input.executable).then(r=>{
  if(input.output){const file=path.resolve(input.output);assert.ok(file.startsWith(path.join(project,'var')+path.sep));fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(r,null,2),{flag:'wx'});}
  console.log(JSON.stringify(r));
}).catch(e=>{console.error(e.stack);process.exitCode=1;});}
module.exports={run,source,target};
