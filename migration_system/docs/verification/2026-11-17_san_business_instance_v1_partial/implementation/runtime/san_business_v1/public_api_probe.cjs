'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {createRequire}=require('node:module'),{createHash}=require('node:crypto');
const {bundle}=require('./compiler.cjs');
const project=path.resolve(__dirname,'../..');
const puppeteer=createRequire(path.join(project,'browser/package.json'))('puppeteer-core');
async function run(executable){
  const browser=await puppeteer.launch({executablePath:executable,headless:true,args:['--disable-background-networking','--disable-extensions','--disable-sync']});
  const observations=[],errors=[],built=bundle();
  try{
    for(const kind of ['source','target']){
      const context=await browser.createBrowserContext(),page=await context.newPage();
      try{
        page.on('pageerror',e=>errors.push({kind,message:e.message}));
        await page.setRequestInterception(true);page.on('request',r=>r.abort());
        await page.setContent('<!doctype html><main id="app"></main>');
        await page.addScriptTag({path:path.join(project,kind==='source'?'frontend/node_modules/vue/dist/vue.global.js':'engine/node_modules/san/dist/san.dev.js')});
        if(kind==='target')await page.addScriptTag({content:built.text+"\nwindow.businessFactory=__businessRequire('./component.cjs');window.businessR=__businessR;"});
        observations.push({kind,...await page.evaluate(async ({kind,bundleText,kernelHash})=>{
          const cases=[];const host=document.getElementById('app');
          {
            const values=[],faults=[],warnings=[];
            const handlers={title:'one',modelValue:'old',modelModifiers:{trim:true,number:true},
              onReady:(...args)=>values.push(['ready',...args]),onReadyOnce:(...args)=>values.push(['once',...args]),
              'onUpdate:modelValue':(...args)=>values.push(['model',...args]),onOops:()=>{throw new RangeError('listener');}};
            const options={props:['title','modelValue','modelModifiers'],emits:['ready','update:modelValue','oops'],
              data(){return {count:0}},methods:{setValue(k,v){this[k]=v}}};
            let app,native,vm;
            if(kind==='source'){
              app=Vue.createApp({...options,render(){return Vue.h('span',this.count)}},handlers);
              app.config.warnHandler=m=>warnings.push(m);app.config.errorHandler=(e,p,phase)=>faults.push([e.name,e.message,phase]);vm=app.mount(host);
            }else{
              const C=businessFactory.defineBusinessComponent(san,businessR,options,'<span>{{count}}</span>',{
                reactivityHash:kernelHash,
                warn:m=>warnings.push(m),onError:(e,p,phase)=>faults.push([e.name,e.message,phase===6?'component event handler':phase])});
              native=new C({data:handlers});vm=C.business(native).instance;native.attach(host);
            }
            const emit=vm.$emit;const returns=[emit('ready',1,{n:2}),emit('ready',3),emit('update:modelValue',' 12.5 '),emit('oops')].map(v=>v===undefined);
            const stableEmit=emit===vm.$emit;
            if(kind==='source')app.unmount();else native.dispose();await vm.$nextTick();emit('ready',99);
            cases.push({name:'events-multiple-args-once-model-modifiers-error-and-unmount',value:{values,faults,warnings,returns,stableEmit}});
          }
          {
            const seen=[],members={};let app,native,parent,child;
            const childOptions={props:['title','item'],data(){return {count:0}},computed:{label(){return this.title+':'+this.count+':'+this.item.n}},
              watch:{title:{handler(v,o){seen.push({value:v,old:o,dom:host.textContent})}}},
              mounted(){members.child=this;},beforeUpdate(){seen.push({hook:'beforeUpdate',dom:host.textContent})},
              updated(){seen.push({hook:'updated',dom:host.textContent})}};
            if(kind==='source'){
              const Child={...childOptions,render(){return Vue.h('span',this.label)}};
              app=Vue.createApp({data(){return {title:'old',item:{n:1}}},render(){return Vue.h('section',[Vue.h(Child,{title:this.title,item:this.item})])}});parent=app.mount(host);child=members.child;
            }else{
              const second=new Function(bundleText+"\nreturn {factory:__businessRequire('./component.cjs'),R:__businessR};")();
              const Child=second.factory.defineBusinessComponent(san,second.R,childOptions,'<span>{{label}}</span>',{reactivityHash:kernelHash});
              const Parent=businessFactory.defineBusinessComponent(san,businessR,{data(){return {title:'old',item:{n:1}}}},
                '<section><child-box title="{{title}}" item="{{item}}"/></section>',{components:{'child-box':Child},reactivityHash:kernelHash});
              native=new Parent();parent=Parent.business(native).instance;native.attach(host);child=members.child;
            }
            await parent.$nextTick();parent.title='new';await parent.$nextTick();
            parent.item.n=2;await parent.$nextTick();
            const value={dom:host.textContent,title:child.title,label:child.label,seen:[...seen],
              parentSame:child.$parent===parent,rootSame:child.$root===parent,itemSame:child.item===parent.item};
            if(kind==='source')app.unmount();else native.dispose();await parent.$nextTick();
            cases.push({name:'real-parent-prop-computed-watch-and-hook-dom-order',value});
          }
          {
            const calls=[];let app,native,vm;
            const options={data(){return {count:0}},methods:{setValue(k,v){this[k]=v}}};
            if(kind==='source'){
              app=Vue.createApp({...options,render(){return Vue.h('span',this.count)}});vm=app.mount(host);app.unmount();
            }else{
              const C=businessFactory.defineBusinessComponent(san,businessR,options,'<span>{{count}}</span>',{reactivityHash:kernelHash});
              native=new C();vm=C.business(native).instance;native.attach(host);native.dispose();
            }
            let registrationError=null,stop;
            try{stop=vm.$watch('count',(v,o)=>calls.push([v,o]));}catch(error){registrationError=error.name;}
            vm.setValue('count',2);await vm.$nextTick();stop?.();vm.setValue('count',3);await vm.$nextTick();
            cases.push({name:'public-watch-after-unmount-is-inactive-and-stoppable',value:{registrationError,calls,count:vm.count,empty:host.textContent===''}});
          }
          {
            const calls=[],dataRecords=[];let app,native,vm;
            const options={props:{base:{default:'base'},derived:{default(props){calls.push(Object.keys(props).sort());return props.base+':derived'}},enabled:Boolean},
              beforeCreate(){dataRecords.push(this.$data)},mounted(){dataRecords.push(this.$data)}};
            if(kind==='source'){
              app=Vue.createApp({...options,render(){return Vue.h('span',this.derived+':'+this.enabled)}});vm=app.mount(host);
            }else{
              const C=businessFactory.defineBusinessComponent(san,businessR,options,'<span>{{derived}}:{{enabled}}</span>',{reactivityHash:kernelHash});
              native=new C();vm=C.business(native).instance;native.attach(host);
            }
            await vm.$nextTick();
            const value={calls,base:vm.base,derived:vm.derived,enabled:vm.enabled,dom:host.textContent,
              sameEmptyData:dataRecords[0]===dataRecords[1],frozen:dataRecords.map(Object.isFrozen)};
            if(kind==='source')app.unmount();else native.dispose();await vm.$nextTick();
            cases.push({name:'prop-default-factory-resolved-input-and-frozen-empty-data',value});
          }
          {
            let app,native,vm;const callback=()=>{};
            const raw={'display-name':'hyphenated','data-note':'kept',onSaveItem:callback,onSaveItemOnce:callback,
              onClick:callback,onlower:callback,onAsProp:callback,key:'root-identity'};
            const options={inheritAttrs:false,props:['displayName','onAsProp'],emits:['save-item']};
            if(kind==='source'){
              app=Vue.createApp({...options,render(){return Vue.h('span','attrs')}},raw);vm=app.mount(host);
            }else{
              const C=businessFactory.defineBusinessComponent(san,businessR,options,'<span>attrs</span>',{reactivityHash:kernelHash});
              native=new C({data:raw});vm=C.business(native).instance;native.attach(host);
            }
            await vm.$nextTick();
            const value={name:vm.displayName??null,propIsCallback:vm.onAsProp===callback,attrs:Object.keys(vm.$attrs).sort(),
              note:vm.$attrs['data-note'],clickIsCallback:vm.$attrs.onClick===callback,lowerIsCallback:vm.$attrs.onlower===callback};
            if(kind==='source')app.unmount();else native.dispose();await vm.$nextTick();
            cases.push({name:'hyphenated-props-emits-filter-and-undeclared-listener-attrs',value});
          }
          return {cases,runtime:{vue:typeof globalThis.Vue!=='undefined'}};
        },{kind,bundleText:built.text,kernelHash:built.fingerprints['frontend/node_modules/@vue/reactivity/dist/reactivity.global.js']})});
      }finally{await context.close();}
    }
    const cases=observations[0].cases.map((row,i)=>({name:row.name,source:row.value,target:observations[1].cases[i].value,
      equal:JSON.stringify(row.value)===JSON.stringify(observations[1].cases[i].value)}));
    return {contract_id:'san-business-instance-v1',status:cases.every(row=>row.equal)?'finite_public_api_cases_match':'public_api_difference_observed',cases,observations,errors,
      fingerprints:{...built.fingerprints,...Object.fromEntries([__filename,path.join(project,'frontend/node_modules/vue/dist/vue.global.js')].map(file=>[path.relative(project,file).replaceAll('\\','/'),createHash('sha256').update(fs.readFileSync(file)).digest('hex')]))},
      compiled_source_proof:false,fixture_scope:'public_api_and_real_native_parent_child_connection',model_calls:0,production_admission_eligible:false};
  }finally{await browser.close();}
}
if(require.main===module){const input=JSON.parse(fs.readFileSync(0,'utf8'));run(input.executable).then(r=>{
  if(input.output){const file=path.resolve(input.output);assert.ok(file.startsWith(path.join(project,'var')+path.sep));fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(r,null,2),{flag:'wx'});}
  console.log(JSON.stringify(r));
}).catch(e=>{console.error(e.stack);process.exitCode=1;});}
module.exports={run};
