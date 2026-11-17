'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{createRequire}=require('node:module'),{createHash}=require('node:crypto');
const {compile,verify}=require('./compiler.cjs');
const project=path.resolve(__dirname,'../..'),puppeteer=createRequire(path.join(project,'browser/package.json'))('puppeteer-core');
const source=`<template><section><child-box ref="child" :title="title" :data-note="note" @ready="handlerList" @tick.once="recordOnce"/><output>{{history}}</output><button class="rename" @click="rename">rename</button></section></template>
<script>globalThis.treeTrace=[];
const Child={inheritAttrs:false,props:['title'],emits:['ready','tick'],data(){return {count:0}},computed:{description(){return this.title+':'+this.$attrs['data-note']}},
 template:'<article><strong>{{description}}:{{count}}</strong><button class="send" @click="send">send</button><button class="fail" @click="fail">fail</button></article>',
 methods:{send(){this.count++;this.$emit('ready',this.count,{value:this.title});this.$emit('tick',this.count)},fail(){throw new RangeError('child failure')}},
 watch:{title(v,o){treeTrace.push(['title',v,o])}},mounted(){treeTrace.push(['child-mounted',this.title])}};
export default {components:{ChildBox:Child},data(){return {title:'old',note:'first',log:[],handlerList:[]}},computed:{history(){return this.log.join('|')}},
 created(){this.handlerList=[this.accept,function(value,object){'use strict';treeTrace.push(['array',value,object.value,this===undefined])}]},
 methods:{setValue(key,value){this[key]=value},accept(value,object){this.log.push(value+':'+object.value)},recordOnce(value){this.log.push('once:'+value)},rename(){this.title='new';this.note='second'}},
 errorCaptured(error,child,phase){treeTrace.push(['capture',error.name,error.message,child.title,phase]);this.log.push('captured');return false},
 mounted(){treeTrace.push(['root-mounted',this.$refs.child.title,this.$refs.child.$parent===this])}}
</script>`;
const target='<template><section><child-box s-ref="child" title="{{title}}"/><output>{{history}}</output><button class="rename" on-click="rename">rename</button></section></template><script>module.exports={};</script>';
async function run(executable){
  const built=compile(source,target);assert.ok(verify(source,built.code,built.manifest));
  const browser=await puppeteer.launch({executablePath:executable,headless:true,args:['--disable-background-networking','--disable-extensions','--disable-sync']});
  const observations=[],errors=[];
  try{
    for(const kind of ['source','target']){
      const context=await browser.createBrowserContext(),page=await context.newPage();
      try{
        page.on('pageerror',error=>errors.push({kind,message:error.message}));
        await page.setRequestInterception(true);page.on('request',request=>request.abort());
        await page.setContent('<!doctype html><main id="app"></main>');
        await page.addScriptTag({path:path.join(project,kind==='source'?'frontend/node_modules/vue/dist/vue.global.js':'engine/node_modules/san/dist/san.dev.js')});
        observations.push({kind,...await page.evaluate(async({kind,source,code})=>{
          const blocks=text=>({script:text.match(/<script>([\s\S]*)<\/script>/)[1],template:text.match(/<template>([\s\S]*?)<\/template>/)[1]});
          let app,native,vm;
          if(kind==='source'){
            const parts=blocks(source),module={exports:{}};new Function('module',parts.script.replace('export default','module.exports='))(module);
            app=Vue.createApp({...module.exports,template:parts.template});vm=app.mount('#app');
          }else{
            const parts=blocks(code),module={exports:{}};new Function('require','module','exports',parts.script)(()=>san,module,module.exports);
            native=new module.exports();vm=module.exports.business(native).instance;native.attach(document.getElementById('app'));
          }
          await vm.$nextTick();const snapshots=[document.getElementById('app').textContent];
          for(const selector of ['.send','.send','.rename','.send','.fail','.rename']){
            if(selector==='.rename'&&vm.title==='old')vm.setValue('rename',function(){'use strict';treeTrace.push(['replacement',this===undefined]);vm.title='replacement';});
            document.querySelector(selector).click();await vm.$nextTick();snapshots.push(document.getElementById('app').textContent);
          }
          vm.setValue('handlerList',[function(value,object){'use strict';treeTrace.push(['new-handler',value,object.value,this===undefined])}]);
          await vm.$nextTick();document.querySelector('.send').click();await vm.$nextTick();snapshots.push(document.getElementById('app').textContent);
          const result={snapshots,trace:globalThis.treeTrace,log:[...vm.log],attrs:{...vm.$refs.child.$attrs},optionsSame:vm.$refs.child.$options===vm.$options.components.ChildBox,count:vm.$refs.child.count,parent:vm.$refs.child.$parent===vm,root:vm.$refs.child.$root===vm,
            runtime:{vue:typeof globalThis.Vue!=='undefined'}};
          if(kind==='source')app.unmount();else native.dispose();await vm.$nextTick();result.empty=!document.getElementById('app').textContent;
          return result;
        },{kind,source,code:built.code})});
      }finally{await context.close();}
    }
    const value=row=>{const {kind,runtime,...rest}=row;return rest;};
    const equal=JSON.stringify(value(observations[0]))===JSON.stringify(value(observations[1]));
    return {contract_id:'san-business-instance-v1',status:equal&&!errors.length?'compiled_source_tree_matches':'compiled_source_tree_difference',equal,errors,observations,
      manifest:built.manifest,source_component_tree_automatic:true,model_calls:0,production_admission_eligible:false,
      fingerprints:{...built.manifest.runtime_fingerprints,[path.relative(project,__filename).replaceAll('\\','/')]:createHash('sha256').update(fs.readFileSync(__filename)).digest('hex')}};
  }finally{await browser.close();}
}
if(require.main===module){const input=JSON.parse(fs.readFileSync(0,'utf8'));run(input.executable).then(report=>{
  if(input.output){const file=path.resolve(input.output);assert.ok(file.startsWith(path.join(project,'var')+path.sep));fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(report,null,2),{flag:'wx'});}
  console.log(JSON.stringify(report));
}).catch(error=>{console.error(error.stack);process.exitCode=1;});}
module.exports={run,source,target};
