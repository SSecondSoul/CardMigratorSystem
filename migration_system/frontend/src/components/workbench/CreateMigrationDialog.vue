<script setup lang="ts">
import {onMounted,onBeforeUnmount,ref,computed} from 'vue'
import UiIcon from '../UiIcon.vue'
import type {MigrationDraft} from '../../lib/migration.ts'
const props=defineProps<{draft:MigrationDraft;sessionReady:boolean;busy:boolean;canSubmit:boolean;error:string}>()
const emit=defineEmits<{close:[];submit:[]}>()
const dialog=ref<HTMLDialogElement|null>(null),uploadError=ref(''),dragging=ref(false)
const bytes=computed(()=>new TextEncoder().encode(props.draft.source).length)
const submitHint=computed(()=>!props.draft.source.trim()?'请先上传或粘贴 Vue 源码。':bytes.value>262144?'源码超过 256 KiB，请缩减后提交。':!props.sessionReady?'本地会话尚未就绪，请检查 API 服务或刷新连接状态。':'')
async function read(file?:File) {
  if(!file)return
  uploadError.value=''
  if(!file.name.endsWith('.vue')||file.size>262144){uploadError.value='请选择 256 KiB 以内的 .vue 单文件。';return}
  try{props.draft.source=new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer());props.draft.filename=file.name;if(!props.draft.name)props.draft.name=file.name.replace(/\.vue$/,'')}
  catch{uploadError.value='文件不是有效的 UTF-8 文本。'}
}
function drop(event:DragEvent){dragging.value=false;void read(event.dataTransfer?.files[0])}
onMounted(()=>{dialog.value?.showModal();document.body.classList.add('cm-dialog-open')})
onBeforeUnmount(()=>document.body.classList.remove('cm-dialog-open'))
</script>
<template>
  <dialog ref="dialog" class="cm-dialog" aria-labelledby="create-title" @cancel.prevent="!busy&&emit('close')" @click.self="!busy&&emit('close')">
    <form @submit.prevent="emit('submit')">
      <header class="cm-dialog-header"><div><span class="cm-eyebrow">NEW MIGRATION</span><h2 id="create-title">新建迁移任务</h2><p>提交 Vue 源码，使用真实模型与多维评估完成迁移。</p></div><button type="button" class="cm-icon-button" aria-label="关闭新建迁移" :disabled="busy" @click="emit('close')"><UiIcon name="close"/></button></header>
      <fieldset class="cm-dialog-body" :disabled="busy">
        <div v-if="error||uploadError" role="alert" class="cm-alert danger">{{uploadError||error}}</div>
        <div class="cm-form-two"><label>任务名称<input v-model="draft.name" maxlength="120" placeholder="例如：搜索结果卡片迁移" /></label><label>文件名<input v-model="draft.filename" required placeholder="SearchCard.vue" /></label></div>
        <label class="cm-drop-zone" :class="{dragging}" @dragover.prevent="dragging=true" @dragleave="dragging=false" @drop.prevent="drop"><UiIcon name="upload" :size="28"/><strong>点击选择 Vue 文件，或拖拽到这里</strong><span>单文件 · UTF-8 · 最大 256 KiB</span><input type="file" accept=".vue" aria-label="上传 Vue 单文件" @change="read(($event.target as HTMLInputElement).files?.[0])" /></label>
        <label><span class="cm-between">Vue 源码 <small :class="{danger:bytes>262144}">{{bytes.toLocaleString()}} / 262,144 B</small></span><textarea v-model="draft.source" rows="8" spellcheck="false" placeholder="或在这里粘贴完整的 template、script 和 style…" required /></label>
        <div class="cm-form-two"><label>迁移策略<input value="SSM ＋ 有界修复" readonly aria-label="迁移策略" /></label><label>最大修复轮数<select v-model.number="draft.rounds"><option v-for="n in [0,1,2,3]" :key="n" :value="n">{{n}} 轮</option></select></label></div>
        <details class="cm-details"><summary>评估配置 <span>props 与代表性交互</span><UiIcon name="chevron" :size="16"/></summary><div class="cm-form-two"><label>props JSON<textarea v-model="draft.propsText" rows="4" spellcheck="false" /></label><label>交互 JSON<textarea v-model="draft.actionsText" rows="4" spellcheck="false" /></label></div><p class="cm-help">没有交互场景请保留 []，报告将显示“未测试”，不会视为交互通过。</p></details>
        <p class="cm-help">创建任务后将执行源码并调用模型，请仅提交可信源码；模型调用可能产生费用。</p>
        <p v-if="submitHint" class="cm-help" role="status">{{submitHint}}</p>
      </fieldset>
      <footer class="cm-dialog-footer"><span>写入请求不自动重试 · 原源码保持不变</span><button type="button" :disabled="busy" @click="emit('close')">取消</button><button class="cm-primary" type="submit" :disabled="!canSubmit"><UiIcon :name="busy?'refresh':'plus'" :size="17"/>{{busy?'正在提交…':'创建真实迁移任务'}}</button></footer>
    </form>
  </dialog>
</template>
