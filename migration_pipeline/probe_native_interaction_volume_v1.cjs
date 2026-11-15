/* Local-only calibration, never a generation or production command. */
'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const {buildPage}=require('./utils/interaction_page_adapter_v1.cjs');
const {run}=require('./run_controlled_browser_interaction_v1.cjs');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const BASE='data/experiments/analysis/native_interaction_volume_v1_20261115';
const sourcePath='data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821/protocol/frozen/data/datasets/components/01_simple/VolumeControl/vue/VolumeControl.vue';
const targetPath='data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821/pipeline/simple/VolumeControl_repaired.san';
function pinned(file,hash){const bytes=fs.readFileSync(file);if(sha(bytes)!==hash)throw Error('Pinned input drift '+file);return bytes.toString('utf8');}
const scenarios={
  range:[{id:'home_first',op:'key',selector:'.volume-slider',key:'Home'},{id:'end_max',op:'key',selector:'.volume-slider',key:'End'},{id:'home_again',op:'key',selector:'.volume-slider',key:'Home'}],
  mute:[{id:'mute',op:'click',selector:'button.primary'},{id:'restore',op:'click',selector:'button.primary'}]
};
function prepareVolume(outputDir){
  const files={vue:pinned(sourcePath,'e3fdfa524545f33182d837b7913bf760afe3476138ef6be147fb222822e7e6e1'),san:pinned(targetPath,'ad2828a2e224ab8fca7a7d0dee015e869a7631cd585f0ddad3f4825c1a3157b7')};
  const runtimes={vue:pinned('data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js','36b10d3b4920592a4ec26c064c429e9a3dfb4689235fdfc91e1736b681c76786'),san:pinned('node_modules/san/dist/san.dev.js','4b1c4a3a918d91663c0f79a4f77358a9de3c0ee1fbc01dfc47897f8531543134')};
  const pages=[],pairs=[],packaging={};
  for(const [scene,actions] of Object.entries(scenarios)){
    for(const framework of ['vue','san']){
      const name=scene+'_'+framework,id='VolumeControl.'+framework;
      const built=buildPage({framework,main:id,modules:[{id,source:files[framework],dependencies:{}}],props:{},events:['change'],
        ready:{fields:['initialVolume','volume','lastVolume','volumeLabel'],equals:{volume:45},minLengths:{}}},runtimes[framework]);
      packaging[name]={manifest:built.manifest,styles:built.styles,boundary:built.boundary,htmlSha256:sha(built.html)};
      pages.push({name,html:built.html,selectors:{root:'.volume-control',title:'h2',label:'.volume-control strong',range:'.volume-slider',action:'button.primary'},actions});
    }
    pairs.push({source:scene+'_vue',target:scene+'_san'});
  }
  return {input:{pages,pairs,viewport:{width:1280,height:800},capturePolicy:'full-page',
    thresholds:{pixelTolerance:0,maxChangedPixelRatio:0,minSSIM:0.999999999},outputDir},packaging};
}
function controlHTML(increment=1,warning=false,disabled=false){
  return '<!doctype html><meta charset="utf-8"><link rel="icon" href="data:,"><button id="action" '+(disabled?'disabled':'')+'>0</button><script>'+
    'let value=0;const events=[];document.querySelector("button").addEventListener("click",event=>{value+='+increment+';events.push({trusted:event.isTrusted,value});event.target.textContent=value;});window.__componentEvidence=()=>({fields:{value},events:events.slice()});'+
    (warning?'console.warn("intentional_source_warning_control");':'')+'window.__visualReady=true;</script>';
}
function prepareControls(outputDir){
  const pages=[],pairs=[];
  for(const kind of ['positive','mismatch','warning','missing','disabled']){
    for(const side of ['source','target']){
      const name=kind+'_'+side;
      pages.push({name,html:controlHTML(kind==='mismatch'&&side==='target'?2:1,kind==='warning'&&side==='source',kind==='disabled'),
        selectors:{button:'#action'},actions:[{id:'first',op:'click',selector:kind==='missing'?'#absent':'#action'},{id:'second',op:'click',selector:'#action'}]});
    }
    pairs.push({source:kind+'_source',target:kind+'_target'});
  }
  return {input:{pages,pairs,viewport:{width:640,height:480},capturePolicy:'full-page',thresholds:{pixelTolerance:0,maxChangedPixelRatio:0,minSSIM:0.999999999},outputDir},packaging:{syntheticControls:true,componentMigrationEvidence:false}};
}
module.exports={prepareVolume,prepareControls,scenarios,BASE};
if(require.main===module){
  const args=process.argv.slice(2),kind=args[0],outputDir=args[1];
  if(!['volume','controls'].includes(kind)||!outputDir)throw Error('Usage: node ... volume|controls NEW_OUTPUT_DIR [--execute]');
  const prepared=(kind==='volume'?prepareVolume:prepareControls)(path.resolve(outputDir));
  if(!args.includes('--execute')){process.stdout.write(JSON.stringify({prepared:true,kind,pages:prepared.input.pages.length,actions:prepared.input.pages.map(p=>({page:p.name,actions:p.actions})),packaging:prepared.packaging}));}
  else run(prepared.input).then(result=>{
    fs.writeFileSync(path.join(outputDir,'packaging.json'),JSON.stringify(prepared.packaging,null,2),{flag:'wx'});
    process.stdout.write(JSON.stringify({kind,status:result.status,passed:result.passed,registryComplete:result.nativeRegistry?.complete,stages:result.comparisons?.map(c=>({source:c.source,stage:c.stage,passed:c.passed,eligible:c.eligible,changedPixels:c.metrics?.changedPixels,reason:c.reason}))}));
    // Negative controls are expected failures; the independent checker determines their calibration outcome.
    if(kind==='volume'&&!result.passed)process.exitCode=2;
  }).catch(error=>{process.stderr.write(error.stack);process.exitCode=2;});
}
