<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { Api, ApiError, errorText } from '../lib/api.ts'
import { shortId, timeLabel } from '../lib/model.ts'
import { canDownloadSsm, evaluationNames, extractionHash, extractionIdFromHash, extractionNames, projectionExplanation } from '../lib/ssm-model.ts'
import type { ExtractionPage, ExtractionReport } from '../lib/types.ts'

const api = new Api()
const page = ref<ExtractionPage>({ items: [], next_cursor: null })
const cursor = ref<string | null>(null)
const previous = ref<(string | null)[]>([])
const selected = ref(extractionIdFromHash(window.location.hash))
const report = ref<ExtractionReport | null>(null)
const listError = ref(''), detailError = ref(''), downloadError = ref(''), updated = ref('')
const listing = ref(false), loading = ref(false), downloading = ref(false)
let alive = true
let listController: AbortController | null = null
let detailController: AbortController | null = null
function aborted(error: unknown) { return error instanceof ApiError && error.code === 'query_aborted' }
async function loadList() {
  listController?.abort()
  const controller = new AbortController(); listController = controller; listing.value = true
  try {
    const result = await api.extractions(cursor.value, controller.signal)
    if (controller.signal.aborted || !alive) return
    page.value = result; listError.value = ''
  } catch (error) { if (alive && !aborted(error)) listError.value = errorText(error) }
  finally { if (listController === controller && alive) listing.value = false }
}
async function loadDetail() {
  detailController?.abort()
  const id = selected.value
  report.value = null; detailError.value = ''; downloadError.value = ''; updated.value = ''
  if (!id) { loading.value = false; return }
  const controller = new AbortController(); detailController = controller; loading.value = true
  try {
    const result = await api.extractionReport(id, controller.signal)
    if (controller.signal.aborted || !alive || selected.value !== id) return
    if (result.extraction_id !== id) throw new Error('报告身份不匹配，禁止下载。')
    report.value = result; updated.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  } catch (error) { if (alive && !aborted(error) && selected.value === id) detailError.value = errorText(error) }
  finally { if (detailController === controller && alive) loading.value = false }
}
function select(id: string) {
  if (selected.value === id) { void loadDetail(); return }
  window.location.hash = extractionHash(window.location.hash, id)
}
function syncHash() {
  const id = extractionIdFromHash(window.location.hash)
  if (id === selected.value) return
  selected.value = id; void loadDetail()
}
function nextPage() {
  if (!page.value.next_cursor) return
  previous.value.push(cursor.value); cursor.value = page.value.next_cursor; void loadList()
}
function previousPage() { cursor.value = previous.value.pop() ?? null; void loadList() }
async function refresh() { await Promise.all([loadList(), loadDetail()]) }
function save(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob), link = document.createElement('a')
  link.href = url; link.download = filename; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
async function download(kind: 'report' | 'ssm') {
  const id = selected.value
  if (!id || !report.value || downloading.value || loading.value || (kind === 'ssm' && !canDownloadSsm(report.value))) return
  downloading.value = true; downloadError.value = ''
  try {
    // Re-audit on click, rather than exporting stale evidence from page memory.
    const current = await api.extractionReport(id)
    if (!alive || selected.value !== id) return
    if (current.extraction_id !== id) throw new Error('报告身份不匹配，禁止下载。')
    report.value = current
    if (kind === 'report') save(new Blob([JSON.stringify(current, null, 2)], { type: 'application/json;charset=utf-8' }), `ssm_report_${id}.json`)
    else {
      if (!canDownloadSsm(current)) throw new Error('该记录没有可下载的已完成 SSM。')
      const blob = await api.extractionArtifact(id)
      if (alive && selected.value === id) save(blob, `ssm_${id}.json`)
    }
  } catch (error) {
    if (alive && selected.value === id) { report.value = null; downloadError.value = errorText(error) }
  } finally { if (alive) downloading.value = false }
}
onMounted(() => { window.addEventListener('hashchange', syncHash); void refresh() })
onBeforeUnmount(() => {
  alive = false; window.removeEventListener('hashchange', syncHash)
  listController?.abort(); detailController?.abort()
})
</script>

