<script setup lang="ts">
import {ref,reactive,onMounted,nextTick} from 'vue'
import {MigrationApi} from '../lib/migration-api.ts'
import {errorText} from '../lib/api.ts'
import {dateTime,migrationStatuses} from '../lib/migration.ts'
import {validateAccountDraft} from '../lib/account-form.ts'
import type {AccountField} from '../lib/account-form.ts'
const api=new MigrationApi(),users=ref<any[]>([]),logs=ref<any[]>([]),jobs=ref<any[]>([]),error=ref(''),notice=ref(''),busy=ref(false),editing=ref(''),target=ref<any>(null)
const form=reactive({username:'',display_name:'',password:'',role:'user'}),limits=reactive<Record<string,number>>({}),adminPassword=ref(''),newPassword=ref('')
const createForm=ref<HTMLFormElement|null>(null),createErrors=reactive<Record<AccountField,string>>({username:'',display_name:'',password:'',role:''})
function checkCreateField(field:AccountField){createErrors[field]=validateAccountDraft(form)[field]}
function recheckCreateField(field:AccountField){if(createErrors[field])checkCreateField(field)}
const labels:Record<string,string>={max_active_jobs:'排队／执行中任务上限',daily_jobs:'每日任务上限',daily_model_calls:'每日模型调用上限',daily_tokens_soft:'每日 Token 停止线（非硬上限）',storage_bytes:'注册源码总字节上限'}
async function load(){try{const [u,a,j]=await Promise.all([api.get<any>('/api/v1/admin/users'),api.get<any>('/api/v1/admin/audit'),api.get<any>('/api/v1/migrations?scope=all')]);users.value=u.items;logs.value=a.items;jobs.value=j.items}catch(e){error.value=errorText(e)}}
async function write(action:()=>Promise<unknown>,message:string){if(busy.value)return;busy.value=true;error.value='';notice.value='';try{await action();notice.value=message;target.value=null;editing.value='';await load()}catch(e){error.value=errorText(e)}finally{busy.value=false;form.password='';adminPassword.value='';newPassword.value=''}}
function edit(row:any){editing.value=row.user.id;Object.assign(limits,row.usage.limits)}
function saveLimits(){void write(()=>api.post(`/api/v1/admin/users/${editing.value}/limits`,{...limits}),'用户额度已更新。')}
async function create(){
  if(busy.value)return
  Object.assign(createErrors,validateAccountDraft(form))
  if(Object.values(createErrors).some(Boolean)){
    await nextTick();createForm.value?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();return
  }
  await write(()=>api.post('/api/v1/admin/users',{...form}),'账号已创建；请将登录账号、临时密码及工作台地址单独告知用户。用户首次登录必须修改临时密码。')
}
function manage(){const id=target.value.id,payload=newPassword.value?{admin_password:adminPassword.value,new_password:newPassword.value}:{admin_password:adminPassword.value,is_active:!target.value.is_active};void write(()=>api.post(`/api/v1/admin/users/${id}`,payload),'账号已更新，旧会话已撤销。')}
onMounted(load)
</script>
<template><section class="cm-admin-page"><div class="cm-page-heading"><div><span class="cm-eyebrow">ADMINISTRATION</span><h1>用户与运行管理</h1><p>普通用户只访问自己的资源。当前列出最近 100 项任务／审计、最多 200 个账号，不是完整历史统计。</p></div><button @click="load">刷新</button></div><div v-if="error" role="alert" class="cm-alert danger">{{error}}</div><div v-if="notice" role="status" class="cm-alert info">{{notice}}</div><section class="cm-panel cm-padded"><h2>创建受邀账号</h2>
<p class="cm-help">填写下面 4 项后点击“创建账号”。带 * 的为必填项；创建成功后，将账号、临时密码和工作台地址通过安全渠道告知用户。</p>
<form ref="createForm" class="cm-admin-create" novalidate @submit.prevent="create">
  <label>登录账号 *
    <input v-model="form.username" name="username" required maxlength="64" autocomplete="off" placeholder="例如：zhangsan_01" :aria-invalid="!!createErrors.username" aria-describedby="cm-create-username-help cm-create-username-error" @blur="checkCreateField('username')" @input="recheckCreateField('username')"/>
    <small id="cm-create-username-help" class="cm-field-help">3–64 位，以英文字母开头，仅含字母、数字、下划线 _、点 . 或横线 -。不能用中文或空格，账号名不可重复。</small>
    <small v-if="createErrors.username" id="cm-create-username-error" class="cm-field-error" role="alert">{{createErrors.username}}</small>
  </label>
  <label>显示名称 *
    <input v-model="form.display_name" name="display_name" required maxlength="240" placeholder="例如：张三（可用中文）" :aria-invalid="!!createErrors.display_name" aria-describedby="cm-create-display-help cm-create-display-error" @blur="checkCreateField('display_name')" @input="recheckCreateField('display_name')"/>
    <small id="cm-create-display-help" class="cm-field-help">1–120 个字符，可使用中文，仅作为界面昵称；用户登录时仍需填写左侧的登录账号。</small>
    <small v-if="createErrors.display_name" id="cm-create-display-error" class="cm-field-error" role="alert">{{createErrors.display_name}}</small>
  </label>
  <label>临时密码 *
    <input v-model="form.password" name="temporary_password" type="password" required maxlength="256" autocomplete="new-password" placeholder="设置 12–128 个字符的临时密码" :aria-invalid="!!createErrors.password" aria-describedby="cm-create-password-help cm-create-password-error" @blur="checkCreateField('password')" @input="recheckCreateField('password')"/>
    <small id="cm-create-password-help" class="cm-field-help">12–128 个字符，建议使用随机密码。用户首次登录必须改密；创建后系统不会回显密码，请事先安全保存并单独告知用户。</small>
    <small v-if="createErrors.password" id="cm-create-password-error" class="cm-field-error" role="alert">{{createErrors.password}}</small>
  </label>
  <label>角色 *
    <select v-model="form.role" name="role" :aria-invalid="!!createErrors.role" aria-describedby="cm-create-role-help"><option value="user">普通用户（推荐）</option><option value="admin">管理员</option></select>
    <small id="cm-create-role-help" class="cm-field-help">一般选择普通用户，只能管理自己的任务。管理员可以管理账号、额度并查看所有用户的任务，请谨慎授予。</small>
    <small v-if="createErrors.role" class="cm-field-error" role="alert">{{createErrors.role}}</small>
  </label>
  <div class="cm-admin-create-actions"><button class="cm-primary" type="submit" :disabled="busy">{{busy?'正在创建…':'创建账号'}}</button><span class="cm-field-help">没有默认密码；不开放匿名注册。首次改密完成后，用户即可创建迁移任务。</span></div>
