<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import SsmPanel from './SsmPanel.vue'
import MigrationWorkbench from './MigrationWorkbench.vue'
import { Api, ApiError, errorText } from '../lib/api.ts'
import { canDownload, decodeSource, dimensionNames, eventNames, idFromHash, profileNames, shortId, statusNames, timeLabel, validateDraft, validToken } from '../lib/model.ts'
import { statuses } from '../lib/types.ts'
import type { Configuration, Draft, EventRow, Health, Report, RunInfo, RunPage, RunStatus, Submission } from '../lib/types.ts'

const api = new Api()
const workspaceMode = ref<'migration'|'development'>('development')
const configuration = ref<Configuration | null>(null)
const live = ref<Health | null>(null)
const ready = ref<Health | null>(null)
const connectionError = ref('')
const listError = ref('')
const detailError = ref('')
const reportError = ref('')
const actionError = ref('')
const notice = ref('')
const writeToken = ref('')
const filter = ref('')
const cursor = ref<string | null>(null)
const previousCursors = ref<(string | null)[]>([])
const page = ref<RunPage>({ items: [], next_cursor: null })
const listLoading = ref(false)
const selectedId = ref(idFromHash(window.location.hash))
const currentRun = ref<RunInfo | null>(null)
const report = ref<Report | null>(null)
const events = ref<EventRow[]>([])
const updatedAt = ref('')
const busy = ref(false)
const actionBusy = ref(false)
const pending = ref<Submission | null>(null)
const submittedId = ref<string | null>(null)
const confirmation = ref<'cancel' | 'resume' | null>(null)
const draft = reactive<Draft>({ name: '', filename: 'Example.vue', source: '', profile: 'repairable', rounds: 3 })
let alive = true
let timer: ReturnType<typeof setTimeout> | null = null
let detailController: AbortController | null = null
let listController: AbortController | null = null
let healthController: AbortController | null = null

const modeAllowed = computed(() => configuration.value?.mode === 'development_stub' && configuration.value.production_ready === false)
const downloadable = computed(() => canDownload(currentRun.value, report.value))
const sourceBytes = computed(() => new TextEncoder().encode(draft.source).length)
const formLocked = computed(() => busy.value || !!pending.value || !!submittedId.value)
const stageCount = computed(() => report.value?.attempts.length ?? 0)

