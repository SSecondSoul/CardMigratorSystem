/* Native-only San candidate checks; no public Proxy or reactive kernel is loaded. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {createRequire} = require('node:module'), {createHash} = require('node:crypto');
const {loadCandidate, fingerprintFiles} = require('./san_candidate.cjs');
const project = path.resolve(__dirname, '../..');
const puppeteer = createRequire(path.join(project, 'browser/package.json'))('puppeteer-core');

async function run(executable) {
  const candidate = loadCandidate();
  const browser = await puppeteer.launch({executablePath: executable, headless:true,
    args:['--disable-background-networking','--disable-extensions','--disable-sync']});
  const observations=[],errors=[];
  try {
    for (const kind of ['source','upstream','candidate']) {
      const context=await browser.createBrowserContext(),page=await context.newPage();
      try {
        page.on('pageerror',error=>errors.push({kind,message:error.message}));
        page.on('console',msg=>{if(['warning','error'].includes(msg.type()))errors.push({kind,message:msg.text()});});
        await page.setRequestInterception(true);page.on('request',request=>request.abort());
        await page.setContent('<!doctype html><main id="app"></main>');
        if(kind==='candidate')await page.addScriptTag({content:candidate.content});
        else await page.addScriptTag({path:path.join(project,kind==='source'?
          'frontend/node_modules/vue/dist/vue.global.js':'engine/node_modules/san/dist/san.dev.js')});
        observations.push({kind,...await page.evaluate(async kind=>{
          const cases=[];let finalDisposal=null;
          const tick=()=>kind==='source'?Vue.nextTick():new Promise(resolve=>san.nextTick(resolve));
          const host=document.getElementById('app');
          // Recreated object items test native prop/index propagation, not proxy child props.
          const fixtures=[['a','b','c'],['c','b'],['b','c'],['d','c','b'],['b','d','c'],
            ['c','d','b'],['c','b','d'],['b','c','d'],['d','b','c'],['b'],[],['b','a'],['a','b']];
          {
            const members=new Map(),disposed=[],created=[];let app,root;
            if(kind==='source') {
              const Child={props:['item','index'],data(){return {count:0};},created(){members.set(this.item.id,this);created.push(this.item.id);},
                unmounted(){disposed.push(this.item.id);},
                render(){return Vue.h('button',{'data-id':this.item.id,onClick:()=>this.count++},`${this.item.label}:${this.index}:${this.count}`);}};
              app=Vue.createApp({data(){return {items:[]};},render(){return Vue.h('section',this.items.map((item,index)=>Vue.h(Child,{key:item.id,item,index})));}});
              root=app.mount(host);
            }else{
              const Child=san.defineComponent({template:'<button data-id="{{item.id}}" on-click="increment">{{item.label}}:{{index}}:{{count}}</button>',
                initData(){return {count:0};},increment(){this.data.set('count',this.data.get('count')+1);},
                inited(){members.set(this.data.get('item').id,this);created.push(this.data.get('item').id);},
                disposed(){disposed.push(this.lastId);},attached(){this.lastId=this.data.get('item').id;}});
              const Root=san.defineComponent({template:'<section><child-box s-for="item,index in items trackBy item.id" item="{{item}}" index="{{index}}"/></section>',
                components:{'child-box':Child},initData(){return {items:[]};}});
              root=new Root();root.attach(host);
            }
            let previous=new Map();const steps=[];
            for(let step=0;step<fixtures.length;step++){
              const ids=fixtures[step],items=ids.map(id=>({id,label:id+'-'+step}));
              if(kind==='source')root.items=items;else root.data.set('items',items);
              await tick();
              const retained=ids.filter(id=>previous.has(id)).map(id=>({id,same:previous.get(id)===members.get(id)}));
              // DOM listener stays on the same native element after moving it.
              for(const button of host.querySelectorAll('button'))button.click();
              await tick();
              steps.push({ids,retained,dom:[...host.querySelectorAll('button')].map(el=>el.textContent),created:[...created],disposed:[...disposed]});
              previous=new Map(ids.map(id=>[id,members.get(id)]));
            }
            const disposeStart=disposed.length;
            if(kind==='source')app.unmount();else root.dispose();await tick();
            finalDisposal=disposed.slice(disposeStart);
            cases.push({name:'native-component-thirteen-updates-identity-local-state-props-index-events',value:{steps}});
          }
          {
            let app,root;
            if(kind==='source'){
              app=Vue.createApp({data(){return {ids:['a','b','c']};},render(){return Vue.h('section',this.ids.map(id=>Vue.h('span',{key:id,'data-id':id},id)));}});root=app.mount(host);
            }else{
              const Root=san.defineComponent({template:'<section><span s-for="id in ids trackBy id" data-id="{{id}}">{{id}}</span></section>',initData(){return {ids:['a','b','c']};}});
              root=new Root();root.attach(host);
            }
            const elements=new Map([...host.querySelectorAll('span')].map(el=>[el.dataset.id,el]));
            const steps=[];
            for(const ids of [['c','b'],['b','c','a'],['a','c','b']]){
              if(kind==='source')root.ids=ids;else root.data.set('ids',ids);await tick();
              steps.push({dom:[...host.querySelectorAll('span')].map(el=>el.textContent),
                retained:ids.filter(id=>id!=='a').map(id=>elements.get(id)===host.querySelector(`[data-id="${id}"]`))});
            }
            if(kind==='source')app.unmount();else root.dispose();await tick();
            cases.push({name:'plain-element-keyed-path-remains-compatible',value:steps});
          }
          const controls=[];
          if(kind==='candidate'){
            // Invoke actual ForNode update synchronously, so rejection is captured, not hidden
            // in an uncaught async page error. Silent Data.set alone is not the tested result.
            function rejected(name,template,next,decorate){
              const members=[];
              const Sub=san.defineComponent({template:'<span>{{item}}</span>'});
              const Child=san.defineComponent({template,components:{'sub-box':Sub},
                fade(){return {enter(el,done){done();},leave(el,done){done();}};},
                initData(){return {count:0};},inited(){members.push(this);}});
              const Root=san.defineComponent({template:'<section><child-box s-for="item in ids trackBy item" item="{{item}}"/></section>',
                components:{'child-box':Child},initData(){return {ids:['a','b','c']};}});
              const root=new Root();root.attach(host);const loop=root.children[0];
              if(decorate)decorate(members);
              const before=host.innerHTML,original=[...loop.children];let message=null;
              root.data.set('ids',next,{silent:true});
              try{loop._update([{type:1,expr:san.parseExpr('ids'),value:next,option:{}}]);}catch(error){message=error.message;}
              controls.push({name,message,domUnchanged:host.innerHTML===before,
                instancesUnchanged:original.every((child,index)=>loop.children[index]===child&&!child.lifeCycle.disposed)});
              // Undo test-only transition marker; native disposal must remain synchronous.
              for(const child of members)delete child.transition;
              root.dispose();
            }
            rejected('fragment-root','<fragment><i>{{item}}</i><b>{{item}}</b></fragment>',['c','b']);
            rejected('conditional-root','<span s-if="true">{{item}}</span>',['c','b']);
            rejected('component-root','<sub-box item="{{item}}"/>',['c','b']);
            rejected('transition-directive','<span s-transition="fade">{{item}}</span>',['c','b']);
            rejected('transition-property','<span>{{item}}</span>',['c','b'],members=>{members[1].transition={};});
            rejected('duplicate-keys','<span>{{item}}</span>',['b','b']);
            rejected('reserved-key','<span>{{item}}</span>',['__proto__','b']);
            rejected('numeric-key','<span>{{item}}</span>',[1,'b']);
            rejected('symbol-key','<span>{{item}}</span>',[Symbol('x'),'b']);
          }
          return {cases,controls,finalDisposal,runtime:{vue:typeof window.Vue!=='undefined',kernel:typeof window.VueReactivity!=='undefined'}};
        },kind)});
      }finally{await context.close();}
    }
    const cases=observations[0].cases.map((source,index)=>{
      const before=observations[1].cases[index],after=observations[2].cases[index];
      return {name:source.name,source:source.value,upstream:before.value,candidate:after.value,
        before_equal:JSON.stringify(source)===JSON.stringify(before),equal:JSON.stringify(source)===JSON.stringify(after)};
    });
    const native_disposal_order={source:observations[0].finalDisposal,upstream:observations[1].finalDisposal,candidate:observations[2].finalDisposal,
      equal:JSON.stringify(observations[0].finalDisposal)===JSON.stringify(observations[2].finalDisposal),
      scope:'raw-San-without-owner-bridge-final-disposal-order-is-not-fixed-by-keyed-move-patch'};
    return {status:cases.every(row=>row.equal)?'finite_native_keyed_cases_match_with_raw_disposal_gap':'native_keyed_difference_observed',cases,observations,errors,native_disposal_order,
      matched_cases:cases.filter(row=>row.equal).length,san_candidate:{...candidate,content:undefined},
      fingerprints:{...fingerprintFiles(),[path.relative(project,__filename).replaceAll('\\','/')]:createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),
        'frontend/node_modules/vue/dist/vue.global.js':createHash('sha256').update(fs.readFileSync(path.join(project,'frontend/node_modules/vue/dist/vue.global.js'))).digest('hex')},
      browser_version:await browser.version(),page_count:3,dynamic_proxy_child_props_verified:false,
      production_admission_eligible:false,arbitrary_public_key_contract_complete:false,model_calls:0,live_database_writes:0};
  }finally{await browser.close();}
}
if(require.main===module){const input=JSON.parse(fs.readFileSync(0,'utf8'));run(input.executable).then(report=>{
  if(input.output){const output=path.resolve(input.output);assert.ok(output.startsWith(path.join(project,'var')+path.sep));
    fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(report,null,2),{flag:'wx'});}
  console.log(JSON.stringify(report));
}).catch(error=>{console.error(error.stack);process.exitCode=1;});}
module.exports={run};
