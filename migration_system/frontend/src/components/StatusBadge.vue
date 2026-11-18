<script setup lang="ts">
import {migrationStatuses,dimensionStatus,tone} from '../lib/migration.ts'
import UiIcon from './UiIcon.vue'
defineProps<{status?:string;label?:string}>()
</script>
<template><span class="cm-status" :class="tone(status)"><span v-if="status==='running'" class="cm-spinner"/><UiIcon v-else :name="tone(status)==='success'?'check':tone(status)==='danger'?'warning':tone(status)==='warning'?'clock':'info'" :size="14"/>{{label??migrationStatuses[status??'']??dimensionStatus[status??'']??'未评估'}}</span></template>
