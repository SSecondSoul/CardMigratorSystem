import {ref,reactive,computed,onMounted,onBeforeUnmount} from 'vue'
import {MigrationApi} from '../lib/migration-api.ts'
import {errorText,ApiError} from '../lib/api.ts'
import {migrationId,userMigrationDraft,validateMigrationDraft,type MigrationRow,type MigrationReport,type Readiness,type FileRef,type MigrationDraft} from '../lib/migration.ts'

export function useMigrationWorkbench() {
  const api=new MigrationApi(),sessionReady=ref(false),rows=ref<MigrationRow[]>([]),selected=ref(''),report=ref<MigrationReport|null>(null)
  const readiness=ref<Readiness|null>(null),connected=ref(false),error=ref(''),detailError=ref(''),notice=ref(''),updated=ref('')
  const refreshing=ref(false),loading=ref(false),submitting=ref(false),writing=ref(false),autoRefresh=ref(true),createOpen=ref(false)
  const code=ref(''),assetError=ref(''),images=ref<Record<string,string>>({}),assetsLoading=ref(false)
  const draft=reactive<MigrationDraft>({name:'',filename:'Example.vue',source:'',strategy:'ssm',rounds:3,propsText:'{}',actionsText:'[]',trusted:false,confirmed:false})
  const manual=reactive({passed:true,lines:null as number|null,seconds:null as number|null,notes:''})
  const selectedRow=computed(()=>rows.value.find(r=>r.migration_id===selected.value))
  const canSubmit=computed(()=>!!draft.source.trim()&&new TextEncoder().encode(draft.source).length<=262144&&sessionReady.value&&!submitting.value)
  const canWrite=computed(()=>sessionReady.value&&!writing.value)
  let alive=true,timer:ReturnType<typeof setTimeout>|undefined,listController:AbortController|null=null,detailController:AbortController|null=null,assetController:AbortController|null=null,assetKey='',pendingAssetKey=''
  const aborted=(e:unknown)=>e instanceof ApiError&&e.code==='query_aborted'||e instanceof DOMException&&e.name==='AbortError'
  function clearImages(){Object.values(images.value).forEach(URL.revokeObjectURL);images.value={}}
  async function loadAssets(data:MigrationReport) {
    const key=JSON.stringify([data.migration_id,data.final_artifact?.sha256,data.assessment?.images])
    if(key===assetKey||key===pendingAssetKey)return
    assetController?.abort();const controller=new AbortController();assetController=controller
    assetKey='';pendingAssetKey=key;code.value='';assetError.value='';clearImages();assetsLoading.value=true
    const nextImages:Record<string,string>={}
    try {
      const nextCode=data.final_artifact?await (await api.file(data.migration_id,data.final_artifact.relative_path,controller.signal)).text():''
      for(const [name,file] of Object.entries(data.assessment?.images??{})) {
        const blob=await api.file(data.migration_id,file.relative_path,controller.signal)
        nextImages[name]=URL.createObjectURL(new Blob([blob],{type:'image/png'}))
      }
      if(!alive||controller.signal.aborted||selected.value!==data.migration_id) {Object.values(nextImages).forEach(URL.revokeObjectURL);return}
      code.value=nextCode;images.value=nextImages;assetKey=key
    }catch(e){Object.values(nextImages).forEach(URL.revokeObjectURL);if(alive&&!aborted(e)&&selected.value===data.migration_id)assetError.value=errorText(e)}
    finally {if(assetController===controller){assetsLoading.value=false;pendingAssetKey=''}}
  }
  async function loadReport(force=false) {
    const id=selected.value;if(!id||loading.value&&!force)return
    detailController?.abort();const controller=new AbortController();detailController=controller;loading.value=true
    try {
      const data=await api.get<MigrationReport>(`/api/v1/migrations/${migrationId(id)}/report`,controller.signal)
      if(!alive||controller.signal.aborted||id!==selected.value)return
      if(data.migration_id!==id)throw Error('报告任务身份不匹配，禁止展示产物。')
      report.value=data;detailError.value='';void loadAssets(data)
    }catch(e){if(alive&&!aborted(e)&&id===selected.value)detailError.value=errorText(e)}
    finally{if(controller===detailController)loading.value=false}
  }
  async function choose(id:string) {
    migrationId(id);if(selected.value===id){await loadReport(true);return}
    detailController?.abort();assetController?.abort();selected.value=id;report.value=null;code.value='';assetKey='';pendingAssetKey='';detailError.value='';clearImages()
    manual.passed=true;manual.lines=null;manual.seconds=null;manual.notes=''
    const hash=new URLSearchParams(window.location.hash.slice(1));hash.set('migration',id);window.history.replaceState(null,'','#'+hash.toString())
    await loadReport(true)
  }
  async function refresh() {
    if(refreshing.value)return
    listController?.abort();const controller=new AbortController();listController=controller;refreshing.value=true
    const [health,list,session]=await Promise.allSettled([api.get<Readiness>('/api/v1/system/readiness',controller.signal),api.get<{items:MigrationRow[]}>('/api/v1/migrations',controller.signal),api.session()])
    if(!alive||controller.signal.aborted)return
    if(health.status==='fulfilled'){readiness.value=health.value;connected.value=true}else{connected.value=false;readiness.value=null}
    if(list.status==='fulfilled')rows.value=list.value.items
    sessionReady.value=session.status==='fulfilled'
    const failure=health.status==='rejected'?health.reason:list.status==='rejected'?list.reason:session.status==='rejected'?session.reason:null
    error.value=failure?errorText(failure):'';updated.value=new Date().toLocaleTimeString('zh-CN',{hour12:false});refreshing.value=false
    if(!selected.value&&rows.value[0])await choose(rows.value[0].migration_id)
    else await loadReport()
  }
  async function submit() {
    if(submitting.value)return
    try {
      const submitted=userMigrationDraft(draft)
      const {props,actions}=validateMigrationDraft(submitted)
      if(!sessionReady.value)throw Error('本地会话尚未就绪，请刷新连接状态后再创建任务。')
      submitting.value=true;error.value='';notice.value=''
      const input=await api.post<{input_id:string}>('/api/v1/inputs',{filename:submitted.filename,source:submitted.source})
      const key=crypto.randomUUID().replaceAll('-','')
      notice.value=`提交标识 ${key}。响应不明时请先核对任务列表，写入请求不会自动重试。`
      const result=await api.post<{migration_id:string}>('/api/v1/migrations',{input_id:input.input_id,name:submitted.name.trim()||submitted.filename,trusted_source:submitted.trusted,confirm_model_calls:submitted.confirmed,props,actions,max_repair_rounds:submitted.rounds,strategy:submitted.strategy},undefined,key)
      if(!alive)return
      createOpen.value=false;await choose(result.migration_id);await refresh();notice.value='任务已持久化入队，等待真实迁移 Worker 执行。'
    }catch(e){if(alive){if(e instanceof ApiError&&['browser_session_required','browser_csrf_required'].includes(e.code))sessionReady.value=false;error.value=e instanceof SyntaxError?'JSON 格式不正确，请检查 props 和交互配置。':errorText(e)}}
    finally{submitting.value=false}
  }
  function save(blob:Blob,name:string){const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
  function saveReport(){if(report.value)save(new Blob([JSON.stringify(report.value,null,2)],{type:'application/json'}),`migration-report-${report.value.migration_id.slice(0,8)}.json`)}
  async function download(file:FileRef){const id=selected.value;try{save(await api.file(id,file.relative_path),file.relative_path.split('/').at(-1)??'artifact')}catch(e){error.value=errorText(e)}}
  async function copyCode(){try{if(!code.value)return;await navigator.clipboard.writeText(code.value);notice.value='已复制当前接受的 San 代码。'}catch{error.value='浏览器不允许复制，请使用下载 San 代码。'}}
  async function action(kind:'cancel'|'resume') {
    if(writing.value)return
    if(!window.confirm(kind==='cancel'?'请求安全取消，保留所有已发生调用和证据？':'仅恢复同版本检查点；已更换实现的任务不能恢复，未知模型调用不会重发。继续？'))return
    writing.value=true
    try{await api.post(`/api/v1/migrations/${migrationId(selected.value)}/${kind}`,{});notice.value=kind==='cancel'?'已请求安全取消。':'已提交受限恢复请求。';await refresh()}catch(e){if(e instanceof ApiError&&['browser_session_required','browser_csrf_required'].includes(e.code))sessionReady.value=false;error.value=errorText(e)}finally{writing.value=false}
  }
  async function feedback() {
    if(!report.value?.final_artifact||writing.value)return
    writing.value=true
    try{await api.post(`/api/v1/migrations/${migrationId(selected.value)}/feedback`,{revision_sha256:report.value.final_artifact.sha256,passed:manual.passed,changed_lines:typeof manual.lines==='number'?manual.lines:null,elapsed_seconds:typeof manual.seconds==='number'?manual.seconds:null,notes:manual.notes});notice.value='人工记录已追加，不会覆盖自动评估结论。';await loadReport(true)}catch(e){if(e instanceof ApiError&&['browser_session_required','browser_csrf_required'].includes(e.code))sessionReady.value=false;error.value=errorText(e)}finally{writing.value=false}
  }
  async function poll(){if(autoRefresh.value||!updated.value)await refresh();if(alive)timer=setTimeout(poll,3000)}
  onMounted(()=>{const id=new URLSearchParams(window.location.hash.slice(1)).get('migration');if(id&&/^[0-9a-f]{32}$/.test(id))selected.value=id;void poll()})
  onBeforeUnmount(()=>{alive=false;if(timer)clearTimeout(timer);listController?.abort();detailController?.abort();assetController?.abort();clearImages();api.clearSession()})
  return {api,sessionReady,rows,selected,selectedRow,report,readiness,connected,error,detailError,notice,updated,refreshing,loading,submitting,writing,autoRefresh,createOpen,code,images,assetsLoading,assetError,draft,manual,canSubmit,canWrite,choose,refresh,submit,download,saveReport,copyCode,action,feedback}
}
