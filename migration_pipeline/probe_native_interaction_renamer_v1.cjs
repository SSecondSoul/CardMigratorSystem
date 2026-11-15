/* Local bounded BatchRenamer calibration; no model or production dispatch. */
'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const {buildPage}=require('./utils/interaction_page_adapter_v2.cjs');
const {run}=require('./run_controlled_browser_interaction_v2.cjs');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const BASE='data/experiments/analysis/native_interaction_renamer_v1_20261115';
function pinned(p,h){const b=fs.readFileSync(p);if(sha(b)!==h)throw Error('Pinned input drift '+p);return b.toString('utf8');}
const edit=[{id:'prefix_img',op:'replace_text',selector:'.rename-rules label:nth-child(1) input',value:'img'},{id:'start_three',op:'replace_text',selector:'input[type=number]',value:'3'}];
const scenarios={edit,toggle:[{id:'hide',op:'click',selector:'.rename-rules button'},{id:'show',op:'click',selector:'.rename-rules button'}],apply:[...edit,{id:'apply_names',op:'click',selector:'button.primary'}]};
function prepareRenamer(outputDir){
  const files={
    vue:pinned('data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821/protocol/frozen/data/datasets/components/02_medium/BatchRenamer/vue/BatchRenamer.vue','c646db8cf35287e77b0c58aae4dc277ad0f35aeeec78dd8d8c28b5d89626be43'),
    san:pinned('data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821/pipeline/medium/BatchRenamer_repaired.san','42f782bec2a9fb1ecbaafe64a4a6a8316a72f5276a97a5e650b34bd1e90215bb')};
  const runtimes={vue:pinned('data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js','36b10d3b4920592a4ec26c064c429e9a3dfb4689235fdfc91e1736b681c76786'),san:pinned('node_modules/san/dist/san.dev.js','4b1c4a3a918d91663c0f79a4f77358a9de3c0ee1fbc01dfc47897f8531543134')};
  const pages=[],pairs=[],packaging={};
  for(const [scene,actions] of Object.entries(scenarios)){
    for(const framework of ['vue','san']){
      const name=scene+'_'+framework,id='BatchRenamer.'+framework;
      const built=buildPage({framework,main:id,modules:[{id,source:files[framework],dependencies:{}}],props:{},events:['apply'],eventIdentityFields:['currentFiles'],
        ready:{fields:['files','currentFiles','prefix','startAt','previewVisible','previews','hasDuplicates'],equals:{prefix:'asset',previewVisible:true},minLengths:{currentFiles:3}}},runtimes[framework]);
      packaging[name]={manifest:built.manifest,styles:built.styles,boundary:built.boundary,htmlSha256:sha(built.html)};
      pages.push({name,html:built.html,actions,selectors:{root:'.batch-renamer',title:'h2',prefix:'.rename-rules label:nth-child(1) input',start:'input[type=number]',toggle:'.rename-rules button',apply:'button.primary'},optionalSelectors:{table:'table',rows:'tbody tr',old_names:'tbody td:nth-child(1)',new_names:'tbody td:nth-child(2)'}});
    }pairs.push({source:scene+'_vue',target:scene+'_san'});
  }
  return {input:{pages,pairs,viewport:{width:1280,height:800},capturePolicy:'full-page',thresholds:{pixelTolerance:0,maxChangedPixelRatio:0,minSSIM:.999999999},outputDir},packaging};
}
function controlHTML(kind,side){
  return '<!doctype html><meta charset="utf-8"><link rel="icon" href="data:,"><input id="edit" value="old" '+(kind==='readonly'?'readonly':'')+'><p id="output">old</p><script>'+
    'let value="old";const events=[];document.querySelector("input").addEventListener("input",e=>{value=e.target.value'+(kind==='mismatch'&&side==='target'?'+ "!"':'')+';events.push({trusted:e.isTrusted,value});document.querySelector("p").textContent=value;});window.__componentEvidence=()=>({fields:{value},events:events.slice()});'+
    (kind==='warning'&&side==='source'?'console.warn("intentional_source_edit_warning");':'')+'window.__visualReady=true;</script>';
}
function prepareControls(outputDir){
  const pages=[],pairs=[];
  for(const kind of ['positive','mismatch','warning','readonly']){
    for(const side of ['source','target']){
      pages.push({name:kind+'_'+side,html:controlHTML(kind,side),selectors:{edit:'#edit',output:'#output'},optionalSelectors:{output:'#output'},
        actions:[{id:'replace',op:'replace_text',selector:'#edit',value:'img'},{id:'replace_again',op:'replace_text',selector:'#edit',value:'final'}]});
    }pairs.push({source:kind+'_source',target:kind+'_target'});
  }return {input:{pages,pairs,viewport:{width:640,height:480},capturePolicy:'full-page',thresholds:{pixelTolerance:0,maxChangedPixelRatio:0,minSSIM:.999999999},outputDir},packaging:{syntheticControls:true,componentMigrationEvidence:false}};
}
module.exports={prepareRenamer,prepareControls,scenarios,BASE};
if(require.main===module){
  const [kind,outputDir,...flags]=process.argv.slice(2);if(!['renamer','controls'].includes(kind)||!outputDir)throw Error('Expected renamer|controls NEW_OUTPUT_DIR [--execute]');
  const prepared=(kind==='renamer'?prepareRenamer:prepareControls)(path.resolve(outputDir));
  if(!flags.includes('--execute'))process.stdout.write(JSON.stringify({kind,pages:prepared.input.pages.map(p=>({name:p.name,actions:p.actions})),packaging:prepared.packaging}));
  else run(prepared.input).then(r=>{
    fs.writeFileSync(path.join(outputDir,'packaging.json'),JSON.stringify(prepared.packaging,null,2),{flag:'wx'});
    process.stdout.write(JSON.stringify({kind,status:r.status,passed:r.passed,registryComplete:r.nativeRegistry?.complete,comparisons:r.comparisons?.map(c=>({source:c.source,stage:c.stage,eligible:c.eligible,passed:c.passed,pixels:c.metrics?.changedPixels,styleChanges:c.styleChanges.length,reason:c.reason}))}));
  }).catch(e=>{process.stderr.write(e.stack);process.exitCode=2;});
}
