/* Source-oracle diagnosis only. Never repairs production/source artifacts or runs models. */
'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const {parse}=require('@vue/compiler-sfc');
const {run}=require('./run_controlled_browser_pixel_v3.cjs');
const BASE='data/experiments/analysis/analytics_source_oracle_audit_v1_20261115';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
function pinned(p,h){const b=fs.readFileSync(p);if(sha(b)!==h)throw Error('Pinned input drift '+p);return b.toString('utf8');}
function snapshotTrend(instance){
  if(!instance||!instance._vnode)throw Error('TrendChart vnode absent');
  const svg=(instance._vnode.children||[]).find(n=>n.tag==='svg');
  if(!svg)throw Error('TrendChart SVG vnode absent');
  const keyed=(svg.children||[]).filter(n=>n.key!==undefined&&n.key!==null).map(n=>({
    key:n.key,kind:(n.children||[]).some(c=>c.tag==='line')?'grid':(n.children||[]).some(c=>c.tag==='circle')?'point':'other'
  }));
  const counts=new Map();for(const n of keyed)counts.set(n.key,(counts.get(n.key)||0)+1);
  const duplicateKeys=[...counts].filter(([,count])=>count>1).map(([key])=>key);
  return {keyed,duplicateKeys,gridGroups:keyed.filter(n=>n.kind==='grid').length,pointGroups:keyed.filter(n=>n.kind==='point').length,
    domCircles:instance.$el.querySelectorAll('circle').length,domGridLines:instance.$el.querySelectorAll('line').length,
    compilerRender:String(instance.$options.render),points:instance.$el.querySelector('polyline').getAttribute('points')};
}
function prepare(outputDir){
  const baseline=JSON.parse(fs.readFileSync(path.join(BASE,'baseline.json'),'utf8')),ref=baseline.native_recording_seal;
  const seal=pinned(ref.path,ref.sha256),dir=path.dirname(ref.path);
  for(const line of seal.trim().split(/\r?\n/)){const [h,p]=line.split('  ');pinned(path.join(dir,p),h);}
  const old=JSON.parse(fs.readFileSync(path.join(dir,'frozen_components/input.json'),'utf8'));
  const selected=baseline.selection.find(p=>p.component==='AnalyticsDashboard');
  const source=pinned(selected.source.path,selected.source.sha256);pinned(selected.target.path,selected.target.sha256);
  const parsed=parse(source,{filename:'AnalyticsDashboard.vue'});if(parsed.errors.length)throw Error('SFC parse failed');
  const script=parsed.descriptor.script.content,module={exports:{}};
  new Function('module','exports',script)(module,module.exports);
  const original=module.exports.components.TrendChart.template;
  if(original.split(':key="i"').length!==2||original.split(':key="idx"').length!==2)throw Error('Expected exact source key sites');
  const namespaced=original.replace(':key="i"',':key="\'grid-\' + i"').replace(':key="idx"',':key="\'point-\' + idx"');
  const runtime=pinned('data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js','36b10d3b4920592a4ec26c064c429e9a3dfb4689235fdfc91e1736b681c76786');
  const pages=[],pairs=[],binding={fullSourceSFC:selected.source,fullTargetSFC:selected.target,sourceScriptSha256:sha(script),
    nativeSeal:ref,fixtureCases:[],boundary:{diagnosisOnly:true,namespaceVariantIsMechanismControlNotSourceCorrection:true,productionOrMigrationPass:false,modelCalls:0}};
  const vue=old.pages.find(p=>p.name==='analytics_default_vue'),san=old.pages.find(p=>p.name==='analytics_default_san');
  if(!vue||!san)throw Error('Old full pages absent');
  const anchor='window.__componentEvidence=observe;';
  if(vue.html.split(anchor).length!==2)throw Error('Expected exact passive observer scaffold');
  const html=vue.html.replace(anchor,'const keySnapshot='+snapshotTrend.toString()+";window.__componentEvidence=()=>({...observe(),keyAudit:keySnapshot(instance.$children.find(c=>c.$options.name==='TrendChart'))});");
  pages.push({...vue,html});pages.push(san);pairs.push({source:vue.name,target:san.name});
  binding.fullPages={sourceOriginalHTMLSha256:sha(vue.html),sourceObservedHTMLSha256:sha(html),targetHTMLSha256:sha(san.html),observerOnlyScaffoldChanged:true};
  const escape=s=>s.replace(/<\//g,'<\\/');
  for(const count of [1,2,7,30,90]){
    const points=Array.from({length:count},(_,i)=>({value:100+i,date:'fixture-'+i,label:String(i)}));
    for(const variant of ['original','namespaced']){
      const name='trend_'+count+'_'+variant,template=variant==='original'?original:namespaced;
      const bootstrap=`(async()=>{const snapshot=${snapshotTrend.toString()},module={exports:{}};
        new Function('module','exports',${JSON.stringify(script)})(module,module.exports);
        const Original=module.exports.components.TrendChart, Component={...Original,template:${JSON.stringify(template)}};
        const Vue=window.Vue;if(Vue.version!=='2.7.16')throw Error('Runtime drift');
        Vue.config.warnHandler=(message,_vm,trace)=>console.error('Vue component warning',message,trace);
        Vue.config.errorHandler=(error,_vm,info)=>console.error('Vue component error',info,error.stack||String(error));
        const vm=new Vue({data(){return {points:[]};},render(h){return h(Component,{props:{data:this.points,height:300,loading:false}});}});
        vm.$mount();document.getElementById('host').append(vm.$el);
        const rows=${JSON.stringify(points)};
        vm.points=rows;await Vue.nextTick();vm.points=rows.slice();await Vue.nextTick();
        window.__componentEvidence=()=>({framework:'vue',fixture:true,count:${count},variant:${JSON.stringify(variant)},keyAudit:snapshot(vm.$children[0])});
        window.__visualReady=true;
        window.addEventListener('pagehide',()=>vm.$destroy(),{once:true});
      })().catch(error=>console.error('Fixture failure',error.stack||String(error)));`;
      const fixture='<!doctype html><meta charset="utf-8"><link rel="icon" href="data:,"><style>body{margin:8px;font-family:Arial}.trend-chart{width:800px}</style><div id="host"></div><script>'+escape(runtime)+'</script><script>'+escape(bootstrap)+'</script>';
      pages.push({name,html:fixture,selectors:{root:'.trend-chart',svg:'svg',legend:'.chart-legend'}});
      binding.fixtureCases.push({name,count,variant,templateSha256:sha(template),htmlSha256:sha(fixture),sourceBusinessBodiesUnmodified:true});
    }pairs.push({source:'trend_'+count+'_original',target:'trend_'+count+'_namespaced'});
  }
  for(const page of pages)for(const block of page.html.matchAll(/<script>([\s\S]*?)<\/script>/g))new (require('vm').Script)(block[1]);
  binding.keySites={grid:{line:source.slice(0,source.indexOf('<g v-for="i in 5"')).split('\n').length,original:':key="i"',control:':key="\'grid-\' + i"'},points:{line:source.slice(0,source.indexOf('<g v-for="(point, idx) in data"')).split('\n').length,original:':key="idx"',control:':key="\'point-\' + idx"'}};
  return {input:{pages,pairs,viewport:{width:1280,height:800},capturePolicy:'full-page',thresholds:{pixelTolerance:0,maxChangedPixelRatio:0,minSSIM:.999999999},outputDir},binding};
}
module.exports={prepare,snapshotTrend,BASE};
if(require.main===module){
 const [out,flag]=process.argv.slice(2);if(!out)throw Error('New output directory required');
 const p=prepare(path.resolve(out));
 if(flag!=='--execute')process.stdout.write(JSON.stringify({pages:p.input.pages.length,pairs:p.input.pairs.length,binding:p.binding}));
 else run(p.input).then(r=>{fs.writeFileSync(path.join(out,'binding.json'),JSON.stringify(p.binding,null,2),{flag:'wx'});process.stdout.write(JSON.stringify({status:r.status,passed:r.passed,registryComplete:r.nativeRegistry?.complete,diagnostics:r.nativeRegistry?.events.length,comparisons:r.comparisons?.map(c=>({source:c.source,eligible:c.eligible,passed:c.passed,pixels:c.metrics?.changedPixels,reason:c.reason,styles:c.styleChanges.length}))}));}).catch(e=>{process.stderr.write(e.stack);process.exitCode=2;});
}