</form></section>
<section class="cm-panel cm-padded"><h2>账号与配额</h2><div class="cm-table-scroll"><table class="cm-table"><thead><tr><th>账号</th><th>状态</th><th>今日任务／调用／Tokens</th><th>操作</th></tr></thead><tbody><tr v-for="row in users" :key="row.user.id"><td>{{row.user.display_name}}<small>{{row.user.username}} · {{row.user.role}}</small></td><td>{{row.user.is_active?'启用':'禁用'}}<small v-if="row.user.must_change_password">首次登录需改密</small></td><td>{{row.usage?`${row.usage.used.jobs} / ${row.usage.used.calls} / ${row.usage.used.known_tokens}`:'—'}}</td><td><button v-if="row.usage" @click="edit(row)">额度</button> <button @click="target=row.user;newPassword='';adminPassword=''">禁用／启用／重置密码</button></td></tr></tbody></table></div><form v-if="editing" class="cm-form-two cm-admin-edit" @submit.prevent="saveLimits"><label v-for="(label,key) in labels" :key="key">{{label}}<input v-model.number="limits[key]" type="number" min="0" step="1" required/></label><div><button :disabled="busy" class="cm-primary">保存额度</button> <button type="button" @click="editing=''">取消</button></div></form><form v-if="target" class="cm-admin-edit cm-account-form" @submit.prevent="manage"><h3>操作账号：{{target.username}}</h3><label>你的管理员密码<input v-model="adminPassword" type="password" required maxlength="128" autocomplete="current-password"/></label><label>新临时密码（留空则{{target.is_active?'禁用':'启用'}}账号）<input v-model="newPassword" type="password" minlength="12" maxlength="128" autocomplete="new-password"/></label><div><button :disabled="busy" class="cm-primary">确认操作</button> <button type="button" @click="target=null">取消</button></div></form></section>
<section class="cm-panel cm-padded"><h2>最近任务与历史归档</h2><p class="cm-help">管理员可读取历史无所有者记录，但不会自动转给新用户；旧实现检查点仍不可跨版本恢复。</p><div class="cm-table-scroll"><table class="cm-table"><thead><tr><th>任务</th><th>状态</th><th>时间</th><th></th></tr></thead><tbody><tr v-for="job in jobs" :key="job.migration_id"><td>{{job.name}}<small>{{job.migration_id}}</small></td><td>{{migrationStatuses[job.status]??job.status}}</td><td>{{dateTime(job.created_at)}}</td><td><a :href="`/#migration=${job.migration_id}`">查看报告</a></td></tr></tbody></table></div></section>
<section class="cm-panel cm-padded"><h2>最近审计记录</h2><div class="cm-table-scroll"><table class="cm-table"><thead><tr><th>时间</th><th>操作</th><th>操作者</th><th>对象</th></tr></thead><tbody><tr v-for="log in logs" :key="log.id"><td>{{dateTime(log.created_at)}}</td><td>{{log.action}}</td><td>{{log.actor_id??'未登录／初始化'}}</td><td>{{log.target_id??'—'}}</td></tr></tbody></table></div></section></section></template>
