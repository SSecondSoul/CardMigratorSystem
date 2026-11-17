import test from 'node:test'
import assert from 'node:assert/strict'
import { canDownloadSsm, extractionHash, extractionIdFromHash, projectionExplanation } from './ssm-model.ts'
import { idFromHash } from './model.ts'
import type { ExtractionReport } from './types.ts'

const id = 'b'.repeat(32)
function report(): ExtractionReport {
  return { status: 'completed', receipt: { status: 'completed' }, contract_evaluation: { status: 'pass' },
    migration_quality_status: 'not_run', production_ready: false, actual_model_calls: 0, langsmith_uploaded: false,
    files: [{ kind: 'ssm' }], contract_report: null,
    contract_projection: { status: 'partial_evaluation_only', reason: 'historical_request_snapshot_missing_no_backfill' } } as ExtractionReport
}
test('SSM selection validates id and preserves independent fixture run selection', () => {
  const hash = extractionHash('#run=' + 'a'.repeat(32), id)
  assert.equal(extractionIdFromHash(hash), id)
  assert.equal(idFromHash(hash), 'a'.repeat(32))
  assert.equal(extractionIdFromHash('#ssm=../outside'), null)
  assert.equal(extractionIdFromHash('#run=' + id), null)
  assert.throws(() => extractionHash('', '../outside'))
})
test('legacy evaluation-only mapping is not treated as extraction failure or fabricated full report', () => {
  assert.match(projectionExplanation(report()), /历史请求未冻结/)
  assert.match(projectionExplanation(report()), /不代表提取失败/)
  assert.equal(canDownloadSsm(report()), true)
})
test('SSM download requires completed audited source facts but never migration pass', () => {
  assert.equal(canDownloadSsm(null), false)
  for (const changed of [
    { status: 'received' }, { status: 'review_required' }, { receipt: null }, { files: [] },
    { contract_evaluation: { status: 'blocked' } }, { migration_quality_status: 'pass' },
    { actual_model_calls: 1 }, { production_ready: true }, { langsmith_uploaded: true },
  ]) assert.equal(canDownloadSsm({ ...report(), ...changed } as ExtractionReport), false)
})
