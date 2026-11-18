<script setup lang="ts">
import {ref,watch,computed} from 'vue'
import UiIcon from '../UiIcon.vue'
import type {Assessment,MigrationReport} from '../../lib/migration.ts'
import {numeric} from '../../lib/migration.ts'
const props=defineProps<{images:Record<string,string>;assessment:Assessment|null;runtime?:MigrationReport['request']['runtime'];loading:boolean;error:string}>()
const mode=ref('side'),opacity=ref(50)
const hasPair=computed(()=>!!props.images.vue&&!!props.images.san)
const viewport=computed(()=>props.runtime?.browser??props.runtime)
const ssim=computed(()=>props.assessment?.dimensions.visual==='not_run'?'—':numeric(props.assessment?.ssim,4))
watch(()=>props.images,()=>{if(mode.value==='diff'&&!props.images.heatmap)mode.value='side'})
</script>
<template>
  <section class="cm-preview">
    <header class="cm-between"><div><h3>界面还原对比</h3><p>同一评估视口 <span v-if="viewport?.width">· {{viewport.width}} × {{viewport.height}}</span> · SSIM {{ssim}}</p></div><div class="cm-segment" aria-label="截图比较方式"><button :class="{active:mode==='side'}" :aria-pressed="mode==='side'" @click="mode='side'">并排</button><button :class="{active:mode==='overlay'}" :aria-pressed="mode==='overlay'" :disabled="!hasPair" @click="mode='overlay'">叠加</button><button :class="{active:mode==='diff'}" :aria-pressed="mode==='diff'" :disabled="!images.heatmap" @click="mode='diff'">差异</button></div></header>
    <div v-if="loading" class="cm-empty compact"><span class="cm-spinner"/>正在读取已登记的评估截图…</div>
    <div v-else-if="error" class="cm-alert danger">{{error}}</div>
    <template v-else-if="hasPair">
      <div v-if="mode==='side'" class="cm-image-pair"><figure v-for="side in ['vue','san']" :key="side"><figcaption><span class="cm-dot" :class="side"/>{{side==='vue'?'源界面 · Vue':'迁移结果 · San'}}<a :href="images[side]" target="_blank" rel="noopener" :aria-label="'查看'+side+'原始截图'">查看原图 ↗</a></figcaption><div class="cm-image-scroll"><img :src="images[side]" :alt="side+' 实际评估截图'" /></div></figure></div>
      <div v-else-if="mode==='overlay'" class="cm-overlay-panel"><div class="cm-overlay-controls"><span>Vue</span><input v-model="opacity" type="range" min="0" max="100" aria-label="San 截图叠加透明度"/><span>San {{opacity}}%</span></div><div class="cm-image-scroll cm-overlay"><img :src="images.vue" alt="Vue 底图"/><img :src="images.san" alt="San 叠加图" :style="{opacity:Number(opacity)/100}"/></div></div>
      <figure v-else class="cm-diff-image"><figcaption>真实像素差异热图 <a :href="images.heatmap" target="_blank" rel="noopener">查看原图 ↗</a></figcaption><div class="cm-image-scroll"><img :src="images.heatmap" alt="实际像素差异热图"/></div></figure>
    </template>
    <div v-else class="cm-empty compact"><UiIcon name="image" :size="30"/><strong>暂无可用评估截图</strong><p>生成或浏览器评估完成后显示真实截图，不使用示例图代替。</p></div>
  </section>
</template>