function aborted(error: unknown) { return error instanceof ApiError && error.code === 'query_aborted' }
async function health() {
  healthController?.abort()
  const controller = new AbortController(); healthController = controller
  try {
    const result = await Promise.all([api.live(controller.signal), api.ready(controller.signal), api.configurations(controller.signal)])
    if (controller.signal.aborted || !alive) return
    ;[live.value, ready.value, configuration.value] = result
    connectionError.value = modeAllowed.value ? '' : '后端模式不受此开发工作台支持，写入已禁用。'
  } catch (error) {
    if (aborted(error) || !alive) return
    live.value = null; ready.value = null; configuration.value = null
    connectionError.value = errorText(error)
  }
}
async function loadList() {
  listController?.abort()
  const controller = new AbortController(); listController = controller
  listLoading.value = true
  try {
    const result = await api.runs(filter.value, cursor.value, controller.signal)
    if (controller.signal.aborted || !alive) return
    page.value = result; listError.value = ''
  } catch (error) {
    if (!aborted(error) && alive) listError.value = errorText(error)
  } finally { if (listController === controller && alive) listLoading.value = false }
}
async function loadDetail() {
  const id = selectedId.value
  if (!id) return
  detailController?.abort()
  const controller = new AbortController(); detailController = controller
  try {
    const result = await api.run(id, controller.signal)
    if (controller.signal.aborted || selectedId.value !== id || !alive) return
    currentRun.value = result; detailError.value = ''; updatedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
    const after = events.value.at(-1)?.sequence ?? 0
    const [eventResult, reportResult] = await Promise.allSettled([api.events(id, after, controller.signal), api.report(id, controller.signal)])
    if (controller.signal.aborted || selectedId.value !== id || !alive) return
    if (eventResult.status === 'fulfilled') {
      const merged = new Map(events.value.map(item => [item.sequence, item]))
      for (const item of eventResult.value.items) merged.set(item.sequence, item)
      events.value = [...merged.values()].sort((a, b) => a.sequence - b.sequence).slice(-1000)
    } else if (!aborted(eventResult.reason)) detailError.value = '事件读取中断：' + errorText(eventResult.reason)
    if (reportResult.status === 'fulfilled') { report.value = reportResult.value; reportError.value = '' }
    else if (!aborted(reportResult.reason)) { report.value = null; reportError.value = errorText(reportResult.reason) }
  } catch (error) { if (!aborted(error) && alive) detailError.value = errorText(error) }
}
function syncHash() {
  detailController?.abort()
  selectedId.value = idFromHash(window.location.hash)
  currentRun.value = null; report.value = null; events.value = []; updatedAt.value = ''
  detailError.value = ''; reportError.value = ''; confirmation.value = null
  if (selectedId.value) void loadDetail()
}
function select(id: string) {
  if (selectedId.value === id) { void loadDetail(); return }
  window.location.hash = 'run=' + id
}
async function refreshAll() { await Promise.all([health(), loadList(), loadDetail()]) }
async function poll() {
  if (!alive) return
  if (!document.hidden) {
    await Promise.all([health(), loadDetail()])
    if (page.value.items.some(item => item.status === 'queued' || item.status === 'running')) await loadList()
  }
  if (alive) timer = setTimeout(poll, 2500)
}
function changeFilter() { cursor.value = null; previousCursors.value = []; void loadList() }
function nextPage() {
  if (!page.value.next_cursor) return
  previousCursors.value.push(cursor.value); cursor.value = page.value.next_cursor; void loadList()
}
function previousPage() { cursor.value = previousCursors.value.pop() ?? null; void loadList() }
async function readFile(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  try { draft.source = await decodeSource(file); draft.filename = file.name; actionError.value = '' }
  catch (error) { actionError.value = errorText(error) }
  finally { target.value = '' }
}
async function submit() {
  if (busy.value || submittedId.value || !modeAllowed.value) return
  actionError.value = ''; notice.value = ''
  try {
    if (!validToken(writeToken.value)) throw new Error('请输入服务器生成的本地写入令牌（24–256 位英文／数字），不是模型密钥。')
    if (!pending.value) {
      validateDraft(draft)
      pending.value = { draft: { ...draft }, key: crypto.randomUUID().replaceAll('-', '') }
    }
    busy.value = true
    const id = await api.submit(pending.value, writeToken.value)
    if (!alive) return
    submittedId.value = id; pending.value = null
    notice.value = '开发运行已持久入队。页面查询和刷新不会重新提交。'
    select(id); cursor.value = null; previousCursors.value = []; filter.value = ''; await loadList()
  } catch (error) { if (alive) actionError.value = errorText(error) }
  finally { if (alive) busy.value = false }
}
function resetForm() {
  pending.value = null; submittedId.value = null; notice.value = ''; actionError.value = ''
}
async function performAction() {
  const id = selectedId.value, action = confirmation.value
  if (!id || !action || actionBusy.value) return
  confirmation.value = null; actionError.value = ''; actionBusy.value = true
  try {
    if (action === 'cancel') await api.cancel(id, writeToken.value)
    else await api.resume(id, writeToken.value)
    notice.value = action === 'cancel' ? '取消请求已登记；正在返回的操作会在安全边界停止。' : '恢复请求已登记；仍按原冻结绑定和收据执行。'
    await Promise.all([loadDetail(), loadList()])
  } catch (error) { if (alive) actionError.value = errorText(error) }
  finally { if (alive) actionBusy.value = false }
}
function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob), anchor = document.createElement('a')
  anchor.href = url; anchor.download = filename; anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
async function downloadArtifact() {
  if (!selectedId.value || !downloadable.value || actionBusy.value) return
  const id = selectedId.value
  actionBusy.value = true; actionError.value = ''
  try { saveBlob(await api.artifact(id), `development_fixture_${id}.san`) }
  catch (error) { actionError.value = errorText(error) }
  finally { actionBusy.value = false }
}
function downloadReport() {
  if (!report.value) return
  saveBlob(new Blob([JSON.stringify(report.value, null, 2)], { type: 'application/json;charset=utf-8' }), `development_report_${report.value.run_id}.json`)
}
onMounted(async () => {
  window.addEventListener('hashchange', syncHash)
  await Promise.all([health(), loadList(), loadDetail()])
  if (alive) timer = setTimeout(poll, 2500)
})
onBeforeUnmount(() => {
  alive = false; if (timer) clearTimeout(timer)
  window.removeEventListener('hashchange', syncHash)
  detailController?.abort(); listController?.abort(); healthController?.abort(); writeToken.value = ''
})
</script>

