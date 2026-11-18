<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import {useMigrationWorkbench} from '../composables/useMigrationWorkbench.ts'
import {migrationStatuses,filterMigrations,dateTime,strategyLabels,phaseItems,stopReasonLabel,type WorkspaceView} from '../lib/migration.ts'
import UiIcon from './UiIcon.vue'
import StatusBadge from './StatusBadge.vue'
import CreateMigrationDialog from './workbench/CreateMigrationDialog.vue'
import QualityEvaluation from './workbench/QualityEvaluation.vue'
import RunEvidence from './workbench/RunEvidence.vue'
const props=defineProps<{view:WorkspaceView;createSequence:number;refreshSequence:number}>()
const emit=defineEmits<{context:[string];connection:[boolean];navigate:[WorkspaceView]}>()
const {sessionReady,rows,selected,selectedRow,report,readiness,connected,error,detailError,notice,updated,refreshing,loading,submitting,autoRefresh,createOpen,code,images,assetsLoading,assetError,draft,manual,canSubmit,canWrite,choose,refresh,submit,download,saveReport,copyCode,action,feedback}=useMigrationWorkbench()
const query=ref(''),filter=ref(''),tab=ref('quality'),page=ref(1)
const filtered=computed(()=>filterMigrations(rows.value,query.value,filter.value))
const pages=computed(()=>Math.max(1,Math.ceil(filtered.value.length/10)))
const paged=computed(()=>filtered.value.slice((page.value-1)*10,page.value*10))
const title=computed(()=>selectedRow.value?.name??report.value?.name??'迁移工作台')
const decisions=computed(()=>report.value?.state.decisions??[])
const phases=computed(()=>phaseItems(report.value))
const workerMissing=computed(()=>readiness.value&&!readiness.value.worker_online&&rows.value.some(r=>r.status==='queued'||r.status==='running'))
watch([query,filter],()=>page.value=1);watch(pages,n=>{if(page.value>n)page.value=n})
watch(title,v=>emit('context',v),{immediate:true});watch(connected,v=>emit('connection',v),{immediate:true})
watch(()=>props.createSequence,()=>createOpen.value=true);watch(()=>props.refreshSequence,()=>void refresh())
watch(selected,()=>tab.value='quality')
async function selectTask(id:string){await choose(id);if(props.view==='records')emit('navigate','workbench')}
</script>
<template>
<div class="cm-workbench">
  <div v-if="error" role="alert" class="cm-alert danger"><UiIcon name="warning"/>{{error}}<button class="cm-text-button" @click="refresh">重试读取</button></div>
  <div v-if="notice" role="status" class="cm-alert info"><UiIcon name="info"/>{{notice}}<button class="cm-icon-button" aria-label="关闭提示" @click="notice=''"><UiIcon name="close" :size="16"/></button></div>
  <div v-if="workerMissing" class="cm-alert warning"><UiIcon name="clock"/>有任务等待执行，但尚未检测到迁移 Worker 心跳。<button class="cm-text-button" @click="emit('navigate','settings')">查看连接状态</button></div>
  <section v-if="view==='settings'">
    <div class="cm-page-heading"><div><span class="cm-eyebrow">SETTINGS & CONNECTIONS</span><h1>设置与连接</h1><p>服务信息来自当前 API，模型配置仍由本机配置文件与 Worker 环境管理。</p></div><button @click="refresh"><UiIcon name="refresh" :size="16"/>刷新状态</button></div>
    <div class="cm-settings-grid"><section class="cm-panel cm-padded"><h2>服务连接</h2><dl class="cm-facts"><dt>API 服务</dt><dd><StatusBadge :status="connected?'pass':'blocked'" :label="connected?'已连接':'未连接'"/></dd><dt>迁移 Worker</dt><dd><StatusBadge :status="readiness?.worker_online?'pass':'not_run'" :label="readiness?.worker_online?'在线':'未检测到心跳'"/></dd><dt>模型</dt><dd>{{readiness?.backend??'—'}} / {{readiness?.model??'—'}}</dd><dt>模型网络</dt><dd>{{readiness?.network_enabled?'已启用':'未启用'}}</dd><dt>LangSmith</dt><dd>{{readiness?.langsmith_enabled?'已启用':'未启用'}}</dd><dt>最近更新</dt><dd>{{updated||'—'}}</dd></dl><div v-if="readiness?.pending.length" class="cm-alert warning"><div><strong>API 进程配置提示</strong><p>{{readiness.pending.join('、')}}</p><p>API 与 Worker 的环境变量独立。API 未读取到模型 key，不代表 Worker 一定缺少凭据；实际调用以任务收据为准。</p></div></div></section>
    <section class="cm-panel cm-padded"><h2>本地工作空间</h2><dl class="cm-facts"><dt>操作会话</dt><dd><StatusBadge :status="sessionReady?'pass':'blocked'" :label="sessionReady?'已自动连接':'尚未就绪'"/></dd></dl><p class="cm-help">仅限本机单用户使用。会话自动建立，创建、取消、恢复和人工记录均由后台校验，无需填写令牌。</p><label class="cm-check"><input v-model="autoRefresh" type="checkbox"/>每 3 秒自动刷新任务与报告</label><div class="cm-alert info">模型密钥仅在 migration-worker 终端配置，不要粘贴到这个页面。修改配置后重启服务，新建任务绑定新版本。</div><h3>配置位置</h3><code>migration_system/configs/system.toml</code><p class="cm-help">安装与启动说明：migration_system/SYSTEM_GUIDE.md</p></section></div>
  </section>
  <section v-else-if="view==='records'">
    <div class="cm-page-heading"><div><span class="cm-eyebrow">MIGRATION HISTORY</span><h1>任务记录</h1><p>展示服务返回的最近 {{rows.length}} 条真实迁移任务，开发夹具不混入。</p></div><button class="cm-primary" @click="createOpen=true"><UiIcon name="plus" :size="17"/>新建迁移</button></div>
    <div class="cm-panel"><div class="cm-list-toolbar"><label class="cm-search"><UiIcon name="search" :size="18"/><input v-model="query" placeholder="搜索任务、文件名或 ID" aria-label="搜索任务记录"/></label><select v-model="filter" aria-label="筛选任务状态"><option value="">全部状态</option><option v-for="(label,value) in migrationStatuses" :key="value" :value="value">{{label}}</option></select></div>
    <div class="cm-table-scroll"><table class="cm-table"><thead><tr><th>迁移任务</th><th>状态</th><th>当前阶段</th><th>创建时间</th><th></th></tr></thead><tbody><tr v-for="row in paged" :key="row.migration_id"><td><button class="cm-row-title" @click="selectTask(row.migration_id)">{{row.name}}</button><small>{{row.filename}} · {{row.migration_id.slice(0,8)}}</small></td><td><StatusBadge :status="row.status"/></td><td><code>{{row.stage}}</code></td><td>{{dateTime(row.created_at)}}</td><td><button class="cm-text-button" @click="selectTask(row.migration_id)">查看详情 →</button></td></tr></tbody></table></div>
    <div v-if="!filtered.length" class="cm-empty">没有符合条件的任务。</div><footer class="cm-pagination"><span>{{filtered.length}} 条 · 第 {{page}} / {{pages}} 页</span><div><button :disabled="page===1" @click="page--">上一页</button><button :disabled="page>=pages" @click="page++">下一页</button></div></footer></div>
  </section>
  <template v-else>
    <header class="cm-task-heading"><div><div class="cm-heading-line"><h1>{{title}}</h1><StatusBadge v-if="report" :status="report.status"/></div><p>{{selectedRow?.filename??'选择已有任务，或创建一次新的迁移'}}<span>Vue → San</span><span v-if="selectedRow">{{dateTime(selectedRow.created_at)}}</span></p></div><div class="cm-header-actions"><button :disabled="!report" @click="saveReport"><UiIcon name="download" :size="18"/>下载报告</button><button class="cm-primary" :disabled="!report?.final_artifact" @click="report?.final_artifact&&download(report.final_artifact)"><UiIcon name="download" :size="18"/>下载 San 代码</button></div></header>
    <section class="cm-pipeline" aria-label="真实迁移阶段"><ol><li v-for="(phase,index) in phases" :key="phase.name" :class="`cm-phase-${phase.state}`"><div class="cm-phase-symbol"><UiIcon :name="phase.icon" :size="24"/><span v-if="phase.state==='done'" class="cm-phase-mark">✓</span><span v-else-if="phase.state==='failed'" class="cm-phase-mark">!</span><span v-else-if="phase.state==='running'" class="cm-spinner"/></div><h3>{{phase.name}}</h3><p>{{phase.detail}}</p><span v-if="index<phases.length-1" class="cm-phase-connector"/></li></ol><div class="cm-pipeline-result"><StatusBadge :status="report?.status" :label="!report?'尚未选择任务':report.status==='finished'?'本次执行已结束':migrationStatuses[report.status]"/></div></section>
    <div class="cm-workspace-grid">
      <aside class="cm-panel cm-recent"><header><h2>最近任务 <span class="cm-count">{{rows.length}}</span></h2><button class="cm-icon-button" aria-label="查看全部任务记录" @click="emit('navigate','records')"><UiIcon name="history" :size="19"/></button></header><label class="cm-search"><UiIcon name="search" :size="16"/><input v-model="query" aria-label="搜索最近任务" placeholder="搜索任务或文件名"/></label>
      <div class="cm-recent-list"><button v-for="row in filtered" :key="row.migration_id" class="cm-task-row" :class="{active:selected===row.migration_id}" :aria-pressed="selected===row.migration_id" @click="choose(row.migration_id)"><UiIcon name="file" :size="20"/><span><strong>{{row.name}}</strong><small>{{row.filename}}</small><StatusBadge :status="row.status"/></span></button><div v-if="!filtered.length" class="cm-empty compact"><UiIcon name="folder" :size="30"/><p>{{query?'没有匹配的任务':'暂无迁移记录'}}</p></div></div>
      <footer v-if="report"><dl class="cm-facts"><dt>迁移策略</dt><dd>{{strategyLabels[report.request.strategy??'']??'未记录'}}</dd><dt>模型已开始</dt><dd>{{report.model_calls_started}} 次</dd><dt>已知 Token 用量</dt><dd>{{report.usage.known_total_tokens.toLocaleString()}}{{report.usage.complete?'':' · 不完整'}}</dd><dt>未知调用</dt><dd>{{report.unknown_calls}} 次</dd><dt>修复候选</dt><dd>{{decisions.length}} 轮</dd></dl><button class="cm-text-button" @click="tab='repairs'">查看修复记录 <UiIcon name="arrow" :size="15"/></button></footer></aside>
      <section class="cm-panel cm-detail-panel" :aria-busy="loading">
      <div v-if="detailError" class="cm-alert danger" role="alert">{{detailError}}<button @click="choose(selected)">重新读取</button></div>
      <template v-if="report"><nav class="cm-tabs" aria-label="任务详情页签"><button v-for="item in [{id:'quality',label:'质量评估'},{id:'code',label:'San 代码'},{id:'repairs',label:'修复记录'},{id:'artifacts',label:'产物与验收'}]" :key="item.id" :class="{active:tab===item.id}" :aria-pressed="tab===item.id" @click="tab=item.id">{{item.label}}<span v-if="item.id==='repairs'&&decisions.length" class="cm-tab-count">{{decisions.length}}</span></button></nav>
      <div class="cm-tab-body"><section v-if="report.state.failure_diagnostics?.length" class="cm-alert danger"><div><h3>源代码预检查诊断</h3><p v-if="report.model_calls_started===0">尚未调用模型。</p><div v-for="(finding,index) in report.state.failure_diagnostics" :key="index"><code>{{finding.code}}</code><p>{{finding.message}}</p><pre v-if="finding.location">{{JSON.stringify(finding.location)}}</pre><pre v-if="finding.excerpt">{{finding.excerpt}}</pre></div></div></section>
      <QualityEvaluation v-if="tab==='quality'" :report="report" :images="images" :loading="assetsLoading" :error="assetError"/>
      <RunEvidence v-else :tab="tab" :report="report" :code="code" :loading="assetsLoading" :error="assetError" :manual="manual" :can-write="canWrite" @copy="copyCode" @download="download" @feedback="feedback"/>
      </div><footer class="cm-report-footer"><div><span>停止原因：{{stopReasonLabel(report.stop_reason)}}</span></div><div><button v-if="['queued','running'].includes(report.status)" :disabled="!canWrite" @click="action('cancel')">安全取消</button><button v-if="['blocked','review_required'].includes(report.status)" :disabled="!canWrite" @click="action('resume')">同版本受限恢复</button></div></footer></template>
      <div v-else class="cm-empty cm-detail-empty"><span v-if="loading" class="cm-spinner"/><UiIcon v-else name="folder" :size="48"/><h2>{{loading?'正在读取迁移报告':'开始你的第一次迁移'}}</h2><p>提交一份 Vue 源码，查看真实评估、修复与 San 产物。</p><button class="cm-primary" @click="createOpen=true"><UiIcon name="plus" :size="18"/>新建迁移</button></div>
      </section>
    </div><footer class="cm-workspace-footer"><span><span class="cm-dot" :class="connected?'connected':'offline'"/>本地工作空间 · 真实记录，不使用示例数据</span><span>上次更新 {{updated||'—'}} · {{refreshing?'正在刷新':autoRefresh?'每 3 秒自动刷新':'自动刷新已暂停'}}</span></footer>
  </template>
  <CreateMigrationDialog v-if="createOpen" :draft="draft" :session-ready="sessionReady" :busy="submitting" :can-submit="!!canSubmit" :error="error" @close="createOpen=false" @submit="submit"/>
</div>
</template>
