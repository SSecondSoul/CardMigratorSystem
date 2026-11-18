/** Display projections only. No scores, success states or model calls are invented. */
export type WorkspaceView = 'workbench' | 'records' | 'settings' | 'development' | 'account' | 'admin'
export interface MigrationRow { migration_id:string; name:string; filename:string; status:string; stage:string; stop_reason:string; created_at:number }
export interface FileRef { relative_path:string; sha256:string; kind:string }
export interface Diagnostic { code:string; message:string; location?:unknown; differences?:unknown[]; details?:unknown }
export interface SourceDiagnostic extends Diagnostic { excerpt?:string; location_precision?:string }
export interface SupportScope { id:string; label:string; dynamic_assignment_contract?:string }
export interface Readiness { ready:boolean; pending:string[]; worker_online:boolean; backend:string; model:string; network_enabled:boolean; langsmith_enabled:boolean; support_scope?:SupportScope }
export interface Assessment {
  dimensions:Record<string,string>; ui_restoration?:number; ssim?:number; different_pixel_ratio?:number;
  images?:Record<string,FileRef>; diagnostics?:Diagnostic[]; structure_ted?:{similarity:number;source_nodes?:number;target_nodes?:number};
  dom_ted?:{similarity:number}; raw_dom_ted?:{similarity:number}; thresholds?:{structure:number;ui:number;pixel_difference:number};
  initial_control_state?:{equal:boolean}; coverage?:string;
  dom_differences?:{path:string;expected?:unknown;actual?:unknown}[];
  styles?:{differences?:{path:string;property:string;source?:unknown;target?:unknown}[];truncated?:boolean}; source_method_contracts?:unknown[];
}
export interface Decision { round:number; accepted:boolean; reason:string; previous:string; candidate:string; added_errors?:string[]; dimensions?:string[] }
export interface MigrationReport {
  migration_id:string; name?:string; status:string; stage:string; stop_reason:string; request_sha256:string; created_at?:number;
  generation_origin?:string|null; support_scope?:SupportScope|null; assessment:Assessment|null; final_artifact:FileRef|null; files:FileRef[];
  usage:{known_total_tokens:number;complete:boolean}; model_calls_started:number; unknown_calls:number;
  state:{decisions?:Decision[];failure_diagnostics?:SourceDiagnostic[]};
  manual_feedback:{id:string;passed:boolean;notes:string;revision_sha256:string}[];
  request:{filename?:string;name?:string;strategy?:string;max_repair_rounds?:number;actions?:unknown[];props?:unknown;runtime?:{width?:number;height?:number;browser?:{width?:number;height?:number}};source_sha256?:string;[key:string]:unknown};
}
export interface MigrationDraft { name:string;filename:string;source:string;strategy:string;rounds:number;propsText:string;actionsText:string;trusted:boolean;confirmed:boolean }
export const migrationStatuses:Record<string,string>={queued:'排队中',running:'迁移中',finished:'配置检查通过',failed:'检查未通过',blocked:'已阻断',review_required:'待复核',cancelled:'已取消'}
export const dimensionLabels:Record<string,string>={static:'静态语义',compile_runtime:'编译／运行',structure:'AST／DOM 结构',visual:'视觉还原',interaction:'代表性交互',source_baseline:'源基准'}
export const dimensionStatus:Record<string,string>={pass:'通过',fail:'未通过',blocked:'阻断',not_run:'未测试'}
export const strategyLabels:Record<string,string>={ssm:'SSM + 有界修复',ssm_no_repair:'SSM · 无修复',direct:'源码直接生成 · 基线'}
export function tone(status?:string) { return status==='pass'||status==='finished'?'success':status==='fail'||status==='failed'||status==='blocked'?'danger':status==='running'?'active':status==='queued'||status==='review_required'?'warning':'neutral' }
export function percent(value:unknown,digits=1) { return typeof value==='number'&&Number.isFinite(value)?`${(100*value).toFixed(digits)}%`:'—' }
export function numeric(value:unknown,digits=1) { return typeof value==='number'&&Number.isFinite(value)?value.toFixed(digits):'—' }
export function dateTime(value?:number) { return value&&Number.isFinite(value)?new Date(value*1000).toLocaleString('zh-CN',{hour12:false,month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}):'时间未记录' }
/** Only called on explicit user submission; experiment drafts/strategies remain unchanged. */
export function userMigrationDraft(draft:MigrationDraft):MigrationDraft {
  return {...draft,strategy:'ssm',trusted:true,confirmed:true}
}
export function validateMigrationDraft(draft:MigrationDraft) {
  if(!/^[A-Za-z][A-Za-z0-9_]{0,100}\.vue$/.test(draft.filename))throw Error('文件名应以英文字母开头，仅含字母、数字或下划线，并以 .vue 结尾。')
  if(!draft.source.trim()||new TextEncoder().encode(draft.source).length>262144)throw Error('请提供非空、256 KiB 以内的 Vue 源码。')
  if(draft.name.trim().length>120)throw Error('任务名称不能超过 120 个字符。')
  if(!['ssm','ssm_no_repair','direct'].includes(draft.strategy)||!Number.isInteger(draft.rounds)||draft.rounds<0||draft.rounds>3)throw Error('迁移策略或修复轮数不合法。')
  const props:unknown=JSON.parse(draft.propsText),actions:unknown=JSON.parse(draft.actionsText)
  if(!props||typeof props!=='object'||Array.isArray(props))throw Error('props JSON 必须是对象。')
  if(!Array.isArray(actions))throw Error('交互 JSON 必须是数组；没有场景请填写 []。')
  if(!draft.trusted||!draft.confirmed)throw Error('请确认源码可信及模型费用授权。')
  return {props,actions}
}
export function migrationId(value:string) { if(!/^[0-9a-f]{32}$/.test(value))throw Error('任务标识无效');return value }
export function evidenceDifferences(assessment:Assessment|null) {
  const value=(v:unknown)=>v===undefined?'未采集':v===null?'缺失':typeof v==='string'?v:JSON.stringify(v)
  return [...(assessment?.dom_differences??[]).map(d=>({kind:'DOM',path:d.path,property:'节点／属性',source:value(d.expected),target:value(d.actual)})),
    ...(assessment?.styles?.differences??[]).map(d=>({kind:'样式',path:d.path,property:d.property,source:value(d.source),target:value(d.target)}))]
}
export function filterMigrations(rows:MigrationRow[],search:string,status:string) { const q=search.trim().toLocaleLowerCase();return rows.filter(r=>(!status||r.status===status)&&(!q||[r.name,r.filename,r.migration_id].some(v=>v.toLocaleLowerCase().includes(q)))) }
export function phaseItems(report:MigrationReport|null) {
  const has=(path:string)=>report?.files.some(f=>f.relative_path.endsWith(path))??false
  const dim=report?.assessment?.dimensions??{},running=report?.status==='running',stage=report?.stage??''
  const state=(ready:boolean,stages:string[],failed=false)=>ready?'done':failed?'failed':running&&stages.some(s=>stage.includes(s))?'running':'waiting'
  const repairs=report?.state.decisions?.length??0
  return [
    {name:'源码解析',icon:'code',detail:'解析 Vue SFC 源码结构',state:state(has('/ssm.json')||running&&/(extract|generate|evaluate|repair|retest)/.test(stage),['preflight'],!!report?.state.failure_diagnostics?.length)},
    {name:'SSM 提取',icon:'layers',detail:'构建结构化语义模型',state:state(has('/ssm.json'),['extract'])},
    {name:'代码生成',icon:'sparkles',detail:report?.generation_origin==='source_ast_rule_generation'?'历史源 AST 规则产物':'基于 LLM 生成 San 代码',state:state(has('/revisions/0.san'),['generate'])},
    {name:'结构校验',icon:'structure',detail:'静态语义 / AST / DOM',state:dim.structure==='fail'||dim.static==='fail'?'failed':dim.structure==='pass'&&dim.static==='pass'?'done':state(false,['evaluate','retest'])},
    {name:'视觉评估',icon:'image',detail:'SSIM 与像素差异',state:dim.visual==='pass'?'done':dim.visual==='fail'?'failed':state(false,['evaluate','retest'])},
    {name:'自动修复',icon:'tool',detail:repairs?`已评估 ${repairs} 轮 / 最多 ${report?.request.max_repair_rounds??'—'} 轮`:'规则修复与候选复检',state:running&&stage.includes('repair')?'running':repairs?(report?.status==='finished'?'done':report?.status==='running'?'running':'failed'):report?.status==='finished'?'skipped':'waiting'},
  ]
}
