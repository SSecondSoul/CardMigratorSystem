import test from 'node:test'
import assert from 'node:assert/strict'
import {filterMigrations,phaseItems,percent,numeric,userMigrationDraft,validateMigrationDraft,evidenceDifferences,type MigrationDraft,type MigrationReport} from './migration.ts'
import {MigrationApi} from './migration-api.ts'
import {ApiError} from './api.ts'
const id='a'.repeat(32),token='disposable-ui-write-token-24-chars'
const draft=():MigrationDraft=>({name:'Card',filename:'Card.vue',source:'<template><p>test</p></template>',strategy:'ssm',rounds:3,propsText:'{}',actionsText:'[]',trusted:true,confirmed:true})
const response=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}})

test('missing or invalid metrics display unknown, never a fabricated zero or perfect score',()=>{
  assert.equal(percent(undefined),'—');assert.equal(percent(null),'—');assert.equal(percent(NaN),'—')
  assert.equal(numeric(undefined),'—');assert.equal(percent(0),'0.0%');assert.equal(percent(.978),'97.8%')
})
test('local search combines filename, task name, ID and status without mutating records',()=>{
  const rows=[{migration_id:id,name:'搜索卡片',filename:'SearchCard.vue',status:'failed',stage:'report',stop_reason:'budget',created_at:1}]
  assert.equal(filterMigrations(rows,'SEARCH','failed').length,1)
  assert.equal(filterMigrations(rows,'搜索','finished').length,0)
  assert.equal(filterMigrations(rows,'missing','').length,0);assert.equal(rows.length,1)
})
test('no report does not manufacture completed pipeline phases',()=>{
  assert.ok(phaseItems(null).every(p=>p.state==='waiting'))
})
test('DOM and style rows preserve raw positions and values without inventing severity',()=>{
  assert.deepEqual(evidenceDifferences(null),[])
  const input={dimensions:{structure:'fail'},dom_differences:[{path:'root.1',expected:'span|',actual:'button|'}],styles:{differences:[{path:'root.2',property:'marginLeft',source:'2px',target:null}]}}
  const before=JSON.stringify(input),rows=evidenceDifferences(input)
  assert.equal(rows.length,2);assert.equal(rows[0].source,'span|');assert.equal(rows[1].source,'2px');assert.equal(rows[1].target,'缺失')
  assert.equal(JSON.stringify(input),before);assert.ok(!('severity' in rows[0]))
})
test('a stopped failed migration does not paint every step green',()=>{
  const report:MigrationReport={migration_id:id,status:'failed',stage:'report',stop_reason:'repair_budget_exhausted',request_sha256:'f'.repeat(64),state:{decisions:[{round:1,accepted:false,reason:'regression',previous:'a',candidate:'b'}]},request:{max_repair_rounds:3},files:[{relative_path:'migrations/x/ssm.json',sha256:'a',kind:'ssm'},{relative_path:'migrations/x/revisions/0.san',sha256:'b',kind:'san'}],assessment:{dimensions:{static:'fail',structure:'fail',visual:'pass'}},final_artifact:null,usage:{known_total_tokens:0,complete:true},model_calls_started:0,unknown_calls:0,manual_feedback:[]}
  const phases=phaseItems(report)
  assert.equal(phases[0].state,'done');assert.equal(phases[3].state,'failed');assert.equal(phases[4].state,'done');assert.equal(phases[5].state,'failed')
  report.status='running';report.stage='extract';report.files=[];report.assessment=null;report.state={}
  assert.equal(phaseItems(report)[0].state,'done');assert.equal(phaseItems(report)[1].state,'running')
})
test('migration draft requires explicit trust, fee authorization and valid JSON shapes',()=>{
  assert.deepEqual(validateMigrationDraft(draft()),{props:{},actions:[]})
  for(const mutation of [{trusted:false},{confirmed:false},{rounds:4},{strategy:'invented'},{propsText:'[]'},{propsText:'null'},{actionsText:'{}'},{filename:'../Card.vue'},{source:' '},{source:'文'.repeat(100000)}])assert.throws(()=>validateMigrationDraft({...draft(),...mutation}))
})
test('user submission fixes SSM strategy and retains backend fields without mutating experiment drafts',()=>{
  for(const strategy of ['ssm','ssm_no_repair','direct']) {
    const original={...draft(),strategy,trusted:false,confirmed:false},before=JSON.stringify(original)
    const submitted=userMigrationDraft(original)
    assert.equal(submitted.strategy,'ssm');assert.equal(submitted.trusted,true);assert.equal(submitted.confirmed,true)
    assert.deepEqual(validateMigrationDraft(submitted),{props:{},actions:[]})
    assert.equal(JSON.stringify(original),before)
    assert.deepEqual(validateMigrationDraft({...draft(),strategy}),{props:{},actions:[]})
  }
  for(const mutation of [{source:''},{propsText:'[]'},{actionsText:'{}'},{rounds:4}])assert.throws(()=>validateMigrationDraft(userMigrationDraft({...draft(),...mutation})))
})

