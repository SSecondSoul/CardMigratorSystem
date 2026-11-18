<script setup lang="ts">
import {ref,onMounted} from 'vue'
import {auth,logout} from '../composables/useAuth.ts'
import {MigrationApi} from '../lib/migration-api.ts'
import {errorText} from '../lib/api.ts'
import AccountPassword from './AccountPassword.vue'
const api=new MigrationApi(),usage=ref<any>(null),error=ref(''),busy=ref(false)
async function load(){try{usage.value=await api.get('/api/v1/auth/usage')}catch(e){error.value=errorText(e)}}
async function exit(){busy.value=true;try{await logout()}catch(e){error.value=errorText(e)}finally{busy.value=false}}
onMounted(load)
</script>
<template><section class="cm-account-page"><div class="cm-page-heading"><div><span class="cm-eyebrow">MY ACCOUNT</span><h1>我的账号</h1><p>{{auth.user?.display_name}} · {{auth.user?.username}} · {{auth.user?.role==='admin'?'管理员':'用户'}}</p></div><button :disabled="busy" @click="exit">退出登录</button></div><div v-if="error" class="cm-alert danger" role="alert">{{error}}</div><div class="cm-settings-grid"><section class="cm-panel cm-padded"><h2>我的额度</h2><p class="cm-help">按 UTC 日统计。Token 为已知实际用量；停止线不是硬计费上限。</p><dl v-if="usage" class="cm-facts"><dt>今日任务</dt><dd>{{usage.used.jobs}} / {{usage.limits.daily_jobs}}</dd><dt>排队／执行中</dt><dd>{{usage.used.active_jobs}} / {{usage.limits.max_active_jobs}}</dd><dt>今日模型调用</dt><dd>{{usage.used.calls}} / {{usage.limits.daily_model_calls}}</dd><dt>已知 Tokens</dt><dd>{{usage.used.known_tokens}} / {{usage.limits.daily_tokens_soft}}</dd><dt>已注册源码</dt><dd>{{usage.used.source_bytes}} / {{usage.limits.storage_bytes}} B</dd></dl><p class="cm-help">源码额度不包括生成代码、截图等产物；它们仍需服务器磁盘监控和保留策略。未知调用／未知用量会阻止后续模型调用，不自动重发。</p><button @click="load">刷新用量</button></section><section class="cm-panel cm-padded"><AccountPassword/></section></div></section></template>
