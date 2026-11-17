import test from 'node:test'
import assert from 'node:assert/strict'
import { canDownload, decodeSource, idFromHash, runId, validToken, validateDraft } from './model.ts'
import type { Draft, Report, RunInfo } from './types.ts'

const draft: Draft = { name: '界面验证', filename: 'Smoke.vue', source: '<template><div /></template>', profile: 'repairable', rounds: 3 }
test('valid draft is bounded to development configuration', () => { assert.doesNotThrow(() => validateDraft(draft)) })
test('invalid paths, empty source, oversize UTF8 and invalid budget are rejected', () => {
  for (const value of [{ ...draft, filename: '../Smoke.vue' }, { ...draft, source: ' ' },
    { ...draft, source: '中'.repeat(90000) }, { ...draft, rounds: 4 }, { ...draft, rounds: NaN }]) assert.throws(() => validateDraft(value))
})
test('UTF8 source file decodes without executing code', async () => {
  const data = new TextEncoder().encode(draft.source)
  assert.equal(await decodeSource({ name: 'Smoke.vue', size: data.byteLength, arrayBuffer: async () => data.buffer }), draft.source)
})
test('oversize or malformed UTF8 file is rejected', async () => {
  await assert.rejects(decodeSource({ name: 'Smoke.vue', size: 262145, arrayBuffer: async () => new ArrayBuffer(0) }))
  await assert.rejects(decodeSource({ name: 'Smoke.vue', size: 2, arrayBuffer: async () => new Uint8Array([0xff, 0xff]).buffer }))
})
test('hash restores only a run ID, not token, code or arbitrary navigation', () => {
  const id = 'a'.repeat(32)
  assert.equal(idFromHash('#run=' + id), id)
  assert.equal(idFromHash('#run=../../bad'), null)
  assert.equal(idFromHash('#token=not-read'), null)
  assert.throws(() => runId('http://elsewhere/'))
})
test('local write token is distinct from empty/Unicode/short input', () => {
  assert.equal(validToken('test-only-workbench-write-token'), true)
  for (const value of ['', 'short', '中'.repeat(30), ' '.repeat(30)]) assert.equal(validToken(value), false)
})
test('download requires matching current and audited accepted revision', () => {
  const run = { run_id: 'a'.repeat(32), status: 'finished', request_sha256: 'hash', final_revision_id: 'accepted' } as RunInfo
  const report = { run_id: run.run_id, status: 'finished', request_sha256: 'hash', final_revision_id: 'accepted',
    fixture_audit: { status: 'verified_development_ledger_not_migration_evidence', accepted_revision_id: 'accepted' } } as Report
  assert.equal(canDownload(run, report), true)
  assert.equal(canDownload(null, report), false)
  assert.equal(canDownload(run, { ...report, request_sha256: 'other' }), false)
  assert.equal(canDownload(run, { ...report, final_revision_id: 'rejected' }), false)
  assert.equal(canDownload({ ...run, status: 'running' }, report), false)
})
