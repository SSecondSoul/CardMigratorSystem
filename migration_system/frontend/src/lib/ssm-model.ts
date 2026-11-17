import type { ExtractionReport } from './types.ts'

export const extractionNames: Record<string, string> = {
  prepared: '已准备，未提取', started: '提取已启动', received: '收据已登记，待归档',
  completed: '提取图已完成', blocked: '已阻断', review_required: '需要人工复核',
}
export const evaluationNames: Record<string, string> = {
  pass: '源提取证据已核对', not_run: '未执行', fail: '源检查失败', unsupported: '暂不支持',
  execution_error: '设施执行异常', blocked: '已阻断', unknown: '未知，需复核',
}
export function extractionIdFromHash(hash: string): string | null {
  const id = new URLSearchParams(hash.replace(/^#/, '')).get('ssm')
  return id && /^[0-9a-f]{32}$/.test(id) ? id : null
}
export function extractionHash(hash: string, id: string): string {
  if (!/^[0-9a-f]{32}$/.test(id)) throw new Error('提取 ID 格式无效。')
  const params = new URLSearchParams(hash.replace(/^#/, ''))
  params.set('ssm', id)
  return params.toString()
}
export function canDownloadSsm(report: ExtractionReport | null): boolean {
  return !!report && report.status === 'completed' && report.receipt?.status === 'completed'
    && report.contract_evaluation.status === 'pass' && report.migration_quality_status === 'not_run'
    && report.production_ready === false && report.actual_model_calls === 0
    && report.langsmith_uploaded === false && report.files.some(file => file.kind === 'ssm')
}
export function projectionExplanation(report: ExtractionReport): string {
  if (report.contract_projection.status === 'partial_evaluation_only'
      && report.contract_projection.reason === 'historical_request_snapshot_missing_no_backfill') {
    return '历史请求未冻结完整契约快照：仅提供源阶段评估，完整 P1 报告不可用。这不代表提取失败，也不会补写历史请求。'
  }
  return '源阶段报告独立于开发夹具；SSM 不充当 San 版本。其余五项目标迁移检查尚未执行。'
}
