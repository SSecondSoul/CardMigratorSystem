/* Opt-in trusted self-contained HTML pair evaluator. Not a source compiler,
 * sandbox for hostile code, interaction oracle, or production batch gate.
 * Node >=22 native WebSocket; local Edge only. No npm/CDN/model dependencies.
 */
'use strict';
const fs=require('fs'),path=require('path'),os=require('os'),http=require('http'),crypto=require('crypto');
const {spawn}=require('child_process');
const {decodePNG,encodePNG,compareRGBA}=require('./utils/browser_pixel_metrics_v1.cjs');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const ENV={width:640,height:480,deviceScaleFactor:1,locale:'zh-CN',timezone:'Asia/Shanghai',theme:'light',
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
  return input;
}
function styleDifferences(a,b){
  const changes=[];for(const key of new Set([...Object.keys(a),...Object.keys(b)])){
    if(!a[key]||!b[key]){changes.push({key,property:'mapping',source:a[key]||null,target:b[key]||null});continue;}
    for(const property of ['rect',...STYLE_KEYS])if(JSON.stringify(a[key][property])!==JSON.stringify(b[key][property]))changes.push({key,property,source:a[key][property],target:b[key][property]});
  }return changes;
}
async function run(input){
  validate(input);const output=path.resolve(input.outputDir||'');if(!input.outputDir||fs.existsSync(output))throw Error('New explicit outputDir required; never overwrite evidence');
  const executable=input.browserExecutable||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
  const executableSha=sha(fs.readFileSync(executable)); // Fail, never skip-as-pass.
  const profile=fs.mkdtempSync(path.join(os.tmpdir(),'cardmig-pixel-v1-'));
  fs.mkdirSync(output,{recursive:true});fs.writeFileSync(path.join(output,'input.json'),JSON.stringify(input,null,2),{flag:'wx'});
  const pages=new Map(input.pages.map((p,i)=>['/page/'+i,p.html]));pages.set('/','<!doctype html><meta charset="utf-8"><link rel="icon" href="data:,">');
  const requests=[],blocked=[],protocolErrors=[],exceptions=[],consoleErrors=[];
  const server=http.createServer((req,res)=>{requests.push({method:req.method,path:req.url});res.setHeader('Cache-Control','no-store');
    res.setHeader('Content-Security-Policy',"default-src 'self' data:; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; connect-src 'none'; frame-src 'none'; worker-src 'none'; object-src 'none'");
    if(req.method!=='GET'||!pages.has(req.url)){res.writeHead(404);res.end();return;}
    res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(pages.get(req.url));});
  let browser,ws,version,result,origin;const pending=new Map();let nextId=0;const commandTimeout=10000;
  const send=(method,params={},sessionId)=>new Promise((resolve,reject)=>{
    const id=++nextId,timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout '+method));},commandTimeout);
    pending.set(id,{resolve,reject,timer});try{ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));}catch(e){clearTimeout(timer);pending.delete(id);reject(e);}
  });
  try{
    await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});origin='http://127.0.0.1:'+server.address().port;
    browser=spawn(executable,['--headless=new','--remote-debugging-port=0','--user-data-dir='+profile,'--no-first-run','--no-default-browser-check',
      '--disable-extensions','--disable-background-networking','--disable-component-update','--disable-sync','--force-color-profile=srgb','--lang=zh-CN','about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
    let spawnError=null,stderr='';browser.on('error',e=>{spawnError=e;});browser.stderr.on('data',data=>{stderr+=String(data);});
    const active=path.join(profile,'DevToolsActivePort'),stop=Date.now()+30000;
    while(!fs.existsSync(active)){if(spawnError)throw spawnError;if(browser.exitCode!==null||Date.now()>stop)throw Error('Browser startup failed '+stderr);await pause(50);}
    const [port,endpoint]=fs.readFileSync(active,'utf8').trim().split(/\r?\n/);if(!/^\d+$/.test(port)||!endpoint.startsWith('/devtools/browser/'))throw Error('Invalid private endpoint');
    ws=new WebSocket('ws://127.0.0.1:'+port+endpoint);
    await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('WebSocket open timeout')),10000);ws.addEventListener('open',()=>{clearTimeout(timer);resolve();},{once:true});ws.addEventListener('error',e=>{clearTimeout(timer);reject(e);},{once:true});});
    ws.addEventListener('message',event=>{
      const m=JSON.parse(event.data);if(m.id){const p=pending.get(m.id);if(p){clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}return;}
      if(m.method==='Runtime.exceptionThrown')exceptions.push({session:m.sessionId,...m.params.exceptionDetails});
      if(m.method==='Runtime.consoleAPICalled'&&m.params.type==='error')consoleErrors.push({session:m.sessionId,...m.params});
      if(m.method==='Log.entryAdded'&&m.params.entry.level==='error')consoleErrors.push({session:m.sessionId,log:m.params.entry});
      if(m.method==='Fetch.requestPaused'){
        const u=m.params.request.url;let allowed=false;try{const url=new URL(u);allowed=url.origin===origin&&pages.has(url.pathname)&&!url.search&&m.params.request.method==='GET';}catch(_e){}
        if(!allowed)blocked.push(u);send(allowed?'Fetch.continueRequest':'Fetch.failRequest',allowed?{requestId:m.params.requestId}:{requestId:m.params.requestId,errorReason:'BlockedByClient'},m.sessionId).catch(e=>protocolErrors.push(String(e)));
      }
    });
    ws.addEventListener('close',()=>{for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('CDP connection closed'));}pending.clear();});
    version=await send('Browser.getVersion');const captures={};
    for(let index=0;index<input.pages.length;index++){
      const page=input.pages[index],start={errors:exceptions.length,console:consoleErrors.length,blocked:blocked.length};
      const {targetId}=await send('Target.createTarget',{url:'about:blank'}),{sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
      await send('Runtime.enable',{},sessionId);await send('Page.enable',{},sessionId);await send('Network.enable',{},sessionId);await send('Log.enable',{},sessionId);
      await send('Network.setCacheDisabled',{cacheDisabled:true},sessionId);await send('Network.setBypassServiceWorker',{bypass:true},sessionId);
      await send('Fetch.enable',{patterns:[{urlPattern:'*'}]},sessionId);
      await send('Emulation.setDeviceMetricsOverride',{width:ENV.width,height:ENV.height,deviceScaleFactor:ENV.deviceScaleFactor,mobile:false},sessionId);
      await send('Emulation.setLocaleOverride',{locale:ENV.locale},sessionId);await send('Emulation.setTimezoneOverride',{timezoneId:ENV.timezone},sessionId);
      await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:ENV.theme},{name:'prefers-reduced-motion',value:ENV.reducedMotion}]},sessionId);
      const init=`(()=>{const NativeDate=Date;class FixedDate extends NativeDate{constructor(...a){super(...(a.length?a:[${ENV.epoch}]));}static now(){return ${ENV.epoch};}};window.Date=FixedDate;let seed=${ENV.seed};Math.random=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;};window.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent='html{font-family:Arial;color-scheme:light}*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}';document.head.append(s);});})()`;
      await send('Page.addScriptToEvaluateOnNewDocument',{source:init},sessionId);await send('Page.navigate',{url:origin+'/page/'+index},sessionId);
      const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},sessionId);if(r.exceptionDetails)throw Error('Page evaluation failed '+JSON.stringify(r.exceptionDetails));return r.result.value;};
      const deadline=Date.now()+3000;while(!await evaluate('document.readyState === "complete" && window.__visualReady === true')){if(Date.now()>deadline)throw Error('Explicit readiness timeout '+page.name);await pause(50);}
      await evaluate('document.fonts.ready.then(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))).then(()=>true)');
      const observationExpression=`(()=>{const out={};for(const [key,selector] of Object.entries(${JSON.stringify(page.selectors)})){const nodes=document.querySelectorAll(selector);if(nodes.length!==1)throw Error('Selector must match exactly one: '+key+' ('+nodes.length+')');const n=nodes[0],s=getComputedStyle(n),r=n.getBoundingClientRect();if(r.width<=0||r.height<=0||r.x<0||r.y<0||r.right>${ENV.width}||r.bottom>${ENV.height})throw Error('Critical element outside viewport '+key);out[key]={rect:{x:r.x,y:r.y,width:r.width,height:r.height},...Object.fromEntries(${JSON.stringify(STYLE_KEYS)}.map(k=>[k,s.getPropertyValue(k)]))};}if(document.documentElement.scrollWidth>${ENV.width}||document.documentElement.scrollHeight>${ENV.height})throw Error('Viewport overflow; full-page evaluation not implemented');return {styles:out,environment:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio,theme:matchMedia('(prefers-color-scheme:light)').matches,reducedMotion:matchMedia('(prefers-reduced-motion:reduce)').matches,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,locale:Intl.DateTimeFormat().resolvedOptions().locale,time:Date.now()}};})()`;
      const observation=await evaluate(observationExpression);
      const screenshot=async()=>Buffer.from((await send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false},sessionId)).data,'base64');
      const first=await screenshot();await pause(ENV.repeatDelayMs);const second=await screenshot(),repeatObservation=await evaluate(observationExpression);
      fs.writeFileSync(path.join(output,page.name+'.png'),first,{flag:'wx'});fs.writeFileSync(path.join(output,page.name+'-repeat.png'),second,{flag:'wx'});
      const decoded=decodePNG(first),again=decodePNG(second);
      if(decoded.width!==ENV.width||decoded.height!==ENV.height)throw Error('Screenshot size differs from protocol');
      const stability=compareRGBA(decoded,again);const stable=stability.changedPixels===0&&JSON.stringify(observation)===JSON.stringify(repeatObservation);
      const clean=exceptions.length===start.errors&&consoleErrors.length===start.console&&blocked.length===start.blocked;
      captures[page.name]={...observation,htmlSha256:sha(Buffer.from(page.html)),screenshotSha256:sha(first),repeatScreenshotSha256:sha(second),stable,clean,
        repeatChangedPixels:stability.changedPixels};
      await send('Target.closeTarget',{targetId});
    }
    const comparisons=input.pairs.map((pair,index)=>{
      const a=captures[pair.source],b=captures[pair.target],metric=compareRGBA(decodePNG(fs.readFileSync(path.join(output,pair.source+'.png'))),decodePNG(fs.readFileSync(path.join(output,pair.target+'.png'))),input.thresholds);
      const diffName='diff-'+index+'.png';fs.writeFileSync(path.join(output,diffName),encodePNG(metric.width,metric.height,metric.diff),{flag:'wx'});delete metric.diff;
      const styleChanges=styleDifferences(a.styles,b.styles),eligible=a.stable&&b.stable&&a.clean&&b.clean&&protocolErrors.length===0;
      return {...pair,metrics:metric,styleChanges,diff:diffName,eligible,passed:eligible&&metric.changedPixelRatio<=input.thresholds.maxChangedPixelRatio&&metric.ssim>=input.thresholds.minSSIM&&styleChanges.length===0};
    });
    if(sha(fs.readFileSync(executable))!==executableSha)throw Error('Browser executable changed during run');
    result={schemaVersion:1,status:comparisons.every(p=>p.eligible)?'evaluated':'blocked',passed:comparisons.every(p=>p.passed),environment:ENV,thresholds:input.thresholds,
      browser:{...version,executable,executableSha256:executableSha,isolatedProfile:true,headless:true},captures,comparisons,
      transport:{requests,blocked,protocolErrors,loopbackOnly:true},exceptions,consoleErrors,
      boundary:{selfContainedHTMLOnly:true,componentCompiler:false,productionIntegrated:false,interactionEquivalence:false,fullPage:false,fontBinaryPinned:false,modelCalls:0,historicalScoresChanged:false}};
  }catch(error){
    result={schemaVersion:1,status:'blocked',passed:false,error:String(error.stack||error),environment:ENV,browser:version||null,exceptions,consoleErrors,blocked,protocolErrors};
  }finally{
    const cleanup=[];
    if(ws?.readyState===WebSocket.OPEN){try{await send('Browser.close');}catch(e){cleanup.push(String(e));}ws.close();}
    if(browser&&browser.exitCode===null){await Promise.race([new Promise(r=>browser.once('exit',r)),pause(3000)]);if(browser.exitCode===null){browser.kill();await Promise.race([new Promise(r=>browser.once('exit',r)),pause(2000)]);}}
    await new Promise(resolve=>server.close(resolve));
    const resolved=path.resolve(profile);if(!resolved.startsWith(path.resolve(os.tmpdir())+path.sep)||!path.basename(resolved).startsWith('cardmig-pixel-v1-'))throw Error('Unsafe profile cleanup target');
    try{fs.rmSync(resolved,{recursive:true,maxRetries:10,retryDelay:100});}catch(e){cleanup.push(String(e));}
    if(cleanup.length){result={...result,status:'blocked',passed:false,cleanupErrors:cleanup};}
  }
  fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2),{flag:'wx'});return result;
}
module.exports={run,validate,styleDifferences,ENV,STYLE_KEYS};
if(require.main===module)run(JSON.parse(fs.readFileSync(0,'utf8'))).then(r=>{process.stdout.write(JSON.stringify(r));if(r.status==='blocked')process.exitCode=2;}).catch(e=>{process.stderr.write(e.stack);process.exitCode=2;});
