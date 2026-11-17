<script setup lang="ts">
import { defineAsyncComponent, ref } from 'vue'
import MigrationWorkbench from './components/MigrationWorkbench.vue'

// Historical control fixtures do not mount or poll during real migrations.
const DevelopmentWorkbench = defineAsyncComponent(() => import('./components/DevelopmentWorkbench.vue'))
const history = ref(false)
</script>

<template>
  <nav class="mode-switch" aria-label="工作台入口">
    <button type="button" :aria-pressed="!history" @click="history=false">迁移工作台</button>
    <button type="button" :aria-pressed="history" @click="history=true">开发验证与历史（不计迁移结果）</button>
  </nav>
  <DevelopmentWorkbench v-if="history" />
  <MigrationWorkbench v-else />
</template>
