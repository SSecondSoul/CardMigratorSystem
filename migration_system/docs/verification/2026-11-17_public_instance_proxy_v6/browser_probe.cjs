'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {createRequire} = require('node:module'), {createHash} = require('node:crypto');
const project = path.resolve(__dirname, '../..');
const puppeteer = createRequire(path.join(project, 'browser/package.json'))('puppeteer-core');

async function run(executable, version = 'v6') {
  assert.ok(['v5','v6'].includes(version));
  const directory = path.join(project, `research/public_instance_${version}`);
  const previous = fs.readFileSync(path.join(project,'research/public_instance_v1/runtime.cjs'),'utf8');
  const implementation = fs.readFileSync(path.join(directory,'runtime.cjs'),'utf8');
  const owner = fs.readFileSync(path.join(directory,'owner.cjs'),'utf8');
  const browser = await puppeteer.launch({executablePath: executable, headless:true,
    args:['--disable-background-networking','--disable-extensions','--disable-sync']});
  const errors = [], observations = [];
  try {
    for (const kind of ['source','target']) {
      const context = await browser.createBrowserContext(), page = await context.newPage();
      try {
        page.on('pageerror', error => errors.push({kind,message:error.message}));
        page.on('console', msg => {if(['warning','error'].includes(msg.type())) errors.push({kind,message:msg.text()});});
        await page.setRequestInterception(true); page.on('request', request=>request.abort());
        await page.setContent('<!doctype html><main id="app"></main><main id="other"></main>');
        await page.addScriptTag({path:path.join(project,kind==='source'?'frontend/node_modules/vue/dist/vue.global.js':'engine/node_modules/san/dist/san.dev.js')});
        if(kind==='target') {
          await page.addScriptTag({path:path.join(project,'frontend/node_modules/@vue/reactivity/dist/reactivity.global.js')});
          await page.addScriptTag({content:`(()=>{
            const previous=(()=>{const module={exports:{}};${previous}\nreturn module.exports;})();
            const require=name=>{if(name!=='../public_instance_v1/runtime.cjs')throw Error('Unexpected dependency');return previous;};
            window.publicPrototype=(()=>{const module={exports:{}};${implementation}\nreturn module.exports;})();
            window.ownerPrototype=(()=>{const module={exports:{}};${owner}\nreturn module.exports;})();})();`});
        }
        const result=await page.evaluate(async ({kind,version})=>{
          const cases=[];
          function mount(ids=['a','b'], destination='app') {
            const members=new Map(), log=[], watches=[], hookErrors=[];
            const dom=()=>Array.from(document.getElementById(destination).querySelectorAll('span')).map(el=>el.textContent);
            const hooks={};
            for(const name of ['beforeMount','mounted','beforeUnmount','unmounted']) hooks[name]=function(){
              log.push({name,id:this.localId,parent:this.$parent?.localId??null,root:this.$root.localId,
                parentSame:this.$parent?this.$.parent.proxy===this.$parent:true,rootSame:this.$.root.proxy===this.$root,
                mounted:this.$.isMounted,unmounted:this.$.isUnmounted,scope:this.$.scope.active,dom:dom()});
            };
            const seed={localId:'root',ids:[...ids],count:0};
            let vm,dispose;
            if(kind==='source') {
              const Child={props:['item'],data(){return {localId:this.item,count:0};},...hooks,
                created(){members.set(this.localId,this);},render(){return Vue.h('span',{'data-id':this.localId},`${this.localId}:${this.count}`);}};
              const app=Vue.createApp({data(){return seed;},...hooks,render(){return Vue.h('section',this.ids.map(id=>Vue.h(Child,{key:id,item:id})));}});
              app.config.errorHandler=(error,proxy,phase)=>hookErrors.push({message:error.message,phase});
              vm=app.mount(document.getElementById(destination)); dispose=()=>app.unmount();
            } else {
              const buildHandle=(native,data)=>publicPrototype.createPublicInstance(native,{sourceData:data,stateKeys:Object.keys(data),
                props:native.owner?{item:native.data.get('item')}: {},reactivity:VueReactivity,parseNativeExpr:san.parseExpr,evaluateNativeExpr:san.evalExpr,
                nextRender:callback=>san.nextTick(callback),onError:(error,proxy,phase)=>hookErrors.push({message:error.message,phase})});
              const Child=san.defineComponent({template:'<span data-id="{{localId}}">{{localId}}:{{count}}</span>',
                initData(){return {localId:'',count:0};},inited(){
                  const data={localId:this.data.get('item'),count:0};
                  const handle=buildHandle(this,data); members.set(data.localId,handle.instance);
                  if(version==='v6') ownerPrototype.connectComponentOwner(this,handle,hooks);
                }});
              const Root=san.defineComponent({template:'<section><child-box s-for="item in ids trackBy item" item="{{item}}"/></section>',
                components:{'child-box':Child},initData(){return seed;}});
              const native=new Root(),handle=buildHandle(native,seed);
              ownerPrototype.connectRootOwner(native,handle,hooks);
              vm=handle.instance;native.attach(document.getElementById(destination));dispose=()=>native.dispose();
            }
            let closed=false;
            return {vm,members,log,watches,hookErrors,dom,dispose(){if(!closed){closed=true;dispose();}},
              register(vm){return vm.$watch('count',(value,old,cleanup)=>{watches.push([vm.localId,value,old]);cleanup(()=>watches.push(['cleanup',vm.localId,value]));},{flush:'sync'});},
              async settle(){await vm.$nextTick();}};
          }
          {
            const f=mount(); const children=[...f.members.values()];
            const links=children.map(child=>({id:child.localId,parent:child.$parent===f.vm,root:child.$root===f.vm,scope:child.$.scope!==f.vm.$.scope}));
            f.dispose(); await f.settle();
            cases.push({name:'parent-child-native-mount-unmount-order-and-links',value:{links,log:f.log,
              inactive:children.every(child=>!child.$.scope.active),errors:f.hookErrors}});
          }
          {
            const f=mount(['a','b','c']);
            const [a,b,c]=['a','b','c'].map(id=>f.members.get(id));
            for(const child of [a,b,c]){f.register(child);child.count=1;}
            await f.settle();
            f.vm.ids=['c','b']; await f.settle();
            const removed={dom:f.dom(),aStopped:!a.$.scope.active,bActive:b.$.scope.active,cActive:c.$.scope.active,
              bSame:f.members.get('b')===b,cSame:f.members.get('c')===c};
            a.count=9;b.count=2;await f.settle();
            const afterChildWrite=f.dom();
            f.vm.ids=['c','b','a'];await f.settle();
            const fresh=f.members.get('a');
            const readded={newInstance:fresh!==a,count:fresh.count,active:fresh.$.scope.active,dom:f.dom()};
            f.dispose();await f.settle();
            cases.push({name:'keyed-reorder-remove-reinsert-keeps-independent-scopes',value:{removed,afterChildWrite,readded,watches:f.watches,
              allStopped:[a,b,c,fresh].every(child=>!child.$.scope.active),errors:f.hookErrors}});
          }
          {
            const f=mount(['x']);const child=f.members.get('x'),pending=[];
            child.$watch('count',value=>pending.push(['pre',value]));
            child.$watch('count',value=>pending.push(['post',value]),{flush:'post'});
            child.count=1;const tick=f.vm.$nextTick(()=>pending.push(['tick',f.dom()]));
            f.dispose();await tick;await f.settle();
            cases.push({name:'parent-disposal-cancels-pending-child-watchers',value:{pending,childStopped:!child.$.scope.active,
              childUnmounted:child.$.isUnmounted,parentUnmounted:f.vm.$.isUnmounted}});
          }
          {
            const a=mount(['left']),b=mount(['right'],'other');
            const left=a.members.get('left'),right=b.members.get('right');a.register(left);b.register(right);
            a.dispose();left.count=5;right.count=3;await b.settle();
            const value={leftStopped:!left.$.scope.active,rightActive:right.$.scope.active,rightParent:right.$parent===b.vm,
              rootsDifferent:left.$root!==right.$root,rightDom:b.dom(),leftWatches:a.watches,rightWatches:[...b.watches]};
            b.dispose();await b.settle();cases.push({name:'separate-root-families-do-not-stop-each-other',value});
          }
          let nativeKeyControl=null;
          if(kind==='target') {
            const members=new Map();
            const Child=san.defineComponent({template:'<span>{{item}}:{{count}}</span>',initData(){return {count:0};},
              inited(){members.set(this.data.get('item'),this);}});
            const Root=san.defineComponent({template:'<section><child-box s-for="item in ids trackBy item" item="{{item}}"/></section>',
              components:{'child-box':Child},initData(){return {ids:['a','b','c']};}});
            const native=new Root();native.attach(document.getElementById('app'));
            const b=members.get('b'),c=members.get('c'); b.data.set('count',1);c.data.set('count',1);
            await new Promise(resolve=>san.nextTick(resolve));
            native.data.set('ids',['c','b']);await new Promise(resolve=>san.nextTick(resolve));
            nativeKeyControl={bSame:members.get('b')===b,cSame:members.get('c')===c,bDisposed:!!b.lifeCycle.disposed,
              dom:Array.from(document.getElementById('app').querySelectorAll('span')).map(el=>el.textContent)};
            native.dispose();
          }
          return {cases,nativeKeyControl,runtime:{vue:typeof window.Vue!=='undefined',kernel:typeof window.VueReactivity!=='undefined'}};
        },{kind,version});
        observations.push({kind,...result});
      }finally{await context.close();}
    }
    const cases=observations[0].cases.map((source,i)=>{
      const target=observations[1].cases[i];let equal=true;try{assert.deepEqual(target,source);}catch{equal=false;}
      return {name:source.name,source:source.value,target:target.value,equal};
    });
    const fingerprints=Object.fromEntries([__filename,path.join(directory,'runtime.cjs'),path.join(directory,'owner.cjs'),
      path.join(project,'research/public_instance_v1/runtime.cjs'),path.join(project,'frontend/node_modules/vue/dist/vue.global.js'),
      path.join(project,'frontend/node_modules/@vue/reactivity/dist/reactivity.global.js'),path.join(project,'engine/node_modules/san/dist/san.dev.js')]
      .map(file=>[path.relative(project,file).replaceAll('\\','/'),createHash('sha256').update(fs.readFileSync(file)).digest('hex')]));
    return {status:cases.every(row=>row.equal)?'finite_owner_tree_cases_match':'owner_tree_difference_observed',runtime_version:version,
      cases,observations,errors,fingerprints,page_count:2,matched_cases:cases.filter(row=>row.equal).length,browser_version:await browser.version(),
      dynamic_child_prop_updates_verified:false,production_admission_eligible:false,arbitrary_public_key_contract_complete:false,model_calls:0,live_database_writes:0};
  }finally{await browser.close();}
}
if(require.main===module){const input=JSON.parse(fs.readFileSync(0,'utf8'));run(input.executable,input.version||'v6').then(report=>{
  if(input.output){const output=path.resolve(input.output);assert.ok(output.startsWith(path.join(project,'var')+path.sep));
    fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(report,null,2),{flag:'wx'});}
  console.log(JSON.stringify(report));
}).catch(error=>{console.error(error.stack);process.exitCode=1;});}
module.exports={run};
