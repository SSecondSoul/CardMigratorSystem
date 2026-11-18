import { validToken } from './model.ts'
import { ApiError } from './api.ts'
import { migrationId } from './migration.ts'
export class MigrationApi {
  private fetcher:typeof fetch
  private csrf=''
  private expires=0
  private pendingSession:Promise<string>|undefined
  constructor(fetcher:typeof fetch=globalThis.fetch) {this.fetcher=fetcher.bind(globalThis)}
  clearSession() {this.csrf='';this.expires=0}
  async session():Promise<void> {await this.sessionToken()}
  async authSession<T>():Promise<T> {return this.json<T>('/api/v1/auth/session',undefined,undefined,undefined,undefined,true)}
  private async sessionToken():Promise<string> {
    if(this.csrf&&Date.now()<this.expires)return this.csrf
    if(!this.pendingSession)this.pendingSession=this.json<{csrf_token:string;expires_in:number}>('/api/v1/browser-session',undefined,undefined,undefined,undefined,true).then(data=>{
      if(!/^[A-Za-z0-9_-]{43}$/.test(data.csrf_token)||!Number.isInteger(data.expires_in)||data.expires_in<60||data.expires_in>28800)throw new ApiError('invalid_browser_session')
      this.csrf=data.csrf_token;this.expires=Date.now()+(data.expires_in-30)*1000;return this.csrf
    }).finally(()=>{this.pendingSession=undefined})
    return this.pendingSession
  }
  async get<T>(path:string,signal?:AbortSignal):Promise<T> { return this.json(path,undefined,undefined,undefined,signal) }
  async post<T>(path:string,body:unknown,token?:string,key?:string):Promise<T> {
    if(!path.startsWith('/api/v1/'))throw Error('无效的本地 API 路径')
    if(token!==undefined&&!validToken(token))throw Error('实验脚本写入令牌无效。')
    const csrf=token===undefined?await this.sessionToken():undefined
    try{return await this.json<T>(path,body,token,key,undefined,false,csrf)}
    catch(error){if(error instanceof ApiError&&['browser_session_required','browser_csrf_required'].includes(error.code))this.clearSession();throw error}
  }
  private async json<T>(path:string,body?:unknown,token?:string,key?:string,signal?:AbortSignal,bootstrap=false,csrf?:string):Promise<T> {
    if(!path.startsWith('/api/v1/'))throw Error('无效的本地 API 路径')
    const headers:Record<string,string>=bootstrap?{'X-Cardmig-Session':'bootstrap'}:{}
    if(body!==undefined){headers['Content-Type']='application/json';if(token!==undefined)headers['X-Cardmig-Token']=token;else headers['X-Cardmig-CSRF']=csrf!;if(key)headers['Idempotency-Key']=key}
    let response:Response
    try { response=await this.fetcher(path,{method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:JSON.stringify(body),credentials:'same-origin',redirect:'error',signal:signal?AbortSignal.any([signal,AbortSignal.timeout(10000)]):AbortSignal.timeout(10000)}) }
    catch(e) { if(signal?.aborted)throw new ApiError('query_aborted');throw new ApiError(e instanceof DOMException&&e.name==='TimeoutError'?'request_timeout':'network_unavailable') }
    let data:any;try{data=await response.json()}catch{throw new ApiError('invalid_api_response',response.status)}
    if(!response.ok){
      if(response.status===401&&data?.error?.code==='auth_required'&&typeof window!=='undefined')window.dispatchEvent(new Event('cardmig-auth-required'))
      throw new ApiError(typeof data?.error?.code==='string'?data.error.code.slice(0,100):'request_failed',response.status)
    }
    return data as T
  }
  async file(id:string,path:string,signal?:AbortSignal) {
    const response=await this.fetcher(`/api/v1/migrations/${migrationId(id)}/files?path=${encodeURIComponent(path)}`,{credentials:'same-origin',redirect:'error',signal:signal?AbortSignal.any([signal,AbortSignal.timeout(15000)]):AbortSignal.timeout(15000)})
    if(!response.ok)throw new ApiError('artifact_download_failed',response.status)
    return response.blob()
  }
}
