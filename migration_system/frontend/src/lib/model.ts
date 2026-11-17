import type { Draft, Report, RunInfo, RunStatus } from './types.ts'

export const statusNames: Record<RunStatus, string> = {
  queued: '排队中', running: '正在执行', review_required: '需要复核',
  finished: '执行结束', cancelled: '已取消', execution_error: '执行异常',
}
export const profileNames = {
  success: '无需修复分支', repairable: '修复后满足分支', regression: '候选退化回退分支', always_fail: '预算耗尽分支',
}
export const dimensionNames: Record<string, string> = {
  ssm_extraction: 'SSM 语义提取', static_validation: '静态校验', san_compile: 'San 编译',
  structure_ted: '结构 TED', browser_visual: '浏览器视觉', browser_interaction: '浏览器交互',
}
export const eventNames: Record<string, string> = {
  queued: '运行已持久入队', running: 'Worker 已认领', stub_response: '已保存开发夹具收据',
  finished: '控制流程结束', cancel_requested: '已请求安全取消', resumed: '运行已重新入队',
  cancelled: '运行已取消', execution_error: '执行出现异常', review_required: '等待复核',
}

export function runId(value: string): string {
  if (!/^[0-9a-f]{32}$/.test(value)) throw new Error('运行标识格式不正确')
  return value
}
export function idFromHash(hash: string): string | null {
  const id = new URLSearchParams(hash.replace(/^#/, '')).get('run')
  return id && /^[0-9a-f]{32}$/.test(id) ? id : null
}
export function validateDraft(draft: Draft): void {
  if (!/^[A-Za-z][A-Za-z0-9_]{0,100}\.vue$/.test(draft.filename)) throw new Error('文件名应以英文字母开头，仅含字母、数字或下划线，并以 .vue 结尾。')
  if (!draft.source.trim()) throw new Error('请选择 Vue 文件，或粘贴源码。')
  if (new TextEncoder().encode(draft.source).length > 262144) throw new Error('源码超过 256 KiB 上限。')
  if (draft.name.trim().length > 120) throw new Error('任务名称不能超过 120 个字符。')
  if (!(draft.profile in profileNames) || !Number.isInteger(draft.rounds) || draft.rounds < 0 || draft.rounds > 3) throw new Error('控制场景或夹具预算不受支持。')
}
export async function decodeSource(file: { name: string; size: number; arrayBuffer: () => Promise<ArrayBuffer> }): Promise<string> {
  if (file.size > 262144) throw new Error('文件超过 256 KiB 上限。')
  let source: string
  try { source = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer()) }
  catch { throw new Error('文件不是可读取的 UTF-8 文本。') }
  validateDraft({ name: '', filename: file.name, source, profile: 'success', rounds: 0 })
  return source
}
export function validToken(value: string): boolean { return /^[\x21-\x7e]{24,256}$/.test(value) }
export function canDownload(run: RunInfo | null, report: Report | null): boolean {
  return !!(run && report && run.status === 'finished' && report.status === 'finished'
    && run.run_id === report.run_id && run.request_sha256 === report.request_sha256
    && run.final_revision_id && run.final_revision_id === report.final_revision_id
    && report.fixture_audit?.accepted_revision_id === run.final_revision_id
    && report.fixture_audit?.status === 'verified_development_ledger_not_migration_evidence')
}
export function shortId(value: string | null | undefined): string { return value ? value.slice(0, 8) : '—' }
export function timeLabel(stamp: number): string {
  return Number.isFinite(stamp) ? new Date(stamp * 1000).toLocaleString('zh-CN', { hour12: false }) : '未记录'
}