test('migration reads send no secret or write headers; default native fetch has the correct receiver',async context=>{
  context.mock.method(globalThis,'fetch',async function(this:unknown,url:RequestInfo|URL,init?:RequestInit){assert.equal(this,globalThis);assert.equal(String(url),'/api/v1/migrations');assert.deepEqual(init?.headers,{});assert.equal(init?.credentials,'same-origin');assert.equal(init?.redirect,'error');return response({items:[]})})
  assert.deepEqual(await new MigrationApi().get('/api/v1/migrations'),{items:[]})
})
test('a migration write requires a valid local token and preserves its idempotency key',async()=>{
  const calls:RequestInit[]=[]
  const api=new MigrationApi((async function(this:unknown,_url:RequestInfo|URL,init:RequestInit){assert.equal(this,globalThis);calls.push(init);return response({migration_id:id},202)}) as typeof fetch)
  await assert.rejects(api.post('/api/v1/migrations',{},'short'));assert.equal(calls.length,0)
  await api.post('/api/v1/migrations',{input_id:id},token,'fixed-key')
  assert.equal(calls.length,1);assert.equal(calls[0].method,'POST');assert.equal((calls[0].headers as Record<string,string>)['Idempotency-Key'],'fixed-key')
})
test('unknown write result is not retried automatically',async()=>{
  let calls=0;const api=new MigrationApi(async()=>{calls++;throw new TypeError('network failure')})
  await assert.rejects(api.post('/api/v1/migrations',{},token),(error:unknown)=>error instanceof ApiError&&error.code==='network_unavailable')
  assert.equal(calls,1)
})

test('browser session is established once and writes use CSRF, never the script token',async()=>{
  const calls:{path:string;init?:RequestInit}[]=[],csrf='s'.repeat(43)
  const api=new MigrationApi(async(path,init)=>{
    calls.push({path:String(path),init})
    return String(path).endsWith('/browser-session')?response({csrf_token:csrf,expires_in:28800}):response({migration_id:id},202)
  })
  await Promise.all([api.session(),api.session()])
  await api.post('/api/v1/migrations',{input_id:id},undefined,'browser-key')
  assert.equal(calls.length,2);assert.equal(calls[0].init?.credentials,'same-origin')
  assert.equal((calls[0].init?.headers as Record<string,string>)['X-Cardmig-Session'],'bootstrap')
  const headers=calls[1].init?.headers as Record<string,string>
  assert.equal(headers['X-Cardmig-CSRF'],csrf);assert.equal(headers['Idempotency-Key'],'browser-key')
  assert.ok(!('X-Cardmig-Token' in headers))
  await api.get('/api/v1/migrations');assert.deepEqual(calls[2].init?.headers,{})
})

test('failed or malformed session never sends a write and can be explicitly established later',async()=>{
  let calls=0
  const api=new MigrationApi(async(_path,init)=>{
    assert.equal(init?.method,'GET');calls++
    return calls===1?response({csrf_token:'invalid',expires_in:28800}):response({csrf_token:'x'.repeat(43),expires_in:28800})
  })
  await assert.rejects(api.post('/api/v1/migrations',{}),(e:unknown)=>e instanceof ApiError&&e.code==='invalid_browser_session')
  assert.equal(calls,1);await api.session();assert.equal(calls,2)
})

test('expired browser auth clears its cache but never replays a rejected write',async()=>{
  let sessions=0,writes=0
  const api=new MigrationApi(async(path)=>{
    if(String(path).endsWith('/browser-session')){sessions++;return response({csrf_token:'x'.repeat(43),expires_in:28800})}
    writes++;return response({error:{code:'browser_session_required'}},403)
  })
  await assert.rejects(api.post('/api/v1/migrations',{}))
  assert.equal(writes,1);assert.equal(sessions,1)
  await api.session();assert.equal(sessions,2);assert.equal(writes,1)
})

test('ambiguous browser write is never retried or given a fresh idempotency key automatically',async()=>{
  let writes=0
  const api=new MigrationApi(async(path)=>{
    if(String(path).endsWith('/browser-session'))return response({csrf_token:'x'.repeat(43),expires_in:28800})
    writes++;throw new TypeError('connection lost')
  })
  await assert.rejects(api.post('/api/v1/migrations',{},undefined,'fixed-browser-key'))
  assert.equal(writes,1)
})
test('unsafe task IDs never reach the artifact network boundary and error responses are not code downloads',async()=>{
  let calls=0;const api=new MigrationApi(async()=>{calls++;return response({error:{code:'failed'}},404)})
  await assert.rejects(api.file('../unsafe','x'));assert.equal(calls,0)
  await assert.rejects(api.file(id,'migrations/'+id+'/revisions/0.san'));assert.equal(calls,1)
})
test('artifact paths are encoded and file reads never carry the local write token',async()=>{
  const api=new MigrationApi(async(url,init)=>{assert.ok(String(url).includes('path=migrations%2F'));assert.equal(init?.headers,undefined);assert.equal(init?.redirect,'error');return new Response('safe text')})
  assert.equal(await (await api.file(id,'migrations/'+id+'/revisions/0.san')).text(),'safe text')
})
