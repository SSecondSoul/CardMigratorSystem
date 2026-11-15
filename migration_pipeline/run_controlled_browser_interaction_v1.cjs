/* Bounded native-input pilot. Derived from v3 native session registered, per-page browser-context full-page capture for prepared frozen components. Not a source compiler,
 * sandbox for hostile code, interaction oracle, or production batch gate.
 * Node >=22 native WebSocket; local Edge only. No npm/CDN/model dependencies.
 */
'use strict';
const fs=require('fs'),path=require('path'),os=require('os'),http=require('http'),crypto=require('crypto');
const {spawn}=require('child_process');
const {validateActions,executeAction}=require('./utils/native_interaction_actions_v1.cjs');
const {SessionRegistry}=require('./utils/browser_session_registry_v1.cjs');
const {decodePNG,encodePNG,compareRGBA}=require('./utils/browser_pixel_metrics_v1.cjs');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const DEFAULT_ENV={width:640,height:480,deviceScaleFactor:1,locale:'zh-CN',timezone:'Asia/Shanghai',theme:'light',
  reducedMotion:'reduce',font:'Arial',epoch:1794700800000,seed:1729,readyContract:'window.__visualReady === true',
  repeatDelayMs:120,animations:'disabled',network:'only exact loopback fixture routes',viewportOnly:true};
const STYLE_KEYS=['display','position','color','background-color','font-family','font-size','font-weight','line-height',
  'padding-top','padding-right','padding-bottom','padding-left','margin-top','margin-right','margin-bottom','margin-left',
  'border-top-width','border-top-color','border-radius','opacity','visibility'];
