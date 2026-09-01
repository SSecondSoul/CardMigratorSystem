<template>
  <main class="operations-board">
    <header class="board-header">
      <div class="title-block">
        <span class="eyebrow">{{ owner }} · 项目</span>
        <h1>{{ title }}</h1>
        <p>最后更新 {{ lastUpdated }}</p>
      </div>
      <div class="header-actions">
        <button type="button" @click="refreshData">{{ loading ? '刷新中' : '刷新数据' }}</button>
        <button type="button" @click="exportReport">导出报告</button>
      </div>
    </header>
    <section class="summary-grid">
      <article v-for="metric in summaryCards" :key="metric.key" class="summary-card">
        <span>{{ metric.label }}</span>
        <strong>{{ metric.value }}</strong>
        <small>{{ metric.note }}</small>
      </article>
    </section>
    <section class="toolbar">
      <label>搜索<input :value="query" @input="updateQuery" placeholder="输入项目名称" /></label>
      <div class="filter-group">
        <button v-for="option in filters" :key="option.value" type="button" :class="{ active: filter === option.value }" @click="setFilter(option.value)">{{ option.label }}</button>
      </div>
      <button type="button" @click="changeSort">排序：{{ sortLabel }}</button>
    </section>
    <p v-if="errorMessage" class="error-banner">{{ errorMessage }}</p>
    <section class="record-panel">
      <div class="record-head"><span>项目</span><span>负责人</span><span>状态</span><span>评分</span></div>
      <article v-for="record in visibleRecords" :key="record.id" :class="['record-row', { selected: selectedId === record.id }]" @click="selectRecord(record)">
        <div><strong>{{ record.name }}</strong><small>更新于 {{ record.updatedAt }}</small></div>
        <span>{{ record.owner }}</span>
        <span class="status-badge" :class="record.status">{{ statusText(record.status) }}</span>
        <div class="score-cell"><strong>{{ record.value }}</strong><button v-if="record.status === 'warning'" type="button" @click.stop="acknowledge(record.id)">确认</button></div>
      </article>
      <div v-if="!visibleRecords.length" class="empty-panel"><strong>没有匹配记录</strong><p>调整搜索条件或状态筛选</p></div>
    </section>
    <footer class="board-footer">
      <span>第 {{ page }} / {{ totalPages }} 页，共 {{ filteredRecords.length }} 条</span>
      <div><button type="button" :disabled="page <= 1" @click="previousPage">上一页</button><button type="button" :disabled="page >= totalPages" @click="nextPage">下一页</button></div>
    </footer>
  </main>
</template>

<script>
module.exports = {
  name: 'ProjectOverview',
  props: {
    title: { type: String, default: '项目总览' },
    owner: { type: String, default: '运营中心' },
    refreshInterval: { type: Number, default: 30000 },
    initialRecords: { type: Array, default: function () { return []; } }
  },
  data() {
    return {
      records: this.initialRecords.length ? this.initialRecords.slice() : [
        { id: 1, name: '网站改版', status: 'active', owner: '陈晨', value: 84, updatedAt: '10:20' },
        { id: 2, name: '移动端升级', status: 'warning', owner: '林静', value: 73, updatedAt: '10:27' },
        { id: 3, name: '数据治理', status: 'stable', owner: '周明', value: 62, updatedAt: '10:34' }
      ],
      query: '',
      filter: 'all',
      filters: [{ value: 'all', label: '全部' }, { value: 'active', label: '进行中' }, { value: 'warning', label: '需关注' }],
      sortKey: 'score',
      selectedId: 0,
      loading: false,
      errorMessage: '',
      lastUpdated: '10:20',
      page: 1,
      pageSize: 2,
      timer: null
    };
  },
  computed: {
    filteredRecords() {
      const keyword = this.query.trim().toLowerCase();
      return this.records.filter(record => (this.filter === 'all' || record.status === this.filter) && (!keyword || record.name.toLowerCase().indexOf(keyword) >= 0));
    },
    visibleRecords() {
      const records = this.filteredRecords.slice();
      records.sort((a, b) => this.sortKey === 'score' ? b.value - a.value : a.name.localeCompare(b.name));
      return records.slice((this.page - 1) * this.pageSize, this.page * this.pageSize);
    },
    summaryCards() {
      return [
        { key: 'total', label: '项目总数', value: this.records.length, note: '当前范围' },
        { key: 'active', label: '进行中', value: this.records.filter(item => item.status === 'active').length, note: '持续跟进' },
        { key: 'warning', label: '需关注', value: this.records.filter(item => item.status === 'warning').length, note: '优先处理' }
      ];
    },
    totalPages() {
      return Math.max(1, Math.ceil(this.filteredRecords.length / this.pageSize));
    },
    sortLabel() {
      return this.sortKey === 'score' ? '评分' : '名称';
    }
  },
  mounted() {
    this.timer = setInterval(this.refreshData, this.refreshInterval);
  },
  beforeDestroy() {
    clearInterval(this.timer);
  },
  methods: {
    updateQuery(event) { this.query = event.target.value; this.page = 1; },
    setFilter(value) { this.filter = value; this.page = 1; },
    selectRecord(record) { this.selectedId = record.id; this.$emit('select', record); },
    changeSort() { this.sortKey = this.sortKey === 'score' ? 'name' : 'score'; },
    nextPage() { this.page = Math.min(this.totalPages, this.page + 1); },
    previousPage() { this.page = Math.max(1, this.page - 1); },
    statusText(status) { return { active: '进行中', warning: '需关注', stable: '稳定' }[status] || status; },
    acknowledge(id) { this.records = this.records.map(item => item.id === id ? Object.assign({}, item, { status: 'active' }) : item); },
    exportReport() { this.$emit('export', this.filteredRecords); },
    async refreshData() {
      if (this.loading) return;
      this.loading = true;
      this.errorMessage = '';
      await Promise.resolve();
      this.lastUpdated = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
      this.loading = false;
    }
  }
};
</script>

<style scoped>
.operations-board { width: 760px; padding: 22px; border: 1px solid #d9dee7; border-radius: 8px; background: #f7f9fc; color: #17212b; font-family: Arial, sans-serif; }
.board-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.title-block h1 { margin: 3px 0; font-size: 25px; }
.eyebrow { color: #506176; font-size: 12px; }
.header-actions { display: flex; gap: 8px; }
.header-actions button, .board-footer button { padding: 8px 12px; border: 1px solid #aab4c2; border-radius: 5px; background: #ffffff; cursor: pointer; }
.summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 20px 0; }
.summary-card { padding: 14px; border-left: 3px solid #2563eb; background: #ffffff; }
.summary-card strong { display: block; margin: 6px 0; font-size: 24px; }
.toolbar { display: grid; grid-template-columns: 1fr auto auto; align-items: end; gap: 10px; margin-bottom: 14px; }
.filter-group { display: flex; gap: 4px; }
.filter-group button.active { background: #1d4ed8; color: #ffffff; }
.error-banner { padding: 10px; background: #fee2e2; color: #991b1b; }
.record-panel { overflow: hidden; border: 1px solid #d9dee7; background: #ffffff; }
.record-head, .record-row { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; align-items: center; gap: 10px; padding: 11px 13px; }
.record-row { border-top: 1px solid #edf0f4; cursor: pointer; }
.record-row.selected { background: #eff6ff; }
.status-badge.warning { color: #b45309; }
.score-cell { display: flex; align-items: center; justify-content: space-between; }
.empty-panel { padding: 30px; text-align: center; color: #687588; }
.board-footer { display: flex; justify-content: space-between; margin-top: 14px; }
</style>
