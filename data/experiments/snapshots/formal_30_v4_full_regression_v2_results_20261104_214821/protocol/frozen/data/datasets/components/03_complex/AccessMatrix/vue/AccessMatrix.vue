<template>
  <main class="access-matrix">
    <header class="matrix-header">
      <div><span class="eyebrow">访问治理</span><h1>{{ title }}</h1><p>按角色和资源维护最小权限集合</p></div>
      <div class="header-actions">
        <button type="button" class="secondary" @click="toggleAudit">{{ showAudit ? '隐藏审计' : '查看审计' }}</button>
        <button type="button" :disabled="locked || !dirty" @click="save">{{ saveState === 'saving' ? '保存中' : '保存变更' }}</button>
      </div>
    </header>
    <section class="matrix-stats">
      <article><span>已授权单元</span><strong>{{ grantedCount }}</strong></article>
      <article><span>授权覆盖率</span><strong>{{ coverage }}%</strong></article>
      <article><span>当前角色</span><strong>{{ selectedRoleName }}</strong></article>
    </section>
    <section class="matrix-toolbar">
      <label>筛选资源<input :value="query" placeholder="名称或分组" @input="updateQuery" /></label>
      <div class="role-tabs">
        <button v-for="role in roles" :key="role.id" type="button" :class="{ active: selectedRoleId === role.id }" @click="selectRole(role.id)">{{ role.name }}</button>
      </div>
      <button type="button" class="secondary" :disabled="locked" @click="setAllForRole(true)">当前角色全选</button>
      <button type="button" class="secondary" :disabled="locked" @click="setAllForRole(false)">当前角色清空</button>
    </section>
    <section class="matrix-shell">
      <table>
        <thead>
          <tr><th>资源</th><th v-for="role in roles" :key="role.id"><span>{{ role.name }}</span><button type="button" :disabled="locked" @click="toggleColumn(role.id)">整列切换</button></th><th>批量</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in matrixRows" :key="row.id">
            <th><strong>{{ row.name }}</strong><small>{{ row.group }}</small></th>
            <td v-for="cell in row.cells" :key="cell.roleId">
              <button type="button" class="grant-cell" :class="{ granted: cell.granted }" :disabled="locked" @click="toggleCell(row.id, cell.roleId)">{{ cell.granted ? '允许' : '拒绝' }}</button>
            </td>
            <td><button type="button" class="row-toggle" :disabled="locked" @click="toggleRow(row.id)">整行切换</button></td>
          </tr>
        </tbody>
      </table>
      <div v-if="!matrixRows.length" class="empty-matrix">没有匹配资源</div>
    </section>
    <aside v-if="showAudit" class="audit-panel">
      <div><strong>最近操作</strong><button type="button" @click="clearAudit">清空</button></div>
      <ol><li v-for="entry in audit" :key="entry.id"><span>{{ entry.message }}</span><small>{{ entry.time }}</small></li></ol>
      <p v-if="!audit.length">暂无操作记录</p>
    </aside>
    <footer class="matrix-footer"><span>{{ locked ? '矩阵已锁定' : dirty ? '存在未保存更改' : '所有更改已保存' }}</span><span>最近保存：{{ lastSaved || '尚未保存' }}</span></footer>
  </main>
</template>