function validate(input){
  if(!input||!Array.isArray(input.pages)||!input.pages.length||input.pages.length>24)throw Error('Need 1..24 self-contained pages');
  const names=new Set();for(const page of input.pages){
    if(!/^[a-z][a-z0-9_-]{0,50}$/.test(page.name)||names.has(page.name)||typeof page.html!=='string'||page.html.length>2000000)throw Error('Invalid/duplicate page');names.add(page.name);
    if(!page.selectors||typeof page.selectors!=='object'||Array.isArray(page.selectors)||!Object.keys(page.selectors).length)throw Error('Explicit nonempty semantic selector mapping required');
    for(const [key,s] of Object.entries(page.selectors))if(!/^[a-z][a-z0-9_-]*$/.test(key)||typeof s!=='string'||!s||s.length>300)throw Error('Invalid selector');
  }
  if(!Array.isArray(input.pairs)||!input.pairs.length)throw Error('Explicit comparison pairs required');
  for(const pair of input.pairs)if(!names.has(pair.source)||!names.has(pair.target))throw Error('Unknown comparison page');
  const t=input.thresholds;if(!t||!Number.isFinite(t.maxChangedPixelRatio)||t.maxChangedPixelRatio<0||t.maxChangedPixelRatio>1||!Number.isFinite(t.minSSIM)||t.minSSIM<-1||t.minSSIM>1||!Number.isInteger(t.pixelTolerance)||t.pixelTolerance<0||t.pixelTolerance>255)throw Error('Explicit finite thresholds required');
  if(!input.viewport||!Number.isInteger(input.viewport.width)||!Number.isInteger(input.viewport.height)||input.viewport.width<320||input.viewport.width>1920||input.viewport.height<240||input.viewport.height>1200)throw Error('Explicit bounded viewport required');
  if(!['viewport','full-page'].includes(input.capturePolicy))throw Error('Explicit capture policy required');
  for(const page of input.pages)validateActions(page.actions);
  for(const pair of input.pairs){
    const a=input.pages.find(p=>p.name===pair.source),b=input.pages.find(p=>p.name===pair.target);
    if(JSON.stringify(a.actions)!==JSON.stringify(b.actions))throw Error('Paired native action plans must be identical');
  }
  return input;
}
function styleDifferences(a,b){
  const changes=[];for(const key of new Set([...Object.keys(a),...Object.keys(b)])){
    if(!a[key]||!b[key]){changes.push({key,property:'mapping',source:a[key]||null,target:b[key]||null});continue;}
    for(const property of ['rect',...STYLE_KEYS])if(JSON.stringify(a[key][property])!==JSON.stringify(b[key][property]))changes.push({key,property,source:a[key][property],target:b[key][property]});
  }return changes;
}
async function run(input){
  validate(input);const ENV={...DEFAULT_ENV,...input.viewport,viewportOnly:input.capturePolicy==='viewport',capturePolicy:input.capturePolicy,maxPixels:4000000,scrollbarGutter:'stable'};const output=path.resolve(input.outputDir||'');if(!input.outputDir||fs.existsSync(output))throw Error('New explicit outputDir required; never overwrite evidence');
  const executable=input.browserExecutable||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
  const executableSha=sha(fs.readFileSync(executable)); // Fail, never skip-as-pass.
  const profile=fs.mkdtempSync(path.join(os.tmpdir(),'cardmig-interaction-v1-'));
  fs.mkdirSync(output,{recursive:true});fs.writeFileSync(path.join(output,'input.json'),JSON.stringify(input,null,2),{flag:'wx'});
  const pages=new Map(input.pages.map((p,i)=>['/page/'+i,p.html]));pages.set('/','<!doctype html><meta charset="utf-8"><link rel="icon" href="data:,">');
  const requests=[],blocked=[],protocolErrors=[],exceptions=[],consoleErrors=[];
  const server=http.createServer((req,res)=>{requests.push({method:req.method,path:req.url});res.setHeader('Cache-Control','no-store');
    res.setHeader('Content-Security-Policy',"default-src 'self' data:; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; connect-src 'none'; frame-src 'none'; worker-src 'none'; object-src 'none'");
    if(req.method!=='GET'||!pages.has(req.url)){res.writeHead(404);res.end();return;}
    res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(pages.get(req.url));});
  let browser,ws,version,result,origin,registry,browserStderr='';const protocolTrace=[];const runId=crypto.randomUUID();const pending=new Map();let nextId=0;const commandTimeout=10000;
  const send=(method,params={},sessionId)=>new Promise((resolve,reject)=>{
    if(ws?.readyState!==WebSocket.OPEN){reject(Error('CDP is not open: '+method));return;}
    const id=++nextId,timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout '+method));},commandTimeout);
    protocolTrace.push({phase:'send',id,method,sessionId:sessionId||null});
    pending.set(id,{resolve,reject,timer});try{ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));}catch(e){clearTimeout(timer);pending.delete(id);reject(e);}
  });
  try{
    await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});origin='http://127.0.0.1:'+server.address().port;
    registry=new SessionRegistry(runId,origin,input.pages,input.pairs);
    browser=spawn(executable,['--headless=new','--remote-debugging-port=0','--user-data-dir='+profile,'--no-first-run','--no-default-browser-check',
      '--disable-extensions','--disable-background-networking','--disable-component-update','--disable-sync','--force-color-profile=srgb','--lang=zh-CN','about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
    let spawnError=null,stderr='';browser.on('error',e=>{spawnError=e;});browser.stderr.on('data',data=>{stderr+=String(data);browserStderr+=String(data);});
    const active=path.join(profile,'DevToolsActivePort'),stop=Date.now()+30000;
    while(!fs.existsSync(active)){if(spawnError)throw spawnError;if(browser.exitCode!==null||Date.now()>stop)throw Error('Browser startup failed '+stderr);await pause(50);}
    const [port,endpoint]=fs.readFileSync(active,'utf8').trim().split(/\r?\n/);if(!/^\d+$/.test(port)||!endpoint.startsWith('/devtools/browser/'))throw Error('Invalid private endpoint');
    ws=new WebSocket('ws://127.0.0.1:'+port+endpoint);
    await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('WebSocket open timeout')),10000);ws.addEventListener('open',()=>{clearTimeout(timer);resolve();},{once:true});ws.addEventListener('error',e=>{clearTimeout(timer);reject(e);},{once:true});});
    ws.addEventListener('message',event=>{
      const m=JSON.parse(event.data);if(m.id){protocolTrace.push({phase:'response',id:m.id,error:m.error||null});const p=pending.get(m.id);if(p){clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}return;}
      if(m.method==='Runtime.executionContextCreated')registry.contextCreated(m.sessionId,m.params.context);
      if(m.method==='Runtime.exceptionThrown'){const e=registry.diagnostic('runtime_exception',m.sessionId,m.params.exceptionDetails);exceptions.push(e);}
      if(m.method==='Runtime.consoleAPICalled'&&['error','warning'].includes(m.params.type))consoleErrors.push(registry.diagnostic('console_'+m.params.type,m.sessionId,m.params));
      if(m.method==='Log.entryAdded'&&['error','warning'].includes(m.params.entry.level))consoleErrors.push(registry.diagnostic('browser_log',m.sessionId,{log:m.params.entry}));
      if(m.method==='Fetch.requestPaused'){
        const u=m.params.request.url,allowed=registry.allows(m.sessionId,m.params.request);
        if(!allowed){blocked.push(u);registry.diagnostic('blocked_request',m.sessionId,{url:u,method:m.params.request.method});}send(allowed?'Fetch.continueRequest':'Fetch.failRequest',allowed?{requestId:m.params.requestId}:{requestId:m.params.requestId,errorReason:'BlockedByClient'},m.sessionId).catch(e=>protocolErrors.push(String(e)));
      }
    });
    ws.addEventListener('close',()=>{for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('CDP connection closed'));}pending.clear();});
    version=await send('Browser.getVersion');const captures={},stages={},actions={};
    for(let index=0;index<input.pages.length;index++){
      const page=input.pages[index];
      stages[page.name]=Object.fromEntries(['initial',...page.actions.map(a=>a.id)].map(id=>[id,{status:'not_run',clean:false,stable:false}]));
      actions[page.name]=page.actions.map(a=>({...a,status:'not_run'}));let currentStage='initial';
      let targetId,contextId,entry;try{
      ({browserContextId:contextId}=await send('Target.createBrowserContext',{disposeOnDetach:true}));
      ({targetId}=await send('Target.createTarget',{url:'about:blank',browserContextId:contextId}));
      const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
      entry=registry.register(index,contextId,targetId,sessionId,sha(Buffer.from(page.html)));
      await send('Runtime.enable',{},sessionId);await send('Page.enable',{},sessionId);await send('Network.enable',{},sessionId);await send('Log.enable',{},sessionId);
      await send('Network.setCacheDisabled',{cacheDisabled:true},sessionId);await send('Network.setBypassServiceWorker',{bypass:true},sessionId);
      await send('Fetch.enable',{patterns:[{urlPattern:'*'}]},sessionId);
      await send('Emulation.setDeviceMetricsOverride',{width:ENV.width,height:ENV.height,deviceScaleFactor:ENV.deviceScaleFactor,mobile:false},sessionId);
      await send('Emulation.setLocaleOverride',{locale:ENV.locale},sessionId);await send('Emulation.setTimezoneOverride',{timezoneId:ENV.timezone},sessionId);
      await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:ENV.theme},{name:'prefers-reduced-motion',value:ENV.reducedMotion}]},sessionId);
      const init=`(()=>{const NativeDate=Date;class FixedDate extends NativeDate{constructor(...a){super(...(a.length?a:[${ENV.epoch}]));}static now(){return ${ENV.epoch};}};window.Date=FixedDate;let seed=${ENV.seed};Math.random=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;};window.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent='html{font-family:Arial;color-scheme:light;scrollbar-gutter:stable}*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}';document.head.append(s);});})()`;
      await send('Page.addScriptToEvaluateOnNewDocument',{source:init},sessionId);await send('Page.navigate',{url:origin+'/page/'+index},sessionId);
      const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},sessionId);if(r.exceptionDetails)throw Error('Page evaluation failed '+JSON.stringify(r.exceptionDetails));return r.result.value;};
      const deadline=Date.now()+3000;while(!await evaluate('document.readyState === "complete" && window.__visualReady === true')){if(Date.now()>deadline)throw Error('Explicit readiness timeout '+page.name);await pause(50);}
      const {targetInfo}=await send('Target.getTargetInfo',{targetId});
      const {frameTree}=await send('Page.getFrameTree',{},sessionId);
      registry.verify(entry,targetInfo,frameTree.frame);
      await evaluate('document.fonts.ready.then(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))).then(()=>true)');
      const observationExpression=`(()=>{const extent={width:document.documentElement.scrollWidth,height:Math.max(innerHeight,document.documentElement.scrollHeight)};if(extent.width>${ENV.width})throw Error('Horizontal overflow; no resize/crop');if(${ENV.viewportOnly}&&extent.height>${ENV.height})throw Error('Viewport overflow');if(extent.width*extent.height>${ENV.maxPixels})throw Error('Full-page pixel budget exceeded');const out={};for(const [key,selector] of Object.entries(${JSON.stringify(page.selectors)})){const nodes=document.querySelectorAll(selector);if(nodes.length!==1)throw Error('Selector must match exactly one: '+key+' ('+nodes.length+')');const n=nodes[0],s=getComputedStyle(n),r=n.getBoundingClientRect();if(r.width<=0||r.height<=0||r.x<0||r.y<0||r.right>${ENV.width}||r.bottom>extent.height)throw Error('Critical element outside capture '+key);out[key]={rect:{x:r.x,y:r.y,width:r.width,height:r.height},...Object.fromEntries(${JSON.stringify(STYLE_KEYS)}.map(k=>[k,s.getPropertyValue(k)]))};}const domValues=Object.fromEntries(Object.entries(${JSON.stringify(page.selectors)}).map(([k,s])=>{const n=document.querySelector(s);return [k,{text:n.textContent,value:n.value??null,checked:n.checked??null}];}));return {styles:out,domValues,extent,componentEvidence:typeof window.__componentEvidence==='function'?window.__componentEvidence():null,environment:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio,theme:matchMedia('(prefers-color-scheme:light)').matches,reducedMotion:matchMedia('(prefers-reduced-motion:reduce)').matches,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,locale:Intl.DateTimeFormat().resolvedOptions().locale,time:Date.now()}};})()`;
      const captureAt=async stage=>{
        const observation=await evaluate(observationExpression);
        const screenshot=async obs=>Buffer.from((await send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:!ENV.viewportOnly,...(ENV.viewportOnly?{}:{clip:{x:0,y:0,width:ENV.width,height:obs.extent.height,scale:1}})},sessionId)).data,'base64');
        const first=await screenshot(observation);await pause(ENV.repeatDelayMs);
        const repeatObservation=await evaluate(observationExpression),second=await screenshot(repeatObservation);
        registry.verify(entry,(await send('Target.getTargetInfo',{targetId})).targetInfo,(await send('Page.getFrameTree',{},sessionId)).frameTree.frame);
        const stem=page.name+'--'+stage;
        fs.writeFileSync(path.join(output,stem+'.png'),first,{flag:'wx'});
        fs.writeFileSync(path.join(output,stem+'-repeat.png'),second,{flag:'wx'});
        const decoded=decodePNG(first),again=decodePNG(second);
        if(decoded.width!==ENV.width||decoded.height!==(ENV.viewportOnly?ENV.height:observation.extent.height))throw Error('Screenshot size differs from capture extent');
        const sameSize=decoded.width===again.width&&decoded.height===again.height,stability=sameSize?compareRGBA(decoded,again):null;
        const stable=!!stability&&stability.changedPixels===0&&JSON.stringify(observation)===JSON.stringify(repeatObservation);
        const changedObservationKeys=Object.keys(observation).filter(key=>JSON.stringify(observation[key])!==JSON.stringify(repeatObservation[key]));
        return {...observation,repeatObservation,changedObservationKeys,stage,screenshot:stem+'.png',
          nativeSessionId:entry.sessionId,nativeContextId:entry.contextId,htmlSha256:sha(Buffer.from(page.html)),
          screenshotSha256:sha(first),repeatScreenshotSha256:sha(second),stable,clean:registry.clean(entry),status:'captured',repeatChangedPixels:stability?.changedPixels??null};
      };
      stages[page.name].initial=await captureAt('initial');captures[page.name]=stages[page.name].initial;
      for(let i=0;i<page.actions.length;i++){
        const action=page.actions[i];currentStage=action.id;
        const performed=await executeAction(action,send,evaluate,sessionId);
        actions[page.name][i]={...performed,status:'executed'};
        stages[page.name][action.id]=await captureAt(action.id);
      }
      }catch(pageError){
        stages[page.name][currentStage]={status:'blocked',error:String(pageError.stack||pageError),clean:false,stable:false};
        if(currentStage==='initial')captures[page.name]=stages[page.name].initial;
        else {const pending=actions[page.name].find(a=>a.id===currentStage);if(pending.status==='not_run')pending.status='blocked';}
      }
      finally{
        if(targetId)try{await send('Target.closeTarget',{targetId});}catch(error){protocolErrors.push(String(error));}
        if(contextId)try{await send('Target.disposeBrowserContext',{browserContextId:contextId});if(entry)registry.disposed(entry);}catch(error){protocolErrors.push(String(error));}
      }
    }
    const nativeRegistry=registry.snapshot();
    for(const entry of nativeRegistry.entries)for(const c of Object.values(stages[entry.page]||{}))if(c.status==='captured')c.clean=registry.clean(entry);
    const comparisons=[];
    for(let index=0;index<input.pairs.length;index++){
      const pair=input.pairs[index],plan=input.pages.find(p=>p.name===pair.source);
      for(const stage of ['initial',...plan.actions.map(a=>a.id)]){
        const a=stages[pair.source][stage],b=stages[pair.target][stage];
        if(a.status!=='captured'||b.status!=='captured'){comparisons.push({...pair,stage,metrics:null,diff:null,styleChanges:[],eligible:false,passed:false,reason:'stage_not_captured'});continue;}
        const left=decodePNG(fs.readFileSync(path.join(output,a.screenshot))),right=decodePNG(fs.readFileSync(path.join(output,b.screenshot)));
        const styleChanges=styleDifferences(a.styles,b.styles),eligible=a.stable&&b.stable&&a.clean&&b.clean&&protocolErrors.length===0&&nativeRegistry.complete;
        if(left.width!==right.width||left.height!==right.height){comparisons.push({...pair,stage,metrics:null,diff:null,styleChanges,eligible,passed:false,reason:'dimension_mismatch_no_resize'});continue;}
        const metric=compareRGBA(left,right,input.thresholds),diffName='diff-'+index+'--'+stage+'.png';
        fs.writeFileSync(path.join(output,diffName),encodePNG(metric.width,metric.height,metric.diff),{flag:'wx'});delete metric.diff;
        comparisons.push({...pair,stage,metrics:metric,styleChanges,diff:diffName,eligible,passed:eligible&&metric.changedPixelRatio<=input.thresholds.maxChangedPixelRatio&&metric.ssim>=input.thresholds.minSSIM&&styleChanges.length===0});
      }
    }
    if(sha(fs.readFileSync(executable))!==executableSha)throw Error('Browser executable changed during run');
    result={schemaVersion:4,nativeRegistry,status:comparisons.every(p=>p.eligible)?'evaluated':'blocked',passed:comparisons.every(p=>p.passed),environment:ENV,thresholds:input.thresholds,
      browser:{...version,executable,executableSha256:executableSha,isolatedProfile:true,isolatedContextPerPage:true,headless:true},captures,stages,actions,comparisons,
      transport:{requests,blocked,protocolErrors,loopbackOnly:true},exceptions,consoleErrors,
      boundary:{selfContainedHTMLOnly:true,componentCompiler:false,productionIntegrated:false,interactionEquivalence:false,nativeBoundedActionPilot:true,comprehensiveMigrationPass:false,fullPage:!ENV.viewportOnly,fontBinaryPinned:false,modelCalls:0,historicalScoresChanged:false}};
  }catch(error){
    result={schemaVersion:4,nativeRegistry:registry?.snapshot()||null,status:'blocked',passed:false,error:String(error.stack||error),environment:ENV,browser:version||null,exceptions,consoleErrors,blocked,protocolErrors};
  }finally{
    const cleanup=[];
    if(ws?.readyState===WebSocket.OPEN){try{await send('Browser.close');}catch(e){cleanup.push(String(e));}ws.close();}
    if(browser&&browser.exitCode===null){await Promise.race([new Promise(r=>browser.once('exit',r)),pause(3000)]);if(browser.exitCode===null){browser.kill();await Promise.race([new Promise(r=>browser.once('exit',r)),pause(2000)]);}}
    await new Promise(resolve=>server.close(resolve));
    const resolved=path.resolve(profile);if(!resolved.startsWith(path.resolve(os.tmpdir())+path.sep)||!path.basename(resolved).startsWith('cardmig-interaction-v1-'))throw Error('Unsafe profile cleanup target');
    try{fs.rmSync(resolved,{recursive:true,maxRetries:10,retryDelay:100});}catch(e){cleanup.push(String(e));}
    if(cleanup.length){result={...result,status:'blocked',passed:false,cleanupErrors:cleanup};}
  }
  result.browserProcess={exitCode:browser?.exitCode,signalCode:browser?.signalCode,stderr:browserStderr,protocolTrace};
  if(result.nativeRegistry&&!result.nativeRegistry.complete)result={...result,status:'blocked',passed:false};
  fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2),{flag:'wx'});return result;
}
module.exports={run,validate,styleDifferences,DEFAULT_ENV,STYLE_KEYS};
if(require.main===module)run(JSON.parse(fs.readFileSync(0,'utf8'))).then(r=>{process.stdout.write(JSON.stringify(r));if(r.status==='blocked')process.exitCode=2;else if(!r.passed)process.exitCode=1;}).catch(e=>{process.stderr.write(e.stack);process.exitCode=2;});
