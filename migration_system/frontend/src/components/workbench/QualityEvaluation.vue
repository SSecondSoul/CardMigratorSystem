<script setup lang="ts">
import {computed,ref} from 'vue'
import UiIcon from '../UiIcon.vue'
import StatusBadge from '../StatusBadge.vue'
import EvidenceComparison from './EvidenceComparison.vue'
import {percent,numeric,dimensionLabels,evidenceDifferences,type MigrationReport} from '../../lib/migration.ts'
const props=defineProps<{report:MigrationReport;images:Record<string,string>;loading:boolean;error:string}>()
const assessment=computed(()=>props.report.assessment),expanded=ref(false)
const diagnostics=computed(()=>assessment.value?.diagnostics??[])
const differences=computed(()=>evidenceDifferences(assessment.value)),differenceLimit=ref(5)
const cards=computed(()=>[
 {label:'结构一致性',icon:'structure',value:assessment.value?.dimensions.structure==='not_run'?'—':percent(assessment.value?.dom_ted?.similarity),status:assessment.value?.dimensions.structure,detail:assessment.value?.thresholds?`一致性阈值 >${percent(assessment.value.thresholds.structure,0)}`:'等待真实评估'},
 {label:'UI 还原度',icon:'monitor',value:assessment.value?.dimensions.visual==='not_run'?'—':numeric(assessment.value?.ui_restoration)+'%',status:assessment.value?.dimensions.visual,detail:assessment.value?.thresholds?`还原度阈值 >${percent(assessment.value.thresholds.ui,0)}`:'等待真实评估'},
 {label:'像素差异率',icon:'grid',value:assessment.value?.dimensions.visual==='not_run'?'—':percent(assessment.value?.different_pixel_ratio),status:assessment.value?.dimensions.visual,detail:assessment.value?.thresholds?`像素目标 <${percent(assessment.value.thresholds.pixel_difference,0)}`:'等待真实评估'},
 {label:'代表性交互',icon:'cursor',value:null,status:assessment.value?.dimensions.interaction??'not_run',detail:props.report.request.actions?.length?`已配置 ${props.report.request.actions.length} 个场景`:'尚未配置交互场景'},
])
</script>
<template>
  <div class="cm-metrics"><article v-for="card in cards" :key="card.label" class="cm-metric"><div><UiIcon :name="card.icon"/><h3>{{card.label}}</h3></div><strong v-if="card.value!==null" class="cm-metric-value">{{card.value==='—%'?'—':card.value}}</strong><StatusBadge v-else :status="card.status"/><p><span v-if="card.status==='pass'" class="cm-tiny-check">✓</span>{{card.detail}}</p></article></div>
  <EvidenceComparison :images="images" :assessment="assessment" :runtime="report.request.runtime" :loading="loading" :error="error"/>
  <section class="cm-semantic-section"><header class="cm-between"><h3>结构与语义检查</h3><button class="cm-text-button" :aria-expanded="expanded" @click="expanded=!expanded">{{expanded?'收起检查详情':'展开检查详情'}}<UiIcon name="chevron" :size="15"/></button></header>
    <div class="cm-semantic-grid"><div v-for="key in ['static','compile_runtime','structure','source_baseline']" :key="key"><UiIcon :name="key==='static'?'link':key==='compile_runtime'?'code':'layers'"/><div><h4>{{dimensionLabels[key]}}</h4><StatusBadge :status="assessment?.dimensions[key]"/></div></div></div>
    <p class="cm-help"><UiIcon name="info" :size="14"/>静态检查通过不代表交互已验证；所有结论仅适用于当前 props 与已配置场景。</p>
    <div v-if="expanded" class="cm-detail-grid"><div><span>模板 AST 相似度</span><strong>{{assessment?.dimensions.structure==='not_run'?'—':percent(assessment?.structure_ted?.similarity,2)}}</strong></div><div><span>有效 DOM 相似度</span><strong>{{assessment?.dimensions.structure==='not_run'?'—':percent(assessment?.dom_ted?.similarity,2)}}</strong></div><div><span>原始 DOM 相似度</span><strong>{{assessment?.dimensions.structure==='not_run'?'—':percent(assessment?.raw_dom_ted?.similarity,2)}}</strong></div><div><span>初始控件实时状态</span><strong>{{assessment?.initial_control_state?assessment.initial_control_state.equal?'一致':'不一致':'未采集'}}</strong></div></div>
  </section>
  <section v-if="differences.length" class="cm-diagnostics"><header class="cm-between"><h3>差异明细 <span class="cm-count warning">已记录 {{differences.length}} 条</span></h3><span class="cm-muted">{{assessment?.styles?.truncated?'样式证据有截断':'按实际节点路径定位'}}</span></header><div class="cm-table-scroll cm-difference-table"><table class="cm-table"><thead><tr><th>类型</th><th>位置／属性</th><th>Vue 源值</th><th>San 结果</th></tr></thead><tbody><tr v-for="(item,index) in differences.slice(0,differenceLimit)" :key="index"><td>{{item.kind}}</td><td><code>{{item.path}}</code><small>{{item.property}}</small></td><td><code>{{item.source}}</code></td><td><code>{{item.target}}</code></td></tr></tbody></table></div><button v-if="differenceLimit<differences.length" class="cm-text-button" @click="differenceLimit+=10">再显示 10 条 · 剩余 {{differences.length-differenceLimit}} 条</button><p class="cm-help">按子节点路径匹配；结构错位可能连带多条样式差异，不等同于独立缺陷数。</p></section>
  <section class="cm-diagnostics"><header class="cm-between"><h3>原始检查诊断 <span class="cm-count" :class="{warning:diagnostics.length}">{{diagnostics.length}} 项</span></h3></header>
    <div v-if="!assessment" class="cm-empty compact">尚未产生评估报告。</div><p v-else-if="!diagnostics.length" class="cm-no-diagnostics">当前报告无诊断项。</p>
    <div v-else class="cm-diagnostic-list"><details v-for="(item,i) in diagnostics" :key="i"><summary><UiIcon name="warning" :size="17"/><code>{{item.code}}</code><span>{{item.message}}</span><UiIcon name="chevron" :size="15"/></summary><pre>{{JSON.stringify(item,null,2)}}</pre></details></div>
  </section>
</template>
