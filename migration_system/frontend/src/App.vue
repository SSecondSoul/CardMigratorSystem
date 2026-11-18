<script setup lang="ts">
import {defineAsyncComponent,ref,watch} from 'vue'
import MigrationWorkbench from './components/MigrationWorkbench.vue'
import UiIcon from './components/UiIcon.vue'
import type {WorkspaceView} from './lib/migration.ts'
import './workbench.css'
import AuthGate from './components/AuthGate.vue'
import {auth} from './composables/useAuth.ts'
const AccountPanel=defineAsyncComponent(()=>import('./components/AccountPanel.vue'))
const AdminUsersPanel=defineAsyncComponent(()=>import('./components/AdminUsersPanel.vue'))
const DevelopmentWorkbench=defineAsyncComponent(()=>import('./components/DevelopmentWorkbench.vue'))
const view=ref<WorkspaceView>('workbench'),createSequence=ref(0),refreshSequence=ref(0),context=ref('迁移工作台'),connected=ref(false)
const names:Record<WorkspaceView,string>={workbench:'迁移工作台',records:'任务记录',settings:'设置与连接',development:'开发验证',account:'我的账号',admin:'用户管理'}
function create(){view.value='workbench';createSequence.value++}
watch(()=>auth.user?.id,()=>{view.value='workbench';context.value='迁移工作台'})
</script>
<template>
  <AuthGate><div class="cm-app"><a class="cm-skip" href="#cm-main">跳至主内容</a><aside class="cm-sidebar"><a class="cm-brand" href="#" @click.prevent="view='workbench'"><span class="cm-brand-mark"><UiIcon name="arrow" :size="27"/></span><span><strong>CardMigrator</strong><small>前端技术栈迁移</small></span></a><button class="cm-primary cm-new-task" @click="create"><UiIcon name="plus" :size="21"/>新建迁移</button>
    <nav aria-label="主要导航"><button v-for="item in [{id:'workbench',label:'迁移工作台',icon:'monitor'},{id:'records',label:'任务记录',icon:'history'}]" :key="item.id" :class="{active:view===item.id}" :aria-current="view===item.id?'page':undefined" @click="view=item.id as WorkspaceView"><UiIcon :name="item.icon"/>{{item.label}}</button></nav>
    <div class="cm-sidebar-bottom"><nav aria-label="系统导航"><button v-if="auth.mode==='local'" :class="{active:view==='development'}" @click="view='development'"><UiIcon name="code"/>开发验证</button><button v-if="auth.mode==='multi_user'" @click="view='account'"><UiIcon name="user"/>我的账号</button><button v-if="auth.user?.role==='admin'" @click="view='admin'"><UiIcon name="settings"/>用户管理</button><button :class="{active:view==='settings'}" @click="view='settings'"><UiIcon name="settings"/>设置与连接</button></nav><button class="cm-local-space" @click="view=auth.mode==='multi_user'?'account':'settings'"><span class="cm-dot connected"/>{{auth.user?.display_name??'本地工作空间'}}<UiIcon name="chevron" :size="16"/></button></div>
  </aside><div class="cm-app-main"><header class="cm-topbar"><div class="cm-breadcrumb"><span>迁移工作台</span><span>/</span><strong>{{view==='workbench'?context:names[view]}}</strong><span class="cm-local-badge">本地迁移系统</span></div><div class="cm-topbar-actions"><span class="cm-service-status"><span class="cm-dot" :class="connected?'connected':'offline'"/>{{connected?'API 已连接':'API 未连接'}}</span><button class="cm-icon-button" aria-label="刷新服务和任务" @click="refreshSequence++"><UiIcon name="refresh" :size="21"/></button><button class="cm-avatar" aria-label="打开设置与连接" @click="view='settings'"><UiIcon name="user" :size="20"/></button></div></header>
    <main id="cm-main"><MigrationWorkbench v-show="!['development','account','admin'].includes(view)" :view="view" :create-sequence="createSequence" :refresh-sequence="refreshSequence" @context="context=$event" @connection="connected=$event" @navigate="view=$event"/><AccountPanel v-if="view==='account'&&auth.user"/><AdminUsersPanel v-if="view==='admin'&&auth.user?.role==='admin'"/><section v-if="view==='development'&&auth.mode==='local'" class="cm-development"><div class="cm-alert warning">开发夹具仅用于验证控制流程，不计作真实组件迁移结果。</div><DevelopmentWorkbench/></section></main>
  </div></div></AuthGate>
</template>
