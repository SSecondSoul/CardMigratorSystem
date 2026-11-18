<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed } from 'vue'
type Row = {migration_id:string;name:string;filename:string;status:string;stage:string;stop_reason:string;created_at:number}
type FileRef = {relative_path:string;sha256:string;kind:string}
type Assessment = {dimensions:Record<string,string>;ui_restoration:number;ssim:number;different_pixel_ratio:number;coverage:string;images:Record<string,FileRef>;diagnostics?:{code:string;message:string}[];initial_control_state?:{equal:boolean}}
type SourceDiagnostic = {code:string;message:string;location?:{line:number;column:number;offset:number};location_precision?:string;excerpt?:string}
type SupportScope = {id:string;label:string;full_public_instance_compatibility:boolean;experimental_public_instance_runtime_enabled:boolean;dynamic_assignment_contract?:string}
type Report = {migration_id:string;status:string;stage:string;stop_reason:string;request_sha256:string;generation_origin?:string|null;support_scope?:SupportScope|null;assessment:Assessment|null;final_artifact:FileRef|null;files:FileRef[];usage:{known_total_tokens:number;complete:boolean};model_calls_started:number;unknown_calls:number;state:{decisions?:unknown[];failure_diagnostics?:SourceDiagnostic[]};manual_feedback:unknown[];request:Record<string,unknown>}
const token=ref(''),source=ref(''),filename=ref('Example.vue'),name=ref(''),rounds=ref(3),strategy=ref('ssm')
const propsText=ref('{}'),actionsText=ref('[]'),trusted=ref(false),confirmed=ref(false),busy=ref(false),error=ref(''),notice=ref('')
const readiness=ref<{ready:boolean;pending:string[];worker_online:boolean;backend:string;model:string;network_enabled:boolean;langsmith_enabled:boolean;support_scope?:SupportScope}|null>(null)
const rows=ref<Row[]>([]),selected=ref(''),report=ref<Report|null>(null),code=ref(''),images=ref<Record<string,string>>({})
const manualPassed=ref(true),manualLines=ref<number|null>(null),manualSeconds=ref<number|null>(null),manualNotes=ref('')
const labels:Record<string,string>={static:'静态语义',compile_runtime:'编译／运行',structure:'AST／DOM 结构',visual:'视觉还原',interaction:'代表性交互',source_baseline:'源基准'}
const statuses:Record<string,string>={queued:'排队',running:'执行中',finished:'配置检查通过',failed:'检查未通过',blocked:'阻断',review_required:'待复核',cancelled:'已取消'}
const sourceReasons:Record<string,string>={source_template_syntax_error:'源 Vue 模板解析失败',source_sfc_syntax_error:'源 Vue 单文件结构解析失败',source_script_syntax_error:'源 Vue 脚本解析失败',source_dynamic_key_contract_unsupported:'源代码合法，但当前系统尚不支持此公开方法契约'}
let active=true,timer:ReturnType<typeof setTimeout>|undefined,controller=new AbortController(),lastArtifact=''
const canSubmit=computed(()=>source.value.trim()&&filename.value.endsWith('.vue')&&token.value.length>=24&&trusted.value&&confirmed.value&&!busy.value)
async function api<T>(url:string,body?:unknown,key?:string):Promise<T>{
  const headers:Record<string,string>={}
  if(body!==undefined){headers['Content-Type']='application/json';headers['X-Cardmig-Token']=token.value;if(key)headers['Idempotency-Key']=key}
  const response=await fetch(url,{method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:JSON.stringify(body),credentials:'same-origin',redirect:'error',signal:AbortSignal.any([controller.signal,AbortSignal.timeout(10000)])})
  const data=await response.json();if(!response.ok)throw Error(data.error?.code??'request_failed');return data as T
}
function resetImages(){Object.values(images.value).forEach(URL.revokeObjectURL);images.value={}}
async function file(ref:FileRef){const r=await fetch(`/api/v1/migrations/${selected.value}/files?path=${encodeURIComponent(ref.relative_path)}`,{signal:controller.signal,redirect:'error'});if(!r.ok)throw Error('artifact_download_failed');return r.blob()}
function save(blob:Blob,name:string){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function saveReport(){if(report.value)save(new Blob([JSON.stringify(report.value,null,2)],{type:'application/json'}),'migration-report.json')}
async function choose(id:string){selected.value=id;lastArtifact='';report.value=null;code.value='';resetImages();await refresh()}
async function refresh(){
  try{
    const [health,list]=await Promise.all([api<NonNullable<typeof readiness.value>>('/api/v1/system/readiness'),api<{items:Row[]}>('/api/v1/migrations')])
    if(!active)return;readiness.value=health;rows.value=list.items
    if(selected.value){const id=selected.value,data=await api<Report>(`/api/v1/migrations/${id}/report`);if(id!==selected.value||!active)return;report.value=data
      if(data.final_artifact&&data.final_artifact.sha256!==lastArtifact){lastArtifact=data.final_artifact.sha256;code.value=await (await file(data.final_artifact)).text();resetImages()
        for(const [name,ref] of Object.entries(data.assessment?.images??{})){const blob=await file(ref);if(!active||id!==selected.value)return;images.value[name]=URL.createObjectURL(new Blob([blob],{type:'image/png'}))}}
    }
    error.value=''
  }catch(e){if(active)error.value=e instanceof Error?e.message:'连接失败'}
}
async function upload(event:Event){const target=event.target as HTMLInputElement,f=target.files?.[0];if(!f)return;if(f.size>262144){error.value='源码不能超过 256 KiB';return}try{const text=new TextDecoder('utf-8',{fatal:true}).decode(await f.arrayBuffer());filename.value=f.name;source.value=text}catch{error.value='文件不是有效的 UTF-8 源码'}}
async function submit(){
  busy.value=true;error.value='';notice.value=''
  try{
    const props=JSON.parse(propsText.value),actions=JSON.parse(actionsText.value)
    const input=await api<{input_id:string}>('/api/v1/inputs',{filename:filename.value,source:source.value})
    const key=crypto.randomUUID().replaceAll('-','')
    // Never retry writes automatically; retain this key in the notice if a response is lost.
    notice.value=`提交标识 ${key}；响应不明时请先检查列表，不要重复提交。`
    const result=await api<{migration_id:string}>('/api/v1/migrations',{input_id:input.input_id,name:name.value||filename.value,trusted_source:true,confirm_model_calls:true,props,actions,max_repair_rounds:rounds.value,strategy:strategy.value},key)
    await choose(result.migration_id);notice.value='已持久化入队，由真实迁移 Worker 执行。'
  }catch(e){error.value=e instanceof Error?e.message:'提交失败'}finally{busy.value=false}
}
async function action(kind:'cancel'|'resume'){
  if(!window.confirm(kind==='cancel'?'请求安全取消，保留所有已发生调用和证据？':'仅恢复同版本检查点；未知模型调用不会重发。继续？'))return
  try{await api(`/api/v1/migrations/${selected.value}/${kind}`,{});await refresh()}catch(e){error.value=String(e)}
}
async function feedback(){if(!report.value?.final_artifact)return
  try{await api(`/api/v1/migrations/${selected.value}/feedback`,{revision_sha256:report.value.final_artifact.sha256,passed:manualPassed.value,changed_lines:manualLines.value,elapsed_seconds:manualSeconds.value,notes:manualNotes.value});notice.value='人工记录已追加，不会覆盖自动评估结论。';await refresh()}catch(e){error.value=String(e)}
}
async function download(ref:FileRef){try{save(await file(ref),ref.relative_path.split('/').at(-1)??'artifact')}catch(e){error.value=String(e)}}
async function poll(){await refresh();if(active)timer=setTimeout(poll,3000)}
onMounted(poll);onBeforeUnmount(()=>{active=false;controller.abort();if(timer)clearTimeout(timer);token.value='';resetImages()})
</script>

<template>
  <div class="migration-workbench">
    <header class="migration-header"><div><span class="eyebrow">MODULAR MIGRATION SYSTEM</span><h1>Vue → SSM → San 迁移工作台</h1><p>真实迁移、独立评估、有界修复与证据归档</p></div><button @click="refresh">刷新状态</button></header>
    <section class="runtime-strip"><span>模型：{{ readiness?.backend }} / {{ readiness?.model }}</span><span>Worker：{{ readiness?.worker_online?'在线':'未启动' }}</span><span>LangSmith：{{ readiness?.langsmith_enabled?'已启用':'未配置／关闭' }}</span><span>本机单用户</span></section>
    <details class="message info"><summary>当前迁移支持范围 · {{ readiness?.support_scope?.id ?? '等待 API 确认' }}</summary>
      <p>面向无外部导入的 JavaScript Options API 单文件组件，目标仍是 San；复用已有 SSM、生成 Prompt、校验和修复规则。通过预检查不等于全部功能已支持。</p>
      <p>setValue 中的 this[key] = value 不再单独触发预检查阻断，仍走原有模型生成、校验和有界修复；不修改 Vue 源码、不按固定键改写，也不接入额外实例代理。放行源码不等于生成结果通过。</p>
      <p v-if="readiness?.support_scope?.dynamic_assignment_contract">动态赋值按行为而非方法名检查：仅证明源码内部可静态确认的普通 data 状态键调用，不证明任意外部公开键等价。未知键、点号键、Symbol、props／computed 和实例命名冲突仍需诊断。</p>
      <p>LangSmith 上传、LoRA 训练和辅助嵌入模型不阻碍普通迁移；未配置交互时报告“未测”，不视为完整验收。</p>
    </details>
    <div v-if="readiness?.pending.length" class="message info">待配置：{{ readiness.pending.join('、') }}。任务可以登记，但未满足条件不会伪造运行结果。详见 migration_system/SETUP_PENDING.md。</div>
    <div v-if="error" class="message error" role="alert">{{ error }}</div><div v-if="notice" class="message info" role="status">{{ notice }}</div>
    <main class="migration-grid">
      <form class="panel migration-form" @submit.prevent="submit"><h2>创建迁移</h2>
        <label>任务名称<input v-model="name" maxlength="120" placeholder="例如：搜索结果卡片迁移" /></label>
        <label>上传 Vue 单文件<input type="file" accept=".vue" @change="upload" /></label>
        <label>文件名<input v-model="filename" /></label>
        <label>源码<textarea v-model="source" rows="12" spellcheck="false" /></label>
        <label>策略<select v-model="strategy"><option value="ssm">SSM ＋ 有界修复</option><option value="ssm_no_repair">SSM 生成，无修复（消融）</option><option value="direct">源码直接生成（基线）</option></select></label>
        <label>最大修复轮数<select v-model.number="rounds"><option v-for="n in [0,1,2,3]" :key="n" :value="n">{{ n }} 轮</option></select></label>
        <details><summary>评估配置（不填交互即报告未测）</summary><label>props JSON<textarea v-model="propsText" rows="3" /></label><label>交互 JSON<textarea v-model="actionsText" rows="5" placeholder='[{"name":"下一页","type":"click","selector":".next"}]' /></label></details>
        <label>本地写入令牌<input v-model="token" type="password" autocomplete="off" /><small>不是模型 API key；只保存在页面内存，刷新清空。</small></label>
        <label class="checkbox-line"><input v-model="trusted" type="checkbox" />我确认源码可信，可在隔离的本地浏览器进程中执行。</label>
        <label class="checkbox-line"><input v-model="confirmed" type="checkbox" />确认此任务最多生成一次、修复三轮；启用云模型后会产生费用。Token 停止线不是硬计费上限。</label>
        <button class="primary-button" :disabled="!canSubmit">{{busy?'登记中…':'创建真实迁移任务'}}</button>
      </form>
      <div class="migration-main"><section class="panel"><h2>迁移记录</h2><div class="table-scroll"><table><thead><tr><th>任务</th><th>执行状态</th><th>当前阶段</th></tr></thead><tbody><tr v-for="row in rows" :key="row.migration_id" :class="{selected:selected===row.migration_id}"><td><button class="text-button" @click="choose(row.migration_id)">{{row.name}}</button><small>{{row.filename}}</small></td><td>{{statuses[row.status]??row.status}}</td><td>{{row.stage}}</td></tr></tbody></table></div><p v-if="!rows.length">暂无真实迁移任务。开发夹具记录在另一个页签，不混入统计。</p></section>
      <section v-if="report" class="panel"><div class="section-heading"><h2>运行与质量报告</h2><span>{{statuses[report.status]}}</span></div><code>{{report.migration_id}}</code><p>停止原因：{{report.stop_reason||'尚未停止'}}</p><p>模型已开始 {{report.model_calls_started}} 次；未知调用 {{report.unknown_calls}} 次；已知 Tokens {{report.usage.known_total_tokens}} {{report.usage.complete?'':'（不完整）'}}</p>
        <p class="field-help">任务支持范围：{{ report.support_scope?.id ?? '历史任务未登记此范围，不追溯改判' }}。该范围不是任意输入／全部公开 API 等价承诺。</p>
        <p v-if="report.support_scope?.dynamic_assignment_contract" class="field-help">动态赋值契约：仅限源码内部可证明的普通 data 状态键；不证明任意外部公开键调用等价。逐方法证据保存在下载报告的 assessment.source_method_contracts。</p>
        <p v-if="report.generation_origin === 'source_ast_rule_generation'" class="field-help">历史生成来源：已撤销的源 AST 规则转换（非模型生成）。新任务不再采用此路径；该历史报告不改判，也不计作模型迁移效果。</p>
        <section v-if="report.state.failure_diagnostics?.length" class="message error source-diagnostics" role="alert">
          <h3>{{ sourceReasons[report.stop_reason] ?? '源代码解析诊断' }}</h3>
          <p v-if="report.model_calls_started === 0">预检查已停止，尚未调用模型。</p>
          <ul><li v-for="(item,index) in report.state.failure_diagnostics" :key="index">
            <code>{{ item.code }}</code>：{{ item.message }}
            <span v-if="item.location">（第 {{ item.location.line }} 行，第 {{ item.location.column }} 列{{ item.location_precision === 'exact' ? '' : '，近似定位' }}）</span>
            <pre v-if="item.excerpt">{{ item.excerpt }}</pre>
          </li></ul>
        </section>
        <div class="quality-cards"><div v-for="(value,key) in report.assessment?.dimensions" :key="key"><span>{{labels[key]??key}}</span><strong :class="value">{{value}}</strong></div></div>
        <p v-if="report.assessment">UI 还原度 {{report.assessment.ui_restoration.toFixed(2)}}% · SSIM {{report.assessment.ssim.toFixed(4)}} · 不同像素 {{(100*report.assessment.different_pixel_ratio).toFixed(2)}}%</p>
        <details v-if="report.assessment?.diagnostics?.length"><summary>未通过原因（原始诊断）</summary><ul><li v-for="(finding,index) in report.assessment.diagnostics" :key="index"><code>{{finding.code}}</code>：{{finding.message}}</li></ul></details>
        <p v-if="report.assessment?.initial_control_state" class="field-help">初始控件实际值：{{report.assessment.initial_control_state.equal?'一致':'不一致'}}。实际值一致不等于 HTML 属性存在性等价，也不代表交互已通过。</p>
        <p class="field-help">通过仅代表给定 props 和场景内检查满足阈值，不代表任意输入或全部功能等价；人工确认独立记录。</p>
        <div class="action-row"><button @click="saveReport">下载报告</button><button v-if="report.final_artifact" @click="download(report.final_artifact)">下载 San</button><button v-if="['queued','running'].includes(report.status)" :disabled="token.length<24" @click="action('cancel')">安全取消</button><button v-if="['blocked','review_required'].includes(report.status)" :disabled="token.length<24" @click="action('resume')">受限恢复</button></div>
        <div class="evidence-images"><figure v-for="(url,name) in images" :key="name"><figcaption>{{name}}</figcaption><img :src="url" :alt="String(name)+'评估截图'" /></figure></div>
        <details><summary>最终接受代码</summary><pre>{{code}}</pre></details><details><summary>候选决策与差异</summary><pre>{{JSON.stringify({assessment:report.assessment,decisions:report.state.decisions},null,2)}}</pre></details>
        <details><summary>全部产物与修复记录 {{report.files.length}}</summary><ul><li v-for="ref in report.files" :key="ref.relative_path"><button class="text-button" @click="download(ref)">{{ref.relative_path.split('/').slice(2).join('/')}}</button><small>{{ref.sha256.slice(0,16)}}</small></li></ul></details>
        <details v-if="report.final_artifact"><summary>追加人工验收</summary><label class="checkbox-line"><input v-model="manualPassed" type="checkbox" />人工确认通过</label><label>人工改动行数（未知留空）<input v-model.number="manualLines" type="number" min="0" /></label><label>人工耗时秒（未知留空）<input v-model.number="manualSeconds" type="number" min="0" /></label><label>验证范围和备注<textarea v-model="manualNotes" rows="3" /></label><button :disabled="token.length<24" @click="feedback">保存人工记录</button><pre>{{JSON.stringify(report.manual_feedback,null,2)}}</pre></details>
      </section><section v-else class="panel"><h2>运行详情</h2><p>选择一条记录查看代码、截图、诊断和候选决策。运行结束与质量通过分开报告。</p></section></div>
    </main>
  </div>
</template>

<style scoped>
.migration-workbench{max-width:1500px;margin:auto;padding:32px;color:#243934}.migration-header,.runtime-strip{display:flex;justify-content:space-between;gap:20px;align-items:center}.migration-header h1{font-size:29px;margin:12px 0}.migration-header p{color:#687e74}.runtime-strip{justify-content:flex-start;flex-wrap:wrap;padding:18px 0;color:#587068;font-size:13px}.migration-grid{display:grid;grid-template-columns:370px minmax(0,1fr);gap:28px}.migration-form,.migration-main>.panel{padding:25px}.migration-main{display:grid;gap:24px;align-content:start}.migration-form{align-self:start}.migration-form label,details label{display:grid;gap:8px;margin:15px 0;font-size:14px}.migration-form input,.migration-form select,.migration-form textarea,details input,details textarea{width:100%;box-sizing:border-box}.migration-form textarea{font:12px/1.6 Consolas,monospace;resize:vertical}.checkbox-line{display:flex!important;align-items:flex-start;line-height:1.7}.checkbox-line input{width:auto!important;flex:none;margin-top:5px}small{display:block;color:#6c8177;font-size:11px;line-height:1.7}.quality-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:20px 0}.quality-cards>div{padding:12px;background:#f1f6f2;display:grid;gap:5px}.pass{color:#127257}.fail,.blocked{color:#ae473e}.not_run{color:#92723f}.evidence-images{display:flex;gap:12px;overflow:auto}.evidence-images figure{margin:15px 0;min-width:200px;flex:1}.evidence-images img{width:100%;border:1px solid #d7e2db}.evidence-images figcaption{font-size:12px;padding-bottom:8px}.migration-main pre{font:12px/1.6 Consolas,monospace;white-space:pre-wrap;overflow:auto;max-height:500px;padding:15px;background:#f4f7f5}.migration-main details{border-top:1px solid #dbe5df;padding:15px 0}.migration-main summary{cursor:pointer}.migration-main td{vertical-align:top}.migration-main li{margin:9px 0;overflow-wrap:anywhere}@media(max-width:900px){.migration-grid{grid-template-columns:1fr}.migration-workbench{padding:18px}.quality-cards{grid-template-columns:repeat(2,1fr)}}
</style>
