import test from 'node:test'
import assert from 'node:assert/strict'
import { Api, ApiError, errorText } from './api.ts'
import type { Submission } from './types.ts'

const token = 'test-only-workbench-write-token'
const id = 'a'.repeat(32)
function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }) }
function submission(): Submission { return { key: 'fixed-test-idempotency-key', draft: { name: '浏览器联调', filename: 'Smoke.vue', source: '<template><div /></template>', profile: 'repairable', rounds: 3 } } }

test('default fetch keeps the browser global receiver for startup queries', async context => {
  const paths: string[] = []
  context.mock.method(globalThis, 'fetch', async function (this: unknown, path: RequestInfo | URL) {
    if (this !== globalThis) throw new TypeError('Illegal invocation')
    paths.push(String(path))
    if (path === '/health/ready') return response({ status: 'not_ready' }, 503)
    if (path === '/api/v1/configurations') return response({ mode: 'development_stub', production_ready: false })
    return response({ status: 'live' })
  })
  const api = new Api()
  const [live, ready, configuration] = await Promise.all([api.live(), api.ready(), api.configurations()])
  assert.equal(live.status, 'live')
  assert.equal(ready.status, 'not_ready')
  assert.equal(configuration.mode, 'development_stub')
  assert.equal(configuration.production_ready, false)
  assert.equal(paths.length, 3)
})
test('receiver-sensitive fetch also supports writes and artifact downloads', async () => {
  const api = new Api((async function (this: unknown, path: RequestInfo | URL) {
    assert.equal(this, globalThis)
    if (String(path).endsWith('/artifact')) return new Response('development fixture')
    return response({})
  }) as typeof fetch)
  await api.cancel(id, token)
  assert.equal(await (await api.artifact(id)).text(), 'development fixture')
})

test('healthy and not-ready are separate read responses, without write token headers', async () => {
  const calls: [string, RequestInit | undefined][] = []
  const api = new Api((async (path, init) => { calls.push([String(path), init]); return response({ status: 'not_ready' }, 503) }) as typeof fetch)
  assert.equal((await api.ready()).status, 'not_ready')
  assert.equal(calls[0]?.[1]?.headers, undefined)
  assert.equal(calls[0]?.[1]?.credentials, 'same-origin')
  assert.equal(calls[0]?.[1]?.redirect, 'error')
})
test('run selection only queries, and unsafe IDs never reach fetch', async () => {
  const paths: string[] = []
  const api = new Api((async path => { paths.push(String(path)); return response({}) }) as typeof fetch)
  await api.run(id); await api.report(id); await api.events(id, 0)
  assert.equal(paths.length, 3)
  await assert.rejects(async () => api.run('../outside'))
  assert.equal(paths.length, 3)
})
test('three-step submission uses local POSTs and explicit run idempotency key', async () => {
  const calls: [string, RequestInit | undefined][] = []
  const api = new Api((async (path, init) => {
    calls.push([String(path), init])
    return response(calls.length === 1 ? { input_id: id } : calls.length === 2 ? { task_id: id } : { run_id: id })
  }) as typeof fetch)
  const pending = submission()
  assert.equal(await api.submit(pending, token), id)
  assert.equal(pending.inputId, id); assert.equal(pending.taskId, id)
  assert.ok(calls.every(([path, init]) => path.startsWith('/api/v1/') && init?.method === 'POST'))
  assert.equal((calls[2]?.[1]?.headers as Record<string, string>)['Idempotency-Key'], pending.key)
  assert.equal((calls[2]?.[1]?.headers as Record<string, string>)['X-Cardmig-Token'], token)
  assert.ok(calls.every(([, init]) => !String(init?.body).includes(token)))
})
test('unknown enqueue response is not auto-retried; explicit continuation keeps known IDs and key', async () => {
  const calls: [string, RequestInit | undefined][] = []
  let fail = true
  const api = new Api((async (path, init) => {
    calls.push([String(path), init])
    if (calls.length === 1) return response({ input_id: id })
    if (calls.length === 2) return response({ task_id: id })
    if (fail) throw new Error('connection dropped')
    return response({ run_id: id })
  }) as typeof fetch)
  const pending = submission()
  await assert.rejects(api.submit(pending, token), (error: unknown) => error instanceof ApiError && error.code === 'network_unavailable')
  assert.equal(calls.length, 3)
  fail = false
  await api.submit(pending, token)
  assert.equal(calls.length, 4)
  assert.equal(calls[2]?.[0], calls[3]?.[0])
  assert.equal((calls[2]?.[1]?.headers as Record<string, string>)['Idempotency-Key'], (calls[3]?.[1]?.headers as Record<string, string>)['Idempotency-Key'])
})
test('invalid write token never sends a request', async () => {
  const api = new Api((async () => { throw new Error('must not call') }) as typeof fetch)
  await assert.rejects(api.submit(submission(), 'short'), /本地令牌/)
})
test('API error shows code/request id, not raw server traceback or echoed secret', async () => {
  const api = new Api((async () => response({ error: { code: 'write_token_required', request_id: id, traceback: token } }, 403)) as typeof fetch)
  try { await api.cancel(id, token); assert.fail('must reject') }
  catch (error) { assert.ok(errorText(error).includes('write_token_required')); assert.ok(!errorText(error).includes(token)) }
})
test('report audit failures block artifact download instead of saving error JSON as San', async () => {
  const api = new Api((async () => response({ error: { code: 'report_final_revision_not_accepted' } }, 409)) as typeof fetch)
  await assert.rejects(api.artifact(id), (error: unknown) => error instanceof ApiError && error.code === 'report_final_revision_not_accepted')
})
test('cancel/resume require explicit POST; read queries never trigger them', async () => {
  const calls: RequestInit[] = []
  const api = new Api((async (_path, init) => { calls.push(init ?? {}); return response({}) }) as typeof fetch)
  await api.run(id); await api.cancel(id, token); await api.resume(id, token)
  assert.equal(calls[0]?.method, undefined)
  assert.equal(calls[1]?.method, 'POST'); assert.equal(calls[2]?.method, 'POST')
})

test('SSM listing/report/download use only same-origin reads without a write token', async () => {
  const calls: [string, RequestInit | undefined][] = []
  const api = new Api((async (path, init) => { calls.push([String(path), init]); return response({}) }) as typeof fetch)
  await api.extractions('bounded_cursor')
  await api.extractionReport(id)
  await api.extractionArtifact(id)
  assert.deepEqual(calls.map(([path]) => path), [
    '/api/v1/ssm-extractions?limit=10&before=bounded_cursor',
    `/api/v1/ssm-extractions/${id}/report`, `/api/v1/ssm-extractions/${id}/artifact`,
  ])
  assert.ok(calls.every(([, init]) => init?.method === undefined && init?.headers === undefined && init?.credentials === 'same-origin'))
  await assert.rejects(async () => api.extractionReport('../outside'))
  await assert.rejects(async () => api.extractionArtifact('../outside'))
  assert.equal(calls.length, 3)
})
test('SSM download audit errors never become a successful JSON artifact', async () => {
  const api = new Api((async () => response({ error: { code: 'ssm_request_hash_mismatch' } }, 409)) as typeof fetch)
  await assert.rejects(api.extractionArtifact(id), (error: unknown) => error instanceof ApiError && error.code === 'ssm_request_hash_mismatch')
})