<template>
  <nav aria-label="工作台模式" class="workspace-switcher"><button @click="workspaceMode='migration'">真实迁移系统</button><button @click="workspaceMode='development'">开发夹具与 SSM 历史</button></nav>
  <MigrationWorkbench v-if="workspaceMode==='migration'" />
  <div v-else class="workbench">
    <header class="masthead">
      <div class="brand"><div class="brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32"><path d="M6 9h12m-4-4 4 4-4 4M26 23H14m4-4-4 4 4 4M7 18v7h4M25 14V7h-4" /></svg></div><div><strong>CardMigrator</strong><span>Vue → SSM → San · 本地工作台</span></div></div>
      <div class="header-meta"><span class="mode-tag">开发模式</span><span class="version">WORKBENCH / 0.1</span></div>
    </header>
    <div class="mode-notice"><span class="notice-dot" aria-hidden="true"></span><div><strong>创建运行仍是开发夹具，不是迁移结果。</strong><span>下方可只读查看真实 SSM 提取；真实生成与目标质量评估尚未接入。</span></div></div>

    <main class="layout">
      <aside class="creation-panel panel">
        <div class="section-heading"><div><span class="eyebrow">NEW RUN</span><h1>创建开发运行</h1></div><span class="number-label">01</span></div>
        <p class="subtle intro">提交源码，验证持久化队列、图编排与报告链路。</p>
        <form @submit.prevent="submit" autocomplete="off">
          <fieldset :disabled="formLocked">
            <label class="field-label" for="task-name">任务名称 <span>选填</span></label>
            <input id="task-name" v-model="draft.name" maxlength="120" placeholder="例如：工作台链路验证" />
            <label class="upload-zone"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 16V4m-4 4 4-4 4 4M4 16v4h16v-4" /></svg><strong>选择 Vue 文件</strong><small>单文件 · UTF-8 · ≤ 256 KiB</small><input type="file" accept=".vue" aria-label="选择 Vue 文件" @change="readFile" /></label>
            <label class="field-label" for="filename">文件名</label><input id="filename" v-model="draft.filename" spellcheck="false" maxlength="105" />
            <div class="label-row"><label class="field-label" for="source">或粘贴源码</label><span class="tiny">{{ sourceBytes.toLocaleString() }} / 262,144 B</span></div>
            <textarea id="source" v-model="draft.source" spellcheck="false" rows="7" placeholder="<template>…</template>" aria-describedby="source-help"></textarea>
            <p id="source-help" class="field-help">仅保存原始文本，不执行上传的源码。暂不支持依赖包。</p>
            <div class="divider"></div>
            <label class="field-label" for="profile">开发控制场景</label>
            <select id="profile" v-model="draft.profile"><option v-for="(name, value) in profileNames" :key="value" :value="value">{{ name }}</option></select>
            <div class="budget-row"><label class="field-label" for="rounds">最多夹具修复轮数</label><select id="rounds" v-model.number="draft.rounds"><option v-for="number in [0, 1, 2, 3]" :key="number" :value="number">{{ number }} 轮</option></select></div>
            <p class="field-help">仅控制测试分支；真实模型／规则迁移额度为 0。</p>
          </fieldset>
          <label class="field-label token-label" for="write-token">本地写入令牌</label><input id="write-token" v-model="writeToken" type="password" autocomplete="off" maxlength="256" placeholder="从 API 启动窗口获取，不是模型密钥" aria-describedby="token-help" />
          <p id="token-help" class="field-help">仅保存在当前页面内存中，刷新即清空。</p>
          <button class="primary submit-button" type="submit" :disabled="busy || !modeAllowed || !!submittedId"><span>{{ busy ? '正在确认提交…' : pending ? '继续此次提交' : submittedId ? '已创建开发运行' : '创建开发运行' }}</span><span aria-hidden="true">↗</span></button>
          <button v-if="pending || submittedId" class="text-button reset-button" type="button" :disabled="busy" @click="resetForm">{{ pending ? '放弃未完成提交（不删除已有记录）' : '新建另一项运行' }}</button>
          <p v-if="pending && !busy" class="field-help retry-note">写入响应丢失时可能已有输入／任务。请先刷新列表核对；已知运行的重交使用原幂等键，不会自动重试。</p>
        </form>
      </aside>

      <div class="workspace-main">
        <section class="connection-bar" aria-label="连接状态"><div class="connection-items"><span><i :class="['status-dot', live ? 'healthy' : 'unknown']"></i>API {{ live ? '已连接' : '未连接' }}</span><span><i :class="['status-dot', ready?.status === 'development_ready' ? 'healthy' : 'waiting']"></i>Worker {{ ready?.status === 'development_ready' ? '心跳正常' : '未就绪' }}</span><span class="local-only">仅本机 · 单 worker</span></div><button class="text-button" type="button" @click="refreshAll">刷新状态 ↻</button></section>
        <div v-if="connectionError" class="message error" role="alert">{{ connectionError }}</div>
        <div v-if="notice" class="message info" role="status">{{ notice }}</div>
        <div v-if="actionError" class="message error" role="alert">{{ actionError }}</div>

        <section class="panel runs-panel" aria-labelledby="runs-title">
          <div class="section-heading"><div><span class="eyebrow">PERSISTENT QUEUE</span><h2 id="runs-title">运行记录</h2></div><select v-model="filter" aria-label="按执行状态筛选" :disabled="listLoading" @change="changeFilter"><option value="">全部执行状态</option><option v-for="status in statuses" :key="status" :value="status">{{ statusNames[status] }}</option></select></div>
          <div v-if="listError" class="message error" role="alert">查询中断，保留上次数据。{{ listError }}</div>
          <div class="table-scroll"><table v-if="page.items.length"><thead><tr><th>任务 / 文件</th><th>执行状态</th><th>迁移检查</th><th>创建时间</th><th><span class="sr-only">打开</span></th></tr></thead><tbody><tr v-for="item in page.items" :key="item.run_id" :class="{ selected: selectedId === item.run_id }"><td><button class="row-link" type="button" @click="select(item.run_id)">{{ item.task_name }}</button><span class="file-line">{{ item.filename }} <code>{{ shortId(item.run_id) }}</code></span></td><td><span :class="['badge', item.status]">{{ statusNames[item.status] ?? '未知状态' }}</span></td><td><span class="muted-status">未执行</span></td><td class="date-cell">{{ timeLabel(item.created_at) }}</td><td><button class="open-button" type="button" :aria-label="'打开运行 ' + item.task_name" @click="select(item.run_id)">↗</button></td></tr></tbody></table></div>
          <div v-if="!page.items.length" class="empty-state"><svg viewBox="0 0 48 48" aria-hidden="true"><path d="M7 14h13l5 6h16v21H7zM7 14V8h13l5 6h16v6M18 29h12m-6-6v12" /></svg><strong>{{ listLoading ? '正在读取运行记录…' : '这里还没有运行记录' }}</strong><p>{{ filter ? '此筛选条件下暂无记录，可切换其他状态。' : '从左侧提交一个 Vue 文件，开始验证开发链路。' }}</p></div>
          <div class="pagination"><span class="tiny">按实际创建时间倒序 · 第 {{ previousCursors.length + 1 }} 页</span><div><button type="button" :disabled="!previousCursors.length || listLoading" @click="previousPage">上一页</button><button type="button" :disabled="!page.next_cursor || listLoading" @click="nextPage">下一页</button></div></div>
        </section>

        <section class="panel detail-panel" aria-labelledby="detail-title">
          <div class="section-heading"><div><span class="eyebrow">RUN INSPECTOR</span><h2 id="detail-title">运行详情</h2></div><span v-if="updatedAt" class="tiny">最后确认 {{ updatedAt }}</span></div>
          <div v-if="!selectedId" class="detail-placeholder"><span class="placeholder-icon" aria-hidden="true">↖</span><div><strong>选择一条运行，查看真实记录</strong><p>这里将展示持久化事件、夹具版本和未执行检查，不显示模拟进度。</p></div></div>
          <template v-else>
            <div v-if="detailError" class="message error" role="alert">查询中断，保留最后确认状态。{{ detailError }}</div>
            <p v-if="!currentRun" class="subtle">正在确认运行 {{ shortId(selectedId) }} 的记录。{{ detailError ? '请检查服务后重试。' : '' }}</p>
            <template v-else>
              <div class="run-identity"><div><code class="run-id">{{ currentRun.run_id }}</code><p>创建于 {{ timeLabel(currentRun.created_at) }}</p></div><span :class="['badge', currentRun.status]">{{ statusNames[currentRun.status] ?? '未知状态' }}</span></div>
              <div class="fact-grid"><div><span>夹具控制场景</span><strong>{{ profileNames[currentRun.request.profile] }}</strong></div><div><span>已登记尝试 / 修复上限</span><strong>{{ stageCount }} 次 <small>/ {{ currentRun.request.max_repair_rounds }} 轮</small></strong></div><div><span>真实模型调用</span><strong>{{ report?.actual_model_calls ?? '未确认' }} <small>次</small></strong></div></div>
              <div class="action-row"><button type="button" :disabled="!report || actionBusy" @click="downloadReport">下载报告 JSON</button><button class="secondary-accent" type="button" :disabled="!downloadable || actionBusy" @click="downloadArtifact">下载开发夹具</button><button v-if="['queued', 'running'].includes(currentRun.status)" type="button" :disabled="actionBusy || !validToken(writeToken) || currentRun.cancel_requested" @click="confirmation = 'cancel'">{{ currentRun.cancel_requested ? '已请求取消' : '请求取消' }}</button><button v-if="['review_required', 'execution_error'].includes(currentRun.status)" type="button" :disabled="actionBusy || !validToken(writeToken)" @click="confirmation = 'resume'">请求受限恢复</button></div>
              <div v-if="confirmation" class="confirmation" role="alert"><p>{{ confirmation === 'cancel' ? '确认请求安全取消？已返回的事实会保留，不强杀在途操作。' : '确认恢复原运行？后端仍会检查实现绑定、租约和未决收据；不创建新的生成运行。' }}</p><button type="button" @click="performAction">确认{{ confirmation === 'cancel' ? '取消' : '恢复' }}</button><button type="button" @click="confirmation = null">返回</button></div>
              <div v-if="currentRun.stop_reason" class="stop-reason"><span>停止原因</span><code>{{ currentRun.stop_reason }}</code></div>
              <div v-if="reportError" class="message error" role="alert">报告审计未通过或暂不可读取，下载已禁用。{{ reportError }}</div>
              <div class="detail-columns"><section class="quality-section"><h3>迁移质量检查 <span class="small-tag">未接入</span></h3><p class="subtle small-copy">以下真实检查尚未执行，不由夹具断言代替。</p><ul class="quality-list"><li v-for="(name, key) in dimensionNames" :key="key"><span><span class="unchecked" aria-hidden="true">—</span>{{ name }}</span><span>未执行</span></li></ul></section><section class="events-section"><h3>实际事件 <span class="count-label">{{ events.length }}</span></h3><p class="subtle small-copy">来自持久化事件，不模拟阶段或百分比。</p><ol v-if="events.length" class="event-list"><li v-for="event in events" :key="event.sequence"><span class="event-sequence">{{ event.sequence }}</span><div><strong>{{ eventNames[event.kind] ?? event.kind }}</strong><code v-if="event.details.revision_id">{{ event.details.revision_id }}</code><code v-else-if="event.details.reason">{{ event.details.reason }}</code></div></li></ol><p v-else class="subtle small-copy">尚未读取到事件。</p></section></div>
              <template v-if="report"><details class="audit-details"><summary>夹具版本与候选审计 <span>{{ report.revisions.length }} 个版本</span></summary><p class="subtle small-copy">{{ report.fixture_audit.status }}；这些版本不是迁移证据。</p><ul class="revision-list"><li v-for="revision in report.revisions" :key="revision.revision_id"><div><code>{{ revision.revision_id }}</code><span class="small-tag">{{ revision.revision_id === currentRun.final_revision_id ? '夹具终态接受版本' : '历史 / 候选版本' }}</span></div><span class="hash-label">SHA-256 <code>{{ revision.sha256 }}</code></span></li></ul><p v-if="!report.revisions.length" class="subtle small-copy">尚无已提交版本。</p><div v-for="decision in report.candidate_decisions" :key="decision.decision_id" class="decision-line"><span :class="['badge', decision.action === 'reject' ? 'review_required' : 'finished']">{{ decision.action === 'reject' ? '已拒绝并回退' : '夹具比较接纳' }}</span><code>{{ shortId(decision.previous_id) }}…{{ decision.previous_id.slice(-2) }} → {{ shortId(decision.candidate_id) }}…{{ decision.candidate_id.slice(-2) }}</code></div></details><details class="audit-details"><summary>统一契约与冻结信息 <span>{{ report.contract_report?.status ?? '不可转换' }}</span></summary><p class="subtle small-copy">P1 没有开发夹具来源，夹具版本和比较保留在应用账本，不冒充真实生成／修复记录。</p><dl class="provenance"><dt>契约映射</dt><dd>{{ report.contract_projection.status }}</dd><dt>契约结论</dt><dd>{{ report.contract_report?.status ?? '缺少冻结快照，不补造' }}</dd><dt>请求指纹</dt><dd><code>{{ currentRun.request_sha256 }}</code></dd><dt>实现指纹</dt><dd><code>{{ currentRun.binding.implementation_sha256 }}</code></dd><dt>LangSmith 上传</dt><dd>{{ report.langsmith_uploaded ? '状态异常，请复核' : '未上传' }}</dd></dl></details></template>
            </template>
          </template>
        </section>
        <SsmPanel />
        <footer class="workspace-footer"><span>本地开发链路 · 不用于论文迁移通过率统计</span><span>真实生成 / 目标评估 / 训练待接入</span></footer>
      </div>
    </main>
  </div>
</template>
