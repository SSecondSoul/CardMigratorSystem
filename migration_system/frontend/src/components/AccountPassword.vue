<script setup lang="ts">
import {ref} from 'vue'
import {changePassword} from '../composables/useAuth.ts'
import {errorText} from '../lib/api.ts'
const current=ref(''),password=ref(''),repeat=ref(''),busy=ref(false),error=ref('')
async function submit(){if(busy.value)return;error.value='';if(password.value!==repeat.value){error.value='两次新密码不一致。';return}busy.value=true;try{await changePassword(current.value,password.value)}catch(e){error.value=errorText(e)}finally{busy.value=false;current.value='';password.value='';repeat.value=''}}
</script>
<template><form class="cm-account-form" @submit.prevent="submit"><h2>修改密码</h2><p class="cm-help">12–128 个字符；修改后需要重新登录，所有旧会话都会失效。</p><div v-if="error" class="cm-alert danger" role="alert">{{error}}</div><label>当前密码<input v-model="current" type="password" required maxlength="128" autocomplete="current-password"/></label><label>新密码<input v-model="password" type="password" required minlength="12" maxlength="128" autocomplete="new-password"/></label><label>再次输入新密码<input v-model="repeat" type="password" required minlength="12" maxlength="128" autocomplete="new-password"/></label><button class="cm-primary" :disabled="busy">{{busy?'正在更新…':'更新密码并退出旧会话'}}</button></form></template>