<template>
  <section class="panel ssm-panel" aria-labelledby="ssm-title">
    <div class="section-heading"><div><span class="eyebrow">REAL SOURCE EVIDENCE · READ ONLY</span><h2 id="ssm-title">真实 SSM 提取</h2></div><button type="button" @click="refresh">刷新提取记录 ↻</button></div>
    <p class="subtle ssm-intro">查看已登记的 CLI 提取。无需写入令牌或 Worker；本面板不会执行提取、恢复或模型调用。</p>
    <div class="message info">提取成功 ≠ 迁移通过。尚未生成 San，也未执行目标静态校验、编译、结构、视觉与交互评估。</div>
    <div v-if="listError" class="message error" role="alert">列表读取中断；以下可能是上次数据。{{ listError }}</div>
    <div class="table-scroll"><table v-if="page.items.length"><thead><tr><th>源文件 / 提取 ID</th><th>登记执行状态</th><th>创建时间</th></tr></thead><tbody><tr v-for="item in page.items" :key="item.extraction_id" :class="{ selected: selected === item.extraction_id }"><td><button class="row-link" type="button" @click="select(item.extraction_id)">{{ item.filename }}</button><code class="file-line">{{ shortId(item.extraction_id) }}</code></td><td>{{ extractionNames[item.status] ?? '未知状态，需复核' }}</td><td class="date-cell">{{ timeLabel(item.created_at) }}</td></tr></tbody></table></div>
    <p v-if="!page.items.length" class="ssm-empty subtle">{{ listing ? '正在读取登记记录…' : listError ? '列表尚未确认，请检查 API 后刷新。' : '暂无已登记提取；离线探测目录不会自动导入。' }}</p>
    <div class="pagination"><span class="tiny">第 {{ previous.length + 1 }} 页 · 列表仅是登记元数据，打开详情才核对证据</span><div><button type="button" :disabled="!previous.length || listing" @click="previousPage">上一页</button><button type="button" :disabled="!page.next_cursor || listing" @click="nextPage">下一页</button></div></div>
    <div class="ssm-detail">
      <p v-if="!selected" class="subtle">选择一个源文件，查看提取报告及文件指纹。</p>
      <p v-if="loading" class="subtle" role="status">正在核对登记文件与报告…</p>
      <div v-if="detailError || downloadError" class="message error" role="alert">报告／证据未确认，下载已禁用。{{ detailError || downloadError }}</div>
      <template v-if="report">
        <div class="run-identity"><div><strong>{{ report.request.source.filename }}</strong><p><code>{{ report.extraction_id }}</code></p></div><span class="tiny">最后核对 {{ updated }}</span></div>
        <div class="fact-grid"><div><span>提取执行</span><strong>{{ extractionNames[report.status] ?? '未知，需复核' }}</strong></div><div><span>源阶段评估</span><strong>{{ evaluationNames[report.contract_evaluation.status] ?? '未知，需复核' }}</strong></div><div><span>整体迁移质量</span><strong>未执行</strong></div></div>
        <p class="subtle small-copy">源评估仅证明已登记的提取产物／证据符合当前受限提取口径；不证明语义等价或语法覆盖率。</p>
        <div class="action-row"><button type="button" :disabled="downloading || loading" @click="download('report')">下载提取报告 JSON</button><button class="secondary-accent" type="button" :disabled="downloading || loading || !canDownloadSsm(report)" @click="download('ssm')">下载真实 SSM JSON</button></div>
        <div class="message info">{{ projectionExplanation(report) }}</div>
        <dl class="provenance"><dt>停止原因</dt><dd><code>{{ report.stop_reason || '尚无终态原因' }}</code></dd><dt>请求协议</dt><dd><code>{{ report.request.protocol }}</code></dd><dt>关联夹具运行</dt><dd><code>{{ report.request.source.referenced_run_id ?? '无（直接关联源输入）' }}</code></dd><dt>源输入 ID</dt><dd><code>{{ report.request.source.input_id }}</code></dd><dt>源码 SHA-256</dt><dd><code>{{ report.request.source.source_sha256 }}</code></dd><dt>请求指纹</dt><dd><code>{{ report.request_sha256 }}</code></dd><dt>P1 报告</dt><dd>{{ report.contract_report ? (evaluationNames[report.contract_report.status] ?? report.contract_report.status) : '不可用（保留历史缺失）' }}</dd><dt>评估器版本</dt><dd><code>{{ report.contract_evaluation.evaluator_version ?? '未执行' }}</code></dd><dt>环境指纹</dt><dd><code>{{ report.contract_evaluation.environment_sha256 ?? '未记录，不补造' }}</code></dd><dt>实际模型调用</dt><dd>{{ report.actual_model_calls }} 次 · LangSmith {{ report.langsmith_uploaded ? '状态异常，请复核' : '未上传' }} · 非生产就绪</dd></dl>
        <ul v-if="report.contract_evaluation.diagnostics.length" class="ssm-diagnostics"><li v-for="diagnostic in report.contract_evaluation.diagnostics" :key="diagnostic.code"><code>{{ diagnostic.code }}</code> · 来源 {{ diagnostic.origin }}（不授权目标修复）</li></ul>
        <details class="audit-details"><summary>已核对的证据文件 <span>{{ report.contract_projection.evidence_index.length }} 项</span></summary><ul class="revision-list"><li v-for="file in report.contract_projection.evidence_index" :key="file.path"><code>{{ file.path }}</code><span class="hash-label">SHA-256 <code>{{ file.sha256 }}</code></span></li></ul></details>
      </template>
    </div>
  </section>
</template>

<style scoped>
.ssm-panel{margin-top:23px;padding:23px;min-width:0;scroll-margin-top:20px}.ssm-panel>.section-heading button{font-size:11px;flex-shrink:0}.ssm-intro{font-size:11px;line-height:1.8;margin:12px 0 16px}.ssm-panel table{min-width:480px}.ssm-panel td{font-size:11px}.ssm-panel .pagination{padding:12px 0;flex-wrap:wrap}.ssm-empty{font-size:12px;padding:20px 0}.ssm-detail{border-top:1px solid var(--border);padding-top:18px;font-size:12px}.ssm-detail .run-identity{margin-top:0}.ssm-diagnostics{padding-left:18px;color:#93634c}.ssm-panel .fact-grid strong{font-size:12px}.ssm-panel .provenance{grid-template-columns:85px minmax(0,1fr)}@media(max-width:760px){.ssm-panel{padding:20px}.ssm-panel>.section-heading{align-items:flex-start;flex-wrap:wrap}.ssm-panel .fact-grid{grid-template-columns:1fr}.ssm-panel .fact-grid>div:last-child{grid-column:auto}}
</style>
