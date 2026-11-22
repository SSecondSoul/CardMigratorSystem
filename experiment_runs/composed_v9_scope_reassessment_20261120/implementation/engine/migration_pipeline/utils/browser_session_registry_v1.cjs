/* Native CDP session ownership. Evidence routing, not authentication of hostile producers. */
'use strict';
class SessionRegistry {
  constructor(runId, origin, pages, pairs) {
    if(typeof runId!=='string'||!runId||!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin))throw Error('Invalid run identity');
    this.runId=runId;this.origin=origin;this.sequence=0;this.pages=pages;this.pairs=pairs;
    this.entries=[];this.events=[];this.integrityErrors=[];
  }
  register(index, contextId, targetId, sessionId, htmlSha256) {
    if(!this.pages[index]||![contextId,targetId,sessionId].every(v=>typeof v==='string'&&v)||!/^\w{64}$/.test(htmlSha256)||!/^[a-f0-9]+$/.test(htmlSha256))throw Error('Incomplete native identity');
    if(this.entries.some(e=>e.index===index||e.contextId===contextId||e.targetId===targetId||e.sessionId===sessionId))throw Error('Duplicate native identity');
    const page=this.pages[index],entry={runId:this.runId,index,page:page.name,url:this.origin+'/page/'+index,
      htmlSha256,contextId,targetId,sessionId,executionContexts:[],mainFrameId:null,identityVerified:false,
      lifecycle:'attached',contextDisposed:false,nativeObservations:[],roles:this.pairs.flatMap((p,i)=>[
        ...(p.source===page.name?[{pair:i,role:'source'}]:[]),...(p.target===page.name?[{pair:i,role:'target'}]:[])])};
    this.entries.push(entry);return entry;
  }
  bySession(sessionId) {return this.entries.find(e=>e.sessionId===sessionId);}
  verify(entry, info, frame) {
    if(!this.entries.includes(entry)||info.type!=='page'||info.targetId!==entry.targetId||info.browserContextId!==entry.contextId||info.url!==entry.url||frame.url!==entry.url||frame.parentId||!frame.id)throw Error('Native target/frame identity mismatch');
    entry.nativeObservations.push({targetInfo:structuredClone(info),mainFrame:structuredClone(frame)});
    entry.mainFrameId=frame.id;entry.identityVerified=true;entry.lifecycle='verified';
  }
  contextCreated(sessionId, context) {
    const entry=this.bySession(sessionId);
    if(!entry||!Number.isInteger(context.id)) {this.integrityErrors.push('Unknown execution context owner');return;}
    entry.executionContexts.push({id:context.id,origin:context.origin,frameId:context.auxData?.frameId||null,isDefault:context.auxData?.isDefault===true});
  }
  diagnostic(kind, sessionId, details) {
    const entry=this.bySession(sessionId),contextId=details.executionContextId;
    const reasons=[];
    if(!entry)reasons.push('unknown_session');
    if(entry&&entry.lifecycle==='disposed')reasons.push('event_after_context_disposal');
    if(entry&&contextId!==undefined&&!entry.executionContexts.some(c=>c.id===contextId))reasons.push('unknown_execution_context');
    // Stack text never chooses the owner; only a conflicting URL makes evidence suspect.
    const frames=details.stackTrace?.callFrames||details.exception?.stackTrace?.callFrames||[];
    const urls=[details.url,details.log?.url,...frames.map(f=>f.url)].filter(Boolean);
    if(entry&&urls.some(u=>/^https?:/.test(u)&&u!==entry.url))reasons.push('foreign_document_url');
    const event={sequence:++this.sequence,kind,sessionId:sessionId||null,
      owner:entry?{runId:entry.runId,page:entry.page,index:entry.index,targetId:entry.targetId,contextId:entry.contextId,sessionId:entry.sessionId}:null,
      attribution:reasons.length?'unverified':'native_session',reasons,details};
    this.events.push(event);return event;
  }
  allows(sessionId, request) {
    const entry=this.bySession(sessionId);
    return !!entry&&entry.lifecycle!=='disposed'&&request.method==='GET'&&request.url===entry.url;
  }
  eventsFor(entry) {return this.events.filter(e=>e.owner?.sessionId===entry.sessionId);}
  clean(entry) {return entry.identityVerified&&this.eventsFor(entry).length===0;}
  disposed(entry) {entry.contextDisposed=true;entry.lifecycle='disposed';}
  snapshot() {
    const identities=this.entries.length===this.pages.length&&this.entries.every(e=>e.identityVerified&&e.contextDisposed);
    return {runId:this.runId,origin:this.origin,entries:this.entries,events:this.events,
      integrityErrors:this.integrityErrors,identitiesComplete:identities,complete:identities&&this.integrityErrors.length===0&&this.events.every(e=>e.attribution==='native_session'),
      isolationPolicy:'fresh_browser_context_per_page',storagePersistedAcrossPages:false};
  }
}
module.exports={SessionRegistry};
