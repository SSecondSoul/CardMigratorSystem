import { runId, validToken } from './model.ts'
import type { Configuration, EventRow, ExtractionPage, ExtractionReport, Health, Profile, Report, RunInfo, RunPage, Submission } from './types.ts'

export class ApiError extends Error {
  code: string
  status: number
  requestId: string | null
  constructor(code: string, status = 0, requestId: string | null = null) {
    super(code); this.code = code; this.status = status; this.requestId = requestId
  }
}
const explanations: Record<string, string> = {
  auth_required:'请先登录，或重新登录已过期的账号。',
  invalid_credentials:'账号或密码不正确，或账号已被禁用。',
  login_rate_limited:'登录尝试过于频繁，请在 15 分钟后再试。',
  admin_required:'此操作仅管理员可用。',
  password_change_required:'首次登录或密码重置后，请先修改密码。',
  password_length_12_to_128:'密码长度应为 12–128 个字符。',
  current_password_incorrect:'当前密码不正确。',
  password_must_change:'新密码不能与旧密码相同。',
  username_unavailable:'账号名已被使用。',
  invalid_username:'账号须以英文字母开头，3–64 位，仅含字母、数字、下划线、点或横线。',
  cannot_disable_self:'不能禁用当前管理员账号。',
  invalid_user_limits:'额度须为允许范围内的非负整数。',
  account_disabled:'账号已禁用，请联系管理员。',
  active_job_limit_reached:'排队／执行中任务已达到个人上限，请等待或取消已有任务。',
  daily_job_limit_reached:'今日任务额度已用完（按 UTC 日统计）。',
  source_storage_limit_reached:'已注册源码字节额度不足，请联系管理员。',
  script_token_disabled_in_multi_user:'账号模式不接受全局本地令牌，请使用登录会话。',
  write_token_required: '本地写入令牌不正确，请核对 API 启动窗口。',
  browser_session_required: '本地会话已失效，请刷新连接状态后重新操作；原写入请求不会自动重发。',
  browser_csrf_required: '操作会话校验失败，请刷新连接状态后重新操作；原写入请求不会自动重发。',
  browser_session_bootstrap_denied: '无法建立本地会话，请从本系统的本机地址打开页面。',
  invalid_browser_session: '服务返回的本地会话无效，请检查 API 版本并刷新页面。',
  network_unavailable: '连接未确认，请检查 API 服务；写入请求不会自动重试，请先核对运行列表。',
  request_timeout: '请求超时，结果尚未确认。请先核对运行列表，不要连续重复提交。',
  worker_still_active: 'Worker 仍持有租约，不能恢复。',
  run_not_resumable: '此运行当前不能恢复。',
  implementation_or_dependency_drift: '实现或依赖已变化，不能直接续跑旧运行。',
  ambiguous_attempt_requires_review: '尝试是否完成尚不明确，需要人工复核，不能自动重试。',
  request_snapshot_missing_or_mismatched: '冻结请求缺失或不匹配，需要复核。',
  not_found: '找不到这条记录。',
}
export function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    const message = explanations[error.code] ?? (error.code.startsWith('report_') || error.code.startsWith('artifact_') || error.code.startsWith('ssm_')
      ? '证据或引用校验被阻断，不能导出。请保留现有记录并检查。' : '请求未完成，请检查服务与输入。')
    return `${message}（${error.code}${error.requestId ? ` · 请求 ${error.requestId}` : ''}）`
  }
  return error instanceof Error ? error.message : '操作未完成。'
}

