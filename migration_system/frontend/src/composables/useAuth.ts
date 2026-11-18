import {reactive} from 'vue'
import {MigrationApi} from '../lib/migration-api.ts'
export interface Account {id:string;username:string;display_name:string;role:'admin'|'user';is_active:boolean;must_change_password:boolean;created_at:number}
export interface AccountSession {mode:'local'|'multi_user';authenticated:boolean;user?:Account|null}
const api=new MigrationApi()
export const authTab=crypto.randomUUID()
export const auth=reactive({ready:false,mode:'multi_user' as 'local'|'multi_user',user:null as Account|null,message:''})
function clearSelection(){if(typeof window!=='undefined')window.history.replaceState(null,'',window.location.pathname+window.location.search)}
function notify(){if(typeof BroadcastChannel!=='undefined'){const channel=new BroadcastChannel('cardmig-auth');channel.postMessage({sender:authTab});channel.close()}}
export async function refreshAuth(){const result=await api.authSession<AccountSession>();auth.mode=result.mode;auth.user=result.user??null;auth.ready=true;return result}
export async function login(username:string,password:string){await api.post('/api/v1/auth/login',{username,password});api.clearSession();clearSelection();await refreshAuth();auth.message='';notify()}
export async function logout(){await api.post('/api/v1/auth/logout',{});api.clearSession();auth.user=null;clearSelection();auth.message='已退出登录。';notify()}
export async function changePassword(current_password:string,new_password:string){await api.post('/api/v1/auth/password',{current_password,new_password});api.clearSession();auth.user=null;clearSelection();auth.message='密码已更新，所有旧会话已失效，请重新登录。';notify()}
export function forgetAuth(){api.clearSession();auth.user=null;auth.ready=false}
