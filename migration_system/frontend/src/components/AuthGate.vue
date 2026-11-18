<script setup lang="ts">
import {ref,onMounted,onBeforeUnmount} from 'vue'
import {auth,authTab,refreshAuth,login,forgetAuth,logout as logoutAccount} from '../composables/useAuth.ts'
import {errorText} from '../lib/api.ts'
import AccountPassword from './AccountPassword.vue'
const username=ref(''),password=ref(''),busy=ref(false),error=ref('')
let channel:BroadcastChannel|undefined
async function connect(){error.value='';try{await refreshAuth()}catch(e){error.value=errorText(e)}}
async function submit(){if(busy.value)return;busy.value=true;error.value='';try{await login(username.value,password.value)}catch(e){error.value=errorText(e)}finally{busy.value=false;password.value=''}}
function expired(){forgetAuth();auth.message='登录已失效，请重新登录。';void connect()}
async function logout(){try{await logoutAccount()}catch(e){error.value=errorText(e)}}
onMounted(()=>{void connect();window.addEventListener('cardmig-auth-required',expired);if(typeof BroadcastChannel!=='undefined'){channel=new BroadcastChannel('cardmig-auth');channel.onmessage=event=>{if(event.data?.sender!==authTab){forgetAuth();void connect()}}}})
onBeforeUnmount(()=>{window.removeEventListener('cardmig-auth-required',expired);channel?.close()})
</script>
<template><div v-if="auth.ready&&(auth.mode==='local'||auth.user&&!auth.user.must_change_password)" :key="auth.user?.id??'local'"><slot/></div><div v-else class="cm-auth-shell"><aside class="cm-auth-intro"><span class="cm-eyebrow">CARDMIGRATOR</span><h1>从 Vue 到 San，<br/>让迁移有据可循。</h1><p>结构化语义提取 · 模型生成 · 多维评估 · 有界修复</p><div class="cm-auth-note">受邀账号工作台<br/>任务、源码和报告按账号隔离。<br/>仅提交你可信并有权处理的源码。</div></aside><main class="cm-auth-card"><template v-if="auth.user?.must_change_password"><h1>首次登录，请更新密码</h1><AccountPassword/><button @click="logout">退出登录</button></template><template v-else><span class="cm-eyebrow">WELCOME BACK</span><h1>登录迁移工作台</h1><p class="cm-help">使用管理员分配的账号；无需模型密钥或本地写入令牌。</p><p v-if="auth.message" class="cm-alert info" role="status">{{auth.message}}</p><div v-if="error" class="cm-alert danger cm-auth-error" role="alert"><span class="cm-auth-error-text">{{error}}</span><button class="cm-auth-reconnect" type="button" @click="connect">重新连接</button></div><form v-if="auth.ready" class="cm-account-form cm-login-form" @submit.prevent="submit"><label>账号<input v-model="username" name="username" autocomplete="username" required maxlength="64" placeholder="输入账号"/></label><label>密码<input v-model="password" name="password" type="password" autocomplete="current-password" required maxlength="128"/></label><button class="cm-primary" :disabled="busy">{{busy?'正在登录…':'登录'}}</button></form><p v-else class="cm-help">正在连接服务…</p><p class="cm-help">未开放自行注册。忘记密码请联系管理员。</p></template></main></div></template>