export class Api {
  private fetcher: typeof fetch
  constructor(fetcher: typeof fetch = fetch) {
    // Native browser fetch must not receive the Api instance as its receiver.
    this.fetcher = fetcher.bind(globalThis)
  }
  private async request<T>(path: string, init: RequestInit, signal: AbortSignal | undefined, read: (response: Response) => Promise<T>): Promise<T> {
    if (!(path.startsWith('/api/v1/') || path.startsWith('/health/')) || path.startsWith('//')) throw new ApiError('invalid_local_api_path')
    const controller = new AbortController()
    const abort = () => controller.abort()
    signal?.addEventListener('abort', abort, { once: true })
    if (signal?.aborted) controller.abort()
    const timer = setTimeout(() => controller.abort(), 10000)
    try { return await read(await this.fetcher(path, { ...init, signal: controller.signal, credentials: 'same-origin', redirect: 'error' })) }
    catch (error) {
      if (signal?.aborted) throw new ApiError('query_aborted')
      if (controller.signal.aborted) throw new ApiError('request_timeout')
      if (error instanceof ApiError) throw error
      throw new ApiError('network_unavailable')
    } finally { clearTimeout(timer); signal?.removeEventListener('abort', abort) }
  }
  private async json<T>(path: string, init: RequestInit = {}, signal?: AbortSignal, acceptNotReady = false): Promise<T> {
    return this.request(path, init, signal, async response => {
      let data: any
      try { data = await response.json() } catch { throw new ApiError('invalid_api_response', response.status) }
      if (!response.ok && !(acceptNotReady && response.status === 503 && data?.status === 'not_ready')) {
        const code = typeof data?.error?.code === 'string' ? data.error.code.slice(0, 100) : 'http_error'
        const id = typeof data?.error?.request_id === 'string' && /^[0-9a-f]{32}$/.test(data.error.request_id) ? data.error.request_id : null
        throw new ApiError(code, response.status, id)
      }
      return data as T
    })
  }
  private write<T>(path: string, body: unknown, token: string, key?: string): Promise<T> {
    if (!validToken(token)) return Promise.reject(new Error('请输入服务器生成的 24–256 位英文／数字本地令牌；它不是模型密钥。'))
    const headers: Record<string, string> = { 'Content-Type': 'application/json', 'X-Cardmig-Token': token }
    if (key) headers['Idempotency-Key'] = key
    return this.json<T>(path, { method: 'POST', headers, body: JSON.stringify(body) })
  }
  configurations(signal?: AbortSignal) { return this.json<Configuration>('/api/v1/configurations', {}, signal) }
  live(signal?: AbortSignal) { return this.json<Health>('/health/live', {}, signal) }
  ready(signal?: AbortSignal) { return this.json<Health>('/health/ready', {}, signal, true) }
  runs(status: string, before: string | null, signal?: AbortSignal) {
    const query = new URLSearchParams({ limit: '10' })
    if (status) query.set('status', status)
    if (before) query.set('before', before)
    return this.json<RunPage>('/api/v1/runs?' + query.toString(), {}, signal)
  }
  run(id: string, signal?: AbortSignal) { return this.json<RunInfo>(`/api/v1/runs/${runId(id)}`, {}, signal) }
  report(id: string, signal?: AbortSignal) { return this.json<Report>(`/api/v1/runs/${runId(id)}/report`, {}, signal) }
  events(id: string, after: number, signal?: AbortSignal) { return this.json<{ items: EventRow[] }>(`/api/v1/runs/${runId(id)}/events?after=${after}`, {}, signal) }
  extractions(before: string | null, signal?: AbortSignal) {
    const query = new URLSearchParams({ limit: '10' })
    if (before) query.set('before', before)
    return this.json<ExtractionPage>('/api/v1/ssm-extractions?' + query.toString(), {}, signal)
  }
  extractionReport(id: string, signal?: AbortSignal) { return this.json<ExtractionReport>(`/api/v1/ssm-extractions/${runId(id)}/report`, {}, signal) }
  extractionArtifact(id: string) { return this.download(`/api/v1/ssm-extractions/${runId(id)}/artifact`) }
  cancel(id: string, token: string) { return this.write<RunInfo>(`/api/v1/runs/${runId(id)}/cancel`, {}, token) }
  resume(id: string, token: string) { return this.write<RunInfo>(`/api/v1/runs/${runId(id)}/resume`, {}, token) }
  async submit(pending: Submission, token: string): Promise<string> {
    if (!pending.inputId) {
      const result = await this.write<{ input_id: string }>('/api/v1/inputs', { filename: pending.draft.filename, source: pending.draft.source }, token)
      pending.inputId = runId(result.input_id)
    }
    if (!pending.taskId) {
      const result = await this.write<{ task_id: string }>('/api/v1/tasks', { input_id: pending.inputId, name: pending.draft.name.trim() || pending.draft.filename.replace(/\.vue$/, '') }, token)
      pending.taskId = runId(result.task_id)
    }
    const result = await this.write<{ run_id: string }>(`/api/v1/tasks/${pending.taskId}/runs`,
      { profile: pending.draft.profile as Profile, max_repair_rounds: pending.draft.rounds }, token, pending.key)
    return runId(result.run_id)
  }
  async artifact(id: string): Promise<Blob> {
    return this.download(`/api/v1/runs/${runId(id)}/artifact`)
  }
  private async download(path: string): Promise<Blob> {
    return this.request(path, {}, undefined, async response => {
      if (!response.ok) {
        let code = 'artifact_download_failed'
        try { const data = await response.json(); if (typeof data?.error?.code === 'string') code = data.error.code.slice(0, 100) } catch { /* no raw HTML/trace in the UI */ }
        throw new ApiError(code, response.status)
      }
      return response.blob()
    })
  }
}
