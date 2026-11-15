/* Local headless Edge + CDP, isolated profile; no dependency installation. */
'use strict';
const fs=require('fs'),path=require('path'),os=require('os'),http=require('http'),crypto=require('crypto');
const {spawn}=require('child_process');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
async function run(input){
 const executable=input.browserExecutable||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
 const executableSha=sha(executable),profile=fs.mkdtempSync(path.join(os.tmpdir(),'cardmig-browser-audit-'));
 const fixture=fs.readFileSync(path.join(__dirname,'audit_async_watcher_browser_v1.js'),'utf8');
 const requests=[],exceptions=[],blockedRequests=[],protocolErrors=[];
 const html='<!doctype html><meta charset="utf-8"><title>Isolated watcher scope audit</title><div id="realms"></div>'+
  '<script src="/fixture.js"></script><script>fetch("/payload.json").then(r=>r.json()).then(runBrowserWatcherAudit)'+
  '.then(r=>{window.__auditResult=r;}).catch(e=>{window.__auditFailure=String(e.stack||e);});</script>';
 const routes={'/': ['text/html',html],'/realm.html':['text/html','<!doctype html><meta charset="utf-8"><title>Isolated realm</title>'],
  '/fixture.js':['application/javascript',fixture],'/payload.json':['application/json',JSON.stringify(input)]};
 const server=http.createServer((req,res)=>{
  requests.push({method:req.method,path:req.url});const route=routes[req.url];
  res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');
  if(req.method!=='GET'||!route){res.writeHead(req.url==='/favicon.ico'?204:404);res.end();return;}
  res.writeHead(200,{'Content-Type':route[0]+'; charset=utf-8'});res.end(route[1]);
 });
 let browser,ws,browserVersion,serverPort,output,cleanupError=null,stderr='',stage='initial',browserExit=null;
 const pending=new Map();let nextId=0;
 const send=(method,params={},sessionId)=>new Promise((resolve,reject)=>{
  const id=++nextId;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));
 });
 try{
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  serverPort=server.address().port;const origin='http://127.0.0.1:'+serverPort;
  browser=spawn(executable,['--headless=new','--remote-debugging-port=0','--user-data-dir='+profile,
   '--no-first-run','--no-default-browser-check','--disable-extensions','--disable-background-networking',
   '--disable-component-update','--disable-sync','about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
  stage='spawned';let spawnError=null;browser.on('error',e=>{spawnError=e;});browser.stderr.on('data',s=>{stderr+=String(s);});
  browser.once('exit',(code,signal)=>{browserExit={code,signal};});
  const active=path.join(profile,'DevToolsActivePort'),deadline=Date.now()+30000;
  while(!fs.existsSync(active)){
   if(spawnError)throw spawnError;
   if(browser.exitCode!==null)throw Error('Isolated browser exited: '+browser.exitCode+' '+stderr);
   if(Date.now()>deadline)throw Error('Timed out waiting for isolated DevTools port: '+stderr);
   await pause(50);
  }
  const [port,endpoint]=fs.readFileSync(active,'utf8').trim().split(/\r?\n/);
  if(!/^\d+$/.test(port)||!endpoint.startsWith('/devtools/browser/'))throw Error('Unexpected private DevTools endpoint');
  ws=new WebSocket('ws://127.0.0.1:'+port+endpoint);
  await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});
  ws.addEventListener('message',event=>{
   const m=JSON.parse(event.data);
   if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}return;}
   if(m.method==='Runtime.exceptionThrown'){
    const d=m.params.exceptionDetails;exceptions.push({text:d.text,description:d.exception?.description||'',url:d.url||'',line:d.lineNumber,column:d.columnNumber});
   }
   if(m.method==='Fetch.requestPaused'){
    const url=m.params.request.url,allowed=url.startsWith(origin+'/');
    if(!allowed)blockedRequests.push(url);
    send(allowed?'Fetch.continueRequest':'Fetch.failRequest',allowed?{requestId:m.params.requestId}:
      {requestId:m.params.requestId,errorReason:'BlockedByClient'},m.sessionId).catch(e=>protocolErrors.push(String(e)));
   }
  });
  ws.addEventListener('close',()=>{for(const p of pending.values())p.reject(Error('CDP connection closed'));pending.clear();});
  stage='browser-version';browserVersion=await send('Browser.getVersion');
  stage='create-target';
  const {targetId}=await send('Target.createTarget',{url:'about:blank'});
  const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
  stage='enable-page';await send('Runtime.enable',{},sessionId);await send('Page.enable',{},sessionId);
  await send('Fetch.enable',{patterns:[{urlPattern:'*'}]},sessionId);
  stage='navigate';await send('Page.navigate',{url:origin+'/'},sessionId);stage='fixture-running';
  const stop=Date.now()+90000;
  while(true){
   const r=await send('Runtime.evaluate',{expression:'JSON.stringify({result:window.__auditResult||null,failure:window.__auditFailure||null})',returnByValue:true},sessionId);
   if(r.exceptionDetails)throw Error('CDP evaluation failure: '+JSON.stringify(r.exceptionDetails));
   const state=JSON.parse(r.result.value);
   if(state.failure)throw Error('Browser fixture failed: '+state.failure);
   if(state.result){output=state.result;break;}
   if(Date.now()>stop)throw Error('Timed out waiting for browser audit result');
   await pause(100);
  }
  if(sha(executable)!==executableSha)throw Error('Browser executable changed during run');
  return {observations:output,browser:{...browserVersion,executable,executable_sha256:executableSha,
    executable_unchanged_during_run:true,profile_isolated:true,headless:true},
   transport:{loopback_only:true,port_ephemeral:true,served_routes:Object.keys(routes),requests,blockedRequests,protocolErrors},
   browser_exceptions:exceptions,model_requests:0,production_integration_enabled:false};
 }catch(e){
  e.message+='\nLaunch diagnostics: '+JSON.stringify({stage,browserVersion,browserExit,stderr,exceptions,protocolErrors});throw e;
 }finally{
  if(ws?.readyState===WebSocket.OPEN){try{await send('Browser.close');}catch(_e){}ws.close();}
  if(browser&&browser.exitCode===null){await Promise.race([new Promise(r=>browser.once('exit',r)),pause(3000)]);if(browser.exitCode===null)browser.kill();}
  await new Promise(r=>server.close(r));
  // Only remove this process's newly-created, explicitly validated temp profile.
  const resolved=path.resolve(profile),tempRoot=path.resolve(os.tmpdir())+path.sep;
  if(!resolved.startsWith(tempRoot)||!path.basename(resolved).startsWith('cardmig-browser-audit-'))throw Error('Refusing unsafe profile cleanup');
  try{fs.rmSync(resolved,{recursive:true,force:false,maxRetries:10,retryDelay:100});}catch(e){cleanupError=String(e);}
  if(cleanupError)process.stderr.write('Isolated temporary profile cleanup failed: '+cleanupError+'\n');
 }
}
if(require.main===module)run(JSON.parse(fs.readFileSync(0,'utf8'))).then(r=>process.stdout.write(JSON.stringify(r)))
 .catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
module.exports={run};