<script>
module.exports = {
  name: 'AccessMatrix',
  props: {
    title: { type: String, default: '项目空间权限' },
    roles: { type: Array, default: function () { return [{ id: 'owner', name: '管理员' }, { id: 'editor', name: '编辑者' }, { id: 'viewer', name: '访客' }]; } },
    resources: { type: Array, default: function () { return [{ id: 'docs', name: '文档库', group: '内容' }, { id: 'data', name: '数据集', group: '资产' }, { id: 'runs', name: '实验任务', group: '运行' }, { id: 'reports', name: '评估报告', group: '内容' }, { id: 'settings', name: '系统设置', group: '管理' }]; } },
    initialGrants: { type: Object, default: function () { return { owner: ['docs', 'data', 'runs', 'reports', 'settings'], editor: ['docs', 'data', 'runs'], viewer: ['docs', 'reports'] }; } },
    locked: { type: Boolean, default: false }
  },
  data() {
    return {
      grants: JSON.parse(JSON.stringify(this.initialGrants)),
      query: '',
      selectedRoleId: this.roles[0].id,
      audit: [],
      dirty: false,
      saveState: 'idle',
      lastSaved: '',
      showAudit: false,
      autosaveTimer: null,
      nextAuditId: 1
    };
  },
  computed: {
    filteredResources() {
      const query = this.query.trim().toLowerCase();
      return this.resources.filter((resource) => !query || resource.name.toLowerCase().includes(query) || resource.group.toLowerCase().includes(query));
    },
    matrixRows() {
      return this.filteredResources.map((resource) => ({
        id: resource.id,
        name: resource.name,
        group: resource.group,
        cells: this.roles.map((role) => ({ roleId: role.id, granted: (this.grants[role.id] || []).indexOf(resource.id) >= 0 }))
      }));
    },
    grantedCount() { return this.roles.reduce((sum, role) => sum + (this.grants[role.id] || []).length, 0); },
    coverage() { return Math.round((this.grantedCount / (this.roles.length * this.resources.length)) * 100); },
    selectedRoleName() { const role = this.roles.find((item) => item.id === this.selectedRoleId); return role ? role.name : '--'; }
  },
  mounted() { this.scheduleAutosave(); },
  beforeDestroy() { clearTimeout(this.autosaveTimer); },
  methods: {
    updateQuery(event) { this.query = event.target.value; },
    selectRole(id) { this.selectedRoleId = id; },
    hasGrant(roleId, resourceId) { return (this.grants[roleId] || []).indexOf(resourceId) >= 0; },
    setGrant(roleId, resourceId, granted) {
      const current = (this.grants[roleId] || []).slice();
      const next = granted ? Array.from(new Set(current.concat(resourceId))) : current.filter((id) => id !== resourceId);
      this.$set(this.grants, roleId, next);
    },
    toggleCell(resourceId, roleId) {
      const granted = !this.hasGrant(roleId, resourceId);
      this.setGrant(roleId, resourceId, granted);
      this.record(`${roleId} 对 ${resourceId} ${granted ? '授权' : '撤权'}`);
      this.changed();
    },
    toggleRow(resourceId) {
      const grantAll = this.roles.some((role) => !this.hasGrant(role.id, resourceId));
      this.roles.forEach((role) => this.setGrant(role.id, resourceId, grantAll));
      this.record(`${resourceId} 整行${grantAll ? '授权' : '清空'}`);
      this.changed();
    },
    toggleColumn(roleId) {
      const grantAll = this.resources.some((resource) => !this.hasGrant(roleId, resource.id));
      this.$set(this.grants, roleId, grantAll ? this.resources.map((resource) => resource.id) : []);
      this.record(`${roleId} 整列${grantAll ? '授权' : '清空'}`);
      this.changed();
    },
    setAllForRole(granted) {
      this.$set(this.grants, this.selectedRoleId, granted ? this.resources.map((resource) => resource.id) : []);
      this.record(`${this.selectedRoleId} ${granted ? '全选' : '清空'}`);
      this.changed();
    },
    record(message) {
      this.audit.unshift({ id: this.nextAuditId++, message: message, time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) });
      this.audit = this.audit.slice(0, 8);
    },
    changed() { this.dirty = true; this.scheduleAutosave(); this.$emit('change', JSON.parse(JSON.stringify(this.grants))); },
    scheduleAutosave() {
      clearTimeout(this.autosaveTimer);
      if (!this.locked && this.dirty) this.autosaveTimer = setTimeout(this.save, 800);
    },
    async save() {
      if (this.locked || !this.dirty) return;
      this.saveState = 'saving';
      await Promise.resolve();
      this.dirty = false; this.saveState = 'saved';
      this.lastSaved = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
      this.$emit('save', JSON.parse(JSON.stringify(this.grants)));
    },
    toggleAudit() { this.showAudit = !this.showAudit; },
    clearAudit() { this.audit = []; }
  }
};
</script>

<style scoped>
.access-matrix { width: 860px; padding: 24px; border: 1px solid #cbd5e1; border-radius: 7px; background: #f8fafc; color: #172026; font-family: Arial, sans-serif; }
.matrix-header { display: flex; justify-content: space-between; gap: 24px; }
.matrix-header h1 { margin: 3px 0; font-size: 24px; }
.matrix-header p, .eyebrow { color: #64748b; font-size: 12px; }
.header-actions { display: flex; gap: 8px; }
.access-matrix button { padding: 7px 10px; border: 1px solid #1d4ed8; border-radius: 4px; background: #1d4ed8; color: #ffffff; cursor: pointer; }
.access-matrix button.secondary { border-color: #94a3b8; background: #ffffff; color: #334155; }
.matrix-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 20px 0; }
.matrix-stats article { padding: 12px; border-left: 3px solid #1d4ed8; background: #ffffff; }
.matrix-stats span { display: block; color: #64748b; font-size: 12px; }
.matrix-stats strong { font-size: 21px; }
.matrix-toolbar { display: grid; grid-template-columns: 1fr auto auto; gap: 8px; align-items: end; margin-bottom: 12px; }
.matrix-toolbar label { display: grid; gap: 5px; color: #475569; font-size: 12px; }
.matrix-toolbar input { padding: 8px; border: 1px solid #94a3b8; }
.role-tabs { grid-column: 1 / -1; display: flex; gap: 5px; }
.role-tabs button { background: #ffffff; color: #334155; border-color: #cbd5e1; }
.role-tabs button.active { background: #dbeafe; border-color: #2563eb; color: #1e40af; }
.matrix-shell { overflow-x: auto; border: 1px solid #d1d5db; background: #ffffff; }
.matrix-shell table { width: 100%; border-collapse: collapse; }
.matrix-shell th, .matrix-shell td { padding: 9px; border: 1px solid #e5e7eb; text-align: center; }
.matrix-shell th:first-child { text-align: left; }
.matrix-shell th small { display: block; color: #64748b; }
.matrix-shell thead { background: #eff6ff; }
.matrix-shell thead th span { display: block; margin-bottom: 6px; }
.matrix-shell thead button, .row-toggle { padding: 4px 6px; border-color: #94a3b8; background: #ffffff; color: #475569; font-size: 11px; }
.grant-cell { min-width: 58px; border-color: #cbd5e1 !important; background: #f8fafc !important; color: #64748b !important; }
.grant-cell.granted { border-color: #16a34a !important; background: #dcfce7 !important; color: #166534 !important; }
.empty-matrix { padding: 28px; text-align: center; color: #94a3b8; }
.audit-panel { margin-top: 14px; padding: 14px; border: 1px solid #fde68a; background: #fffbeb; }
.audit-panel > div, .audit-panel li { display: flex; justify-content: space-between; gap: 16px; }
.audit-panel ol { padding-left: 20px; }
.audit-panel li { margin: 6px 0; }
.audit-panel small { color: #78716c; }
.matrix-footer { display: flex; justify-content: space-between; margin-top: 14px; color: #64748b; font-size: 12px; }
</style>
